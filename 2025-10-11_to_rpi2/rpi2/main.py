# main.py - Slave Pico - Linson Writer's Deck
# Handles e-ink display rendering and UART command processing
# Receives display commands from Master Pico via UART
# For Raspberry Pi Pico 2W (RP2350)

import time, utime, machine, json
from machine import Pin, SPI, UART
from display42 import EPD_4in2

#───────────────────────────────────────────────#
# ─────────── Constants & Config ───────────────#
#───────────────────────────────────────────────#

# Display constants
CHAR_WIDTH   = 8
CHAR_HEIGHT  = 15
MARGIN_LEFT  = 5
MARGIN_TOP   = 5

# UART configuration
UART_ID = 1
UART_TX = 8   # GP8 (UART1 TX)
UART_RX = 9   # GP9 (UART1 RX)
UART_BAUDRATE = 115200

# SPI and control pins (updated for Pico 2W)
SPI_SCK  = 10  # GP10 (SPI1 SCK)
SPI_MOSI = 11  # GP11 (SPI1 MOSI)
CS_PIN   = 13  # GP13 (Chip select)
DC_PIN   = 14  # GP14 (Data/Command)
RST_PIN  = 15  # GP15 (Display reset)
BUSY_PIN = 16  # GP16 (Busy status)

#───────────────────────────────────────────────#
# ─────────── Global State ─────────────────────#
#───────────────────────────────────────────────#

# Hardware objects
epd  = None
uart = None

# Display dimensions
max_w = 0
max_h = 0

#───────────────────────────────────────────────#
# ─────────── UART Communication ───────────────#
#───────────────────────────────────────────────#

def init_uart():
    """Initialize UART for communication with Master Pico"""
    global uart
    try:
        uart = UART(UART_ID, baudrate=UART_BAUDRATE,
                   tx=Pin(UART_TX), rx=Pin(UART_RX))
        print(f"✓ UART initialized on GP{UART_TX}/GP{UART_RX} @ {UART_BAUDRATE} baud")
        return True
    except Exception as e:
        print(f"✗ UART init failed: {e}")
        return False

def send_uart_response(response_dict):
    """Send JSON response to Master Pico via UART"""
    try:
        msg = json.dumps(response_dict) + '\n'
        uart.write(msg.encode())
    except Exception as e:
        print(f"UART send error: {e}")

def receive_uart_command(timeout_ms=10):
    """Receive JSON command from Master Pico"""
    try:
        if uart.any():
            line = uart.readline()
            if line:
                return json.loads(line.decode().strip())
        return None
    except Exception as e:
        print(f"UART receive error: {e}")
        return None

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

#───────────────────────────────────────────────#
# ──────── Display Functions ───────────────────#
#───────────────────────────────────────────────#

def clear_display_buffer():
    """Clear the display buffer to white"""
    epd.image1Gray.fill(0xFF)

def render_text_page(page_chars):
    """Render text characters to display buffer"""
    clear_display_buffer()
    for x, y, ch in page_chars:
        if ch not in '\n':
            epd.image1Gray.text(ch, x, y, epd.black)

def render_cursor(x, y):
    """Draw cursor at specified position"""
    epd.image1Gray.fill_rect(x, y + CHAR_HEIGHT - 2, CHAR_WIDTH, 2, epd.black)

def show_linson():
    """Display 'Linson' logo (screen saver)"""
    clear_display_buffer()
    epd.image1Gray.fill(0x00)  # Black background
    txt = "Linson"
    x = (max_w - len(txt) * CHAR_WIDTH) // 2
    y = (max_h - CHAR_HEIGHT) // 2
    epd.image1Gray.text(txt, x, y, 0xFF)  # White text
    epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)

def show_status(msg):
    """Show status message at bottom of screen"""
    bottom_y = max_h - CHAR_HEIGHT
    epd.image1Gray.fill_rect(0, bottom_y, max_w, CHAR_HEIGHT, 0xFF)
    epd.image1Gray.text(msg, MARGIN_LEFT, bottom_y, epd.black)
    epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)

def partial_refresh():
    """Perform partial display refresh"""
    try:
        print("[DISPLAY] Partial refresh starting...")  # DEBUG
        epd.EPD_4IN2_V2_PartialDisplay(epd.buffer_1Gray)
        print("[DISPLAY] Partial refresh complete")  # DEBUG
    except Exception as e:
        print(f"Partial refresh error: {e}")

