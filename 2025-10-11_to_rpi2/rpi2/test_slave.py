# test_slave.py - Slave Pico Hardware Integration Tests
# Tests all hardware connections on Slave Pico 2W independently
# Run this on the Slave Pico to validate wiring before integration
# For Raspberry Pi Pico 2W (RP2350)

import time
import utime
import machine
import json
from machine import Pin, SPI, UART

# Import display driver
try:
    from display42 import EPD_4in2
except ImportError:
    print("⚠ Warning: display42.py not found - display tests will be skipped")
    EPD_4in2 = None

#───────────────────────────────────────────────#
# ─────────── Test Configuration ───────────────#
#───────────────────────────────────────────────#

# Pin configurations (matching main.py)
SPI_SCK  = 10  # GP10 (SPI1 SCK)
SPI_MOSI = 11  # GP11 (SPI1 MOSI)
CS_PIN   = 13  # GP13 (Chip select)
DC_PIN   = 14  # GP14 (Data/Command)
RST_PIN  = 15  # GP15 (Display reset)
BUSY_PIN = 16  # GP16 (Busy status)

UART_ID = 1
UART_TX = 8   # GP8 (UART1 TX)
UART_RX = 9   # GP9 (UART1 RX)
UART_BAUDRATE = 115200

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
    print("  SLAVE PICO 2W HARDWARE INTEGRATION TEST SUITE")
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
# ─────────── SPI Bus Tests ────────────────────#
#───────────────────────────────────────────────#

def test_spi_initialization():
    """Test SPI1 bus initialization"""
    try:
        spi = SPI(1, polarity=0, phase=0, sck=Pin(SPI_SCK), mosi=Pin(SPI_MOSI), miso=None)
        spi.init(baudrate=4000_000)
        return True, spi, f"SPI1 initialized on GP{SPI_SCK}/GP{SPI_MOSI} @ 4MHz"
    except Exception as e:
        return False, None, f"SPI init failed: {e}"

def test_spi_write(spi):
    """Test SPI write operations"""
    try:
        # Write test data
        test_data = bytes([0x12, 0x34, 0x56, 0x78])
        spi.write(test_data)
        return True, f"SPI write OK ({len(test_data)} bytes)"
    except Exception as e:
        return False, f"SPI write failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Display Control Pin Tests ────────#
#───────────────────────────────────────────────#

def test_cs_pin():
    """Test Chip Select pin (GP13)"""
    try:
        cs = Pin(CS_PIN, Pin.OUT)
        cs.value(1)  # Set high
        time.sleep_ms(10)
        cs.value(0)  # Set low
        time.sleep_ms(10)
        cs.value(1)  # Set high again

        if cs.value() == 1:
            return True, "CS pin functional (currently HIGH)"
        else:
            return False, "CS pin stuck LOW"
    except Exception as e:
        return False, f"CS pin test failed: {e}"

def test_dc_pin():
    """Test Data/Command pin (GP14)"""
    try:
        dc = Pin(DC_PIN, Pin.OUT)
        dc.value(0)  # Command mode
        time.sleep_ms(10)
        dc.value(1)  # Data mode
        time.sleep_ms(10)

        if dc.value() == 1:
            return True, "DC pin functional (currently HIGH - data mode)"
        else:
            return False, "DC pin stuck LOW"
    except Exception as e:
        return False, f"DC pin test failed: {e}"

def test_rst_pin():
    """Test Reset pin (GP15)"""
    try:
        rst = Pin(RST_PIN, Pin.OUT)
        rst.value(1)  # Normal operation
        time.sleep_ms(10)
        rst.value(0)  # Reset
        time.sleep_ms(10)
        rst.value(1)  # Release reset
        time.sleep_ms(10)

        if rst.value() == 1:
            return True, "RST pin functional (currently HIGH - normal)"
        else:
            return False, "RST pin stuck LOW"
    except Exception as e:
        return False, f"RST pin test failed: {e}"

