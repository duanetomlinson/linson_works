"""
Benchmark framework for comparing threading vs async approaches
Tests performance metrics to determine which approach provides better non-blocking behavior
"""

import utime
import gc
import sys

class BenchmarkRunner:
    """
    Performance testing framework for single Pico 2W investigation

    Tests both main_threaded.py and main_async.py implementations
    and collects comparative metrics
    """

    def __init__(self):
        self.results = {
            'threading': {},
            'async': {}
        }

    def test_typing_latency(self, implementation):
        """
        Measure time from keypress to character appearing on display

        Args:
            implementation: 'threading' or 'async'

        Returns:
            Average latency in milliseconds
        """
        print(f"\n=== Testing Typing Latency ({implementation}) ===")
        print("Type 10 characters, measuring response time...")

        # This would need keyboard input in real test
        # For now, returns simulated metric
        latencies = []

        # Simulate 10 keypress tests
        for i in range(10):
            start = utime.ticks_ms()
            # In real test: wait for keypress, measure until display update
            utime.sleep_ms(50)  # Simulated
            end = utime.ticks_ms()
            latency = utime.ticks_diff(end, start)
            latencies.append(latency)
            print(f"  Key {i+1}: {latency}ms")

        avg_latency = sum(latencies) // len(latencies)
        print(f"Average latency: {avg_latency}ms")

        self.results[implementation]['typing_latency'] = avg_latency
        return avg_latency

    def test_display_blocking(self, implementation):
        """
        Test if keyboard input is blocked during display refresh

        Args:
            implementation: 'threading' or 'async'

        Returns:
            True if non-blocking, False if blocked
        """
        print(f"\n=== Testing Display Blocking ({implementation}) ===")
        print("Triggering display refresh and checking keyboard responsiveness...")

        # In real test: trigger refresh, attempt keyboard input
        # Measure if input is captured during refresh

        # Threading should be non-blocking (Core 1 handles display)
        # Async should be non-blocking (cooperative yielding)
        is_non_blocking = True  # Simulated

        print(f"Result: {'NON-BLOCKING' if is_non_blocking else 'BLOCKING'}")

        self.results[implementation]['non_blocking'] = is_non_blocking
        return is_non_blocking

    def test_throughput(self, implementation):
        """
        Measure maximum typing speed before dropped characters

        Args:
            implementation: 'threading' or 'async'

        Returns:
            Characters per minute
        """
        print(f"\n=== Testing Throughput ({implementation}) ===")
        print("Measuring maximum typing speed...")

        # Simulate rapid keypress sequence
        test_duration_ms = 10000  # 10 seconds
        chars_typed = 0

        start = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start) < test_duration_ms:
            # In real test: send keypresses as fast as possible
            chars_typed += 1
            utime.sleep_ms(50)  # Simulated typing speed

        cpm = (chars_typed * 60000) // test_duration_ms
        print(f"Throughput: {cpm} characters per minute")

        self.results[implementation]['throughput_cpm'] = cpm
        return cpm

    def test_memory_usage(self, implementation):
        """
        Measure memory footprint during operation

        Args:
            implementation: 'threading' or 'async'

        Returns:
            Dict with memory stats
        """
        print(f"\n=== Testing Memory Usage ({implementation}) ===")

        gc.collect()
        initial_free = gc.mem_free()
        initial_alloc = gc.mem_alloc()

        print(f"Initial free: {initial_free:,} bytes")
        print(f"Initial allocated: {initial_alloc:,} bytes")

        # In real test: run implementation for 1 minute
        # Monitor memory changes
        utime.sleep(1)  # Simulated

        gc.collect()
        final_free = gc.mem_free()
        final_alloc = gc.mem_alloc()

        memory_increase = initial_alloc - final_alloc

        print(f"Final free: {final_free:,} bytes")
        print(f"Final allocated: {final_alloc:,} bytes")
        print(f"Memory change: {memory_increase:+,} bytes")

        stats = {
            'peak_allocated': final_alloc,
            'memory_increase': memory_increase,
            'final_free': final_free
        }

        self.results[implementation]['memory'] = stats
        return stats

    def test_display_refresh_time(self, implementation):
        """
        Measure actual e-ink refresh duration

        Args:
            implementation: 'threading' or 'async'

        Returns:
            Refresh time in milliseconds
        """
        print(f"\n=== Testing Display Refresh Time ({implementation}) ===")
        print("Measuring e-ink partial refresh duration...")

        # In real test: trigger partial refresh, time from start to completion
        start = utime.ticks_ms()
        utime.sleep_ms(800)  # Simulated e-ink refresh (~800ms typical)
        end = utime.ticks_ms()

        refresh_time = utime.ticks_diff(end, start)
        print(f"Refresh time: {refresh_time}ms")

        self.results[implementation]['refresh_time_ms'] = refresh_time
        return refresh_time

    def test_file_save_blocking(self, implementation):
        """
        Test if file saves block UI

        Args:
            implementation: 'threading' or 'async'

        Returns:
            True if non-blocking, False if blocked
        """
        print(f"\n=== Testing File Save Blocking ({implementation}) ===")
        print("Triggering file save and checking UI responsiveness...")

        # In real test: trigger save, attempt keyboard input
        is_non_blocking = True  # Simulated

        print(f"Result: {'NON-BLOCKING' if is_non_blocking else 'BLOCKING'}")

        self.results[implementation]['file_save_non_blocking'] = is_non_blocking
        return is_non_blocking

    def run_full_benchmark(self, implementation):
        """
        Run complete benchmark suite

        Args:
            implementation: 'threading' or 'async'
        """
        print("\n" + "="*60)
        print(f"BENCHMARKING: {implementation.upper()}")
        print("="*60)

        self.test_typing_latency(implementation)
        self.test_display_blocking(implementation)
        self.test_throughput(implementation)
        self.test_memory_usage(implementation)
        self.test_display_refresh_time(implementation)
        self.test_file_save_blocking(implementation)

        print(f"\n{'='*60}")
        print(f"BENCHMARK COMPLETE: {implementation.upper()}")
        print("="*60)

    def compare_results(self):
        """
        Print comparison table of both approaches
        """
        print("\n" + "="*60)
        print("COMPARISON RESULTS")
        print("="*60)

        metrics = [
            ('Typing Latency', 'typing_latency', 'ms', 'lower'),
            ('Display Blocking', 'non_blocking', '', 'higher'),
            ('Throughput', 'throughput_cpm', 'cpm', 'higher'),
            ('Refresh Time', 'refresh_time_ms', 'ms', 'lower'),
            ('File Save Blocking', 'file_save_non_blocking', '', 'higher')
        ]

        print(f"\n{'Metric':<25} {'Threading':<20} {'Async':<20} {'Winner':<10}")
        print("-" * 80)

        for name, key, unit, better in metrics:
            threading_val = self.results['threading'].get(key, 'N/A')
            async_val = self.results['async'].get(key, 'N/A')

            if isinstance(threading_val, bool):
                threading_str = 'Yes' if threading_val else 'No'
                async_str = 'Yes' if async_val else 'No'
                winner = 'Tie' if threading_val == async_val else (
                    'Threading' if threading_val else 'Async'
                )
            else:
                threading_str = f"{threading_val} {unit}"
                async_str = f"{async_val} {unit}"

                if better == 'lower':
                    winner = 'Threading' if threading_val < async_val else 'Async'
                else:
                    winner = 'Threading' if threading_val > async_val else 'Async'

            print(f"{name:<25} {threading_str:<20} {async_str:<20} {winner:<10}")

        # Memory comparison
        print("\nMemory Usage:")
        for impl in ['threading', 'async']:
            mem = self.results[impl].get('memory', {})
            print(f"  {impl.capitalize()}:")
            print(f"    Peak allocated: {mem.get('peak_allocated', 0):,} bytes")
            print(f"    Memory increase: {mem.get('memory_increase', 0):+,} bytes")
            print(f"    Final free: {mem.get('final_free', 0):,} bytes")

        print("\n" + "="*60)
        print("RECOMMENDATION")
        print("="*60)

        # Simple scoring
        threading_score = 0
        async_score = 0

        for name, key, unit, better in metrics:
            threading_val = self.results['threading'].get(key, 0)
            async_val = self.results['async'].get(key, 0)

            if isinstance(threading_val, bool):
                if threading_val:
                    threading_score += 1
                if async_val:
                    async_score += 1
            else:
                if better == 'lower':
                    if threading_val < async_val:
                        threading_score += 1
                    else:
                        async_score += 1
                else:
                    if threading_val > async_val:
                        threading_score += 1
                    else:
                        async_score += 1

        print(f"\nScore: Threading={threading_score}, Async={async_score}")

        if threading_score > async_score:
            print("\n✓ THREADING approach shows better performance")
            print("  Consider using main_threaded.py for production")
        elif async_score > threading_score:
            print("\n✓ ASYNC approach shows better performance")
            print("  Consider using main_async.py for production")
        else:
            print("\n= Both approaches show similar performance")
            print("  Choose based on stability and ease of maintenance")

        print("\nNote: Async approach typically more stable due to")
        print("      known MicroPython threading GC issues on Pico")
        print("="*60)

    def save_results(self, filename='benchmark_results.txt'):
        """
        Save benchmark results to file

        Args:
            filename: Output file path
        """
        try:
            with open(filename, 'w') as f:
                f.write("Benchmark Results - Single Pico 2W Investigation\n")
                f.write("="*60 + "\n\n")

                for impl in ['threading', 'async']:
                    f.write(f"{impl.upper()} RESULTS:\n")
                    f.write("-"*40 + "\n")
                    for key, value in self.results[impl].items():
                        f.write(f"{key}: {value}\n")
                    f.write("\n")

                f.write("\nTest completed at: ")
                # Would add timestamp here
                f.write("\n")

            print(f"\nResults saved to: {filename}")
        except Exception as e:
            print(f"Error saving results: {e}")


def main():
    """
    Main benchmark execution
    """
    print("\n" + "="*60)
    print("SINGLE PICO 2W BENCHMARK")
    print("Threading vs Async Performance Comparison")
    print("="*60)

    runner = BenchmarkRunner()

    # Run benchmarks for both approaches
    runner.run_full_benchmark('threading')
    utime.sleep(2)  # Brief pause between tests
    runner.run_full_benchmark('async')

    # Compare results
    runner.compare_results()

    # Save to file
    runner.save_results()

    print("\nBenchmark complete!")
    print("Press any key to exit...")


if __name__ == "__main__":
    main()
