# Linson Writer's Deck Test Suite

Comprehensive test suite for the dual Raspberry Pi Pico 2W Master-Slave architecture.

## Test Structure

```
project/
├── rpi1/                          # Master Pico files
│   ├── main.py                    # Main application
│   ├── tca8418.py                 # Keyboard driver
│   ├── test_master.py             # Hardware integration tests
│   └── test_master_unit.py        # Application unit tests
│
├── rpi2/                          # Slave Pico files
│   ├── main.py                    # Main application
│   ├── display42.py               # Display driver
│   ├── test_slave.py              # Hardware integration tests
│   └── test_slave_unit.py         # Application unit tests
│
└── tests/                         # Shared tests
    ├── test_text_layout.py        # TextLayout edge cases
    ├── test_uart_protocol.py      # UART protocol tests
    └── README.md                  # This file
```

## Test Categories

### 1. Hardware Integration Tests
**Purpose:** Validate physical hardware connections and peripherals

#### Master Pico (`rpi1/test_master.py`)
- **I2C Bus:** I2C1 initialization on GP2/GP3 @ 400kHz
- **TCA8418 Keyboard:** Device detection, register access, FIFO operations
- **Interrupt/Reset Pins:** GP20 (INT), GP21 (RST) functionality
- **Power Button:** GP22 input with pull-up detection
- **UART:** UART1 initialization, loopback test, JSON serialization

**Run on:** Master Pico 2W hardware
**Requirements:** TCA8418 keyboard connected, optional loopback wire (GP8→GP9)

#### Slave Pico (`rpi2/test_slave.py`)
- **SPI Bus:** SPI1 initialization on GP10/GP11 @ 4MHz
- **Display Control Pins:** CS (GP13), DC (GP14), RST (GP15), BUSY (GP16)
- **E-ink Display:** Initialization, partial/full refresh, framebuffer operations
- **UART:** UART1 initialization, loopback test, JSON parsing

**Run on:** Slave Pico 2W hardware
**Requirements:** Waveshare 4.2" e-ink display connected, optional loopback wire (GP8→GP9)

### 2. Application Unit Tests
**Purpose:** Test application logic without hardware dependencies

#### Master Application (`rpi1/test_master_unit.py`)
- **TextLayout:** Word wrapping, pagination, cursor positioning
- **Text Editing:** Character insertion, backspace, word deletion
- **Power Management:** Screensaver (2min), auto-off (5min) timing
- **Key Processing:** Glyph conversion, shift/alt/ctrl modifiers
- **File Operations:** Page splitting/joining with markers

**Run on:** Master Pico or desktop Python
**Requirements:** None (pure logic tests)

#### Slave Application (`rpi2/test_slave_unit.py`)
- **TextLayout:** Word wrapping, pagination (same as Master)
- **UART Commands:** All command structure validation
- **Command Handlers:** INIT, RENDER_TEXT, SCREENSAVER, etc.
- **Response Format:** OK and error response structures
- **JSON Protocol:** Serialization, parsing, unicode handling

**Run on:** Slave Pico or desktop Python
**Requirements:** None (pure logic tests)

### 3. Shared Component Tests
**Purpose:** Test shared logic used by both Picos

#### TextLayout Edge Cases (`tests/test_text_layout.py`)
- **Edge Cases:** Empty strings, single characters, space/newline-only text
- **Boundaries:** Exact line width, overflow by one character
- **Long Words:** Word breaking across multiple lines
- **Pagination:** Exact page fills, overflow detection
- **Cursor Position:** Start, end, newlines, multiple pages

**Run on:** Any Python environment
**Requirements:** None

#### UART Protocol (`tests/test_uart_protocol.py`)
- **Command Structures:** All 7 command types validated
- **Response Structures:** OK and error responses
- **JSON Serialization:** Encoding, decoding, roundtrip
- **Protocol Format:** Newline terminator, message size limits
- **Special Characters:** Unicode, escape sequences, empty strings
- **Error Handling:** Malformed JSON, missing fields, invalid types
- **Performance:** Encoding/decoding speed tests

**Run on:** Any Python environment
**Requirements:** None

## Running Tests

### On Raspberry Pi Pico 2W

#### Master Pico Tests

1. **Copy files to Master Pico:**
   ```
   rpi1/main.py
   rpi1/tca8418.py
   rpi1/test_master.py
   rpi1/test_master_unit.py
   ```

2. **Hardware integration tests:**
   ```python
   import test_master
   # Runs all hardware tests
   ```

3. **Application unit tests:**
   ```python
   import test_master_unit
   # Runs all logic tests
   ```

#### Slave Pico Tests

1. **Copy files to Slave Pico:**
   ```
   rpi2/main.py
   rpi2/display42.py
   rpi2/test_slave.py
   rpi2/test_slave_unit.py
   ```

2. **Hardware integration tests:**
   ```python
   import test_slave
   # Runs all hardware tests (takes 10-15 seconds due to display)
   ```

3. **Application unit tests:**
   ```python
   import test_slave_unit
   # Runs all logic tests
   ```

### On Desktop Python

#### Shared Tests

```bash
cd tests/
python test_text_layout.py
python test_uart_protocol.py
```

#### Application Tests (if compatible)

```bash
cd rpi1/
python test_master_unit.py

cd rpi2/
python test_slave_unit.py
```

## Test Output Format

