# Linson Writer's Deck - Master-Slave Wiring Guide
## Dual Raspberry Pi Pico 2W Complete Pinout Map

---

## Overview

This document provides complete wiring instructions for the Master-Slave dual Pico 2W architecture.

**Architecture:**
- **Master Pico (rpi1)**: Handles keyboard input, file operations, and power management
- **Slave Pico (rpi2)**: Handles e-ink display rendering
- **Communication**: UART serial @ 115200 baud

---

## Master Pico (rpi1) - Keyboard & Logic Controller

### Complete Pinout Table

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MASTER PICO 2W PINOUT MAP                        │
├──────────┬─────────┬──────────────┬──────────────────────────────────┤
│ Physical │ GP Pin  │ Connection   │ Purpose                          │
├──────────┼─────────┼──────────────┼──────────────────────────────────┤
│ Pin 1    │ GP0     │ (unused)     │                                  │
│ Pin 2    │ GP1     │ (unused)     │                                  │
│ Pin 3    │ GND     │ GROUND       │ Common ground for all devices    │
│ Pin 4    │ GP2     │ TCA8418 SDA  │ I2C1 Data (keyboard)             │
│ Pin 5    │ GP3     │ TCA8418 SCL  │ I2C1 Clock (keyboard)            │
│ Pin 6    │ GP4     │ (unused)     │                                  │
│ Pin 7    │ GP5     │ (unused)     │                                  │
│ Pin 8    │ GND     │ GROUND       │ Common ground                    │
│ Pin 9    │ GP6     │ (unused)     │                                  │
│ Pin 10   │ GP7     │ (unused)     │                                  │
│ Pin 11   │ GP8     │ UART TX      │ → Slave Pico GP9 (RX)            │
│ Pin 12   │ GP9     │ UART RX      │ ← Slave Pico GP8 (TX)            │
│ Pin 13   │ GND     │ GROUND       │ Common ground                    │
│ Pin 14   │ GP10    │ (unused)     │                                  │
│ Pin 15   │ GP11    │ (unused)     │                                  │
│ Pin 16   │ GP12    │ (unused)     │                                  │
│ Pin 17   │ GP13    │ (unused)     │                                  │
│ Pin 18   │ GND     │ GROUND       │ Common ground                    │
│ Pin 19   │ GP14    │ (unused)     │                                  │
│ Pin 20   │ GP15    │ (unused)     │                                  │
│ Pin 21   │ GP16    │ (unused)     │                                  │
│ Pin 22   │ GP17    │ (unused)     │                                  │
│ Pin 23   │ GND     │ GROUND       │ Common ground                    │
│ Pin 24   │ GP18    │ (unused)     │                                  │
│ Pin 25   │ GP19    │ (unused)     │                                  │
│ Pin 26   │ GP20    │ TCA8418 INT  │ Keyboard interrupt (active low)  │
│ Pin 27   │ GP21    │ TCA8418 RST  │ Keyboard reset (active low)      │
│ Pin 28   │ GND     │ GROUND       │ Common ground                    │
│ Pin 29   │ GP22    │ POWER BTN    │ Power button input (pull-up)     │
│ Pin 30   │ RUN     │ (unused)     │ Reset pin                        │
│ Pin 31   │ GP26    │ (unused)     │                                  │
│ Pin 32   │ GP27    │ (unused)     │                                  │
│ Pin 33   │ GND     │ GROUND       │ Common ground                    │
│ Pin 34   │ GP28    │ (unused)     │                                  │
│ Pin 35   │ ADC_REF │ (unused)     │                                  │
│ Pin 36   │ 3V3(OUT)│ POWER OUT    │ 3.3V supply for TCA8418          │
│ Pin 37   │ 3V3_EN  │ (unused)     │                                  │
│ Pin 38   │ GND     │ GROUND       │ Common ground                    │
│ Pin 39   │ VSYS    │ POWER IN     │ System power input (5V from USB) │
│ Pin 40   │ VBUS    │ USB POWER    │ USB 5V input                     │
└──────────┴─────────┴──────────────┴──────────────────────────────────┘
```

### Master Pico - TCA8418 Keyboard Controller Connections

```
┌────────────────────────────────────────────────────────────────┐
│ TCA8418 Pin │ Master Pico Pin │ GP Pin │ Description          │
├─────────────┼─────────────────┼────────┼──────────────────────┤
│ VCC         │ Pin 36          │ 3V3    │ Power (3.3V)         │
│ GND         │ Pin 3/8/13/etc  │ GND    │ Ground               │
│ SDA         │ Pin 4           │ GP2    │ I2C1 Data            │
│ SCL         │ Pin 5           │ GP3    │ I2C1 Clock           │
│ INT         │ Pin 26          │ GP20   │ Interrupt (active L) │
│ RST         │ Pin 27          │ GP21   │ Reset (active L)     │
└─────────────┴─────────────────┴────────┴──────────────────────┘
```

### Master Pico - Slave Pico UART Connection

```
┌───────────────────────────────────────────────────────────────┐
│ Master Signal │ Master Pin │ GP Pin │ → Slave Pin │ Slave GP │
├───────────────┼────────────┼────────┼─────────────┼──────────┤
│ UART TX       │ Pin 11     │ GP8    │ → Pin 12    │ GP9      │
│ UART RX       │ Pin 12     │ GP9    │ ← Pin 11    │ GP8      │
│ GND           │ Pin 3/8/13 │ GND    │ → Pin 3/8   │ GND      │
└───────────────┴────────────┴────────┴─────────────┴──────────┘

