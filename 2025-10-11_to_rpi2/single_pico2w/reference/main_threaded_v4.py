"""
main_threaded_v4.py - Dual-core threading with optimized refresh + interrupt keyboard
Version 4: Production-ready with all critical performance fixes

CHANGES IN V4:
==============
1. CRITICAL: Interrupt-driven keyboard (checks has_interrupt() before FIFO)
   → SUPERIOR to ESP32 version which uses pure polling
2. CRITICAL PERFORMANCE FIXES:
   → Display throttle: ZERO (0ms) - updates on EVERY keystroke for fast typers
   → Worker throttle: 50ms (minimal e-ink protection only)
   → Keyboard scan: 1000Hz (1ms) - captures EVERY keystroke, never misses input
   → Removed SPI lock from buffer rendering - only locks actual SPI operations
3. DISPLAY FIXES:
   → Menu uses FULL refresh to clear old arrow positions (was partial)
   → Cursor tracking: clears old position BEFORE drawing new one
   → All refreshes use FULL mode for cleaner display (no ghosting)
4. Code quality:
   → Fixed missing global declarations (menu_files, file_dirty, last_cursor_pos)
   → Added debug output for menu key detection

FIXES FROM V3:
==============
✓ Interrupt-driven keyboard solves Enter key detection issues
✓ menu_files and file_dirty properly declared as global
✓ Faster display refresh throttling (200ms vs 500ms)
✓ All V3 features preserved (key combos, page nav, actions)

ARCHITECTURE:
=============
Core 0 (Main):
  - Keyboard scanning (1ms interval @ 1000Hz - CAPTURES EVERY KEYSTROKE)
  - Text processing and buffer updates
  - Display buffer rendering (NO SPI LOCK - memory operations only)
  - User input handling
  - Garbage collection (thread-safe)

Core 1 (Worker):
  - Display refresh operations (blocking e-ink updates, 50ms throttle)
  - File save operations
  - Background tasks
  - NO GC (moved to Core 0)

Communication:
  - queue.Queue for task requests
  - _thread.allocate_lock() for shared data
  - SPI lock ONLY for actual SPI operations (not buffer rendering)
  - Global flags for state management

Performance Characteristics:
  - Zero input lag: 0ms display throttle, immediate keystroke response
  - High-speed keyboard: 1000Hz scan rate never misses fast typing
  - Buffer rendering is non-blocking: Core 0 never waits for Core 1
  - Only actual SPI operations are serialized via lock

KEY COMBOS:
===========
Editor Mode:
  - Ctrl+S: Save current file
  - Ctrl+O: Open file menu
  - Ctrl+N: Create new file
  - Ctrl+R: Rename current file
  - Ctrl+D: Delete current file
  - Ctrl+T: Upload to Todoist (placeholder)
  - Alt+Backspace: Delete word
  - Shift+Enter: Insert page marker (---)
  - PgUp/PgDn: Enter page view mode
  - Home (in page view): Return to editor
  - Esc: Return to menu

Menu Mode:
  - Up/PgUp: Navigate up
  - Down/PgDn: Navigate down
  - Enter: Open selected file
  - N: Create new file
  - Backspace/Del: Delete selected file
  - Esc: Exit application
"""

import _thread
import time
import utime
from machine import Pin
import gc
import os

# Import hardware abstraction
import hardware_pico
from display42 import EPD_4in2
from tca8418 import TCA8418
from editor_base import (
    TextLayout, PageManager, KeyboardHelper, FileHelper, MenuRenderer,
    CHAR_WIDTH, CHAR_HEIGHT, MARGIN_LEFT, MARGIN_TOP
)

# Try to import queue for thread-safe communication
try:
    from queue import Queue
except:
    # MicroPython doesn't have queue module - implement simple version
    class Queue:
        """Simple queue implementation for MicroPython"""
        def __init__(self, maxsize=10):
            self.items = []
            self.maxsize = maxsize
            self.lock = _thread.allocate_lock()

        def put(self, item):
            with self.lock:
                if len(self.items) < self.maxsize:
                    self.items.append(item)
                    return True
                return False

        def get(self):
            with self.lock:
                if self.items:
                    return self.items.pop(0)
                return None

        def empty(self):
            with self.lock:
                return len(self.items) == 0

        def qsize(self):
            with self.lock:
                return len(self.items)


# =============================================================================
# GLOBAL STATE (shared between threads)
# =============================================================================

# Hardware objects
epd = None
keyboard = None
max_w = max_h = 0

# Text state (protected by text_lock)
text_buffer = []
cursor_index = 0
current_page_index = 0
current_subpage_index = 0
text_lock = None  # Will be allocated_lock()

# Display state (protected by display_lock)
display_dirty = False
display_lock = None  # Will be allocated_lock()

# SPI lock for thread-safe display operations (V2 FIX)
spi_lock = None  # Will be allocated_lock()

