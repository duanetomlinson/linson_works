# tca8418_keyboard_diagnostic.py - Diagnostic tool to map your physical keyboard layout
# This will help identify how your keyboard matrix is actually wired

from machine import I2C, Pin
import utime
from tca8418 import TCA8418  # Import your existing module

def keyboard_diagnostic():
    """
    Diagnostic tool to map physical keyboard layout
    Press each key and see what row/column it reports
    """
    
    # Initialize I2C
    i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
    
    # Configure interrupt and reset pins
    interrupt_pin = Pin(21, Pin.IN, Pin.PULL_UP)
    reset_pin = Pin(38, Pin.OUT, value=1)
    
    try:
        # Initialize keyboard controller
        keyboard = TCA8418(i2c, interrupt_pin=interrupt_pin, reset_pin=reset_pin)
        
        print("=" * 70)
        print("    KEYBOARD MATRIX DIAGNOSTIC MODE")
        print("=" * 70)
        print("Instructions:")
        print("1. Press each key one at a time")
        print("2. Note which key you pressed and what row/col is reported")
        print("3. This will help us create the correct mapping")
        print("4. Press Ctrl+C when done")
        print("=" * 70)
        print("\nReady! Press keys one at a time...\n")
        
        # Track pressed keys to avoid duplicates
        currently_pressed = set()
        
        # Store discovered mappings
        discovered_map = {}
        
        while True:
            if keyboard.has_interrupt():
                # Read raw events
                while True:
                    event = keyboard.read_key_event()
                    if event is None:
                        break
                    
                    row, col, pressed = event
                    key_pos = (row, col)
                    
                    if pressed and key_pos not in currently_pressed:
                        currently_pressed.add(key_pos)
                        
                        # Show the raw row/col
                        print(f"\n>>> Key pressed at Row {row}, Column {col}")
                        print(f"    Position: ({row}, {col})")
                        
                        # Show what the current mapping thinks this is
                        expected_key = keyboard.get_key_name(row, col)
                        if expected_key and not expected_key.startswith("Unknown"):
                            print(f"    Currently mapped as: '{expected_key}'")
                        else:
                            print(f"    Currently unmapped")
                        
                        print("    What key did you actually press? ", end="")
                        
                    elif not pressed and key_pos in currently_pressed:
                        currently_pressed.discard(key_pos)
                
                keyboard.clear_interrupts()
            
            utime.sleep_ms(1)
            
    except KeyboardInterrupt:
        print("\n\nDiagnostic complete!")
        

