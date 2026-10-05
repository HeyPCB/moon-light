# 06 · Luna, the night-light moon: SPEC

## Who it's for, and the use case

Parents of small children, anyone who gets up at night, and anyone who sleeps better with a little
light. Luna hangs by the bed, the crib-side wall or the hallway, switches itself on when the room goes
dark, glows a warm amber that doesn't wake you up the way white light does, and fades out by itself
once you (or the kid) have fallen asleep. It stays off for the rest of the night and re-arms in the
morning.

## The cute concept

A sleepy crescent moon on a night-blue board: one closed eye with lashes, a little smile, a round gold
cheek, "z z Z" floating off its forehead and gold stars around it. Eight orange LEDs along its inner
curve glow like a soft halo. Pat its cheek to switch it by hand.

## Features

| | |
|---|---|
| Light | 8 orange 605 nm LEDs (XL-1608UOC), each with its own 220 Ω from 5 V, switched together by an AO3400A on a 1 kHz PWM pin; fades with a square-law curve so they look even. No blue light. |
| Auto on | an APDS-9306 ambient light sensor read once a second; 20 s of darkness fades the glow up over 3 s |
| Sleep timer | 15, 45 (default) or 90 minutes, then a 2-minute fade to dark; it stays off until the room sees daylight again |
| Touch | the gold cheek (ADC touch): pat = on/off, hold 1.5 s = next timer (1/2/3 blinks) |
| MCU | CH32V003F4P6 at 3.3 V from an XC6206 LDO (Basic); the LEDs run from 5 V |
| Power | USB-C, any phone charger |
| Board | 2 layers, blue mask, white silk, ENIG; single-sided SMT, 32 placed parts; keyhole cutout for a nail; QR on the back |

## Power budget

USB-powered. Each LED ≈ 13 mA at full on ((5 V - 2.1 V) / 220 Ω); the default glow is 60 % perceived,
36 % duty, so the string draws ≈ 38 mA. CH32V003 at 48 MHz ≈ 3 mA, APDS-9306 ≈ 0.1 mA, LDO quiescent
negligible.

| State | Current at 5 V | Power |
|---|---|---|
| Waiting (dark or day) | ≈ 4 mA | ≈ 20 mW (about 0.18 kWh a year) |
| Glowing (default) | ≈ 42 mA | ≈ 0.21 W |
| Full brightness (not used by default) | ≈ 110 mA | ≈ 0.55 W |

A 45-minute night costs about 0.16 Wh. Design estimates from datasheet typicals; no Luna has been built.

## BOM (100 units, live JLC/LCSC prices read 2026-10-05)

| Refs | Value | Qty | LCSC | MPN | Class | Unit @100 | Line |
|---|---|---|---|---|---|---|---|
| C1 | 10uF | 1 | C15850 | CL21A106KAYNNNE | basic | $0.0773 | $0.0773 |
| C2,C3 | 1uF | 2 | C15849 | CL10A105KB8NNNC | basic | $0.0297 | $0.0594 |
| C4 | 100nF | 1 | C14663 | CC0603KRX7R9BB104 | basic | $0.0106 | $0.0106 |
| C5 | 1uF 0402 | 1 | C52923 | CL05A105KA5NQNC | basic | $0.0143 | $0.0143 |
| D1-D8 | Orange | 8 | C965800 | XL-1608UOC-06 | extended | $0.0071 | $0.0568 |
| J1 | USB-C | 1 | C165948 | TYPE-C-31-M-12 | extended | $0.1468 | $0.1468 |
| Q1 | AO3400A | 1 | C20917 | AO3400A | basic | $0.0682 | $0.0682 |
| R1,R2 | 5.1k | 2 | C25905 | 0402WGF5101TCE | basic | $0.0009 | $0.0018 |
| R3,R4 | 10k | 2 | C25744 | 0402WGF1002TCE | basic | $0.0029 | $0.0058 |
| R5 | 1k | 1 | C21190 | 0603WAF1001T5E | basic | $0.0039 | $0.0039 |
| R6 | 100k | 1 | C25803 | 0603WAF1003T5E | basic | $0.0016 | $0.0016 |
| R7-R14 | 220 | 8 | C22962 | 0603WAF2200T5E | basic | $0.0014 | $0.0112 |
| U1 | XC6206P332MR | 1 | C5446 | XC6206P332MR-G | basic | $0.0962 | $0.0962 |
| U2 | CH32V003F4P6 | 1 | C5187096 | CH32V003F4P6 | extended | $0.2227 | $0.2227 |
| U3 | APDS-9306-065 | 1 | C2649498 | APDS-9306-065 | extended | $0.5304 | $0.5304 |
| | **Parts** | | | | | | **$1.31** |
| | Extended-part loading fee ($3 x 4 / 100 boards) | | | | | | $0.12 |
| | **BOM per board @100** | | | | | | **$1.43** |

Not in the BOM: the PCB (2 layers, ENIG, 54.0 x 62.7 mm), assembly labour and a USB-C cable. TP1-TP4
are copper pads. Machine-readable: [`bom_cost.json`](bom_cost.json).

## Dimensions

54.0 x 62.7 mm (Edge.Cuts bounding box, pcbnew), 13.9 cm² (it's a crescent), 1.6 mm FR4. Keyhole: a
7 mm head opening and a 3.6 mm slot.

## Mounting plan (no enclosure)

Hang it on a small nail or screw through the keyhole: the hole sits near the moon's centre of mass, so it
hangs level, and the slot locks the screw head. The USB-C cable leaves straight down from its bottom.
It also lies flat on a nightstand. For a child's room, mount it out of reach and route the cable along the
wall, as with any corded night light.

## Safety

5 V USB only. Every corner of the outline is rounded (2 mm minimum; the crescent's two horn tips are
fully round). The LEDs are dimmed and spread over the board, about 0.2 W in all, so nothing gets warm.
No blue or white LEDs: the light is orange (605 nm).

## Verification (measured by KiCad 10.0.6 on the files in this folder)

ERC 0 errors · netlist round trip identical (22 nets) · routing 67 → 0 open (240 tracks, 13 vias) · DRC
0 errors / 0 unconnected / 0 parity, 1 warning (`lib_footprint_mismatch` on the USB-C: its overhanging
footprint silk clipped) · DFM `jlcpcb_2layer` 0 errors · fab gate ready · QR modules 0.345 mm. Full
numbers: [`report.json`](report.json), [`measured.json`](measured.json).

Two routing attempts before this one left one connection open (the FET's gate across the LED string,
then SCL past the keyhole); moving the FET next to the MCU and the bit-banged I²C to the MCU's top-right
pins gave 0 open.

**Not built yet.** Not fabricated, assembled or powered; the firmware compiles but has not run on
hardware. Tune `DARK`, `DAYLIGHT` and the touch threshold on the first prototype in a real bedroom.