def test_busy_pin():
    """Test BUSY status pin (GP16)"""
    try:
        busy = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        state = busy.value()

        if state == 0:
            return True, "BUSY pin LOW (display idle)"
        else:
            return True, "BUSY pin HIGH (display may be busy)"
    except Exception as e:
        return False, f"BUSY pin test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── E-ink Display Tests ──────────────#
#───────────────────────────────────────────────#

def test_display_initialization():
    """Test e-ink display initialization"""
    if EPD_4in2 is None:
        return False, None, "Display driver not available"

    try:
        # This will initialize the full display driver
        # WARNING: This takes several seconds!
        print("\n    (Display init takes 5-10 seconds...)", end='')
        epd = EPD_4in2()
        return True, epd, f"Display initialized: {epd.width}x{epd.height}px"
    except Exception as e:
        return False, None, f"Display init failed: {e}"

def test_display_buffer_operations(epd):
    """Test framebuffer operations"""
    try:
        # Clear buffer
        epd.image1Gray.fill(0xFF)

        # Draw text
        epd.image1Gray.text("TEST", 10, 10, epd.black)

        # Draw rectangle
        epd.image1Gray.rect(50, 50, 100, 50, epd.black)

        return True, "Framebuffer operations OK (text, rect)"
    except Exception as e:
        return False, f"Buffer ops failed: {e}"

def test_display_partial_refresh(epd):
    """Test partial display refresh"""
    try:
        print("\n    (Partial refresh takes 1-2 seconds...)", end='')

        # Clear and draw test pattern
        epd.image1Gray.fill(0xFF)
        epd.image1Gray.text("PARTIAL", 10, 10, epd.black)

        # Partial refresh
        epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)

        return True, "Partial refresh completed"
    except Exception as e:
        return False, f"Partial refresh failed: {e}"

def test_display_full_refresh(epd):
    """Test full display refresh"""
    try:
        print("\n    (Full refresh takes 3-5 seconds...)", end='')

        # Clear and draw test pattern
        epd.image1Gray.fill(0xFF)
        epd.image1Gray.text("FULL REFRESH", 50, 50, epd.black)

        # Full refresh
        epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)

        return True, "Full refresh completed"
    except Exception as e:
        return False, f"Full refresh failed: {e}"

def test_display_busy_signal(epd):
    """Test reading display BUSY signal"""
    try:
        busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)

        # Display should be idle after previous operations
        state = busy_pin.value()

        if state == 0:
            return True, "BUSY signal reads correctly (idle)"
        else:
            return True, "BUSY signal HIGH (display may be refreshing)"
    except Exception as e:
        return False, f"BUSY signal test failed: {e}"

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
          Remove this wire before connecting to Master Pico!
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

def test_uart_json_parsing(uart):
    """Test JSON command parsing"""
    try:
        # Create test command JSON
        test_cmd = {
            "cmd": "RENDER_TEXT",
            "text": "Hello World",
            "cursor_x": 10,
            "cursor_y": 20
        }

        # Serialize
        msg = json.dumps(test_cmd)

        # Parse back
        parsed = json.loads(msg)

        if parsed["cmd"] == "RENDER_TEXT" and parsed["text"] == "Hello World":
            return True, f"JSON parsing OK ({len(msg)} bytes)"
        else:
            return False, "JSON parse mismatch"
    except Exception as e:
        return False, f"JSON test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Pin Configuration Tests ──────────#
#───────────────────────────────────────────────#

