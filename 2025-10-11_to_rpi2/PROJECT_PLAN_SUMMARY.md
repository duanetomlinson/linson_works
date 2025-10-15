# Linson Writers Deck - Dual-Core Optimization Project Plan
**Project Tracking Created: 2025-10-15**

## Executive Summary

A comprehensive project plan has been created for optimizing the Linson Writers Deck e-ink typewriter to fully leverage the dual-core RP2350 processors in both Raspberry Pi Pico 2W devices. The plan includes 50 structured tasks covering analysis, design, implementation, testing, and deployment phases.

## Project Context

### Current State (Completed)
- **Hardware Migration**: Successfully migrated from ESP32-S3 to dual Raspberry Pi Pico 2W Master-Slave architecture
- **Master Pico**: Handles keyboard input via TCA8418 (I2C1 on GP2/GP3)
- **Slave Pico**: Handles e-ink display via Waveshare 4.2" (SPI1 on GP10/GP11)
- **Communication**: UART at 115200 baud on GP8/GP9 between devices
- **Functional**: Basic typing, file operations, display refresh working

### Optimization Objective
- **Primary Goal**: Leverage dual cores within each Pico to eliminate blocking operations
- **Master Optimization**: Core 0 for keyboard scanning, Core 1 for file I/O and WiFi operations
- **Slave Optimization**: Core 0 for UART receiver, Core 1 for display rendering
- **Additional Goal**: Implement async/await patterns for cleaner event coordination
- **Expected Outcome**: 50% reduction in input latency, 2-3x increase in typing throughput, zero keyboard lag during file saves or display refreshes

## Project Structure

### Phase 1: Analysis and Planning (Tasks 1-8) - COMPLETED
Status: 5 of 8 tasks completed

**Completed:**
- TASK-001: Project initialization and architecture review
- TASK-002: Codebase analysis and blocking operation identification
- TASK-003: RP2350 hardware specifications review
- TASK-004: Pin assignment documentation
- TASK-008: Implementation plan creation
- TASK-038: Architectural documentation with ASCII diagrams

**In Progress:**
- TASK-005: Master Pico dual-core architecture design
- TASK-006: Slave Pico dual-core architecture design (blocked on TASK-002)
- TASK-007: Async operation pattern design (blocked on TASK-005)

### Phase 2: Core Infrastructure (Tasks 9-10)
Status: 0 of 2 tasks started

**Objectives:**
- Implement thread-safe queue systems for inter-core communication
- Create Master FileOperationQueue (saves, uploads)
- Create Slave DisplayCommandQueue (render commands, power management)
- Establish lock primitives and message passing protocols

**Key Deliverables:**
- `/rpi1/master_queue.py` - Thread-safe queue for Master Core 0 ↔ Core 1
- `/rpi2/slave_queue.py` - Thread-safe queue for Slave Core 0 ↔ Core 1

### Phase 3: Master Pico Dual-Core Implementation (Tasks 11-13, 22)
Status: 0 of 4 tasks started

**Objectives:**
- Refactor Master main.py for dual-core operation
- Launch Core 1 file I/O worker thread
- Add lock protection for shared state (text_buffer, file metadata)
- Implement Core 1 health monitoring and restart mechanism

**Key Changes:**
- Core 0: Keyboard scanning (no blocking)
- Core 1: File saves, WiFi uploads, Todoist sync
- Lock hierarchy: text_buffer_lock → file_state_lock → ui_state_lock

### Phase 4: Slave Pico Dual-Core Implementation (Tasks 14-16)
Status: 0 of 3 tasks started

**Objectives:**
- Refactor Slave main.py for dual-core operation
- Launch Core 1 display worker thread
- Add lock protection for display resources
- Implement command queue with deduplication and throttling

**Key Changes:**
- Core 0: UART receiver (fast ACK response)
- Core 1: Display rendering (1.5s e-ink refresh)
- Display command deduplication (latest RENDER wins)

### Phase 5: Async Refactoring (Tasks 17-21)
Status: 0 of 5 tasks started

**Objectives:**
- Convert Master Core 0 to async/await event loop
- Create async tasks: keyboard_scanner, text_processor, uart_commander, idle_monitor
- Implement power management with async sleep
- Maintain Core 1 as thread (not async) for I/O operations

