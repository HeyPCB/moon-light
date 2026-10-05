"""Shared geometry, art and brief helpers for the heypcb.ai merch boards (boards/merch_*/make_brief.py).

Runs under KiCad's Python, because the outlines are built with pcbnew's own polygon booleans
(SHAPE_POLY_SET) and the pre-checks load the real footprints from KiCad's libraries:

    "$KICAD_PYTHON" boards/merch_<name>/make_brief.py

Frame: mm from the board frame's top-left corner, y down, the frame of `placement` locks (with
"from_center": false) and of `art` items. Nothing here is a measurement of the finished board: the
checks only stop a bad brief before the pipeline spends a routing run on it. DRC measures it all again.
"""
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pcbnew  # noqa: E402

from heypcb_kicad import env  # noqa: E402

NM = 1e6
ERR = 0.01          # mm, arc approximation error for outlines and art


def world_id(slug: str) -> str:
    """Circuit World's board id for github.com/HeyPCB/<slug>: the first 12 hex of sha256 of the
    lowercased canonical URL (HeyPCB scripts/import-world-boards.mjs)."""
    return hashlib.sha256(("https://github.com/heypcb/%s" % slug).lower().encode()).hexdigest()[:12]


def world_url(slug: str) -> str:
    return "https://heypcb.ai/world/b/" + world_id(slug)


# ------------------------------------------------------------------------------------------ shapes
class Shape(object):
    """A region in the frame (mm), backed by a SHAPE_POLY_SET in nm."""

    def __init__(self, ps=None):
        self.ps = ps if ps is not None else pcbnew.SHAPE_POLY_SET()

    @staticmethod
    def poly(points):
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        for x, y in points:
            ps.Append(int(round(x * NM)), int(round(y * NM)))
        return Shape(ps)

    @staticmethod
    def ellipse(cx, cy, rx, ry=None, rot=0.0, n=None):
        ry = rx if ry is None else ry
        n = n or max(48, int(2 * math.pi * max(rx, ry) / 0.25))
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = rx * math.cos(a), ry * math.sin(a)
            pts.append((cx + x * c - y * s, cy + x * s + y * c))
        return Shape.poly(pts)

    circle = ellipse

    @staticmethod
    def rect(x0, y0, x1, y1, r=0.0):
        s = Shape.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        return s.rounded(r) if r > 0 else s

    @staticmethod
    def capsule(x0, y0, x1, y1, w):
        """A stroke from (x0, y0) to (x1, y1), w wide, round ends."""
        a = math.atan2(y1 - y0, x1 - x0)
        nx, ny = -math.sin(a) * w / 2, math.cos(a) * w / 2
        s = Shape.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)])
        return s | Shape.circle(x0, y0, w / 2) | Shape.circle(x1, y1, w / 2)

    def copy(self):
        return Shape(self.ps.CloneDropTriangulation())

    def __or__(self, other):
        p = self.copy()
        p.ps.BooleanAdd(other.ps)
        return p

    def __sub__(self, other):
        p = self.copy()
        p.ps.BooleanSubtract(other.ps)
        return p

    def __and__(self, other):
        p = self.copy()
        p.ps.BooleanIntersection(other.ps)
        return p

    def offset(self, d):
        p = self.copy()
        p.ps.Inflate(int(round(d * NM)), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, int(ERR * NM))
        return p

    def rounded(self, r):
        """Every convex corner rounded to r, then every concave one: an edge a hand never catches on."""
        return self.offset(-r).offset(r).offset(r).offset(-r)

    def rings(self):
        """[(outline points, [hole points, ...]), ...] in mm."""
        out = []
        for oi in range(self.ps.OutlineCount()):
            ring = self.ps.Outline(oi)
            pts = [(ring.CPoint(k).x / NM, ring.CPoint(k).y / NM) for k in range(ring.PointCount())]
            holes = []
            for hi in range(self.ps.HoleCount(oi)):
                h = self.ps.Hole(oi, hi)
                holes.append([(h.CPoint(k).x / NM, h.CPoint(k).y / NM) for k in range(h.PointCount())])
            out.append((pts, holes))
        return out

    def simplified(self, tol=0.008):
        """Every outline and hole decimated to `tol` mm (Douglas-Peucker), as a new shape."""
        ps = pcbnew.SHAPE_POLY_SET()
        for pts, holes in self.rings():
            ps.NewOutline()
            for x, y in _ring_simplify(pts, tol):
                ps.Append(int(round(x * NM)), int(round(y * NM)))
            for h in holes:
                hi = ps.NewHole()                  # Append's hole index -1 is the outline itself
                for x, y in _ring_simplify(h, tol):
                    ps.Append(int(round(x * NM)), int(round(y * NM)), -1, hi)
        return Shape(ps)

    def fractured(self, tol=0.008):
        """Outlines with every hole bridged in (KiCad's Fracture), each a plain point list for an art poly."""
        p = self.simplified(tol) if tol else self.copy()
        p.ps.Fracture()
        return [pts for pts, _ in p.rings()]

    def largest(self):
        """The region of the shape with the largest area (drops slivers a subtraction leaves)."""
        best, area = None, -1.0
        for oi in range(self.ps.OutlineCount()):
            ps = pcbnew.SHAPE_POLY_SET()
            ps.AddOutline(self.ps.Outline(oi))
            for hi in range(self.ps.HoleCount(oi)):
                ps.AddHole(self.ps.Hole(oi, hi))
            a = ps.Area()
            if a > area:
                best, area = ps, a
        return Shape(best if best is not None else pcbnew.SHAPE_POLY_SET())

    def bbox(self):
        b = self.ps.BBox()
        return (b.GetX() / NM, b.GetY() / NM, b.GetRight() / NM, b.GetBottom() / NM)

    def area(self):
        return self.ps.Area() / (NM * NM)

    def contains(self, x, y):
        return self.ps.Contains(pcbnew.VECTOR2I(int(x * NM), int(y * NM)))


