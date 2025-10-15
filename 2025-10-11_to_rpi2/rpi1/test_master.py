# test_master.py - Master Pico Hardware Integration Tests
# Tests all hardware connections on Master Pico 2W independently
# Run this on the Master Pico to validate wiring before integration
# For Raspberry Pi Pico 2W (RP2350)

import time
import utime
import machine
import json
from machine import Pin, I2C, UART

# Import TCA8418 driver
try:
    from tca8418 import TCA8418
except ImportError:
    print("⚠ Warning: tca8418.py not found - keyboard tests will be skipped")
    TCA8418 = None

#───────────────────────────────────────────────#
# ─────────── Test Configuration ───────────────#
#───────────────────────────────────────────────#

# Pin configurations (matching main.py)
I2C_SDA = 2   # GP2 (I2C1 SDA)
I2C_SCL = 3   # GP3 (I2C1 SCL)
TCA_INT = 20  # GP20
TCA_RST = 21  # GP21

UART_ID = 1
UART_TX = 8   # GP8 (UART1 TX)
UART_RX = 9   # GP9 (UART1 RX)
UART_BAUDRATE = 115200

POWER_BTN_PIN = 22  # GP22

# Test state
tests_passed = 0
tests_failed = 0
test_start_time = 0

#───────────────────────────────────────────────#
# ─────────── Test Helper Functions ────────────#
#───────────────────────────────────────────────#

def print_header():
    """Print test suite header"""
    print("\n" + "="*55)
    print("  MASTER PICO 2W HARDWARE INTEGRATION TEST SUITE")
    print("="*55)
    print(f"Date: {time.localtime()}")
    print(f"Board: Raspberry Pi Pico 2W (RP2350)")
    print("="*55 + "\n")

def print_test(num, total, name):
    """Print test start message"""
    global test_start_time
    test_start_time = utime.ticks_ms()
    print(f"[{num}/{total}] {name}...", end='')

def print_result(passed, details="", elapsed_ms=None):
    """Print test result"""
    global tests_passed, tests_failed, test_start_time

    if elapsed_ms is None:
        elapsed_ms = utime.ticks_diff(utime.ticks_ms(), test_start_time)

    if passed:
        tests_passed += 1
        print(f" ✓ PASS ({elapsed_ms}ms)")
    else:
        tests_failed += 1
        print(f" ✗ FAIL ({elapsed_ms}ms)")

    if details:
        print(f"    {details}")

def print_summary():
    """Print test summary"""
    total = tests_passed + tests_failed
    print("\n" + "="*55)
    print(f"  RESULTS: {tests_passed}/{total} PASSED")
    if tests_failed > 0:
        print(f"  FAILED: {tests_failed} tests")
    print("="*55 + "\n")

#───────────────────────────────────────────────#
# ─────────── I2C Bus Tests ────────────────────#
#───────────────────────────────────────────────#

def test_i2c_initialization():
    """Test I2C bus initialization on I2C1"""
    try:
        i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
        return True, i2c, "I2C1 initialized on GP2/GP3 @ 400kHz"
    except Exception as e:
        return False, None, f"I2C init failed: {e}"

def test_i2c_scan(i2c):
    """Scan I2C bus for devices"""
    try:
        devices = i2c.scan()
        if devices:
            device_str = ", ".join([f"0x{addr:02X}" for addr in devices])
            return True, devices, f"Found {len(devices)} device(s): {device_str}"
        else:
            return False, [], "No I2C devices found - check wiring"
    except Exception as e:
        return False, [], f"I2C scan failed: {e}"

def test_tca8418_detection(i2c):
    """Test TCA8418 device detection at 0x34"""
    try:
        devices = i2c.scan()
        TCA_ADDR = 0x34

        if TCA_ADDR in devices:
            # Try to read a register to verify communication
            i2c.writeto(TCA_ADDR, bytes([0x01]))  # CFG register
            data = i2c.readfrom(TCA_ADDR, 1)
            return True, f"TCA8418 detected at 0x{TCA_ADDR:02X}, CFG=0x{data[0]:02X}"
        else:
            return False, f"TCA8418 not found at 0x{TCA_ADDR:02X}"
    except Exception as e:
        return False, f"TCA8418 detection failed: {e}"

#───────────────────────────────────────────────#
# ─────────── TCA8418 Keyboard Tests ───────────#
#───────────────────────────────────────────────#

