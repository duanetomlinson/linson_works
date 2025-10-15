"""
editor_base.py - Shared utilities for both threading and async approaches
Provides text layout, pagination, and file management utilities
For Raspberry Pi Pico 2W e-ink typewriter investigation

This module is shared between main_threaded.py and main_async.py
"""

# Display constants
CHAR_WIDTH = 8
CHAR_HEIGHT = 15
MARGIN_LEFT = 5
MARGIN_TOP = 5


class TextLayout:
    """
    Handles text layout and word wrapping logic
    Pure computational class - no I/O or blocking operations
    """

    @staticmethod
    def get_word_boundaries(text, start_pos=0):
        """
        Find word boundaries from a starting position

        Args:
            text: String to analyze
            start_pos: Position to start searching from

        Returns:
            (word_start, word_end) tuple of indices
        """
        if start_pos >= len(text):
            return start_pos, start_pos

        # Skip any leading spaces
        while start_pos < len(text) and text[start_pos] == ' ':
            start_pos += 1

        word_start = start_pos
        word_end = start_pos

        # Find end of word (stop at space or newline)
        while word_end < len(text) and text[word_end] not in ' \n':
            word_end += 1

        return word_start, word_end

    @staticmethod
    def calculate_lines(text, max_width):
        """
        Calculate line breaks with word wrapping

        Args:
            text: String to wrap
            max_width: Maximum width in pixels

        Returns:
            List of lines, where each line is [(x_pos, char), ...]
        """
        lines = []
        current_line = []
        current_x = MARGIN_LEFT
        i = 0

        while i < len(text):
            # Handle explicit newlines
            if text[i] == '\n':
                lines.append(current_line[:])
                current_line = []
                current_x = MARGIN_LEFT
                i += 1
                continue

            # Handle spaces
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
                # Word fits - add it
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

        # Add final line if not empty
        if current_line:
            lines.append(current_line)

        return lines

    @staticmethod
    def get_screen_pages(text, max_width, max_height):
        """
        Calculate screen pages from text with word wrapping

        Args:
            text: String to paginate
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels

        Returns:
            List of pages, where each page is [(x, y, char), ...]
        """
        lines = TextLayout.calculate_lines(text, max_width)
        pages = []
        current_page = []
        current_y = MARGIN_TOP

        for line in lines:
            if current_y + CHAR_HEIGHT > max_height:
                # Line doesn't fit - start new page
                pages.append(current_page[:])
                current_page = []
                current_y = MARGIN_TOP

            # Add y-coordinate to each character
            line_with_y = [(x, current_y, ch) for x, ch in line]
            current_page.extend(line_with_y)
            current_y += CHAR_HEIGHT

        # Add final page if not empty
        if current_page:
            pages.append(current_page)

        return pages if pages else [[]]

    @staticmethod
    def get_cursor_screen_pos(text, cursor_index, max_width, max_height):
        """
        Convert cursor index to screen position (x, y, page_num)

        Args:
            text: Current text buffer
            cursor_index: Index in text buffer
            max_width: Screen width
            max_height: Screen height

        Returns:
            (x, y, page_num) tuple
        """
        if cursor_index > len(text):
            cursor_index = len(text)

        # Calculate lines up to cursor
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

    @staticmethod
    def extract_subpage_text(pages, subpage_index):
        """
        Extract the actual text from a specific subpage

        Args:
            pages: List of pages from get_screen_pages()
            subpage_index: Which subpage to extract

        Returns:
            String of text from that subpage
        """
        if subpage_index >= len(pages):
            return ""

        text = []
        page_chars = pages[subpage_index]

        # Sort by y then x to maintain proper order
        sorted_chars = sorted(page_chars, key=lambda item: (item[1], item[0]))

        for x, y, ch in sorted_chars:
            text.append(ch)

        return ''.join(text)


class PageManager:
    """
    Manages the relationship between explicit pages and overflow subpages
    Explicit pages are user-created with Shift+Enter (--- markers)
    Subpages are automatic overflows when text exceeds screen height
    """

    @staticmethod
    def get_full_page_text(file_content, page_index):
        """
        Get the complete text of an explicit page

        Args:
            file_content: Full file content string
            page_index: Which explicit page (0-indexed)

        Returns:
            String of page text
        """
        pages = file_content.split('\n---\n')
        if page_index < len(pages):
            return pages[page_index]
        return ""

    @staticmethod
    def split_into_pages(file_content):
        """
        Split file content into explicit pages

        Args:
            file_content: Full file content string

        Returns:
            List of page strings
        """
        if not file_content.strip():
            return [""]
        return file_content.split('\n---\n')

    @staticmethod
    def merge_pages(pages):
        """
        Merge pages back into file content

        Args:
            pages: List of page strings

        Returns:
            Full file content string
        """
        return '\n---\n'.join(pages)

    @staticmethod
    def merge_subpage_content(original_page_text, subpage_index, new_subpage_text,
                            max_width, max_height):
        """
        Merge new subpage content with existing page content
        Used when editing a specific subpage of a multi-subpage document

        Args:
            original_page_text: Original full page text
            subpage_index: Which subpage is being edited
            new_subpage_text: New text for that subpage
            max_width: Screen width
            max_height: Screen height

        Returns:
            Updated full page text
        """
        if subpage_index == 0:
            # First subpage - just return the new text
            return new_subpage_text

        # Get all subpages from original text
        all_subpages = TextLayout.get_screen_pages(original_page_text, max_width, max_height)

        # Reconstruct text from previous subpages
        result = []

        # Add text from all previous subpages
        for i in range(min(subpage_index, len(all_subpages))):
            subpage_text = TextLayout.extract_subpage_text(all_subpages, i)
            result.append(subpage_text)

        # Add the new subpage text
        result.append(new_subpage_text)

        # Note: Subpages after current one are discarded
        # This is intentional editing behavior

        return ''.join(result)


