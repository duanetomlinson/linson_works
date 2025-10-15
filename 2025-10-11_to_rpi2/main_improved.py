# main.py - Writer's Deck with TCA8418 keyboard controller
# Refactored with proper page/subpage handling and word wrapping

import time, utime, os, uos, esp32, machine, sys
from machine import Pin, SPI, lightsleep, SoftSPI, I2C
from display42 import EPD_4in2
from tca8418 import TCA8418
from wifi_transfer import send_file_to_server
from todoist_upload import upload_to_todoist


#───────────────────────────────────────────────#
# ─────────── Constants & Config ───────────────#
#───────────────────────────────────────────────#

# Display constants
CHAR_WIDTH = 8
CHAR_HEIGHT = 15
MARGIN_LEFT = 5
MARGIN_TOP = 5

# Timing constants
REFRESH_PAUSE_MS = 500
FILE_FLUSH_INTERVAL_MS = 2000
INACT_LIGHT_MS = 120_000   # 2 min
INACT_DEEP_MS = 600_000    # 10 min
LIGHT_SLEEP_MS = 10_000    # 10 seconds

# Power management
FN_KEY = (6, 4)
FN_HOLD_MS = 2_000

# I2C configuration
I2C_SDA = 4
I2C_SCL = 5
TCA_INT = 21
TCA_RST = 38

# Power button
POWER_BTN = Pin(0, Pin.IN, Pin.PULL_UP)

#───────────────────────────────────────────────#
# ─────────── Global State ─────────────────────#
#───────────────────────────────────────────────#

# Display objects
epd = None
keyboard = None
max_w = max_h = 0

# Text buffer - stores pure text without positioning
text_buffer = []  # List of characters including newlines

# Cursor position (logical, not screen position)
cursor_index = 0  # Index in text_buffer

# Page tracking
current_page_index = 0      # Which explicit page (separated by ---) we're on
current_subpage_index = 0   # Which overflow subpage within that page

# File paths
STORAGE_BASE = "saved_files"  # User-editable files directory
ACTIVE_FILE = ""  # Will be set after file selection

# System files (stored in root)
CURSOR_FILE = "cursor_position.txt"
SCREEN_BUFFER = "screen_buffer.txt"
ERROR_LOG = "error_log.txt"

# State flags
display_dirty = True
file_dirty = False
file_last_flush = 0
in_menu = False
in_paged_view = False

# Key tracking
prev_keys = set()
current_pressed = set()
last_key_time = 0

#───────────────────────────────────────────────#
# ─────────── Storage Setup ────────────────────#
#───────────────────────────────────────────────#

def log_exception(exc, func_name="unknown"):
    """Log exception for debugging"""
    try:
        with open(ERROR_LOG, "a") as f:
            f.write(f"\n[{utime.time()}] {func_name}: {type(exc).__name__}: {exc}\n")
            import sys
            sys.print_exception(exc, f)
    except:
        pass

def init_storage():
    """Initialize storage directories"""
    global STORAGE_BASE
    
    # Future SD card support placeholder
    SD_MOUNTED = init_sd_card()
    
    if SD_MOUNTED:
        STORAGE_BASE = "/sd/saved_files"
        print(f"  Using SD card storage: {STORAGE_BASE}")
    else:
        STORAGE_BASE = "saved_files"
        print(f"  Using internal storage: {STORAGE_BASE}")
    
    # Create saved_files directory
    try:
        os.mkdir(STORAGE_BASE)
        print(f"  Created directory: {STORAGE_BASE}")
    except OSError:
        print(f"  Directory exists: {STORAGE_BASE}")

def init_sd_card():
    """Initialize SD card and return True if successful"""
    # Disabled for now - will implement later
    return False

def save_cursor_position():
    """Save cursor position to file"""
    try:
        with open(CURSOR_FILE, "w") as f:
            f.write(f"{cursor_index},{current_page_index},{current_subpage_index}")
    except Exception as e:
        log_exception(e, "save_cursor_position")

def load_cursor_position():
    """Load cursor position from file"""
    global cursor_index, current_page_index, current_subpage_index
    try:
        with open(CURSOR_FILE, "r") as f:
            data = f.read().strip().split(',')
            if len(data) >= 3:
                cursor_index = int(data[0])
                current_page_index = int(data[1])
                current_subpage_index = int(data[2])
            else:
                # Old format compatibility
                cursor_index = int(data[0]) if data else 0
    except:
        cursor_index = 0
        current_page_index = 0
        current_subpage_index = 0

def save_screen_buffer():
    """Save current screen content to buffer file"""
    try:
        with open(SCREEN_BUFFER, "w") as f:
            f.write(''.join(text_buffer))
    except Exception as e:
        log_exception(e, "save_screen_buffer")

#───────────────────────────────────────────────#
# ──────── Text Layout Engine ──────────────────#
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

    @staticmethod
    def extract_subpage_text(pages, subpage_index):
        """Extract the actual text from a specific subpage"""
        if subpage_index >= len(pages):
            return ""
        
        text = []
        page_chars = pages[subpage_index]
        
        # Sort by y then x to maintain proper order
        sorted_chars = sorted(page_chars, key=lambda item: (item[1], item[0]))
        
        last_y = None
        for x, y, ch in sorted_chars:
            # Add newlines when y changes (except for display newlines)
            if last_y is not None and y > last_y and text and text[-1] != '\n':
                # Check if this is a wrapped line or an actual newline
                # This is tricky - we need to know if the original text had a newline here
                pass  # For now, just add the character
            text.append(ch)
            last_y = y
        
        return ''.join(text)


#───────────────────────────────────────────────#
# ──────── Async Display Manager ───────────────#
#───────────────────────────────────────────────#

class DisplayUpdate:
    """Represents a display update request"""
    def __init__(self, update_type='partial', priority=0, region=None):
        self.update_type = update_type  # 'partial', 'full', 'cursor'
        self.priority = priority        # Higher = more important
        self.region = region           # Optional (x, y, w, h) tuple
        self.timestamp = utime.ticks_ms()

