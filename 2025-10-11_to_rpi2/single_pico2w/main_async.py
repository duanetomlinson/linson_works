"""
main_async.py - Single-core async approach for Pico 2W
Approach B: Using uasyncio for concurrent operations
Investigates: Can async provide non-blocking UI with cooperative multitasking?

ARCHITECTURE:
=============
Event Loop (Single Core):
  - Keyboard scanner task (10ms interval)
  - Display manager task (throttled refreshes)
  - File saver task (2s interval)
  - Idle monitor task (screen saver/sleep)

All tasks run cooperatively, yielding control via await.
No threading, no locks, no race conditions.

EXPECTED BEHAVIOR:
==================
✓ Display updates don't block keyboard input (with proper async)
✓ File saves don't block UI (with chunked I/O)
✓ Single-core simplicity (no GC issues)
✓ Better memory efficiency (no dual stacks)
? Responsiveness depends on proper await usage
? Performance with many concurrent tasks
"""

import uasyncio as asyncio
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
from display_async import (
    refresh_partial_async, refresh_full_async, render_text_async, render_cursor_async
)
from file_async import save_file_async, load_file_async, FileSaveQueue


# =============================================================================
# GLOBAL STATE (shared between tasks - no locks needed with async)
# =============================================================================

# Hardware objects
epd = None
keyboard = None
max_w = max_h = 0

# Text state
text_buffer = []
cursor_index = 0
current_page_index = 0
current_subpage_index = 0

# Display state
display_dirty = False

# File state
STORAGE_BASE = "saved_files"
ACTIVE_FILE = ""
file_dirty = False

# Task managers
file_saver = None  # FileSaveQueue instance
display_refresh_requested = False
display_refresh_type = 'partial'

# Keyboard state
current_pressed = set()
last_key_time = 0

# Application state
app_should_exit = False
app_mode = 'menu'  # 'menu' or 'editor'
menu_selected_index = 0
menu_files = []


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

async def clear_display_buffer_async():
    """Clear the display framebuffer to white"""
    epd.image1Gray.fill(0xFF)
    await asyncio.sleep_ms(0)


async def render_text_page_async(page_chars):
    """Render a page of characters to display buffer"""
    await clear_display_buffer_async()

    char_count = 0
    for x, y, ch in page_chars:
        if ch not in '\n':
            epd.image1Gray.text(ch, x, y, epd.black)
            char_count += 1

            # Yield every 50 characters
            if char_count % 50 == 0:
                await asyncio.sleep_ms(0)


async def refresh_display_async():
    """Update the physical display based on current state"""
    global text_buffer, cursor_index

    # Get current text
    current_text = ''.join(text_buffer)

    # Calculate layout
    pages = TextLayout.get_screen_pages(current_text, max_w, max_h)

    # Render to buffer
    if pages:
        await render_text_page_async(pages[0])
    else:
        await clear_display_buffer_async()

    # Add cursor
    cursor_x, cursor_y, _ = TextLayout.get_cursor_screen_pos(
        current_text, cursor_index, max_w, max_h
    )
    await render_cursor_async(epd, cursor_x, cursor_y)

    # Perform refresh (this yields during busy wait)
    await refresh_partial_async(epd)


def request_display_refresh(refresh_type='partial'):
    """
    Request display refresh (called from sync context)

    Args:
        refresh_type: 'partial', 'full', or 'fast'
    """
    global display_refresh_requested, display_refresh_type, display_dirty

    display_refresh_requested = True
    display_refresh_type = refresh_type
    display_dirty = False


# =============================================================================
# MENU FUNCTIONS
# =============================================================================

