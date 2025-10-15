# main.py - Master Pico - Linson Writer's Deck
# Handles keyboard capture, text buffer, file operations, and power management
# Sends display commands to Slave Pico via UART
# For Raspberry Pi Pico 2W (RP2350)

import time, utime, os, machine, json
from machine import Pin, I2C, UART
from tca8418 import TCA8418

#───────────────────────────────────────────────#
# ─────────── Constants & Config ───────────────#
#───────────────────────────────────────────────#

# Display constants (for layout calculations)
CHAR_WIDTH   = 8
CHAR_HEIGHT  = 15
MARGIN_LEFT  = 5
MARGIN_TOP   = 5
DISPLAY_WIDTH  = 400
DISPLAY_HEIGHT = 300

# Timing constants
FILE_FLUSH_INTERVAL_MS = 2000
SCREENSAVER_TIMEOUT_MS = 120_000   # 2 minutes
AUTO_OFF_TIMEOUT_MS    = 300_000   # 5 minutes

# Power management
FN_KEY      = (6, 4)
FN_HOLD_MS  = 2_000

# I2C configuration (updated for Pico 2W)
I2C_SDA = 2   # GP2 (I2C1 SDA)
I2C_SCL = 3   # GP3 (I2C1 SCL)
TCA_INT = 20  # GP20
TCA_RST = 21  # GP21

# UART configuration
UART_ID = 1
UART_TX = 8   # GP8 (UART1 TX)
UART_RX = 9   # GP9 (UART1 RX)
UART_BAUDRATE = 115200

# Power button
POWER_BTN = Pin(22, Pin.IN, Pin.PULL_UP)  # GP22

#───────────────────────────────────────────────#
# ─────────── Global State ─────────────────────#
#───────────────────────────────────────────────#

# Hardware objects
keyboard    = None
uart        = None

# Text buffer - stores pure text without positioning
text_buffer   = []   # list of characters incl. newlines
cursor_index  = 0    # logical cursor position

# Page tracking
current_page_index    = 0
current_subpage_index = 0

# File paths
STORAGE_BASE = "saved_files"
ACTIVE_FILE  = ""

# System files
CURSOR_FILE     = "cursor_position.txt"
SCREEN_BUFFER   = "screen_buffer.txt"
ERROR_LOG       = "error_log.txt"

# State flags
file_dirty      = False
file_last_flush = 0
in_menu         = False
in_paged_view   = False

# Key tracking
prev_keys         = set()
current_pressed   = set()
last_key_time     = 0

# Power management state
screensaver_active = False

#───────────────────────────────────────────────#
# ─────────── UART Communication ───────────────#
#───────────────────────────────────────────────#

def init_uart():
    """Initialize UART for communication with Slave Pico"""
    global uart
    try:
        uart = UART(UART_ID, baudrate=UART_BAUDRATE,
                   tx=Pin(UART_TX), rx=Pin(UART_RX))
        print(f"✓ UART initialized on GP{UART_TX}/GP{UART_RX} @ {UART_BAUDRATE} baud")
        return True
    except Exception as e:
        print(f"✗ UART init failed: {e}")
        return False

def send_uart_command(cmd_dict):
    """Send JSON command to Slave Pico via UART"""
    try:
        msg = json.dumps(cmd_dict) + '\n'
        uart.write(msg.encode())
        print(f"[UART TX] {cmd_dict.get('cmd', 'UNKNOWN')}")  # DEBUG
    except Exception as e:
        log_exception(e, "send_uart_command")