**Benefits:**
- Cleaner event coordination than pure threading
- Natural I/O multiplexing
- Simpler error handling
- More pythonic code structure

### Phase 6: Optimization and Polish (Tasks 23-25, 31, 33-36)
Status: 0 of 8 tasks started

**Objectives:**
- UART protocol optimization (compact JSON, differential updates)
- Display command deduplication and throttling
- Partial region update optimization
- Memory usage optimization
- TextLayout algorithm performance improvements
- Bug fixes: newline concatenation, smart backspace, file menu timeout

### Phase 7: Testing and Validation (Tasks 26-30, 40-44)
Status: 0 of 9 tasks started

**Test Levels:**
1. **Unit Tests**: Master dual-core, Slave dual-core, threading, locks
2. **Integration Tests**: End-to-end Master-Slave communication
3. **Hardware Tests**: Physical device validation with oscilloscope/logic analyzer
4. **Performance Tests**: Baseline vs optimized benchmarking
5. **Stress Tests**: 2-hour typing sessions, power cycling, memory stability

**Success Criteria:**
- Sub-500ms average typing latency (keypress to visible)
- No dropped characters at 120 WPM (10 chars/sec)
- Keyboard responsive during file saves and uploads
- No memory leaks over 1-hour session
- Clean power management (2min screensaver, 5min auto-off, fast wake)

### Phase 8: Network Optimization (Tasks 46-47)
Status: 0 of 2 tasks started

**Objectives:**
- WiFi transfer optimization on Core 1
- Todoist upload optimization on Core 1
- Progress indication during uploads
- Streaming transfers for large files

### Phase 9: Reliability and Security (Tasks 32, 48-49)
Status: 0 of 3 tasks started

**Objectives:**
- Comprehensive error handling for dual-core edge cases
- Graceful degradation to single-core fallback mode
- UART protocol validation and security review
- Error code system and user-facing error reporting

### Phase 10: Documentation and UAT (Tasks 37, 39, 45, 50)
Status: 1 of 4 tasks started (TASK-038 completed)

**Objectives:**
- Inline code comments and docstrings
- Update update_notes.json with changes
- Code cleanup (remove obsolete files)
- User acceptance testing with real-world scenarios

## Task Dependencies Visualization

```
Phase 1: Analysis
├─ TASK-001 (DONE) → TASK-002 (DONE) → TASK-005 (IN PROGRESS)
│                                     └→ TASK-006 (PENDING)
│                                     └→ TASK-007 (PENDING)
└─ TASK-003 (DONE) → TASK-004 (DONE)
└─ TASK-008 (DONE)
└─ TASK-038 (DONE)

Phase 2: Infrastructure
├─ TASK-009 (needs TASK-005) → Master queue implementation
└─ TASK-010 (needs TASK-006) → Slave queue implementation

Phase 3: Master Dual-Core
├─ TASK-011 (needs TASK-009, TASK-005) → Master refactor
│   ├→ TASK-012 (needs TASK-011) → File I/O worker
│   └→ TASK-013 (needs TASK-011) → Lock protection
└─ TASK-022 (needs TASK-012, TASK-017) → Health monitoring

Phase 4: Slave Dual-Core
├─ TASK-014 (needs TASK-010, TASK-006) → Slave refactor
│   ├→ TASK-015 (needs TASK-014) → Display worker
│   └→ TASK-016 (needs TASK-014) → Lock protection

Phase 5: Async
└─ TASK-017 (needs TASK-013, TASK-007) → Async main loop
    ├→ TASK-018 (needs TASK-017) → Keyboard scanner
    ├→ TASK-019 (needs TASK-017) → Text processor
    ├→ TASK-020 (needs TASK-017) → UART commander
    └→ TASK-021 (needs TASK-017) → Idle monitor

Phase 6: Optimization
├─ TASK-023 (needs TASK-020) → UART protocol
├─ TASK-024 (needs TASK-015) → Queue deduplication
├─ TASK-025 (needs TASK-015) → Partial updates
├─ TASK-031 (needs TASK-011, TASK-014) → Memory optimization
├─ TASK-033 (needs TASK-002) → TextLayout optimization
├─ TASK-034 (needs TASK-033) → Smart backspace
├─ TASK-035 (needs TASK-033) → Newline bug fix
└─ TASK-036 (needs TASK-021) → Menu timeout

Phase 7: Testing
├─ TASK-026 (needs TASK-011, TASK-013) → Master unit tests
├─ TASK-027 (needs TASK-014, TASK-016) → Slave unit tests
├─ TASK-028 (needs TASK-026, TASK-027) → Integration tests
├─ TASK-029 (needs TASK-028) → Baseline benchmarks
├─ TASK-030 (needs TASK-029, TASK-028) → Post-optimization benchmarks
├─ TASK-040 (needs TASK-011, TASK-012, TASK-013) → Master hardware test
├─ TASK-041 (needs TASK-014, TASK-015, TASK-016) → Slave hardware test
├─ TASK-042 (needs TASK-040, TASK-041) → Latency measurement
├─ TASK-043 (needs TASK-040, TASK-041) → Power management test
└─ TASK-044 (needs TASK-040, TASK-041, TASK-042) → Stress test

Phase 8: Network
├─ TASK-046 (needs TASK-012) → WiFi optimization
└─ TASK-047 (needs TASK-012) → Todoist optimization

Phase 9: Reliability
├─ TASK-032 (needs TASK-022, TASK-028) → Error handling
├─ TASK-048 (needs TASK-032) → Fallback mode
└─ TASK-049 (needs TASK-023) → Security review

Phase 10: Documentation
├─ TASK-037 (needs TASK-011, TASK-014) → Code comments
├─ TASK-039 (needs TASK-030, TASK-037) → Update notes
├─ TASK-045 (needs TASK-030, TASK-040) → Code cleanup
└─ TASK-050 (needs TASK-044, TASK-045) → UAT
```

