# Mobile Hacking Skills Reference (Android)

A field-tested reference for analyzing and attacking Android applications — built from the
CMPen CTF and general mobile-appsec tradecraft. Use this as the playbook whenever a mobile
appsec task arrives.

---

## 0. Ethos & Scope

- This is for **authorized testing only**: your own apps, lab CTFs, or engagements with permission.
- Every technique below is reversible — attackers use it, defenders enumerate it to fix. Frame findings as fixes, not just exploits.
- Goal: identify **root cause -> impact -> exploit** and deliver a **repro + fix** per finding.

---

## 1. The Mobile-Audit Pipeline

Always run in this order. Each stage feeds the next and de-risks the later ones.

```
1. RECON (identify targets/assets)
2. STATIC ANALYSIS (read everything without running)
3. DYNAMIC ANALYSIS (run it, poke it, trace it)
4. NETWORK INTERCEPTION (watch/redirect traffic)
5. EXPLOITATION → REPORT
```

Skip-ahead only when you have a strong lead; otherwise the pipeline prevents blind alleys.

---

## 2. Recon — Before You Touch the Binary

### App inventory
- Gather APK, version, package name, targetSdk/minSdk.
- `targetSdk` is the single most predictive flag of modern-vs-legacy security posture.
- Note connected devices (real vs emulator) — emulator evidence (goldfish/ranchu, sdk) is itself a fingerprint an app may check.

### Environment facts worth recording
- OS, ADB version, root status, VPN topology (WSL/VM vs host networking breaks reachability to internal CTF/vuln targets).

---

## 3. Static Analysis — Reading the App Cold

### Step 1 — Extract & inspect structure
```bash
apktool d app.apk -o out/          # smali + resources (rebuildable)
unzip -l app.apk | grep -iE "META-INF|\.so$|\.dex$|\.yml$|\.xml$"
```
**apktool.yml**: `targetSdkVersion`, `minSdkVersion`, `versionName`, unknown files (native libs / extra assets).

### Step 2 — Manifest triage (always, it's the map)
```bash
grep -oE 'android:permission\.[A-Z_]+' out/AndroidManifest.xml | sort -u
grep -oE '<(activity|service|receiver|provider)[^>]*android:exported="true"' out/AndroidManifest.xml
grep -oE 'android:(debuggable|allowBackup|usesCleartextTraffic|networkSecurityConfig)="[^"]*"' out/AndroidManifest.xml
grep -oE 'android:exported="true"' out/AndroidManifest.xml
cat out/res/xml/network_security_config.xml 2>/dev/null
```
Check: exported components, debug flag, backup, cleartext, NSC pin-set, custom permissions, intent filters reachable from outside.

### Step 3 — Rapid string / secret sweep
```bash
grep -rhoE 'const-string v[0-9]+, "[^"]*"' out/smali/<pkg>/*.smali | grep -oE '"[^"]*"' | sort -u
grep -riE "secret|password|apikey|token|key|Bearer|Basic |BEGIN" out/ --include="*.xml" --include="*.smali"
grep -rhoE '(password|passwd|user|username) ?[\'\"]?\s*[:=]\s*[\'\"][^\"\']+' out/res/ out/smali/<pkg>/ 2>/dev/null
```

### Step 4 — Library & version census
- Read `smali/okhttp3/internal/Version.smali`, `smali/retrofit2/Retrofit.smali`, `META-INF/*.version`.
- Cross-check every suspect version against CVE feeds / EOL lists (e.g. OkHttp 3.x EOL; DES/MD5/SHA1 algorithm deprecations).
- Look for embedded native libs (`*.so`) — those often hold the real secrets/roots-of-trust.

### Step 5 — Crypto inventory
```bash
grep -rE 'Cipher\.getInstance|SecretKeySpec|DES|AES|RSA|"ECB"|"CBC"|PKCS5|SHA1|MD5' out/smali/<pkg>/
```
Crypto red flags:
- hardcoded keys next to ciphertext (identity of adversary trivial)
- ECB mode (deterministic, leaks block patterns)
- legacy/broken algos: DES, 3DES, RC4, MD5, SHA1, RSA with e=3
- keys in SharedPreferences, build config, or `strings.xml`

