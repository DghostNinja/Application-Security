"""MEmu flow: spawn gating, await spawn, inject, start app."""
import frida, subprocess, time, os

HERE = os.path.dirname(os.path.abspath(__file__))

# EDIT THESE: package name of the app you are testing (run: adb shell pm list packages)
PKG = "com.example.yourapp"
# Package the app spawns under (MEmu helper by default - change if your app differs)
SPAWN_ID = "com.microvirt.tools"
# Launch activity of the app (run: adb shell cmd package resolve-activity --brief <PKG>)
ACTIVITY = "com.example.yourapp.MainActivity"
SCRIPT = os.path.join(HERE, "bypass-final.js")

def adb(*args, timeout=10):
    r = subprocess.run(["adb"] + list(args), capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

device = frida.get_usb_device(timeout=10)
try:
    device.enable_spawn_gating()
    print("[*] gating ON", flush=True)
except Exception as e:
    print(f"[!] gating: {e}", flush=True)

adb("shell", "am", "force-stop", PKG)
time.sleep(1)

frida_cmd = [
    "frida", "-U", "-W", SPAWN_ID,
    "-l", SCRIPT, "-q", "-t", "60", "--eternalize"
]
print(f"[*] starting: {' '.join(frida_cmd)}", flush=True)
outf = open(os.path.join(HERE, "await_out.txt"), "w")
proc = subprocess.Popen(
    frida_cmd,
    cwd=HERE,
    stdout=outf,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
)
time.sleep(3)
outf.flush()
with open(os.path.join(HERE, "await_out.txt")) as f:
    print("[*] frida says:", f.read().strip(), flush=True)

print("[*] starting app...", flush=True)
adb("shell", "am", "start", "-n", f"{PKG}/{ACTIVITY}")

print("[*] waiting for frida (60s max)...", flush=True)
try:
    proc.wait(timeout=65)
except subprocess.TimeoutExpired:
    print("[!] frida timeout, killing", flush=True)
    proc.kill()

outf.close()
with open(os.path.join(HERE, "await_out.txt")) as f:
    content = f.read()
print("==== FRIDA OUTPUT ====", flush=True)
print(content, flush=True)

pid = adb("shell", "pidof", PKG)
print(f"[*] app PID: {pid}", flush=True)
