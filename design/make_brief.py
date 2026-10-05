"""Writes boards/merch_moon_light/board.json: Luna, the night-light moon (heypcb.ai merch 06).

    "$KICAD_PYTHON" boards/merch_moon_light/make_brief.py

A sleepy crescent moon for the bedside or a kid's room. When the room goes dark, eight orange LEDs
along its inner curve fade up to a candle-coloured glow (no blue light), then fade out slowly after a
sleep timer. Pat its gold cheek to switch it on or off by hand. An APDS-9306 measures the room light;
a CH32V003 runs it from a 3.3 V LDO on USB-C. It hangs from a nail by its keyhole. Edit this file,
not board.json. Frame 66 x 74 mm, origin top-left, y down.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import merch_kit as K  # noqa: E402

SLUG = "moon-light"
W, H = 66.0, 74.0
OUT_C, OUT_R = (33.0, 37.0), 31.0
IN_C, IN_R = (47.0, 31.0), 25.0
LED_R = IN_R + 3.0
LED_ANGLES = [220.0 - 13.0 * k for k in range(8)]

MCU_PINS = {"U?.14": "LED_PWM", "U?.20": "SDA", "U?.19": "SCL", "U?.6": "TOUCH"}
MCU_NC = ["U?.%d" % p for p in (1, 2, 3, 4, 5, 8, 10, 11, 12, 13, 15, 16, 17)]

BLOCKS = [
    {"block": "usb_c_data_5v", "as": "usb", "title": "USB-C: 5 V in (data pins unused)",
     "nets": {"USB_DP": "USB_DP", "USB_DM": "USB_DM"}},
    {"block": "quackface_ldo_xc6206", "as": "ldo", "title": "3.3 V for the MCU and the light sensor (XC6206)",
     "nets": {"5V": "VBUS"}},
    {"block": "merch_mcu_ch32v003", "as": "mcu", "title": "CH32V003: light, touch, fade, sleep timer",
     "nets": {"VDD": "3V3"}, "pinNets": MCU_PINS, "no_connect": MCU_NC},
    {"block": "merch_apds9306", "as": "als", "title": "APDS-9306: how dark is the room", "nets": {"SDA": "SDA", "SCL": "SCL"}},
    {"block": "merch_touch_pad", "as": "cheek", "title": "Gold cheek: the touch switch", "nets": {"TOUCH": "TOUCH"}},
    {"block": "merch_lowside_fet", "as": "fet", "title": "The glow's PWM switch", "nets": {"LOAD": "LED_K", "EN": "LED_PWM"}},
] + [{"block": "merch_led_from_rail", "as": "glow%d" % k, "title": "Glow LED %d (orange)" % k,
      "nets": {"LED_K": "LED_K"}} for k in range(8)]

# ---------------------------------------------------------------------------------------- outline
outer = K.Shape.circle(OUT_C[0], OUT_C[1], OUT_R)
inner = K.Shape.circle(IN_C[0], IN_C[1], IN_R)
usb_flat = K.Shape.rect(25.0, 56.0, 41.0, 68.6)
outline = ((outer - inner) | usb_flat).rounded(2.0)
KEY_C = (9.5, 44.0)                     # near the centre of mass, so it hangs level
keyhole = K.Shape.circle(KEY_C[0], KEY_C[1], 3.5) | K.Shape.capsule(KEY_C[0], KEY_C[1], KEY_C[0], KEY_C[1] - 4.7, 3.6)


def polar(r, deg):
    return IN_C[0] + r * math.cos(math.radians(deg)), IN_C[1] + r * math.sin(math.radians(deg))


# ---------------------------------------------------------------------------------------- parts
parts = K.design_footprints(BLOCKS, os.path.join(os.path.dirname(HERE), "..", "blocks"))
L = K.Layout(parts)
for k, deg in enumerate(LED_ANGLES):
    x, y = polar(LED_R, deg)
    radial_horizontal = abs(math.cos(math.radians(deg))) >= 0.707
    rot = 0 if radial_horizontal else 90             # both parts lie radially, thin along the arc
    L.lock("glow%d:D?" % k, x, y, rot, "glow LED %d along the inner curve, like a ray" % k)
    rx, ry = polar(LED_R, deg - 6.5)
    L.lock("glow%d:R?" % k, rx, ry, rot, "its 220 ohm, next along the arc")
L.lock("usb:J?", 33.0, 68.6 + 0.6 - 4.2, 0, "USB-C on the bottom flat, mouth down", overhang=True)
L.lock("usb:C?", 25.0, 62.0, 90, "VBUS bulk")
L.lock("usb:R1?", 40.8, 61.8, 0, "CC1 5.1k")
L.lock("usb:R2?", 40.8, 63.6, 0, "CC2 5.1k")
L.lock("ldo:U?", 21.0, 58.6, 0, "3.3 V LDO")
L.lock("ldo:C1?", 28.6, 56.2, 0, "")
L.lock("ldo:C2?", 17.4, 60.6, 90, "")
L.lock("fet:Q?", 24.6, 53.8, 0, "the glow switch, beside the MCU")
L.lock("fet:R?", 32.4, 57.6, 0, "gate pull-down")
L.lock("mcu:U?", 16.0, 52.0, 0, "MCU low in the moon's thick part")
L.lock("mcu:C?", 16.0, 47.0, 0, "bypass")
for i in range(3):
    L.lock("mcu:TP%d?" % (i + 1), 12.4 + 2.54 * i, 56.62, 0, "SWIO pads (VDD, SWIO, GND)")
L.lock("als:U?", 10.4, 20.8, 0, "the light sensor on the forehead")
L.lock("als:C?", 13.4, 20.8, 90, "")
L.lock("als:R1?", 9.6, 24.6, 0, "SDA pull-up, by the sensor")
L.lock("als:R2?", 12.8, 24.6, 0, "SCL pull-up")
L.lock("cheek:TP?", 7.6, 33.4, 0, "the gold cheek: pat it")
L.lock("cheek:R?", 7.6, 29.4, 0, "")

# ---------------------------------------------------------------------------------------- art
art = []
EYE = (13.4, 28.6)
art += K.silk_line(K.arc_points(EYE[0], EYE[1], 2.4, 20, 160, 14), "eye", 0.3)          # a sleeping eye
for a in (40.0, 90.0, 140.0):                                                       # its lashes
    x0, y0 = EYE[0] + 2.4 * math.cos(math.radians(a)), EYE[1] + 2.4 * math.sin(math.radians(a))
    art += K.silk_line([(x0, y0), (x0 + 1.0 * math.cos(math.radians(a)), y0 + 1.0 * math.sin(math.radians(a)))],
                       "lash", 0.2)
art += K.silk_line(K.arc_points(13.0, 34.6, 2.0, 30, 150, 12), "smile", 0.3)
art += K.text("z", 16.8, 15.8, size=1.1, italic=True, name="z1")
art += K.text("z", 19.8, 12.8, size=1.4, italic=True, name="z2")
art += K.text("Z", 23.4, 9.8, size=1.7, italic=True, name="z3")
for (sx, sy, r) in ((28.6, 9.0, 1.3), (45.8, 62.4, 1.0), (8.8, 52.4, 1.0)):
    art += K.gold(K.star(sx, sy, r), "star")
art += K.text("heypcb.ai", 47.2, 59.6, size=0.8, name="brand_front")
# back: QR, how it works, the brand
art += K.qr(K.world_url(SLUG), 19.5, 53.5, size=10.0, side="B")
for i, line in enumerate(["glows when the room", "goes dark, fades out", "after 45 min", "pat my cheek: on / off",
                          "hold: 15 / 45 / 90 min"]):
    art += K.text(line, 12.6, 27.0 + 1.9 * i, size=0.9, side="B", name="howto%d" % i)
art += K.text("heypcb.ai", 47.4, 59.8, size=1.0, side="B", bold=True, name="brand_back")

keep = {"keyhole": keyhole.offset(0.5)}
for i, it in enumerate(a for a in art if "F.Cu" in a.get("layers", [])):
    keep["gold%d" % i] = K.Shape.poly(it["points"]).offset(0.3)
if os.environ.get("MERCH_PREVIEW"):
    K.preview(os.environ["MERCH_PREVIEW"], outline - keyhole, L, art, keep)
K.check_art(outline - keyhole, art)
L.check(outline - keyhole, edge=0.5, keep=keep)

brief = {
    "name": "moon_light",
    "title": "Luna - night-light moon: auto-on amber glow, light sensor, touch, sleep timer, USB-C",
    "revision": "A",
    "brief": "A crescent-moon night light on USB-C. An APDS-9306 measures the room's light over I2C; when it goes "
             "dark a CH32V003 (3.3 V from an XC6206) fades eight orange 605 nm LEDs, each with its own 220 ohm from 5 V, "
             "up through one AO3400A on a PWM pin, and fades them out after a sleep timer. A gold touch pad on the "
             "moon's cheek switches it by hand and sets the timer. A keyhole cutout hangs it on a nail. 2 layers, "
             "single-sided SMT, blue mask, ENIG.",
    "blocks": BLOCKS,
    "pwrFlags": ["GND", "VBUS"],
    "netClasses": [],
    "board": {
        "width": W, "height": H, "corner_radius": 0.0, "layers": 2, "origin": [100.0, 100.0],
        "shape": {"type": "polygon", "points": K.outline_points(outline), "fillet": 0},
        "cutouts": [{"type": "polygon", "points": K.outline_points(keyhole), "fillet": 0}],
        "rules": {"clearance": 0.2, "track": 0.2, "via": [0.6, 0.3], "edge_clearance": 0.5,
                  "hole_to_hole": 0.5, "min_through_hole": 0.3, "min_track": 0.15},
        "finish": {"mask": "Blue", "silk": "White", "copper": "ENIG",
                   "why": "a moon in the night sky: gold stars, white ink"},
        "unpoured": ["F.Cu"],
        "notes": "2 layers; the face is unpoured, GND plane on the back. The keyhole is a polygon cutout.",
    },
    "placement": L.locks,
    "route": {"passes": 30, "fanout": True, "solve_s": 240},
    "stitch_pitch": 6.0,
    "silk": {"designators": "hide",
             "title": [{"text": "Luna", "y": 24.0, "size": 1.8, "bold": True},
                       {"text": "night light  rev {revision}", "y": 26.6, "size": 0.9}]},
    "art": art,
    "captions": {"done_3d": "Luna: eight amber LEDs on the inner curve, a light sensor, a gold touch cheek."},
}
K.write_brief(os.path.join(HERE, "board.json"), brief)
print("wrote board.json: %d outline points, %d art items, %d locks, QR -> %s"
      % (len(brief["board"]["shape"]["points"]), len(art), len(L.locks), K.world_url(SLUG)))