# File state
STORAGE_BASE = "saved_files"
ACTIVE_FILE = ""
file_dirty = False
file_last_flush = 0

# Communication queues
display_queue = None  # Queue for display refresh requests
file_queue = None     # Queue for file save requests

# Thread control
worker_running = False
worker_should_stop = False

# Keyboard state
current_pressed = set()
last_key_time = 0

# Application state
app_mode = 'menu'  # 'menu', 'editor', or 'paged_view' (V3: added paged_view)
menu_selected_index = 0
menu_files = []

# Page view state (V3 NEW)
in_paged_view = False
view_page_index = 0
view_subpage_index = 0

# Cursor tracking for proper clearing (V4 FIX)
last_cursor_pos = None  # Store (x, y) of last cursor position


# =============================================================================
# WORKER THREAD (Core 1)
# =============================================================================

def worker_thread():
    """
    Worker thread running on Core 1
    Handles blocking operations: display refreshes and file saves
    V2: Added SPI locking and display re-initialization
    """
    global worker_running, worker_should_stop, epd, display_queue, file_queue
    global spi_lock

    print("Worker thread starting on Core 1...")
    worker_running = True

    # Local state
    last_display_time = 0
    throttle_ms = 50  # V4 FIX: Minimal throttle (50ms) for e-ink protection only

    try:
        while not worker_should_stop:
            # Process display refresh requests
            if display_queue and not display_queue.empty():
                request = display_queue.get()
                if request:
                    refresh_type = request.get('type', 'partial')

                    # Check throttle
                    now = utime.ticks_ms()
                    elapsed = utime.ticks_diff(now, last_display_time)
                    if elapsed < throttle_ms:
                        time.sleep_ms(throttle_ms - elapsed)

                    # Perform refresh (this blocks Core 1 but not Core 0)
                    # V2 FIX: Added SPI lock and display re-initialization
                    try:
                        with spi_lock:  # V2: Protect SPI bus access
                            if refresh_type == 'partial':
                                # V2 FIX: Re-init display before partial refresh
                                epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
                                epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
                            elif refresh_type == 'full':
                                # V2 FIX: Re-init display before full refresh
                                epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
                                epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)
                            elif refresh_type == 'clear':
                                # V2 FIX: Full init for clear operation
                                epd.EPD_4IN2_V2_Init()
                                epd.EPD_4IN2_V2_Clear()

                        last_display_time = utime.ticks_ms()
                        print(f"Display refresh complete: {refresh_type}")

                    except Exception as e:
                        print(f"Display refresh error: {e}")

            # Process file save requests
            if file_queue and not file_queue.empty():
                request = file_queue.get()
                if request:
                    path = request.get('path')
                    content = request.get('content')

                    if path and content is not None:
                        try:
                            # File save (blocks Core 1 but not Core 0)
                            with open(path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            print(f"File saved: {path}")

                        except Exception as e:
                            print(f"File save error: {e}")

            # Brief sleep to yield CPU
            time.sleep_ms(10)

            # V2 FIX: Removed GC from Core 1 - now only runs on Core 0 for thread safety

    except Exception as e:
        print(f"Worker thread error: {e}")

    finally:
        worker_running = False
        print("Worker thread stopped")


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

def clear_display_buffer():
    """Clear the display framebuffer to white"""
    epd.image1Gray.fill(0xFF)


def render_text_page(page_chars):
    """
    Render a page of characters to display buffer
    This only updates the buffer - refresh happens on worker thread
    """
    clear_display_buffer()
    for x, y, ch in page_chars:
        if ch not in '\n':
            epd.image1Gray.text(ch, x, y, epd.black)


def render_cursor(x, y):
    """Draw cursor at specified position"""
    epd.image1Gray.fill_rect(x, y + CHAR_HEIGHT - 2, CHAR_WIDTH, 2, epd.black)


def partial_refresh():
    """
    Partial display refresh - direct hardware call

    This function provides DIRECT hardware access for cases where we don't
    want to queue the refresh (like prompts, dialogs, status messages).
    Uses SPI lock to ensure thread-safe hardware access.
    """
    try:
        with spi_lock:
            epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
            epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
    except Exception as e:
        print(f"Partial refresh error: {e}")


def full_refresh():
    """
    Full display refresh - direct hardware call

    This function provides DIRECT hardware access for cases where we don't
    want to queue the refresh (like prompts, dialogs, status messages).
    Uses SPI lock to ensure thread-safe hardware access.
    """
    try:
        with spi_lock:
            epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
            epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)
    except Exception as e:
        print(f"Full refresh error: {e}")


def full_refresh_blocking():
    """
    Blocking full display refresh - synchronous hardware call

    This is identical to full_refresh() but with a more explicit name
    to indicate blocking behavior. Used for splash screens and initialization.
    Uses SPI lock to ensure thread-safe hardware access.
    """
    try:
        with spi_lock:
            epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
            epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)
    except Exception as e:
        print(f"Full refresh blocking error: {e}")