## Critical Path

The fastest path to working dual-core optimization:

1. **Complete Design** (TASK-005, 006, 007) - 1-2 days
2. **Build Infrastructure** (TASK-009, 010) - 1 day
3. **Master Dual-Core** (TASK-011, 012, 013) - 2-3 days
4. **Slave Dual-Core** (TASK-014, 015, 016) - 2-3 days
5. **Basic Testing** (TASK-040, 041, 042) - 1-2 days
6. **Async Refactor** (TASK-017-021) - 3-4 days
7. **Optimization** (TASK-023-025, 033) - 2-3 days
8. **Full Testing** (TASK-026-030, 043-044) - 3-4 days

**Total Estimated Timeline**: 15-24 days (3-5 weeks)

## Resource Allocation

| Role | Tasks | Estimated Effort |
|------|-------|------------------|
| System Architect | 3 tasks | 3-4 days |
| Core Developer | 20 tasks | 12-15 days |
| Display Engineer | 2 tasks | 2-3 days |
| Algorithm Engineer | 1 task | 1-2 days |
| QA Engineer | 6 tasks | 5-7 days |
| Performance Engineer | 4 tasks | 2-3 days |
| Hardware QA | 5 tasks | 4-6 days |
| Network Engineer | 2 tasks | 2-3 days |
| Reliability Engineer | 2 tasks | 2-3 days |
| Protocol Engineer | 1 task | 1-2 days |
| Security Engineer | 1 task | 1 day |
| Documentation Engineer | 3 tasks | 2-3 days |
| Code Maintainer | 1 task | 0.5 days |
| Product Manager | 1 task | 2-3 days |
| **Total** | **50 tasks** | **~40-60 person-days** |

## Risk Assessment

### High Risk Items
1. **Memory Constraints** (RP2350 has 520KB, threading adds overhead)
   - Mitigation: TASK-031 memory optimization, fallback mode in TASK-048
2. **Display Ghosting** (e-ink partial refresh artifacts)
   - Mitigation: TASK-025 intelligent full refresh scheduling
3. **Lock Contention** (deadlocks or excessive blocking)
   - Mitigation: TASK-013, TASK-016 strict lock hierarchy
4. **UART Bandwidth** (115200 baud may be limiting)
   - Mitigation: TASK-023 protocol optimization, compression

### Medium Risk Items
1. **Core 1 Crash Recovery** - Handled by TASK-022 health monitoring
2. **WiFi Reliability** - Handled by TASK-046, 047 retry logic
3. **Power Management Complexity** - Handled by TASK-021, 043 testing

### Low Risk Items
1. **Code Cleanup** - TASK-045 is low priority
2. **Documentation** - Can be done in parallel with implementation

## Key Performance Indicators (KPIs)

