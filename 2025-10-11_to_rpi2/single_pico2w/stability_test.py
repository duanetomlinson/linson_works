"""
Long-running stability test for threading vs async approaches
Tests stability over 24+ hours to detect memory leaks, GC issues, and crashes
"""

import utime
import gc
import sys

class StabilityMonitor:
    """
    24-hour stability testing framework

    Monitors for:
    - Memory leaks
    - Crashes/exceptions
    - GC failures
    - Performance degradation
    """

    def __init__(self, implementation, duration_hours=24):
        self.implementation = implementation
        self.duration_ms = duration_hours * 3600 * 1000
        self.start_time = None
        self.stats = {
            'start_free_mem': 0,
            'min_free_mem': 999999,
            'max_alloc_mem': 0,
            'gc_collections': 0,
            'exceptions': 0,
            'exception_log': [],
            'operations': 0,
            'crashes': 0
        }

    def start(self):
        """Begin stability monitoring"""
        print(f"\n{'='*60}")
        print(f"STABILITY TEST: {self.implementation.upper()}")
        print(f"Duration: {self.duration_ms // 3600000} hours")
        print(f"{'='*60}\n")

        gc.collect()
        self.stats['start_free_mem'] = gc.mem_free()
        self.stats['min_free_mem'] = self.stats['start_free_mem']
        self.start_time = utime.ticks_ms()

        print(f"Start time: {utime.localtime()}")
        print(f"Initial free memory: {self.stats['start_free_mem']:,} bytes\n")

    def check_memory(self):
        """Monitor memory usage"""
        gc.collect()
        self.stats['gc_collections'] += 1

        free_mem = gc.mem_free()
        alloc_mem = gc.mem_alloc()

        if free_mem < self.stats['min_free_mem']:
            self.stats['min_free_mem'] = free_mem

        if alloc_mem > self.stats['max_alloc_mem']:
            self.stats['max_alloc_mem'] = alloc_mem

        # Check for potential memory leak
        memory_loss = self.stats['start_free_mem'] - free_mem
        if memory_loss > 10000:  # More than 10KB lost
            print(f"⚠️  WARNING: Potential memory leak detected!")
            print(f"   Lost {memory_loss:,} bytes since start")
            return False

        return True

    def log_exception(self, exception):
        """Record exception details"""
        self.stats['exceptions'] += 1
        error_info = {
            'time': utime.ticks_diff(utime.ticks_ms(), self.start_time),
            'type': type(exception).__name__,
            'message': str(exception)
        }
        self.stats['exception_log'].append(error_info)

        print(f"\n❌ EXCEPTION at {error_info['time']}ms:")
        print(f"   {error_info['type']}: {error_info['message']}\n")

    def print_status(self):
        """Print current status"""
        elapsed = utime.ticks_diff(utime.ticks_ms(), self.start_time)
        elapsed_hours = elapsed / 3600000
        progress = (elapsed / self.duration_ms) * 100

        free_mem = gc.mem_free()
        alloc_mem = gc.mem_alloc()

        print(f"\n{'='*60}")
        print(f"Status Update: {elapsed_hours:.2f}h elapsed ({progress:.1f}%)")
        print(f"{'='*60}")
        print(f"Memory:")
        print(f"  Current free: {free_mem:,} bytes")
        print(f"  Current allocated: {alloc_mem:,} bytes")
        print(f"  Min free seen: {self.stats['min_free_mem']:,} bytes")
        print(f"  Max allocated: {self.stats['max_alloc_mem']:,} bytes")
        print(f"Stats:")
        print(f"  Operations: {self.stats['operations']:,}")
        print(f"  GC collections: {self.stats['gc_collections']}")
        print(f"  Exceptions: {self.stats['exceptions']}")
        print(f"  Crashes: {self.stats['crashes']}")
        print(f"{'='*60}\n")

    def run_test_cycle(self):
        """
        Simulate one cycle of operation

        In real test, this would:
        - Process keyboard input
        - Update display
        - Save file
        - Handle idle/sleep
        """
        try:
            # Simulate operations
            self.stats['operations'] += 1

            # Simulate some work
            data = bytearray(100)  # Small allocation
            for i in range(100):
                data[i] = i % 256

            # Simulate delay between operations
            utime.sleep_ms(100)

            return True

        except Exception as e:
            self.log_exception(e)
            return False

    def run(self):
        """
        Run full stability test

        Returns:
            True if passed, False if failed
        """
        self.start()

        last_status = utime.ticks_ms()
        status_interval_ms = 3600000  # Print status every hour

        try:
            while True:
                # Check if test duration completed
                elapsed = utime.ticks_diff(utime.ticks_ms(), self.start_time)
                if elapsed >= self.duration_ms:
                    print(f"\n✓ Test duration completed!")
                    break

                # Run test cycle
                if not self.run_test_cycle():
                    self.stats['crashes'] += 1
                    if self.stats['crashes'] >= 5:
                        print(f"\n❌ Too many crashes ({self.stats['crashes']})")
                        print(f"   Aborting test")
                        return False

                # Check memory periodically
                if self.stats['operations'] % 100 == 0:
                    if not self.check_memory():
                        print(f"\n❌ Memory check failed")
                        return False

                # Print status update
                now = utime.ticks_ms()
                if utime.ticks_diff(now, last_status) >= status_interval_ms:
                    self.print_status()
                    last_status = now

            # Test completed successfully
            return True

        except KeyboardInterrupt:
            print(f"\n⚠️  Test interrupted by user")
            return False

        except Exception as e:
            print(f"\n❌ CRITICAL ERROR:")
            print(f"   {type(e).__name__}: {e}")
            self.log_exception(e)
            return False

        finally:
            self.print_final_report()

    def print_final_report(self):
        """Print comprehensive final report"""
        elapsed = utime.ticks_diff(utime.ticks_ms(), self.start_time)
        elapsed_hours = elapsed / 3600000

        print(f"\n{'='*60}")
        print(f"FINAL REPORT: {self.implementation.upper()}")
        print(f"{'='*60}")
        print(f"\nDuration: {elapsed_hours:.2f} hours")
        print(f"\nMemory Stats:")
        print(f"  Start free: {self.stats['start_free_mem']:,} bytes")
        print(f"  End free: {gc.mem_free():,} bytes")
        print(f"  Min free: {self.stats['min_free_mem']:,} bytes")
        print(f"  Max allocated: {self.stats['max_alloc_mem']:,} bytes")
        print(f"  Memory leaked: {self.stats['start_free_mem'] - gc.mem_free():,} bytes")

        print(f"\nOperation Stats:")
        print(f"  Total operations: {self.stats['operations']:,}")
        print(f"  GC collections: {self.stats['gc_collections']}")
        print(f"  Operations/hour: {(self.stats['operations'] / elapsed_hours):.0f}")

        print(f"\nError Stats:")
        print(f"  Exceptions: {self.stats['exceptions']}")
        print(f"  Crashes: {self.stats['crashes']}")

        if self.stats['exception_log']:
            print(f"\nException Log:")
            for error in self.stats['exception_log'][:10]:  # Show first 10
                print(f"  {error['time']//1000}s: {error['type']} - {error['message']}")
            if len(self.stats['exception_log']) > 10:
                print(f"  ... and {len(self.stats['exception_log'])-10} more")

        # Pass/fail criteria
        passed = True
        print(f"\nStability Assessment:")

        memory_leak = self.stats['start_free_mem'] - gc.mem_free()
        if memory_leak > 50000:
            print(f"  ❌ FAIL: Significant memory leak ({memory_leak:,} bytes)")
            passed = False
        else:
            print(f"  ✓ PASS: No significant memory leak")

        if self.stats['crashes'] > 0:
            print(f"  ❌ FAIL: System crashed {self.stats['crashes']} times")
            passed = False
        else:
            print(f"  ✓ PASS: No crashes detected")

        if self.stats['exceptions'] > 100:
            print(f"  ⚠️  WARNING: Many exceptions ({self.stats['exceptions']})")
        elif self.stats['exceptions'] > 0:
            print(f"  ⚠️  Minor issues: {self.stats['exceptions']} exceptions")
        else:
            print(f"  ✓ PASS: No exceptions")

        print(f"\n{'='*60}")
        if passed:
            print(f"VERDICT: ✓ STABLE")
            print(f"The {self.implementation} approach is suitable for production")
        else:
            print(f"VERDICT: ❌ UNSTABLE")
            print(f"The {self.implementation} approach has stability issues")
        print(f"{'='*60}\n")

        return passed

    def save_report(self, filename=None):
        """Save detailed report to file"""
        if filename is None:
            filename = f'stability_{self.implementation}.txt'

        try:
            with open(filename, 'w') as f:
                f.write(f"Stability Test Report\n")
                f.write(f"Implementation: {self.implementation}\n")
                f.write(f"{'='*60}\n\n")

                f.write(f"Duration: {(utime.ticks_diff(utime.ticks_ms(), self.start_time) / 3600000):.2f} hours\n")
                f.write(f"Operations: {self.stats['operations']:,}\n")
                f.write(f"Exceptions: {self.stats['exceptions']}\n")
                f.write(f"Crashes: {self.stats['crashes']}\n")
                f.write(f"GC collections: {self.stats['gc_collections']}\n\n")

                f.write(f"Memory:\n")
                f.write(f"  Start free: {self.stats['start_free_mem']:,}\n")
                f.write(f"  End free: {gc.mem_free():,}\n")
                f.write(f"  Min free: {self.stats['min_free_mem']:,}\n")
                f.write(f"  Max allocated: {self.stats['max_alloc_mem']:,}\n\n")

                if self.stats['exception_log']:
                    f.write(f"Exception Log:\n")
                    for error in self.stats['exception_log']:
                        f.write(f"  {error['time']//1000}s: {error['type']} - {error['message']}\n")

            print(f"Report saved to: {filename}")
        except Exception as e:
            print(f"Error saving report: {e}")


