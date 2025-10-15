# Single Pico 2W Investigation

## Objective

Investigate whether a single Raspberry Pi Pico 2W can achieve non-blocking operation for the Linson Writers Deck e-ink typewriter by comparing two approaches:

1. **Approach A: Threading** - Dual-core with `_thread` module
2. **Approach B: Async** - Single-core with `uasyncio` module

## Project Structure

```
single_pico2w/
├── README.md                 # This file
├── hardware_pico.py          # Pin definitions and hardware abstraction
├── boot.py                   # Boot sequence for Pico 2W
├── config.py                 # WiFi credentials and API tokens
├── display42.py              # Waveshare 4.2" e-ink driver (migrated)
├── tca8418.py                # TCA8418 keyboard controller driver
├── editor_base.py            # Shared utilities (TextLayout, PageManager, etc.)
├── display_async.py          # Async display operation wrappers
├── file_async.py             # Async file operation wrappers
├── main_threaded.py          # Approach A: Threading implementation
├── main_async.py             # Approach B: Async implementation
├── benchmark.py              # Performance testing framework
└── stability_test.py         # Long-running stability tests
```

## Hardware Pin Assignments (Pico 2W)

### E-ink Display (SPI1)
- **SCK** (Clock): GP10
- **MOSI** (Data): GP11
- **CS** (Chip Select): GP13
- **DC** (Data/Command): GP14
- **RST** (Reset): GP15
- **BUSY** (Status): GP16

### Keyboard (I2C0)
- **SDA**: GP4
- **SCL**: GP5
- **INT** (Interrupt): GP6
- **RST** (Reset): GP7

### Power
- **Button**: GP22

**Note**: GP23-GP25 are reserved for WiFi (CYW43439 chip)

## Quick Start

### 1. Upload Files to Pico 2W

Copy all files to your Pico 2W using Thonny, rshell, or mpremote:

```bash
# Using mpremote
mpremote connect /dev/ttyACM0 cp *.py :
```

### 2. Test Threading Approach

```python
import main_threaded
main_threaded.main()
```

Press **Esc** to exit.

### 3. Test Async Approach

```python
import main_async
main_async.main()
```

Press **Esc** to exit.

### 4. Run Benchmarks

```python
import benchmark
benchmark.main()
```

This will test both approaches and generate a comparison report.

### 5. Run Stability Tests

```python
import stability_test
stability_test.main()
```

Runs 10-minute stability tests on both approaches (edit duration for 24-hour tests).

## Approach A: Threading (Dual-Core)

### Architecture
```
Core 0 (Main Thread)              Core 1 (Worker Thread)
├─ Keyboard scanning              ├─ Display refresh operations
├─ Text buffer management         ├─ File save operations
├─ UI rendering                   ├─ WiFi uploads
├─ Menu navigation                └─ Background tasks
└─ Command processing
         │                                  │
         └──────────► Queue ◄───────────────┘
                (Thread-safe communication)
```

### Expected Characteristics
- ✓ True parallelism (separate cores)
- ✓ Display refresh doesn't block keyboard
- ✗ Known GC stability issues with MicroPython threading
- ✗ Higher memory overhead (~60KB for dual stacks)
- ⚠️  May crash after hours/days of operation

### Usage
```python
from main_threaded import main
main()
```

## Approach B: Async (Single-Core)

### Architecture
```
Core 0 (Async Event Loop)
├─ keyboard_scanner_task()      [10ms interval]
├─ display_manager_task()       [checks display_dirty]
├─ file_saver_task()            [2s interval]
├─ idle_monitor_task()          [1s interval]
└─ stats_monitor_task()         [5s interval]
         │
         └── Cooperative Multitasking ──┘
             (All tasks yield control)
```

### Expected Characteristics
- ✓ Proven stable (no threading issues)
- ✓ Lower memory overhead (~40KB)
- ✓ Simpler debugging (single execution context)
- ✓ Good enough for I/O-bound operations
- ✗ No true parallelism

### Usage
```python
from main_async import main
main()
```

## Key Differences

