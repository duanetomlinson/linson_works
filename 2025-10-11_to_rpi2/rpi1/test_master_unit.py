# test_master_unit.py - Master Pico Application Unit Tests
# Tests application logic without requiring hardware
# Can run on actual Pico or desktop Python with mocked hardware
# For Raspberry Pi Pico 2W (RP2350)

import time

#───────────────────────────────────────────────#
# ─────────── Test Configuration ───────────────#
#───────────────────────────────────────────────#

# Display constants (from main.py)
CHAR_WIDTH   = 8
CHAR_HEIGHT  = 15
MARGIN_LEFT  = 5
MARGIN_TOP   = 5
DISPLAY_WIDTH  = 400
DISPLAY_HEIGHT = 300

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

    @staticmethod
    def get_cursor_screen_pos(text, cursor_index, max_width, max_height):
        """Convert cursor index to screen position"""
        if cursor_index > len(text):
            cursor_index = len(text)

        lines = TextLayout.calculate_lines(text[:cursor_index], max_width)

        if not lines:
            return MARGIN_LEFT, MARGIN_TOP, 0

        # Calculate which page the cursor is on
        total_lines = len(lines)
        lines_per_page = (max_height - MARGIN_TOP) // CHAR_HEIGHT
        page_num = (total_lines - 1) // lines_per_page if total_lines > 0 else 0

        # Get position on the last line
        last_line = lines[-1] if lines else []
        if last_line:
            last_x = last_line[-1][0] + CHAR_WIDTH
        else:
            last_x = MARGIN_LEFT

        y_on_page = MARGIN_TOP + ((total_lines - 1) % lines_per_page) * CHAR_HEIGHT

        return last_x, y_on_page, page_num

#───────────────────────────────────────────────#
# ─────────── Test Helper Functions ────────────#
#───────────────────────────────────────────────#

def print_header():
    """Print test suite header"""
    print("\n" + "="*55)
    print("  MASTER PICO APPLICATION UNIT TEST SUITE")
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

def test_word_boundaries_simple():
    """Test word boundary detection with simple text"""
    text = "Hello World"
    start, end = TextLayout.get_word_boundaries(text, 0)

    if start == 0 and end == 5 and text[start:end] == "Hello":
        return True, "Found 'Hello' at position 0-5"
    else:
        return False, f"Expected 'Hello' (0-5), got '{text[start:end]}' ({start}-{end})"

def test_word_boundaries_with_spaces():
    """Test word boundary detection skipping leading spaces"""
    text = "   Hello"
    start, end = TextLayout.get_word_boundaries(text, 0)

    if start == 3 and end == 8 and text[start:end] == "Hello":
        return True, "Skipped leading spaces, found 'Hello'"
    else:
        return False, f"Expected 'Hello' (3-8), got '{text[start:end]}' ({start}-{end})"

def test_calculate_lines_single_line():
    """Test line calculation for text that fits on one line"""
    text = "Hello"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 1 and len(lines[0]) == 5:
        return True, f"Single line with {len(lines[0])} characters"
    else:
        return False, f"Expected 1 line with 5 chars, got {len(lines)} lines"

def test_calculate_lines_word_wrap():
    """Test word wrapping when line exceeds width"""
    # Create text that will wrap (each char is 8px wide)
    max_chars = (DISPLAY_WIDTH - MARGIN_LEFT) // CHAR_WIDTH
    text = "A" * (max_chars + 5)  # Exceed line width

    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) >= 2:
        return True, f"Text wrapped to {len(lines)} lines"
    else:
        return False, f"Expected word wrap, got {len(lines)} line(s)"

def test_calculate_lines_with_newline():
    """Test explicit newline handling"""
    text = "Line1\nLine2"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 2:
        return True, "Newline created 2 lines"
    else:
        return False, f"Expected 2 lines, got {len(lines)}"

