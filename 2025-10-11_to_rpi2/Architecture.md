# Linson Writers Deck - System Architecture
**Dual Raspberry Pi Pico 2W Master-Slave E-ink Typewriter**

## System Overview

The Linson Writers Deck uses two Raspberry Pi Pico 2W microcontrollers in a Master-Slave architecture, optimized for dual-core processing on each device. This design eliminates display refresh blocking and provides zero-latency keyboard input.

---

## Physical Hardware Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LINSON WRITERS DECK HARDWARE                    │
└─────────────────────────────────────────────────────────────────────┘

    MASTER PICO 2W (RP2350)              SLAVE PICO 2W (RP2350)
    ┌─────────────────────┐              ┌─────────────────────┐
    │   Core 0: Main      │              │   Core 0: UART RX   │
    │   Core 1: File I/O  │              │   Core 1: Display   │
    └─────────────────────┘              └─────────────────────┘
            │                                      │
            │ I2C1 (GP2/GP3)                      │ SPI1 (GP10/GP11)
            ↓                                      ↓
    ┌───────────────┐                      ┌─────────────────┐
    │   TCA8418     │                      │  Waveshare 4.2" │
    │   Keyboard    │                      │   E-ink Display │
    │   Controller  │                      │   (400x300px)   │
    │   (10x8 matrix)│                      │                 │
    └───────────────┘                      └─────────────────┘
            ↑                                      ↑
            │ INT: GP20                            │ BUSY: GP16
            │ RST: GP21                            │ DC: GP14
                                                   │ RST: GP15
                                                   │ CS: GP13

    Master GP8 (TX) ────────────────────→ Slave GP8 (RX)
    Master GP9 (RX) ←──────────────────── Slave GP9 (TX)
                   UART @ 115200 baud

    Both Picos share common GND
    Each powered independently (USB or battery)
```

---

## Software Architecture - Dual-Core Design

### MASTER PICO (Keyboard & Logic Controller)

```
┌──────────────────────────────────────────────────────────────────┐
│                        MASTER PICO 2W                            │
│                         (RP2350)                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      CORE 0 (Primary)                      │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  ┌──────────────┐      ┌──────────────┐                  │ │
│  │  │ Async Task:  │      │ Async Task:  │                  │ │
│  │  │  Keyboard    │      │    Text      │                  │ │
│  │  │   Scanner    │─────→│  Processor   │                  │ │
│  │  │ (TCA8418)    │      │              │                  │ │
│  │  └──────────────┘      └──────────────┘                  │ │
│  │         │                      │                          │ │
│  │         │ key_event_queue      │                          │ │
│  │         ↓                      ↓                          │ │
│  │  ┌──────────────┐      ┌──────────────┐                  │ │
│  │  │ Async Task:  │      │ Async Task:  │                  │ │
│  │  │     UART     │      │     Idle     │                  │ │
│  │  │  Commander   │      │   Monitor    │                  │ │
│  │  │ (to Slave)   │      │  (Power Mgmt)│                  │ │
│  │  └──────────────┘      └──────────────┘                  │ │
│  │         │                      │                          │ │
│  │         │                      │ triggers                 │ │
│  │         ↓                      ↓                          │ │
│  │  ┌──────────────────────────────────┐                    │ │
│  │  │      Shared State (Locked)       │                    │ │
│  │  │  • text_buffer[]                 │                    │ │
│  │  │  • cursor_index                  │                    │ │
│  │  │  • display_dirty flag            │                    │ │
│  │  │  • file_dirty flag               │                    │ │
│  │  │  • current_page_index            │                    │ │
│  │  └──────────────────────────────────┘                    │ │
│  │         │                      ↑                          │ │
│  │         │ read                 │ write                    │ │
│  │         ↓                      │                          │ │
│  │  ┌──────────────────────────────────┐                    │ │
│  │  │  FileOperationQueue (Core 1)     │                    │ │
│  │  │  Enqueue: save_request           │                    │ │
│  │  │           upload_request         │                    │ │
│  │  └──────────────────────────────────┘                    │ │
│  │                                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │                                    │
│                             │ thread-safe queue                  │
│                             ↓                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    CORE 1 (Background)                     │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │          file_io_worker_thread()                     │ │ │
│  │  │                                                      │ │ │
│  │  │  while True:                                         │ │ │
│  │  │    operation = queue.dequeue(timeout=1s)            │ │ │
│  │  │                                                      │ │ │
│  │  │    if operation.type == SAVE:                       │ │ │
│  │  │      acquire text_buffer_lock                       │ │ │
│  │  │      copy = text_buffer[:]                          │ │ │
│  │  │      release text_buffer_lock                       │ │ │
│  │  │      write_to_file(copy)  # NON-BLOCKING            │ │ │
│  │  │                                                      │ │ │
│  │  │    elif operation.type == UPLOAD:                   │ │ │
│  │  │      wifi_connect()                                 │ │ │
│  │  │      transfer_file()     # NON-BLOCKING             │ │ │
│  │  │                                                      │ │ │
│  │  │    update heartbeat_timestamp                       │ │ │
│  │  │    gc.collect()                                     │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### SLAVE PICO (Display Controller)

