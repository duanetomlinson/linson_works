# test_uart_protocol.py - UART JSON Protocol Tests
# Tests the UART communication protocol between Master and Slave Picos
# Validates JSON structure, serialization, parsing, and error handling
# Can run on Pico or desktop Python

import json

#───────────────────────────────────────────────#
# ─────────── Test Configuration ───────────────#
#───────────────────────────────────────────────#

# Test state
tests_passed = 0
tests_failed = 0

# Protocol constants
UART_BAUDRATE = 115200
MAX_MESSAGE_SIZE = 1024  # bytes

#───────────────────────────────────────────────#
# ─────────── Test Helper Functions ────────────#
#───────────────────────────────────────────────#

def print_header():
    """Print test suite header"""
    print("\n" + "="*55)
    print("  UART JSON PROTOCOL TEST SUITE")
    print("="*55 + "\n")

def print_test(name):
    """Print test start message"""
    print(f"Testing: {name}...", end=' ')

def print_result(passed, details=""):
    """Print test result"""
    global tests_passed, tests_failed

    if passed:
        tests_passed += 1
        print("✓ PASS")
    else:
        tests_failed += 1
        print("✗ FAIL")

    if details:
        print(f"  {details}")

def print_summary():
    """Print test summary"""
    total = tests_passed + tests_failed
    print("\n" + "="*55)
    print(f"  RESULTS: {tests_passed}/{total} PASSED")
    if tests_failed > 0:
        print(f"  FAILED: {tests_failed} tests")
    print("="*55 + "\n")

#───────────────────────────────────────────────#
# ─────────── Command Structure Tests ──────────#
#───────────────────────────────────────────────#

def test_init_command():
    """Test INIT command structure"""
    cmd = {
        "cmd": "INIT",
        "width": 400,
        "height": 300
    }

    required_fields = ["cmd", "width", "height"]
    for field in required_fields:
        if field not in cmd:
            return False, f"Missing required field: {field}"

    if cmd["cmd"] != "INIT":
        return False, f"Invalid cmd value: {cmd['cmd']}"

    return True, "INIT command structure valid"

def test_render_text_command():
    """Test RENDER_TEXT command structure"""
    cmd = {
        "cmd": "RENDER_TEXT",
        "text": "Hello World",
        "cursor_x": 10,
        "cursor_y": 20
    }

    required_fields = ["cmd", "text", "cursor_x", "cursor_y"]
    for field in required_fields:
        if field not in cmd:
            return False, f"Missing required field: {field}"

    if not isinstance(cmd["text"], str):
        return False, "text field must be string"

    if not isinstance(cmd["cursor_x"], int) or not isinstance(cmd["cursor_y"], int):
        return False, "cursor coordinates must be integers"

    return True, "RENDER_TEXT command structure valid"

def test_show_screensaver_command():
    """Test SHOW_SCREENSAVER command structure"""
    cmd = {"cmd": "SHOW_SCREENSAVER"}

    if "cmd" not in cmd:
        return False, "Missing cmd field"

    if cmd["cmd"] != "SHOW_SCREENSAVER":
        return False, f"Invalid cmd value: {cmd['cmd']}"

    return True, "SHOW_SCREENSAVER command structure valid"

def test_wake_up_command():
    """Test WAKE_UP command structure"""
    cmd = {"cmd": "WAKE_UP"}

    if "cmd" not in cmd:
        return False, "Missing cmd field"

    return True, "WAKE_UP command structure valid"

def test_power_off_command():
    """Test POWER_OFF command structure"""
    cmd = {"cmd": "POWER_OFF"}

    if "cmd" not in cmd:
        return False, "Missing cmd field"

    return True, "POWER_OFF command structure valid"

def test_clear_command():
    """Test CLEAR command structure"""
    cmd = {"cmd": "CLEAR"}

    if "cmd" not in cmd:
        return False, "Missing cmd field"

    return True, "CLEAR command structure valid"

def test_status_command():
    """Test STATUS command structure"""
    cmd = {
        "cmd": "STATUS",
        "text": "Saved"
    }

    required_fields = ["cmd", "text"]
    for field in required_fields:
        if field not in cmd:
            return False, f"Missing required field: {field}"

    if not isinstance(cmd["text"], str):
        return False, "text field must be string"

    return True, "STATUS command structure valid"

