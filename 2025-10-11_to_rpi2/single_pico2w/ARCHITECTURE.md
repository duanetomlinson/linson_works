# Writer's Deck - Pico 2W Architecture

## Overview
Full-featured e-ink typewriter using Raspberry Pi Pico 2W with dual-core threading architecture for responsive UI.

## File Structure

```
single_pico2w/
├── main_threaded.py      # Main application (dual-core threading)
├── editor_base.py        # Shared utilities (text layout, file ops, menu)
├── display42.py          # E-ink display driver (4.2" EPD)
├── tca8418.py           # Keyboard controller driver
├── hardware_pico.py     # Pico-specific hardware abstraction
├── config.py            # Configuration settings
└── boot.py              # Boot configuration
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Raspberry Pi Pico 2W                         │
│                                                                  │
│  ┌────────────────────────┐    ┌────────────────────────────┐  │
│  │      CORE 0 (Main)     │    │     CORE 1 (Worker)        │  │
│  │                        │    │                             │  │
│  │  • Keyboard Scanning   │    │  • Display Refreshes       │  │
│  │  • Input Processing    │────▶  • File Saves             │  │
│  │  • Text Buffer Updates │    │  • Background Tasks        │  │
│  │  • Display Rendering   │    │                             │  │
│  │  • State Management    │    │  (Blocking operations      │  │
│  │                        │    │   don't freeze UI)         │  │
│  └────────────────────────┘    └────────────────────────────┘  │
│           │                              ▲                      │
│           │                              │                      │
│           ▼                              │                      │
│  ┌──────────────────────────────────────┴────────────────┐    │
│  │            Thread Communication Layer                  │    │
│  │  • Display Queue (5 items)                            │    │
│  │  • File Queue (5 items)                               │    │
│  │  • Thread Locks (text_lock, display_lock)             │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────┐
         │          Hardware Layer                 │
         │                                         │
         │  ┌──────────────┐  ┌────────────────┐ │
         │  │  TCA8418     │  │  EPD 4.2"      │ │
         │  │  Keyboard    │  │  E-ink Display │ │
         │  │  Controller  │  │                 │ │
         │  └──────────────┘  └────────────────┘ │
         │       (I2C)              (SPI)         │
         └────────────────────────────────────────┘
```

## Application State Machine

```
┌──────────────┐
│   STARTUP    │
└──────┬───────┘
       │
       ▼
┌──────────────┐         N key          ┌──────────────┐
│  MENU MODE   │◄─────────────────────────┤  EDITOR MODE │
│              │                          │              │
│ • File List  │  Enter on file           │ • Text Edit  │
│ • Navigate   ├─────────────────────────▶│ • Page Nav   │
│ • Create     │                          │ • Actions    │
│ • Delete     │      Esc                 │              │
└──────┬───────┘◄─────────────────────────└──────┬───────┘
       │                                          │
       │                                          │ PgUp/PgDn
       │                                          │
       │                                          ▼
       │                                  ┌──────────────┐
       │                                  │  PAGE VIEW   │
       │                                  │              │
       │                                  │ • Read-Only  │
       │          Home key                │ • Navigate   │
       └──────────────────────────────────┤ • Review     │
                                          └──────────────┘
```

## Key Features Implementation

### 1. Menu System
```
show_menu()
  └─▶ list_files()
  └─▶ MenuRenderer.render_file_menu()
  └─▶ request_display_refresh('full')

handle_menu_input(key)
  ├─▶ Up/Down: Navigate selection
  ├─▶ Enter: Open file
  ├─▶ N: Create new file
  ├─▶ Backspace/Del: Delete file
  └─▶ Esc: Exit application
```

### 2. Text Editing
```
insert_char(ch)
  └─▶ text_buffer.insert(cursor_index, ch)
  └─▶ mark display_dirty
  └─▶ mark file_dirty

backspace()
  └─▶ text_buffer.pop(cursor_index - 1)
  └─▶ mark display_dirty

delete_word() [Alt+Backspace]
  └─▶ find word boundaries
  └─▶ delete multiple chars
  └─▶ mark display_dirty
```