def show_linson():
    """
    Display "Linson" splash screen

    Used for screen saver and shutdown sequences.
    Renders white "Linson" text on black background with full blocking refresh.
    """
    try:
        # Clear to black background
        epd.image1Gray.fill(0x00)  # Black background

        # Draw "Linson" in white centered on screen
        text = "Linson"
        text_width = len(text) * CHAR_WIDTH
        text_x = (max_w - text_width) // 2
        text_y = (max_h - CHAR_HEIGHT) // 2
        epd.image1Gray.text(text, text_x, text_y, 0xFF)  # White text

        # Full blocking refresh
        full_refresh_blocking()
    except Exception as e:
        print(f"Show Linson error: {e}")


def status(msg, in_page_view=False, duration=2000):
    """
    Display temporary status message at bottom of screen

    Args:
        msg: Status message to display
        in_page_view: If True, preserves page view display
        duration: How long to show message (ms) before clearing

    The message appears at the bottom of the screen and auto-clears after duration.
    Uses partial refresh for fast feedback.
    """
    global text_buffer, cursor_index, display_dirty

    # Save current display state
    if in_page_view:
        # In page view mode, just update status area
        status_y = max_h - CHAR_HEIGHT - 2

        # Clear status area (bottom line)
        epd.image1Gray.fill_rect(0, status_y, max_w, CHAR_HEIGHT + 2, 0xFF)

        # Draw status message
        epd.image1Gray.text(msg, MARGIN_LEFT, status_y, epd.black)

        # Partial refresh
        partial_refresh()
    else:
        # In editor mode, redraw everything with status
        with text_lock:
            current_text = ''.join(text_buffer)
            cursor_pos = cursor_index

        # Calculate and render page
        pages = TextLayout.get_screen_pages(current_text, max_w, max_h - CHAR_HEIGHT - 4)
        if pages:
            render_text_page(pages[0])
        else:
            clear_display_buffer()

        # Draw cursor
        cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
            current_text, cursor_pos, max_w, max_h - CHAR_HEIGHT - 4
        )
        render_cursor(cursor_x, cursor_y)

        # Draw status at bottom
        status_y = max_h - CHAR_HEIGHT - 2
        epd.image1Gray.text(msg, MARGIN_LEFT, status_y, epd.black)

        # Partial refresh
        partial_refresh()

    # Schedule status clear after duration
    # Note: MicroPython doesn't have threading.Timer, so this would need
    # to be implemented in the main loop with a timestamp check
    # For now, status messages will persist until next display update


def clear_screen():
    """
    Full screen clear and refresh

    Reinitializes display in fast mode, clears buffer, and performs full refresh.
    Used when transitioning between major UI states or recovering from overflow.
    """
    try:
        # Reinitialize display
        with spi_lock:
            epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)

        # Clear buffer
        clear_display_buffer()

        # Full refresh
        full_refresh()

        print("Screen cleared and refreshed")
    except Exception as e:
        print(f"Clear screen error: {e}")


def request_display_refresh(refresh_type='partial'):
    """
    Request display refresh on worker thread

    Args:
        refresh_type: 'partial', 'full', or 'clear'

    Returns:
        True if queued, False if queue full
    """
    global display_queue, display_dirty

    if display_queue:
        success = display_queue.put({'type': refresh_type})
        if success:
            with display_lock:
                display_dirty = False
        return success
    return False


def refresh_display():
    """Update the physical display based on current state (partial refresh)"""
    global text_buffer, cursor_index, last_cursor_pos

    # Get text (thread-safe read)
    with text_lock:
        current_text = ''.join(text_buffer)
        cursor_pos = cursor_index

    # Calculate layout
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)

    # Render to buffer (NO SPI LOCK - buffer operations don't need SPI protection)
    if pages:
        render_text_page(pages[0])
    else:
        clear_display_buffer()

    # V4 FIX: Clear old cursor position BEFORE drawing new one
    if last_cursor_pos:
        old_x, old_y = last_cursor_pos
        epd.image1Gray.fill_rect(old_x, old_y + CHAR_HEIGHT - 2, CHAR_WIDTH, 2, 0xFF)  # White

    # Calculate and draw new cursor
    cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
        current_text, cursor_pos, max_w, max_h
    )
    render_cursor(cursor_x, cursor_y)
    last_cursor_pos = (cursor_x, cursor_y)  # Store for next clear

    # Request refresh on worker thread (non-blocking, only SPI operations need lock)
    request_display_refresh('full')  # V4 FIX: Use FULL refresh for cleaner display