def display_worker_thread():
    """Background thread that handles display updates"""
    global display_thread_running, epd
    
    print("Display worker thread started")
    last_update = utime.ticks_ms()
    min_update_interval = 200  # Minimum ms between updates
    
    while display_thread_running:
        try:
            # Wait for update request (non-blocking with timeout)
            try:
                update = display_queue.get(timeout=0.1)
            except:
                # No updates pending
                continue
            
            # Throttle updates to prevent display flashing
            now = utime.ticks_ms()
            time_since_last = utime.ticks_diff(now, last_update)
            if time_since_last < min_update_interval:
                time.sleep_ms(min_update_interval - time_since_last)
            
            # Perform the update with lock
            with display_lock:
                if update.update_type == 'partial':
                    epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
                elif update.update_type == 'full':
                    epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)
                elif update.update_type == 'cursor':
                    # Quick cursor-only update if supported
                    epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
            
            last_update = utime.ticks_ms()
            
        except Exception as e:
            log_exception(e, "display_worker_thread")
            time.sleep_ms(100)  # Prevent tight error loop
    
    print("Display worker thread stopped")

def start_display_thread():
    """Start the background display update thread"""
    global display_thread_running
    
    if not display_thread_running:
        display_thread_running = True
        _thread.start_new_thread(display_worker_thread, ())
        print("Display thread started")

def stop_display_thread():
    """Stop the background display thread"""
    global display_thread_running
    display_thread_running = False
    time.sleep_ms(200)  # Give thread time to exit

def request_display_update(update_type='partial', priority=0, region=None):
    """Queue a display update request"""
    try:
        update = DisplayUpdate(update_type, priority, region)
        display_queue.put(update, block=False)
    except:
        # Queue full, skip this update
        pass



#───────────────────────────────────────────────#
# ──────── Page Management ─────────────────────#
#───────────────────────────────────────────────#

class PageManager:
    """Manages the relationship between explicit pages and overflow subpages"""
    
    @staticmethod
    def get_full_page_text(file_content, page_index):
        """Get the complete text of an explicit page"""
        pages = file_content.split('\n---\n')
        if page_index < len(pages):
            return pages[page_index]
        return ""
    
    @staticmethod
    def merge_subpage_content(original_page_text, subpage_index, new_subpage_text, max_width, max_height):
        """Merge new subpage content with existing page content"""
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
        
        # If there are subpages after the current one, we need to decide
        # whether to keep them or discard them (for now, discard)
        
        return ''.join(result)

#───────────────────────────────────────────────#
# ──────── Display Functions ───────────────────#
#───────────────────────────────────────────────#

def clear_display_buffer():
    """Clear the display buffer"""
    epd.image1Gray.fill(0xFF)

def render_text_page(page_chars):
    """Render a page of characters to display buffer"""
    clear_display_buffer()
    for x, y, ch in page_chars:
        if ch not in '\n':
            epd.image1Gray.text(ch, x, y, epd.black)

def render_cursor(x, y):
    """Draw cursor at specified position"""
    epd.image1Gray.fill_rect(x, y + CHAR_HEIGHT - 2, CHAR_WIDTH, 2, epd.black)

def partial_refresh():
    """Partial display refresh"""
    try:
        epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
    except Exception as e:
        log_exception(e, "partial_refresh")

def full_refresh():
    """Full display refresh"""
    epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)

def refresh_display():
    """Update the physical display based on current page and subpage"""
    global display_dirty, text_buffer, current_subpage_index
    
    # For editing mode, we need to show the current buffer content
    # which represents the current subpage being edited
    current_text = ''.join(text_buffer)
    
    # Get the screen representation
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)
    
    # Since text_buffer contains only current subpage content,
    # we should always display the first page of the buffer
    if pages:
        render_text_page(pages[0])
    else:
        clear_display_buffer()
    
    # Add cursor
    cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
        current_text, cursor_index, max_w, max_h
    )
    render_cursor(cursor_x, cursor_y)
    
    # Update display
    partial_refresh()
    display_dirty = False

def show_linson():
    """Display Linson splash screen with correct colors"""
    clear_display_buffer()
    
    # Ensure white background (0xFF)
    epd.image1Gray.fill(0x00)
    
    text = "Linson"
    x = (max_w - len(text) * CHAR_WIDTH) // 2
    y = (max_h - CHAR_HEIGHT) // 2
    
    # Draw black text (0x00)
    epd.image1Gray.text(text, x, y, 0xFF)
    
    # Use full refresh to ensure proper display
    full_refresh()
    
def status(msg: str, in_page_view: bool = False, duration: int = 2000):
    """Show temporary status message with configurable duration"""
    global display_dirty
    
    # Save current display state
    bottom_y = max_h - CHAR_HEIGHT
    
    # Clear status area and show message
    epd.image1Gray.fill_rect(0, bottom_y, max_w, CHAR_HEIGHT, 0xFF)
    epd.image1Gray.text(msg, MARGIN_LEFT, bottom_y, epd.black)
    partial_refresh()
    
    def clear_status():
        epd.image1Gray.fill_rect(0, bottom_y, max_w, CHAR_HEIGHT, 0xFF)
        if not in_page_view:
            refresh_display()
        else:
            partial_refresh()
    
    machine.Timer(0).init(
        period=duration,  # Use configurable duration
        mode=machine.Timer.ONE_SHOT, 
        callback=lambda t: clear_status()
    )
#───────────────────────────────────────────────#
# ──────── Text Editing Functions ──────────────#
#───────────────────────────────────────────────#