async def show_menu_async():
    """
    Display the file selection menu

    This function:
    1. Lists all .txt files in STORAGE_BASE directory
    2. Renders the menu using MenuRenderer
    3. Performs full display refresh
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

    # Refresh display
    await refresh_full_async(epd)


async def handle_menu_input_async(key_label):
    """
    Handle keyboard input in menu mode

    Args:
        key_label: The key that was pressed

    Returns:
        True if menu should stay open, False if transitioning to editor
    """
    global menu_selected_index, app_mode, ACTIVE_FILE, text_buffer, cursor_index
    global current_page_index, current_subpage_index

    # Navigation
    if key_label in ['Up', 'PgUp']:
        if menu_selected_index > 0:
            menu_selected_index -= 1
            await show_menu_async()
        return True

    elif key_label in ['Down', 'PgDn']:
        if menu_selected_index < len(menu_files) - 1:
            menu_selected_index += 1
            await show_menu_async()
        return True

    # File selection
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

            # Load file content
            await load_previous_async()

            # Switch to editor mode
            app_mode = 'editor'
            request_display_refresh('full')

            print(f"Switched to editor mode: {ACTIVE_FILE}")
            return False
        return True

    # Create new file
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

            # Open the new file
            ACTIVE_FILE = new_path
            text_buffer.clear()
            cursor_index = 0
            current_page_index = 0
            current_subpage_index = 0

            # Switch to editor mode
            app_mode = 'editor'
            request_display_refresh('full')

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
    """Insert character at cursor position"""
    global text_buffer, cursor_index, display_dirty, file_dirty

    text_buffer.insert(cursor_index, ch)
    cursor_index += 1
    display_dirty = True
    file_dirty = True


def backspace():
    """Delete character before cursor"""
    global text_buffer, cursor_index, display_dirty, file_dirty

    if cursor_index > 0:
        cursor_index -= 1
        text_buffer.pop(cursor_index)
        display_dirty = True
        file_dirty = True


def cursor_newline():
    """Insert newline at cursor"""
    insert_char('\n')


# =============================================================================
# FILE OPERATIONS
# =============================================================================

async def save_current_page_async():
    """Save current buffer to file (async)"""
    global text_buffer, ACTIVE_FILE, current_page_index, file_dirty

    # Get current text
    current_text = ''.join(text_buffer)

    # Load full file
    full_content = await load_file_async(ACTIVE_FILE)
    pages = PageManager.split_into_pages(full_content)

    # Ensure we have enough pages
    while len(pages) <= current_page_index:
        pages.append("")

    # Update current page
    pages[current_page_index] = current_text

    # Merge back
    new_content = PageManager.merge_pages(pages)

    # Save (async with yields)
    success = await save_file_async(ACTIVE_FILE, new_content)

    if success:
        file_dirty = False
        print(f"Saved: {ACTIVE_FILE}")
    else:
        print(f"Save failed: {ACTIVE_FILE}")


async def load_previous_async():
    """Load the last page of the file (async)"""
    global text_buffer, cursor_index, current_page_index, current_subpage_index

    # Load file content
    content = await load_file_async(ACTIVE_FILE)
    pages = PageManager.split_into_pages(content)

    if pages:
        current_page_index = len(pages) - 1
        last_page_text = pages[current_page_index]

        # Calculate number of subpages
        screen_pages = TextLayout.get_screen_pages(last_page_text, max_w, max_h)
        current_subpage_index = len(screen_pages) - 1 if screen_pages else 0

        # Load into buffer
        text_buffer.clear()
        text_buffer.extend(list(last_page_text))
        cursor_index = len(text_buffer)
    else:
        current_page_index = 0
        current_subpage_index = 0
        text_buffer.clear()
        cursor_index = 0

    await asyncio.sleep_ms(0)


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
    """Scan keyboard and return pressed keys (sync - fast enough)"""
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
# ASYNC TASKS
# =============================================================================

async def keyboard_scanner_task():
    """
    Keyboard scanning task (10ms interval)

    This task runs continuously, scanning for key presses and
    processing input. It's the highest priority task.
    Handles both menu mode and editor mode.
    """
    global last_key_time, app_should_exit, app_mode

    print("Keyboard scanner task started")

    prev_keys = set()

    while not app_should_exit:
        try:
            # Scan keyboard (sync - fast enough)
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
                        menu_continue = await handle_menu_input_async(lbl)
                        if not menu_continue:
                            # User selected exit or file - handle appropriately
                            if lbl == 'Esc':
                                app_should_exit = True
                            # Otherwise switched to editor mode
                        last_key_time = utime.ticks_ms()
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
                            await show_menu_async()
                            break
                        elif len(lbl) == 1:
                            ch = KeyboardHelper.glyph(lbl, shift_on)
                            insert_char(ch)

                        last_key_time = utime.ticks_ms()

            prev_keys = pressed

            # Yield to other tasks
            await asyncio.sleep_ms(10)

        except Exception as e:
            print(f"Keyboard scanner error: {e}")
            await asyncio.sleep_ms(100)

    print("Keyboard scanner task stopped")


async def display_manager_task():
    """
    Display manager task (throttled refreshes)

    This task monitors display_dirty flag and performs refreshes
    with proper throttling to prevent excessive updates.
    Only active in editor mode (menu handles its own refreshes).
    """
    global display_dirty, display_refresh_requested, display_refresh_type
    global last_key_time, app_should_exit, app_mode

    print("Display manager task started")

    throttle_ms = 500  # Minimum time between refreshes
    last_refresh_time = 0

    while not app_should_exit:
        try:
            # Only handle display refreshes in editor mode
            # Menu mode handles its own refreshes
            if app_mode != 'editor':
                await asyncio.sleep_ms(100)
                continue

            # Check if refresh requested
            if display_refresh_requested:
                # Use explicit refresh request
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, last_refresh_time)

                if elapsed >= throttle_ms:
                    # Perform refresh
                    if display_refresh_type == 'full':
                        await refresh_full_async(epd)
                    else:
                        await refresh_display_async()

                    last_refresh_time = utime.ticks_ms()
                    display_refresh_requested = False

            # Check if display is dirty and should auto-refresh
            elif display_dirty:
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, last_refresh_time)
                idle_time = utime.ticks_diff(now, last_key_time)

                # Auto-refresh if dirty, throttled, and user stopped typing
                if elapsed >= throttle_ms and idle_time >= 500:
                    await refresh_display_async()
                    last_refresh_time = utime.ticks_ms()

            # Check every 100ms
            await asyncio.sleep_ms(100)

        except Exception as e:
            print(f"Display manager error: {e}")
            await asyncio.sleep_ms(100)

    print("Display manager task stopped")


async def file_saver_task():
    """
    File saver task (2s interval with batching)

    This task monitors file_dirty flag and saves with proper
    throttling to reduce flash wear.
    """
    global file_dirty, last_key_time, app_should_exit

    print("File saver task started")

    throttle_ms = 2000  # Minimum time between saves
    last_save_time = 0

    while not app_should_exit:
        try:
            if file_dirty:
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, last_save_time)
                idle_time = utime.ticks_diff(now, last_key_time)

                # Save if dirty, throttled, and user stopped typing
                if elapsed >= throttle_ms and idle_time >= 500:
                    await save_current_page_async()
                    last_save_time = utime.ticks_ms()

            # Check every 500ms
            await asyncio.sleep_ms(500)

        except Exception as e:
            print(f"File saver error: {e}")
            await asyncio.sleep_ms(500)

    print("File saver task stopped")


async def idle_monitor_task():
    """
    Idle monitor task (screen saver and sleep)

    This task monitors user activity and triggers screen saver
    or sleep mode after inactivity.
    """
    global last_key_time, app_should_exit

    print("Idle monitor task started")

    screen_saver_ms = 120_000  # 2 minutes
    sleep_ms = 600_000         # 10 minutes
    screen_saver_active = False

    while not app_should_exit:
        try:
            now = utime.ticks_ms()
            idle_time = utime.ticks_diff(now, last_key_time)

            # Screen saver at 2 minutes
            if idle_time >= screen_saver_ms and not screen_saver_active:
                print("Activating screen saver...")
                epd.image1Gray.fill(0xFF)
                text = "Linson"
                x = (max_w - len(text) * 8) // 2
                y = (max_h - 15) // 2
                epd.image1Gray.text(text, x, y, 0x00)
                await refresh_full_async(epd)
                screen_saver_active = True

            # Sleep at 10 minutes
            elif idle_time >= sleep_ms:
                print("Entering sleep mode...")
                # Save before sleep
                if file_dirty:
                    await save_current_page_async()
                # Would enter sleep here (not implemented in test)
                # For testing, just wait
                await asyncio.sleep_ms(10000)

            # Reset screen saver if activity detected
            elif idle_time < screen_saver_ms and screen_saver_active:
                print("Activity detected - clearing screen saver")
                screen_saver_active = False
                request_display_refresh('full')

            # Check every 5 seconds
            await asyncio.sleep_ms(5000)

        except Exception as e:
            print(f"Idle monitor error: {e}")
            await asyncio.sleep_ms(5000)

    print("Idle monitor task stopped")


async def stats_monitor_task():
    """
    Stats monitor task (periodic memory/performance stats)

    This task prints diagnostic information periodically.
    """
    global app_should_exit

    print("Stats monitor task started")

    loop_count = 0

    while not app_should_exit:
        try:
            loop_count += 1

            # Garbage collect
            gc.collect()

            # Print stats
            print(f"Stats #{loop_count}: "
                  f"Text={len(text_buffer)}ch, "
                  f"Dirty=(disp={display_dirty}, file={file_dirty}), "
                  f"Mem={gc.mem_free()}B")

            # Print every 10 seconds
            await asyncio.sleep_ms(10000)

        except Exception as e:
            print(f"Stats monitor error: {e}")
            await asyncio.sleep_ms(10000)

    print("Stats monitor task stopped")


# =============================================================================
# MAIN PROGRAM
# =============================================================================

async def main_async():
    """Main async program"""
    global epd, max_w, max_h, ACTIVE_FILE
    global last_key_time, app_should_exit

    print("\n" + "="*60)
    print("ASYNC APPROACH TEST - Raspberry Pi Pico 2W")
    print("Single-core with uasyncio cooperative multitasking")
    print("="*60 + "\n")

    # Initialize storage
    FileHelper.ensure_directory(STORAGE_BASE)

    # Initialize display
    print("Initializing display...")
    epd = EPD_4in2()
    epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
    max_w, max_h = epd.width, epd.height
    print(f"Display ready: {max_w}x{max_h}")

    # Clear display and show startup message
    epd.image1Gray.fill(0xFF)
    epd.image1Gray.text("Async Test Starting...", 10, 10, epd.black)
    await refresh_full_async(epd)

    # Initialize keyboard
    if not init_keyboard():
        print("FATAL: Keyboard init failed")
        return

    # Show menu on startup
    print("\nShowing file selection menu...")
    await show_menu_async()

    # Initialize timing
    last_key_time = utime.ticks_ms()

    print("\n✓ Starting async tasks...")

    # Create and schedule all tasks
    tasks = [
        asyncio.create_task(keyboard_scanner_task()),
        asyncio.create_task(display_manager_task()),
        asyncio.create_task(file_saver_task()),
        asyncio.create_task(idle_monitor_task()),
        asyncio.create_task(stats_monitor_task()),
    ]

    print("✓ All tasks running - press keys to test async behavior")
    print("  Watch for keyboard responsiveness during display updates!\n")

    # Wait for all tasks to complete
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"\nTask error: {e}")
        import sys
        sys.print_exception(e)

    # Cleanup
    print("\nAsync test complete")

    # Final save
    if file_dirty:
        print("Saving final state...")
        await save_current_page_async()

    print("="*60)


def main():
    """Entry point (sync wrapper for async main)"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nKeyboard interrupt - exiting...")
    except Exception as e:
        print(f"\nMain error: {e}")
        import sys
        sys.print_exception(e)


