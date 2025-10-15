"""
display_async.py - Async wrappers for e-ink display operations
Provides non-blocking display refresh operations using uasyncio
For Raspberry Pi Pico 2W e-ink typewriter async investigation

These wrappers allow display operations to yield control to other tasks,
preventing UI blocking during long e-ink refresh operations (typically 300-2000ms)
"""

import uasyncio as asyncio
import utime


async def wait_for_busy_async(epd, check_interval_ms=50):
    """
    Asynchronously wait for EPD busy pin to go low (ready)

    The EPD busy pin is HIGH when display is updating, LOW when idle.
    This function polls the pin and yields control between checks.

    Args:
        epd: EPD_4in2 display object
        check_interval_ms: How often to check busy pin (default 50ms)

    Workflow:
        1. Check busy pin
        2. If HIGH (busy), sleep for interval and repeat
        3. If LOW (ready), return
    """
    while epd.digital_read(epd.busy_pin) == 1:  # HIGH = busy, LOW = idle
        await asyncio.sleep_ms(check_interval_ms)


async def send_command_async(epd, command):
    """
    Send command to EPD with async yield

    Args:
        epd: EPD_4in2 display object
        command: Command byte to send
    """
    epd.send_command(command)
    await asyncio.sleep_ms(0)  # Yield to allow other tasks to run


async def send_data_async(epd, data):
    """
    Send data to EPD with async yield

    Args:
        epd: EPD_4in2 display object
        data: Data byte(s) to send
    """
    if isinstance(data, int):
        epd.send_data(data)
    else:
        epd.send_data1(data)
    await asyncio.sleep_ms(0)  # Yield to allow other tasks to run


async def refresh_partial_async(epd, buffer=None):
    """
    Perform partial refresh asynchronously

    Partial refresh is faster (~300ms) but lower quality.
    Used for typing and cursor updates.

    Args:
        epd: EPD_4in2 display object
        buffer: Optional buffer (uses epd.buffer_1Gray if None)

    Timing:
        - Command/data transmission: ~50ms
        - Display update: ~300ms (blocking on busy pin)
        - Total: ~350ms with async yields

    Workflow:
        1. Configure partial update mode
        2. Send buffer to display RAM
        3. Trigger update command
        4. Wait for busy pin (async)
    """
    if buffer is None:
        buffer = epd.buffer_1Gray

    # Configure partial update mode
    await send_command_async(epd, 0x3C)  # BorderWavefrom
    await send_data_async(epd, 0x80)

    await send_command_async(epd, 0x21)  # Display update control
    await send_data_async(epd, 0x00)
    await send_data_async(epd, 0x00)

    await send_command_async(epd, 0x3C)  # BorderWavefrom
    await send_data_async(epd, 0x80)

    # Set display window (full screen)
    await send_command_async(epd, 0x44)
    await send_data_async(epd, 0x00)
    await send_data_async(epd, 0x31)

    await send_command_async(epd, 0x45)
    await send_data_async(epd, 0x00)
    await send_data_async(epd, 0x00)
    await send_data_async(epd, 0x2B)
    await send_data_async(epd, 0x01)

    await send_command_async(epd, 0x4E)
    await send_data_async(epd, 0x00)

    await send_command_async(epd, 0x4F)
    await send_data_async(epd, 0x00)
    await send_data_async(epd, 0x00)

    # Write buffer to display RAM
    await send_command_async(epd, 0x24)  # WRITE_RAM
    await send_data_async(epd, buffer)

    # Trigger display update
    await send_command_async(epd, 0x22)  # Display Update Control
    await send_data_async(epd, 0xFF)     # Partial update sequence
    await send_command_async(epd, 0x20)  # Activate Display Update Sequence

    # Wait for display to finish (async - yields to other tasks)
    await wait_for_busy_async(epd)


async def refresh_full_async(epd, buffer=None):
    """
    Perform full refresh asynchronously

    Full refresh is slower (~2000ms) but higher quality.
    Used for page changes and screen clearing.

    Args:
        epd: EPD_4in2 display object
        buffer: Optional buffer (uses epd.buffer_1Gray if None)

    Timing:
        - Command/data transmission: ~50ms
        - Display update: ~2000ms (blocking on busy pin)
        - Total: ~2050ms with async yields

    Workflow:
        1. Send buffer to both RAM buffers (current and previous)
        2. Trigger full update command
        3. Wait for busy pin (async)
    """
    if buffer is None:
        buffer = epd.buffer_1Gray

    # Write to RAM buffer 1
    await send_command_async(epd, 0x24)
    await send_data_async(epd, buffer)

    # Write to RAM buffer 2 (for ghosting prevention)
    await send_command_async(epd, 0x26)
    await send_data_async(epd, buffer)

    # Trigger full display update
    await send_command_async(epd, 0x22)  # Display Update Control
    await send_data_async(epd, 0xF7)     # Full update sequence
    await send_command_async(epd, 0x20)  # Activate Display Update Sequence

    # Wait for display to finish (async - yields to other tasks)
    await wait_for_busy_async(epd)


