import utime
import gc
from epd_driver import EPD_7in5
from todoist_sync import sync_and_get_tasks

# Import configuration
try:
    from utils.config import TITLE
except ImportError:
    TITLE = "Today's Focus"

def main_clean():
    """Display tasks in a clean, focused layout"""
    
    # Step 1: Setup display
    print("\n📱 Setting up display...")
    epd = EPD_7in5()
    epd.clear_screen()
    
    # Step 2: Get your tasks
    print("\n📋 Getting your tasks...")
    tasks_text = sync_and_get_tasks(force_refresh=True)
    
    # Step 3: Show on screen
    print("\n✨ Showing your tasks...")
    
    # Simple, clean display:
    # - Title at top
    # - Tasks below with good spacing
    epd.print_mixed_content(
        title=TITLE,
        tasks=tasks_text,
        title_x=20,      # Slight indent from edge
        title_y=20,      # Space from top
        tasks_x=20,      # Aligned with title
        tasks_y=100     # Clear gap after title
    )
    
    # Step 4: Save power
    utime.sleep(2)
    epd.sleep()
    
    # Done
    gc.collect()
    print("\n✅ Ready!")

# Run when this file is executed
if __name__ == "__main__":
    main_clean()