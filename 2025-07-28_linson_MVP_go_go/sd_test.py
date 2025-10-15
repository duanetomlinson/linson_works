'''SD Card File Operations Test for ESP32-S3
Tests creating folders, writing, reading, and listing files
''' 

import machine
from machine import Pin, SoftSPI
import os
import time
import sdcard

print("SD Card File Operations Test")
print("=" * 40)

# SD Card pins
SD_SCK  = 18
SD_MOSI = 11
SD_MISO = 13
SD_CS   = 43

# Mount SD Card
try:
    # Configure MISO with pull-up for reliable communication
    miso_pin = Pin(SD_MISO, Pin.IN, Pin.PULL_UP)
    
    spi = SoftSPI(
        baudrate=500_000,
        polarity=0,
        phase=0,
        sck=Pin(SD_SCK),
        mosi=Pin(SD_MOSI),
        miso=miso_pin
    )
    sd = sdcard.SDCard(spi, Pin(SD_CS, Pin.OUT))
    vfs = os.VfsFat(sd)
    os.mount(vfs, '/sd')
    print("✓ SD Card mounted to /sd")
except Exception as e:
    print(f"✗ Failed to mount SD card: {e}")
    raise

print("\n1. Current SD card contents:")
print("-" * 30)
try:
    files = os.listdir('/sd')
    for f in files:
        # Get file info
        try:
            stat = os.stat(f'/sd/{f}')
            size = stat[6]  # File size
            is_dir = stat[0] & 0x4000  # Check if directory
            type_str = "DIR " if is_dir else "FILE"
            print(f"   {type_str} {f:<20} {size:>10} bytes")
        except:
            print(f"   ?    {f}")
except Exception as e:
    print(f"Error listing files: {e}")

print("\n2. Creating test folder structure:")
print("-" * 30)

# Create nested folders
folders = [
    '/sd/saved_files',
    '/sd/saved_files/backup',
    '/sd/test_folder'
]

for folder in folders:
    try:
        os.mkdir(folder)
        print(f"   ✓ Created: {folder}")
    except OSError as e:
        if "EEXIST" in str(e):
            print(f"   - Exists: {folder}")
        else:
            print(f"   ✗ Failed: {folder} - {e}")

print("\n3. Writing test files:")
print("-" * 30)

# Test file contents
test_files = [
    ('/sd/test_simple.txt', 'Hello from ESP32-S3!\n'),
    ('/sd/saved_files/note_001.txt', 'This is a test note.\nIt has multiple lines.\nLine 3 here!'),
    ('/sd/saved_files/config.txt', 'user=esp32\nmode=typewriter\nversion=1.0'),
    ('/sd/test_timestamp.txt', f'Created at: {time.time()}\nTicks: {time.ticks_ms()}\n')
]

for filepath, content in test_files:
    try:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"   ✓ Written: {filepath} ({len(content)} bytes)")
    except Exception as e:
        print(f"   ✗ Failed: {filepath} - {e}")

print("\n4. Reading test files back:")
print("-" * 30)

for filepath, _ in test_files:
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        print(f"   ✓ Read: {filepath}")
        print(f"     First 50 chars: {repr(content[:50])}")
    except Exception as e:
        print(f"   ✗ Failed to read: {filepath} - {e}")

print("\n5. Appending to a file:")
print("-" * 30)

append_file = '/sd/append_test.txt'
try:
    # Write initial content
    with open(append_file, 'w') as f:
        f.write("Line 1\n")
    print(f"   Created {append_file}")
    
    # Append more lines
    for i in range(2, 5):
        with open(append_file, 'a') as f:
            f.write(f"Line {i}\n")
        print(f"   Appended line {i}")
    
    # Read it back
    with open(append_file, 'r') as f:
        content = f.read()
    print(f"   Final content:\n{content}")
    
except Exception as e:
    print(f"   ✗ Append test failed: {e}")

print("\n6. File listing after operations:")
print("-" * 30)

def list_directory(path, indent=0):
    """Recursively list directory contents"""
    try:
        items = os.listdir(path)
        for item in sorted(items):
            full_path = f"{path}/{item}"
            try:
                stat = os.stat(full_path)
                is_dir = stat[0] & 0x4000
                size = stat[6]
                
                if is_dir:
                    print(f"{'  ' * indent}📁 {item}/")
                    list_directory(full_path, indent + 1)
                else:
                    print(f"{'  ' * indent}📄 {item} ({size} bytes)")
            except Exception as e:
                print(f"{'  ' * indent}❓ {item} (error: {e})")
    except Exception as e:
        print(f"{'  ' * indent}Error listing {path}: {e}")

print("SD Card contents:")
list_directory('/sd')

print("\n7. Testing file operations in saved_files:")
print("-" * 30)

# Simulate what your main app would do
test_log = '/sd/saved_files/text_log.txt'
try:
    # Write some pages
    with open(test_log, 'w') as f:
        f.write("Page 1 content here\n")
        f.write("More text on page 1\n")
        f.write("\n---\n")  # Page separator
        f.write("Page 2 starts here\n")
        f.write("Second page content\n")
    print(f"   ✓ Created multi-page text_log.txt")
    
    # Read it back
    with open(test_log, 'r') as f:
        content = f.read()
        pages = content.split('\n---\n')
    print(f"   ✓ Read back {len(pages)} pages")
    
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Cleanup - unmount
print("\n8. Unmounting SD card...")
try:
    os.umount('/sd')
    print("   ✓ SD card unmounted cleanly")
except Exception as e:
    print(f"   ✗ Unmount failed: {e}")

print("\n" + "="*40)
print("Test complete! Check your SD card on a computer")
print("to verify all files were created properly.")