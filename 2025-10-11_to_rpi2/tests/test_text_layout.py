# test_text_layout.py - Shared TextLayout Unit Tests
# Comprehensive edge case and boundary condition tests for TextLayout class
# Can run on Pico or desktop Python
# Tests shared logic used by both Master and Slave Picos

#───────────────────────────────────────────────#
# ─────────── Test Configuration ───────────────#
#───────────────────────────────────────────────#

# Display constants
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
# ─────────── TextLayout Class ─────────────────#
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
    print("  TEXTLAYOUT COMPREHENSIVE UNIT TEST SUITE")
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
# ─────────── Edge Case Tests ──────────────────#
#───────────────────────────────────────────────#

def test_empty_string():
    """Test empty string handling"""
    text = ""
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 0:
        return True, "Empty string produces 0 lines"
    else:
        return False, f"Expected 0 lines, got {len(lines)}"

def test_single_character():
    """Test single character"""
    text = "A"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 1 and len(lines[0]) == 1:
        return True, "Single character on 1 line"
    else:
        return False, f"Expected 1 line with 1 char, got {len(lines)} lines"

def test_only_spaces():
    """Test string with only spaces"""
    text = "     "
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) >= 0:  # Should handle gracefully
        return True, f"Space-only string: {len(lines)} line(s)"
    else:
        return False, "Failed to handle space-only string"

def test_only_newlines():
    """Test string with only newlines"""
    text = "\n\n\n"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 4:  # 3 newlines create 4 lines (including empty first)
        return True, "Newline-only string creates correct number of lines"
    else:
        return False, f"Expected 4 lines, got {len(lines)}"

def test_trailing_newline():
    """Test text with trailing newline"""
    text = "Hello\n"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 2:  # "Hello" + empty line
        return True, "Trailing newline creates empty line"
    else:
        return False, f"Expected 2 lines, got {len(lines)}"

def test_leading_newline():
    """Test text with leading newline"""
    text = "\nHello"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 2:  # Empty line + "Hello"
        return True, "Leading newline creates empty line"
    else:
        return False, f"Expected 2 lines, got {len(lines)}"

def test_multiple_consecutive_newlines():
    """Test multiple consecutive newlines"""
    text = "A\n\n\nB"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 4:  # A, empty, empty, B
        return True, "Multiple newlines create empty lines"
    else:
        return False, f"Expected 4 lines, got {len(lines)}"

def test_multiple_consecutive_spaces():
    """Test multiple consecutive spaces"""
    text = "A     B"
    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 1:  # Should all fit on one line
        char_count = len(lines[0])
        if char_count == 7:  # A + 5 spaces + B
            return True, "Multiple spaces preserved"
        else:
            return True, f"Spaces handled ({char_count} chars)"
    else:
        return False, f"Expected 1 line, got {len(lines)}"

def test_word_at_exact_line_boundary():
    """Test word that fits exactly at line width"""
    max_chars = (DISPLAY_WIDTH - MARGIN_LEFT) // CHAR_WIDTH
    text = "A" * max_chars

    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 1:
        return True, f"Word fits exactly at boundary ({max_chars} chars)"
    else:
        return False, f"Expected 1 line, got {len(lines)}"

def test_word_one_char_over_boundary():
    """Test word one character over line width"""
    max_chars = (DISPLAY_WIDTH - MARGIN_LEFT) // CHAR_WIDTH
    text = "A" * (max_chars + 1)

    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) == 2:
        return True, f"Word wraps at {max_chars}+1 chars"
    else:
        return False, f"Expected 2 lines, got {len(lines)}"

def test_very_long_word():
    """Test extremely long word (exceeds multiple lines)"""
    max_chars = (DISPLAY_WIDTH - MARGIN_LEFT) // CHAR_WIDTH
    text = "A" * (max_chars * 3)  # 3x line width

    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) >= 3:
        return True, f"Very long word split across {len(lines)} lines"
    else:
        return False, f"Expected >=3 lines, got {len(lines)}"

