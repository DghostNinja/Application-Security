# Android Rooting — Complete 100-Step Guide

Root any Android device safely with Magisk: backup → unlock → patch → flash → verify.

**Golden rules (read first):**

- **Backup before you touch anything.** Unlocking the bootloader wipes ALL data.
- **Root survives nothing by accident:** a system update (OTA) replaces the boot image and removes root — it does not usually brick the phone, but you must re-patch.
- **Match the image to the build.** Flashing a boot image from a different build = bootloop.
- **Nothing here is reversible-proof.** If you relock the bootloader on modified images, you can brick. Never relock unless everything is 100% stock.

**Legend:** `<>` = replace with your values. Run commands on your computer unless it says "on phone".

---

## Phase 1 — Understand the plan & risks (Steps 1–12)

1. Identify your exact device model and variant (e.g. Pixel 4 "flame", Pixel 7 "panther") — the wrong image for a sibling model will not boot.
2. Read the build number: **Settings → About phone → Build number** (e.g. `TP1A.220624.014`) — every image you download must match this *exactly*.
3. Understand what rooting means here: we patch the stock `boot` image with **Magisk** (a systemless root), then flash it back — no permanent system modification.
4. Check if your bootloader is *unlockable*: OEM unlocking must exist in Developer options; some brands (Xiaomi needs a waiting period, many Samsung US carriers, some Sony) refuse unlocks entirely.
5. Understand the cost: **unlocking the bootloader performs a factory reset — photos, apps, chats, 2FA seeds, bank apps all vanish.** This is why backup is step 23+, not optional.
6. Understand the maintenance cost: **any OS update replaces `boot.img` and removes root.** Your two choices after every update: re-patch the new build, or stay unrooted.
7. Charge the phone to at least **50%** — a battery death during flashing can hard-brick.
8. Use a **known-good USB cable** and plug directly into the computer (no hubs) — flaky cables cause half-flashed partitions.
9. Check for **anti-rollback / critical-partition** protections on your device (common on Xiaomi, some OnePlus) — flashing older firmware than installed can permanently brick.
10. Choose your root solution: **Magisk** (default, works almost everywhere), **KernelSU** (kernel-level, needs a compatible kernel), **APatch** (kernel patch without unlocking, newer devices).
11. Research your device's XDA/development thread — it tells you known pitfalls for your exact model (partition layout, vbmeta flags, quirks).
12. Freeze your workflow in time: turn OFF automatic updates **now** (Settings → Developer options → *Automatic system updates* off) so nothing downloads mid-process.

## Phase 2 — Install host tools (Steps 13–22)

13. Install **platform-tools** (adb + fastboot): Linux `sudo apt install adb fastboot` or `android-tools`; macOS `brew install android-platform-tools`; Windows: download from Google's official developer site and unzip.
14. Verify adb: run `adb version` — you need 1.0.41 or newer.
15. Verify fastboot: run `fastboot --version` — any recent version works.
16. **Linux only:** make sure your user is in the right group (`sudo usermod -aG plugdev $USER`) and Google USB udev rules exist, or fastboot will report "no permissions".
17. **macOS:** nothing extra needed — no drivers.
18. **Windows:** if the device ever shows an unknown device in Device Manager, install **Google USB Driver** (zip from Google) via Device Manager → Update driver → Have disk.
19. ⚠️ **WSL2 users:** WSL has **no USB access** — `adb` may work (it talks to the Windows adb server) but **Linux `fastboot` will never see a phone in bootloader mode.** Always use `fastboot.exe` from Windows platform-tools instead.
20. Download the **official Magisk APK** only from `github.com/topjohnwu/Magisk/releases` — dozens of fake "Magisk" APKs ship malware.
21. Make sure you have a zip tool (`unzip`, 7-Zip, or Finder) for factory images.
22. Free up at least **5 GB** on disk — factory images are 2–3 GB and you'll want copies of both stock and patched boot images.

## Phase 3 — Back up BEFORE rooting (Steps 23–34)

