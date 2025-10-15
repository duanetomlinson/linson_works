# GPIO Pinout Conversion: ESP32-S3-WROOM-1 to Raspberry Pi Pico 2W

This document provides the complete pin mapping for migrating the Linson Writer's Deck project from ESP32-S3-WROOM-1 to Raspberry Pi Pico 2W.

---

## Table of Contents
1. [Quick Reference Conversion Table](#quick-reference-conversion-table)
2. [Detailed Pin Mappings by Peripheral](#detailed-pin-mappings-by-peripheral)
3. [I2C Configuration](#i2c-configuration)
4. [SPI Configuration](#spi-configuration)
5. [Code Changes Required](#code-changes-required)
6. [Wiring Diagram](#wiring-diagram)
7. [Important Differences](#important-differences)

---

## Quick Reference Conversion Table

| Function | ESP32-S3 GPIO | Pico 2W GPIO | Pico 2W Physical Pin | Notes |
|----------|---------------|--------------|----------------------|-------|
| **I2C (Keyboard Controller)** |
| I2C SDA | GPIO 4 | **GP2** | Pin 4 | I2C1 default SDA |
| I2C SCL | GPIO 5 | **GP3** | Pin 5 | I2C1 default SCL |
| **Keyboard Interrupt & Reset** |
| TCA INT | GPIO 21 | **GP20** | Pin 26 | Keyboard interrupt (active low) |
| TCA RST | GPIO 38 | **GP21** | Pin 27 | Keyboard reset (active low) |
| **SPI (E-ink Display)** |
| SPI SCK | GPIO 18 | **GP10** | Pin 14 | SPI1 default SCK |
| SPI MOSI | GPIO 11 | **GP11** | Pin 15 | SPI1 default MOSI |
| EINK CS | GPIO 10 | **GP13** | Pin 17 | Chip select |
| EINK DC | GPIO 14 | **GP14** | Pin 19 | Data/Command |
| EINK RST | GPIO 15 | **GP15** | Pin 20 | Display reset |
| EINK BUSY | GPIO 16 | **GP16** | Pin 21 | Busy status |
| **Power Management** |
| POWER BTN | GPIO 0 | **GP22** | Pin 29 | Power button input |

---

## Detailed Pin Mappings by Peripheral

### 1. TCA8418 Keyboard Controller (I2C)

```ascii
┌─────────────────┬──────────────┬─────────────┬──────────────┐
│ Signal          │ ESP32-S3     │ Pico 2W     │ Pico Pin #   │
├─────────────────┼──────────────┼─────────────┼──────────────┤
│ VCC             │ 3.3V         │ 3V3 (OUT)   │ Pin 36       │
│ GND             │ GND          │ GND         │ Pin 3/8/13/  │
│ SDA (Data)      │ GPIO 4       │ GP2         │ Pin 4        │
│ SCL (Clock)     │ GPIO 5       │ GP3         │ Pin 5        │
│ INT (Interrupt) │ GPIO 21      │ GP20        │ Pin 26       │
│ RST (Reset)     │ GPIO 38      │ GP21        │ Pin 27       │
└─────────────────┴──────────────┴─────────────┴──────────────┘
```

**Rationale:**
- **I2C1 Bus**: Pico 2W default I2C1 pins are GP2 (SDA) and GP3 (SCL)
- **GP20/GP21**: Available GPIO pins suitable for interrupt and reset
- **INT Pin**: Must be input with pull-up (active low trigger)
- **RST Pin**: Output pin for hardware reset (active low)

---

### 2. Waveshare 4.2" E-ink Display (SPI)

```ascii
┌─────────────────┬──────────────┬─────────────┬──────────────┐
│ Signal          │ ESP32-S3     │ Pico 2W     │ Pico Pin #   │
├─────────────────┼──────────────┼─────────────┼──────────────┤
│ VCC             │ 3.3V         │ 3V3 (OUT)   │ Pin 36       │
│ GND             │ GND          │ GND         │ Pin 3/8/13/  │
│ DIN (MOSI)      │ GPIO 11      │ GP11        │ Pin 15       │
│ CLK (SCK)       │ GPIO 18      │ GP10        │ Pin 14       │
│ CS (Chip Sel)   │ GPIO 10      │ GP13        │ Pin 17       │
│ DC (Data/Cmd)   │ GPIO 14      │ GP14        │ Pin 19       │
│ RST (Reset)     │ GPIO 15      │ GP15        │ Pin 20       │
│ BUSY (Status)   │ GPIO 16      │ GP16        │ Pin 21       │
└─────────────────┴──────────────┴─────────────┴──────────────┘
```

**Rationale:**
- **SPI1 Bus**: Pico 2W default SPI1 pins are GP10 (SCK) and GP11 (MOSI)
- **GP13-GP16**: Sequential GPIO block for control signals
- **No MISO**: E-ink displays are write-only, no MISO connection needed

---

### 3. Power Button

```ascii
┌─────────────────┬──────────────┬─────────────┬──────────────┐
│ Signal          │ ESP32-S3     │ Pico 2W     │ Pico Pin #   │
├─────────────────┼──────────────┼─────────────┼──────────────┤
│ POWER_BTN       │ GPIO 0       │ GP22        │ Pin 29       │
│ (Pull-up Input) │              │             │              │
└─────────────────┴──────────────┴─────────────┴──────────────┘
```

**Rationale:**
- **GP22**: Available GPIO, easily accessible physical pin
- **Internal Pull-up**: Active low button (pressed = LOW)

---

## I2C Configuration

### ESP32-S3 Code (Current):
```python
I2C_SDA = 4
I2C_SCL = 5

i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
```

### Pico 2W Code (New):
```python
I2C_SDA = 2  # GP2 - I2C1 SDA
I2C_SCL = 3  # GP3 - I2C1 SCL

i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)  # Use I2C1
```

**Key Changes:**
- I2C bus ID changes from `I2C(0)` to `I2C(1)` on Pico 2W
- Pin numbers change: GPIO 4/5 → GP2/3
- I2C1 is recommended for external devices (I2C0 conflicts with internal flash on some boards)

---

## SPI Configuration

### ESP32-S3 Code (Current):
```python
SPI_SCK  = 18
SPI_MOSI = 11

spi = SPI(baudrate=80_000_000, polarity=0, phase=0, bits=8,
          sck=Pin(SPI_SCK), mosi=Pin(SPI_MOSI))
```

### Pico 2W Code (New):
```python
SPI_SCK  = 10  # GP10 - SPI1 SCK
SPI_MOSI = 11  # GP11 - SPI1 MOSI (no change!)

spi = SPI(1, baudrate=80_000_000, polarity=0, phase=0, bits=8,
          sck=Pin(SPI_SCK), mosi=Pin(SPI_MOSI))  # Use SPI1
```

**Key Changes:**
- SPI bus ID: Must specify `SPI(1)` explicitly
- SCK pin: GPIO 18 → GP10
- MOSI pin: GPIO 11 → GP11 (same number, different chip!)

---

## Code Changes Required

### 1. Pin Constant Updates

**File: `main.py`, `main_improved.py`, `main_optimized.py`**

```python
# OLD (ESP32-S3)
I2C_SDA = 4
I2C_SCL = 5
TCA_INT = 21
TCA_RST = 38
POWER_BTN = Pin(0, Pin.IN, Pin.PULL_UP)

# NEW (Pico 2W)
I2C_SDA = 2   # GP2
I2C_SCL = 3   # GP3
TCA_INT = 20  # GP20
TCA_RST = 21  # GP21
POWER_BTN = Pin(22, Pin.IN, Pin.PULL_UP)  # GP22
```

**File: `display42.py`**

```python
# OLD (ESP32-S3)
SPI_SCK   = 18
SPI_MOSI  = 11
RST_PIN   = 15
DC_PIN    = 14
CS_PIN    = 10
BUSY_PIN  = 16

# NEW (Pico 2W)
SPI_SCK   = 10  # GP10
SPI_MOSI  = 11  # GP11
RST_PIN   = 15  # GP15
DC_PIN    = 14  # GP14
CS_PIN    = 13  # GP13
BUSY_PIN  = 16  # GP16
```

**File: `tca8418.py`**

```python
# In all example functions, update:

# OLD
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
interrupt_pin = Pin(21, Pin.IN, Pin.PULL_UP)
reset_pin = Pin(38, Pin.OUT, value=1)

# NEW
i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=400000)  # I2C1
interrupt_pin = Pin(20, Pin.IN, Pin.PULL_UP)  # GP20
reset_pin = Pin(21, Pin.OUT, value=1)  # GP21
```

---

### 2. I2C Bus Initialization

```python
# OLD
i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)

# NEW - Must use I2C bus 1
i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
```

---

### 3. Deep Sleep & Wake Functionality

**⚠️ CRITICAL DIFFERENCE:** RP2040/RP2350 does NOT support deep sleep like ESP32!

#### ESP32-S3 Code (Remove):
```python
# DOES NOT WORK ON PICO 2W
import esp32
esp32.wake_on_ext0(pin=Pin(TCA_INT), level=esp32.WAKEUP_ALL_LOW)
machine.deepsleep()
```

#### Pico 2W Alternative (Use `lightsleep`):
```python
# Replace deep sleep with light sleep on Pico 2W
import machine

# Configure wake on interrupt (if supported by firmware)
# Note: RP2040 lightsleep wakes on ANY interrupt
wake_pin = Pin(TCA_INT, Pin.IN, Pin.PULL_UP)

# Use lightsleep instead (wakes on interrupts automatically)
machine.lightsleep(10000)  # 10 second sleep, wakes on any interrupt
```

**Alternative: Dormant Mode (Lower Power)**
```python
# For lowest power, use dormant mode (RP2-specific)
import rp2

# Enter dormant state (wakes on edge trigger)
# This requires specific RP2 firmware support
rp2.dormant()  # Very low power, wakes on GPIO edge
```

**⚠️ Power Consumption Note:**
- ESP32 deep sleep: ~10-150 µA
- RP2040 lightsleep: ~3-5 mA (much higher!)
- RP2040 dormant mode: ~180 µA (closer to ESP32)

Consider using dormant mode for battery operation, but note it requires careful wake source configuration.

---

### 4. Import Changes

```python
# Remove ESP32-specific imports
# import esp32  # ← REMOVE for Pico 2W

# Add RP2-specific imports if using dormant mode
import rp2  # For dormant() and other RP2040-specific features
```

---

### 5. Threading Availability

**Good News:** The `_thread` module IS available on Pico 2W, so `main_optimized.py` should work!

```python
# This works on Pico 2W
import _thread
import queue  # May need to check if queue module exists

# Threading code from main_optimized.py should work as-is
_thread.start_new_thread(display_worker_thread, ())
```

**Note:** If `queue` module is missing, you may need to implement a simple queue or use `_thread.allocate_lock()` for synchronization.

---

## Wiring Diagram

### Raspberry Pi Pico 2W Pinout (40-pin)

```ascii
        ┌─────────────────────────────┐
        │                             │
  GP0 ──┤ 1                    VBUS ├── 40
  GP1 ──┤ 2                    VSYS ├── 39
  GND ──┤ 3                     GND ├── 38
  GP2 ──┤ 4  ← I2C1 SDA         3V3 ├── 37 ← OUT
  GP3 ──┤ 5  ← I2C1 SCL    3V3_EN ├── 36
  GP4 ──┤ 6                 ADC_REF ├── 35
  GP5 ──┤ 7                    GP28 ├── 34
  GND ──┤ 8                     GND ├── 33
  GP6 ──┤ 9                    GP27 ├── 32
  GP7 ──┤10                    GP26 ├── 31
  GP8 ──┤11                     RUN ├── 30
  GP9 ──┤12                    GP22 ├── 29 ← POWER_BTN
  GND ──┤13                     GND ├── 28
 GP10 ──┤14 ← SPI1 SCK        GP21 ├── 27 ← TCA_RST
 GP11 ──┤15 ← SPI1 MOSI       GP20 ├── 26 ← TCA_INT
 GP12 ──┤16                    GP19 ├── 25
 GP13 ──┤17 ← EINK_CS         GP18 ├── 24
  GND ──┤18                     GND ├── 23
 GP14 ──┤19 ← EINK_DC         GP17 ├── 22
 GP15 ──┤20 ← EINK_RST        GP16 ├── 21 ← EINK_BUSY
        │                             │
        └─────────────────────────────┘
             USB connector bottom
```

### Connection Summary

```ascii
┌─────────────────────────────────────────────────────────────┐
│ TCA8418 Keyboard Controller → Pico 2W                      │
├─────────────────────────────────────────────────────────────┤
│ TCA8418 VCC  → Pin 36 (3V3 OUT)                            │
│ TCA8418 GND  → Pin 3, 8, 13, etc (any GND)                 │
│ TCA8418 SDA  → Pin 4  (GP2, I2C1 SDA)                      │
│ TCA8418 SCL  → Pin 5  (GP3, I2C1 SCL)                      │
│ TCA8418 INT  → Pin 26 (GP20, interrupt input)              │
│ TCA8418 RST  → Pin 27 (GP21, reset output)                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Waveshare 4.2" E-ink Display → Pico 2W                     │
├─────────────────────────────────────────────────────────────┤
│ EINK VCC   → Pin 36 (3V3 OUT)                              │
│ EINK GND   → Pin 3, 8, 13, etc (any GND)                   │
│ EINK DIN   → Pin 15 (GP11, SPI1 MOSI)                      │
│ EINK CLK   → Pin 14 (GP10, SPI1 SCK)                       │
│ EINK CS    → Pin 17 (GP13, chip select)                    │
│ EINK DC    → Pin 19 (GP14, data/command)                   │
│ EINK RST   → Pin 20 (GP15, display reset)                  │
│ EINK BUSY  → Pin 21 (GP16, busy status)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Power Button → Pico 2W                                      │
├─────────────────────────────────────────────────────────────┤
│ Button terminal 1 → Pin 29 (GP22)                          │
│ Button terminal 2 → GND (any GND pin)                      │
│ (Internal pull-up enabled, active low)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Important Differences

### 1. **Pin Numbering**
- ESP32-S3 uses GPIO numbers (0-48)
- Pico 2W uses GP numbers (0-28) - fewer pins!
- Physical pin numbers (1-40) are different from GP numbers

### 2. **I2C Buses**
- ESP32-S3: 2 I2C buses (0, 1), any pins via pin muxing
- Pico 2W: 2 I2C buses (0, 1), fixed default pins but remappable
  - I2C0: GP0/GP1, GP4/GP5, GP8/GP9, GP12/GP13, GP16/GP17, GP20/GP21
  - I2C1: GP2/GP3, GP6/GP7, GP10/GP11, GP14/GP15, GP18/GP19, GP26/GP27

### 3. **SPI Buses**
- ESP32-S3: 3 SPI buses (0, 1, 2), any pins via pin muxing
- Pico 2W: 2 SPI buses (0, 1), fixed default pins but remappable
  - SPI0: SCK=GP2/GP6/GP18, MOSI=GP3/GP7/GP19
  - SPI1: SCK=GP10/GP14/GP26, MOSI=GP11/GP15/GP27

### 4. **Deep Sleep**
- ⚠️ **CRITICAL:** RP2040/RP2350 does NOT have ESP32-style deep sleep
- Use `machine.lightsleep()` (higher power ~3-5mA) or `rp2.dormant()` (low power ~180µA)
- Wake sources are different - dormant mode wakes on GPIO edges

### 5. **Voltage Levels**
- Both: 3.3V I/O (compatible ✓)
- Pico 2W has 3.3V LDO output on Pin 36 (max 300mA)

### 6. **WiFi**
- Both support WiFi (Pico 2W uses CYW43439)
- Network module API is the same in MicroPython
- WiFi code should work without changes

### 7. **CPU Frequency**
- ESP32-S3: Default 240 MHz (adjustable)
- RP2040: Default 125 MHz (adjustable to ~250 MHz)
- RP2350: Default 150 MHz (adjustable to ~300 MHz on Pico 2)

### 8. **Memory**
- ESP32-S3: 512 KB SRAM, 384 KB ROM
- RP2040: 264 KB SRAM (less than ESP32!)
- RP2350: 520 KB SRAM (similar to ESP32-S3)
- **Action:** Monitor memory usage, may need optimization for RP2040

### 9. **Threading**
- Both support `_thread` module ✓
- Threading code should work on both platforms

### 10. **Hardware Considerations**
- Pico 2W has fewer GPIO pins (26 usable GP pins vs 45 on ESP32-S3)
- Some ESP32-S3 pins (like GPIO 38) don't exist on Pico 2W
- Pin mapping requires careful planning to avoid conflicts

---

## Testing Checklist

After making these changes, test in this order:

- [ ] Power up - verify 3.3V on all VCC connections
- [ ] I2C scan - verify TCA8418 appears at address 0x34
- [ ] Keyboard test - verify key press/release events
- [ ] SPI communication - verify e-ink display responds
- [ ] Display refresh - test partial and full refresh
- [ ] WiFi connection - verify network connectivity
- [ ] Power button - verify interrupt on press
- [ ] Sleep mode - test lightsleep/dormant wake
- [ ] Full application - run complete typewriter software
- [ ] Memory usage - monitor RAM consumption during operation

---

## Summary of Files to Modify

1. **`main.py`** - Update pin constants, I2C/SPI initialization, remove `esp32` imports
2. **`main_improved.py`** - Same changes as main.py
3. **`main_optimized.py`** - Same changes, verify `queue` module availability
4. **`display42.py`** - Update SPI and control pin constants
5. **`tca8418.py`** - Update I2C pins in all example/test functions
6. **`boot.py`** - Remove `esp32` imports if present

---

## Quick Migration Script

```python
# Pin mapping dictionary for search-and-replace
PIN_MAPPING = {
    'I2C_SDA = 4': 'I2C_SDA = 2',
    'I2C_SCL = 5': 'I2C_SCL = 3',
    'TCA_INT = 21': 'TCA_INT = 20',
    'TCA_RST = 38': 'TCA_RST = 21',
    'Pin(0, Pin.IN': 'Pin(22, Pin.IN',  # Power button
    'SPI_SCK   = 18': 'SPI_SCK   = 10',
    'CS_PIN    = 10': 'CS_PIN    = 13',
    'I2C(0': 'I2C(1',  # I2C bus change
    # Add more as needed
}

# Note: Manual review still required after automated changes!
```

---

**Document Version:** 1.0
**Last Updated:** 2025-10-11
**Compatibility:** Raspberry Pi Pico 2W (RP2350), MicroPython v1.24+
