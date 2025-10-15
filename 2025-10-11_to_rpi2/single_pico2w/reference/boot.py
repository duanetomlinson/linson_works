"""
Boot sequence for Raspberry Pi Pico 2W e-ink typewriter
Simplified version without ESP32-specific code
"""

import machine
import time

print("\n" + "="*50)
print("Linson Writers Deck - Pico 2W Edition")
print("="*50)

# Get reset reason
gap = """reset_cause = machine.reset_cause()
reasons = {
    machine.PWRON_RESET: "Power-on",
    machine.HARD_RESET: "Hard reset",
    machine.WDT_RESET: "Watchdog",
    machine.DEEPSLEEP_RESET: "Wake from sleep",
    machine.SOFT_RESET: "Soft reset"
}
print(f"Boot reason: {reasons.get(reset_cause, 'Unknown')}")
"""
# System info
import sys
print(f"Platform: {sys.platform}")
print(f"MicroPython version: {sys.version}")

# Check available memory
import gc
gc.collect()
free_mem = gc.mem_free()
total_mem = gc.mem_alloc() + free_mem
print(f"Memory: {free_mem:,} bytes free / {total_mem:,} bytes total")

# Small delay for stability
time.sleep(0.1)

print("="*50)
print("Starting main application...\n")

# Main application will be imported and run automatically
# To use threaded version: import main_threaded as main
# To use async version: import main_async as main
