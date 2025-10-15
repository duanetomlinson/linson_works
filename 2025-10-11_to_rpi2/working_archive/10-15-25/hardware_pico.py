"""
Hardware abstraction layer for Raspberry Pi Pico 2W
Defines pin assignments and hardware initialization for the e-ink typewriter

Pin assignments avoid GP23-GP25 (used by CYW43439 WiFi chip)
"""

from machine import Pin, SPI, I2C

# E-ink Display (Waveshare 4.2" EPD) - SPI1
# Using SPI1 to avoid conflicts with potential future SPI0 usage
SPI_SCK = 10    # GP10 - SPI1 SCK
SPI_MOSI = 11   # GP11 - SPI1 TX (MOSI)
CS_PIN = 13     # GP13 - Chip Select
DC_PIN = 14     # GP14 - Data/Command
RST_PIN = 15    # GP15 - Reset
BUSY_PIN = 16   # GP16 - Busy status

# TCA8418 Keyboard Controller - I2C0
# Standard I2C pins for easy breadboard connections
I2C_SDA = 4     # GP4 - I2C0 SDA
I2C_SCL = 5     # GP5 - I2C0 SCL
TCA_INT = 6     # GP6 - Keyboard interrupt (was GPIO21 on ESP32)
TCA_RST = 7     # GP7 - Keyboard reset (was GPIO38 on ESP32)

# Power Management
POWER_BTN = 22  # GP22 - Power button (safe, not WiFi)

# Platform identification
PLATFORM = 'pico2w'

def init_spi():
    """
    Initialize SPI for e-ink display
    Returns: SPI object configured for EPD communication
    """
    # Pico 2W SPI initialization - specify all parameters at once
    spi = SPI(
        1,                      # SPI1 bus
        baudrate=2_000_000,     # 4 MHz (EPD max is typically 10-20 MHz)
        polarity=0,             # CPOL=0
        phase=0,                # CPHA=0
        bits=8,                 # 8-bit transfers
        firstbit=SPI.MSB,       # MSB first
        sck=Pin(SPI_SCK),       # Clock pin
        mosi=Pin(SPI_MOSI),     # MOSI pin
        miso=None               # No MISO needed for EPD
    )
    return spi

def init_i2c():
    """
    Initialize I2C for keyboard controller
    Returns: I2C object configured for TCA8418
    """
    # I2C initialization - compatible between ESP32 and Pico
    i2c = I2C(
        0,                      # I2C0 bus
        scl=Pin(I2C_SCL),       # Clock pin
        sda=Pin(I2C_SDA),       # Data pin
        freq=400_000            # 400 kHz (fast mode)
    )
    return i2c

def init_display_pins():
    """
    Initialize GPIO pins for display control
    Returns: dict of Pin objects
    """
    pins = {
        'cs': Pin(CS_PIN, Pin.OUT, value=1),      # CS high (inactive)
        'dc': Pin(DC_PIN, Pin.OUT, value=0),      # DC low (command mode)
        'rst': Pin(RST_PIN, Pin.OUT, value=1),    # RST high (not in reset)
        'busy': Pin(BUSY_PIN, Pin.IN)             # BUSY input
    }
    return pins

def init_keyboard_pins():
    """
    Initialize GPIO pins for keyboard controller
    Returns: dict of Pin objects
    """
    pins = {
        'interrupt': Pin(TCA_INT, Pin.IN, Pin.PULL_UP),  # INT with pull-up
        'reset': Pin(TCA_RST, Pin.OUT, value=1)          # RST high (not in reset)
    }
    return pins

def init_power_button():
    """
    Initialize power button pin
    Returns: Pin object
    """
    return Pin(POWER_BTN, Pin.IN, Pin.PULL_UP)

def enter_dormant_mode(wake_pin):
    """
    Enter low-power dormant mode on Pico 2W
    Wake on GPIO interrupt (different from ESP32 deep sleep)

    Args:
        wake_pin: Pin object to wake from (e.g., keyboard interrupt)

    Note: Pico 2W doesn't have ESP32's wake_on_ext0().
    Use machine.lightsleep() or dormant mode via RP2 registers.
    """
    import machine

    # Configure wake pin interrupt
    wake_pin.irq(trigger=Pin.IRQ_FALLING, wake=machine.DEEPSLEEP)

    # Enter light sleep (lowest power while maintaining RAM)
    # For true dormant mode, would need direct RP2 register access
    machine.lightsleep()

def get_reset_reason():
    """
    Get reason for last reset
    Returns: String describing reset reason

    Note: Different from ESP32 reset codes
    """
    import machine

    reset_cause = machine.reset_cause()

    reasons = {
        machine.PWRON_RESET: "Power-on reset",
        machine.HARD_RESET: "Hard reset (button/external)",
        machine.WDT_RESET: "Watchdog timer reset",
        machine.DEEPSLEEP_RESET: "Deep sleep wake",
        machine.SOFT_RESET: "Soft reset (Ctrl+D)"
    }

    return reasons.get(reset_cause, f"Unknown reset ({reset_cause})")

# Pin summary for reference
PIN_MAP = {
    'Display SPI1': {
        'SCK': SPI_SCK,
        'MOSI': SPI_MOSI,
        'CS': CS_PIN,
        'DC': DC_PIN,
        'RST': RST_PIN,
        'BUSY': BUSY_PIN
    },
    'Keyboard I2C0': {
        'SDA': I2C_SDA,
        'SCL': I2C_SCL,
        'INT': TCA_INT,
        'RST': TCA_RST
    },
    'Power': {
        'BUTTON': POWER_BTN
    }
}

def print_pin_map():
    """Print pin assignment summary"""
    print("\n" + "="*50)
    print("Raspberry Pi Pico 2W Pin Assignments")
    print("="*50)
    for category, pins in PIN_MAP.items():
        print(f"\n{category}:")
        for name, pin_num in pins.items():
            print(f"  {name:6s} = GP{pin_num}")
    print("\nNote: GP23-GP25 reserved for WiFi (CYW43439)")
    print("="*50 + "\n")