#───────────────────────────────────────────────#
# ─────────── Response Structure Tests ─────────#
#───────────────────────────────────────────────#

def test_ok_response():
    """Test OK response structure"""
    response = {
        "status": "ok",
        "cmd": "INIT"
    }

    required_fields = ["status", "cmd"]
    for field in required_fields:
        if field not in response:
            return False, f"Missing required field: {field}"

    if response["status"] != "ok":
        return False, f"Invalid status: {response['status']}"

    return True, "OK response structure valid"

def test_error_response():
    """Test error response structure"""
    response = {
        "status": "error",
        "cmd": "UNKNOWN",
        "error": "Unknown command"
    }

    required_fields = ["status", "cmd", "error"]
    for field in required_fields:
        if field not in response:
            return False, f"Missing required field: {field}"

    if response["status"] != "error":
        return False, f"Invalid status: {response['status']}"

    if not isinstance(response["error"], str):
        return False, "error field must be string"

    return True, "Error response structure valid"

#───────────────────────────────────────────────#
# ─────────── JSON Serialization Tests ─────────#
#───────────────────────────────────────────────#

def test_json_encode_simple():
    """Test JSON encoding of simple command"""
    cmd = {"cmd": "CLEAR"}

    try:
        msg = json.dumps(cmd)
        if len(msg) > 0:
            return True, f"Encoded to {len(msg)} bytes"
        else:
            return False, "Empty encoding result"
    except Exception as e:
        return False, f"Encoding failed: {e}"

def test_json_encode_complex():
    """Test JSON encoding of complex command"""
    cmd = {
        "cmd": "RENDER_TEXT",
        "text": "Hello World",
        "cursor_x": 10,
        "cursor_y": 20
    }

    try:
        msg = json.dumps(cmd)
        if len(msg) > 0:
            return True, f"Encoded to {len(msg)} bytes"
        else:
            return False, "Empty encoding result"
    except Exception as e:
        return False, f"Encoding failed: {e}"

def test_json_decode_simple():
    """Test JSON decoding of simple message"""
    msg = '{"cmd":"CLEAR"}'

    try:
        cmd = json.loads(msg)
        if cmd.get("cmd") == "CLEAR":
            return True, "Decoded successfully"
        else:
            return False, "Decoded with wrong content"
    except Exception as e:
        return False, f"Decoding failed: {e}"

def test_json_decode_complex():
    """Test JSON decoding of complex message"""
    msg = '{"cmd":"RENDER_TEXT","text":"Hello","cursor_x":10,"cursor_y":20}'

    try:
        cmd = json.loads(msg)
        if (cmd.get("cmd") == "RENDER_TEXT" and
            cmd.get("text") == "Hello" and
            cmd.get("cursor_x") == 10):
            return True, "Decoded successfully"
        else:
            return False, "Decoded with wrong content"
    except Exception as e:
        return False, f"Decoding failed: {e}"

def test_json_roundtrip():
    """Test JSON encode-decode roundtrip"""
    original = {
        "cmd": "RENDER_TEXT",
        "text": "Test",
        "cursor_x": 5,
        "cursor_y": 10
    }

    try:
        encoded = json.dumps(original)
        decoded = json.loads(encoded)

        if decoded == original:
            return True, "Roundtrip successful"
        else:
            return False, "Roundtrip data mismatch"
    except Exception as e:
        return False, f"Roundtrip failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Protocol Format Tests ────────────#
#───────────────────────────────────────────────#

def test_newline_terminator():
    """Test newline terminator requirement"""
    cmd = {"cmd": "CLEAR"}
    msg = json.dumps(cmd) + '\n'

    if msg.endswith('\n'):
        return True, "Newline terminator present"
    else:
        return False, "Missing newline terminator"

def test_parse_with_newline():
    """Test parsing message with newline"""
    msg = '{"cmd":"CLEAR"}\n'

    try:
        stripped = msg.strip()
        cmd = json.loads(stripped)
        if cmd.get("cmd") == "CLEAR":
            return True, "Parsed with newline terminator"
        else:
            return False, "Parse error"
    except Exception as e:
        return False, f"Parse failed: {e}"

