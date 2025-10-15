# tca8418.py - TCA8418 I2C Keypad Controller for Linson Keyboard
# Complete MicroPython implementation with enhanced Linson 10x8 key mapping
# For Raspberry Pi Pico 2W (RP2350) with full pin support and improved punctuation handling
#
# COMPLETE WIRING GUIDE:
#   TCA8418 VCC → Pico 2W 3.3V (Pin 36)
#   TCA8418 GND → Pico 2W GND (Pin 3/8/13/etc)
#   TCA8418 SDA → Pico 2W GP2  (Pin 4 - I2C1 Data)
#   TCA8418 SCL → Pico 2W GP3  (Pin 5 - I2C1 Clock)
#   TCA8418 INT → Pico 2W GP20 (Pin 26 - Interrupt - RECOMMENDED for efficiency)
#   TCA8418 RST → Pico 2W GP21 (Pin 27 - Reset - OPTIONAL for recovery)
#
# IMPORTANT: This version uses CORRECTED register addresses per TCA8418 datasheet
# - Fixed missing KEY_EVENT_G, H, I, J registers (0x0A-0x0D)
# - Fixed KP_LCK_TIMER address (0x0E, was incorrectly 0x0A)
# - Fixed all subsequent register addresses (+4 offset correction)
# - Added proper INT/RST pin support for optimal performance
# - Enhanced punctuation mapping system

from machine import I2C, Pin
import utime

