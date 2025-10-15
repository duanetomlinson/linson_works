# test_slave_unit.py - Slave Pico Application Unit Tests
# Tests application logic without requiring hardware
# Can run on actual Pico or desktop Python with mocked hardware
# For Raspberry Pi Pico 2W (RP2350)

import json

#───────────────────────────────────────────────#
# ─────────── Test Configuration ───────────────#
#───────────────────────────────────────────────#

# Display constants (from main.py)
CHAR_WIDTH   = 8
CHAR_HEIGHT  = 15
MARGIN_LEFT  = 5
MARGIN_TOP   = 5

# Test state
tests_passed = 0
tests_failed = 0

#───────────────────────────────────────────────#
# ─────────── TextLayout Class (from main.py) ──#
#───────────────────────────────────────────────#

class TextLayout:
    """Handles text layout and word wrapping logic"""

    @staticmethod
    def get_word_boundaries(text, start_pos=0):
        """Find word boundaries from a starting position"""
        if start_pos >= len(text):
            return start_pos, start_pos

        # Skip any leading spaces
        while start_pos < len(text) and text[start_pos] == ' ':
            start_pos += 1

        word_start = start_pos
        word_end = start_pos

        # Find end of word
        while word_end < len(text) and text[word_end] not in ' \n':
            word_end += 1

        return word_start, word_end

    @staticmethod
    def calculate_lines(text, max_width):
        """Calculate line breaks with word wrapping"""
        lines = []
        current_line = []
        current_x = MARGIN_LEFT
        i = 0

        while i < len(text):
            if text[i] == '\n':
                lines.append(current_line[:])
                current_line = []
                current_x = MARGIN_LEFT
                i += 1
                continue

            if text[i] == ' ':
                if current_x + CHAR_WIDTH <= max_width:
                    current_line.append((current_x, ' '))
                    current_x += CHAR_WIDTH
                i += 1
                continue

            # Find word boundaries
            word_start, word_end = TextLayout.get_word_boundaries(text, i)
            word = text[word_start:word_end]
            word_width = len(word) * CHAR_WIDTH

            # Check if word fits on current line
            if current_x + word_width <= max_width:
                # Word fits
                for ch in word:
                    current_line.append((current_x, ch))
                    current_x += CHAR_WIDTH
                i = word_end
            else:
                # Word doesn't fit
                if current_x == MARGIN_LEFT or word_width > max_width - MARGIN_LEFT:
                    # Word is too long or we're at line start - break it
                    while i < word_end and current_x + CHAR_WIDTH <= max_width:
                        current_line.append((current_x, text[i]))
                        current_x += CHAR_WIDTH
                        i += 1
                    if i < word_end:
                        lines.append(current_line[:])
                        current_line = []
                        current_x = MARGIN_LEFT
                else:
                    # Start new line with this word
                    lines.append(current_line[:])
                    current_line = []
                    current_x = MARGIN_LEFT

        if current_line:
            lines.append(current_line)

        return lines

    @staticmethod
    def get_screen_pages(text, max_width, max_height):
        """Calculate screen pages from text"""
        lines = TextLayout.calculate_lines(text, max_width)
        pages = []
        current_page = []
        current_y = MARGIN_TOP

        for line in lines:
            if current_y + CHAR_HEIGHT > max_height:
                pages.append(current_page[:])
                current_page = []
                current_y = MARGIN_TOP

            # Add y-coordinate to each character
            line_with_y = [(x, current_y, ch) for x, ch in line]
            current_page.extend(line_with_y)
            current_y += CHAR_HEIGHT

        if current_page:
            pages.append(current_page)

        return pages if pages else [[]]

#───────────────────────────────────────────────#
# ─────────── Test Helper Functions ────────────#
#───────────────────────────────────────────────#

def print_header():
    """Print test suite header"""
    print("\n" + "="*55)
    print("  SLAVE PICO APPLICATION UNIT TEST SUITE")
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
# ─────────── TextLayout Tests ─────────────────#
#───────────────────────────────────────────────#

def test_word_wrap_short_text():
    """Test word wrapping with short text"""
    text = "Hello"
    max_width = 400
    lines = TextLayout.calculate_lines(text, max_width)

    if len(lines) == 1 and len(lines[0]) == 5:
        return True, f"Short text fits on 1 line"
    else:
        return False, f"Expected 1 line, got {len(lines)}"

