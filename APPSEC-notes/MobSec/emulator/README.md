# Emulator Bypass Scripts (AVD / MEmu)

Linux (`.sh`) and Windows (`.bat`) helpers that deploy `frida-server` and run the
bypass flow (`full_flow.py`) against an Android emulator.

## Requirements

- `adb` and `frida` / `frida-tools` on your PATH (`pip install frida-tools`)
- Python 3 (`python3` on Linux, `python` on Windows)
- A `frida-server` build matching your installed Frida version
- AVD: a rooted emulator image. MEmu: **Root = ON** in MEmu settings.

## Where you must edit (checklist)

Replace every placeholder below with **your own values** before running anything.

| # | File | What to change | Your value |
|---|------|----------------|------------|
| 1 | `avd/full_flow.py` | `PKG = "com.example.yourapp"` → your app's package name | |
| 2 | `avd/full_flow.py` | `SPAWN_ID = "com.example.yourapp"` → package the app spawns as (usually same as `PKG`) | |
| 3 | `avd/full_flow.py` | `ACTIVITY = "com.example.yourapp.MainActivity"` → your launcher activity | |
| 4 | `memu/full_flow.py` | `PKG`, `SPAWN_ID`, `ACTIVITY` → same three values as above | |
| 5 | `avd/setup_frida.sh` | `FRIDA_SERVER="$HOME/Tools/frida-server"` → path to your `frida-server` binary | |
| 6 | `avd/setup_frida.bat` | `C:\Users\Shondels\Downloads\Tools\AVD\frida-server` → path to your `frida-server` binary | |

Find your values with:

```sh
adb shell pm list packages                                   # installed package names
adb shell cmd package resolve-activity --brief <your.package> # launcher activity
```

Example after editing `avd/full_flow.py`:

```python
# EDIT THESE: package name of the app you are testing (run: adb shell pm list packages)
PKG = "com.mybank.mobile"
SPAWN_ID = "com.mybank.mobile"
ACTIVITY = "com.mybank.mobile.SplashActivity"
```

## Linux

```sh
# AVD
cd avd
FRIDA_SERVER=/path/to/frida-server ./setup_frida.sh   # push + start frida-server as root
./run_avd.sh                                          # run the bypass

# MEmu
cd ../memu
./run_memu.sh                                         # run the bypass
```

`setup_frida.sh` defaults to `$HOME/Tools/frida-server` — pass `FRIDA_SERVER=...`
or edit the variable in the script.

## Windows

```bat
cd avd
setup_frida.bat
run_avd.bat

cd ..\memu
run_memu.bat
```

Edit the `frida-server` path in `avd\setup_frida.bat` first (item 6 above).

## Files

| File | Purpose |
|------|---------|
| `avd/setup_frida.sh` / `.bat` | Push `frida-server` to AVD, make it executable, start it |
| `avd/run_avd.sh` / `.bat` | Run the Frida bypass flow against the AVD |
| `memu/run_memu.sh` / `.bat` | Run the Frida bypass flow against MEmu |
| `full_flow.py` | Spawn gating → inject `bypass-final.js` → start app |
| `bypass-final.js` | Frida instrumentation script |
| `probe.js` | Small script to inspect the running app |
| `test_conn.py` | Quick check that Frida can see the device |

## Troubleshooting

- **`frida-server not found`** — set `FRIDA_SERVER` to the correct path (items 5–6).
- **Device not found** — check `adb devices`; emulator must be running first.
- **App not spawning** — confirm `SPAWN_ID` matches the package the app actually
  starts (see `avd/await_out.txt` after a run).
