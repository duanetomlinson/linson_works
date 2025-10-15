# wifi_transfer.py - WiFi file transfer module for Writer's Deck

import network
import urequests
import ujson
import ubinascii
import utime
import time
import os
from config import WIFI_SSID, WIFI_PASSWORD

#───────────────────────────────────────────────#
# ─────────── Configuration ────────────────────#
#───────────────────────────────────────────────#

# WiFi credentials - modify these for your network
WIFI_SSID = WIFI_SSID
WIFI_PASSWORD = WIFI_PASSWORD

# Server configuration
SERVER_URL = "http://nion-edge-server.local:8080/upload"
SERVER_USER = "nion"
SERVER_PASS = "nion edge s01"

# WiFi instance
wlan = None

#───────────────────────────────────────────────#
# ─────────── WiFi Functions ───────────────────#
#───────────────────────────────────────────────#

def connect_wifi(timeout=20):
    """Connect to WiFi network"""
    global wlan
    
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(False)
        utime.sleep(500)
        wlan.active(True)
        utime.sleep(500)
        
        if wlan.isconnected():
            return True
            
        print(f"Connecting to WiFi: {WIFI_SSID}")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Wait for connection
        start_time = utime.time()
        while not wlan.isconnected():
            if utime.time() - start_time > timeout:
                print("WiFi connection timeout")
                return False
            time.sleep_ms(100)
        
        print(f"Connected! IP: {wlan.ifconfig()[0]}")
        return True
        
    except Exception as e:
        print(f"WiFi error: {e}")
        return False

def disconnect_wifi():
    """Disconnect from WiFi"""
    global wlan
    if wlan and wlan.isconnected():
        wlan.disconnect()
        wlan.active(False)
        print("WiFi disconnected")

#───────────────────────────────────────────────#
# ─────────── File Transfer ────────────────────#
#───────────────────────────────────────────────#

def create_auth_header():
    """Create basic auth header"""
    credentials = f"{SERVER_USER}:{SERVER_PASS}"
    encoded = ubinascii.b2a_base64(credentials.encode()).decode().strip()
    return {"Authorization": f"Basic {encoded}"}

def send_file_to_server(filepath, status_callback=None):
    """
    Send file to home server via HTTP POST
    
    Args:
        filepath: Path to the file to send
        status_callback: Optional function to call with status messages
        
    Returns:
        tuple: (success: bool, message: str)
    """
    
    def update_status(msg):
        if status_callback:
            status_callback(msg)
        print(msg)
    
    # Check if file exists
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
        update_status("Sending file...")
        
        # Prepare the request
        headers = create_auth_header()
        headers['Content-Type'] = 'application/json'
        
        # Create JSON payload
        data = {
            'filename': filename,
            'content': content,
            'timestamp': utime.time()
        }
        
        # Send the file
        response = urequests.post(
            SERVER_URL,
            json=data,
            headers=headers
        )
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            saved_as = result.get('saved_as', filename)
            response.close()
            return True, f"Saved as: {saved_as}"
        else:
            error = f"Server error: {response.status_code}"
            response.close()
            return False, error
            
    except Exception as e:
        print(f"Transfer error: {e}")
        return False, str(e)
    finally:
        disconnect_wifi()

#───────────────────────────────────────────────#
# ─────────── Alternative FTP ──────────────────#
#───────────────────────────────────────────────#

def send_file_via_ftp(filepath, status_callback=None):
    """
    Alternative: Send file via FTP
    Requires uftplib to be installed
    """
    def update_status(msg):
        if status_callback:
            status_callback(msg)
        print(msg)
    
    try:
        import uftplib
    except ImportError:
        return False, "FTP not available (install uftplib)"
    
    try:
        if not connect_wifi():
            return False, "WiFi connection failed"
        
        update_status("Connecting to FTP...")
        
        # Connect to FTP server
        ftp = uftplib.FTP("nion-edge-server.local")
        ftp.login(SERVER_USER, SERVER_PASS)
        
        # Change to target directory
        try:
            ftp.cwd("/linson_files")
        except:
            ftp.mkd("/linson_files")
            ftp.cwd("/linson_files")
        
        # Check if file exists and generate unique name
        filename = filepath.split('/')[-1]
        base_name = filename.rsplit('.', 1)[0]
        extension = filename.rsplit('.', 1)[1] if '.' in filename else ''
        
        remote_name = filename
        counter = 1
        
        # List files to check for duplicates
        existing_files = []
        ftp.retrlines('LIST', lambda x: existing_files.append(x.split()[-1]))
        
        while remote_name in existing_files:
            remote_name = f"{base_name}_{counter}.{extension}" if extension else f"{base_name}_{counter}"
            counter += 1
        
        # Upload file
        update_status(f"Uploading as {remote_name}...")
        with open(filepath, 'rb') as f:
            ftp.storbinary(f'STOR {remote_name}', f)
        
        ftp.quit()
        disconnect_wifi()
        
        return True, f"Saved as: {remote_name}"
        
    except Exception as e:
        disconnect_wifi()
        print(f"FTP error: {e}")
        return False, str(e)