### 3. Page Navigation
```
Editor Mode:
  PgUp/PgDn ──▶ Enter PAGE_VIEW mode
                 ├─▶ save current page
                 ├─▶ load all pages
                 └─▶ display_page()

Page View Mode:
  PgUp ──▶ Navigate backwards
  PgDn ──▶ Navigate forwards
  Home ──▶ Return to Editor Mode
           └─▶ load_specific_page() if changed
```

### 4. Control Actions
```
Ctrl+S ──▶ action_save()
           └─▶ save_current_page()

Ctrl+O ──▶ action_open()
           ├─▶ save current
           └─▶ show_menu()

Ctrl+N ──▶ action_new()
           ├─▶ create timestamped file
           └─▶ clear text_buffer

Ctrl+R ──▶ action_rename()
           ├─▶ prompt_filename()
           └─▶ os.rename()

Ctrl+D ──▶ action_delete()
           ├─▶ confirm dialog
           └─▶ os.remove()

Ctrl+T ──▶ action_upload_todoist()
           └─▶ [placeholder]
```

### 5. File Operations
```
save_current_page()
  ├─▶ read text_buffer (thread-safe)
  ├─▶ load full file content
  ├─▶ split into pages
  ├─▶ update current page
  ├─▶ merge pages back
  └─▶ request_file_save() [queued to Core 1]

load_previous()
  ├─▶ load file
  ├─▶ split into pages
  ├─▶ get last page
  ├─▶ calculate subpages
  └─▶ load into text_buffer (thread-safe)
```

## Threading Architecture

### Core 0 (Main Thread)
**Responsibilities:**
- Keyboard scanning at 10ms intervals
- Key press processing
- Text buffer manipulation (with locks)
- Display buffer rendering
- State machine management

**Runs at:** ~100Hz (10ms cycle)

### Core 1 (Worker Thread)
**Responsibilities:**
- Display refresh operations (blocking 300-2000ms)
- File save operations (blocking ~20ms)
- Periodic garbage collection

**Throttling:** 500ms minimum between display refreshes

### Communication
```
Core 0                          Core 1
  │                               │
  ├─▶ display_queue.put()        │
  │                               ├─▶ display_queue.get()
  │                               ├─▶ epd.refresh() [BLOCKING]
  │                               └─▶ done
  │                               │
  ├─▶ file_queue.put()           │
  │                               ├─▶ file_queue.get()
  │                               ├─▶ file.write() [BLOCKING]
  │                               └─▶ done
  │                               │
```

### Thread Safety
```python
# Text buffer access
with text_lock:
    text_buffer.insert(cursor_index, ch)
    cursor_index += 1

# Display state access
with display_lock:
    display_dirty = True
```

## Text Layout Engine

### Word Wrapping
```
Text Buffer (linear string)
         │
         ▼
calculate_lines(text, max_width)
  ├─▶ Find word boundaries
  ├─▶ Check if word fits on line
  ├─▶ Wrap to next line if needed
  └─▶ Return: [(x_pos, char), ...] per line
         │
         ▼
get_screen_pages(text, max_width, max_height)
  ├─▶ Calculate lines
  ├─▶ Group lines into pages
  └─▶ Return: [(x, y, char), ...] per page
         │
         ▼
  Display Rendering
```

### Cursor Positioning
```
cursor_index in text_buffer
         │
         ▼
calculate_lines(text[:cursor_index], max_width)
         │
         ▼
Count lines ──▶ Calculate page number
         │
         ▼
Get last line position ──▶ Calculate (x, y)
         │
         ▼
Return: (x, y, page_num)
```

## Page Management

### Explicit Pages vs Subpages
```
File Content
    │
    ├─▶ Split by '\n---\n' ──▶ Explicit Pages (user-created)
    │                           │
    │                           ├─▶ Page 0: "Introduction..."
    │                           ├─▶ Page 1: "Chapter 1..."
    │                           └─▶ Page 2: "Chapter 2..."
    │
    └─▶ get_screen_pages() ───▶ Subpages (auto-wrap)
                                │
                                ├─▶ Page 0, Subpage 0
                                ├─▶ Page 0, Subpage 1
                                ├─▶ Page 1, Subpage 0
                                └─▶ etc.
```