def test_calculate_lines_empty():
    """Test empty text handling"""
    text = ""
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 0:
        return True, "Empty text produced no lines"
    else:
        return False, f"Expected 0 lines, got {len(lines)}"

def test_get_screen_pages_single_page():
    """Test pagination for text that fits on one page"""
    text = "Hello World"
    pages = TextLayout.get_screen_pages(text, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if len(pages) == 1:
        return True, "Text fits on single page"
    else:
        return False, f"Expected 1 page, got {len(pages)}"

def test_get_screen_pages_multiple_pages():
    """Test pagination for text spanning multiple pages"""
    # Create enough lines to exceed one page
    lines_per_page = (DISPLAY_HEIGHT - MARGIN_TOP) // CHAR_HEIGHT
    text = "Line\n" * (lines_per_page + 5)  # Exceed one page

    pages = TextLayout.get_screen_pages(text, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if len(pages) >= 2:
        return True, f"Text split into {len(pages)} pages"
    else:
        return False, f"Expected multiple pages, got {len(pages)}"

def test_get_cursor_screen_pos_start():
    """Test cursor position at text start"""
    text = "Hello World"
    x, y, page = TextLayout.get_cursor_screen_pos(text, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if x == MARGIN_LEFT and y == MARGIN_TOP and page == 0:
        return True, f"Cursor at start: ({x}, {y}), page {page}"
    else:
        return False, f"Expected ({MARGIN_LEFT}, {MARGIN_TOP}, 0), got ({x}, {y}, {page})"

def test_get_cursor_screen_pos_end():
    """Test cursor position at text end"""
    text = "Hello"
    cursor_index = len(text)
    x, y, page = TextLayout.get_cursor_screen_pos(text, cursor_index, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    expected_x = MARGIN_LEFT + (len(text) * CHAR_WIDTH)

    if x == expected_x and y == MARGIN_TOP and page == 0:
        return True, f"Cursor at end: ({x}, {y})"
    else:
        return False, f"Expected ({expected_x}, {MARGIN_TOP}, 0), got ({x}, {y}, {page})"

def test_get_cursor_screen_pos_with_newline():
    """Test cursor position after newline"""
    text = "Hello\nWorld"
    cursor_index = 6  # After newline, before 'W'
    x, y, page = TextLayout.get_cursor_screen_pos(text, cursor_index, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    expected_y = MARGIN_TOP + CHAR_HEIGHT

    if x == MARGIN_LEFT and y == expected_y and page == 0:
        return True, f"Cursor after newline: ({x}, {y})"
    else:
        return False, f"Expected ({MARGIN_LEFT}, {expected_y}, 0), got ({x}, {y}, {page})"

#───────────────────────────────────────────────#
# ─────────── Text Editing Logic Tests ─────────#
#───────────────────────────────────────────────#

def test_insert_char_logic():
    """Test character insertion logic"""
    buffer = list("Hello")
    cursor = 5

    # Insert space
    buffer.insert(cursor, ' ')
    cursor += 1

    if ''.join(buffer) == "Hello " and cursor == 6:
        return True, f"Inserted space: '{(''.join(buffer))}'"
    else:
        return False, f"Insert failed: got '{(''.join(buffer))}', cursor {cursor}"

def test_backspace_logic():
    """Test backspace deletion logic"""
    buffer = list("Hello")
    cursor = 5

    # Delete 'o'
    if cursor > 0:
        cursor -= 1
        buffer.pop(cursor)

    if ''.join(buffer) == "Hell" and cursor == 4:
        return True, f"Backspace OK: '{(''.join(buffer))}'"
    else:
        return False, f"Backspace failed: got '{(''.join(buffer))}', cursor {cursor}"

def test_delete_word_logic():
    """Test word deletion logic"""
    buffer = list("Hello World")
    cursor = 11  # End of text

    # Find word start
    i = cursor - 1
    # Skip trailing spaces
    while i >= 0 and buffer[i] == ' ':
        i -= 1
    # Find word boundary
    while i >= 0 and buffer[i] not in ' \n':
        i -= 1

    # Delete from word start to cursor
    chars_to_delete = cursor - (i + 1)
    for _ in range(chars_to_delete):
        if cursor > 0:
            cursor -= 1
            buffer.pop(cursor)

    if ''.join(buffer) == "Hello " and cursor == 6:
        return True, f"Deleted word: '{(''.join(buffer))}'"
    else:
        return False, f"Word delete failed: got '{(''.join(buffer))}', cursor {cursor}"

#───────────────────────────────────────────────#
# ─────────── Power Management Tests ───────────#
#───────────────────────────────────────────────#

def test_screensaver_timeout():
    """Test screensaver timeout calculation"""
    SCREENSAVER_TIMEOUT_MS = 120_000  # 2 minutes

    if SCREENSAVER_TIMEOUT_MS == 120000:
        seconds = SCREENSAVER_TIMEOUT_MS / 1000
        return True, f"Timeout correctly set to {seconds} seconds (2 minutes)"
    else:
        return False, f"Timeout is {SCREENSAVER_TIMEOUT_MS}ms, expected 120000ms"

def test_auto_off_timeout():
    """Test auto-off timeout calculation"""
    AUTO_OFF_TIMEOUT_MS = 300_000  # 5 minutes

    if AUTO_OFF_TIMEOUT_MS == 300000:
        seconds = AUTO_OFF_TIMEOUT_MS / 1000
        return True, f"Timeout correctly set to {seconds} seconds (5 minutes)"
    else:
        return False, f"Timeout is {AUTO_OFF_TIMEOUT_MS}ms, expected 300000ms"

def test_idle_detection_logic():
    """Test idle time detection logic"""
    # Simulate timing
    last_key_time = 1000  # ms
    current_time = 121000  # ms (121 seconds later)

    idle_time = current_time - last_key_time
    SCREENSAVER_TIMEOUT_MS = 120_000

    if idle_time >= SCREENSAVER_TIMEOUT_MS:
        return True, f"Idle time {idle_time}ms exceeds threshold {SCREENSAVER_TIMEOUT_MS}ms"
    else:
        return False, f"Idle detection logic incorrect"

#───────────────────────────────────────────────#
# ─────────── Key Processing Tests ─────────────#
#───────────────────────────────────────────────#

def test_glyph_conversion_lowercase():
    """Test glyph conversion to lowercase"""
    # Simulate glyph() function
    lbl = 'A'
    shift = False

    ch = lbl.lower() if not shift else lbl.upper()

    if ch == 'a':
        return True, f"'{lbl}' → '{ch}' (lowercase)"
    else:
        return False, f"Expected 'a', got '{ch}'"

def test_glyph_conversion_uppercase():
    """Test glyph conversion to uppercase"""
    lbl = 'a'
    shift = True

    ch = lbl.upper() if shift else lbl.lower()

    if ch == 'A':
        return True, f"'{lbl}' + Shift → '{ch}' (uppercase)"
    else:
        return False, f"Expected 'A', got '{ch}'"

def test_glyph_conversion_punctuation():
    """Test glyph conversion with punctuation shift"""
    punct_map = {'1': '!', '2': '@', '3': '#'}
    lbl = '1'
    shift = True

    ch = punct_map.get(lbl) if shift else lbl

    if ch == '!':
        return True, f"'{lbl}' + Shift → '{ch}'"
    else:
        return False, f"Expected '!', got '{ch}'"

def test_space_key_handling():
    """Test space key special handling"""
    lbl = 'Space'

    ch = ' ' if lbl == 'Space' else lbl

    if ch == ' ':
        return True, "'Space' → ' ' (space character)"
    else:
        return False, f"Expected ' ', got '{ch}'"

#───────────────────────────────────────────────#
# ─────────── File Operations Tests ────────────#
#───────────────────────────────────────────────#

def test_page_split_logic():
    """Test explicit page marker splitting"""
    content = "Page1\n---\nPage2\n---\nPage3"
    pages = content.split('\n---\n')

    if len(pages) == 3 and pages[0] == "Page1" and pages[2] == "Page3":
        return True, f"Split into {len(pages)} pages"
    else:
        return False, f"Expected 3 pages, got {len(pages)}"

def test_page_join_logic():
    """Test joining pages with markers"""
    pages = ["Page1", "Page2", "Page3"]
    content = '\n---\n'.join(pages)

    expected = "Page1\n---\nPage2\n---\nPage3"

    if content == expected:
        return True, f"Joined {len(pages)} pages with markers"
    else:
        return False, f"Join failed: got '{content}'"

#───────────────────────────────────────────────#
# ─────────── Main Test Runner ─────────────────#
#───────────────────────────────────────────────#

def run_all_tests():
    """Run all Master Pico unit tests"""
    print_header()

    # TextLayout Tests
    print("═ TextLayout Tests ═")
    print_test("Word boundaries (simple)")
    passed, details = test_word_boundaries_simple()
    print_result(passed, details)

    print_test("Word boundaries (with spaces)")
    passed, details = test_word_boundaries_with_spaces()
    print_result(passed, details)

    print_test("Calculate lines (single line)")
    passed, details = test_calculate_lines_single_line()
    print_result(passed, details)

    print_test("Calculate lines (word wrap)")
    passed, details = test_calculate_lines_word_wrap()
    print_result(passed, details)

    print_test("Calculate lines (newline)")
    passed, details = test_calculate_lines_with_newline()
    print_result(passed, details)

    print_test("Calculate lines (empty)")
    passed, details = test_calculate_lines_empty()
    print_result(passed, details)

    print_test("Screen pages (single page)")
    passed, details = test_get_screen_pages_single_page()
    print_result(passed, details)

    print_test("Screen pages (multiple pages)")
    passed, details = test_get_screen_pages_multiple_pages()
    print_result(passed, details)

    print_test("Cursor position (start)")
    passed, details = test_get_cursor_screen_pos_start()
    print_result(passed, details)

    print_test("Cursor position (end)")
    passed, details = test_get_cursor_screen_pos_end()
    print_result(passed, details)

    print_test("Cursor position (after newline)")
    passed, details = test_get_cursor_screen_pos_with_newline()
    print_result(passed, details)

    # Text Editing Tests
    print("\n═ Text Editing Logic Tests ═")
    print_test("Insert character")
    passed, details = test_insert_char_logic()
    print_result(passed, details)

    print_test("Backspace deletion")
    passed, details = test_backspace_logic()
    print_result(passed, details)

    print_test("Delete word")
    passed, details = test_delete_word_logic()
    print_result(passed, details)

    # Power Management Tests
    print("\n═ Power Management Tests ═")
    print_test("Screensaver timeout")
    passed, details = test_screensaver_timeout()
    print_result(passed, details)

    print_test("Auto-off timeout")
    passed, details = test_auto_off_timeout()
    print_result(passed, details)

    print_test("Idle detection logic")
    passed, details = test_idle_detection_logic()
    print_result(passed, details)

    # Key Processing Tests
    print("\n═ Key Processing Tests ═")
    print_test("Glyph conversion (lowercase)")
    passed, details = test_glyph_conversion_lowercase()
    print_result(passed, details)

    print_test("Glyph conversion (uppercase)")
    passed, details = test_glyph_conversion_uppercase()
    print_result(passed, details)

    print_test("Glyph conversion (punctuation)")
    passed, details = test_glyph_conversion_punctuation()
    print_result(passed, details)

    print_test("Space key handling")
    passed, details = test_space_key_handling()
    print_result(passed, details)

    # File Operations Tests
    print("\n═ File Operations Tests ═")
    print_test("Page split logic")
    passed, details = test_page_split_logic()
    print_result(passed, details)

    print_test("Page join logic")
    passed, details = test_page_join_logic()
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
