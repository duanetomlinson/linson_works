# *****************************************************************************
# * | File        :   display42.py (Pico 2W Version)
# * | Author      :   Waveshare team (Modified for Pico 2W by Linson Works)
# * | Function    :   Electronic paper driver for Waveshare 4.2" EPD V2
# * | Info        :   Migrated from ESP32S3 to Raspberry Pi Pico 2W
# *----------------
# * | This version:   V1.1 (Pico 2W)
# * | Date        :   2025-10-15
# * | Info        :   MicroPython driver for Pico 2W
# *----------------
# * PICO 2W CHANGES:
# * - Updated pin assignments to use hardware_pico module
# * - Changed SPI initialization from ESP32 style to Pico format
# * - Uses hardware_pico.init_spi() for consistent SPI setup
# * - All EPD display logic remains unchanged from original
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from machine import Pin
import framebuf
import utime
import hardware_pico  # Pico 2W hardware abstraction layer

# Display resolution (unchanged from original)
EPD_WIDTH       = 400
EPD_HEIGHT      = 300

# Pin assignments now come from hardware_pico module
# These match the Pico 2W pin layout defined in hardware_pico.py:
# - SPI1 bus: SCK=GP10, MOSI=GP11
# - Control pins: CS=GP13, DC=GP14, RST=GP15, BUSY=GP16
RST_PIN         = hardware_pico.RST_PIN
DC_PIN          = hardware_pico.DC_PIN
CS_PIN          = hardware_pico.CS_PIN
BUSY_PIN        = hardware_pico.BUSY_PIN

# Look-Up Table for grayscale waveforms (unchanged from original)
# This LUT controls the e-ink display refresh patterns for 4-gray mode
LUT_ALL=[   0x01,	0x0A,	0x1B,	0x0F,	0x03,	0x01,	0x01,
            0x05,	0x0A,	0x01,	0x0A,	0x01,	0x01,	0x01,
            0x05,	0x08,	0x03,	0x02,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x02,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x0A,	0x1B,	0x0F,	0x03,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x48,	0x03,	0x82,	0x84,	0x01,	0x01,
            0x01,	0x84,	0x84,	0x82,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x0A,	0x1B,	0x8F,	0x03,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x48,	0x83,	0x82,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x02,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x8A,	0x1B,	0x8F,	0x03,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x48,	0x83,	0x02,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x02,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x8A,	0x9B,	0x8F,	0x03,	0x01,	0x01,
            0x05,	0x4A,	0x01,	0x8A,	0x01,	0x01,	0x01,
            0x05,	0x48,	0x03,	0x42,	0x04,	0x01,	0x01,
            0x01,	0x04,	0x04,	0x42,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x01,	0x00,	0x00,	0x00,	0x00,	0x01,	0x01,
            0x00,	0x00,	0x00,	0x00,	0x00,	0x00,	0x00,
            0x00,	0x00,	0x00,	0x00,	0x00,	0x00,	0x00,
            0x02,	0x00,	0x00,	0x07,	0x17,	0x41,	0xA8,
            0x32,	0x30 ]