### Page Markers
- **Explicit:** User creates with `Shift+Enter` → inserts `\n---\n`
- **Subpage:** Automatic overflow when text exceeds screen height
- **Navigation:** PgUp/PgDn navigates through both

## Memory Management

### Allocation
```
Text Buffer:     Dynamic list of chars (~1KB per page)
Display Buffer:  Fixed framebuffer (~12KB for 400x300)
Queues:          2 queues × 5 items × ~100 bytes = ~1KB
Locks:           2 locks × minimal overhead
Stack:           ~2KB per thread = ~4KB total
```

### Garbage Collection
- **Core 0:** Manual gc.collect() every 1000 loops
- **Core 1:** Automatic gc.collect() every 5 seconds
- **Strategy:** Minimize object creation in tight loops

## Error Handling

### Exception Logging
```python
try:
    # Risky operation
    save_file()
except Exception as e:
    log_exception(e, "function_name")
    # Continue execution or show error to user
```

### Log File Format
```
[timestamp] function_name: ExceptionType: message
Traceback:
  File "main.py", line X, in function
    statement
```

## Performance Characteristics

### Latency
- **Keyboard scan:** 10ms cycle (responsive)
- **Display refresh:** 500-2000ms (non-blocking on Core 0)
- **File save:** ~20ms (non-blocking on Core 0)
- **Text insert:** <1ms (immediate feedback)

### Throughput
- **Typing speed:** Limited by keyboard, not software
- **Display updates:** ~1-2 per second (throttled)
- **File saves:** ~50 per second (throttled to avoid wear)

## Testing Strategy

### Unit Tests
- Text layout calculations
- Page management logic
- File operations
- Thread safety primitives

### Integration Tests
- Full workflow: Menu → Editor → Save → Menu
- Page navigation across multiple pages
- Control action sequences
- Error recovery scenarios

### Hardware Tests
- E-ink display refresh quality
- Keyboard responsiveness under load
- File system reliability
- Memory stability over time

## Known Limitations

### Current
1. **No WiFi:** Network features not yet implemented
2. **No Todoist:** API integration pending
3. **Simple Status:** Status messages don't auto-clear
4. **No Sleep:** Power management simplified
5. **GC Concerns:** MicroPython GC not fully thread-safe

### Future Enhancements
1. WiFi file transfer to home server
2. Todoist task upload integration
3. Better status message system with timers
4. Deep sleep with wake on keypress
5. Battery monitoring and warnings
6. Cursor movement keys (arrows)
7. Search/find functionality
8. Multiple cursor support

## Porting Notes

### From ESP32 to Pico 2W

**What Worked:**
- Core text editing logic
- File operations
- Menu system
- Page management

**What Changed:**
- Hardware init: ESP32 → Pico GPIO
- Power management: deepsleep → simplified
- Threading: Single core → dual core
- Display: Direct refresh → queued refresh

**What's Missing:**
- WiFi/network (hardware supported, not implemented)
- Deep sleep (different implementation needed)
- RTC wake (different GPIO domain)

## Development Workflow

### Deploy to Pico
```bash
# Copy files to Pico
cp single_pico2w/*.py /Volumes/RPI-RP2/

# Test via REPL
screen /dev/tty.usbmodem* 115200

# Run main
>>> import main_threaded
>>> main_threaded.main()
```

### Debug Tips
1. Check error_log.txt after crashes
2. Monitor memory with gc.mem_free()
3. Use print() liberally (goes to REPL)
4. Test threading with loop_count stats
5. Verify queue sizes don't overflow

## References

- **MicroPython Docs:** https://docs.micropython.org/
- **Pico SDK:** https://github.com/raspberrypi/pico-sdk
- **EPD Display:** Waveshare 4.2" e-Paper
- **TCA8418:** NXP Keyboard Controller
- **ESP32 Reference:** main.py (original implementation)
