# todoist_upload.py - Upload Writer's Deck files to Todoist as tasks with text as comment

import network
import urequests
import ujson
import utime
import time
import gc
from config import WIFI_SSID, WIFI_PASSWORD, TODOIST_API_TOKEN

#───────────────────────────────────────────────#
# ─────────── Configuration ────────────────────#
#───────────────────────────────────────────────#

# WiFi credentials
WIFI_SSID = WIFI_SSID
WIFI_PASSWORD = WIFI_PASSWORD

# Todoist API configuration
TODOIST_API_TOKEN = TODOIST_API_TOKEN

# WiFi instance
wlan = None

#───────────────────────────────────────────────#
# ─────────── WiFi Functions ───────────────────#
#───────────────────────────────────────────────#

def connect_wifi(timeout=20):
    """Connect to WiFi with disconnect/reconnect sequence"""
    global wlan
    wlan = network.WLAN(network.STA_IF)
    
    # Disconnect first if connected
    if wlan.isconnected():
        print('📡 Disconnecting existing WiFi...')
        wlan.disconnect()
        utime.sleep_ms(1000)
    
    wlan.active(True)
    
    if not wlan.isconnected():
        print(f'📡 Connecting to WiFi: {WIFI_SSID}...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Wait for connection with timeout
        start_time = utime.time()
        while not wlan.isconnected() and (utime.time() - start_time) < timeout:
            print(f'⏳ Waiting... {timeout - int(utime.time() - start_time)}s')
            time.sleep(1)
            
        if wlan.isconnected():
            print('✅ WiFi connected')
            print(f'IP: {wlan.ifconfig()[0]}')
            return True
        else:
            print('❌ WiFi connection failed')
            return False
    
    return True

def disconnect_wifi():
    """Disconnect WiFi to save power"""
    global wlan
    if wlan and wlan.isconnected():
        wlan.disconnect()
        wlan.active(False)
        print('📡 WiFi disconnected')

#───────────────────────────────────────────────#
# ─────────── Todoist Functions ────────────────#
#───────────────────────────────────────────────#

def create_task(filename):
    """Create a task in Todoist Inbox"""
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Create task with filename as title
    task_data = {
        "content": filename
        # project_id is optional - omitting it puts task in Inbox
    }
    
    print(f"📝 Creating task: {filename}")
    
    try:
        response = urequests.post(url, json=task_data, headers=headers)
        
        if response.status_code in [200, 201]:
            task = response.json()
            task_id = task.get('id')
            response.close()
            print(f"✅ Task created with ID: {task_id}")
            return task_id
        else:
            print(f"❌ Failed to create task: {response.status_code}")
            response.close()
            return None
            
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        return None

def add_comment(task_id, content):
    """Add file content as a comment using v2 API"""
    url = "https://api.todoist.com/rest/v2/comments"
    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    comment_data = {
        "task_id": str(task_id),
        "content": content
    }
    
    print(f"💬 Adding file content as comment...")
    
    try:
        response = urequests.post(url, json=comment_data, headers=headers)
        
        if response.status_code in [200, 201]:
            response.close()
            print("✅ File content added as comment")
            return True
        else:
            print(f"❌ Failed to add comment: {response.status_code}")
            response.close()
            return False
            
    except Exception as e:
        print(f"❌ Error adding comment: {e}")
        return False

def check_existing_tasks(filename):
    """Check for existing tasks and generate unique name if needed"""
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}
    
    try:
        response = urequests.get(url, headers=headers)
        
        if response.status_code == 200:
            tasks = response.json()
            response.close()
            
            # Extract base name and extension
            base_name = filename.rsplit('.', 1)[0]
            extension = filename.rsplit('.', 1)[1] if '.' in filename else ''
            
            # Count existing tasks with similar names
            existing_count = 0
            for task in tasks:
                content = task.get('content', '')
                if content.startswith(base_name):
                    existing_count += 1
            
            if existing_count > 0:
                # Generate unique name
                new_filename = f"{base_name}_{existing_count}"
                if extension:
                    new_filename += f".{extension}"
                return new_filename
            
            return filename
        else:
            response.close()
            return filename
            
    except Exception as e:
        print(f"⚠️ Couldn't check for duplicates: {e}")
        return filename

#───────────────────────────────────────────────#
# ─────────── Main Upload Function ─────────────#
#───────────────────────────────────────────────#

def upload_to_todoist(filepath, status_callback=None):
    """
    Upload file to Todoist as a task with content as comment
    
    Args:
        filepath: Path to the file to upload
        status_callback: Optional function to call with status messages
        
    Returns:
        tuple: (success: bool, message: str)
    """
    
    def update_status(msg):
        if status_callback:
            status_callback(msg)
        print(msg)
    
    # Read file content
    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except OSError:
        return False, "File not found"
    
    # Extract filename
    filename = filepath.split('/')[-1]
    
    # Connect to WiFi
    update_status("Connecting to WiFi...")
    if not connect_wifi():
        return False, "WiFi connection failed"
    
    try:
        # Check for duplicates and get unique filename
        update_status("Checking Todoist...")
        unique_filename = check_existing_tasks(filename)
        
        # Create task
        update_status("Creating task...")
        task_id = create_task(unique_filename)
        
        if not task_id:
            return False, "Failed to create task"
        
        # Add file content as comment
        update_status("Uploading content...")
        success = add_comment(task_id, content)
        
        if success:
            return True, f"Saved as: {unique_filename}"
        else:
            return False, "Failed to add content"
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False, str(e)
    finally:
        # Clean up
        gc.collect()
        disconnect_wifi()