def check_overflow():
    """Check if we've overflowed to a new subpage and handle it"""
    global current_subpage_index, text_buffer, cursor_index
    
    # Check if cursor position would be off screen
    current_text = ''.join(text_buffer)
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)
    
    if len(pages) > 1:
        # We've overflowed - need to move to next subpage
        save_current_page()
        
        # Extract text that should go to next subpage
        overflow_text = TextLayout.extract_subpage_text(pages, 1)
        
        # Move to next subpage
        current_subpage_index += 1
        text_buffer = list(overflow_text)
        cursor_index = len(text_buffer)
        
        # Clear and refresh display
        epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
        clear_display_buffer()
        full_refresh()
        
        display_dirty = True

def insert_char(ch: str):
    """Insert character at cursor position"""
    global text_buffer, cursor_index, display_dirty, file_dirty
    global current_subpage_index
    
    # Simply insert the character
    text_buffer.insert(cursor_index, ch)
    cursor_index += 1
    
    # Check if we need to move to next subpage for DISPLAY only
    # Calculate where cursor would appear on screen
    current_text = ''.join(text_buffer)
    _, _, cursor_page = TextLayout.get_cursor_screen_pos(
        current_text, cursor_index, max_w, max_h
    )
    
    # If cursor moved to next page visually, update display
    if cursor_page > 0 and current_subpage_index == 0:
        # We've typed beyond first screen
        save_current_page()
        current_subpage_index = cursor_page
        
        # Don't modify text_buffer - just update display
        epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
        clear_display_buffer()
        full_refresh()
    
    display_dirty = True
    file_dirty = True
    save_cursor_position()

def backspace():
    """Delete character before cursor"""
    global text_buffer, cursor_index, display_dirty, file_dirty
    global current_page_index, current_subpage_index
    
    if cursor_index > 0:
        cursor_index -= 1
        text_buffer.pop(cursor_index)
        display_dirty = True
        file_dirty = True
        save_cursor_position()
    elif cursor_index == 0 and (current_page_index > 0 or current_subpage_index > 0):
        # At start of current subpage, need to go back
        save_current_page()
        
        if current_subpage_index > 0:
            # Go to previous subpage of same page
            current_subpage_index -= 1
            load_specific_page(current_page_index, current_subpage_index)
            # Position cursor at end
            cursor_index = len(text_buffer)
        else:
            # Go to last subpage of previous page
            current_page_index -= 1
            # Load the page to determine number of subpages
            pages = load_pages(ACTIVE_FILE)
            if current_page_index < len(pages):
                page_text = pages[current_page_index]
                screen_pages = TextLayout.get_screen_pages(page_text, max_w, max_h)
                current_subpage_index = len(screen_pages) - 1 if screen_pages else 0
                load_specific_page(current_page_index, current_subpage_index)
                cursor_index = len(text_buffer)
        
        display_dirty = True
        file_dirty = True
        save_cursor_position()

def cursor_newline():
    """Insert newline at cursor"""
    insert_char('\n')

def delete_word():
    """Delete word before cursor"""
    global text_buffer, cursor_index, display_dirty, file_dirty
    
    if cursor_index == 0:
        return
    
    # Find start of current word
    i = cursor_index - 1
    
    # Skip trailing spaces
    while i >= 0 and text_buffer[i] == ' ':
        i -= 1
    
    # Find word boundary
    while i >= 0 and text_buffer[i] not in ' \n':
        i -= 1
    
    # Delete from word start to cursor
    chars_to_delete = cursor_index - (i + 1)
    for _ in range(chars_to_delete):
        if cursor_index > 0:
            cursor_index -= 1
            text_buffer.pop(cursor_index)
    
    display_dirty = True
    file_dirty = True
    save_cursor_position()

def clear_screen(keep_file=False):
    """Clear screen and reset to beginning of current subpage"""
    global cursor_index, display_dirty, text_buffer
    
    if not keep_file:
        save_screen_buffer()
    
    epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
    clear_display_buffer()
    full_refresh()
    
    text_buffer.clear()
    cursor_index = 0
    save_cursor_position()
    display_dirty = True

#───────────────────────────────────────────────#
# ──────── File Operations ─────────────────────#
#───────────────────────────────────────────────#

def save_current_page():
    """Save current buffer to file - only explicit newlines, no wrap formatting"""
    global file_dirty, file_last_flush, current_page_index
    
    try:
        # Read the full file
        with open(ACTIVE_FILE, "r", encoding='utf-8') as f:
            full_content = f.read()
    except:
        full_content = ""
    
    # Split into explicit pages (marked by user with Shift+Enter)
    pages = full_content.split('\n---\n')
    
    # Ensure we have enough pages
    while len(pages) <= current_page_index:
        pages.append("")
    
    # Simply save the text buffer as-is
    # It contains only user-entered text with explicit newlines
    pages[current_page_index] = ''.join(text_buffer)
    
    # Join pages back
    new_content = '\n---\n'.join(pages)
    
    try:
        with open(ACTIVE_FILE, "w", encoding='utf-8') as f:
            f.write(new_content)
        file_dirty = False
        file_last_flush = utime.ticks_ms()
        save_screen_buffer()
    except Exception as e:
        log_exception(e, "save_current_page")

def load_pages(path: str):
    """Load file and split by page markers"""
    try:
        with open(path, "r", encoding='utf-8') as f:
            content = f.read()
    except:
        return [""]
    
    if not content.strip():
        return [""]
    
    return content.split('\n---\n')

def load_specific_page(page_idx, subpage_idx=0):
    """Load a specific page into buffer - always load complete text"""
    global text_buffer, cursor_index, current_page_index, current_subpage_index
    
    current_page_index = page_idx
    current_subpage_index = subpage_idx
    
    # Get all pages
    pages = load_pages(ACTIVE_FILE)
    
    if page_idx < len(pages):
        # ALWAYS load the complete page text, including all newlines
        text_buffer = list(pages[page_idx])
    else:
        text_buffer = []
    
    # Set cursor to end
    cursor_index = len(text_buffer)
    save_cursor_position()

