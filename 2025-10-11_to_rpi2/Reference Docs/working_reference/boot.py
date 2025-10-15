#will want to import and run main code.

# boot.py - This file is executed on every boot (including wake-boot from deepsleep)

import esp
import gc
import machine

# Disable debug output to save power (optional)
esp.osdebug(None)

# Run garbage collection to free up memory
gc.collect()

# Optional: Set CPU frequency (240MHz is default, 160MHz saves power)
# machine.freq(160000000)

# Optional: Print boot information
print("=== Writer's Deck Boot ===")
print(f"Free memory: {gc.mem_free()} bytes")
print(f"CPU Frequency: {machine.freq()} Hz")

# Check reset cause
reset_cause = machine.reset_cause()
print(f"Reset cause: {reset_cause}")

if reset_cause == machine.DEEPSLEEP_RESET:
    print("Woke from deep sleep")
elif reset_cause == machine.SOFT_RESET:
    print("Soft reset")
elif reset_cause == machine.PWRON_RESET:
    print("Power on reset")
elif reset_cause == machine.HARD_RESET:
    print("Hard reset")

# Import and run main.py
try:
    print("Starting Writer's Deck...")
    import main
    main.main()
except Exception as e:
    print(f"Failed to start main program: {e}")
    # Optional: Log error to file
    try:
        with open("boot_error.txt", "a") as f:
            import utime
            f.write(f"\n[{utime.time()}] Boot error: {e}\n")
    except:
        pass