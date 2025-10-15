# Linson Writers Deck - Quick Reference Guide
**Dual-Core Optimization Project**

## File Structure

```
/Users/duanetomlinson/projects/linson_works/2025-10-11_to_rpi2/
│
├── linson_project.csv              ← PROJECT TRACKING (50 tasks)
├── PROJECT_PLAN_SUMMARY.md         ← This summary document
├── QUICK_REFERENCE.md              ← You are here
├── Architecture.md                 ← System architecture with ASCII diagrams
├── update_notes.json               ← Historical project updates
├── CLAUDE.md                       ← Project guidelines
│
├── rpi1/                           ← MASTER PICO (Keyboard)
│   ├── main.py                     ← Main keyboard/logic controller
│   ├── tca8418.py                  ← Keyboard driver (I2C)
│   ├── master_queue.py             ← TO BE CREATED (TASK-009)
│   ├── test_master.py              ← Hardware test
│   └── test_master_unit.py         ← Unit test
│
├── rpi2/                           ← SLAVE PICO (Display)
│   ├── main.py                     ← Main display controller
│   ├── display42.py                ← E-ink driver (SPI)
│   ├── slave_queue.py              ← TO BE CREATED (TASK-010)
│   ├── test_slave.py               ← Hardware test
│   └── test_slave_unit.py          ← Unit test
│
├── tests/                          ← TEST SUITES
│   ├── test_text_layout.py
│   ├── test_uart_protocol.py
│   ├── test_master_dual_core.py    ← TO BE CREATED (TASK-026)
│   ├── test_slave_dual_core.py     ← TO BE CREATED (TASK-027)
│   └── test_integration_dual_core.py ← TO BE CREATED (TASK-028)
│
├── config.py                       ← WiFi credentials, Todoist token
├── wifi_transfer.py                ← WiFi file upload
├── todoist_upload.py               ← Todoist integration
├── boot.py                         ← Boot configuration
│
└── Reference Docs/                 ← Hardware specs, datasheets
    └── working_reference/          ← Original ESP32 code
```

## Hardware Pin Assignments

### Master Pico 2W (Keyboard Controller)

| Component | Function | GPIO | Physical Pin | Notes |
|-----------|----------|------|--------------|-------|
| TCA8418 | I2C SDA | GP2 | Pin 4 | I2C1 bus |
| TCA8418 | I2C SCL | GP3 | Pin 5 | I2C1 bus |
| TCA8418 | Interrupt | GP20 | Pin 26 | Falling edge |
| TCA8418 | Reset | GP21 | Pin 27 | Active low |
| UART to Slave | TX | GP8 | Pin 11 | 115200 baud |
| UART from Slave | RX | GP9 | Pin 12 | 115200 baud |

### Slave Pico 2W (Display Controller)

| Component | Function | GPIO | Physical Pin | Notes |
|-----------|----------|------|--------------|-------|
| E-ink Display | SPI SCK | GP10 | Pin 14 | SPI1 bus |
| E-ink Display | SPI MOSI | GP11 | Pin 15 | SPI1 bus |
| E-ink Display | Chip Select | GP13 | Pin 17 | Active low |
| E-ink Display | Data/Command | GP14 | Pin 19 | Low=cmd, High=data |
| E-ink Display | Reset | GP15 | Pin 20 | Active low |
| E-ink Display | Busy | GP16 | Pin 21 | High=busy |
| UART from Master | RX | GP8 | Pin 11 | 115200 baud |
| UART to Master | TX | GP9 | Pin 12 | 115200 baud |

## Core Assignments (Planned)

### Master Pico - Dual Core Architecture

**Core 0 (Primary)**
- Async event loop (uasyncio)
- Keyboard scanning (TCA8418 I2C polling)
- Text buffer management
- UART command transmission to Slave
- Power management (idle detection)
- UI state (menu, paged view)

**Core 1 (Background)**
- File I/O worker thread (_thread)
- Auto-save operations (every 2s)
- WiFi file uploads
- Todoist API calls
- Garbage collection

### Slave Pico - Dual Core Architecture

**Core 0 (UART Receiver)**
- UART command receiver loop
- JSON command parser
- Command queue enqueue
- ACK/NACK responses
- Power state management

**Core 1 (Display Worker)**
- Display worker thread (_thread)
- Command queue dequeue
- TextLayout calculations
- E-ink refresh operations (1.5-4s)
- Display throttling (min 200ms between refreshes)
- Command deduplication

## Common Commands

### Update Task Status
```bash
# Open the CSV file and update the row:
# 1. Change status field: Not Started → In Progress → Completed
# 2. Add notes with timestamp
# 3. Update updated_date to current date
# 4. Add actual_effort if completed
```

### Read Project Files
```bash
# View project tracking
cat linson_project.csv

# View architecture
cat Architecture.md

# View update history
cat update_notes.json

# View quick reference
cat QUICK_REFERENCE.md
```