def load_previous():
    """Load the last page of the file"""
    global cursor_index, current_page_index, current_subpage_index
    
    pages = load_pages(ACTIVE_FILE)
    if pages:
        current_page_index = len(pages) - 1
        # Get the last page text
        last_page_text = pages[current_page_index]
        
        # Calculate number of subpages
        screen_pages = TextLayout.get_screen_pages(last_page_text, max_w, max_h)
        current_subpage_index = len(screen_pages) - 1 if screen_pages else 0
        
        # Load the specific subpage
        load_specific_page(current_page_index, current_subpage_index)
    else:
        current_page_index = 0
        current_subpage_index = 0
        text_buffer.clear()
        cursor_index = 0
    
    save_cursor_position()

def new_page_marker():
    """Insert explicit page break"""
    global file_dirty, current_page_index, current_subpage_index
    
    # Save current content
    save_current_page()
    
    # Add page marker
    try:
        with open(ACTIVE_FILE, "a", encoding='utf-8') as f:
            f.write('\n---\n')
    except Exception as e:
        log_exception(e, "new_page_marker")
    
    current_page_index += 1
    current_subpage_index = 0
    text_buffer.clear()
    cursor_index = 0
    file_dirty = True
    save_cursor_position()

def render_file(path: str):
    """Preview file without loading it for editing"""
    clear_display_buffer()
    
    try:
        with open(path, "r") as f:
            content = f.read()
    except:
        content = "(Unable to load file)"
    
    # Use TextLayout to properly render with word wrapping
    pages = TextLayout.get_screen_pages(content, max_w, max_h)
    if pages:
        render_text_page(pages[0])
    
    partial_refresh()

#───────────────────────────────────────────────#
# ──────── Keyboard Functions ──────────────────#
#───────────────────────────────────────────────#

def init_keyboard():
    """Initialize TCA8418 keyboard"""
    global keyboard
    try:
        i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
        interrupt_pin = Pin(TCA_INT, Pin.IN, Pin.PULL_UP)
        reset_pin = Pin(TCA_RST, Pin.OUT, value=1)
        
        keyboard = TCA8418(i2c, interrupt_pin=interrupt_pin, reset_pin=reset_pin)
        print("✓ TCA8418 keyboard initialized")
        return True
    except Exception as e:
        print(f"✗ Keyboard init failed: {e}")
        log_exception(e, "init_keyboard")
        return False

def scan_keys():
    """Scan keyboard and return pressed keys"""
    global keyboard, current_pressed
    
    if not keyboard:
        return set()
    
    while keyboard.get_key_count() > 0:
        event = keyboard.read_key_event()
        if event is None:
            break
        
        row, col, pressed = event
        key_pos = (row, col)
        
        if pressed:
            current_pressed.add(key_pos)
        else:
            current_pressed.discard(key_pos)
    
    return current_pressed.copy()

def glyph(lbl: str, shift: bool) -> str:
    """Convert key label to character"""
    if lbl == 'Space':
        return ' '
    
    if len(lbl) == 1:
        if shift and hasattr(keyboard, 'punct_map') and lbl in keyboard.punct_map:
            return keyboard.punct_map[lbl]
        elif lbl.isalpha():
            return lbl.upper() if shift else lbl.lower()
        else:
            return lbl
    
    return lbl

def wait_for_char() -> str:
    """Wait for a single character"""
    while True:
        pressed = scan_keys()
        if pressed:
            for pos in pressed:
                lbl = keyboard.key_map.get(pos, '')
                if lbl:
                    # Wait for key release
                    while scan_keys():
                        time.sleep_ms(10)
                    return lbl
        time.sleep_ms(10)

#───────────────────────────────────────────────#
# ──────── Menu Functions ──────────────────────#
#───────────────────────────────────────────────#

def list_txt_files():
    """List only user-editable text files"""
    files = []
    
    # List files in the saved_files directory
    try:
        for f in os.listdir(STORAGE_BASE):
            if f.endswith('.txt'):
                # Skip any system files that somehow ended up here
                if f not in ['cursor_position.txt', 'screen_buffer.txt', 'error_log.txt']:
                    try:
                        stat = os.stat(f"{STORAGE_BASE}/{f}")
                        mtime = stat[8] if len(stat) > 8 else 0
                    except:
                        mtime = 0
                    files.append((mtime, f))
    except Exception as e:
        log_exception(e, "list_txt_files")
    
    files.sort(reverse=True)
    return [f for _, f in files]