---

## 4. Vulnerability Classes — Test Playbooks

For each: **identify → confirm → exploit → fix**.

### 4.1 Hardcoded Secrets / Credentials / Keys
- **Identify**: string sweep + crypto inventory.
- **Confirm**: map each secret to its usage (parameter name, header, cipher key).
- **Exploit**: decrypt blobs with recovered keys; reuse creds on exposed endpoints.
- **Fix**: Android Keystore, runtime secret delivery, no secrets in `strings.xml`.

### 4.2 Root Detection & Anti-Analysis
- **Identify**: grep for `su`, `test-keys` (build tag), `/system/xbin/which`, mount checks.
- **Classify bypassability**: single choke point → trivially patchable (Magisk hides su; patching one check defeats all).
- **Exploit**: Frida hook to force `false` / return true; patch smali; run on Magisk.
- **Fix**: layered + server-side enforcement, never security through one client check.

### 4.3 SSL/TLS Pinning
- **Identify**: OkHttp `CertificatePinner`, NSC `<pin-set>`, TrustManager overrides, `X509TrustManager`, `checkServerTrusted`, third-party libs (TrustKit).
- **Bypass ladder** (least → most invasive):
  1. Frida `ssl_pinning_bypass` / objection `android sslpinning disable`
  2. Hook `CertificatePinner.check` / `TrustManagerImpl.verifyChain`
  3. Repackage: replace pinned hashes with your MITM cert (needs re-sign).
  4. Patch smali to no-op.
- **Evidence**: capture the request the pin "protects" and demonstrate MITM read.
- **Note**: pinning is a control, not an endpoint; inventory base URLs & header requirements from `APIInterface`/Retrofit config.

### 4.4 Insecure Logging
- **Identify**: `Log.d/i/w/e`, `android.util.Log`, `System.out`, custom logger around sensitive ops.
- **Prize**: passwords/tokens/keys/`decryptData key:` style leaks in logcat.
- **Exploit**: `adb logcat`, filter by tag; correlate leaked values to live endpoints.
- **Fix**: redaction, no secrets in logs, minimal log levels in release.

### 4.5 Exported Components (Insecure Activities/Providers/Receivers)
- **Identify**: `android:exported="true"` + no permission, no intent-filter.
- **Exploit** (from outside the app):
```bash
adb shell am start -n <pkg>/.FlagActivity
adb shell am start -n <pkg>/.Activity --es extra "value"
adb shell content call --uri content://<pkg>/...   # providers
adb shell am broadcast -n <pkg>/.Receiver -a ACTION   # receivers
```
- **Fix**: `exported=false` (or explicit permission), validate intents.

### 4.6 Auth Bypass / Logical Flaws
- **Identify**: enumerate endpoints (Retrofit interface, strings, bots, `strings` on DEX); test auth on each.
- **Attack surface**:
  - unauthenticated admin/log endpoints
  - client-side-only authz decisions
  - predictable session tokens, missing BFLA/IDOR checks
  - `null` vs missing vs wrong-token behavior differences.
- **Exploit**: direct `curl` of unauthenticated endpoints; replay a dev token.
- **Fix**: server-side authz on every route, don't trust client state.

### 4.7 Misconfigured Backends — Firebase & Friends
- **REST probe** (public read/write misconfig):
```bash
curl -sk "<firedb-url>/.json"                       # root dump
curl -sk "<firedb-url>/<path>.json"
curl -sk -X PUT -d '{"pwned":1}' "<firedb-url>/probe.json"   # test write
```
- Also probe: exposed S3 buckets, iCloud containers, unauthenticated GraphQL/REST, admin panels (`/admin`, `/server_status`, hidden paths).
- **Fix**: rules deny by default + per-node auth.