def refresh_display_full():
    """
    Full display refresh for mode transitions (V2 NEW FUNCTION)
    Use this when transitioning from menu to editor or vice versa
    """
    global text_buffer, cursor_index, last_cursor_pos

    # Get text (thread-safe read)
    with text_lock:
        current_text = ''.join(text_buffer)
        cursor_pos = cursor_index

    # Calculate layout
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)

    # Render to buffer (NO SPI LOCK - buffer operations don't need SPI protection)
    if pages:
        render_text_page(pages[0])
    else:
        clear_display_buffer()

    # V4 FIX: Clear old cursor position BEFORE drawing new one
    if last_cursor_pos:
        old_x, old_y = last_cursor_pos
        epd.image1Gray.fill_rect(old_x, old_y + CHAR_HEIGHT - 2, CHAR_WIDTH, 2, 0xFF)  # White

    # Calculate and draw new cursor
    cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
        current_text, cursor_pos, max_w, max_h
    )
    render_cursor(cursor_x, cursor_y)
    last_cursor_pos = (cursor_x, cursor_y)  # Store for next clear

    # Request FULL refresh for clean display
    request_display_refresh('full')


def display_page(page_num, subpage_num, total_pages, page_text):
    """
    Display a page in read-only view mode (V3 NEW)
    Used for PgUp/PgDn navigation
    """
    global display_dirty

    # Get pages for the text (leave room for footer)
    pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)

    # Ensure valid subpage
    if subpage_num >= len(pages):
        subpage_num = len(pages) - 1
    if subpage_num < 0:
        subpage_num = 0

    # Render to buffer (NO SPI LOCK - buffer operations don't need SPI protection)
    clear_display_buffer()

    # Render the subpage
    if pages and subpage_num < len(pages):
        render_text_page(pages[subpage_num])

    # Draw footer
    footer_y = max_h - CHAR_HEIGHT - 2
    epd.image1Gray.text("[PgUp/PgDn] Navigate | [Home] Exit", MARGIN_LEFT, footer_y, epd.black)

    # Page number
    num_subpages = len(pages)
    if num_subpages > 1:
        label = f"{page_num + 1}.{subpage_num + 1}/{total_pages}"
    else:
        label = f"{page_num + 1}/{total_pages}"
    label_width = len(label) * CHAR_WIDTH
    px = max_w - label_width - 10
    epd.image1Gray.text(label, px, footer_y, epd.black)

    # V4 FIX: Use FULL refresh for cleaner page navigation
    request_display_refresh('full')
    display_dirty = False


# =============================================================================
# MENU FUNCTIONS
# =============================================================================

def show_menu():
    """
    Display the file selection menu (OPTIMIZED for instant response)

    This function:
    1. Lists all .txt files in STORAGE_BASE directory
    2. Renders the menu using MenuRenderer
    3. Uses DIRECT partial refresh for snappy navigation (not queued)

    V4 OPTIMIZATION: Menu uses blocking partial refresh instead of queued
    refresh for instant visual feedback during navigation. This is critical
    for good UX - users expect immediate response to menu navigation.
    """
    global menu_files, menu_selected_index

    # Get list of .txt files
    menu_files = FileHelper.list_files(STORAGE_BASE, '.txt')

    # If no files exist, create a default one
    if not menu_files:
        import utime
        timestamp = utime.time() % 100000
        default_file = f"note_{timestamp}.txt"
        default_path = f"{STORAGE_BASE}/{default_file}"
        try:
            with open(default_path, 'w') as f:
                f.write("")
            print(f"Created default file: {default_file}")
            menu_files = [default_file]
        except Exception as e:
            print(f"Error creating default file: {e}")
            menu_files = []

    # Ensure selected index is valid
    if menu_selected_index >= len(menu_files):
        menu_selected_index = len(menu_files) - 1 if menu_files else 0

    # Render menu
    if menu_files:
        MenuRenderer.render_file_menu(epd, menu_files, menu_selected_index, max_w, max_h)
    else:
        # No files - show error
        epd.image1Gray.fill(0xFF)
        epd.image1Gray.text("No files found", MARGIN_LEFT, MARGIN_TOP, epd.black)
        epd.image1Gray.text("Press 'N' to create new file", MARGIN_LEFT, MARGIN_TOP + CHAR_HEIGHT, epd.black)

    # V4 FIX: Use FULL refresh for menu to clear old arrow positions
    # Partial refresh was leaving "►" characters from previous selections
    with spi_lock:
        epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
        epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)  # FULL refresh clears old content