def full_refresh():
    """Perform full display refresh"""
    try:
        epd.EPD_4IN2_V2_Display_Fast(epd.buffer_1Gray)
    except Exception as e:
        print(f"Full refresh error: {e}")

#───────────────────────────────────────────────#
# ──────── Command Handlers ────────────────────#
#───────────────────────────────────────────────#

def handle_init(cmd):
    """Handle initialization command"""
    global max_w, max_h
    max_w = cmd.get("width", 400)
    max_h = cmd.get("height", 300)
    print(f"Display initialized: {max_w}x{max_h}")
    send_uart_response({"status": "ok", "cmd": "INIT"})

def handle_render_text(cmd):
    """Handle text rendering command"""
    text = cmd.get("text", "")
    cursor_x = cmd.get("cursor_x", MARGIN_LEFT)
    cursor_y = cmd.get("cursor_y", MARGIN_TOP)

    # Calculate layout
    pages = TextLayout.get_screen_pages(text, max_w, max_h)

    # Render first page
    if pages:
        render_text_page(pages[0])
    else:
        clear_display_buffer()

    # Render cursor
    render_cursor(cursor_x, cursor_y)

    # Partial refresh
    partial_refresh()

    send_uart_response({"status": "ok", "cmd": "RENDER_TEXT"})

def handle_show_screensaver(cmd):
    """Handle screensaver display command"""
    show_linson()
    send_uart_response({"status": "ok", "cmd": "SHOW_SCREENSAVER"})

def handle_wake_up(cmd):
    """Handle wake-up command"""
    # Clear the screensaver
    clear_display_buffer()
    full_refresh()
    send_uart_response({"status": "ok", "cmd": "WAKE_UP"})

def handle_power_off(cmd):
    """Handle power-off command"""
    # Show shutdown message
    clear_display_buffer()
    epd.image1Gray.text("Power Off", MARGIN_LEFT, MARGIN_TOP, epd.black)
    full_refresh()

    # Enter display sleep mode
    epd.Sleep()

    send_uart_response({"status": "ok", "cmd": "POWER_OFF"})

    # Enter light sleep
    print("Slave entering light sleep...")
    machine.lightsleep()

def handle_clear(cmd):
    """Handle clear screen command"""
    clear_display_buffer()
    full_refresh()
    send_uart_response({"status": "ok", "cmd": "CLEAR"})

def handle_status(cmd):
    """Handle status message command"""
    msg = cmd.get("text", "")
    show_status(msg)
    send_uart_response({"status": "ok", "cmd": "STATUS"})

# Command dispatcher
COMMAND_HANDLERS = {
    "INIT": handle_init,
    "RENDER_TEXT": handle_render_text,
    "SHOW_SCREENSAVER": handle_show_screensaver,
    "WAKE_UP": handle_wake_up,
    "POWER_OFF": handle_power_off,
    "CLEAR": handle_clear,
    "STATUS": handle_status,
}

#───────────────────────────────────────────────#
# ──────── Main Program ─────────────────────────#
#───────────────────────────────────────────────#

def main():
    """Main program entry point"""
    global epd, max_w, max_h

    print("Slave Pico starting...")

    # Initialize UART first
    if not init_uart():
        print("Failed to initialize UART!")
        return

    # Initialize display
    try:
        epd = EPD_4in2()
        epd.EPD_4IN2_V2_Init_Fast(epd.Seconds_1_5S)
        max_w, max_h = epd.width, epd.height
        print(f"✓ Display initialized: {max_w}x{max_h}")

        # Clear display
        clear_display_buffer()
        full_refresh()
        time.sleep_ms(100)
    except Exception as e:
        print(f"✗ Display init failed: {e}")
        return

    # Clear display and wait for commands
    clear_display_buffer()
    full_refresh()

    print("Slave Pico ready - waiting for commands")

    # Main loop - wait for UART commands
    while True:
        cmd = receive_uart_command()

        if cmd:
            cmd_type = cmd.get("cmd")
            print(f"[UART RX] {cmd_type}")  # DEBUG
            if cmd_type in COMMAND_HANDLERS:
                try:
                    COMMAND_HANDLERS[cmd_type](cmd)
                except Exception as e:
                    print(f"Error handling {cmd_type}: {e}")
                    send_uart_response({"status": "error", "cmd": cmd_type, "error": str(e)})
            else:
                print(f"Unknown command: {cmd_type}")
                send_uart_response({"status": "error", "cmd": cmd_type, "error": "Unknown command"})

        time.sleep_ms(10)

if __name__ == "__main__":
    main()