23. On phone: Settings → About phone → tap **Build number 7×** to enable Developer options.
24. On phone: Settings → System → Developer options → enable **USB debugging** (leave **OEM unlocking** visible here too for Phase 4).
25. Plug the phone in and **accept the "Allow USB debugging?" popup** on the phone — check "Always allow from this computer".
26. Confirm the link: `adb devices` must show your serial with state `device` (not `unauthorized` or `offline`).
27. Pull your camera photos: `adb pull /sdcard/DCIM ./backup/DCIM`
28. Pull screenshots & edited images: `adb pull /sdcard/Pictures ./backup/Pictures`
29. Pull everything else worth keeping: `adb pull /sdcard/Download ./backup/Download` (and `Documents`, `Movies`, `Music` if present).
30. Back up app data: use Google's backup (Settings → System → Backup) plus a dedicated tool (Swift Backup / Neo Backup, root comes later for full data) for anything critical.
31. Sync check: open Google Photos (or your gallery backup) and confirm the newest photo is actually uploaded before continuing.
32. Record critical identifiers off-device (IMEI via `*#06#`, modem/Wi-Fi MAC, 2FA recovery codes) — you'll need them if the wipe hits.
33. **Verify the backup**: count files and compare sizes (`du -sh ./backup` vs the phone's `adb shell du -sh /sdcard/DCIM`).
34. Put the backup in **two places** (external drive or cloud) — a backup next to the only computer that could fail is not a backup.

## Phase 4 — Unlock the bootloader (Steps 35–46)

> Skip to Phase 5 if `fastboot getvar unlocked` already says `yes` (your device was unlocked before). Unlocking again would wipe data for nothing.

35. Check current state: `adb shell getprop ro.boot.vbmeta.device_state` → `unlocked` or `locked`.
36. On phone: Developer options → enable **OEM unlocking** (greyed out = carrier/region locked, stop here).
37. Brand-specific gates: Xiaomi = bind a Mi account & wait 72h (or 168h); Motorola = get an unlock code from their site; Samsung = Knox trips **permanently** (Warranty bit) — accept or abort.
38. Enter bootloader: `adb reboot bootloader`
39. Confirm detection: `fastboot devices` (on WSL: `fastboot.exe devices`) — if empty, fix drivers (Steps 96–97) before going further.
40. Start the unlock: `fastboot flashing unlock` (older devices: `fastboot oem unlock`).
41. On the phone: a full-screen warning appears — use **volume keys** to select *Unlock the bootloader*, **power button** to confirm — this is the point of no return.
42. Wait for the wipe to finish and the phone to reboot (first boot can take several minutes).
43. Skip through setup — you'll restore from your Phase 3 backup later; you only need the OS up.
44. Re-enable Developer options + USB debugging again (a wipe resets them) and re-authorize the computer.
45. Verify: `adb shell getprop ro.boot.vbmeta.device_state` must now say `unlocked`.
46. Remember this rule forever: **never run `fastboot flashing lock` / `oem lock` unless the device is 100% stock** — locking over modified partitions bricks it and requires a full factory-image restore.

## Phase 5 — Get the matching stock boot image (Steps 47–58)

47. Read the exact fingerprint: `adb shell getprop ro.build.fingerprint` (e.g. `google/flame/flame:13/TP1A.220624.014/...`).
48. Read the display build ID: `adb shell getprop ro.build.display.id` → this string is your download search key.
49. **Pixel devices:** download the *factory image* for that exact build ID from `developers.google.com/android/images` (e.g. `flame-tp1a.220624.014-factory-<hash>.zip`).
50. Non-Pixel: get the **stock firmware package** for your exact model/region from the manufacturer (SamFw, Xiaomi firmware repo, etc.) — you need its `boot.img`/`init_boot.img` from the `images/` folder inside.
51. Alternative: the **full OTA** package for your build + `payload-dumper-go` extracts `boot.img` from `payload.bin` — useful when factory images don't exist (some OEMs).
52. **Cross-check the build ID inside the downloaded package before flashing anything** — filename, build.prop, and phone must all agree.
53. Extract the factory zip: `unzip <factory>.zip` → you get a folder with `image-<device>-<build>.zip` plus bootloader/radio files.
54. Extract the inner image zip: `unzip image-*.zip boot.img` (grab **only** `boot.img` — you don't need to flash anything else when just re-rooting).
55. **Android 13+ GKI devices:** if the package has `init_boot.img` instead of / alongside `boot.img`, **Magisk must patch `init_boot`** on those devices (Pixel 6+, many 2022+ devices). Patch whatever holds the ramdisk: `boot` on older devices, `init_boot` on newer.
56. Verify integrity: `sha256sum boot.img` and compare against a trusted source if available; at minimum confirm the zip tested clean (`unzip -t`).
57. Don't be alarmed by file dates: factory images stamp files with a fixed date (e.g. 2009-01-01) — the **build number** is what matters, not the timestamp.
58. Archive this stock `boot.img` in a folder named after the build — it is your unbrick lifeline and lets you restore unrooted state anytime.

## Phase 6 — Patch the image with Magisk (Steps 59–68)

59. Install the Magisk APK on the phone: `adb install Magisk-v<version>.apk`.
60. Push the stock image to the phone: `adb push boot.img /sdcard/Download/`
61. Open the **Magisk** app → tap **Install** (next to the Magisk card).
62. Choose **Select and patch a file**.
63. Navigate to `Download/boot.img` and select it.
64. Tap **Let's Go** → wait for **"All done!"** — the patched image lands in `/sdcard/Download/magisk_patched-<version>_<random>.img`.
65. Pull it: `adb pull /sdcard/Download/magisk_patched-*.img patched.img` — if several exist (old OTA cycles), pick the one with **today's timestamp**.
66. Sanity-check it's a real boot image: `file patched.img` (or `xxd | head`) must show the magic `ANDROID!`.
67. Confirm size equality: `ls -l boot.img patched.img` — both must be byte-identical in size (patching replaces content in place).
68. If you're on **WSL**: also copy the patched file to a Windows path (`cp patched.img /mnt/c/Users/<you>/Downloads/`) because Windows `fastboot.exe` can't read WSL paths reliably.

## Phase 7 — Flash the patched boot image (Steps 69–78)

69. Reboot to bootloader: `adb reboot bootloader`
70. ⚠️ **Do not press any buttons on the phone** while it sits on the fastboot screen — arrow keys navigate and the power button executes (people have locked/wiped by mis-pressing here).
71. Confirm detection: `fastboot devices` (WSL: `fastboot.exe devices`) — if empty, stop and do Steps 96–97.
72. Check the active slot: `fastboot getvar current-slot` (A/B devices) — modern fastboot flashes the active slot automatically when you say `flash boot`.
73. Flash: `fastboot flash boot patched.img` (newer devices with `init_boot`: `fastboot flash init_boot patched.img`).
74. Read the output: you must see `Sending ... OKAY` **and** `Writing ... OKAY` — any `FAILED` = stop, investigate, do not reboot blindly.
75. Reboot: `fastboot reboot`
76. Wait: first boot after patching takes 30–90 seconds — if the OS comes up, the hard part is over.
77. Some devices additionally need `fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img` **only if** they refuse the patched boot — Pixels generally don't; research your device before touching vbmeta.
78. Skip fastbootd (`fastboot reboot fastboot`) for plain boot-image flashes — stock bootloader mode is correct for this.

## Phase 8 — Verify root (Steps 79–88)

79. Wait for Android: `adb wait-for-device` / `adb devices` shows `device` again.
80. Open the Magisk app — it must show **Installed** with a version number (this confirms the patched boot is actually running).
81. Grant root: `adb shell su -c id` → the phone pops a Magisk grant dialog — **accept it** → output must be `uid=0(root)`.
82. Confirm the Magisk context: output should include a Magisk SELinux context (e.g. `u:r:magisk:s0`) — plain `root` without it may be something else entirely.
83. Check modules: Magisk app → Modules (or `adb shell su -c ls /data/adb/modules/`) — old modules from before the update may still be present; disable any that target the old Android version if things act up.
84. Check Zygisk: `adb shell su -c 'magisk --sqlite "SELECT * FROM settings"'` → `zygisk=1` means on (needed for Shamiko/Zygisk-based hiding); enable in Magisk → Settings if off, then reboot.
85. Optional integrity check: Play Integrity / SafetyNet may fail out of the box — that's what Shamiko + Play Integrity Fix modules are for; root itself is unaffected.
86. Verify nothing else broke: `adb shell pm list packages | wc -l` should be a normal number (hundreds), and your apps/data should be intact.
87. Ground-truth check for the *real* bootloader state (prop values can be spoofed by root-hiding modules): `adb shell su -c cat /proc/cmdline | tr ' ' '\n' | grep device_state` → `unlocked` = you're fine even if `getprop` claims "locked".
88. Restore your Phase 3 backup to the phone (`adb push ./backup/DCIM /sdcard/`) — a rooted phone is a great phone, but it's still a phone you want your photos on.

## Phase 9 — Keep root alive (Steps 89–94)

89. **Disable auto-updates NOW:** Settings → System → Developer options → *Automatic system updates* OFF (this is the #1 way people silently lose root).
90. When a "System update available" notification appears: **do not install it** unless you're ready to redo Steps 47–78 with the new build.
91. If you *do* update: root dies (or the update fails), then simply repeat Phase 5 → 7 with a factory image matching the **new** build number — no unlock needed, data survives.
92. Archive per build: keep `<build>/stock-boot.img` + `<build>/magisk-patched.img` folders so future re-rooting is a two-command job.
93. Update Magisk only through the Magisk app's own installer — never via random APKs or "Magisk Manager" look-alikes.
94. After flashing any module or changing Magisk settings, reboot fully; and keep the last known-good patched image on the computer for `fastboot flash boot` emergency re-flashes (no computer-side re-patch needed).

## Phase 10 — Troubleshooting & recovery (Steps 95–100)

95. **`adb devices` says `unauthorized`** → unlock the phone, tap *Allow* on the popup, check "Always allow"; still stuck? `adb kill-server && adb devices`.
96. **`fastboot devices` is empty (especially under WSL2 or Windows)** → use Windows `fastboot.exe`; if still empty, the bootloader-mode driver is missing: install Google USB Driver (its INF already contains the Pixel bootloader IDs) with admin `pnputil /add-driver android_winusb.inf /install` — a UAC prompt must be approved; Device Manager should then show *Android Bootloader Interface* with WinUSB.
97. **Device Manager shows the phone with error code 28 ("drivers for this device are not installed")** → same fix as 96; verify with `powershell Get-PnpDevice | where InstanceId -like '*18D1*'` that Status becomes OK and Service = WinUSB before retrying `fastboot devices`.
98. **Bootloop / stuck on logo after flashing** → don't panic: hold Power ~30s to force off, boot to bootloader (`adb reboot bootloader` won't work if Android won't start — use the button combo: hold Volume Down + Power), then `fastboot flash boot stock-boot.img` with the **stock** image from Step 58 — phone boots unrooted, data intact, then re-patch carefully.
99. **Root missing after reboot but boot is fine** → you likely flashed the wrong slot (check `getvar current-slot` vs what you flashed) or a Magisk module is looping (hold Volume Down during boot to skip modules, then disable the culprit in the app).
100. **Hard-brick (no bootloader, EDL/9008 mode or nothing at all)** → last resort: full factory-image restore (`flash-all` script) on a computer — this **wipes data**; on devices with EDL auth (Qualcomm) you may need an authorized account — never attempt EDL tricks on devices you don't own.

---

## Quick reference card

```bash
# --- the entire happy path, condensed ---
adb pull /sdcard/DCIM ./backup/                 # 1. backup
adb reboot bootloader                           # 2. to fastboot
fastboot getvar unlocked                        # 3. confirm unlock
#    (if locked: fastboot flashing unlock → wipes data)
adb reboot bootloader && adb push boot.img /sdcard/Download/
adb install Magisk.apk                          # 4. patch on phone:
#    Magisk → Install → Select and patch a file → boot.img
adb pull /sdcard/Download/magisk_patched-*.img  # 5. pull patched
adb reboot bootloader                           # 6. to fastboot
fastboot flash boot magisk_patched-*.img        # 7. flash
fastboot reboot                                 # 8. done
adb shell su -c id                              # 9. verify: uid=0(root)
```

**Restore unrooted:** `fastboot flash boot stock-boot.img` (the Step 58 archive).
**After every OTA:** repeat Steps 47–78 with the new build's image.
**Never:** relock the bootloader over modified images; flash a boot image from a different build; trust Magisk APKs from anywhere but the official GitHub.