def create_mapping_helper():
    """
    Interactive helper to create the correct key mapping
    """
    print("\n" + "=" * 70)
    print("    INTERACTIVE KEYBOARD MAPPING CREATOR")
    print("=" * 70)
    print("Let's create the correct mapping for your keyboard!")
    print("I'll guide you through pressing each key in order.\n")
    
    # Initialize I2C
    i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
    
    # Configure interrupt and reset pins
    interrupt_pin = Pin(21, Pin.IN, Pin.PULL_UP)
    reset_pin = Pin(38, Pin.OUT, value=1)
    
    # Expected Linson keyboard layout
    expected_layout = [
        # Row 0
        ['Esc', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
        # Row 1  
        ['0', '-', '=', 'Backspace', 'Home', 'Tab', 'Q', 'W', 'E', 'R'],
        # Row 2
        ['T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '\\', 'Del'],
        # Row 3
        ['Caps', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
        # Row 4
        [';', "'", 'Enter', 'PgUp', 'Shift', 'Z', 'X', 'C', 'V', 'B'],
        # Row 5
        ['N', 'M', ',', '.', '/', 'Shift', 'Up', 'PgDn', 'Alt', 'Win'],
        # Row 6
        ['Ctrl', 'Space', 'Alt', 'Fn', 'Ctrl', 'Left', 'Down', 'Right']
    ]
    
    try:
        keyboard = TCA8418(i2c, interrupt_pin=interrupt_pin, reset_pin=reset_pin)
        
        # This will store the actual physical mapping
        actual_mapping = {}
        
        for layout_row, keys in enumerate(expected_layout):
            for layout_col, key_name in enumerate(keys):
                if key_name is None:
                    continue
                    
                print(f"\nPlease press the '{key_name}' key...")
                
                # Wait for key press
                key_found = False
                while not key_found:
                    if keyboard.has_interrupt():
                        event = keyboard.read_key_event()
                        if event:
                            row, col, pressed = event
                            if pressed:
                                actual_mapping[(row, col)] = key_name
                                print(f"✓ '{key_name}' is at physical position ({row}, {col})")
                                key_found = True
                                
                                # Wait for key release
                                while keyboard.has_interrupt():
                                    keyboard.read_key_event()
                                    keyboard.clear_interrupts()
                                    utime.sleep_ms(10)
                                
                        keyboard.clear_interrupts()
                    utime.sleep_ms(1)
        
        # Generate the new mapping code
        print("\n\n" + "=" * 70)
        print("MAPPING COMPLETE! Here's your corrected key_map:\n")
        print("key_map = {")
        
        # Group by physical rows
        for row in range(8):
            row_keys = [(col, key) for (r, col), key in sorted(actual_mapping.items()) if r == row]
            if row_keys:
                print(f"    # Row {row}")
                for i in range(0, len(row_keys), 5):
                    chunk = row_keys[i:i+5]
                    line = "    "
                    for col, key in chunk:
                        line += f"({row}, {col}): '{key}', "
                    print(line.rstrip(", ") + ",")
                print()
        
        print("}")
        
    except KeyboardInterrupt:
        print("\n\nMapping cancelled.")
    except Exception as e:
        print(f"\nError: {e}")


def test_specific_keys():
    """
    Test specific problematic keys
    """
    print("\nTEST SPECIFIC KEYS MODE")
    print("Press the following keys and verify the output:")
    
    test_keys = ['Esc', '1', 'Q', 'A', 'Space', 'Enter']
    
    # Initialize
    i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
    interrupt_pin = Pin(21, Pin.IN, Pin.PULL_UP)
    reset_pin = Pin(38, Pin.OUT, value=1)
    
    keyboard = TCA8418(i2c, interrupt_pin=interrupt_pin, reset_pin=reset_pin)
    
    for test_key in test_keys:
        print(f"\nPress '{test_key}' and see what it reports...")
        
    currently_pressed = set()
    
    try:
        while True:
            if keyboard.has_interrupt():
                events = keyboard.read_keys_with_names()
                
                for key_name, pressed in events:
                    if pressed and key_name not in currently_pressed:
                        print(f"Detected: {key_name}")
                        currently_pressed.add(key_name)
                    elif not pressed and key_name in currently_pressed:
                        currently_pressed.discard(key_name)
                
                keyboard.clear_interrupts()
            
            utime.sleep_ms(1)
            
    except KeyboardInterrupt:
        print("\nTest complete!")


# Menu to choose diagnostic mode
def main():
    print("\nKEYBOARD DIAGNOSTIC TOOL")
    print("========================")
    print("1. Basic diagnostic (see raw row/col for each key)")
    print("2. Interactive mapping creator (guided mapping)")
    print("3. Test specific keys")
    print("\nWhich mode? (1/2/3): ", end="")
    
    # Simple input simulation - in real use, you'd run one function directly
    # For now, just run the basic diagnostic
    keyboard_diagnostic()


if __name__ == "__main__":
    # Run the diagnostic directly
    print("Starting keyboard diagnostic...")
    print("Choose which function to run:")
    print("  keyboard_diagnostic()     - See raw row/col values")
    print("  create_mapping_helper()   - Guided mapping creator")
    print("  test_specific_keys()      - Test specific keys")
    
    # Run the basic diagnostic by default
    keyboard_diagnostic()