Note: TX of one device connects to RX of the other (crossover)
```

### Master Pico - Power Button

```
┌──────────────────────────────────────────────────────┐
│ Button Terminal │ Master Pico Pin │ GP Pin │ Notes  │
├─────────────────┼─────────────────┼────────┼────────┤
│ Terminal 1      │ Pin 29          │ GP22   │ Input  │
│ Terminal 2      │ Any GND pin     │ GND    │ Ground │
└─────────────────┴─────────────────┴────────┴────────┘

Configuration: Internal pull-up enabled, active low (pressed = LOW)
```

---

## Slave Pico (rpi2) - Display Controller

### Complete Pinout Table

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SLAVE PICO 2W PINOUT MAP                        │
├──────────┬─────────┬──────────────┬──────────────────────────────────┤
│ Physical │ GP Pin  │ Connection   │ Purpose                          │
├──────────┼─────────┼──────────────┼──────────────────────────────────┤
│ Pin 1    │ GP0     │ (unused)     │                                  │
│ Pin 2    │ GP1     │ (unused)     │                                  │
│ Pin 3    │ GND     │ GROUND       │ Common ground for all devices    │
│ Pin 4    │ GP2     │ (unused)     │                                  │
│ Pin 5    │ GP3     │ (unused)     │                                  │
│ Pin 6    │ GP4     │ (unused)     │                                  │
│ Pin 7    │ GP5     │ (unused)     │                                  │
│ Pin 8    │ GND     │ GROUND       │ Common ground                    │
│ Pin 9    │ GP6     │ (unused)     │                                  │
│ Pin 10   │ GP7     │ (unused)     │                                  │
│ Pin 11   │ GP8     │ UART TX      │ → Master Pico GP9 (RX)           │
│ Pin 12   │ GP9     │ UART RX      │ ← Master Pico GP8 (TX)           │
│ Pin 13   │ GND     │ GROUND       │ Common ground                    │
│ Pin 14   │ GP10    │ E-INK SCK    │ SPI1 Clock (display)             │
│ Pin 15   │ GP11    │ E-INK MOSI   │ SPI1 Data Out (display)          │
│ Pin 16   │ GP12    │ (unused)     │                                  │
│ Pin 17   │ GP13    │ E-INK CS     │ Chip Select (display)            │
│ Pin 18   │ GND     │ GROUND       │ Common ground                    │
│ Pin 19   │ GP14    │ E-INK DC     │ Data/Command (display)           │
│ Pin 20   │ GP15    │ E-INK RST    │ Reset (display)                  │
│ Pin 21   │ GP16    │ E-INK BUSY   │ Busy Status (display)            │
│ Pin 22   │ GP17    │ (unused)     │                                  │
│ Pin 23   │ GND     │ GROUND       │ Common ground                    │
│ Pin 24   │ GP18    │ (unused)     │                                  │
│ Pin 25   │ GP19    │ (unused)     │                                  │
│ Pin 26   │ GP20    │ (unused)     │                                  │
│ Pin 27   │ GP21    │ (unused)     │                                  │
│ Pin 28   │ GND     │ GROUND       │ Common ground                    │
│ Pin 29   │ GP22    │ (unused)     │                                  │
│ Pin 30   │ RUN     │ (unused)     │ Reset pin                        │
│ Pin 31   │ GP26    │ (unused)     │                                  │
│ Pin 32   │ GP27    │ (unused)     │                                  │
│ Pin 33   │ GND     │ GROUND       │ Common ground                    │
│ Pin 34   │ GP28    │ (unused)     │                                  │
│ Pin 35   │ ADC_REF │ (unused)     │                                  │
│ Pin 36   │ 3V3(OUT)│ POWER OUT    │ 3.3V supply for e-ink display    │
│ Pin 37   │ 3V3_EN  │ (unused)     │                                  │
│ Pin 38   │ GND     │ GROUND       │ Common ground                    │
│ Pin 39   │ VSYS    │ POWER IN     │ System power input (5V from USB) │
│ Pin 40   │ VBUS    │ USB POWER    │ USB 5V input                     │
└──────────┴─────────┴──────────────┴──────────────────────────────────┘
```