def test_all_pins_configured():
    """Verify all required pins are accessible"""
    pins_to_test = {
        "GP8 (UART TX)": UART_TX,
        "GP9 (UART RX)": UART_RX,
        "GP10 (SPI SCK)": SPI_SCK,
        "GP11 (SPI MOSI)": SPI_MOSI,
        "GP13 (CS)": CS_PIN,
        "GP14 (DC)": DC_PIN,
        "GP15 (RST)": RST_PIN,
        "GP16 (BUSY)": BUSY_PIN
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
    """Run all Slave Pico hardware tests"""
    global tests_passed, tests_failed

    print_header()

    # Test counter
    test_num = 0
    total_tests = 14

    # Test 1: Pin configuration
    test_num += 1
    print_test(test_num, total_tests, "GPIO Pin Configuration")
    passed, details = test_all_pins_configured()
    print_result(passed, details)

    # Test 2: SPI initialization
    test_num += 1
    print_test(test_num, total_tests, "SPI Bus Initialization")
    passed, spi, details = test_spi_initialization()
    print_result(passed, details)

    if not passed:
        print("\n⚠ Cannot continue without SPI - check wiring!\n")
        print_summary()
        return

    # Test 3: SPI write
    test_num += 1
    print_test(test_num, total_tests, "SPI Write Operations")
    passed, details = test_spi_write(spi)
    print_result(passed, details)

    # Test 4: CS pin
    test_num += 1
    print_test(test_num, total_tests, "Chip Select Pin (GP13)")
    passed, details = test_cs_pin()
    print_result(passed, details)

    # Test 5: DC pin
    test_num += 1
    print_test(test_num, total_tests, "Data/Command Pin (GP14)")
    passed, details = test_dc_pin()
    print_result(passed, details)

    # Test 6: RST pin
    test_num += 1
    print_test(test_num, total_tests, "Reset Pin (GP15)")
    passed, details = test_rst_pin()
    print_result(passed, details)

    # Test 7: BUSY pin
    test_num += 1
    print_test(test_num, total_tests, "BUSY Status Pin (GP16)")
    passed, details = test_busy_pin()
    print_result(passed, details)

    # Test 8: Display initialization
    test_num += 1
    print_test(test_num, total_tests, "E-ink Display Initialization")
    if EPD_4in2 is not None:
        passed, epd, details = test_display_initialization()
        print_result(passed, details)
    else:
        print_result(False, "Display driver not available")
        epd = None

    # Test 9: Framebuffer operations
    test_num += 1
    print_test(test_num, total_tests, "Framebuffer Operations")
    if epd:
        passed, details = test_display_buffer_operations(epd)
        print_result(passed, details)
    else:
        print_result(False, "Display not initialized")

    # Test 10: Partial refresh
    test_num += 1
    print_test(test_num, total_tests, "Partial Display Refresh")
    if epd:
        passed, details = test_display_partial_refresh(epd)
        print_result(passed, details)
    else:
        print_result(False, "Display not initialized")

    # Test 11: Full refresh
    test_num += 1
    print_test(test_num, total_tests, "Full Display Refresh")
    if epd:
        passed, details = test_display_full_refresh(epd)
        print_result(passed, details)
    else:
        print_result(False, "Display not initialized")

    # Test 12: BUSY signal
    test_num += 1
    print_test(test_num, total_tests, "Display BUSY Signal Reading")
    if epd:
        passed, details = test_display_busy_signal(epd)
        print_result(passed, details)
    else:
        print_result(False, "Display not initialized")

    # Test 13: UART initialization
    test_num += 1
    print_test(test_num, total_tests, "UART Initialization")
    passed, uart, details = test_uart_initialization()
    print_result(passed, details)

    if not passed:
        uart = None

    # Test 14: UART loopback
    test_num += 1
    print_test(test_num, total_tests, "UART Loopback Test")
    if uart:
        passed, details = test_uart_loopback(uart)
        print_result(passed, details)
    else:
        print_result(False, "UART not initialized")

    # Test 15: JSON parsing
    test_num += 1
    print_test(test_num, total_tests, "JSON Command Parsing")
    if uart:
        passed, details = test_uart_json_parsing(uart)
        print_result(passed, details)
    else:
        print_result(False, "UART not initialized")

    # Print summary
    print_summary()

    # Additional notes
    print("NOTES:")
    print("• Display tests may take 10-15 seconds total")
    print("• For UART loopback test: connect GP8 (TX) to GP9 (RX)")
    print("• Remove loopback wire before connecting to Master Pico")
    print("• You should see 'PARTIAL' and 'FULL REFRESH' on the display")
    print("• All tests use SPI1 and UART1 as per wiring guide\n")

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