```
┌──────────────────────────────────────────────────────────────────┐
│                        SLAVE PICO 2W                             │
│                         (RP2350)                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      CORE 0 (UART)                         │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │         UART Command Receiver Loop                   │ │ │
│  │  │                                                      │ │ │
│  │  │  while True:                                         │ │ │
│  │  │    json_cmd = uart.readline()  # blocking read      │ │ │
│  │  │    command = parse_json(json_cmd)                   │ │ │
│  │  │                                                      │ │ │
│  │  │    if command.type == RENDER_TEXT:                  │ │ │
│  │  │      display_queue.enqueue(command, priority=MED)   │ │ │
│  │  │      send_ack()  # immediate response               │ │ │
│  │  │                                                      │ │ │
│  │  │    elif command.type == POWER_OFF:                  │ │ │
│  │  │      display_queue.enqueue(command, priority=HIGH)  │ │ │
│  │  │      send_ack()                                     │ │ │
│  │  │                                                      │ │ │
│  │  │    elif command.type == SCREENSAVER:                │ │ │
│  │  │      display_queue.enqueue(command, priority=LOW)   │ │ │
│  │  │      send_ack()                                     │ │ │
│  │  │                                                      │ │ │
│  │  │    elif command.type == STATUS:                     │ │ │
│  │  │      send_status_response()  # instant reply        │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │         │                                                 │ │
│  │         │ enqueue commands                                │ │
│  │         ↓                                                 │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │       DisplayCommandQueue (Core 1)                   │ │ │
│  │  │  • Priority-ordered queue                            │ │ │
│  │  │  • Deduplication (latest RENDER wins)                │ │ │
│  │  │  • Max size: 5 commands                              │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │                                    │
│                             │ thread-safe queue                  │
│                             ↓                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  CORE 1 (Display Worker)                   │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │        display_worker_thread()                       │ │ │
│  │  │                                                      │ │ │
│  │  │  while True:                                         │ │ │
│  │  │    command = queue.dequeue(timeout=1s)              │ │ │
│  │  │                                                      │ │ │
│  │  │    # Throttle: min 200ms between renders            │ │ │
│  │  │    time_since_last = ticks_diff(now, last_render)   │ │ │
│  │  │    if time_since_last < 200:                        │ │ │
│  │  │      sleep(200 - time_since_last)                   │ │ │
│  │  │                                                      │ │ │
│  │  │    acquire display_lock                             │ │ │
│  │  │                                                      │ │ │
│  │  │    if command.type == RENDER_TEXT:                  │ │ │
│  │  │      layout = TextLayout.calculate(command.text)    │ │ │
│  │  │      draw_text_to_framebuffer(layout)               │ │ │
│  │  │      epd.EPD_4IN2_V2_PartialDisplay()  # 1.5s       │ │ │
│  │  │                                                      │ │ │
│  │  │    elif command.type == SCREENSAVER:                │ │ │
│  │  │      draw_screensaver("Linson")                     │ │ │
│  │  │      epd.EPD_4IN2_V2_Display_Fast()   # full 4s     │ │ │
│  │  │                                                      │ │ │
│  │  │    elif command.type == POWER_OFF:                  │ │ │
│  │  │      epd.Sleep()                                    │ │ │
│  │  │      enter_low_power_wait()                         │ │ │
│  │  │                                                      │ │ │
│  │  │    release display_lock                             │ │ │
│  │  │    last_render = ticks_ms()                         │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### Keypress to Display Update Path

```
TIME →