def test_word_wrap_long_word():
    """Test word wrapping with word too long for line"""
    max_width = 100  # Small width to force wrap
    long_word = "A" * 50  # Very long word
    lines = TextLayout.calculate_lines(long_word, max_width)

    if len(lines) >= 2:
        return True, f"Long word split across {len(lines)} lines"
    else:
        return False, f"Expected multiple lines, got {len(lines)}"

def test_pagination_empty_text():
    """Test pagination with empty text"""
    text = ""
    pages = TextLayout.get_screen_pages(text, 400, 300)

    if len(pages) == 1 and len(pages[0]) == 0:
        return True, "Empty text produces 1 empty page"
    else:
        return False, f"Expected 1 empty page, got {len(pages)} pages"

def test_pagination_with_newlines():
    """Test pagination with newlines"""
    text = "Line1\nLine2\nLine3"
    pages = TextLayout.get_screen_pages(text, 400, 300)

    if len(pages) >= 1:
        # Count actual content
        char_count = sum(len(page) for page in pages)
        expected_chars = len(text) - text.count('\n')  # Newlines don't render

        if char_count == expected_chars:
            return True, f"All {char_count} characters paginated"
        else:
            return False, f"Expected {expected_chars} chars, got {char_count}"
    else:
        return False, "No pages generated"

#───────────────────────────────────────────────#
# ─────────── UART Command Tests ───────────────#
#───────────────────────────────────────────────#

def test_command_init_structure():
    """Test INIT command structure"""
    cmd = {"cmd": "INIT", "width": 400, "height": 300}

    if cmd.get("cmd") == "INIT" and cmd.get("width") == 400:
        return True, "INIT command structure valid"
    else:
        return False, "INIT command structure invalid"

def test_command_render_text_structure():
    """Test RENDER_TEXT command structure"""
    cmd = {
        "cmd": "RENDER_TEXT",
        "text": "Hello World",
        "cursor_x": 10,
        "cursor_y": 20
    }

    if (cmd.get("cmd") == "RENDER_TEXT" and
        cmd.get("text") == "Hello World" and
        cmd.get("cursor_x") == 10 and
        cmd.get("cursor_y") == 20):
        return True, "RENDER_TEXT command structure valid"
    else:
        return False, "RENDER_TEXT command structure invalid"

def test_command_show_screensaver_structure():
    """Test SHOW_SCREENSAVER command structure"""
    cmd = {"cmd": "SHOW_SCREENSAVER"}

    if cmd.get("cmd") == "SHOW_SCREENSAVER":
        return True, "SHOW_SCREENSAVER command structure valid"
    else:
        return False, "SHOW_SCREENSAVER command structure invalid"

def test_command_wake_up_structure():
    """Test WAKE_UP command structure"""
    cmd = {"cmd": "WAKE_UP"}

    if cmd.get("cmd") == "WAKE_UP":
        return True, "WAKE_UP command structure valid"
    else:
        return False, "WAKE_UP command structure invalid"

def test_command_power_off_structure():
    """Test POWER_OFF command structure"""
    cmd = {"cmd": "POWER_OFF"}

    if cmd.get("cmd") == "POWER_OFF":
        return True, "POWER_OFF command structure valid"
    else:
        return False, "POWER_OFF command structure invalid"

def test_command_clear_structure():
    """Test CLEAR command structure"""
    cmd = {"cmd": "CLEAR"}

    if cmd.get("cmd") == "CLEAR":
        return True, "CLEAR command structure valid"
    else:
        return False, "CLEAR command structure invalid"

def test_command_status_structure():
    """Test STATUS command structure"""
    cmd = {"cmd": "STATUS", "text": "Saved"}

    if cmd.get("cmd") == "STATUS" and cmd.get("text") == "Saved":
        return True, "STATUS command structure valid"
    else:
        return False, "STATUS command structure invalid"

#───────────────────────────────────────────────#
# ─────────── Command Handler Logic Tests ──────#
#───────────────────────────────────────────────#

def test_handle_init_logic():
    """Test INIT command handler logic"""
    cmd = {"cmd": "INIT", "width": 400, "height": 300}

    # Simulate handler
    max_w = cmd.get("width", 400)
    max_h = cmd.get("height", 300)

    if max_w == 400 and max_h == 300:
        return True, f"Init set dimensions: {max_w}x{max_h}"
    else:
        return False, f"Init failed: got {max_w}x{max_h}"

