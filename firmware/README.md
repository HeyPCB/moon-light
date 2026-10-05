# Luna firmware (CH32V003)

One file, [`luna.c`](luna.c), on [ch32fun](https://github.com/cnlohr/ch32fun) (MIT): startup code,
registers, the bit-banged I²C (`extralibs/static_i2c.h`) and the ADC touch routine
(`extralibs/ch32v00x_touch.h`). The comments at the top of the file say what it does.

## Build

```sh
git clone https://github.com/cnlohr/ch32fun
make build CH32FUN=/path/to/ch32fun/ch32fun PREFIX=/path/to/bin/riscv-none-elf
```

Always name the `build` target: ch32fun's own default target flashes the chip.

Built on 2026-10-05 with xPack riscv-none-elf-gcc 15.2.0 and ch32fun at commit 6b247c7:

```
Memory region         Used Size  Region Size  %age Used
           FLASH:        3216 B        16 KB     19.63%
             RAM:         472 B         2 KB     23.05%
```

[`luna.hex`](luna.hex) and [`luna.bin`](luna.bin) are that build. The two compiler warnings come from
ch32fun itself (an unused `ReadTouchPinSafe` and its RWX linker note).

## Flash

A WCH-LinkE on the three SWIO pads (VDD, SWIO, GND) under the MCU: `make flash CH32FUN=...`.

## Status

Compiled, not run on hardware. Tune in a real bedroom: `DARK` (the ALS count below which the room counts
as dark), `DAYLIGHT` (the re-arm level, far above the moon's own glow on the walls) and the touch
threshold. The final 2-minute fade blocks the touch pad until it finishes.

## License

MIT (see [`LICENSE`](LICENSE)).