def test_tca8418_initialization(i2c):
    """Test TCA8418 driver initialization"""
    if TCA8418 is None:
        return False, "TCA8418 driver not available"

    try:
        interrupt_pin = Pin(TCA_INT, Pin.IN, Pin.PULL_UP)
        reset_pin = Pin(TCA_RST, Pin.OUT, value=1)

        keyboard = TCA8418(i2c, interrupt_pin=interrupt_pin, reset_pin=reset_pin)
        return True, keyboard, "TCA8418 driver initialized successfully"
    except Exception as e:
        return False, None, f"TCA8418 init failed: {e}"

def test_keyboard_interrupt_pin():
    """Test keyboard interrupt pin (GP20)"""
    try:
        int_pin = Pin(TCA_INT, Pin.IN, Pin.PULL_UP)

        # Check pin state (should be HIGH when idle, LOW when keys pressed)
        state = int_pin.value()

        if state == 1:
            return True, "INT pin HIGH (idle state) - correct"
        else:
            return True, "INT pin LOW (active) - keys may be pressed or pending"
    except Exception as e:
        return False, f"INT pin test failed: {e}"

def test_keyboard_reset_pin():
    """Test keyboard reset pin (GP21)"""
    try:
        rst_pin = Pin(TCA_RST, Pin.OUT, value=1)

        # Test toggle
        rst_pin.value(0)
        time.sleep_ms(10)
        rst_pin.value(1)
        time.sleep_ms(10)

        state = rst_pin.value()
        if state == 1:
            return True, "RST pin functional (active high)"
        else:
            return False, "RST pin stuck low"
    except Exception as e:
        return False, f"RST pin test failed: {e}"

def test_keyboard_fifo(keyboard):
    """Test keyboard FIFO operations"""
    try:
        # Clear any pending events
        keyboard.clear_interrupts()

        # Check FIFO is empty
        count = keyboard.get_key_count()

        if count == 0:
            return True, "FIFO empty after clear"
        else:
            return True, f"FIFO contains {count} event(s) - may have pending keys"
    except Exception as e:
        return False, f"FIFO test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Power Button Tests ───────────────#
#───────────────────────────────────────────────#

def test_power_button():
    """Test power button on GP22"""
    try:
        btn_pin = Pin(POWER_BTN_PIN, Pin.IN, Pin.PULL_UP)

        # Read button state
        state = btn_pin.value()

        if state == 1:
            return True, "Power button released (pulled HIGH)"
        else:
            return True, "Power button pressed (LOW) - button is being held"
    except Exception as e:
        return False, f"Power button test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── UART Tests ───────────────────────#
#───────────────────────────────────────────────#

def test_uart_initialization():
    """Test UART1 initialization"""
    try:
        uart = UART(UART_ID, baudrate=UART_BAUDRATE,
                   tx=Pin(UART_TX), rx=Pin(UART_RX))
        return True, uart, f"UART1 initialized on GP{UART_TX}/GP{UART_RX} @ {UART_BAUDRATE} baud"
    except Exception as e:
        return False, None, f"UART init failed: {e}"

def test_uart_loopback(uart):
    """
    Test UART loopback (requires TX connected to RX externally)

    NOTE: This test requires a wire connecting GP8 (TX) to GP9 (RX)
          Remove this wire before connecting to Slave Pico!
    """
    try:
        # Clear receive buffer
        while uart.any():
            uart.read()

        # Send test message
        test_msg = b"LOOPBACK_TEST\n"
        uart.write(test_msg)
        time.sleep_ms(50)

        # Try to receive
        if uart.any():
            received = uart.read()
            if received == test_msg:
                return True, "Loopback successful - TX→RX working"
            else:
                return False, f"Loopback mismatch: sent {test_msg}, got {received}"
        else:
            return False, "No loopback data received - connect GP8 to GP9 for this test"
    except Exception as e:
        return False, f"Loopback test failed: {e}"

def test_uart_json_serialization(uart):
    """Test JSON command serialization"""
    try:
        # Create test command
        test_cmd = {
            "cmd": "TEST",
            "text": "Hello World",
            "cursor_x": 10,
            "cursor_y": 20
        }

        # Serialize to JSON
        msg = json.dumps(test_cmd) + '\n'

        # Verify serialization worked
        if len(msg) > 0 and msg.endswith('\n'):
            return True, f"JSON serialization OK ({len(msg)} bytes)"
        else:
            return False, "JSON serialization failed"
    except Exception as e:
        return False, f"JSON test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Pin Configuration Tests ──────────#
#───────────────────────────────────────────────#