def receive_uart_response(timeout_ms=100):
    """Receive JSON response from Slave Pico"""
    try:
        start = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start) < timeout_ms:
            if uart.any():
                line = uart.readline()
                if line:
                    return json.loads(line.decode().strip())
            time.sleep_ms(10)
        return None
    except Exception as e:
        log_exception(e, "receive_uart_response")
        return None

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
    """Initialize storage directories and system files"""
    global STORAGE_BASE

    STORAGE_BASE = "saved_files"
    print(f"  Using internal storage: {STORAGE_BASE}")

    # Create saved_files directory
    try:
        os.mkdir(STORAGE_BASE)
        print(f"  Created directory: {STORAGE_BASE}")
    except OSError:
        print(f"  Directory exists: {STORAGE_BASE}")

    # Initialize system files if they don't exist
    try:
        # Create cursor_position.txt with defaults if missing
        try:
            with open(CURSOR_FILE, "r") as f:
                pass  # File exists
        except OSError:
            with open(CURSOR_FILE, "w") as f:
                f.write("0,0,0")  # cursor_index=0, page=0, subpage=0
            print(f"  Created {CURSOR_FILE}")

        # Create screen_buffer.txt if missing
        try:
            with open(SCREEN_BUFFER, "r") as f:
                pass  # File exists
        except OSError:
            with open(SCREEN_BUFFER, "w") as f:
                f.write("")  # Empty buffer
            print(f"  Created {SCREEN_BUFFER}")
    except Exception as e:
        print(f"  Warning: Could not initialize system files: {e}")

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

#───────────────────────────────────────────────#
# ──────── Display Commands ────────────────────#
#───────────────────────────────────────────────#