| Feature | Threading (Approach A) | Async (Approach B) |
|---------|------------------------|---------------------|
| **Cores Used** | Core 0 + Core 1 | Core 0 only |
| **Concurrency** | Parallel (true) | Cooperative |
| **Stability** | ⚠️ GC issues likely | ✓ Stable |
| **Memory** | ~60KB overhead | ~40KB overhead |
| **Blocking** | Display doesn't block | Display yields control |
| **Complexity** | Higher (locks, queues) | Lower (no locks) |
| **Debugging** | Harder (race conditions) | Easier (linear flow) |

## Testing Methodology

### Performance Metrics
1. **Typing Latency**: Time from keypress to character visible
2. **Throughput**: Maximum typing speed (characters/minute)
3. **Display Blocking**: Can you type during refresh?
4. **Memory Usage**: Peak allocation and leaks
5. **Refresh Time**: Actual e-ink update duration
6. **File Save Blocking**: Does saving freeze UI?

### Stability Metrics
1. **Time to First Crash**: How long until failure?
2. **Exception Count**: Number of errors over time
3. **Memory Leaks**: Free memory trend
4. **GC Collections**: Garbage collection frequency
5. **Operations Count**: Total work completed

### Expected Results

Based on MicroPython community feedback and architectural analysis:

**Threading Approach:**
- Fast initial performance
- True non-blocking (separate cores)
- **BUT**: Likely to crash within hours due to GC issues on Core 1
- Memory corruption possible

**Async Approach:**
- Slightly higher latency (cooperative vs parallel)
- Still non-blocking (proper yielding)
- **Stable**: Runs 24/7 without crashes
- Lower memory footprint

## Comparison Report Template

After testing, document findings:

### Performance Winner: _______
- Typing latency: _______ ms (Threading) vs _______ ms (Async)
- Throughput: _______ cpm (Threading) vs _______ cpm (Async)
- Display blocking: _______ (Threading) vs _______ (Async)

### Stability Winner: _______
- Threading stability: _______ (PASS/FAIL)
- Async stability: _______ (PASS/FAIL)
- Memory leaks: _______ (Threading) vs _______ (Async)

### Recommendation: _______
Choose based on:
1. **If Threading is stable**: Use if true parallelism needed
2. **If Async is stable**: Use for production (likely winner)
3. **If both unstable**: Investigate further or use dual-Pico architecture

## Migration from ESP32-S3

Key changes made from Reference Docs/working_reference/:

1. **Removed ESP32-specific code**:
   - `import esp`, `import esp32`
   - `esp32.wake_on_ext0()`
   - ESP32 reset codes

2. **Updated pin assignments**:
   - ESP32 pins → Pico GP pins
   - Avoided GP23-25 (WiFi reserved)

3. **Updated SPI initialization**:
   - ESP32 style → Pico unified initialization
   - All parameters in single SPI() call

4. **Added hardware abstraction**:
   - `hardware_pico.py` centralizes all pin definitions
   - Easy to modify for different hardware

5. **Improved code organization**:
   - Split monolithic main.py into modules
   - Separated async wrappers
   - Class-based utilities

## Next Steps

1. **Test on actual hardware**
   - Upload to Pico 2W
   - Run both approaches
   - Collect real performance data

2. **Run stability tests**
   - 24-hour continuous operation
   - Monitor memory and exceptions
   - Document crashes

3. **Make recommendation**
   - Compare objective metrics
   - Consider stability vs performance
   - Choose production approach

4. **Optimize chosen approach**
   - Fine-tune timing parameters
   - Reduce memory usage if needed
   - Add production features

## Known Limitations

### Threading Approach
- **GC Instability**: Core 1 garbage collection is broken in MicroPython
- **Memory Corruption**: No memory protection between cores
- **Debugging Difficulty**: Race conditions hard to reproduce

### Async Approach
- **Not True Parallelism**: CPU-bound tasks still block
- **Cooperative**: Tasks must explicitly yield control
- **E-ink Refresh**: Still takes 800ms-2s (hardware limitation)

## Conclusion

This investigation provides objective data to determine if a single Pico 2W can handle the e-ink typewriter workload with acceptable non-blocking behavior. Based on community consensus and architectural analysis, **async approach is expected to win** due to MicroPython threading stability issues.

However, real-world testing will provide definitive proof.

---

**Project**: Linson Writers Deck - Single Pico 2W Investigation
**Date**: 2025-10-15
**Hardware**: Raspberry Pi Pico 2W, Waveshare 4.2" EPD, TCA8418 Keyboard
**MicroPython**: v1.20+ required