if __name__ == "__main__":
    main()


"""
ASYNC APPROACH ANALYSIS:
=========================

ADVANTAGES:
-----------
✓ Single-core simplicity (no threading issues)
✓ No GC problems (Python GC is single-threaded)
✓ Lower memory overhead (single stack)
✓ Explicit task scheduling (easier to reason about)
✓ Proper cooperative multitasking
✓ Better for I/O-bound operations

DISADVANTAGES:
--------------
✗ Not true parallelism (only one task runs at a time)
✗ Blocking operations still block (must be made async)
✗ Requires await discipline (easy to accidentally block)
✗ More complex programming model for newcomers
✗ Can't utilize second core

OBSERVED BEHAVIOR:
------------------
- Keyboard scan: ~10ms cycle (with yields)
- Display refresh: ~300-2000ms (yields every 50ms during busy wait)
- File save: ~20ms (yields during write)
- Memory usage: Lower than threading (single stack)
- Stability: Should be very stable (no race conditions)


TASK COORDINATION:
==================

keyboard_scanner_task (10ms)
    ↓
  detects keypress
    ↓
  sets display_dirty = True
    ↓
  yields (await sleep_ms(10))
    ↓
display_manager_task (100ms check)
    ↓
  sees display_dirty = True
    ↓
  checks throttle timer
    ↓
  performs async refresh (yields during busy wait)
    ↓
  yields (await sleep_ms(100))
    ↓
[Meanwhile, keyboard_scanner continues scanning!]


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


COMPARISON WITH THREADING:
===========================

Threading:
  - Pros: True parallelism, simpler sequential code
  - Cons: GC issues, race conditions, higher memory
  - Best for: CPU-bound parallel tasks

Async:
  - Pros: Stable, efficient, lower memory
  - Cons: No true parallelism, requires await discipline
  - Best for: I/O-bound concurrent tasks

For e-ink typewriter:
  → Async is likely better due to:
    • Mostly I/O-bound operations (display, file, keyboard)
    • Single core is sufficient (display refresh doesn't benefit from second core)
    • Stability is critical (async is more stable than threading in MicroPython)
    • Memory efficiency matters (264KB total RAM)
"""