def request_display_update():
    """Send current text buffer and cursor to Slave for rendering"""
    global screensaver_active

    current_text = ''.join(text_buffer)
    cx, cy, _ = TextLayout.get_cursor_screen_pos(current_text, cursor_index, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    send_uart_command({
        "cmd": "RENDER_TEXT",
        "text": current_text,
        "cursor_x": cx,
        "cursor_y": cy
    })
    screensaver_active = False

def show_screensaver():
    """Tell Slave to show screensaver"""
    global screensaver_active
    send_uart_command({"cmd": "SHOW_SCREENSAVER"})
    screensaver_active = True

def wake_display():
    """Wake Slave from screensaver"""
    global screensaver_active
    if screensaver_active:
        send_uart_command({"cmd": "WAKE_UP"})
        request_display_update()
        screensaver_active = False

def power_off_display():
    """Tell Slave to enter low-power mode"""
    send_uart_command({"cmd": "POWER_OFF"})

def show_status(msg):
    """Send status message to Slave"""
    send_uart_command({"cmd": "STATUS", "text": msg})

#───────────────────────────────────────────────#
# ──────── Text Editing Functions ──────────────#
#───────────────────────────────────────────────#

def insert_char(ch: str):
    """Insert character at cursor position"""
    global text_buffer, cursor_index, file_dirty

    text_buffer.insert(cursor_index, ch)
    cursor_index += 1
    file_dirty = True
    save_cursor_position()
    request_display_update()

def backspace():
    """Delete character before cursor"""
    global text_buffer, cursor_index, file_dirty

    if cursor_index > 0:
        cursor_index -= 1
        text_buffer.pop(cursor_index)
        file_dirty = True
        save_cursor_position()
        request_display_update()

def cursor_newline():
    """Insert newline at cursor"""
    insert_char('\n')

def delete_word():
    """Delete word before cursor"""
    global text_buffer, cursor_index, file_dirty

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

    file_dirty = True
    save_cursor_position()
    request_display_update()

def clear_screen(keep_file=False):
    """Clear screen and reset to beginning"""
    global cursor_index, text_buffer

    if not keep_file:
        save_screen_buffer()

    # Send clear command to Slave
    send_uart_command({"cmd": "CLEAR"})

    text_buffer.clear()
    cursor_index = 0
    save_cursor_position()

#───────────────────────────────────────────────#
# ──────── File Operations ─────────────────────#
#───────────────────────────────────────────────#

def save_current_page():
    """Save current buffer to file"""
    global file_dirty, file_last_flush, current_page_index

    try:
        # Read the full file
        with open(ACTIVE_FILE, "r", encoding='utf-8') as f:
            full_content = f.read()
    except:
        full_content = ""

    # Split into explicit pages
    pages = full_content.split('\n---\n')

    # Ensure we have enough pages
    while len(pages) <= current_page_index:
        pages.append("")

    # Save the text buffer
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
    """Load a specific page into buffer"""
    global text_buffer, cursor_index, current_page_index, current_subpage_index

    current_page_index = page_idx
    current_subpage_index = subpage_idx

    # Get all pages
    pages = load_pages(ACTIVE_FILE)

    if page_idx < len(pages):
        text_buffer = list(pages[page_idx])
    else:
        text_buffer = []

    # Set cursor to end
    cursor_index = len(text_buffer)
    save_cursor_position()
    request_display_update()

def load_previous():
    """Load the last page of the file"""
    global cursor_index, current_page_index, current_subpage_index

    pages = load_pages(ACTIVE_FILE)
    if pages:
        current_page_index = len(pages) - 1
        last_page_text = pages[current_page_index]

        # Calculate number of subpages
        screen_pages = TextLayout.get_screen_pages(last_page_text, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        current_subpage_index = len(screen_pages) - 1 if screen_pages else 0

        # Load the specific page
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
    request_display_update()

#───────────────────────────────────────────────#
# ──────── Keyboard Functions ──────────────────#
#───────────────────────────────────────────────#

def init_keyboard():
    """Initialize TCA8418 keyboard"""
    global keyboard
    try:
        i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)  # I2C1 for Pico 2W
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

#───────────────────────────────────────────────#
# ──────── Menu Functions ──────────────────────#
#───────────────────────────────────────────────#

def list_txt_files():
    """List only user-editable text files"""
    files = []

    try:
        for f in os.listdir(STORAGE_BASE):
            if f.endswith('.txt'):
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
    """File selection menu (Master-Slave adapted)"""
    global in_menu, prev_keys

    in_menu = True

    files = list_txt_files()

    # If no files exist and not from editor, create default file
    if not files:
        if not from_editor:
            timestamp = utime.time() % 100000
            new_name = f"note_{timestamp}.txt"
            new_path = f"{STORAGE_BASE}/{new_name}"
            open(new_path, 'w').close()
            show_status(f"Created: {new_name}")
            in_menu = False
            return new_name
        else:
            show_status("No .txt files found")
            in_menu = False
            return None

    # Menu state
    idx = 0
    window = 0
    max_files_shown = min(10, (DISPLAY_HEIGHT - CHAR_HEIGHT * 3) // CHAR_HEIGHT)
    last_activity = utime.ticks_ms()
    fn_down_at = None

    def draw_menu():
        """Render menu to Slave display"""
        # Calculate footer position (at bottom of screen)
        footer_y = DISPLAY_HEIGHT - CHAR_HEIGHT * 2

        # Calculate how many lines we can show (leave room for footer)
        lines_available = (footer_y - MARGIN_TOP) // CHAR_HEIGHT
        actual_max_shown = min(max_files_shown, lines_available)

        # Build menu text with proper spacing to push footer to bottom
        menu_lines = []

        # Draw files
        for i, name in enumerate(files[window:window + actual_max_shown]):
            if window + i == idx:
                menu_lines.append(f"► {name}")
            else:
                menu_lines.append(f"  {name}")

        # Calculate blank lines needed to reach footer position
        current_y = MARGIN_TOP + len(menu_lines) * CHAR_HEIGHT
        blank_lines_needed = (footer_y - current_y) // CHAR_HEIGHT

        # Add blank lines to push footer to bottom
        for _ in range(blank_lines_needed):
            menu_lines.append("")

        # Add footer (now at bottom of screen)
        menu_lines.append(f"Files {idx+1}/{len(files)}")
        menu_lines.append("[Fn hold] Sleep | [PgUp/PgDn] Navigate")

        # Send to Slave via UART
        menu_text = '\n'.join(menu_lines)
        send_uart_command({
            "cmd": "RENDER_TEXT",
            "text": menu_text,
            "cursor_x": MARGIN_LEFT,
            "cursor_y": MARGIN_TOP
        })

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
                shutdown()
        else:
            fn_down_at = None

        if new_keys:
            last_activity = utime.ticks_ms()

            for k in new_keys:
                lbl = keyboard.key_map.get(k, '')
                print(f"Menu key pressed: {k} -> '{lbl}'")  # DEBUG

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
                    # File selected
                    in_menu = False
                    return files[idx]

                elif lbl == 'Esc' and from_editor:
                    in_menu = False
                    return None

        prev_keys = pressed

        # Timeout check (only when called from editor)
        if from_editor and utime.ticks_diff(utime.ticks_ms(), last_activity) > 30_000:
            in_menu = False
            return None

        time.sleep_ms(10)

#───────────────────────────────────────────────#
# ──────── Power Management ────────────────────#
#───────────────────────────────────────────────#

def idle_screensaver():
    """Show screensaver after inactivity"""
    # Save state
    if file_dirty:
        save_current_page()
    save_cursor_position()

    # Show screensaver on Slave
    show_screensaver()

def shutdown():
    """Power off both devices"""
    # Save work
    if file_dirty:
        save_current_page()
    save_cursor_position()

    # Tell Slave to power off
    power_off_display()
    time.sleep_ms(500)

    # Reset keyboard
    if keyboard:
        keyboard.reset()

    # Master enters light sleep
    print("Entering light sleep mode...")
    machine.lightsleep()

#───────────────────────────────────────────────#
# ──────── Main Program ─────────────────────────#
#───────────────────────────────────────────────#

def main():
    """Main program entry point"""
    global ACTIVE_FILE, last_key_time, file_last_flush, prev_keys
    global screensaver_active

    # Check wake reason
    wake_reason = machine.reset_cause()
    print(f"Reset cause: {wake_reason}")

    # Initialize storage first
    init_storage()

    # Initialize UART
    if not init_uart():
        print("Failed to initialize UART!")
        return

    # Initialize keyboard
    if not init_keyboard():
        print("Failed to initialize keyboard!")
        return

    # Send ready command to Slave
    send_uart_command({"cmd": "INIT", "width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT})
    time.sleep_ms(200)

    # File selection menu
    choice = file_menu(from_editor=False)
    if choice:
        ACTIVE_FILE = f"{STORAGE_BASE}/{choice}"
    else:
        # Should not happen (file_menu creates default file if none exist)
        # but handle gracefully
        timestamp = utime.time() % 100000
        ACTIVE_FILE = f"{STORAGE_BASE}/note_{timestamp}.txt"
        open(ACTIVE_FILE, 'w').close()

    # Ensure file exists
    open(ACTIVE_FILE, 'a').close()

    # Load cursor position and content
    load_cursor_position()
    load_previous()

    # Show initial content
    request_display_update()
    show_status(f"Editing: {ACTIVE_FILE.split('/')[-1]}")

    # Initialize timing
    last_key_time = utime.ticks_ms()
    file_last_flush = last_key_time
    fn_down_at = None

    print("Master Pico ready - keyboard active")

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
            last_key_time = now  # Reset inactivity timer

            # Wake from screensaver if needed
            if screensaver_active:
                wake_display()

            for k in new_keys:
                lbl = keyboard.key_map.get(k, '')

                # Handle special keys
                if lbl == 'Backspace':
                    if alt_on:
                        delete_word()
                    else:
                        backspace()
                elif lbl == 'Enter':
                    if shift_on:
                        new_page_marker()
                        clear_screen()
                    else:
                        cursor_newline()
                elif lbl == 'Space':
                    insert_char(' ')
                elif ctrl_on and lbl and len(lbl) == 1 and lbl.lower() == 's':
                    save_current_page()
                    show_status("Saved")
                elif len(lbl) == 1 and not ctrl_on:
                    ch = glyph(lbl, shift_on)
                    insert_char(ch)

        prev_keys = pressed

        # File save
        if file_dirty and \
           utime.ticks_diff(now, file_last_flush) > FILE_FLUSH_INTERVAL_MS:
            save_current_page()

        # Idle detection
        idle_time = utime.ticks_diff(now, last_key_time)
        if idle_time >= AUTO_OFF_TIMEOUT_MS:
            # 5 minutes - power off both devices
            shutdown()
        elif idle_time >= SCREENSAVER_TIMEOUT_MS and not screensaver_active:
            # 2 minutes - show screensaver
            idle_screensaver()

        time.sleep_ms(10)

if __name__ == "__main__":
    main()