User           Master Core 0      Master Core 1      UART        Slave Core 0       Slave Core 1         Display
 │                  │                  │              │                │                 │                │
 │ press 'A'        │                  │              │                │                 │                │
 ├────────────────→ │                  │              │                │                 │                │
 │                  │ read TCA8418    │              │                │                 │                │
 │                  │ INT pin (GP20)  │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │              [10ms scan latency]    │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │                  │ get_character()  │              │                │                 │                │
 │                  │ → 'A' + shift    │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │                  │ insert_char('A') │              │                │                 │                │
 │                  │ acquire lock     │              │                │                 │                │
 │                  │ text_buffer += 'A'              │                │                 │                │
 │                  │ cursor_index++   │              │                │                 │                │
 │                  │ release lock     │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │              [5ms processing]       │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │                  │ mark display_dirty=true         │                │                 │                │
 │                  │                  │              │                │                 │                │
 │                  │ construct JSON:  │              │                │                 │                │
 │                  │ {"cmd":"RENDER", │              │                │                 │                │
 │                  │  "txt":"...A...", │             │                │                 │                │
 │                  │  "cursor":42}    │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │                  │ send UART ───────┼────────────→ │ receive JSON  │                 │                │
 │                  │                  │              │ parse command  │                 │                │
 │                  │                  │              │                │                 │                │
 │              [2ms UART @ 115200]    │              │                │                 │                │
 │                  │                  │              │                │                 │                │
 │                  │                  │              │ enqueue_render()                 │                │
 │                  │                  │              │ (priority: MED)                  │                │
 │                  │                  │              │                │                 │                │
 │                  │ ←─ ACK ───────────┼─────────────┤ send_ack()    │                 │                │
 │                  │                  │              │                │                 │                │
 │            [Total: ~20ms to ACK]    │              │         [queue depth: 1]        │                │
 │                  │                  │              │                │                 │                │
 │                  │                  │              │                │ dequeue cmd     │                │
 │                  │                  │              │                │ wait for prev   │                │
 │                  │                  │              │                │ refresh done    │                │
 │                  │                  │              │                │                 │                │
 │                  │                  │              │                │ acquire lock    │                │
 │                  │                  │              │                │ calculate_lines()                │
 │                  │                  │              │                │ render_to_fb()  │                │
 │                  │                  │              │                │                 │                │
 │                  │                  │              │                │      [200ms layout calc]         │
 │                  │                  │              │                │                 │                │
 │                  │                  │              │                │ EPD_Partial()   │                │
 │                  │                  │              │                │ ────────────────┼──────────────→ │
 │                  │                  │              │                │                 │  SPI transfer  │
 │                  │                  │              │                │                 │  + e-ink refresh
 │                  │                  │              │                │                 │                │
 │                  │                  │              │                │  [1500ms display refresh time]   │
 │                  │                  │              │                │                 │                │
 │                  │                  │              │                │ release lock    │                │
 │                  │                  │              │                │ mark done       │    visible     │
 │                  │                  │              │                │                 │   change 'A'   │
 │                  │                  │              │                │                 │ ←──────────────┤
 │                  │                  │              │                │                 │                │
│            [Total end-to-end: ~1.7s from keypress to visible]                                          │
│                                                                                                          │
│  During 1.7s display refresh, Master Core 0 continues scanning keyboard →                              │
│  User can type next character immediately (buffered in key_event_queue)                                │
```

### File Save Operation Path (Dual-Core)

```
TIME →