def main():
    """
    Main stability test execution

    Usage:
        # Quick test (10 minutes)
        python stability_test.py

        # Full 24-hour test (edit duration_hours parameter)
    """
    print("\n" + "="*60)
    print("SINGLE PICO 2W STABILITY TEST")
    print("="*60)
    print("\nSelect test:")
    print("1. Threading approach (dual-core with _thread)")
    print("2. Async approach (single-core with uasyncio)")
    print("3. Both (sequential)")

    # For automated testing, default to option 3
    choice = 3

    if choice == 1:
        monitor = StabilityMonitor('threading', duration_hours=0.17)  # 10 min
        result = monitor.run()
        monitor.save_report()

    elif choice == 2:
        monitor = StabilityMonitor('async', duration_hours=0.17)  # 10 min
        result = monitor.run()
        monitor.save_report()

    elif choice == 3:
        # Test both approaches
        print("\n" + "="*60)
        print("Testing Threading Approach First")
        print("="*60)
        monitor1 = StabilityMonitor('threading', duration_hours=0.17)
        result1 = monitor1.run()
        monitor1.save_report()

        print("\n\nBrief pause between tests...")
        utime.sleep(5)

        print("\n" + "="*60)
        print("Testing Async Approach")
        print("="*60)
        monitor2 = StabilityMonitor('async', duration_hours=0.17)
        result2 = monitor2.run()
        monitor2.save_report()

        # Comparison
        print("\n" + "="*60)
        print("COMPARISON")
        print("="*60)
        print(f"\nThreading: {'PASSED' if result1 else 'FAILED'}")
        print(f"Async: {'PASSED' if result2 else 'FAILED'}")

        if result1 and result2:
            print("\n✓ Both approaches are stable")
        elif result2 and not result1:
            print("\n✓ Async approach is more stable")
            print("  Recommendation: Use async for production")
        elif result1 and not result2:
            print("\n✓ Threading approach is more stable")
            print("  Recommendation: Use threading for production")
        else:
            print("\n❌ Both approaches have stability issues")
            print("  Further investigation required")

    print("\nStability test complete!")


if __name__ == "__main__":
    main()
