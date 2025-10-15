# E-Ink Typewriter Project Summary & Context

## Project Overview
Building a distraction-free e-ink typewriter using:
- **Hardware**: ESP32-S3 with MicroPython, Waveshare 4.2" e-ink display (400x300px)
- **Keyboard**: Custom matrix (5 rows × 16 columns) with physical keys
- **Goal**: Create a Word/Docs-like text editor with explicit page breaks, similar to traditional typewriters but with modern file management

## Core Design Philosophy
1. **Continuous Document Model**: Text flows naturally between pages (like Word), not independent pages
2. **Explicit Page Breaks**: Shift+Enter creates `---` markers for manual page breaks
3. **Natural Overflow**: Text automatically flows to next page when screen fills
4. **Edit at End Only**: Like a typewriter, editing happens at the document's end (last page)

## Technical Constraints & MicroPython Quirks

### Display Constraints
- **Character Size**: 12×20 pixels per character
- **Partial Refresh**: Must use `EPD_4IN2_V2_PartialDisplay()` for speed
- **E-ink Busy**: Constant refreshing causes "e-Paper busy" messages and slows responsiveness
- **Buffer Management**: `screen_content` list tracks character positions for display

### MicroPython Limitations Discovered
1. **No `os.path` module**: Use `os.stat()` to check file existence
2. **Type Hints**: Can't use `str | None`, must import Union or remove hints
3. **No Regex**: Can't use `re.split()` for parsing
4. **File Operations**: Different from standard Python (no context managers in some versions)
5. **Memory**: Limited RAM affects how much can be buffered

## Successful Fixes Implemented

### 1. Paging System (Tasks 1-3)
```python
# Added paged view state management
in_paged_view = False
stay_in_paged_view = False

# Fixed display refresh blocking during paging
if display_dirty and not in_paged_view and utime.ticks_diff(now,last_key_time)>REFRESH_PAUSE_MS:
    refresh_display()
```

### 2. Loading Pages Without Extra Space
```python
# Strip leading newlines when loading
last = last.lstrip('\n')
```

### 3. Fast Page Navigation
```python
# Removed slow clear_screen(), use partial refresh only
screen_content.clear()
epd.image1Gray.fill(epd.white)
epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
```

### 4. File Rename with Shift Support
```python
# Scan keys continuously instead of wait_for_char
pressed = scan_keys()
shift_on = any(key_map.get(k)=='Shift' for k in pressed)

# Only refresh display when needed
if needs_refresh:
    epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
    needs_refresh = False
```

### 5. Page-Aware File Saving
```python
# Track current page being edited
current_page_index = 0

# Save only current page within full document
def flush_file():
    sections = full_content.split('\n---\n')
    sections[current_page_index] = current_content
    new_content = '\n---\n'.join(sections)
```

## Current Bug: Newline Concatenation

**Problem**: When viewing pages (Page Up/Down), newlines are being removed and lines concatenate together.

**Root Cause**: The `load_pages()` function tries to calculate display lines for wrapping but loses track of actual newline characters vs wrapped lines.

**Failed Approaches**:
1. ❌ Adding `\n` to display_lines when preserving newlines
2. ❌ Using `''.join()` vs `'\n'.join()` for page text
3. ❌ Tracking newlines separately from display lines

**What Happens**:
```
Original text:
Line 1
Line 2

Displayed as:
Line 1Line 2
```

## Failed Approaches to Avoid

### 1. Complex Shift Detection in wait_for_char()
- **Tried**: Modifying `wait_for_char()` to return shift state
- **Issue**: Timing problems, shift key itself triggered returns
- **Solution**: Use main loop's scanning approach instead

### 2. Appending vs Replacing Pages
- **Tried**: Original append-only file system
- **Issue**: Deleted text reappeared on reload
- **Solution**: Replace entire page content on save

### 3. Independent Page Editing
- **Considered**: Edit any page independently
- **Issue**: Breaks document flow, complex edge cases
- **Decision**: Keep continuous document model

## Outstanding Tasks for MVP

### 1. Fix Newline Concatenation (Critical)
- Need new approach to `load_pages()` that preserves actual newlines
- Consider simpler line counting without display calculation

### 2. File Menu Deep Sleep (Task 5)
- Add 20-second timeout in `file_menu()`
- Non-blocking key detection
- Fn hold detection for manual sleep

### 3. Smart Backspace Across Pages
- Detect when at start of page
- Load previous page if backspacing from page start
- Handle both explicit breaks and overflow

### 4. Natural Overflow Handling
- Update `cursor_newline()` to handle screen overflow
- Don't add `---` for natural page breaks
- Ensure `load_pages()` handles both break types

## Code Architecture Notes

### Key Global Variables
- `screen_content`: List of (x, y, char) tuples for display
- `file_buffer`: Pending characters to write
- `current_page_index`: Which page/section being edited
- `display_dirty`/`file_dirty`: Flags for refresh timing

### File Format
```
Page 1 content
---
Page 2 content
---
Page 3 content
```

### Critical Functions
- `flush_file()`: Saves current page within document
- `load_pages()`: Splits document into displayable pages (BUGGY)
- `display_page()`: Shows page in read-only mode
- `load_previous()`: Loads last page for editing

## Recommended Next Steps

1. **Simplify `load_pages()`**: Don't calculate display lines, just split on `---` and trust the display functions to handle wrapping
2. **Add Debug Logging**: Track where newlines are lost
3. **Test Incrementally**: Fix newline issue before adding more features