"""
main_threaded_v2.py - Fixed dual-core threading approach for Pico 2W
Version 2: Fixes screen refresh issues and menu-to-editor transitions

FIXES IN V2:
============
1. Added SPI lock for thread-safe display operations
2. Added display re-initialization before partial/full refreshes
3. Created refresh_display_full() for clean mode transitions
4. Fixed menu-to-editor transition with proper clear sequence
5. Fixed new file creation transition
6. Moved GC to Core 0 only (thread-safe)

ARCHITECTURE:
=============
Core 0 (Main):
  - Keyboard scanning (10ms interval)
  - Text processing and buffer updates
  - Display buffer rendering
  - User input handling
  - Garbage collection (thread-safe)

Core 1 (Worker):
  - Display refresh operations (blocking e-ink updates)
  - File save operations
  - Background tasks
  - NO GC (moved to Core 0)

Communication:
  - queue.Queue for task requests
  - _thread.allocate_lock() for shared data
  - SPI lock for display operations
  - Global flags for state management

EXPECTED BEHAVIOR:
==================
✓ Display updates don't block keyboard input
✓ File saves don't block UI
✓ Clean screen transitions between menu and editor
✓ Thread-safe display operations with SPI lock
✓ Proper display initialization before refreshes
"""

import _thread
import time
import utime
from machine import Pin
import gc

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
app_mode = 'menu'  # 'menu' or 'editor'
menu_selected_index = 0
menu_files = []


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
    throttle_ms = 500

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
    global text_buffer, cursor_index

    # Get text (thread-safe read)
    with text_lock:
        current_text = ''.join(text_buffer)
        cursor_pos = cursor_index

    # Calculate layout
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)

    # Render to buffer
    if pages:
        render_text_page(pages[0])
    else:
        clear_display_buffer()

    # Add cursor
    cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
        current_text, cursor_pos, max_w, max_h
    )
    render_cursor(cursor_x, cursor_y)

    # Request refresh on worker thread (non-blocking)
    request_display_refresh('partial')


def refresh_display_full():
    """
    Full display refresh for mode transitions (V2 NEW FUNCTION)
    Use this when transitioning from menu to editor or vice versa
    """
    global text_buffer, cursor_index

    # Get text (thread-safe read)
    with text_lock:
        current_text = ''.join(text_buffer)
        cursor_pos = cursor_index

    # Calculate layout
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)

    # Render to buffer
    if pages:
        render_text_page(pages[0])
    else:
        clear_display_buffer()

    # Add cursor
    cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
        current_text, cursor_pos, max_w, max_h
    )
    render_cursor(cursor_x, cursor_y)

    # Request FULL refresh for clean display
    request_display_refresh('full')


# =============================================================================
# MENU FUNCTIONS
# =============================================================================

def show_menu():
    """
    Display the file selection menu (sync version for threading)

    This function:
    1. Lists all .txt files in STORAGE_BASE directory
    2. Renders the menu using MenuRenderer
    3. Requests full display refresh via worker thread
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

    # Request full refresh via worker thread
    request_display_refresh('full')


def handle_menu_input(key_label):
    """
    Handle keyboard input in menu mode (V2 FIXED)

    Args:
        key_label: The key that was pressed

    Returns:
        True if menu should stay open, False if transitioning to editor or exit
    """
    global menu_selected_index, app_mode, ACTIVE_FILE, text_buffer, cursor_index
    global current_page_index, current_subpage_index

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


def cursor_newline():
    """Insert newline at cursor"""
    insert_char('\n')


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
    Scan keyboard and return pressed keys

    This runs on Core 0 and can execute even while Core 1 is
    performing blocking display refreshes.
    """
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


# =============================================================================
# MAIN PROGRAM (Core 0)
# =============================================================================

def main():
    """Main program running on Core 0 (V2 FIXED)"""
    global epd, max_w, max_h, ACTIVE_FILE
    global display_dirty, file_dirty, last_key_time, file_last_flush
    global text_lock, display_lock, spi_lock, app_mode
    global display_queue, file_queue
    global worker_should_stop

    print("\n" + "="*60)
    print("THREADING APPROACH V2 - Raspberry Pi Pico 2W")
    print("Fixed dual-core with proper screen transitions")
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
    epd.image1Gray.text("Threading V2 Starting...", 10, 10, epd.black)
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
    refresh_pause_ms = 500
    file_flush_interval_ms = 2000

    print("\n✓ Entering main loop - press keys to test threading")
    print("  Watch for keyboard responsiveness during display updates!\n")

    # Main loop (Core 0)
    loop_count = 0
    try:
        while True:
            loop_count += 1
            now = utime.ticks_ms()

            # Scan keyboard (runs on Core 0, non-blocking even during Core 1 operations)
            pressed = scan_keys()
            new_keys = pressed - prev_keys

            # Check modifiers
            shift_on = any(keyboard.key_map.get(k) == 'Shift' for k in pressed)

            # Process key presses
            if new_keys:
                for k in new_keys:
                    lbl = keyboard.key_map.get(k, '')

                    # Handle menu mode
                    if app_mode == 'menu':
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

                    # Handle editor mode
                    elif app_mode == 'editor':
                        # Handle typing
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
                        elif len(lbl) == 1:
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

            # Core 0 main loop runs at ~100Hz (10ms cycle)
            time.sleep_ms(10)

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

        print("\nThreading V2 test complete")
        print("="*60)


if __name__ == "__main__":
    main()


"""
THREADING APPROACH V2 CHANGELOG:
=================================

VERSION 2 FIXES:
----------------
✓ Added SPI lock for thread-safe display operations
✓ Added display re-initialization before partial/full refreshes
✓ Created refresh_display_full() for clean mode transitions
✓ Fixed menu-to-editor transition with proper clear sequence
✓ Fixed new file creation transition with proper clear sequence
✓ Moved GC to Core 0 only for thread safety
✓ Added debug output for transition tracking

EXPECTED IMPROVEMENTS:
----------------------
✓ Clean screen transitions (no menu artifacts in editor)
✓ Reliable display refreshes (no blank screens)
✓ Thread-safe SPI operations (no display corruption)
✓ Stable memory management (GC on Core 0 only)
✓ Continued non-blocking keyboard input during refreshes

TESTING CHECKLIST:
------------------
[ ] Menu displays correctly on startup
[ ] Pressing Enter clears screen before showing editor
[ ] Editor content displays cleanly without menu artifacts
[ ] Typing during screen refresh continues to work
[ ] Screen updates show all captured keystrokes
[ ] Creating new file (N key) shows clean transition
[ ] Returning to menu (Esc) works correctly
[ ] No crashes or display corruption during extended use
[ ] Memory remains stable over time

TEST RESULTS:
=============
[To be filled during testing]

Screen transition quality: ___/10
Keyboard responsiveness: ___/10
Display update quality: ___/10
File save reliability: ___/10
Memory stability: ___/10
Overall rating: ___/10

Notes:
______________________________________________________________________
______________________________________________________________________
______________________________________________________________________
"""