### Test on Hardware
```bash
# Master Pico test
cd rpi1
python test_master.py

# Slave Pico test
cd rpi2
python test_slave.py

# Unit tests
cd tests
python test_text_layout.py
```

## Task Status Quick View

### Completed (8 tasks)
- TASK-001: Project initialization ✓
- TASK-002: Codebase analysis ✓
- TASK-003: Hardware specs review ✓
- TASK-004: Pin assignments ✓
- TASK-008: Implementation plan ✓
- TASK-038: Architecture documentation ✓

### In Progress (1 task)
- TASK-005: Master dual-core design (IN PROGRESS)

### Next Up (Critical Path)
1. TASK-005: Complete Master architecture design
2. TASK-006: Complete Slave architecture design
3. TASK-007: Complete async design patterns
4. TASK-009: Implement Master queue system
5. TASK-010: Implement Slave queue system
6. TASK-011: Refactor Master for dual-core
7. TASK-014: Refactor Slave for dual-core

## Performance Targets

| Metric | Current (Est) | Target | Task |
|--------|---------------|--------|------|
| Typing latency | ~2000ms | <500ms | TASK-042 |
| Keyboard blocked during save | YES | NO | TASK-011 |
| Throughput | 30-40 cpm | 120+ cpm | TASK-030 |
| Memory overhead | 0KB | <10KB | TASK-031 |
| Display refresh | 1500ms | 1500ms | Hardware limit |

## Key Concepts

### Lock Hierarchy (Master)
```
1. text_buffer_lock      (highest priority)
2. file_state_lock
3. ui_state_lock         (lowest priority)
```
Rule: Always acquire in this order to prevent deadlocks

### Lock Hierarchy (Slave)
```
1. display_lock          (highest priority)
2. framebuffer_lock      (lowest priority)
```

### Queue Sizes
- Master FileOperationQueue: 10 operations
- Slave DisplayCommandQueue: 5 commands

### UART Commands (Master → Slave)
- `RENDER_TEXT`: Update display with new text + cursor
- `SHOW_SCREENSAVER`: Display "Linson" screensaver
- `POWER_OFF`: Put display to sleep
- `WAKE_UP`: Wake display from sleep
- `CLEAR`: Clear display to white
- `STATUS`: Request status info

### Power Management Timing
- 2 minutes idle → Screensaver
- 5 minutes idle → Auto power off (lightsleep)
- Any key press → Wake up

## Troubleshooting

### Issue: Task blocked on dependencies
**Solution**: Check dependencies field in CSV, complete prerequisite tasks first

### Issue: Not sure what to work on next
**Solution**: Filter CSV for Status="Pending" AND Dependencies are all Completed, sort by Priority (Critical > High > Medium > Low)

### Issue: Need to understand system architecture
**Solution**: Read Architecture.md for visual diagrams and data flow

### Issue: Task taking longer than estimated
**Solution**: Add notes to task explaining challenges, may need to break into subtasks

### Issue: Hardware not responding
**Solution**: Check pin assignments in QUICK_REFERENCE.md, verify wiring matches Physical Pin column

## Development Workflow

1. **Choose Task**: Pick next task from critical path
2. **Update Status**: Mark task as "In Progress" in CSV
3. **Read Dependencies**: Review notes from prerequisite tasks
4. **Implement**: Write code following Architecture.md design
5. **Test**: Run unit tests, hardware tests
6. **Document**: Add inline comments, update notes
7. **Complete**: Mark task as "Completed", add actual_effort, update updated_date
8. **Next Task**: Move to next dependency or critical path item

## Resources

### Documentation
- `Architecture.md` - System design, ASCII diagrams, data flows
- `PROJECT_PLAN_SUMMARY.md` - Full project plan, phases, dependencies
- `linson_project.csv` - Task tracking (50 tasks)
- `update_notes.json` - Historical changes
- `CLAUDE.md` - Project guidelines and requirements

### Reference
- `/Reference Docs/` - RP2350 datasheets, MicroPython docs
- `/Reference Docs/working_reference/` - Original ESP32 code

### Code Files
- `rpi1/main.py` - Master keyboard controller
- `rpi2/main.py` - Slave display controller
- `rpi1/tca8418.py` - Keyboard driver
- `rpi2/display42.py` - E-ink driver

## Contact

For task updates or questions, update the notes field in linson_project.csv with:
- Timestamp
- Issue description
- Resolution or question
- Next steps

Project managed by: Scrum Master role
Development by: Various specialized roles (see PROJECT_PLAN_SUMMARY.md)

---

**Last Updated**: 2025-10-15
**Project Phase**: Planning Complete - Implementation Starting
**Next Milestone**: Complete TASK-005, 006, 007 (Design Phase)