```
======================================================
  MASTER PICO 2W HARDWARE INTEGRATION TEST SUITE
======================================================

[1/12] GPIO Pin Configuration.................. ✓ PASS (5ms)
[2/12] I2C Bus Initialization.................. ✓ PASS (23ms)
[3/12] I2C Device Scan......................... ✓ PASS (15ms)
    Found 1 device(s): 0x34
[4/12] TCA8418 Device Detection................ ✓ PASS (18ms)
    TCA8418 detected at 0x34, CFG=0x80
...

======================================================
  RESULTS: 12/12 PASSED
======================================================
```

## Test Coverage

### Master Pico
- **Hardware Tests:** 12 tests covering I2C, keyboard, UART, pins
- **Unit Tests:** 23 tests covering text layout, editing, power, keys, files
- **Total:** 35 tests

### Slave Pico
- **Hardware Tests:** 14 tests covering SPI, display, UART, pins
- **Unit Tests:** 23 tests covering text layout, commands, responses, JSON
- **Total:** 37 tests

### Shared
- **TextLayout Tests:** 23 edge case and boundary tests
- **UART Protocol Tests:** 28 protocol validation tests
- **Total:** 51 tests

**Grand Total:** 123 tests

## Hardware Test Notes

### Master Pico (`test_master.py`)
- **UART Loopback:** Requires temporary wire connecting GP8 (TX) to GP9 (RX)
  - **Remove wire before connecting to Slave Pico!**
- **Keyboard:** Physical keyboard should be connected to see full functionality
- **All tests pass without keyboard**, but won't detect key presses

### Slave Pico (`test_slave.py`)
- **Display Tests:** Take 10-15 seconds total due to e-ink refresh times
  - Partial refresh: ~1-2 seconds
  - Full refresh: ~3-5 seconds
- **UART Loopback:** Requires temporary wire connecting GP8 (TX) to GP9 (RX)
  - **Remove wire before connecting to Master Pico!**
- **Visual Verification:** You should see "PARTIAL" and "FULL REFRESH" on display

## Troubleshooting

### Master Pico

**I2C fails:**
- Check TCA8418 wiring: SDA→GP2, SCL→GP3
- Verify 3.3V power to TCA8418
- Ensure common ground

**TCA8418 not found at 0x34:**
- Check I2C address (might be 0x35 if A0 pin is high)
- Verify I2C pull-ups (some boards need external 4.7kΩ resistors)

**UART loopback fails:**
- Ensure loopback wire is firmly connected: GP8→GP9
- Check no other device is connected to UART pins
- Verify UART1 (not UART0)

### Slave Pico

**SPI fails:**
- Check display wiring: SCK→GP10, MOSI→GP11
- Verify all control pins connected

**Display doesn't initialize:**
- Check 3.3V power to display
- Ensure all pins connected: CS, DC, RST, BUSY
- Try pressing Pico RESET button

**Display refresh takes too long:**
- Normal behavior - e-ink displays are slow
- Partial refresh: 1-2 seconds
- Full refresh: 3-5 seconds

**BUSY pin always HIGH:**
- Display may be refreshing
- Wait for refresh to complete
- Check BUSY pin connection (GP16)

## Test Development

### Adding New Tests

1. **Hardware tests:** Add to `test_master.py` or `test_slave.py`
2. **Application tests:** Add to `test_master_unit.py` or `test_slave_unit.py`
3. **Shared tests:** Add to `tests/test_text_layout.py` or `tests/test_uart_protocol.py`

### Test Function Template

```python
def test_new_feature():
    """Test description"""
    # Test implementation

    if condition:
        return True, "Success message"
    else:
        return False, "Failure message"
```

### Running Specific Tests

Modify the `run_all_tests()` function to comment out unwanted tests, or create a custom test runner:

```python
# Run only I2C tests
print_test(1, 1, "I2C Bus Initialization")
passed, i2c, details = test_i2c_initialization()
print_result(passed, details)
```

## Integration Testing

### Master ↔ Slave Communication

After both hardware test suites pass independently:

1. **Remove loopback wires** from both Picos
2. **Connect UART crossover:**
   - Master GP8 (TX) → Slave GP9 (RX)
   - Master GP9 (RX) ← Slave GP8 (TX)
   - Common GND between both
3. **Run main applications:**
   - Master: `import main` (in `rpi1/`)
   - Slave: `import main` (in `rpi2/`)
4. **Test end-to-end:**
   - Press keys on keyboard → should appear on display
   - Wait 2 minutes → screensaver should activate
   - Press key → screensaver should clear

## Performance Benchmarks

### Expected Test Execution Times

| Test Suite | Duration | Notes |
|------------|----------|-------|
| Master Hardware | 300-500ms | Without display refresh |
| Slave Hardware | 10-15s | Includes display refresh |
| Master Unit | 50-100ms | Pure logic |
| Slave Unit | 50-100ms | Pure logic |
| TextLayout | 100-200ms | Edge cases |
| UART Protocol | 50-100ms | Including 100-iteration tests |

### Hardware Performance

- **I2C (TCA8418):** 400kHz bus speed
- **SPI (Display):** 4MHz bus speed
- **UART:** 115200 baud
- **JSON serialization:** ~1ms per message
- **Display partial refresh:** 1-2 seconds
- **Display full refresh:** 3-5 seconds

## Continuous Integration

These tests are designed to run on actual hardware. For CI/CD:

1. **Unit tests** can run on any Python environment
2. **Hardware tests** require actual Pico 2W hardware
3. **Integration tests** require full system setup

Consider using hardware-in-the-loop (HIL) testing for automated CI.

## License

Same license as main project.

## Authors

Generated by Claude Code for Linson Writer's Deck project.