class TCA8418:
    """
    TCA8418 I2C Keypad Controller Library for MicroPython
    Supports 8x10 matrix (80 keys), hardware debouncing, and interrupt support
    Enhanced with Linson keyboard layout mapping and punctuation handling
    """

    # I2C Address (default for TCA8418)
    I2C_ADDR = 0x34

    # Register addresses (CORRECTED per TCA8418 datasheet)
    REG_CFG         = 0x01
    REG_INT_STAT    = 0x02
    REG_KEY_LCK_EC  = 0x03
    REG_KEY_EVENT_A = 0x04
    REG_KEY_EVENT_B = 0x05
    REG_KEY_EVENT_C = 0x06
    REG_KEY_EVENT_D = 0x07
    REG_KEY_EVENT_E = 0x08
    REG_KEY_EVENT_F = 0x09
    REG_KEY_EVENT_G = 0x0A  # FIXED: Was missing
    REG_KEY_EVENT_H = 0x0B  # FIXED: Was missing
    REG_KEY_EVENT_I = 0x0C  # FIXED: Was missing
    REG_KEY_EVENT_J = 0x0D  # FIXED: Was missing
    REG_KP_LCK_TIMER= 0x0E  # FIXED: Was 0x0A, now correct
    REG_UNLOCK1     = 0x0F  # FIXED: Was 0x0B, now correct
    REG_UNLOCK2     = 0x10  # FIXED: Was 0x0C, now correct
    REG_GPIO_INT_STAT1 = 0x11  # FIXED: All subsequent addresses shifted +4
    REG_GPIO_INT_STAT2 = 0x12
    REG_GPIO_INT_STAT3 = 0x13
    REG_GPIO_DAT_STAT1 = 0x14
    REG_GPIO_DAT_STAT2 = 0x15
    REG_GPIO_DAT_STAT3 = 0x16
    REG_GPIO_DAT_OUT1  = 0x17
    REG_GPIO_DAT_OUT2  = 0x18
    REG_GPIO_DAT_OUT3  = 0x19
    REG_GPIO_INT_EN1   = 0x1A
    REG_GPIO_INT_EN2   = 0x1B
    REG_GPIO_INT_EN3   = 0x1C
    REG_KP_GPIO1       = 0x1D
    REG_KP_GPIO2       = 0x1E
    REG_KP_GPIO3       = 0x1F
    REG_GPI_EM1        = 0x20
    REG_GPI_EM2        = 0x21
    REG_GPI_EM3        = 0x22
    REG_GPIO_DIR1      = 0x23
    REG_GPIO_DIR2      = 0x24
    REG_GPIO_DIR3      = 0x25
    REG_GPIO_INT_LVL1  = 0x26
    REG_GPIO_INT_LVL2  = 0x27
    REG_GPIO_INT_LVL3  = 0x28
    REG_DEBOUNCE_DIS1  = 0x29
    REG_DEBOUNCE_DIS2  = 0x2A
    REG_DEBOUNCE_DIS3  = 0x2B
    REG_GPIO_PULL1     = 0x2C
    REG_GPIO_PULL2     = 0x2D
    REG_GPIO_PULL3     = 0x2E

    # Configuration bits
    CFG_AI = 0x80      # Auto-increment
    CFG_GPI_E_CFG = 0x40
    CFG_OVR_FLOW_M = 0x20
    CFG_INT_CFG = 0x10
    CFG_OVR_FLOW_IEN = 0x08
    CFG_K_LCK_IEN = 0x04
    CFG_GPI_IEN = 0x02
    CFG_KE_IEN = 0x01

    # Key event codes
    KEY_PRESSED = 0x80
    KEY_RELEASED = 0x00

    def __init__(self, i2c, addr=None, interrupt_pin=None, reset_pin=None):
        """
        Initialize TCA8418 for Linson keyboard
        :param i2c: I2C object
        :param addr: I2C address (default 0x34)
        :param interrupt_pin: Optional GPIO pin for interrupt (Pin object) - RECOMMENDED
        :param reset_pin: Optional GPIO pin for hardware reset (Pin object) - OPTIONAL
        """
        self.i2c = i2c
        self.addr = addr or self.I2C_ADDR
        self.interrupt_pin = interrupt_pin
        self.reset_pin = reset_pin

        # Configure interrupt pin if provided
        if self.interrupt_pin:
            self.interrupt_pin.init(Pin.IN, Pin.PULL_UP)  # Active low with pull-up
            print(f"INT pin configured on GP{self.interrupt_pin}")

        # Configure reset pin if provided
        if self.reset_pin:
            self.reset_pin.init(Pin.OUT, value=1)  # Start high (not in reset)
            print(f"RST pin configured on GP{self.reset_pin}")

        # Hardware reset if reset pin is available
        if self.reset_pin:
            self.hardware_reset()

        # Check if device is present:
        devices = self.i2c.scan()
        if self.addr not in devices:
            raise OSError(f"TCA8418 not found at address 0x{self.addr:02X}")

        # Linson keyboard 10x8 matrix key mapping (matches your layout). Row 7 not used.
        self.key_map = {
            # Row 0
            (0, 1): 'Esc', (0, 2): '1', (0, 3): '2', (0, 4): '3', (0, 5): '4',
            (0, 6): '5', (0, 7): '6', (0, 8): '7', (0, 9): '8', (1, 0): '9',

             # Row 1
            (1, 1): '0', (1, 2): '-', (1, 3): '=', (1, 4): 'Backspace', (1, 5): 'Home',
            (1, 6): 'Tab', (1, 7): 'Q', (1, 8): 'W', (1, 9): 'E', (2, 0): 'R',

            # Row 2
            (2, 1): 'T', (2, 2): 'Y', (2, 3): 'U', (2, 4): 'I', (2, 5): 'O',
            (2, 6): 'P', (2, 7): '[', (2, 8): ']', (2, 9): '\\', (3, 0): 'Del',

            # Row 3
            (3, 1): 'Caps', (3, 2): 'A', (3, 3): 'S', (3, 4): 'D', (3, 5): 'F',
            (3, 6): 'G', (3, 7): 'H', (3, 8): 'J', (3, 9): 'K', (4, 0): 'L',

            # Row 4
            (4, 1): ';', (4, 2): "'", (4, 3): 'Enter', (4, 4): 'PgUp', (4, 5): 'Shift',
            (4, 6): 'Z', (4, 7): 'X', (4, 8): 'C', (4, 9): 'V', (5, 0): 'B',

            # Row 5
            (5, 1): 'N', (5, 2): 'M', (5, 3): ',', (5, 4): '.', (5, 5): '/',
            (5, 6): 'Shift', (5, 7): 'Up', (5, 8): 'PgDn', (5, 9): 'Alt', (6, 0): 'Win',

            # Row 6
            (6, 1): 'Ctrl', (6, 2): 'Space', (6, 3): 'Alt', (6, 4): 'Fn', (6, 5): 'Ctrl',
            (6, 6): 'Left', (6, 7): 'Down', (6, 8): 'Right',
        }

        # Enhanced punctuation mapping for shift key combinations
        # This handles both basic punctuation and special characters
        self.punct_map = {
            '1':'!', '2':'@', '3':'#', '4':'$', '5':'%', '6':'^',
            '7':'&', '8':'*', '9':'(', '0':')', '-':'_', '=':'+',
            '/':'?', ',':'<', '.':'>', ';':':', "'":'"', '[':'{',
            ']':'}', '\\':'|'
        }

        # Create a mapping for easy access to shifted characters
        self.shift_chars = {}
        for base, shifted in self.punct_map.items():
            self.shift_chars[base] = shifted

        # Initialize the device
        self.reset()
        self.configure()
        print("TCA8418 initialized with CORRECTED register addresses for Linson 10x8 keyboard matrix")

    def hardware_reset(self):
        """Perform hardware reset using RST pin if available"""
        if not self.reset_pin:
            return

        print("Performing hardware reset...")
        self.reset_pin.value(0)  # Assert reset (active low)
        utime.sleep_ms(10)       # Hold reset for 10ms
        self.reset_pin.value(1)  # Release reset
        utime.sleep_ms(50)       # Wait for device to stabilize

    def reset(self):
        """Software reset of TCA8418"""
        # Clear all configuration
        self._write_reg(self.REG_CFG, 0x00)
        utime.sleep_ms(10)

    def configure(self):
        """Configure TCA8418 for keypad operation"""
        # Configure for keypad mode with interrupts
        config = (self.CFG_AI |          # Auto-increment
                 self.CFG_KE_IEN |       # Key event interrupt enable
                 self.CFG_OVR_FLOW_IEN)  # Overflow interrupt enable

        self._write_reg(self.REG_CFG, config)

        # Set all pins as keypad inputs (rows and columns)
        # For 8 rows × 10 columns = 18 pins total
        self._write_reg(self.REG_KP_GPIO1, 0xFF)  # R0-R7 (pins 0-7)
        self._write_reg(self.REG_KP_GPIO2, 0xFF)  # C0-C7 (pins 8-15)
        self._write_reg(self.REG_KP_GPIO3, 0x03)  # C8-C9 (pins 16-17)

        # Clear any pending interrupts
        self.clear_interrupts()

    def _write_reg(self, reg, value):
        """Write to a register"""
        self.i2c.writeto(self.addr, bytes([reg, value]))

    def _read_reg(self, reg):
        """Read from a register"""
        self.i2c.writeto(self.addr, bytes([reg]))
        return self.i2c.readfrom(self.addr, 1)[0]

    def clear_interrupts(self):
        """Clear all pending interrupts"""
        # Read interrupt status to clear
        self._read_reg(self.REG_INT_STAT)

        # Clear entire key event FIFO (all 10 registers A-J)
        # With auto-increment enabled, this properly clears the FIFO
        while self.get_key_count() > 0:
            self._read_reg(self.REG_KEY_EVENT_A)  # Auto-increment handles A-J

    def get_key_count(self):
        """Get number of keys in FIFO"""
        return self._read_reg(self.REG_KEY_LCK_EC) & 0x0F

    def read_key_event(self):
        """
        Read next key event from FIFO
        Returns: (row, col, pressed) or None if no events
        """
        if self.get_key_count() == 0:
            return None

        # Read key event from FIFO (auto-increment reads through registers A-J)
        # With auto-increment enabled, reading REG_KEY_EVENT_A automatically
        # moves through the 10-deep FIFO (registers 0x04-0x0D)
        event = self._read_reg(self.REG_KEY_EVENT_A)

        if event == 0:
            return None

        # Decode event
        pressed = bool(event & self.KEY_PRESSED)
        key_code = event & 0x7F

        # Convert key code to row/column
        # TCA8418 uses: key_code = row * 10 + col
        row = key_code // 10
        col = key_code % 10

        return (row, col, pressed)

    def get_key_name(self, row, col):
        """Get key name from row/column using Linson layout"""
        return self.key_map.get((row, col), f"Unknown({row},{col})")

    def get_character(self, key_name, shift_pressed=False):
        """
        Get the character for a key, handling shift combinations
        :param key_name: The base key name (e.g., '1', 'a', ';')
        :param shift_pressed: Whether shift is currently pressed
        :return: The character to output
        """
        if not key_name or len(key_name) != 1:
            return key_name  # Return special keys unchanged

        # Handle alphabetic characters
        if key_name.isalpha():
            return key_name.upper() if shift_pressed else key_name.lower()

        # Handle punctuation and numbers with shift
        if shift_pressed and key_name in self.punct_map:
            return self.punct_map[key_name]

        # Return the key as-is for other cases
        return key_name

    def read_keys_with_names(self):
        """
        Read all pending key events with key names
        Returns: List of (key_name, pressed) tuples
        """
        events = []
        while True:
            event = self.read_key_event()
            if event is None:
                break

            row, col, pressed = event
            key_name = self.get_key_name(row, col)
            if key_name and not key_name.startswith("Unknown"):  # Skip unmapped keys
                events.append((key_name, pressed))

        return events

    def scan_keys(self):
        """
        Scan for all key events and return list of pressed keys (original method)
        Returns: List of (row, col) tuples for currently pressed keys
        """
        pressed_keys = []

        # Process all events in FIFO
        while True:
            event = self.read_key_event()
            if event is None:
                break

            row, col, pressed = event
            if pressed:
                # Add to pressed keys if not already there
                key_pos = (row, col)
                if key_pos not in pressed_keys:
                    pressed_keys.append(key_pos)
            else:
                # Remove from pressed keys if it was there
                key_pos = (row, col)
                if key_pos in pressed_keys:
                    pressed_keys.remove(key_pos)

        return pressed_keys

    def has_interrupt(self):
        """Check if there are pending interrupts"""
        if self.interrupt_pin:
            # Use hardware interrupt pin (active low)
            return not self.interrupt_pin.value()
        else:
            # Fall back to polling interrupt status register
            status = self._read_reg(self.REG_INT_STAT)
            return status != 0

    def get_interrupt_status(self):
        """Get detailed interrupt status"""
        return self._read_reg(self.REG_INT_STAT)

    def get_text_for_key(self, key_name, shift_pressed=False, caps_lock=False):
        """
        Complete text generation for a key press, handling all modifiers
        :param key_name: The key that was pressed
        :param shift_pressed: Whether shift is currently held
        :param caps_lock: Whether caps lock is active
        :return: The text that should be inserted
        """
        # Handle special keys that don't produce text
        special_keys = ['Shift', 'Ctrl', 'Alt', 'Fn', 'Caps', 'Tab', 'Enter',
                       'Backspace', 'Esc', 'Home', 'Del', 'PgUp', 'PgDn',
                       'Up', 'Down', 'Left', 'Right', 'Win']

        if key_name in special_keys:
            return key_name  # Return the key name for special processing

        # Handle space key
        if key_name == 'Space':
            return ' '

        # Handle printable characters
        if len(key_name) == 1:
            # Alphabetic characters with caps lock and shift logic
            if key_name.isalpha():
                # XOR logic: caps lock XOR shift determines final case
                make_upper = caps_lock ^ shift_pressed
                return key_name.upper() if make_upper else key_name.lower()

            # Numbers and punctuation with shift
            if shift_pressed and key_name in self.punct_map:
                return self.punct_map[key_name]
            else:
                return key_name

        # For any other keys, return as-is
        return key_name