Master Core 0      Master Core 1      Flash Storage
     │                  │                  │
     │ 2s auto-save     │                  │
     │ timer expires    │                  │
     │                  │                  │
     │ enqueue_save()   │                  │
     │ acquire lock     │                  │
     │ create SaveOp    │                  │
     │ copy filename    │                  │
     │ release lock     │                  │
     │                  │                  │
     │ push to queue ──→│ dequeue_save()   │
     │ continue keyboard│ acquire lock     │
     │ scanning         │ copy text_buffer │
     │                  │ release lock     │
     │ ← NO BLOCKING    │                  │
     │                  │ [lock held <5ms] │
     │                  │                  │
     │ user typing...   │ open file ──────→│
     │ 'B' 'C' 'D'      │ write(copy)      │
     │ buffered OK      │                  │
     │                  │                  │
     │                  │ [file write 50ms]│
     │                  │                  │
     │                  │ close file       │
     │                  │ sync ────────────→│
     │ still typing...  │                  │
     │                  │ mark clean       │
     │                  │ update heartbeat │
     │                  │ gc.collect()     │
     │                  │                  │
     │ no interruption  │ back to queue    │
     │ from save        │ wait             │
     │                  │                  │
```

### Power Management Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   POWER MANAGEMENT STATE MACHINE            │
└─────────────────────────────────────────────────────────────┘

    ┌──────────┐
    │  ACTIVE  │  ← typing, keyboard input, display updates
    │          │
    └────┬─────┘
         │
         │ 120s idle (no keypresses)
         ↓
    ┌──────────┐
    │SCREENSAVER│  ← Master → SHOW_SCREENSAVER → Slave
    │          │     Slave Core 1 renders "Linson" centered
    └────┬─────┘     Display stays on (no power save)
         │
         │ 180s more idle (300s total)
         ↓
    ┌──────────┐
    │ POWER OFF│  ← Master → POWER_OFF → Slave
    │          │     Slave: epd.Sleep() + lightsleep wait
    └────┬─────┘     Master: lightsleep(INT pin wake)
         │
         │ any keypress (TCA8418 INT goes low)
         │ GP20 interrupt wakes Master
         ↓
    ┌──────────┐
    │   WAKE   │  ← Master wakes from lightsleep
    │          │     Master → WAKE_UP → Slave
    └────┬─────┘     Slave wakes Core 0 → resumes UART
         │           Slave Core 1 wakes display
         │
         │ restore last display state
         ↓
    ┌──────────┐
    │  ACTIVE  │  ← back to normal operation
    │          │
    └──────────┘

Manual power-off: Fn + Q held for 2s → immediate POWER_OFF
```

---

## Code File Map

### Master Pico (rpi1/ directory)

| File                | Core | Functions | Complexity | Description |
|---------------------|------|-----------|------------|-------------|
| `main.py`           | 0    | `main()` <br> `keyboard_scanner()` <br> `text_processor()` <br> `uart_commander()` <br> `idle_monitor()` <br> `file_menu()` <br> `save_current_page()` <br> `load_pages()` <br> `insert_char()` <br> `delete_char()` | High | Main entry point and Core 0 async event loop. Coordinates keyboard, text processing, UART, power management. Classes: `TextLayout`, `PageManager` |
| `main.py`           | 1    | `file_io_worker_thread()` <br> `process_save_operation()` <br> `process_upload_operation()` | Medium | Core 1 background thread. Handles file I/O and network operations without blocking keyboard. Thread lifecycle and error recovery. |
| `master_queue.py`   | Both | `FileOperationQueue` <br> `.enqueue_save()` <br> `.enqueue_upload()` <br> `.dequeue()` | Medium | Thread-safe queue for Core 0 → Core 1 communication. Lock-protected with priority handling. |
| `tca8418.py`        | 0    | `TCA8418` class <br> `.scan_keys()` <br> `.read_key_event()` <br> `.get_character()` <br> `.configure()` <br> `.hardware_reset()` | High | I2C keyboard controller driver. 10x8 matrix mapping, shift combinations, interrupt handling. |
| `config.py`         | -    | WiFi credentials <br> Todoist token | Low | Configuration constants |
| `wifi_transfer.py`  | 1    | `upload_file()` <br> `connect_wifi()` | Medium | HTTP file upload, WiFi management. Called from Core 1 only. |
| `todoist_upload.py` | 1    | `upload_to_todoist()` <br> `authenticate()` | Medium | Todoist API integration. Called from Core 1 only. |
| `boot.py`           | -    | Initialization <br> GC setup | Low | Boot configuration, imports main.py |

### Slave Pico (rpi2/ directory)