def test_all_pins_configured():
    """Verify all required pins are accessible"""
    pins_to_test = {
        "GP2 (I2C SDA)": I2C_SDA,
        "GP3 (I2C SCL)": I2C_SCL,
        "GP8 (UART TX)": UART_TX,
        "GP9 (UART RX)": UART_RX,
        "GP20 (INT)": TCA_INT,
        "GP21 (RST)": TCA_RST,
        "GP22 (PWR BTN)": POWER_BTN_PIN
    }

    failed_pins = []

    try:
        for name, pin_num in pins_to_test.items():
            try:
                test_pin = Pin(pin_num, Pin.IN)
                test_pin.value()  # Try to read
            except Exception as e:
                failed_pins.append(f"{name}: {e}")

        if not failed_pins:
            return True, f"All {len(pins_to_test)} GPIO pins accessible"
        else:
            return False, f"Pin errors: {', '.join(failed_pins)}"
    except Exception as e:
        return False, f"Pin test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Main Test Runner ─────────────────#
#───────────────────────────────────────────────#

def run_all_tests():
    """Run all Master Pico hardware tests"""
    global tests_passed, tests_failed

    print_header()

    # Test counter
    test_num = 0
    total_tests = 12

    # Test 1: Pin configuration
    test_num += 1
    print_test(test_num, total_tests, "GPIO Pin Configuration")
    passed, details = test_all_pins_configured()
    print_result(passed, details)

    # Test 2: I2C initialization
    test_num += 1
    print_test(test_num, total_tests, "I2C Bus Initialization")
    passed, i2c, details = test_i2c_initialization()
    print_result(passed, details)

    if not passed:
        print("\n⚠ Cannot continue without I2C - check wiring!\n")
        print_summary()
        return

    # Test 3: I2C scan
    test_num += 1
    print_test(test_num, total_tests, "I2C Device Scan")
    passed, devices, details = test_i2c_scan(i2c)
    print_result(passed, details)

    # Test 4: TCA8418 detection
    test_num += 1
    print_test(test_num, total_tests, "TCA8418 Device Detection")
    passed, details = test_tca8418_detection(i2c)
    print_result(passed, details)

    # Test 5: TCA8418 initialization
    test_num += 1
    print_test(test_num, total_tests, "TCA8418 Driver Initialization")
    if TCA8418 is not None:
        passed, keyboard, details = test_tca8418_initialization(i2c)
        print_result(passed, details)
    else:
        print_result(False, "TCA8418 driver not available")
        keyboard = None

    # Test 6: Keyboard interrupt pin
    test_num += 1
    print_test(test_num, total_tests, "Keyboard Interrupt Pin (GP20)")
    passed, details = test_keyboard_interrupt_pin()
    print_result(passed, details)

    # Test 7: Keyboard reset pin
    test_num += 1
    print_test(test_num, total_tests, "Keyboard Reset Pin (GP21)")
    passed, details = test_keyboard_reset_pin()
    print_result(passed, details)

    # Test 8: Keyboard FIFO
    test_num += 1
    print_test(test_num, total_tests, "Keyboard FIFO Operations")
    if keyboard:
        passed, details = test_keyboard_fifo(keyboard)
        print_result(passed, details)
    else:
        print_result(False, "Keyboard not initialized")

    # Test 9: Power button
    test_num += 1
    print_test(test_num, total_tests, "Power Button Detection (GP22)")
    passed, details = test_power_button()
    print_result(passed, details)

    # Test 10: UART initialization
    test_num += 1
    print_test(test_num, total_tests, "UART Initialization")
    passed, uart, details = test_uart_initialization()
    print_result(passed, details)

    if not passed:
        uart = None

    # Test 11: UART loopback
    test_num += 1
    print_test(test_num, total_tests, "UART Loopback Test")
    if uart:
        passed, details = test_uart_loopback(uart)
        print_result(passed, details)
    else:
        print_result(False, "UART not initialized")

    # Test 12: JSON serialization
    test_num += 1
    print_test(test_num, total_tests, "JSON Command Serialization")
    if uart:
        passed, details = test_uart_json_serialization(uart)
        print_result(passed, details)
    else:
        print_result(False, "UART not initialized")

    # Print summary
    print_summary()

    # Additional notes
    print("NOTES:")
    print("• For UART loopback test: connect GP8 (TX) to GP9 (RX)")
    print("• Remove loopback wire before connecting to Slave Pico")
    print("• Press keyboard keys to verify physical keyboard connections")
    print("• All tests use I2C1 and UART1 as per wiring guide\n")

#───────────────────────────────────────────────#
# ─────────── Entry Point ──────────────────────#
#───────────────────────────────────────────────#

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠ Tests interrupted by user\n")
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}\n")
        import sys
        sys.print_exception(e)