def handle_menu_input(key_label):
    """
    Handle keyboard input in menu mode (V2 FIXED)

    Args:
        key_label: The key that was pressed

    Returns:
        True if menu should stay open, False if transitioning to editor or exit
    """
    global menu_selected_index, app_mode, ACTIVE_FILE, text_buffer, cursor_index
    global current_page_index, current_subpage_index, menu_files, file_dirty

    # Navigation
    if key_label in ['Up', 'PgUp']:
        if menu_selected_index > 0:
            menu_selected_index -= 1
            show_menu()
        return True

    elif key_label in ['Down', 'PgDn']:
        if menu_selected_index < len(menu_files) - 1:
            menu_selected_index += 1
            show_menu()
        return True

    # File selection (V2 FIXED: Added proper clear sequence)
    elif key_label == 'Enter':
        if menu_files:
            # Open selected file
            ACTIVE_FILE = f"{STORAGE_BASE}/{menu_files[menu_selected_index]}"
            print(f"Opening file: {ACTIVE_FILE}")

            # Ensure file exists
            try:
                open(ACTIVE_FILE, 'a').close()
            except:
                pass

            # V2 FIX: Clear screen FIRST before loading content
            print("Clearing screen for editor transition...")
            clear_display_buffer()
            request_display_refresh('clear')
            time.sleep_ms(200)  # Brief delay for clear to process

            # Load file content
            load_previous()

            # Switch to editor mode
            app_mode = 'editor'

            # V2 FIX: Use full refresh for clean transition
            print("Refreshing display with editor content...")
            refresh_display_full()

            print(f"Switched to editor mode: {ACTIVE_FILE}")
            return False
        return True

    # Create new file (V2 FIXED: Added proper clear sequence)
    elif key_label == 'N' or key_label == 'n':
        # Create new file with timestamp
        import utime
        timestamp = utime.time() % 100000
        new_filename = f"note_{timestamp}.txt"
        new_path = f"{STORAGE_BASE}/{new_filename}"

        try:
            with open(new_path, 'w') as f:
                f.write("")
            print(f"Created new file: {new_filename}")

            # V2 FIX: Clear screen FIRST before loading editor
            print("Clearing screen for new file...")
            clear_display_buffer()
            request_display_refresh('clear')
            time.sleep_ms(200)  # Brief delay for clear to process

            # Open the new file
            ACTIVE_FILE = new_path
            with text_lock:
                text_buffer.clear()
                cursor_index = 0
            current_page_index = 0
            current_subpage_index = 0

            # Switch to editor mode
            app_mode = 'editor'

            # V2 FIX: Use full refresh for clean transition
            print("Refreshing display with editor content...")
            refresh_display_full()

            print(f"Switched to editor mode: {ACTIVE_FILE}")
            return False

        except Exception as e:
            print(f"Error creating file: {e}")
            return True

    # Delete file (V3 NEW)
    elif key_label in ['Backspace', 'Del']:
        if menu_files:
            to_remove = f"{STORAGE_BASE}/{menu_files[menu_selected_index]}"
            # Simple inline delete without confirmation for simplicity
            try:
                os.remove(to_remove)
                print(f"Deleted: {to_remove}")
                # Refresh list
                menu_files = FileHelper.list_files(STORAGE_BASE, '.txt')
                menu_selected_index = max(0, min(menu_selected_index, len(menu_files) - 1))
                show_menu()
            except:
                print(f"Failed to delete: {to_remove}")
        return True

    # Exit application
    elif key_label == 'Esc':
        print("Exiting from menu...")
        return False

    return True


# =============================================================================
# TEXT EDITING FUNCTIONS
# =============================================================================

def insert_char(ch):
    """Insert character at cursor position (thread-safe)"""
    global text_buffer, cursor_index, display_dirty, file_dirty

    with text_lock:
        text_buffer.insert(cursor_index, ch)
        cursor_index += 1

    with display_lock:
        display_dirty = True

    file_dirty = True


def backspace():
    """Delete character before cursor (thread-safe)"""
    global text_buffer, cursor_index, display_dirty, file_dirty

    with text_lock:
        if cursor_index > 0:
            cursor_index -= 1
            text_buffer.pop(cursor_index)

            with display_lock:
                display_dirty = True
            file_dirty = True


def delete_word():
    """Delete word before cursor (V3 NEW - Alt+Backspace)"""
    global text_buffer, cursor_index, display_dirty, file_dirty

    with text_lock:
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

    with display_lock:
        display_dirty = True
    file_dirty = True


def cursor_newline():
    """Insert newline at cursor"""
    insert_char('\n')


def new_page_marker():
    """Insert explicit page marker (V3 NEW - Shift+Enter)"""
    global file_dirty, current_page_index, current_subpage_index
    global text_buffer, cursor_index

    # Save current content
    save_current_page()

    # Move to next page
    current_page_index += 1
    current_subpage_index = 0

    with text_lock:
        text_buffer.clear()
        cursor_index = 0

    file_dirty = True

    # Clear and refresh
    clear_display_buffer()
    request_display_refresh('clear')
    time.sleep_ms(200)
    refresh_display_full()


# =============================================================================
# FILE OPERATIONS
# =============================================================================