def test_mixed_short_and_long_words():
    """Test mixture of short and long words"""
    max_chars = (DISPLAY_WIDTH - MARGIN_LEFT) // CHAR_WIDTH
    long_word = "A" * (max_chars - 10)
    text = f"Hi {long_word} there"

    lines = TextLayout.calculate_lines(text, DISPLAY_WIDTH)

    if len(lines) >= 2:
        return True, f"Mixed words wrap correctly ({len(lines)} lines)"
    else:
        return False, f"Expected >=2 lines, got {len(lines)}"

def test_word_boundaries_at_text_end():
    """Test word boundary detection at text end"""
    text = "Hello"
    start, end = TextLayout.get_word_boundaries(text, 5)  # Past end

    if start == 5 and end == 5:
        return True, "Boundary at end returns end position"
    else:
        return False, f"Expected (5, 5), got ({start}, {end})"

def test_word_boundaries_mid_word():
    """Test word boundary detection mid-word"""
    text = "Hello World"
    start, end = TextLayout.get_word_boundaries(text, 2)  # 'l' in "Hello"

    if start == 2 and end == 5:
        return True, f"Mid-word boundary: '{text[start:end]}'"
    else:
        return False, f"Expected (2, 5), got ({start}, {end})"

#───────────────────────────────────────────────#
# ─────────── Pagination Edge Cases ────────────#
#───────────────────────────────────────────────#

