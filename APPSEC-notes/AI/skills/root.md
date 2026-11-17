---
name: android-rooting
description: Use when the user wants to root an Android device, re-root after an OTA/system update killed root, install Magisk, unlock a bootloader, patch or flash a boot/init_boot image, or fix root-related problems (bootloop, fastboot not detected, unauthorized adb, driver error 28, WSL fastboot). Covers Pixel, Samsung, Xiaomi and other devices. Full reference lives at ~/android-rooting-guide.md.
---

# Android Rooting

Guide the user through rooting (or re-rooting) an Android device with Magisk using the full 100-step reference at `~/android-rooting-guide.md`. Read that file when the task actually begins — it holds the complete numbered procedure, per-brand notes, and recovery steps. This skill holds the workflow order, the safety gates, and the environment-specific gotchas.

## Hard safety gates (never skip)

1. **Backup first, always.** Before any unlock or flash: `adb pull /sdcard/DCIM`, `/sdcard/Pictures`, `/sdcard/Download` to the computer, verify file counts/sizes, and put a second copy somewhere safe. Unlocking the bootloader **factory-resets** the device.
2. **Match build exactly.** Get `adb shell getprop ro.build.display.id` and `ro.build.fingerprint`; the factory image / stock firmware / boot.img must carry the identical build ID. Mismatched boot image = bootloop.
3. **Never relock** a bootloader over modified images. Only run `fastboot flashing lock` on a 100% stock device.
4. **OTAs remove root.** Have the user turn off Settings → Developer options → *Automatic system updates*, and never install an update without being ready to redo the patch cycle.
5. Confirm state before touching fastboot: `adb shell getprop ro.boot.vbmeta.device_state` — if already `unlocked`, skip the unlock entirely (re-unlocking would wipe data).

## Workflow

1. **Triage:** device model + variant, build ID, current lock state, root goal (fresh root vs re-root after OTA).
2. **Tools:** adb/fastboot (platform-tools), official Magisk APK only from `github.com/topjohnwu/Magisk/releases`, unzip tool, ~5 GB free disk.
3. **Backup** (gates above), then **unlock** only if locked (Steps 35–46 of the guide; brand gates: Xiaomi account wait, Samsung Knox trip, carrier-locked = abort).
4. **Acquire stock image** for the exact build — Pixel factory image, OEM firmware, or OTA + payload-dumper. Extract `boot.img` (`init_boot.img` on Android 13+ GKI devices — patch whichever holds the ramdisk). Archive the stock image; it's the unbrick path.
5. **Patch:** `adb install Magisk.apk`, `adb push boot.img /sdcard/Download/`, in Magisk app: Install → Select and patch a file → pull back `magisk_patched-*.img` (newest timestamp if several exist). Verify magic `ANDROID!` and byte-identical size vs stock.
6. **Flash:** `adb reboot bootloader` → verify `fastboot devices` → `fastboot flash boot <patched>` (fastboot picks the active A/B slot) → `fastboot reboot`.
7. **Verify:** Magisk app shows *Installed*; `adb shell su -c id` → `uid=0(root)` (user must tap Grant); check `zygisk` setting via `magisk --sqlite`; confirm real lock state from `/proc/cmdline` (props can be spoofed by Shamiko).
8. **Maintain:** auto-updates off; archive `<build>/stock-boot.img` + patched image; on future OTAs, repeat only the acquire→patch→flash cycle with the new build.

## Environment gotchas (this machine)

- Host is **WSL2**: Linux `fastboot` can NEVER see a phone (no USB in WSL). `adb` works because it talks to the Windows adb server. Always use `C:\Users\Shondels\Downloads\platform-tools-latest-windows\platform-tools\fastboot.exe` for bootloader work, and keep flashed images on a Windows path (`/mnt/c/...`), not `/tmp`.
- Windows fastboot driver problems: symptom = `fastboot devices` empty while the phone shows the bootloader screen. Fix = install Google USB Driver (`latest_usb_driver_windows.zip`) via elevated `pnputil /add-driver android_winusb.inf /install` (UAC prompt must be approved). Device Manager must show *Android Bootloader Interface* / WinUSB / Status OK first. The INF already contains Pixel bootloader IDs (e.g. `USB\VID_18D1&PID_4EE0`).
- adb `unauthorized` → user must tap Allow on the phone popup; `adb kill-server` if stale.
- Never press buttons on the fastboot screen while waiting — the user (or agent) should only ever issue software commands.

## Recovery

- Bootloop after flash: force off (hold Power ~30s) → bootloader via Volume Down + Power → `fastboot flash boot <stock-boot.img>` → boots unrooted with data intact → re-patch carefully.
- Root lost but boots: check active slot vs what was flashed; Magisk module loop → hold Volume Down at boot to skip modules.
- Reference the guide's Steps 95–100 for full troubleshooting, and Steps 47–58 for image acquisition details.