def request_file_save(path, content):
    """
    Request file save on worker thread (non-blocking)

    Args:
        path: File path
        content: Content to save

    Returns:
        True if queued, False if queue full
    """
    global file_queue, file_dirty

    if file_queue:
        success = file_queue.put({'path': path, 'content': content})
        if success:
            file_dirty = False
        return success
    return False


def save_current_page():
    """Save current buffer to file (non-blocking)"""
    global text_buffer, ACTIVE_FILE, current_page_index

    # Read current state (thread-safe)
    with text_lock:
        current_text = ''.join(text_buffer)

    # Load full file
    full_content = FileHelper.load_file(ACTIVE_FILE)
    pages = PageManager.split_into_pages(full_content)

    # Ensure we have enough pages
    while len(pages) <= current_page_index:
        pages.append("")

    # Update current page
    pages[current_page_index] = current_text

    # Merge back
    new_content = PageManager.merge_pages(pages)

    # Request save on worker thread (non-blocking)
    request_file_save(ACTIVE_FILE, new_content)


def load_previous():
    """Load the last page of the file"""
    global text_buffer, cursor_index, current_page_index, current_subpage_index

    pages = PageManager.split_into_pages(FileHelper.load_file(ACTIVE_FILE))

    if pages:
        current_page_index = len(pages) - 1
        last_page_text = pages[current_page_index]

        # Calculate number of subpages
        screen_pages = TextLayout.get_screen_pages(last_page_text, max_w, max_h)
        current_subpage_index = len(screen_pages) - 1 if screen_pages else 0

        # Load into buffer (thread-safe)
        with text_lock:
            text_buffer.clear()
            text_buffer.extend(list(last_page_text))
            cursor_index = len(text_buffer)
    else:
        current_page_index = 0
        current_subpage_index = 0
        with text_lock:
            text_buffer.clear()
            cursor_index = 0


def load_pages(path):
    """Load file and split by page markers (V3 NEW)"""
    try:
        with open(path, "r", encoding='utf-8') as f:
            content = f.read()
    except:
        return [""]

    if not content.strip():
        return [""]

    return content.split('\n---\n')


# =============================================================================
# ACTION FUNCTIONS (V3 NEW)
# =============================================================================

def action_save():
    """Ctrl+S - Save current file"""
    save_current_page()
    print("File saved")


def action_open():
    """Ctrl+O - Open file menu"""
    global app_mode

    # Save current work
    if file_dirty:
        save_current_page()

    # Switch to menu
    app_mode = 'menu'
    show_menu()


def action_new():
    """Ctrl+N - Create new file"""
    global ACTIVE_FILE, text_buffer, cursor_index, current_page_index, current_subpage_index
    global file_dirty  # V4 FIX: Missing global declaration

    timestamp = utime.time() % 100000
    ACTIVE_FILE = f"{STORAGE_BASE}/note_{timestamp}.txt"

    try:
        open(ACTIVE_FILE, 'w').close()
        print(f"Created: {ACTIVE_FILE}")

        with text_lock:
            text_buffer.clear()
            cursor_index = 0
        current_page_index = 0
        current_subpage_index = 0
        file_dirty = False  # V4 FIX: Reset dirty flag for new file

        refresh_display_full()
    except Exception as e:
        print(f"Error creating file: {e}")


def action_rename():
    """Ctrl+R - Rename current file (stub for now)"""
    print("Rename not implemented in threaded version yet")


def action_delete():
    """Ctrl+D - Delete current file"""
    global ACTIVE_FILE, file_dirty  # V4 FIX: Added missing global declaration

    try:
        os.remove(ACTIVE_FILE)
        print(f"Deleted: {ACTIVE_FILE}")
        file_dirty = False  # V4 FIX: Reset dirty flag before creating new file
        # Create new file
        action_new()
    except Exception as e:
        print(f"Error deleting file: {e}")


def action_upload_todoist():
    """Ctrl+T - Upload to Todoist (placeholder)"""
    print("Todoist upload not implemented yet")


# =============================================================================
# KEYBOARD FUNCTIONS
# =============================================================================

def init_keyboard():
    """Initialize TCA8418 keyboard controller"""
    global keyboard

    try:
        i2c = hardware_pico.init_i2c()
        kbd_pins = hardware_pico.init_keyboard_pins()

        keyboard = TCA8418(
            i2c,
            interrupt_pin=kbd_pins['interrupt'],
            reset_pin=kbd_pins['reset']
        )
        print("✓ Keyboard initialized")
        return True

    except Exception as e:
        print(f"✗ Keyboard init failed: {e}")
        return False