### Slave Pico - Waveshare 4.2" E-ink Display Connections

```
┌─────────────────────────────────────────────────────────────────┐
│ E-ink Pin │ Slave Pico Pin │ GP Pin │ Description               │
├───────────┼────────────────┼────────┼───────────────────────────┤
│ VCC       │ Pin 36         │ 3V3    │ Power (3.3V)              │
│ GND       │ Pin 3/8/13/etc │ GND    │ Ground                    │
│ DIN       │ Pin 15         │ GP11   │ SPI1 MOSI (Data In)       │
│ CLK       │ Pin 14         │ GP10   │ SPI1 SCK (Clock)          │
│ CS        │ Pin 17         │ GP13   │ Chip Select (active low)  │
│ DC        │ Pin 19         │ GP14   │ Data/Command select       │
│ RST       │ Pin 20         │ GP15   │ Reset (active low)        │
│ BUSY      │ Pin 21         │ GP16   │ Busy status (input)       │
└───────────┴────────────────┴────────┴───────────────────────────┘

Note: No MISO connection needed (e-ink is write-only)
```

### Slave Pico - Master Pico UART Connection

```
┌──────────────────────────────────────────────────────────────┐
│ Slave Signal │ Slave Pin │ GP Pin │ → Master Pin │ Master GP │
├──────────────┼───────────┼────────┼──────────────┼───────────┤
│ UART TX      │ Pin 11    │ GP8    │ → Pin 12     │ GP9       │
│ UART RX      │ Pin 12    │ GP9    │ ← Pin 11     │ GP8       │
│ GND          │ Pin 3/8   │ GND    │ → Pin 3/8/13 │ GND       │
└──────────────┴───────────┴────────┴──────────────┴───────────┘

Baudrate: 115200 baud
Protocol: JSON messages terminated with newline
```

---

## Inter-Device Connections Summary

### UART Serial Link (Master ↔ Slave)

```
Master Pico                           Slave Pico
┌───────────┐                        ┌───────────┐
│           │                        │           │
│  GP8 (TX) ├────────────────────────┤ GP9 (RX)  │
│           │                        │           │
│  GP9 (RX) ├────────────────────────┤ GP8 (TX)  │
│           │                        │           │
│    GND    ├────────────────────────┤   GND     │
│           │                        │           │
└───────────┘                        └───────────┘
```

**Critical:** This is a crossover connection:
- Master TX (GP8) → Slave RX (GP9)
- Master RX (GP9) ← Slave TX (GP8)

### Power Distribution

Both Pico 2W boards can be powered independently via USB, or you can use a shared power supply:

```
Option 1: Dual USB (Recommended for development)
- Master Pico: USB power via Pin 40 (VBUS)
- Slave Pico: USB power via Pin 40 (VBUS)
- Common ground between both devices

Option 2: Single Power Supply
- 5V supply → Both VSYS pins (Pin 39)
- Ground → All GND pins on both boards
- USB not required (except for programming)
```

---

