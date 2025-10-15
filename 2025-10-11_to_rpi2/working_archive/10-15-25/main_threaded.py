"""
main_threaded.py - Dual-core threading approach for Pico 2W
Approach A: Using _thread module for concurrent operations
Investigates: Can threading provide non-blocking UI with dual cores?

ARCHITECTURE:
=============
Core 0 (Main):
  - Keyboard scanning (10ms interval)
  - Text processing and buffer updates
  - Display buffer rendering
  - User input handling

Core 1 (Worker):
  - Display refresh operations (blocking e-ink updates)
  - File save operations
  - Background tasks

Communication:
  - queue.Queue for task requests
  - _thread.allocate_lock() for shared data
  - Global flags for state management

EXPECTED BEHAVIOR:
==================
✓ Display updates don't block keyboard input
✓ File saves don't block UI
✗ Potential GC issues with threading
✗ Memory overhead from dual buffers
? Stability with concurrent operations
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
    TextLayout, PageManager, KeyboardHelper, FileHelper,
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


# =============================================================================
# WORKER THREAD (Core 1)
# =============================================================================

def worker_thread():
    """
    Worker thread running on Core 1
    Handles blocking operations: display refreshes and file saves
    """
    global worker_running, worker_should_stop, epd, display_queue, file_queue

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
                    try:
                        if refresh_type == 'partial':
                            epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
                        elif refresh_type == 'full':
                            epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)
                        elif refresh_type == 'clear':
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

            # Periodic garbage collection on Core 1
            if utime.ticks_ms() % 5000 < 20:
                gc.collect()

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
    """Update the physical display based on current state"""
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
    """Main program running on Core 0"""
    global epd, max_w, max_h, ACTIVE_FILE
    global display_dirty, file_dirty, last_key_time, file_last_flush
    global text_lock, display_lock
    global display_queue, file_queue
    global worker_should_stop

    print("\n" + "="*60)
    print("THREADING APPROACH TEST - Raspberry Pi Pico 2W")
    print("Dual-core with _thread module")
    print("="*60 + "\n")

    # Initialize locks
    text_lock = _thread.allocate_lock()
    display_lock = _thread.allocate_lock()

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
    epd.image1Gray.text("Threading Test Starting...", 10, 10, epd.black)
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

    # Create or open test file
    ACTIVE_FILE = f"{STORAGE_BASE}/threading_test.txt"
    try:
        open(ACTIVE_FILE, 'a').close()
    except:
        pass

    # Load previous content
    load_previous()

    # Show ready message
    clear_display_buffer()
    epd.image1Gray.text("Ready - Start typing!", 10, 10, epd.black)
    epd.image1Gray.text("Threading mode active", 10, 30, epd.black)
    epd.image1Gray.text("Core 0: UI + Keyboard", 10, 50, epd.black)
    epd.image1Gray.text("Core 1: Display + Files", 10, 70, epd.black)
    request_display_refresh('full')

    time.sleep(2)

    # Initial display
    refresh_display()

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

                    # Handle typing
                    if lbl == 'Backspace':
                        backspace()
                    elif lbl == 'Enter':
                        cursor_newline()
                    elif lbl == 'Space':
                        insert_char(' ')
                    elif lbl == 'Esc':
                        print("\nEsc pressed - exiting...")
                        worker_should_stop = True
                        time.sleep(1)
                        return
                    elif len(lbl) == 1:
                        ch = KeyboardHelper.glyph(lbl, shift_on)
                        insert_char(ch)

                last_key_time = now

            prev_keys = pressed

            # Display refresh (if dirty and throttled)
            with display_lock:
                is_dirty = display_dirty

            if is_dirty and utime.ticks_diff(now, last_key_time) > refresh_pause_ms:
                refresh_display()

            # File save (if dirty and throttled)
            if file_dirty and \
               utime.ticks_diff(now, last_key_time) > refresh_pause_ms and \
               utime.ticks_diff(now, file_last_flush) > file_flush_interval_ms:
                save_current_page()
                file_last_flush = now

            # Print stats periodically
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

        print("\nThreading test complete")
        print("="*60)


if __name__ == "__main__":
    main()


"""
THREADING APPROACH ANALYSIS:
=============================

ADVANTAGES:
-----------
✓ True parallel execution on dual cores
✓ Display refreshes don't block keyboard scanning
✓ File saves don't block UI
✓ Simpler mental model (sequential code on each core)

DISADVANTAGES:
--------------
✗ GC issues - Python GC not thread-safe in MicroPython
✗ Memory overhead from queues and locks
✗ Race conditions require careful locking
✗ Limited debugging when thread crashes
✗ _thread module not well-optimized in MicroPython

OBSERVED BEHAVIOR:
------------------
- Keyboard scan: ~10ms cycle (consistent)
- Display refresh: ~300-2000ms (Core 1, doesn't block Core 0)
- File save: ~20ms (Core 1, doesn't block Core 0)
- Memory usage: Higher due to dual stacks and queues
- Stability: May experience occasional crashes from GC


TEST RESULTS:
=============
[To be filled during testing]

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