| File                | Core | Functions | Complexity | Description |
|---------------------|------|-----------|------------|-------------|
| `main.py`           | 0    | `main()` <br> `uart_receiver_loop()` <br> `parse_command()` <br> `handle_render()` <br> `handle_power()` <br> `send_ack()` | Medium | UART command receiver on Core 0. Parses JSON, enqueues display operations, sends acknowledgments. |
| `main.py`           | 1    | `display_worker_thread()` <br> `render_text()` <br> `render_screensaver()` <br> `power_off_display()` | High | Core 1 display rendering worker. Dequeues commands, calculates layout, drives e-ink display. Implements throttling and deduplication. |
| `slave_queue.py`    | Both | `DisplayCommandQueue` <br> `.enqueue_render()` <br> `.enqueue_power()` <br> `.dequeue()` <br> `.deduplicate()` | Medium | Thread-safe priority queue for Core 0 → Core 1 communication. Intelligent deduplication for RENDER commands. |
| `display42.py`      | 1    | `EPD_4in2` class <br> `.EPD_4IN2_V2_Init_Fast()` <br> `.EPD_4IN2_V2_Display_Fast()` <br> `.EPD_4IN2_V2_PartialDisplay()` <br> `.Clear()` <br> `.Sleep()` | High | Waveshare 4.2" e-ink display driver. SPI communication, full/partial refresh, power management. Timing-critical operations. |
| `TextLayout`        | 1    | `.get_word_boundaries()` <br> `.calculate_lines()` <br> `.get_screen_pages()` <br> `.get_cursor_screen_pos()` | High | Word wrapping and pagination engine. CPU-intensive calculations done on Core 1 to not block UART receiver. |

### Shared / Test Files

| File                       | Description |
|----------------------------|-------------|
| `tests/test_master_dual_core.py` | Unit tests for Master threading, locks, queue |
| `tests/test_slave_dual_core.py`  | Unit tests for Slave threading, display queue |
| `tests/test_integration_dual_core.py` | End-to-end tests with both Picos |
| `tests/test_text_layout.py` | TextLayout algorithm tests |
| `tests/test_uart_protocol.py` | UART JSON protocol validation tests |
| `Reference Docs/` | RP2350 datasheets, MicroPython docs, e-ink specs |

---

## Threading Model

### Lock Hierarchy (Master)

To prevent deadlocks, locks must be acquired in this order if multiple needed:

1. `text_buffer_lock` - Protects text content array
2. `file_state_lock` - Protects file metadata (filename, dirty flags, page index)
3. `ui_state_lock` - Protects UI state (menu active, paged view)

**Rule:** Never hold lock during I/O operation (file, network, UART, display)

### Lock Hierarchy (Slave)

1. `display_lock` - Protects EPD driver during SPI operations (high priority)
2. `framebuffer_lock` - Protects frame buffer during text rendering

### Queue Characteristics

**Master FileOperationQueue:**
- Max size: 10 operations
- Types: SAVE (priority: HIGH), UPLOAD (priority: LOW)
- Overflow policy: Drop oldest LOW priority operation
- Timeout: 1s on dequeue (allows heartbeat update)

**Slave DisplayCommandQueue:**
- Max size: 5 commands
- Types: RENDER_TEXT (MED), SCREENSAVER (LOW), POWER_OFF (HIGH), WAKE_UP (HIGH), STATUS (CRITICAL)
- Overflow policy: Deduplicate RENDER commands (keep latest)
- Timeout: 1s on dequeue (allows health check)

---

## UART Protocol Specification

### Message Format (JSON)

```json
{
  "cmd": "RENDER_TEXT",
  "seq": 42,
  "txt": "Hello World",
  "cursor": 5,
  "page": 0
}
```

### Commands (Master → Slave)

| Command | Fields | Description |
|---------|--------|-------------|
| `RENDER_TEXT` | txt, cursor, page | Render text with cursor at position |
| `SHOW_SCREENSAVER` | - | Display "Linson" screensaver |
| `POWER_OFF` | - | Put display to sleep mode |
| `WAKE_UP` | - | Wake display from sleep |
| `CLEAR` | - | Clear display (full white) |
| `STATUS` | - | Request status from Slave |

### Responses (Slave → Master)