## Complete System Wiring Diagram (ASCII Art)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LINSON WRITER'S DECK SYSTEM                          │
└─────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────┐
                    │   TCA8418 Keyboard       │
                    │   10x8 Matrix Controller │
                    └───┬──────────────────┬───┘
                        │                  │
                 SDA(GP2)│           SCL(GP3)
                 INT(GP20)          RST(GP21)
                        │                  │
                        ▼                  ▼
        ┌───────────────────────────────────────┐
        │                                       │
        │      MASTER PICO 2W (rpi1)           │
        │    Keyboard & Logic Controller        │
        │                                       │
        │  • Keyboard scanning (continuous)     │
        │  • Text buffer & file operations      │
        │  • Power management (2min/5min)       │
        │  • UART command sender                │
        │                                       │
        └───────────┬──────────────────┬────────┘
                    │                  │
             UART TX(GP8)      UART RX(GP9)
                    │                  │
                    │     ╔════════╗   │
                    └─────╢ UART   ╟───┘
                          ╚════════╝
                    ┌─────╢ Link   ╟───┐
                    │     ╚════════╝   │
             UART RX(GP9)      UART TX(GP8)
                    │                  │
                    ▼                  ▼
        ┌───────────────────────────────────────┐
        │                                       │
        │       SLAVE PICO 2W (rpi2)           │
        │       Display Controller              │
        │                                       │
        │  • UART command receiver              │
        │  • Display rendering & refresh        │
        │  • Screen saver display               │
        │  • Text layout calculations           │
        │                                       │
        └───────────┬──────────────────┬────────┘
                    │                  │
              SPI1 SCK(GP10)     SPI1 MOSI(GP11)
              CS(GP13) DC(GP14)  RST(GP15) BUSY(GP16)
                    │                  │
                    ▼                  ▼
                    ┌──────────────────────────┐
                    │  Waveshare 4.2" E-ink    │
                    │  400x300 Display         │
                    └──────────────────────────┘


      [Power Button]──GP22─→ Master Pico


Legend:
  ══════  UART Serial Link @ 115200 baud
  ──────  GPIO connections
  ▼       Signal direction