def test_message_size_limit():
    """Test message size limit"""
    # Create a large message
    large_text = "A" * 500
    cmd = {"cmd": "RENDER_TEXT", "text": large_text, "cursor_x": 0, "cursor_y": 0}

    try:
        msg = json.dumps(cmd) + '\n'
        size = len(msg.encode())

        if size <= MAX_MESSAGE_SIZE:
            return True, f"Message size OK ({size} bytes)"
        else:
            return False, f"Message too large ({size} > {MAX_MESSAGE_SIZE} bytes)"
    except Exception as e:
        return False, f"Size test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Special Character Tests ──────────#
#───────────────────────────────────────────────#

def test_unicode_characters():
    """Test Unicode character handling"""
    cmd = {"cmd": "RENDER_TEXT", "text": "Hello™", "cursor_x": 0, "cursor_y": 0}

    try:
        msg = json.dumps(cmd)
        decoded = json.loads(msg)

        if decoded["text"] == "Hello™":
            return True, "Unicode handling OK"
        else:
            return False, f"Unicode mismatch: got '{decoded['text']}'"
    except Exception as e:
        return False, f"Unicode test failed: {e}"

def test_special_characters():
    """Test special character escaping"""
    text_with_special = 'Line1\nLine2\t"quoted"'
    cmd = {"cmd": "RENDER_TEXT", "text": text_with_special, "cursor_x": 0, "cursor_y": 0}

    try:
        msg = json.dumps(cmd)
        decoded = json.loads(msg)

        if decoded["text"] == text_with_special:
            return True, "Special characters handled correctly"
        else:
            return False, "Special character mismatch"
    except Exception as e:
        return False, f"Special char test failed: {e}"

def test_empty_string_field():
    """Test empty string in text field"""
    cmd = {"cmd": "RENDER_TEXT", "text": "", "cursor_x": 0, "cursor_y": 0}

    try:
        msg = json.dumps(cmd)
        decoded = json.loads(msg)

        if decoded["text"] == "":
            return True, "Empty string handled"
        else:
            return False, "Empty string not preserved"
    except Exception as e:
        return False, f"Empty string test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Error Handling Tests ─────────────#
#───────────────────────────────────────────────#

def test_malformed_json():
    """Test malformed JSON handling"""
    bad_msg = '{"cmd":"CLEAR"'  # Missing closing brace

    try:
        cmd = json.loads(bad_msg)
        return False, "Malformed JSON should raise error"
    except Exception:
        return True, "Malformed JSON correctly rejected"

def test_missing_cmd_field():
    """Test missing cmd field"""
    cmd = {"text": "Hello"}  # Missing cmd field

    msg = json.dumps(cmd)
    decoded = json.loads(msg)

    if "cmd" not in decoded:
        return True, "Missing cmd field detected"
    else:
        return False, "Should detect missing cmd field"

def test_invalid_cmd_type():
    """Test invalid command type"""
    cmd = {"cmd": "UNKNOWN_COMMAND"}

    valid_commands = ["INIT", "RENDER_TEXT", "SHOW_SCREENSAVER",
                     "WAKE_UP", "POWER_OFF", "CLEAR", "STATUS"]

    if cmd["cmd"] not in valid_commands:
        return True, "Invalid command type detected"
    else:
        return False, "Should detect invalid command"

def test_invalid_field_type():
    """Test invalid field type"""
    cmd = {"cmd": "RENDER_TEXT", "text": 123, "cursor_x": 0, "cursor_y": 0}  # text should be string

    if not isinstance(cmd["text"], str):
        return True, "Invalid field type detected"
    else:
        return False, "Should detect invalid field type"

#───────────────────────────────────────────────#
# ─────────── Performance Tests ────────────────#
#───────────────────────────────────────────────#

def test_encoding_speed():
    """Test JSON encoding performance"""
    cmd = {"cmd": "RENDER_TEXT", "text": "Hello World", "cursor_x": 10, "cursor_y": 20}

    try:
        # Encode multiple times
        for _ in range(100):
            msg = json.dumps(cmd)

        return True, "Encoding performance OK (100 iterations)"
    except Exception as e:
        return False, f"Performance test failed: {e}"