### 4.8 Cleartext Traffic
- **Identify**: `usesCleartextTraffic="true"` or NSC `cleartextTrafficPermitted="true"`.
- **Exploit**: force the app to plain HTTP, sniff with mitmproxy/tcpdump; look for creds/tokens/req bodies.
- **Fix**: HTTPS-only NSC + `usesCleartextTraffic=false`.

### 4.9 Backup & Data Extraction
- **Identify**: `android:allowBackup="true"`.
- **Exploit**:
```bash
adb backup -f data.ab <pkg>            # produces .ab archive
# unpack with 'abe': java -jar abe.jar unpack data.ab data.tar
# also: adb restore data.ab   (data injection: overwrite app state)
```
- **Prize**: SharedPreferences tokens, DBs, cached JWT/keys.
- **Fix**: `allowBackup=false` or strict `fullBackupContent`.

### 4.10 Insecure / Over-privileged Permissions
- **Identify**: permission list vs. actual API usage (`grep` app code for storage/contacts/location etc.).
- **Prize**: dangerous permissions requested but unused → pure attack surface (e.g. READ/WRITE_EXTERNAL_STORAGE with zero storage code).
- **Fix**: least privilege, scoped APIs (MediaStore/SAF).

### 4.11 Debuggable & Anti-Debug
- **Identify**: `android:debuggable="true"` + presence/absence of anti-debug (ptrace, `Debug.isDebuggerConnected`, Frida checks, timing).
- **Exploit when debuggable & unprotected**: attach jdb, dump memory, read fields, hot-patch checks mid-run.
- **Fix**: release `debuggable=false` + tamper/debug detection (still defeatable — layering).

### 4.12 Signing & Update Security
- **Inspect** signer:
```bash
openssl pkcs7 -inform DER -in META-INF/CERT.RSA -print_certs -noout | grep -iE "subject|issuer"
openssl pkcs7 -inform DER -in META-INF/CERT.RSA -print_certs -noout -text | grep -iE "Not Before|Not After"
```
- **Classify**: `CN=Android Debug,O=Android,C=US` → **debug cert** (password `android`, public template) → can re-sign tampered builds → integrity defeats.
- **Signature schemes & targetSdk**:
  - v1 (JAR) — obsolete; **disabled for targetSdk ≥ 30** (Android 11+); vulnerable to entry-level tamper (Janus/downgrade).
  - v2 — whole-file, current standard (API 24+).
  - v3/v3.1 — key rotation (API 28+).
  - fixture: `targetSdk 33` + v1 files only ⇒ **v1 is the obsolete scheme**.
- **Fix**: release key, v2+v3, Play App Signing, key rotation.

### 4.13 Outdated Libraries / Supply Chain
- **Identify**: version markers in smali, `META-INF/*.version`, gradle metadata.
- **Assess**: EOL branches + active CVEs in the *security-critical* stack (OkHttp/TLS, WebView, crypto providers).
- **Fix**: upgrade, automate dependency scanning (Dependency-Check / gradle `dependencyUpdates`).

---

## 4.14 Field Notes — OneBank / Sterling (com.innovantics.bbb.sterling)

Observed on the `BSSIS_PILOT.apk` (versionName `6-pentest`, targetSdk 34, native app). Revisit these on every run — they shortcut the pipeline.

### App identity & stack (read BEFORE attaching)
- **Native Kotlin + OkHttp/Retrofit — NOT Flutter.** `flutter.js`/`libflutter.so` bypass is a no-op; the agent errors `libflutter.so not found`. Use the OkHttp/native unpin path below.
- Pinning state: `CERTIFICATE_PINS` (`Li/a;->b`) is an **empty array**; `NetworkModule.smali` reads it but never calls `.certificatePinner(...)` → **no real pinning**. No need to defeat pins.
- Base URL: `https://biometricselfservice.sterling.ng/` (`Li/a;->a`). API paths: `/deviceauth`, `/DeviceAuth/persona-login`, `/banks`, `/branches/customer`, `/feedback`, `/tellerauth`, `/accountenquiry`, `/customerauth/otp/request`.
- Crypto is sound: AES/GCM via Android Keystore, RSA/KeyStore, no hardcoded secrets found in app smali.