### Pre-Optimization Baseline (Current System)
- Typing latency: ~2000ms (keypress to visible)
- Keyboard blocked during file save: YES
- Keyboard blocked during display refresh: NO (Master-Slave already solves this)
- Throughput: ~30-40 chars/min effective (due to save blocking)

### Post-Optimization Targets
- Typing latency: <500ms (75% improvement)
- Keyboard blocked during file save: NO
- Throughput: 120+ chars/min (10 chars/sec at 120 WPM)
- Memory overhead: <10KB for threading
- Stability: 2-hour clean run without crashes

## Deliverables

### Code Artifacts
1. `/rpi1/master_queue.py` - Master inter-core queue system
2. `/rpi2/slave_queue.py` - Slave inter-core queue system
3. `/rpi1/main.py` - Refactored with dual-core + async
4. `/rpi2/main.py` - Refactored with dual-core display worker
5. `/tests/test_master_dual_core.py` - Master unit tests
6. `/tests/test_slave_dual_core.py` - Slave unit tests
7. `/tests/test_integration_dual_core.py` - Integration tests

### Documentation
1. `Architecture.md` - System architecture with ASCII diagrams (COMPLETED)
2. `Threading_Architecture.md` - Detailed threading model
3. `UART_Protocol.md` - Protocol v2 specification
4. `Performance_Report.md` - Benchmark results
5. `Power_Management.md` - Power consumption analysis
6. `Error_Codes.md` - Error code reference
7. `UAT_Feedback.md` - User acceptance testing results
8. `update_notes.json` - Updated with project changes

## Next Steps

### Immediate Actions (This Week)
1. **Complete design tasks** (TASK-005, 006, 007)
   - Finalize Master Core 0/Core 1 responsibilities
   - Finalize Slave Core 0/Core 1 responsibilities
   - Define async task structure
2. **Build queue infrastructure** (TASK-009, 010)
   - Create master_queue.py with FileOperationQueue
   - Create slave_queue.py with DisplayCommandQueue
3. **Start Master refactor** (TASK-011)
   - Initialize Core 1 thread
   - Test with simple print statements

### Near-Term Actions (Next 2 Weeks)
1. Complete Master dual-core implementation (TASK-011-013)
2. Complete Slave dual-core implementation (TASK-014-016)
3. Hardware validation on physical devices (TASK-040, 041)
4. Measure initial performance gains (TASK-042)

### Mid-Term Actions (Weeks 3-4)
1. Implement async refactoring (TASK-017-021)
2. Optimize UART protocol and display rendering (TASK-023-025)
3. Comprehensive testing (TASK-026-030)
4. Bug fixes and polish (TASK-034-036)

### Long-Term Actions (Week 5+)
1. Network optimization (TASK-046, 047)
2. Error handling and security (TASK-032, 048, 049)
3. Documentation (TASK-037, 039)
4. User acceptance testing (TASK-050)
5. Production release

## Success Metrics

The project will be considered successful when:

1. All 50 tasks marked as Completed in linson_project.csv
2. End-to-end typing latency <500ms (verified by TASK-042)
3. No keyboard lag during file saves (verified by TASK-040)
4. 2-hour stress test passes without crashes (verified by TASK-044)
5. Memory usage <235KB typical (verified by TASK-031)
6. User acceptance testing shows positive feedback (TASK-050)
7. All documentation updated (TASK-037, 039)

## Project Tracking

All tasks are tracked in **linson_project.csv** with the following fields:
- task_id: Unique identifier (TASK-001 through TASK-050)
- task_name: Clear description
- status: Not Started | In Progress | Completed | Blocked | Cancelled
- agent_owner: Responsible party
- priority: Critical | High | Medium | Low
- dependencies: Comma-separated task_ids
- notes: Detailed implementation guidance
- created_date: 2025-10-15
- updated_date: Updated as status changes
- estimated_effort: Small | Medium | Large | XLarge
- actual_effort: Recorded on completion

## Contact and Updates

For task updates, status changes, or to report completion:
- Update the corresponding row in `linson_project.csv`
- Add timestamped notes to the notes field
- Update the updated_date field
- Update status field appropriately

For questions about task dependencies or priorities, consult the project Scrum Master.

---

**Document Created**: 2025-10-15
**Last Updated**: 2025-10-15
**Project Status**: Planning Complete - Ready for Implementation
**Next Review**: After TASK-005, 006, 007 completion