```json
{
  "ack": "RENDER_TEXT",
  "seq": 42,
  "status": "OK"
}
```

```json
{
  "status": "IDLE",
  "queue_depth": 2,
  "last_render_ms": 1500
}
```

### Error Handling

- Master timeout: 500ms for ACK, retry 3x, then log error
- Slave error: Send NACK with error code
- Sequence numbers detect missing commands
- CRC16 optional for integrity checking (future enhancement)

---

## Performance Characteristics

### Measured Latencies (Target vs Actual - TBD after hardware testing)

| Operation | Target | Current (Est) | Notes |
|-----------|--------|----------|-------|
| Keypress → Core 0 event | < 20ms | 10ms | TCA8418 INT + I2C read |
| Text insertion | < 5ms | 3ms | Array append + lock |
| UART command send | < 10ms | 5ms | JSON + 115200 baud |
| Display queue enqueue | < 1ms | 0.5ms | Lock + queue insert |
| Layout calculation | < 200ms | 150ms | CPU-bound on Core 1 |
| E-ink partial refresh | 1500ms | 1500ms | Hardware limitation |
| E-ink full refresh | 4000ms | 4000ms | Hardware limitation |
| File save (1KB) | < 100ms | 50ms | Flash write on Core 1 |
| End-to-end (key → visible) | < 2000ms | ~1700ms | Total pipeline |

### Throughput

- Typing speed: 120 WPM sustained (10 chars/sec) without lag
- UART bandwidth: ~10KB/sec (limited by 115200 baud)
- Display refresh rate: Max 1 refresh per 2s (throttled)
- File save rate: Max 1 save per 2s (auto-save interval)

### Memory Usage (RP2350 has 520KB total)

| Component | RAM Usage | Notes |
|-----------|-----------|-------|
| MicroPython runtime | ~150KB | Base interpreter |
| Core 0 stack | ~4KB | Main thread |
| Core 1 stack | ~4KB | Worker thread |
| Text buffer (10KB doc) | ~10KB | Single page in memory |
| Display framebuffer | ~15KB | 400x300 @ 1bpp |
| Queue buffers | ~2KB | Command queues |
| Code + globals | ~50KB | All modules loaded |
| **Total (typical)** | **~235KB** | ~45% of available RAM |
| Available for documents | ~285KB | Headroom for large files |

---

## Critical Sections and Race Conditions

### Identified Race Conditions and Mitigations

1. **Text buffer concurrent access**
   - **Risk:** Core 0 modifies while Core 1 reads for save
   - **Mitigation:** text_buffer_lock, copy buffer to Core 1 thread (max 5ms lock hold)

2. **Display state during UART flood**
   - **Risk:** Queue overflow from rapid Master commands
   - **Mitigation:** Deduplication logic, max queue size 5, drop oldest RENDER

3. **Display busy during refresh**
   - **Risk:** New render attempt while e-ink busy
   - **Mitigation:** Display worker checks BUSY pin (GP16), waits up to 3s, then forces reset

4. **Core 1 crash/hang detection**
   - **Risk:** Worker thread exception leaves system unresponsive
   - **Mitigation:** Heartbeat timestamp checked by Core 0, auto-restart after 15s stale

5. **Lock inversion deadlock**
   - **Risk:** Core 0 acquires A then B, Core 1 acquires B then A
   - **Mitigation:** Strict lock ordering hierarchy enforced, documented in code

---

## Future Optimizations

1. **Differential Display Updates** - Send only changed text regions over UART
2. **Frame Buffer Compression** - Compress framebuffer before transfer (if UART becomes bottleneck)
3. **Predictive Text Layout** - Pre-calculate next page layout during current page render
4. **Adaptive Refresh Rate** - Faster partial refresh during typing bursts, slower full refresh periodically
5. **UART Bandwidth Optimization** - Binary protocol instead of JSON for high-frequency commands
6. **Core Affinity Optimization** - Pin specific ISRs to specific cores for lower interrupt latency
7. **DMA for SPI** - Use RP2350 DMA controller for display SPI transfers (frees CPU during refresh)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-15 | Scrum Master | Initial architecture documentation for dual-core optimization project |

---

**Document Status:** Living document, update as architecture evolves during implementation.