### The MITM gotcha — NSC system-only trust ("internet drops")
- `res/xml/network_security_config.xml`: base-config `cleartextTrafficPermitted="false"` + **system-only** trust anchors for the prod host. HTTP Toolkit/Burp installs its CA as a **user** cert → app TLS handshake **fails on every request** → looks like the app loses internet (it's the app, not other apps).
- Exception: `3bapp.innovantics.com` and `api.innovantics.com` **do** trust user CAs in the NSC — those hosts are MITM-able with zero bypass.
- **Fix/bypass ladder for this app:**
  1. Frida: hook `com.android.org.conscrypt.TrustManagerImpl.verifyChain` (all overloads) → return the unverified chain. This is the NSC enforcement point.
  2. Belt-and-suspenders: also hook `okhttp3.CertificatePinner.check*` and `SSLContext.init` → TrustAll.
  3. Rooted: install CA as a **system** cert (`/system/etc/security/cacerts/`) — app trusts system CAs.
  4. Do NOT waste time with Flutter bypasses.

### Signing red flag
- Signer chains to **Wizarpos `releasetestv1` (Testing) CA** (issuer `O=wizarpos, OU=Testing, CN=releasetestv1`), subject `O=Innovantics Ltd, CN=3BApp`. Banking app signed via vendor *testing* CA → repackage/re-sign risk if that CA leaks.
- Check `META-INF/CERT.RSA` before trusting any tamper-resistance claim.

### System-CA install on MEmu emulator (when Frida-only unpin isn't enough)
If app-side TLS is already bypassed (hooks fire) but traffic still doesn't surface, the blocker is the
*user* CA being rejected by NSC — install the CA as a **system** cert so the app trusts it natively.

Pre-req: enable **root** in MEmu (`MEmu settings ⚙ → Other → Root`) and fully restart the emulator.
```bat
:: 1. root + remount system
adb root && adb wait-for-device && adb remount
:: 2. pull the CA HTTP Toolkit already installed as a *user* cert (already hashed, no openssl needed)
adb shell su -c "cp -r /data/misc/user/0/cacerts-added/ /sdcard/cacerts-added/"
adb pull /sdcard/cacerts-added/ C:\path\to\cacerts-added
:: 3. push into system store
adb shell su -c "mount -o rw,remount /system"
adb shell su -c "mkdir -p /system/etc/security/cacerts"
for %%f in (C:\path\to\cacerts-added\*) do (
  adb shell su -c "cp /sdcard/cacerts-added/%%~nxf /system/etc/security/cacerts/%%~nxf"
  adb shell su -c "chmod 644 /system/etc/security/cacerts/%%~nxf"
  adb shell su -c "chown root:root /system/etc/security/cacerts/%%~nxf"
)
:: 4. SELinux context + reboot
adb shell su -c "chcon u:object_r:system_file:s0 /system/etc/security/cacerts/*"
adb reboot
```
Verify after boot:
```bat
adb shell su -c "ls -l /system/etc/security/cacerts/"
adb shell settings get global http_proxy   REM must show the HTTP Toolkit proxy; empty = proxy not applied to the app
```
Debug tip: if hooks fire but traffic never shows, suspect proxy delivery (MEmu drops `adb reverse`
tunnels on reboot — re-set in HTTP Toolkit after `adb root`), not the app's TLS.

---

## 5. Dynamic Analysis Cheatsheet

### Emulator & device prep
```bash
adb devices
adb install -r app.apk
# emulator detection note: build props (goldfish/ranchu/geny) are fingerprints.
```

### Logcat discipline
```bash
adb logcat -v time | grep -iE "flag|key|secret|password|token|decrypt"
adb logcat -v time *:S TAG:I        # isolate a tag
```

### Frida (de facto standard)
```bash
pip install frida-tools objection
frida-ps -U
frida -U -f <pkg> -l hook.js
objection -g <pkg> explore
#  android sslpinning disable
#  android root disable
#  memory dump / dump keystore
```
Marker snippets:
- bypass root: hook the check method → return false/true as needed.
- dump method args/returns: `Interceptor.attach(target, { onEnter/onLeave })`.
- patch decisions: replace return values, bypass PIN dialogs, skip flags.

### Network interception
- mitmproxy + emulator `-http-proxy` + iOS/Android CA install;
- Frida SSL-unpinning for encrypted traffic;
- compare responses across headers/tokens (authz fuzzing: `Authorization: Bearer x`, `insecure-activity: <leaked>` etc.)

---

## 6. Reporting Template (per finding)

```
## [Severity] Title
- LOCATION      : file:line / component / endpoint
- TYPE          : OWASP/MASVS category
- ROOT CAUSE    : why it exists (one sentence)
- IMPACT        : what an attacker gets (credential leak, MITM, tamper, RCE...)
- REPRODUCE     : exact commands/steps (someone must be able to re-run it)
- EVIDENCE      : output, screenshots, dumps
- FIX           : concrete remediation + verification
```

`Severity` scale: Critical (RCE/seed data/credential theft) → High (MITM/tamper) →
Medium (data exposure/over-privilege) → Low (hygiene/EOL libs) → Info.

---

## 7. MASVS / OWASP Mapping Quick View

| Finding | MASVS |
|---------|-------|
| Hardcoded secrets, weak crypto | MSTG-CRYPTO |
| Root detection bypass, debuggable | MSTG-RESILIENCE |
| Pinning weak, cleartext | MSTG-NETWORK |
| Exported components, backup, storage | MSTG-PLATFORM |
| Auth bypass/logical flaws, insecure logging | MSTG-AUTH / MSTG-CODE |
| Outdated libs, signing | Supply-chain / MASVS-STORAGE |

---

## 8. Fast-Reference Command Bank

```bash
# recon
aapt dump badging app.apk | grep -E "package|sdkVersion|targetSdkVersion"
apktool d app.apk -o out
# manifest flags
grep -oE 'android:(debuggable|allowBackup|usesCleartextTraffic)="true"' out/AndroidManifest.xml
# secrets
grep -rhoE 'const-string v[0-9]+, "[^"]*"' out/smali/<pkg>/*.smali | grep -oE '"[^"]*"' | sort -u
# components
grep -oE '<(activity|service|receiver|provider)[^>]*exported="true"' out/AndroidManifest.xml
# decrypt demo (DES from recovered key)
echo -n "<ciphertext b64>" | openssl enc -d -des-ecb -K $(printf %s "<key>" | xxd -p)
# native (non-Flutter) NSC unpin — see §4.14 for the OneBank case
frida -U -f com.innovantics.bbb.sterling -l unpin.js   # hooks TrustManagerImpl.verifyChain + CertificatePinner
# signer
openssl pkcs7 -inform DER -in out/original/META-INF/CERT.RSA -print_certs | grep -iE "subject|issuer"
# firebase misconfig
curl -sk "<url>/.json"
# dynamic
adb logcat -v time | grep -iE "secret|key|token|password|flag"
adb shell am start -n <pkg>/.<ExportedActivity>
adb backup -f data.ab <pkg> && java -jar abe.jar unpack data.ab data.tar
frida -U -f <pkg> -l hook.js    # objection android sslpinning disable / android root disable
```

---

## 9. Mindset Notes (sharp edges)

- **The endpoint is the real target.** Client checks (root, pinning, authz) are theater if the server doesn't enforce.
- **Everything recoverable = do not fight it, prove it.** If a key is in the APK, treat data as plaintext.
- **Log everything, correlate everything.** A leaked log value + a header = a flag.
- **Read the manifest before the code.** It's the attack-surface map; most wins start there.
- **Verify re-runnable reproduces.** A finding without a repro is a rumor.
- **Fix-first framing**: every exploitation step has a corresponding hardening step — deliver both.