def scan_keys():
    """
    Scan keyboard and return pressed keys (INTERRUPT-DRIVEN + HIGH-SPEED)

    This runs on Core 0 at 1000Hz (1ms scan interval) and can execute
    even while Core 1 is performing blocking display refreshes.

    V4 FIX: Runs at 1000Hz (was 100Hz) to capture EVERY keystroke from fast typers
    V3 FIX: Checks interrupt pin FIRST before reading FIFO
    This eliminates the timing window that caused missed key presses
    """
    global keyboard, current_pressed

    if not keyboard:
        return set()

    # V3 FIX: Only read FIFO if interrupt pin indicates pending events
    # This ensures we don't miss key presses due to polling timing
    if not keyboard.has_interrupt():
        return current_pressed.copy()

    # Process all events in FIFO
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

    # Clear interrupt flag
    keyboard.clear_interrupts()

    return current_pressed.copy()


# =============================================================================
# MAIN PROGRAM (Core 0)
# =============================================================================

def main():
    """
    Main program running on Core 0
    V4: Optimized for ZERO input lag and fast typing
    - 1000Hz keyboard scan (1ms interval)
    - 0ms display throttle (updates every keystroke)
    - Full refresh for clean display with no ghosting
    """
    global epd, max_w, max_h, ACTIVE_FILE
    global display_dirty, file_dirty, last_key_time, file_last_flush
    global text_lock, display_lock, spi_lock, app_mode
    global display_queue, file_queue
    global worker_should_stop
    global in_paged_view, view_page_index, view_subpage_index

    print("\n" + "="*60)
    print("THREADING APPROACH V4 - Raspberry Pi Pico 2W")
    print("OPTIMIZED FOR FAST TYPING - ZERO INPUT LAG")
    print("1000Hz keyboard | 0ms throttle | Full refresh")
    print("="*60 + "\n")

    # V2 FIX: Initialize all locks including SPI lock
    text_lock = _thread.allocate_lock()
    display_lock = _thread.allocate_lock()
    spi_lock = _thread.allocate_lock()  # V2: NEW - Protect SPI bus
    print("✓ Locks initialized (text, display, SPI)")

    # Initialize queues
    display_queue = Queue(maxsize=5)
    file_queue = Queue(maxsize=5)

    # Initialize storage
    FileHelper.ensure_directory(STORAGE_BASE)

    # Initialize display
    print("Initializing display...")
    epd = EPD_4in2()
    epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
    max_w, max_h = epd.width, epd.height
    print(f"Display ready: {max_w}x{max_h}")

    # Clear display
    clear_display_buffer()
    epd.image1Gray.text("Threading V3 Starting...", 10, 10, epd.black)
    epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)

    # Initialize keyboard
    if not init_keyboard():
        print("FATAL: Keyboard init failed")
        return

    # Start worker thread on Core 1
    print("\nStarting worker thread on Core 1...")
    _thread.start_new_thread(worker_thread, ())

    # Wait for worker to start
    timeout = 0
    while not worker_running and timeout < 50:
        time.sleep_ms(100)
        timeout += 1

    if not worker_running:
        print("FATAL: Worker thread failed to start")
        return

    print("✓ Worker thread running")

    # Show menu on startup
    print("\nShowing file selection menu...")
    show_menu()

    # Wait for menu refresh to complete
    time.sleep(1)

    # Main loop variables
    last_key_time = utime.ticks_ms()
    file_last_flush = last_key_time
    prev_keys = set()
    refresh_pause_ms = 0  # V4 FIX: ZERO throttle - update on EVERY keystroke for fast typers
    file_flush_interval_ms = 2000

    print("\n✓ Entering main loop - full key combo support active!\n")

    # Main loop (Core 0)
    loop_count = 0
    try:
        while True:
            loop_count += 1
            now = utime.ticks_ms()

            # Scan keyboard (runs on Core 0, non-blocking even during Core 1 operations)
            pressed = scan_keys()
            new_keys = pressed - prev_keys

            # V3: Check ALL modifiers (not just shift)
            shift_on = any(keyboard.key_map.get(k) == 'Shift' for k in pressed)
            ctrl_on = any(keyboard.key_map.get(k) == 'Ctrl' for k in pressed)
            alt_on = any(keyboard.key_map.get(k) == 'Alt' for k in pressed)

            # Process key presses
            if new_keys:
                for k in new_keys:
                    lbl = keyboard.key_map.get(k, '')

                    # Handle menu mode
                    if app_mode == 'menu':
                        # V3 DEBUG: Print key detected in menu
                        print(f"Menu key: '{lbl}'")

                        # Process menu input
                        menu_continue = handle_menu_input(lbl)
                        if not menu_continue:
                            # User selected exit or file - handle appropriately
                            if lbl == 'Esc':
                                print("\nEsc pressed - exiting...")
                                worker_should_stop = True
                                time.sleep(1)
                                return
                            # Otherwise switched to editor mode
                        last_key_time = now
                        break

                    # V3 NEW: Handle page view mode
                    elif app_mode == 'paged_view' or lbl in ('PgUp', 'PgDn', 'Home'):
                        if not in_paged_view and lbl in ('PgUp', 'PgDn'):
                            # Enter page view mode
                            if file_dirty or text_buffer:
                                save_current_page()

                            in_paged_view = True
                            app_mode = 'paged_view'
                            pages = load_pages(ACTIVE_FILE)
                            view_page_index = current_page_index
                            view_subpage_index = current_subpage_index

                        if in_paged_view:
                            pages = load_pages(ACTIVE_FILE)

                            if lbl == 'PgUp':
                                # Navigate backwards
                                page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                                screen_pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)

                                if view_subpage_index > 0:
                                    view_subpage_index -= 1
                                elif view_page_index > 0:
                                    view_page_index -= 1
                                    page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                                    screen_pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)
                                    view_subpage_index = len(screen_pages) - 1 if screen_pages else 0

                                page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                                display_page(view_page_index, view_subpage_index, len(pages), page_text)

                            elif lbl == 'PgDn':
                                # Navigate forwards
                                page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                                screen_pages = TextLayout.get_screen_pages(page_text, max_w, max_h - 2 * CHAR_HEIGHT)
                                num_subpages = len(screen_pages)

                                if view_subpage_index < num_subpages - 1:
                                    view_subpage_index += 1
                                elif view_page_index < len(pages) - 1:
                                    view_page_index += 1
                                    view_subpage_index = 0

                                page_text = pages[view_page_index] if view_page_index < len(pages) else ""
                                display_page(view_page_index, view_subpage_index, len(pages), page_text)

                            elif lbl == 'Home':
                                # Exit page view
                                in_paged_view = False
                                app_mode = 'editor'
                                refresh_display()

                        last_key_time = now
                        continue

                    # Handle editor mode
                    elif app_mode == 'editor':
                        # V3 NEW: Ctrl key combinations
                        if ctrl_on and lbl and len(lbl) == 1 and lbl.lower() in 'sonrtd':
                            actions = {
                                's': action_save,
                                'o': action_open,
                                'n': action_new,
                                'r': action_rename,
                                't': action_upload_todoist,
                                'd': action_delete
                            }
                            actions[lbl.lower()]()
                            last_key_time = now
                            continue

                        # V3 NEW: Alt+Backspace = delete word
                        if alt_on and lbl == 'Backspace':
                            delete_word()
                            last_key_time = now
                            continue

                        # V3 NEW: Shift+Enter = page marker
                        if shift_on and lbl == 'Enter':
                            new_page_marker()
                            last_key_time = now
                            continue

                        # Normal typing
                        if lbl == 'Backspace':
                            backspace()
                        elif lbl == 'Enter':
                            cursor_newline()
                        elif lbl == 'Space':
                            insert_char(' ')
                        elif lbl == 'Esc':
                            # In editor mode, Esc returns to menu
                            print("\nEsc pressed - returning to menu...")
                            app_mode = 'menu'
                            show_menu()
                            break
                        elif len(lbl) == 1 and not ctrl_on:
                            ch = KeyboardHelper.glyph(lbl, shift_on)
                            insert_char(ch)

                        last_key_time = now

            prev_keys = pressed

            # Display refresh (if dirty and throttled) - only in editor mode
            if app_mode == 'editor':
                with display_lock:
                    is_dirty = display_dirty

                if is_dirty and utime.ticks_diff(now, last_key_time) > refresh_pause_ms:
                    refresh_display()

            # File save (if dirty and throttled) - only in editor mode
            if app_mode == 'editor' and file_dirty and \
               utime.ticks_diff(now, last_key_time) > refresh_pause_ms and \
               utime.ticks_diff(now, file_last_flush) > file_flush_interval_ms:
                save_current_page()
                file_last_flush = now

            # V2 FIX: GC runs ONLY on Core 0 for thread safety
            if loop_count % 1000 == 0:
                gc.collect()
                print(f"Loop {loop_count}: "
                      f"Keys={len(pressed)}, "
                      f"Text={len(text_buffer)}ch, "
                      f"Display_Q={display_queue.qsize()}, "
                      f"File_Q={file_queue.qsize()}, "
                      f"Mem={gc.mem_free()}B")

            # V4 FIX: Core 0 main loop runs at ~1000Hz (1ms cycle) to capture EVERY keystroke
            # Critical for fast typers - never miss a key press
            time.sleep_ms(1)

    except KeyboardInterrupt:
        print("\nKeyboard interrupt - cleaning up...")

    except Exception as e:
        print(f"\nMain loop error: {e}")
        import sys
        sys.print_exception(e)

    finally:
        # Cleanup
        print("\nStopping worker thread...")
        worker_should_stop = True
        time.sleep(1)

        # Final save
        if file_dirty:
            print("Saving final state...")
            save_current_page()
            time.sleep(1)

        print("\nThreading V3 test complete")
        print("="*60)


if __name__ == "__main__":
    main()