def file_menu(from_editor=False):
    """File selection menu"""
    global in_menu, display_dirty, prev_keys
    
    in_menu = True
    saved_display_dirty = display_dirty
    display_dirty = False
    
    files = list_txt_files()
    
    if not files:
        if not from_editor:
            # Create new file at startup
            timestamp = utime.time() % 100000
            new_name = f"note_{timestamp}.txt"
            new_path = f"{STORAGE_BASE}/{new_name}"
            open(new_path, 'w').close()
            status(f"Created: {new_name}")
            in_menu = False
            display_dirty = saved_display_dirty
            return new_name
        else:
            status("No .txt files found")
            in_menu = False
            display_dirty = saved_display_dirty
            return None
    
    # Menu state
    idx = 0
    window = 0
    max_files_shown = min(10, (max_h - CHAR_HEIGHT * 3) // CHAR_HEIGHT)
    last_activity = utime.ticks_ms()
    fn_down_at = None
    
    def draw_menu():
        clear_display_buffer()
        
        # Draw files
        for i, name in enumerate(files[window:window + max_files_shown]):
            y = MARGIN_TOP + i * CHAR_HEIGHT
            if window + i == idx:
                epd.image1Gray.text("► " + name, MARGIN_LEFT, y, epd.black)
            else:
                epd.image1Gray.text("  " + name, MARGIN_LEFT, y, epd.black)
        
        # Draw footer
        footer_y = max_h - CHAR_HEIGHT * 2
        epd.image1Gray.text(f"Files {idx+1}/{len(files)}", MARGIN_LEFT, footer_y, epd.black)
        epd.image1Gray.text("[Fn hold] Sleep | [PgUp/PgDn] Navigate", 
                           MARGIN_LEFT, footer_y + CHAR_HEIGHT, epd.black)
        
        partial_refresh()
    
    # Initial draw
    draw_menu()
    
    # Clear key state
    prev_keys = set()
    current_pressed.clear()
    
    # Menu loop
    while True:
        pressed = scan_keys()
        new_keys = pressed - prev_keys
        
        # Check Fn long-press
        if FN_KEY in pressed:
            if fn_down_at is None:
                fn_down_at = utime.ticks_ms()
            elif utime.ticks_diff(utime.ticks_ms(), fn_down_at) >= FN_HOLD_MS:
                in_menu = False
                display_dirty = saved_display_dirty
                shutdown()
        else:
            fn_down_at = None
        
        if new_keys:
            last_activity = utime.ticks_ms()
            
            for k in new_keys:
                lbl = keyboard.key_map.get(k, '')
                
                if lbl in ['PgUp', 'Up'] and idx > 0:
                    idx -= 1
                    if idx < window:
                        window = idx
                    draw_menu()
                    
                elif lbl in ['PgDn', 'Down'] and idx < len(files) - 1:
                    idx += 1
                    if idx >= window + max_files_shown:
                        window = idx - max_files_shown + 1
                    draw_menu()
                    
                elif lbl == 'Enter':
                    # Show file preview
                    render_file(f"{STORAGE_BASE}/{files[idx]}")
                    time.sleep(1)
                    in_menu = False
                    display_dirty = saved_display_dirty
                    return files[idx]
                    
                elif lbl == 'Esc' and from_editor:
                    in_menu = False
                    display_dirty = saved_display_dirty
                    return None
                
                elif lbl in ["Backspace", "Del"]:          # NEW – delete highlighted file
                    to_remove = f"{STORAGE_BASE}/{files[idx]}"
                    if action_delete(to_remove):
                        files = list_txt_files()           # refresh list
                        idx   = max(0, min(idx, len(files) - 1))
                        window = max(0, min(window, idx))
                        draw_menu()
        
        prev_keys = pressed
        
        # Timeout check
        if from_editor and utime.ticks_diff(utime.ticks_ms(), last_activity) > 30_000:
            in_menu = False
            display_dirty = saved_display_dirty
            return None
        
        time.sleep_ms(10)

def prompt_filename(initial: str = "new_note.txt") -> str:
    """Prompt for filename input"""
    global keyboard, prev_keys
    
    # Clear screen and show layout
    clear_display_buffer()
    epd.image1Gray.text("Rename file:", MARGIN_LEFT, MARGIN_TOP, epd.black)
    epd.image1Gray.text("Current:  " + initial, MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
    epd.image1Gray.text("New name: ", MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, epd.black)
    partial_refresh()
    
    buf = list(initial.replace('.txt', ''))
    prev_keys = set()
    first_backspace = True
    needs_refresh = True
    
    while True:
        if needs_refresh:
            epd.image1Gray.fill_rect(MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, 
                                    max_w, CHAR_HEIGHT, epd.white)
            epd.image1Gray.text("New name: " + "".join(buf), 
                               MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, epd.black)
            partial_refresh()
            needs_refresh = False
        
        pressed = scan_keys()
        new_keys = pressed - prev_keys
        
        shift_on = any(keyboard.key_map.get(k) == 'Shift' for k in pressed)
        
        if new_keys:
            for k in new_keys:
                lbl = keyboard.key_map.get(k, '')
                
                if lbl == "Enter" and buf:
                    return "".join(buf)
                elif lbl == "Esc":
                    return None
                elif lbl == "Backspace":
                    if first_backspace and "".join(buf) == initial.replace('.txt', ''):
                        buf = []
                        first_backspace = False
                    elif buf:
                        buf.pop()
                    needs_refresh = True
                elif lbl == "Space":
                    buf.append(' ')
                    needs_refresh = True
                elif len(lbl) == 1:
                    ch = glyph(lbl, shift_on)
                    buf.append(ch)
                    needs_refresh = True
        
        prev_keys = pressed
        time.sleep_ms(10)

#───────────────────────────────────────────────#
# ──────── Page View Functions ─────────────────#
#───────────────────────────────────────────────#

def display_page(page_num: int, subpage_num: int, total_pages: int, page_text: str):
    """Display a page in read-only view mode"""
    global display_dirty
    
    clear_display_buffer()
    
    # Get pages for the text (leave room for footer)
    pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)
    
    # Ensure valid subpage
    if subpage_num >= len(pages):
        subpage_num = len(pages) - 1
    if subpage_num < 0:
        subpage_num = 0
    
    # Render the subpage
    if pages and subpage_num < len(pages):
        render_text_page(pages[subpage_num])
    
    # Draw footer
    footer_y = max_h - CHAR_HEIGHT - 2
    epd.image1Gray.text("[=] Page View – Read Only", MARGIN_LEFT, footer_y, epd.black)
    
    # Page number
    num_subpages = len(pages)
    if num_subpages > 1:
        label = f"{page_num + 1}.{subpage_num + 1}/{total_pages}"
    else:
        label = f"{page_num + 1}/{total_pages}"
    label_width = len(label) * CHAR_WIDTH
    px = max_w - label_width - 10
    epd.image1Gray.text(label, px, footer_y, epd.black)
    
    partial_refresh()
    display_dirty = False

#───────────────────────────────────────────────#
# ──────── Power Management ────────────────────#
#───────────────────────────────────────────────#

def idle_sleep():
    """Enter deep sleep mode until any key press"""
    try:
        # Save state
        if file_dirty:
            save_current_page()
        save_cursor_position()
        
        # Show Linson screen
        show_linson()
        time.sleep_ms(200)
        
        # Clear keyboard buffer
        if keyboard:
            while keyboard.get_key_count() > 0:
                keyboard.read_key_event()
        
        # Configure wake on TCA_INT (GPIO 21)
        # This is within RTC domain (0-21) on ESP32-S3
        wake_pin = Pin(TCA_INT, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext0(pin=wake_pin, level=esp32.WAKEUP_ALL_LOW)
        
        # Enter deep sleep
        print("Entering deep sleep, any key to wake...")
        machine.deepsleep()
        
    except Exception as e:
        log_exception(e, "idle_sleep")
        # On any error, just reset
        machine.reset()

def shutdown():
    """Enter deep sleep (manual shutdown with Fn key hold)"""
    # Save work
    if file_dirty:
        save_current_page()
    
    # Show shutdown screen
    show_linson()
    time.sleep_ms(500)
    
    # Reset keyboard
    if keyboard:
        keyboard.reset()
    
    # Configure wake on any key press (via TCA_INT)
    esp32.wake_on_ext0(pin=Pin(TCA_INT), level=esp32.WAKEUP_ALL_LOW)
    
    # Enter deep sleep
    machine.deepsleep()
    
    
#───────────────────────────────────────────────#
# ──────── Main Actions ─────────────────────────#
#───────────────────────────────────────────────#

def action_save():
    """Save current file"""
    save_current_page()
    status("Saved")

def action_open():
    """Open a file"""
    global ACTIVE_FILE, text_buffer, cursor_index, file_dirty
    global current_page_index, current_subpage_index
    
    # Save current work
    action_save()
    time.sleep_ms(50)
    
    # Clear any pending keys
    while scan_keys():
        time.sleep_ms(10)
    
    choice = file_menu(from_editor=True)
    
    if choice:
        ACTIVE_FILE = f"{STORAGE_BASE}/{choice}"
        open(ACTIVE_FILE, 'a').close()
        current_page_index = 0
        current_subpage_index = 0
        clear_screen(True)
        load_previous()
        refresh_display()
        status(f"Opened: {choice}")
        file_dirty = False
        display_dirty = False
    else:
        # User cancelled - restore display
        refresh_display()
        display_dirty = False
    
    time.sleep_ms(100)

def action_new():
    """Create new file"""
    global ACTIVE_FILE, text_buffer, cursor_index, current_page_index, current_subpage_index
    
    timestamp = utime.time() % 100000
    ACTIVE_FILE = f"{STORAGE_BASE}/note_{timestamp}.txt"
    open(ACTIVE_FILE, 'w').close()
    
    text_buffer.clear()
    cursor_index = 0
    current_page_index = 0
    current_subpage_index = 0
    
    clear_screen(True)
    status(f"New: note_{timestamp}.txt")
    file_dirty = False

def action_rename():
    """Rename current file"""
    global ACTIVE_FILE, file_dirty
    
    # Save current display state
    saved_text = text_buffer[:]
    saved_cursor = cursor_index
    
    old_name = ACTIVE_FILE.split("/")[-1]
    new_name = prompt_filename(old_name)
    
    if new_name is None:
        # User cancelled
        refresh_display()
        status("Rename cancelled")
        return
    
    new_name = new_name.strip()
    if not new_name.endswith(".txt"):
        new_name += ".txt"
    new_path = f"{STORAGE_BASE}/{new_name}"
    
    try:
        os.rename(ACTIVE_FILE, new_path)
        ACTIVE_FILE = new_path
        open(ACTIVE_FILE, 'a').close()
        file_dirty = False
        clear_screen(True)
        load_previous()
        status(f"Renamed: {new_name}")
    except OSError as e:
        log_exception(e, "action_rename")
        status("Rename failed!")
        # Restore display
        text_buffer = saved_text
        cursor_index = saved_cursor
        refresh_display()
        
def action_upload():
    """Upload current file to home server with enhanced feedback"""
    global file_dirty
    
    # Save current work first
    if file_dirty:
        save_current_page()
    
    # Get file size for display
    try:
        file_stats = os.stat(ACTIVE_FILE)
        file_size = file_stats[6]  # Size in bytes
        size_kb = file_size / 1024
    except:
        size_kb = 0
    
    # Confirm with user - show more details
    clear_display_buffer()
    epd.image1Gray.text("Send to server?", MARGIN_LEFT, MARGIN_TOP, epd.black)
    epd.image1Gray.text(f"File: {ACTIVE_FILE.split('/')[-1]}", 
                       MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
    epd.image1Gray.text(f"Size: {size_kb:.1f} KB", 
                       MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, epd.black)
    epd.image1Gray.text("[Enter] Send  [Esc] Cancel", 
                       MARGIN_LEFT, MARGIN_TOP + 4 * CHAR_HEIGHT, epd.black)
    partial_refresh()
    
    # Wait for response
    while True:
        choice = wait_for_char()
        if choice == 'Enter':
            break
        elif choice == 'Esc':
            refresh_display()
            status("Upload cancelled")
            return
    
    # Show uploading screen with progress
    clear_display_buffer()
    epd.image1Gray.text("Uploading...", MARGIN_LEFT, MARGIN_TOP, epd.black)
    epd.image1Gray.text(f"File: {ACTIVE_FILE.split('/')[-1]}", 
                       MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
    epd.image1Gray.text("Please wait...", 
                       MARGIN_LEFT, MARGIN_TOP + 3 * CHAR_HEIGHT, epd.black)
    partial_refresh()
    
    # Track timing
    start_time = utime.ticks_ms()
    
    # Send the file
    success, message = send_file_to_server(ACTIVE_FILE, status_callback=status)
    
    # Calculate transfer time
    transfer_time = utime.ticks_diff(utime.ticks_ms(), start_time) / 1000
    
    # Show detailed result
    refresh_display()
    if success:
        # Success - show transfer details
        clear_display_buffer()
        epd.image1Gray.text("Upload Complete!", MARGIN_LEFT, MARGIN_TOP, epd.black)
        epd.image1Gray.text(f"{message}", MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
        epd.image1Gray.text(f"Time: {transfer_time:.1f} seconds", 
                           MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, epd.black)
        epd.image1Gray.text(f"Size: {size_kb:.1f} KB", 
                           MARGIN_LEFT, MARGIN_TOP + 3 * CHAR_HEIGHT, epd.black)
        epd.image1Gray.text("[Any key to continue]", 
                           MARGIN_LEFT, MARGIN_TOP + 5 * CHAR_HEIGHT, epd.black)
        partial_refresh()
        
        # Wait for key press
        wait_for_char()
        refresh_display()
    else:
        # Failure - show error for longer
        status(f"✗ Upload failed: {message}", duration=5000)  # Show for 5 seconds


def action_upload_todoist():
    """Upload current file to Todoist as a backup"""
    global file_dirty
    
    # Save current work first
    if file_dirty:
        save_current_page()
    
    # Get file info for display
    try:
        char_count = len(''.join(text_buffer))
    except:
        char_count = 0
    
    # Confirm with user
    clear_display_buffer()
    epd.image1Gray.text("Upload to Todoist?", MARGIN_LEFT, MARGIN_TOP, epd.black)
    epd.image1Gray.text(f"File: {ACTIVE_FILE.split('/')[-1]}", 
                       MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
    epd.image1Gray.text(f"Size: {char_count} chars", 
                       MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, epd.black)
    epd.image1Gray.text("[Enter] Upload  [Esc] Cancel", 
                       MARGIN_LEFT, MARGIN_TOP + 4 * CHAR_HEIGHT, epd.black)
    partial_refresh()
    
    # Wait for response
    while True:
        choice = wait_for_char()
        if choice == 'Enter':
            break
        elif choice == 'Esc':
            refresh_display()
            status("Upload cancelled")
            return
    
    # Show uploading screen
    clear_display_buffer()
    epd.image1Gray.text("Uploading to Todoist...", MARGIN_LEFT, MARGIN_TOP, epd.black)
    epd.image1Gray.text(f"File: {ACTIVE_FILE.split('/')[-1]}", 
                       MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
    partial_refresh()
    
    # Track timing
    start_time = utime.ticks_ms()
    
    # Upload the file
    success, message = upload_to_todoist(ACTIVE_FILE, status_callback=status)
    
    # Calculate transfer time
    transfer_time = utime.ticks_diff(utime.ticks_ms(), start_time) / 1000
    
    # Show result
    refresh_display()
    if success:
        # Success screen
        clear_display_buffer()
        epd.image1Gray.text("Upload Complete!", MARGIN_LEFT, MARGIN_TOP, epd.black)
        epd.image1Gray.text(f"{message}", MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)
        epd.image1Gray.text(f"Time: {transfer_time:.1f}s", 
                           MARGIN_LEFT, MARGIN_TOP + 2 * CHAR_HEIGHT, epd.black)
        epd.image1Gray.text("Check Todoist Inbox", 
                           MARGIN_LEFT, MARGIN_TOP + 4 * CHAR_HEIGHT, epd.black)
        epd.image1Gray.text("[Any key]", 
                           MARGIN_LEFT, MARGIN_TOP + 6 * CHAR_HEIGHT, epd.black)
        partial_refresh()
        
        # Wait for key press
        wait_for_char()
        refresh_display()
    else:
        # Failure - show error
        status(f"Upload failed: {message}")
        
        
def action_delete(path: str | None = None):
    """
    Permanently delete a .txt file.
    If called with no path it deletes the ACTIVE_FILE.
    Returns True on success, False on cancel/error.
    """
    global ACTIVE_FILE, text_buffer, cursor_index
    global current_page_index, current_subpage_index, file_dirty

    target = path or ACTIVE_FILE
    name   = target.split('/')[-1]

    # confirmation dialog
    clear_display_buffer()
    epd.image1Gray.text(f"Delete '{name}'?", MARGIN_LEFT, MARGIN_TOP, epd.black)
    epd.image1Gray.text("[Enter] Yes   [Esc] No", 
                        MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT * 2, epd.black)
    partial_refresh()

    while True:
        key = wait_for_char()
        if key == "Enter":
            break
        if key == "Esc":
            refresh_display(); status("Delete cancelled")
            return False

    try:
        os.remove(target)
        status("File deleted")

        # If we just deleted the open file, fall back to a fresh note
        if target == ACTIVE_FILE:
            text_buffer.clear(); cursor_index = 0
            current_page_index = current_subpage_index = 0
            file_dirty = False
            action_new()            # reuse existing helper
        return True

    except Exception as e:
        log_exception(e, "action_delete")
        status("✗ Delete failed")
        return False

#───────────────────────────────────────────────#
# ──────── Main Program ─────────────────────────#
#───────────────────────────────────────────────#

def main():
    """Main program entry point"""
    global epd, max_w, max_h, ACTIVE_FILE
    global display_dirty, file_dirty, prev_keys
    global last_key_time, file_last_flush
    global current_page_index, current_subpage_index
    global in_paged_view
    
    # Check wake reason
    wake_reason = machine.reset_cause()
    print(f"Reset cause: {wake_reason}")
    if wake_reason == machine.DEEPSLEEP_RESET:
        print("Woke from deep sleep!")
    
    # Initialize storage first
    init_storage()
    
    # Initialize display
    epd = EPD_4in2()
    epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
    clear_display_buffer()
    full_refresh()
    time.sleep_ms(100)
    print("Display initialized")
    
    # Set display dimensions
    max_w, max_h = epd.width, epd.height
    print(f"Display: {max_w}x{max_h}, char: {CHAR_WIDTH}x{CHAR_HEIGHT}")
    
    # Initialize keyboard
    if not init_keyboard():
        print("Failed to initialize keyboard!")
        return
    
    # Show ready message
    clear_display_buffer()
    epd.image1Gray.text("Keyboard ready", 10, 10, epd.black)
    partial_refresh()
    time.sleep(1)
    
    # File selection
    choice = file_menu(from_editor=False)
    if choice:
        ACTIVE_FILE = f"{STORAGE_BASE}/{choice}"
    else:
        # Should not happen, but create default file
        ACTIVE_FILE = f"{STORAGE_BASE}/text_log.txt"
    
    # Ensure file exists
    open(ACTIVE_FILE, 'a').close()
    
    # Load cursor position and content
    load_cursor_position()
    load_previous()
    refresh_display()
    status(f"Editing: {ACTIVE_FILE.split('/')[-1]}")
    
    # Initialize timing
    last_key_time = utime.ticks_ms()
    file_last_flush = last_key_time
    fn_down_at = None
    
    # Page view state
    in_paged_view = False
    view_page_index = 0
    view_subpage_index = 0
    pages = []
    
    # Main loop
    while True:
        now = utime.ticks_ms()
        pressed = scan_keys()
        new_keys = pressed - prev_keys
        
        # Check modifiers
        alt_on = any(keyboard.key_map.get(k) == 'Alt' for k in pressed)
        shift_on = any(keyboard.key_map.get(k) == 'Shift' for k in pressed)
        ctrl_on = any(keyboard.key_map.get(k) == 'Ctrl' for k in pressed)
        
        # Fn long-press for shutdown
        if FN_KEY in pressed:
            if fn_down_at is None:
                fn_down_at = now
            elif utime.ticks_diff(now, fn_down_at) >= FN_HOLD_MS:
                shutdown()
        else:
            fn_down_at = None
        
        # Process key presses
        if new_keys:
            for k in new_keys:
                lbl = keyboard.key_map.get(k, '')
                
                # Page View mode
                if lbl in ('PgUp', 'PgDn', 'Home'):
                    if not in_paged_view:
                        # Enter page view mode
                        if file_dirty or text_buffer:
                            save_current_page()
                        
                        in_paged_view = True
                        pages = load_pages(ACTIVE_FILE)
                        view_page_index = current_page_index
                        view_subpage_index = current_subpage_index
                    
                    if lbl == 'PgUp':
                        # Navigate backwards through subpages then pages
                        if view_subpage_index > 0:
                            view_subpage_index -= 1
                        elif view_page_index > 0:
                            view_page_index -= 1
                            # Calculate subpages for new page
                            page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                            screen_pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)
                            view_subpage_index = len(screen_pages) - 1 if screen_pages else 0
                        else:
                            status("Already at first page", in_page_view=True)
                            continue
                        
                        # Display the page
                        page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                        display_page(view_page_index, view_subpage_index, len(pages), page_text)
                        
                    elif lbl == 'PgDn':
                        # Navigate forwards through subpages then pages
                        page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                        screen_pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)
                        num_subpages = len(screen_pages)
                        
                        if view_subpage_index < num_subpages - 1:
                            view_subpage_index += 1
                        elif view_page_index < len(pages) - 1:
                            view_page_index += 1
                            view_subpage_index = 0
                        else:
                            status("Already at last page", in_page_view=True)
                            continue
                        
                        # Display the page
                        page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                        display_page(view_page_index, view_subpage_index, len(pages), page_text)
                        
                    elif lbl == 'Home':
                        # Exit page view mode
                        in_paged_view = False
                        
                        # Check if we were viewing a different page than we're editing
                        if view_page_index != current_page_index:
                            # User navigated to a different page - load it
                            current_page_index = view_page_index
                            current_subpage_index = view_subpage_index
                            load_specific_page(current_page_index, 0)  # Load full page
                        # else: keep the current text_buffer as is
                        
                        refresh_display()
                        status("Resumed editing")
                    continue
                
                # Skip other keys in page view mode
                if in_paged_view:
                    continue
                
                # Ctrl combinations
                if ctrl_on and lbl and len(lbl) == 1 and lbl.lower() in 'sonrtd':
                    display_dirty = False
                    actions = {
                        's': action_save,
                        'o': action_open,
                        'n': action_new,
                        'r': action_rename,
                        't': action_upload_todoist,
                        'd': action_delete            # NEW – Ctrl+D deletes current file
                    }
                    actions[lbl.lower()]()
                    continue
                
                # Alt+Backspace
                if alt_on and lbl == 'Backspace':
                    delete_word()
                    continue
                
                # Normal typing
                if lbl == 'Backspace':
                    backspace()
                elif lbl == 'Enter':
                    if shift_on:
                        new_page_marker()
                        clear_screen()
                    else:
                        cursor_newline()
                elif lbl == 'Space':
                    insert_char(' ')
                elif len(lbl) == 1:
                    ch = glyph(lbl, shift_on)
                    insert_char(ch)
            
            last_key_time = now
        
        prev_keys = pressed
        
        # Display refresh
        if display_dirty and not in_paged_view and not in_menu and \
           utime.ticks_diff(now, last_key_time) > REFRESH_PAUSE_MS:
            refresh_display()
        
        # File save
        if file_dirty and not in_paged_view and \
           utime.ticks_diff(now, last_key_time) > REFRESH_PAUSE_MS and \
           utime.ticks_diff(now, file_last_flush) > FILE_FLUSH_INTERVAL_MS:
            save_current_page()
            
        # Idle detection
        idle_time = utime.ticks_diff(now, last_key_time)
        if idle_time >= INACT_DEEP_MS:
            # 10 minutes - deep sleep
            idle_sleep()
        elif idle_time >= INACT_LIGHT_MS:
            # 2 minutes - also deep sleep (since you want restart behavior)
            idle_sleep()
        
        time.sleep_ms(10)

if __name__ == "__main__":
    main() 