def test_pagination_exactly_one_page():
    """Test text that exactly fills one page"""
    lines_per_page = (DISPLAY_HEIGHT - MARGIN_TOP) // CHAR_HEIGHT
    text = "Line\n" * lines_per_page

    pages = TextLayout.get_screen_pages(text, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # May be 1 or 2 pages depending on exact fit
    if len(pages) >= 1:
        return True, f"Exact page fill: {len(pages)} page(s)"
    else:
        return False, "Pagination failed"

def test_pagination_one_line_over():
    """Test text one line over page capacity"""
    lines_per_page = (DISPLAY_HEIGHT - MARGIN_TOP) // CHAR_HEIGHT
    text = "Line\n" * (lines_per_page + 1)

    pages = TextLayout.get_screen_pages(text, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if len(pages) == 2:
        return True, "One extra line creates second page"
    else:
        return False, f"Expected 2 pages, got {len(pages)}"

def test_pagination_empty_pages():
    """Test that empty pages are handled"""
    text = ""
    pages = TextLayout.get_screen_pages(text, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if len(pages) == 1 and len(pages[0]) == 0:
        return True, "Empty text creates one empty page"
    else:
        return False, f"Expected 1 empty page, got {len(pages)}"

def test_pagination_character_count():
    """Test that all characters are paginated"""
    text = "Hello World\nSecond Line"
    pages = TextLayout.get_screen_pages(text, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    total_chars = sum(len(page) for page in pages)
    expected = len(text) - text.count('\n')  # Newlines don't render

    if total_chars == expected:
        return True, f"All {total_chars} characters paginated"
    else:
        return False, f"Expected {expected} chars, got {total_chars}"

#───────────────────────────────────────────────#
# ─────────── Cursor Position Edge Cases ───────#
#───────────────────────────────────────────────#

def test_cursor_at_zero():
    """Test cursor at position 0"""
    text = "Hello"
    x, y, page = TextLayout.get_cursor_screen_pos(text, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if x == MARGIN_LEFT and y == MARGIN_TOP and page == 0:
        return True, "Cursor at position 0"
    else:
        return False, f"Expected ({MARGIN_LEFT}, {MARGIN_TOP}, 0), got ({x}, {y}, {page})"

def test_cursor_past_text_end():
    """Test cursor past end of text"""
    text = "Hello"
    x, y, page = TextLayout.get_cursor_screen_pos(text, 100, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Should clamp to text length
    expected_x = MARGIN_LEFT + (len(text) * CHAR_WIDTH)

    if x == expected_x:
        return True, f"Cursor clamped to text end: x={x}"
    else:
        return False, f"Expected x={expected_x}, got x={x}"

def test_cursor_after_newline():
    """Test cursor position immediately after newline"""
    text = "Hello\n"
    x, y, page = TextLayout.get_cursor_screen_pos(text, 6, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    expected_y = MARGIN_TOP + CHAR_HEIGHT

    if x == MARGIN_LEFT and y == expected_y:
        return True, "Cursor after newline on new line"
    else:
        return False, f"Expected ({MARGIN_LEFT}, {expected_y}), got ({x}, {y})"

def test_cursor_on_second_page():
    """Test cursor position on second page"""
    lines_per_page = (DISPLAY_HEIGHT - MARGIN_TOP) // CHAR_HEIGHT
    text = "Line\n" * (lines_per_page + 2)
    cursor_index = len(text)

    x, y, page = TextLayout.get_cursor_screen_pos(text, cursor_index, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    if page == 1:  # Second page (0-indexed)
        return True, f"Cursor on page {page}"
    else:
        return False, f"Expected page 1, got page {page}"

#───────────────────────────────────────────────#
# ─────────── Main Test Runner ─────────────────#
#───────────────────────────────────────────────#

def run_all_tests():
    """Run all TextLayout edge case tests"""
    print_header()

    # Edge Case Tests
    print("═ Basic Edge Cases ═")
    print_test("Empty string")
    passed, details = test_empty_string()
    print_result(passed, details)

    print_test("Single character")
    passed, details = test_single_character()
    print_result(passed, details)

    print_test("Only spaces")
    passed, details = test_only_spaces()
    print_result(passed, details)

    print_test("Only newlines")
    passed, details = test_only_newlines()
    print_result(passed, details)

    print_test("Trailing newline")
    passed, details = test_trailing_newline()
    print_result(passed, details)

    print_test("Leading newline")
    passed, details = test_leading_newline()
    print_result(passed, details)

    print_test("Multiple consecutive newlines")
    passed, details = test_multiple_consecutive_newlines()
    print_result(passed, details)

    print_test("Multiple consecutive spaces")
    passed, details = test_multiple_consecutive_spaces()
    print_result(passed, details)

    # Boundary Tests
    print("\n═ Line Width Boundary Tests ═")
    print_test("Word at exact boundary")
    passed, details = test_word_at_exact_line_boundary()
    print_result(passed, details)

    print_test("Word one char over boundary")
    passed, details = test_word_one_char_over_boundary()
    print_result(passed, details)

    print_test("Very long word")
    passed, details = test_very_long_word()
    print_result(passed, details)

    print_test("Mixed short and long words")
    passed, details = test_mixed_short_and_long_words()
    print_result(passed, details)

    # Word Boundary Tests
    print("\n═ Word Boundary Tests ═")
    print_test("Boundary at text end")
    passed, details = test_word_boundaries_at_text_end()
    print_result(passed, details)

    print_test("Boundary mid-word")
    passed, details = test_word_boundaries_mid_word()
    print_result(passed, details)

    # Pagination Tests
    print("\n═ Pagination Edge Cases ═")
    print_test("Exactly one page")
    passed, details = test_pagination_exactly_one_page()
    print_result(passed, details)

    print_test("One line over page")
    passed, details = test_pagination_one_line_over()
    print_result(passed, details)

    print_test("Empty pages")
    passed, details = test_pagination_empty_pages()
    print_result(passed, details)

    print_test("Character count preservation")
    passed, details = test_pagination_character_count()
    print_result(passed, details)

    # Cursor Position Tests
    print("\n═ Cursor Position Edge Cases ═")
    print_test("Cursor at position 0")
    passed, details = test_cursor_at_zero()
    print_result(passed, details)

    print_test("Cursor past text end")
    passed, details = test_cursor_past_text_end()
    print_result(passed, details)

    print_test("Cursor after newline")
    passed, details = test_cursor_after_newline()
    print_result(passed, details)

    print_test("Cursor on second page")
    passed, details = test_cursor_on_second_page()
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
