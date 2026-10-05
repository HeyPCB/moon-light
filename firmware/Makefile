# Luna firmware: CH32V003 on ch32fun (https://github.com/cnlohr/ch32fun).
#   make build CH32FUN=/path/to/ch32fun/ch32fun PREFIX=/path/to/bin/riscv-none-elf
#   make flash CH32FUN=...      (minichlink and a WCH-LinkE on the SWIO pad)
# Always name a target: ch32fun's own default target flashes the chip.
all : build

TARGET := luna
TARGET_MCU ?= CH32V003
CH32FUN ?= ../../../../ch32fun/ch32fun
include $(CH32FUN)/ch32fun.mk

flash : cv_flash
clean : cv_clean