class KeyboardHelper:
    """Helper functions for keyboard input processing"""

    # Punctuation mapping for shift key combinations
    PUNCT_MAP = {
        '1':'!', '2':'@', '3':'#', '4':'$', '5':'%', '6':'^',
        '7':'&', '8':'*', '9':'(', '0':')', '-':'_', '=':'+',
        '/':'?', ',':'<', '.':'>', ';':':', "'":'"', '[':'{',
        ']':'}', '\\':'|'
    }

    @staticmethod
    def glyph(key_label, shift_pressed):
        """
        Convert key label to character with shift handling

        Args:
            key_label: Key name from keyboard (e.g., 'A', '1', 'Space')
            shift_pressed: Whether shift is held

        Returns:
            Character to insert
        """
        if key_label == 'Space':
            return ' '

        if len(key_label) == 1:
            # Handle punctuation with shift
            if shift_pressed and key_label in KeyboardHelper.PUNCT_MAP:
                return KeyboardHelper.PUNCT_MAP[key_label]
            # Handle alphabetic with shift
            elif key_label.isalpha():
                return key_label.upper() if shift_pressed else key_label.lower()
            else:
                return key_label

        # Return special keys as-is for caller to handle
        return key_label


class FileHelper:
    """Helper functions for file operations"""

    @staticmethod
    def ensure_directory(path):
        """
        Ensure directory exists, create if needed

        Args:
            path: Directory path
        """
        import os
        try:
            os.mkdir(path)
        except OSError:
            pass  # Directory already exists

    @staticmethod
    def load_file(path):
        """
        Load file content safely

        Args:
            path: File path

        Returns:
            File content as string, or empty string on error
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ""

    @staticmethod
    def save_file(path, content):
        """
        Save content to file safely

        Args:
            path: File path
            content: String content to save

        Returns:
            True on success, False on error
        """
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except:
            return False

    @staticmethod
    def list_files(directory, extension='.txt'):
        """
        List files in directory with given extension

        Args:
            directory: Directory path
            extension: File extension to filter (default '.txt')

        Returns:
            List of filenames (sorted by modification time, newest first)
        """
        import os
        files = []

        try:
            for f in os.listdir(directory):
                if f.endswith(extension):
                    try:
                        stat = os.stat(f"{directory}/{f}")
                        mtime = stat[8] if len(stat) > 8 else 0
                    except:
                        mtime = 0
                    files.append((mtime, f))
        except:
            pass

        files.sort(reverse=True)
        return [f for _, f in files]


class MemoryHelper:
    """Helper functions for memory management"""

    @staticmethod
    def print_memory_stats():
        """Print current memory usage statistics"""
        import gc
        gc.collect()
        free = gc.mem_free()
        allocated = gc.mem_alloc()
        total = free + allocated
        print(f"Memory: {allocated}/{total} bytes ({allocated*100//total}% used)")

    @staticmethod
    def force_gc():
        """Force garbage collection"""
        import gc
        gc.collect()


# ASCII art for architectural understanding
"""
TEXT LAYOUT WORKFLOW:
====================

Text Buffer (linear)
    |
    v
calculate_lines()  --> [(x, char), (x, char), ...] per line
    |
    v
get_screen_pages() --> [(x, y, char), ...] per page
    |
    v
Display Rendering


PAGE MANAGEMENT:
================

File Content
    |
    v
split('\n---\n') --> [Page 0, Page 1, Page 2, ...]  (Explicit pages)
    |
    v
get_screen_pages() --> [[Subpage 0.0], [Subpage 0.1], ...]  (Auto overflow)
    |
    v
Display or Edit


CURSOR POSITIONING:
===================

cursor_index in text_buffer
    |
    v
calculate_lines(text[:cursor_index])
    |
    v
Determine line count --> Calculate page and y position
    |
    v
Get last line position --> Calculate x position
    |
    v
(x, y, page_num)
"""