def simplify(points, tol=0.008):
    """Douglas-Peucker on an open point list: drop points within `tol` mm of the chord."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (x0, y0), (x1, y1) = points[i], points[j]
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1e-12
        best, idx = -1.0, None
        for k in range(i + 1, j):
            d = abs(dy * (points[k][0] - x0) - dx * (points[k][1] - y0)) / n
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(points, keep) if k]


def _ring_simplify(ring, tol):
    if len(ring) < 8:
        return ring
    far = max(range(len(ring)), key=lambda k: (ring[k][0] - ring[0][0]) ** 2 + (ring[k][1] - ring[0][1]) ** 2)
    return simplify(ring[:far + 1], tol)[:-1] + simplify(ring[far:] + [ring[0]], tol)[:-1]


def outline_points(shape: Shape, ndigits=3, tol=0.008):
    """The single outline of a board shape, as board.shape points (holes are refused: use cutouts),
    simplified to `tol` mm."""
    rings = shape.rings()
    if len(rings) != 1 or rings[0][1]:
        raise ValueError("a board outline must be one region without holes (got %d regions)" % len(rings))
    # split the closed ring at its two farthest-apart points so the simplifier keeps both
    raw = _ring_simplify(rings[0][0], tol)
    pts = []
    for x, y in raw:
        p = [round(x, ndigits), round(y, ndigits)]
        if not pts or p != pts[-1]:
            pts.append(p)
    if pts[0] == pts[-1]:
        pts.pop()
    return pts


# ------------------------------------------------------------------------------------------ art
def _pts(points, nd=3):
    return [[round(x, nd), round(y, nd)] for x, y in points]


def _polys(shape: Shape, layers, name, extra):
    """One art poly per region of the shape, its holes as real holes (art.py `holes`), not fractured:
    a fracture's zero-width bridge renders as a seam (air_ghost's eye sparkle, 2026-10-05)."""
    out = []
    for i, (pts, holes) in enumerate(shape.simplified().rings()):
        it = {"kind": "poly", "layers": layers, "points": _pts(pts), "fill": True, "name": "%s.%d" % (name, i)}
        if holes:
            it["holes"] = [_pts(h) for h in holes]
        it.update(extra)
        out.append(it)
    return out


def gold(shape: Shape, name, side="F", grow=0.05):
    """ENIG art: the shape on copper, its mask opened over it (art.py adds the copper's rule area)."""
    return _polys(shape, ["%s.Cu" % side, "%s.Mask" % side], name, {"mask_grow": grow})


def silk_fill(shape: Shape, name, side="F"):
    return _polys(shape, ["%s.SilkS" % side], name, {})


def silk_line(points, name, width=0.2, side="F", closed=False):
    pts = list(points) + ([points[0]] if closed else [])
    return [{"kind": "polyline", "layers": ["%s.SilkS" % side], "points": _pts(pts), "width": width, "name": name}]


def silk_ring(shape: Shape, name, width=0.2, side="F"):
    """Every outline (and hole) of a shape as a closed silk line."""
    out = []
    for i, (pts, holes) in enumerate(shape.simplified().rings()):
        out += silk_line(pts, "%s.%d" % (name, i), width, side, closed=True)
        for j, h in enumerate(holes):
            out += silk_line(h, "%s.%d.h%d" % (name, i, j), width, side, closed=True)
    return out


def arc_points(cx, cy, r, a0, a1, n=24):
    """Points along a circle arc, degrees, y down (0 = +x, 90 = +y)."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def text(s, x, y, size=1.2, side="F", bold=False, italic=False, layers=None, justify="center", angle=0,
         knockout=False, name=None):
    return [{"kind": "text", "layers": layers or ["%s.SilkS" % side], "text": s, "at": [round(x, 3), round(y, 3)],
             "size": size, "bold": bold, "italic": italic, "justify": justify, "angle": angle,
             "knockout": knockout, "name": name or s}]


def qr(url, x, y, size=11.0, side="B", ecc="M", margin=0.8):
    return [{"kind": "qr", "layers": ["%s.SilkS" % side], "text": url, "at": [round(x, 3), round(y, 3)],
             "size": size, "ecc": ecc, "knockout": True, "margin": margin, "name": "qr"}]


def heart(cx, cy, s):
    """A heart s mm wide, point down."""
    r = s / 4.0
    h = Shape.circle(cx - r, cy - r * 0.3, r) | Shape.circle(cx + r, cy - r * 0.3, r)
    tri = Shape.poly([(cx - 2 * r, cy - 0.1 * r), (cx + 2 * r, cy - 0.1 * r), (cx, cy + 1.9 * r)])
    return (h | tri).rounded(min(0.25, r * 0.3))


def star(cx, cy, r_out, r_in=None, n=5, rot=-90.0, round_r=0.2):
    r_in = r_in or r_out * 0.45
    pts = []
    for k in range(2 * n):
        r = r_out if k % 2 == 0 else r_in
        a = math.radians(rot + 180.0 * k / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    s = Shape.poly(pts)
    return s.rounded(round_r) if round_r else s


# ------------------------------------------------------------------------------------------ checks
def footprint_at(fpid, x, y, rot, side="top"):
    lib, name = fpid.split(":", 1)
    fp = pcbnew.FootprintLoad(str(env.FOOTPRINT_DIR / (lib + ".pretty")), name)
    if fp is None:
        raise KeyError("footprint %s not found" % fpid)
    fp.SetPosition(pcbnew.VECTOR2I(int(x * NM), int(y * NM)))
    fp.SetOrientationDegrees(rot)
    if side == "bottom":
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    return fp


def courtyard(fp):
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    if cy.OutlineCount():
        return Shape(cy.CloneDropTriangulation())
    b = fp.GetBoundingBox(False)
    return Shape.rect(b.GetX() / NM, b.GetY() / NM, b.GetRight() / NM, b.GetBottom() / NM)


def pads_shape(fp, margin=0.0):
    s = pcbnew.SHAPE_POLY_SET()
    for p in fp.Pads():
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(lid):
                p.TransformShapeToPolygon(s, lid, int(margin * NM), int(ERR * NM), pcbnew.ERROR_OUTSIDE)
    return Shape(s)


def pad_xy(fp, number):
    for p in fp.Pads():
        if p.GetNumber() == str(number):
            q = p.GetPosition()
            return (q.x / NM, q.y / NM)
    raise KeyError("pad %s of %s" % (number, fp.GetFPIDAsString()))


class Layout(object):
    """Locks plus the footprints they place, for checks and for reading pad positions."""

    def __init__(self, design_parts):
        self.parts = design_parts      # {"alias:TOKEN": footprint id}
        self.locks = {}
        self.fps = {}
        self.overhang = set()

    def lock(self, key, x, y, rot=0, why="", side="top", overhang=False):
        """`overhang`: an edge connector whose mouth sits proud of the outline on purpose; its
        courtyard may leave the outline (its pads may not)."""
        if key not in self.parts:
            raise KeyError("no part %s in the design" % key)
        if rot not in (0, 90, 180, 270):
            raise ValueError("%s: rot %s is not a quarter turn (the SDK takes 0/90/180/270 only)" % (key, rot))
        self.locks[key] = {"lock": [round(x, 3), round(y, 3)], "rot": rot, "from_center": False,
                           "why": why}
        if side == "bottom":
            self.locks[key]["side"] = "bottom"
        self.fps[key] = footprint_at(self.parts[key], x, y, rot, side)
        if overhang:
            self.overhang.add(key)
        return self.fps[key]

    def check(self, outline: Shape, edge=0.5, keep=None):
        """Raise on overlapping courtyards (same face), a pad closer than `edge` to the outline, a
        courtyard leaving the outline, or a part on a `keep` region (dict name -> Shape)."""
        problems = []
        inner = outline.offset(-edge)
        keys = sorted(self.fps)
        cys = {k: courtyard(self.fps[k]) for k in keys}
        for i, a in enumerate(keys):
            pa = pads_shape(self.fps[a])
            if (pa - inner).area() > 1e-4:
                problems.append("%s: a pad is within %.2f mm of the edge or outside" % (a, edge))
            if a not in self.overhang and (cys[a] - outline).area() > 1e-3:
                problems.append("%s: courtyard leaves the outline" % a)
            for b in keys[i + 1:]:
                if self.fps[a].IsFlipped() != self.fps[b].IsFlipped():
                    continue
                if (cys[a] & cys[b]).area() > 1e-4:
                    problems.append("courtyards overlap: %s / %s" % (a, b))
            for name, region in (keep or {}).items():
                if (cys[a] & region).area() > 1e-4:
                    problems.append("%s sits on %s" % (a, name))
        if problems:
            raise SystemExit("layout check failed:\n  " + "\n  ".join(problems))
        return True


def check_art(outline: Shape, art, edge=0.5):
    """Raise on art polygons that leave the outline (copper by `edge`, silk and mask by 0.3 mm), the same
    rule art.py applies at the board stage; text is checked there, by its rendered strokes."""
    bad = []
    inner = {"cu": outline.offset(-edge), "other": outline.offset(-0.3)}
    for it in art:
        if it.get("kind") == "text":
            # an estimate of KiCad's stroke font box: 0.8 x size per character, 1.25 x size tall
            n, sz = len(it["text"]), it.get("size", 1.0)
            w, h = 0.8 * sz * n, 1.25 * sz
            x, y = it["at"]
            jx = {"left": 0.0, "center": -w / 2, "right": -w}[it.get("justify", "center")]
            if abs(it.get("angle", 0)) in (90, 270):
                s = Shape.rect(x - h / 2, y - w / 2, x + h / 2, y + w / 2)
            else:
                s = Shape.rect(x + jx, y - h / 2, x + jx + w, y + h / 2)
        elif it.get("kind") == "qr":
            half = it["size"] / 2 + it.get("margin", 0.8)
            x, y = it["at"]
            s = Shape.rect(x - half, y - half, x + half, y + half)
        elif it.get("kind") in ("poly", "circle"):
            s = Shape.poly(it["points"]) if it["kind"] == "poly" else Shape.circle(it["at"][0], it["at"][1], it["r"])
        elif it.get("kind") == "polyline":
            wd = max(it.get("width", 0.15), 0.15)
            pts = it["points"]
            s = Shape.circle(pts[0][0], pts[0][1], wd / 2, n=12)
            for a, b in zip(pts[:-1], pts[1:]):
                s = s | Shape.capsule(a[0], a[1], b[0], b[1], wd)
        else:
            continue
        lim = inner["cu" if any(l.endswith(".Cu") for l in it["layers"]) else "other"]
        if (s - lim).area() > 1e-4:
            bad.append(it.get("name", "?"))
    if bad:
        raise SystemExit("art leaves the outline: %s" % ", ".join(bad))


def preview(path, outline: Shape, layout=None, art=None, keep=None, scale=12.0):
    """An SVG sketch of the outline, every locked part's courtyard and pads, and the art, for looking at a
    placement before the pipeline runs (rsvg-convert it to PNG). A sketch, not a render."""
    x0, y0, x1, y1 = outline.bbox()
    m = 3.0
    w, h = (x1 - x0 + 2 * m) * scale, (y1 - y0 + 2 * m) * scale

    def path_of(s: Shape):
        d = []
        for pts, holes in s.rings():
            for ring in [pts] + holes:
                d.append("M " + " L ".join("%.2f %.2f" % ((x - x0 + m) * scale, (y - y0 + m) * scale)
                                          for x, y in ring) + " Z")
        return " ".join(d)

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (w, h, w, h),
           '<rect width="100%" height="100%" fill="#fff"/>',
           '<path d="%s" fill="#cfe3d4" stroke="#222" stroke-width="2" fill-rule="evenodd"/>' % path_of(outline)]
    for it in art or []:
        if it.get("kind") == "poly":
            s = Shape.poly(it["points"])
            col = "#e0b000" if any(l.endswith(".Cu") for l in it["layers"]) else (
                "#888" if it["layers"][0].startswith("F.") else "none")
            if col != "none":
                out.append('<path d="%s" fill="%s" opacity="0.8"/>' % (path_of(s), col))
        elif it.get("kind") == "polyline" and it["layers"][0].startswith("F."):
            pts = " ".join("%.2f,%.2f" % ((x - x0 + m) * scale, (y - y0 + m) * scale) for x, y in it["points"])
            out.append('<polyline points="%s" fill="none" stroke="#555" stroke-width="%.1f"/>'
                       % (pts, max(1.0, it.get("width", 0.2) * scale)))
    for name, s in (keep or {}).items():
        out.append('<path d="%s" fill="none" stroke="#c00" stroke-dasharray="4 3" stroke-width="1"/>' % path_of(s))
    for key, fp in sorted((layout.fps if layout else {}).items()):
        out.append('<path d="%s" fill="none" stroke="#06c" stroke-width="1.2"/>' % path_of(courtyard(fp)))
        out.append('<path d="%s" fill="#b87333"/>' % path_of(pads_shape(fp)))
        p = fp.GetPosition()
        out.append('<text x="%.1f" y="%.1f" font-size="11" fill="#036" text-anchor="middle">%s</text>'
                   % ((p.x / NM - x0 + m) * scale, (p.y / NM - y0 + m) * scale - 6, key))
    out.append("</svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    return path


def design_footprints(board_json_blocks, blocks_dir):
    """{"alias:TOKEN": footprint} for a brief's blocks, with the tokens the composer will give them."""
    out = {}
    for inst in board_json_blocks:
        blk = json.load(open(os.path.join(blocks_dir, inst["block"] + ".json")))
        comps = blk["components"]
        counts = {}
        for c in comps:
            counts[c["ref_prefix"]] = counts.get(c["ref_prefix"], 0) + 1
        seen = {}
        for c in comps:
            pre = c["ref_prefix"]
            seen[pre] = seen.get(pre, 0) + 1
            tok = ("%s?" % pre) if counts[pre] == 1 else ("%s%d?" % (pre, seen[pre]))
            out["%s:%s" % (inst["as"], tok)] = c["footprint"]
    return out


def write_brief(path, brief):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(brief, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, path)