class EPD_4in2:
    def __init__(self):
        """
        Initialize the Waveshare 4.2" e-Paper Display V2

        PICO 2W SPECIFIC INITIALIZATION:
        - Uses hardware_pico.init_spi() for SPI bus setup
        - SPI1 bus with SCK=GP10, MOSI=GP11
        - Control pins: CS=GP13, DC=GP14, RST=GP15, BUSY=GP16
        """
        # Initialize control pins (unchanged logic)
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)

        # Display dimensions
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        # Refresh timing modes
        self.Seconds_1_5S = 0
        self.Seconds_1S = 1

        # LUT for 4-gray mode
        self.LUT_ALL = LUT_ALL

        # Color definitions for drawing
        self.black = 0x00
        self.white = 0xff
        self.darkgray = 0xaa
        self.grayish = 0x55

        # PICO 2W CHANGE: Use hardware_pico.init_spi() instead of manual SPI setup
        # Original ESP32 code was:
        #   self.spi = SPI(1, polarity=0, phase=0, sck=Pin(SPI_SCK), mosi=Pin(SPI_MOSI), miso=None)
        #   self.spi.init(baudrate=4000_000)
        # New Pico 2W code uses centralized initialization:
        self.spi = hardware_pico.init_spi()

        # Initialize frame buffers for 1-bit and 4-gray modes
        self.buffer_1Gray = bytearray(self.height * self.width // 8)
        self.buffer_4Gray = bytearray(self.height * self.width // 4)
        self.image1Gray = framebuf.FrameBuffer(self.buffer_1Gray, self.width, self.height, framebuf.MONO_HLSB)
        self.image4Gray = framebuf.FrameBuffer(self.buffer_4Gray, self.width, self.height, framebuf.GS2_HMSB)

        # Initialize display and clear screen
        self.EPD_4IN2_V2_Init()
        self.EPD_4IN2_V2_Clear()
        utime.sleep_ms(500)

    # =========================================================================
    # LOW-LEVEL HARDWARE INTERFACE METHODS
    # (Unchanged from original - these work identically on Pico 2W)
    # =========================================================================

    def digital_write(self, pin, value):
        """Set GPIO pin high (1) or low (0)"""
        pin.value(value)

    def digital_read(self, pin):
        """Read GPIO pin state"""
        return pin.value()

    def delay_ms(self, delaytime):
        """Delay in milliseconds"""
        utime.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        """Write bytes to SPI bus"""
        self.spi.write(bytearray(data))

    def module_exit(self):
        """Prepare module for shutdown"""
        self.digital_write(self.reset_pin, 0)

    # =========================================================================
    # E-INK DISPLAY CONTROL METHODS
    # (All unchanged from original - EPD commands are hardware-independent)
    # =========================================================================

    def reset(self):
        """
        Hardware reset sequence for EPD
        Multiple reset pulses ensure clean initialization
        """
        self.digital_write(self.reset_pin, 1)
        self.delay_ms(20)
        self.digital_write(self.reset_pin, 0)
        self.delay_ms(2)
        self.digital_write(self.reset_pin, 1)
        self.delay_ms(20)
        self.digital_write(self.reset_pin, 0)
        self.delay_ms(2)
        self.digital_write(self.reset_pin, 1)
        self.delay_ms(20)
        self.digital_write(self.reset_pin, 0)
        self.delay_ms(2)
        self.digital_write(self.reset_pin, 1)
        self.delay_ms(20)

    def send_command(self, command):
        """Send command byte to EPD (DC=0, CS=0, write, CS=1)"""
        self.digital_write(self.dc_pin, 0)
        self.digital_write(self.cs_pin, 0)
        self.spi_writebyte([command])
        self.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        """Send single data byte to EPD (DC=1, CS=0, write, CS=1)"""
        self.digital_write(self.dc_pin, 1)
        self.digital_write(self.cs_pin, 0)
        self.spi_writebyte([data])
        self.digital_write(self.cs_pin, 1)

    def send_data1(self, buf):
        """Send data buffer to EPD (DC=1, CS=0, write, CS=1)"""
        self.digital_write(self.dc_pin, 1)
        self.digital_write(self.cs_pin, 0)
        self.spi.write(bytearray(buf))
        self.digital_write(self.cs_pin, 1)

    def ReadBusy(self):
        """
        Wait for EPD to become ready
        BUSY pin: LOW=idle, HIGH=busy
        """
        print("e-Paper busy")
        while(self.digital_read(self.busy_pin) == 1):      #  LOW: idle, HIGH: busy
            self.delay_ms(100)
        print("e-Paper busy release")

    # =========================================================================
    # DISPLAY UPDATE CONTROL METHODS
    # Different update modes for various refresh requirements
    # =========================================================================

    def TurnOnDisplay(self):
        """Standard full refresh (high quality, slower)"""
        self.send_command(0x22) # Display Update Control
        self.send_data(0xF7)
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()

    def TurnOnDisplay_Fast(self):
        """Fast refresh mode (lower quality, faster)"""
        self.send_command(0x22) # Display Update Control
        self.send_data(0xC7)
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()

    def TurnOnDisplay_Partial(self):
        """Partial update mode (update only changed areas)"""
        self.send_command(0x22) # Display Update Control
        self.send_data(0xFF)
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()

    def TurnOnDisplay_4GRAY(self):
        """4-grayscale mode refresh"""
        self.send_command(0x22) # Display Update Control
        self.send_data(0xCF)
        self.send_command(0x20) # Activate Display Update Sequence
        self.ReadBusy()

    # =========================================================================
    # INITIALIZATION MODES
    # =========================================================================

    def EPD_4IN2_V2_Init(self):
        """
        Standard initialization sequence for EPD 4.2" V2
        Sets up display registers for normal operation
        """
        # EPD hardware init start
        self.reset()
        self.ReadBusy()

        self.send_command(0x12) # SWRESET
        self.ReadBusy()

        self.send_command(0x21)  # Display update control
        self.send_data(0x40)
        self.send_data(0x00)

        self.send_command(0x3C)  # BorderWavefrom
        self.send_data(0x05)

        self.send_command(0x11)  # data  entry  mode
        self.send_data(0x03)  # X-mode

        self.send_command(0x44)
        self.send_data(0x00)
        self.send_data(0x31)

        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x2B)
        self.send_data(0x01)

        self.send_command(0x4E)
        self.send_data(0x00)

        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

    def EPD_4IN2_V2_Init_Fast(self, mode):
        """
        Fast refresh initialization
        Args:
            mode: Seconds_1_5S or Seconds_1S for refresh speed
        """
        self.reset()
        self.ReadBusy()

        self.send_command(0x12) # SWRESET
        self.ReadBusy()

        self.send_command(0x21)  # Display update control
        self.send_data(0x40)
        self.send_data(0x00)

        self.send_command(0x3C)  # BorderWavefrom
        self.send_data(0x05)

        if mode == self.Seconds_1_5S:
            self.send_command(0x1A)
            self.send_data(0x6E)
        else :
            self.send_command(0x1A)
            self.send_data(0x5A)

        self.send_command(0x22)  # Load temperature value
        self.send_data(0x91)
        self.send_command(0x20)
        self.ReadBusy()

        self.send_command(0x11)  # data  entry  mode
        self.send_data(0x03)  # X-mode

        self.send_command(0x44)
        self.send_data(0x00)
        self.send_data(0x31)

        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x2B)
        self.send_data(0x01)

        self.send_command(0x4E)
        self.send_data(0x00)

        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

    def Lut(self):
        """Load Look-Up Table for 4-gray mode waveforms"""
        self.send_command(0x32)
        for i in range(227):
            self.send_data(self.LUT_ALL[i])

        self.send_command(0x3F)
        self.send_data(self.LUT_ALL[227])

        self.send_command(0x03)
        self.send_data(self.LUT_ALL[228])

        self.send_command(0x04)
        self.send_data(self.LUT_ALL[229])
        self.send_data(self.LUT_ALL[230])
        self.send_data(self.LUT_ALL[231])

        self.send_command(0x2c)
        self.send_data(self.LUT_ALL[232])

    def EPD_4IN2_V2_Init_4Gray(self):
        """
        Initialize EPD for 4-grayscale mode
        Enables black, white, and 2 shades of gray
        """
        # EPD hardware init start
        self.reset()
        self.ReadBusy()

        self.send_command(0x12) # SWRESET
        self.ReadBusy()

        self.send_command(0x21)  # Display update control
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x3C)  # BorderWavefrom
        self.send_data(0x03)

        self.send_command(0x0C)  # BTST
        self.send_data(0x8B) # 8B
        self.send_data(0x9C) # 9C
        self.send_data(0xA4) # 96 A4
        self.send_data(0x0F) # 0F

        self.Lut()

        self.send_command(0x11)  # data  entry  mode
        self.send_data(0x03)  # X-mode

        self.send_command(0x44)
        self.send_data(0x00)
        self.send_data(0x31)

        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x2B)
        self.send_data(0x01)

        self.send_command(0x4E)
        self.send_data(0x00)

        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

    # =========================================================================
    # DISPLAY DRAWING METHODS
    # =========================================================================

    def EPD_4IN2_V2_Clear(self):
        """
        Clear entire display to white
        Writes to both RAM buffers for clean refresh
        """
        high = self.height
        if( self.width % 8 == 0) :
            wide =  self.width // 8
        else :
            wide =  self.width // 8 + 1

        self.send_command(0x24)
        for i in range(0, wide):
            self.send_data1([0xff] * high)

        self.send_command(0x26)
        for i in range(0, wide):
            self.send_data1([0xff] * high)

        self.TurnOnDisplay()

    def EPD_4IN2_V2_Display(self, Image):
        """
        Display 1-bit (black/white) image with standard refresh
        Args:
            Image: bytearray of image data (width*height/8 bytes)
        """
        self.send_command(0x24)
        self.send_data1(Image)

        self.send_command(0x26)
        self.send_data1(Image)

        self.TurnOnDisplay()

    def EPD_4IN2_V2_Display_Fast(self, image):
        """
        Display 1-bit image with fast refresh
        Args:
            image: bytearray of image data (width*height/8 bytes)
        """
        self.send_command(0x24)
        self.send_data1(image)

        self.send_command(0x26)
        self.send_data1(image)

        self.TurnOnDisplay_Fast()

    def EPD_4IN2_V2_PartialDisplay(self, Image):
        """
        Partial update - refresh only changed regions
        Args:
            Image: bytearray of image data for changed region
        """
        self.send_command(0x3C)  # BorderWavefrom
        self.send_data(0x80)

        self.send_command(0x21)  # Display update control
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x3C)  # BorderWavefrom
        self.send_data(0x80)

        self.send_command(0x44)
        self.send_data(0x00)
        self.send_data(0x31)

        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x2B)
        self.send_data(0x01)

        self.send_command(0x4E)
        self.send_data(0x00)

        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x24) # WRITE_RAM
        self.send_data1(Image)
        self.TurnOnDisplay_Partial()


    def EPD_4IN2_V2_4GrayDisplay(self, Image):
        """
        Display 4-grayscale image
        Converts 2-bit per pixel format to dual-buffer format
        Args:
            Image: bytearray with 2-bit grayscale data (width*height/4 bytes)
        """
        self.send_command(0x24)
        for i in range(0, 15000):
            temp3=0
            for j in range(0, 2):
                temp1 = Image[i*2+j]
                for k in range(0, 2):
                    temp2 = temp1&0x03
                    if(temp2 == 0x03):
                        temp3 |= 0x01   # white
                    elif(temp2 == 0x00):
                        temp3 |= 0x00   # black
                    elif(temp2 == 0x02):
                        temp3 |= 0x01   # gray1
                    else:   # 0x01
                        temp3 |= 0x00   # gray2
                    temp3 <<= 1

                    temp1 >>= 2
                    temp2 = temp1&0x03
                    if(temp2 == 0x03):   # white
                        temp3 |= 0x01
                    elif(temp2 == 0x00):   # black
                        temp3 |= 0x00
                    elif(temp2 == 0x02):
                        temp3 |= 0x01   # gray1
                    else:   # 0x01
                        temp3 |= 0x00   # gray2

                    if (( j!=1 ) | ( k!=1 )):
                        temp3 <<= 1

                    temp1 >>= 2
            self.send_data(temp3)

        self.send_command(0x26)
        for i in range(0, 15000):
            temp3=0
            for j in range(0, 2):
                temp1 = Image[i*2+j]
                for k in range(0, 2):
                    temp2 = temp1&0x03
                    if(temp2 == 0x03):
                        temp3 |= 0x01   # white
                    elif(temp2 == 0x00):
                        temp3 |= 0x00   # black
                    elif(temp2 == 0x02):
                        temp3 |= 0x00   # gray1
                    else:   # 0x01
                        temp3 |= 0x01   # gray2
                    temp3 <<= 1

                    temp1 >>= 2
                    temp2 = temp1&0x03
                    if(temp2 == 0x03):   # white
                        temp3 |= 0x01
                    elif(temp2 == 0x00):   # black
                        temp3 |= 0x00
                    elif(temp2 == 0x02):
                        temp3 |= 0x00   # gray1
                    else:   # 0x01
                        temp3 |= 0x01   # gray2

                    if (( j!=1 ) | ( k!=1 )):
                        temp3 <<= 1

                    temp1 >>= 2
            self.send_data(temp3)
        self.TurnOnDisplay_4GRAY()

    def Sleep(self):
        """
        Put EPD into deep sleep mode (low power)
        Reduces current consumption when display not in use
        """
        self.send_command(0x10)  # DEEP_SLEEP
        self.send_data(0x01)