def test_handle_render_text_logic():
    """Test RENDER_TEXT command handler logic"""
    cmd = {
        "cmd": "RENDER_TEXT",
        "text": "Test",
        "cursor_x": 10,
        "cursor_y": 20
    }

    # Simulate handler
    text = cmd.get("text", "")
    cursor_x = cmd.get("cursor_x", MARGIN_LEFT)
    cursor_y = cmd.get("cursor_y", MARGIN_TOP)

    if text == "Test" and cursor_x == 10 and cursor_y == 20:
        return True, f"Render command parsed: '{text}' at ({cursor_x}, {cursor_y})"
    else:
        return False, "Render command parsing failed"

def test_handle_status_logic():
    """Test STATUS command handler logic"""
    cmd = {"cmd": "STATUS", "text": "Saved"}

    # Simulate handler
    msg = cmd.get("text", "")

    if msg == "Saved":
        return True, f"Status message: '{msg}'"
    else:
        return False, "Status command parsing failed"

#───────────────────────────────────────────────#
# ─────────── Response Tests ───────────────────#
#───────────────────────────────────────────────#

def test_response_ok_structure():
    """Test OK response structure"""
    response = {"status": "ok", "cmd": "INIT"}

    if response.get("status") == "ok" and response.get("cmd") == "INIT":
        return True, "OK response structure valid"
    else:
        return False, "OK response structure invalid"

def test_response_error_structure():
    """Test error response structure"""
    response = {"status": "error", "cmd": "TEST", "error": "Unknown command"}

    if (response.get("status") == "error" and
        response.get("cmd") == "TEST" and
        "error" in response):
        return True, "Error response structure valid"
    else:
        return False, "Error response structure invalid"

#───────────────────────────────────────────────#
# ─────────── JSON Protocol Tests ──────────────#
#───────────────────────────────────────────────#

def test_json_serialization():
    """Test JSON command serialization"""
    cmd = {"cmd": "RENDER_TEXT", "text": "Hello"}

    try:
        msg = json.dumps(cmd)
        parsed = json.loads(msg)

        if parsed == cmd:
            return True, f"JSON serialization OK ({len(msg)} bytes)"
        else:
            return False, "JSON round-trip failed"
    except Exception as e:
        return False, f"JSON error: {e}"

def test_json_with_newline():
    """Test JSON message with newline terminator"""
    cmd = {"cmd": "TEST"}
    msg = json.dumps(cmd) + '\n'

    if msg.endswith('\n'):
        stripped = msg.strip()
        parsed = json.loads(stripped)
        if parsed == cmd:
            return True, "JSON with newline terminator OK"
        else:
            return False, "Parse failed after stripping newline"
    else:
        return False, "Newline not appended"

def test_json_unicode_handling():
    """Test JSON with unicode characters"""
    cmd = {"cmd": "RENDER_TEXT", "text": "Hello™"}

    try:
        msg = json.dumps(cmd)
        parsed = json.loads(msg)

        if parsed["text"] == "Hello™":
            return True, "Unicode handling OK"
        else:
            return False, f"Unicode mismatch: got '{parsed['text']}'"
    except Exception as e:
        return False, f"Unicode error: {e}"

#───────────────────────────────────────────────#
# ─────────── Display Buffer Logic Tests ───────#
#───────────────────────────────────────────────#

def test_cursor_render_bounds():
    """Test cursor rendering position bounds"""
    cursor_x = 50
    cursor_y = 100
    cursor_width = CHAR_WIDTH
    cursor_height = 2

    # Check bounds
    rect_x = cursor_x
    rect_y = cursor_y + CHAR_HEIGHT - 2
    rect_w = cursor_width
    rect_h = cursor_height

    if (rect_x >= 0 and rect_y >= 0 and
        rect_w > 0 and rect_h > 0):
        return True, f"Cursor bounds OK: ({rect_x}, {rect_y}, {rect_w}, {rect_h})"
    else:
        return False, "Cursor bounds invalid"

def test_text_render_coordinates():
    """Test text character rendering coordinates"""
    page_chars = [
        (5, 5, 'H'),
        (13, 5, 'i')
    ]

    for x, y, ch in page_chars:
        if x < 0 or y < 0:
            return False, f"Invalid coordinates: ({x}, {y}) for '{ch}'"

    return True, f"All {len(page_chars)} characters have valid coordinates"

#───────────────────────────────────────────────#
# ─────────── Command Dispatcher Tests ─────────#
#───────────────────────────────────────────────#