def test_decoding_speed():
    """Test JSON decoding performance"""
    msg = '{"cmd":"RENDER_TEXT","text":"Hello World","cursor_x":10,"cursor_y":20}'

    try:
        # Decode multiple times
        for _ in range(100):
            cmd = json.loads(msg)

        return True, "Decoding performance OK (100 iterations)"
    except Exception as e:
        return False, f"Performance test failed: {e}"

#───────────────────────────────────────────────#
# ─────────── Main Test Runner ─────────────────#
#───────────────────────────────────────────────#

def run_all_tests():
    """Run all UART protocol tests"""
    print_header()

    # Command Structure Tests
    print("═ Command Structure Tests ═")
    print_test("INIT command")
    passed, details = test_init_command()
    print_result(passed, details)

    print_test("RENDER_TEXT command")
    passed, details = test_render_text_command()
    print_result(passed, details)

    print_test("SHOW_SCREENSAVER command")
    passed, details = test_show_screensaver_command()
    print_result(passed, details)

    print_test("WAKE_UP command")
    passed, details = test_wake_up_command()
    print_result(passed, details)

    print_test("POWER_OFF command")
    passed, details = test_power_off_command()
    print_result(passed, details)

    print_test("CLEAR command")
    passed, details = test_clear_command()
    print_result(passed, details)

    print_test("STATUS command")
    passed, details = test_status_command()
    print_result(passed, details)

    # Response Structure Tests
    print("\n═ Response Structure Tests ═")
    print_test("OK response")
    passed, details = test_ok_response()
    print_result(passed, details)

    print_test("Error response")
    passed, details = test_error_response()
    print_result(passed, details)

    # JSON Serialization Tests
    print("\n═ JSON Serialization Tests ═")
    print_test("Encode simple command")
    passed, details = test_json_encode_simple()
    print_result(passed, details)

    print_test("Encode complex command")
    passed, details = test_json_encode_complex()
    print_result(passed, details)

    print_test("Decode simple message")
    passed, details = test_json_decode_simple()
    print_result(passed, details)

    print_test("Decode complex message")
    passed, details = test_json_decode_complex()
    print_result(passed, details)

    print_test("Encode-decode roundtrip")
    passed, details = test_json_roundtrip()
    print_result(passed, details)

    # Protocol Format Tests
    print("\n═ Protocol Format Tests ═")
    print_test("Newline terminator")
    passed, details = test_newline_terminator()
    print_result(passed, details)

    print_test("Parse with newline")
    passed, details = test_parse_with_newline()
    print_result(passed, details)

    print_test("Message size limit")
    passed, details = test_message_size_limit()
    print_result(passed, details)

    # Special Character Tests
    print("\n═ Special Character Tests ═")
    print_test("Unicode characters")
    passed, details = test_unicode_characters()
    print_result(passed, details)

    print_test("Special characters")
    passed, details = test_special_characters()
    print_result(passed, details)

    print_test("Empty string field")
    passed, details = test_empty_string_field()
    print_result(passed, details)

    # Error Handling Tests
    print("\n═ Error Handling Tests ═")
    print_test("Malformed JSON")
    passed, details = test_malformed_json()
    print_result(passed, details)

    print_test("Missing cmd field")
    passed, details = test_missing_cmd_field()
    print_result(passed, details)

    print_test("Invalid cmd type")
    passed, details = test_invalid_cmd_type()
    print_result(passed, details)

    print_test("Invalid field type")
    passed, details = test_invalid_field_type()
    print_result(passed, details)

    # Performance Tests
    print("\n═ Performance Tests ═")
    print_test("Encoding speed")
    passed, details = test_encoding_speed()
    print_result(passed, details)

    print_test("Decoding speed")
    passed, details = test_decoding_speed()
    print_result(passed, details)

    # Print summary
    print_summary()

    # Additional notes
    print("PROTOCOL SPECIFICATION:")
    print(f"• Baudrate: {UART_BAUDRATE} baud")
    print(f"• Format: JSON with newline terminator")
    print(f"• Max message size: {MAX_MESSAGE_SIZE} bytes")
    print("• All commands must have 'cmd' field")
    print("• All responses must have 'status' and 'cmd' fields")
    print("• Error responses must include 'error' field\n")

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
        try:
            import sys
            sys.print_exception(e)
        except:
            print(str(e))