```

---

## Pin Assignment Summary Tables

### Master Pico Active Pins

| Pin Function        | GP Pin | Physical Pin | Connected To        |
|---------------------|--------|--------------|---------------------|
| I2C1 SDA (Keyboard) | GP2    | Pin 4        | TCA8418 SDA         |
| I2C1 SCL (Keyboard) | GP3    | Pin 5        | TCA8418 SCL         |
| UART1 TX            | GP8    | Pin 11       | Slave GP9 (RX)      |
| UART1 RX            | GP9    | Pin 12       | Slave GP8 (TX)      |
| Keyboard INT        | GP20   | Pin 26       | TCA8418 INT         |
| Keyboard RST        | GP21   | Pin 27       | TCA8418 RST         |
| Power Button        | GP22   | Pin 29       | Button to GND       |
| 3.3V Output         | 3V3    | Pin 36       | TCA8418 VCC         |
| Ground              | GND    | Pins 3,8,13+ | Common GND          |

**Total Active Pins: 7 GPIO + Power**

### Slave Pico Active Pins

| Pin Function         | GP Pin | Physical Pin | Connected To        |
|----------------------|--------|--------------|---------------------|
| UART1 TX             | GP8    | Pin 11       | Master GP9 (RX)     |
| UART1 RX             | GP9    | Pin 12       | Master GP8 (TX)     |
| SPI1 SCK (Display)   | GP10   | Pin 14       | E-ink CLK           |
| SPI1 MOSI (Display)  | GP11   | Pin 15       | E-ink DIN           |
| Display CS           | GP13   | Pin 17       | E-ink CS            |
| Display DC           | GP14   | Pin 19       | E-ink DC            |
| Display RST          | GP15   | Pin 20       | E-ink RST           |
| Display BUSY         | GP16   | Pin 21       | E-ink BUSY          |
| 3.3V Output          | 3V3    | Pin 36       | E-ink VCC           |
| Ground               | GND    | Pins 3,8,13+ | Common GND          |

**Total Active Pins: 8 GPIO + Power**

---

## Step-by-Step Wiring Instructions

### Step 1: Master Pico - Keyboard Connections

1. **Power the TCA8418:**
   - TCA8418 VCC → Master Pin 36 (3.3V)
   - TCA8418 GND → Master Pin 3 (GND)

2. **I2C Connection:**
   - TCA8418 SDA → Master Pin 4 (GP2)
   - TCA8418 SCL → Master Pin 5 (GP3)

3. **Control Pins:**
   - TCA8418 INT → Master Pin 26 (GP20)
   - TCA8418 RST → Master Pin 27 (GP21)

4. **Power Button:**
   - Button Terminal 1 → Master Pin 29 (GP22)
   - Button Terminal 2 → Master GND (any GND pin)

### Step 2: Slave Pico - Display Connections

1. **Power the E-ink Display:**
   - E-ink VCC → Slave Pin 36 (3.3V)
   - E-ink GND → Slave Pin 3 (GND)

2. **SPI Connection:**
   - E-ink CLK → Slave Pin 14 (GP10)
   - E-ink DIN → Slave Pin 15 (GP11)

3. **Control Pins:**
   - E-ink CS → Slave Pin 17 (GP13)
   - E-ink DC → Slave Pin 19 (GP14)
   - E-ink RST → Slave Pin 20 (GP15)
   - E-ink BUSY → Slave Pin 21 (GP16)

### Step 3: Master ↔ Slave UART Connection

**Critical Crossover Connection:**

1. **Master TX to Slave RX:**
   - Master Pin 11 (GP8, TX) → Slave Pin 12 (GP9, RX)

2. **Slave TX to Master RX:**
   - Slave Pin 11 (GP8, TX) → Master Pin 12 (GP9, RX)

3. **Common Ground:**
   - Master GND → Slave GND (connect any GND pins together)

### Step 4: Power Supply

Choose one method:

**Method A: Dual USB (Recommended for Development)**
- Connect USB cable to Master Pico
- Connect USB cable to Slave Pico
- Ensure common ground between devices (completed in Step 3)

**Method B: Single Power Supply**
- Connect 5V power to both VSYS pins (Pin 39 on both boards)
- Connect GND to multiple GND pins on both boards
- Use proper voltage regulation (5V only)

---

## Verification Checklist

Before powering on, verify:

- [ ] All I2C connections correct (SDA/SCL not swapped)
- [ ] UART crossover correct (TX→RX, RX←TX)
- [ ] All GND connections established
- [ ] No short circuits between power and ground
- [ ] 3.3V supplies connected to correct pins
- [ ] Display SPI connections match Slave pinout
- [ ] Keyboard I2C connections match Master pinout
- [ ] Power button connected with internal pull-up (no external resistor needed)

---

## Troubleshooting Guide

### Master Pico Not Detecting Keyboard

**Check:**
1. I2C wiring (SDA on GP2, SCL on GP3)
2. TCA8418 powered (3.3V on VCC)
3. I2C bus set to I2C(1) in code, not I2C(0)
4. Common ground between Master and TCA8418

### Slave Pico Display Not Updating

**Check:**
1. SPI wiring (SCK on GP10, MOSI on GP11)
2. All control pins connected (CS, DC, RST, BUSY)
3. E-ink powered (3.3V on VCC)
4. SPI bus set to SPI(1) in code
5. Common ground between Slave and display

### No UART Communication

**Check:**
1. Crossover connection (Master TX → Slave RX, and vice versa)
2. Common ground between Master and Slave
3. Baudrate matches (115200) on both devices
4. UART IDs correct (UART1 on both)
5. TX/RX pins not swapped on same device

### Power Issues

**Check:**
1. Voltage at 3.3V pins measures correct (~3.3V)
2. Current draw within limits (Pico 2W 3.3V out: max 300mA)
3. USB power cables functional
4. No reversed polarity on power connections

---

## Pin Reference Quick Lookup

### Master Pico Quick Reference

```
GP2  → I2C1 SDA (Keyboard)
GP3  → I2C1 SCL (Keyboard)
GP8  → UART TX (to Slave RX)
GP9  → UART RX (from Slave TX)
GP20 → Keyboard INT
GP21 → Keyboard RST
GP22 → Power Button
```

### Slave Pico Quick Reference

```
GP8  → UART TX (to Master RX)
GP9  → UART RX (from Master TX)
GP10 → SPI1 SCK (Display)
GP11 → SPI1 MOSI (Display)
GP13 → Display CS
GP14 → Display DC
GP15 → Display RST
GP16 → Display BUSY
```

---

## Notes

- All GPIO pins are 3.3V logic level
- Internal pull-ups available on all GPIO (used for Power Button)
- Maximum 3.3V output current: 300mA per Pico 2W
- UART supports up to 921600 baud (115200 used for reliability)
- I2C supports up to 1MHz (400kHz used for compatibility)
- SPI supports up to 62.5MHz (4MHz used for stability)
- E-ink BUSY pin is input only (read display status)
- TCA8418 INT pin is active-low (pulled high when idle)

---

**Document Version:** 1.0
**Date:** 2025-01-11
**Hardware:** Raspberry Pi Pico 2W (RP2350) × 2
**Firmware:** MicroPython v1.24+