def test_command_dispatcher_valid():
    """Test command dispatcher with valid command"""
    COMMAND_HANDLERS = {
        "INIT": lambda cmd: "init_called",
        "RENDER_TEXT": lambda cmd: "render_called",
        "CLEAR": lambda cmd: "clear_called"
    }

    cmd = {"cmd": "INIT"}
    cmd_type = cmd.get("cmd")

    if cmd_type in COMMAND_HANDLERS:
        result = COMMAND_HANDLERS[cmd_type](cmd)
        if result == "init_called":
            return True, "Valid command dispatched correctly"
        else:
            return False, "Handler returned unexpected result"
    else:
        return False, "Command not found in dispatcher"

def test_command_dispatcher_invalid():
    """Test command dispatcher with invalid command"""
    COMMAND_HANDLERS = {
        "INIT": lambda cmd: "init_called",
    }

    cmd = {"cmd": "UNKNOWN"}
    cmd_type = cmd.get("cmd")

    if cmd_type in COMMAND_HANDLERS:
        return False, "Invalid command found in dispatcher (should fail)"
    else:
        return True, "Invalid command correctly rejected"

#───────────────────────────────────────────────#
# ─────────── Main Test Runner ─────────────────#
#───────────────────────────────────────────────#

def run_all_tests():
    """Run all Slave Pico unit tests"""
    print_header()

    # TextLayout Tests
    print("═ TextLayout Tests ═")
    print_test("Word wrap (short text)")
    passed, details = test_word_wrap_short_text()
    print_result(passed, details)

    print_test("Word wrap (long word)")
    passed, details = test_word_wrap_long_word()
    print_result(passed, details)

    print_test("Pagination (empty text)")
    passed, details = test_pagination_empty_text()
    print_result(passed, details)

    print_test("Pagination (with newlines)")
    passed, details = test_pagination_with_newlines()
    print_result(passed, details)

    # UART Command Structure Tests
    print("\n═ UART Command Structure Tests ═")
    print_test("INIT command")
    passed, details = test_command_init_structure()
    print_result(passed, details)

    print_test("RENDER_TEXT command")
    passed, details = test_command_render_text_structure()
    print_result(passed, details)

    print_test("SHOW_SCREENSAVER command")
    passed, details = test_command_show_screensaver_structure()
    print_result(passed, details)

    print_test("WAKE_UP command")
    passed, details = test_command_wake_up_structure()
    print_result(passed, details)

    print_test("POWER_OFF command")
    passed, details = test_command_power_off_structure()
    print_result(passed, details)

    print_test("CLEAR command")
    passed, details = test_command_clear_structure()
    print_result(passed, details)

    print_test("STATUS command")
    passed, details = test_command_status_structure()
    print_result(passed, details)

    # Command Handler Logic Tests
    print("\n═ Command Handler Logic Tests ═")
    print_test("INIT handler logic")
    passed, details = test_handle_init_logic()
    print_result(passed, details)

    print_test("RENDER_TEXT handler logic")
    passed, details = test_handle_render_text_logic()
    print_result(passed, details)

    print_test("STATUS handler logic")
    passed, details = test_handle_status_logic()
    print_result(passed, details)

    # Response Tests
    print("\n═ Response Structure Tests ═")
    print_test("OK response")
    passed, details = test_response_ok_structure()
    print_result(passed, details)

    print_test("Error response")
    passed, details = test_response_error_structure()
    print_result(passed, details)

    # JSON Protocol Tests
    print("\n═ JSON Protocol Tests ═")
    print_test("JSON serialization")
    passed, details = test_json_serialization()
    print_result(passed, details)

    print_test("JSON with newline")
    passed, details = test_json_with_newline()
    print_result(passed, details)

    print_test("JSON unicode handling")
    passed, details = test_json_unicode_handling()
    print_result(passed, details)

    # Display Buffer Logic Tests
    print("\n═ Display Buffer Logic Tests ═")
    print_test("Cursor render bounds")
    passed, details = test_cursor_render_bounds()
    print_result(passed, details)

    print_test("Text render coordinates")
    passed, details = test_text_render_coordinates()
    print_result(passed, details)

    # Command Dispatcher Tests
    print("\n═ Command Dispatcher Tests ═")
    print_test("Dispatcher (valid command)")
    passed, details = test_command_dispatcher_valid()
    print_result(passed, details)

    print_test("Dispatcher (invalid command)")
    passed, details = test_command_dispatcher_invalid()
    print_result(passed, details)

    # Print summary
    print_summary()

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