async def refresh_fast_async(epd, buffer=None):
    """
    Perform fast refresh asynchronously

    Fast refresh is medium speed (~1000ms) with acceptable quality.
    Good for frequent updates without full ghosting cycles.

    Args:
        epd: EPD_4in2 display object
        buffer: Optional buffer (uses epd.buffer_1Gray if None)

    Timing:
        - Command/data transmission: ~50ms
        - Display update: ~1000ms (blocking on busy pin)
        - Total: ~1050ms with async yields
    """
    if buffer is None:
        buffer = epd.buffer_1Gray

    # Write to both RAM buffers
    await send_command_async(epd, 0x24)
    await send_data_async(epd, buffer)

    await send_command_async(epd, 0x26)
    await send_data_async(epd, buffer)

    # Trigger fast display update
    await send_command_async(epd, 0x22)  # Display Update Control
    await send_data_async(epd, 0xC7)     # Fast update sequence
    await send_command_async(epd, 0x20)  # Activate Display Update Sequence

    # Wait for display to finish (async)
    await wait_for_busy_async(epd)


async def clear_display_async(epd):
    """
    Clear display to white asynchronously

    Args:
        epd: EPD_4in2 display object

    Timing:
        - Buffer fill: instant
        - Display update: ~2000ms (full refresh)
    """
    # Clear framebuffer to white
    epd.image1Gray.fill(0xFF)
    await asyncio.sleep_ms(0)  # Yield

    # Perform full refresh to display white screen
    await refresh_full_async(epd)


async def render_text_async(epd, page_chars):
    """
    Render text characters to framebuffer asynchronously

    This only updates the framebuffer - display refresh must be called separately.

    Args:
        epd: EPD_4in2 display object
        page_chars: List of (x, y, char) tuples

    Yields periodically to prevent blocking during large text rendering
    """
    # Clear buffer to white
    epd.image1Gray.fill(0xFF)
    await asyncio.sleep_ms(0)

    # Render each character
    char_count = 0
    for x, y, ch in page_chars:
        if ch not in '\n':
            epd.image1Gray.text(ch, x, y, epd.black)
            char_count += 1

            # Yield every 50 characters to prevent blocking
            if char_count % 50 == 0:
                await asyncio.sleep_ms(0)


async def render_cursor_async(epd, x, y):
    """
    Render cursor at specified position asynchronously

    Cursor is drawn as a horizontal line below character position.

    Args:
        epd: EPD_4in2 display object
        x: X position in pixels
        y: Y position in pixels
    """
    from editor_base import CHAR_WIDTH, CHAR_HEIGHT

    # Draw cursor as horizontal line
    epd.image1Gray.fill_rect(x, y + CHAR_HEIGHT - 2, CHAR_WIDTH, 2, epd.black)
    await asyncio.sleep_ms(0)


# Async display task manager
class DisplayQueue:
    """
    Queue-based display manager for async operations

    Manages display refresh requests and throttling to prevent
    excessive refresh commands during rapid typing.
    """

    def __init__(self, epd, throttle_ms=500):
        """
        Initialize display queue

        Args:
            epd: EPD_4in2 display object
            throttle_ms: Minimum time between refreshes (default 500ms)
        """
        self.epd = epd
        self.throttle_ms = throttle_ms
        self.queue = asyncio.Queue(maxsize=1)
        self.last_refresh_time = 0
        self.pending_refresh = False

    async def request_refresh(self, refresh_type='partial', buffer=None):
        """
        Request a display refresh

        Args:
            refresh_type: 'partial', 'full', or 'fast'
            buffer: Optional buffer to use

        Returns:
            True if refresh was queued, False if already pending
        """
        if self.queue.full():
            return False  # Already have pending refresh

        try:
            self.queue.put_nowait((refresh_type, buffer))
            return True
        except:
            return False

    async def process_refreshes(self):
        """
        Background task to process display refreshes with throttling

        This task runs continuously, processing refresh requests
        while respecting the throttle interval.
        """
        while True:
            try:
                # Wait for refresh request
                refresh_type, buffer = await self.queue.get()

                # Check throttle
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_refresh_time)
                if elapsed < self.throttle_ms:
                    # Wait for throttle period to expire
                    await asyncio.sleep_ms(self.throttle_ms - elapsed)

                # Perform refresh
                if refresh_type == 'partial':
                    await refresh_partial_async(self.epd, buffer)
                elif refresh_type == 'full':
                    await refresh_full_async(self.epd, buffer)
                elif refresh_type == 'fast':
                    await refresh_fast_async(self.epd, buffer)

                self.last_refresh_time = utime.ticks_ms()

            except Exception as e:
                print(f"Display refresh error: {e}")
                await asyncio.sleep_ms(100)


# ASCII art for async display workflow
"""
ASYNC DISPLAY WORKFLOW:
=======================

Main Task                Display Queue Task
    |                           |
    v                           v
Modify buffer          Wait for refresh request
    |                           |
    v                           |
Request refresh    -->    Queue refresh
    |                           |
Continue UI                     v
    |                    Check throttle timer
    |                           |
    v                           v
Handle keys            Perform async refresh
    |                    (yields during busy wait)
    |                           |
    v                           v
(non-blocking)          Update complete
                                |
                                v
                        Ready for next refresh


TIMING COMPARISON:
==================

Partial Refresh (async):
  - Sync:  300ms blocking
  - Async: 300ms total, yields every 50ms
  - UI responsiveness: ~50ms max delay

Full Refresh (async):
  - Sync:  2000ms blocking
  - Async: 2000ms total, yields every 50ms
  - UI responsiveness: ~50ms max delay

Keyboard scan (10ms) can run during any refresh operation!
"""
