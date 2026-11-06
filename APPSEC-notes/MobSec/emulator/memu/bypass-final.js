"use strict";
// Minimal bypass — only what's needed. No Build/SystemProperties spoof (breaks MEmu GPU).
// Root trigger: Gh/b.b() finds /system/xbin/su -> rootedOrJailbroken=true
// MEmu Build props already pass emulator checks (G011A, release-keys, qcom).
var TAG = "[BYPASS]";

function install() {
  Java.perform(function () {
    console.log(TAG + " installing...");

    // 1. Root check -> false
    try {
      var Ghb = Java.use("Gh.b");
      var bOvl = Ghb.b.overload();
      bOvl.implementation = function () {
        console.log(TAG + " Gh/b.b() [root] -> false");
        return false;
      };
      console.log(TAG + " hooked Gh/b.b");
    } catch (e) { console.log(TAG + " Gh/b.b ERR: " + e); }

    // 2. Clone check -> false
    try {
      var aOvl = Java.use("Gh.b").a.overload();
      aOvl.implementation = function () {
        console.log(TAG + " Gh/b.a() [clone] -> false");
        return false;
      };
      console.log(TAG + " hooked Gh/b.a");
    } catch (e) { console.log(TAG + " Gh/b.a ERR: " + e); }

    // 3. Hide su/magisk/frida file paths
    try {
      var File = Java.use("java.io.File");
      var existsOrig = File.exists.overload();
      var bad = [
        "/system/bin/su","/system/xbin/su","/sbin/su","/system/sd/xbin/su",
        "/system/bin/failsafe/su","/data/local/su","/data/local/bin/su",
        "/data/local/xbin/su","/su/bin/su","/vendor/bin/su",
        "/system/app/Superuser.apk","/system/xbin/busybox","/sbin/busybox",
        "/data/local/tmp/frida-server","/data/local/tmp/re.frida.server"
      ];
      File.exists.implementation = function () {
        var p = this.getAbsolutePath();
        for (var i = 0; i < bad.length; i++) {
          if (p === bad[i]) return false;
        }
        return existsOrig.call(this);
      };
      console.log(TAG + " hooked File.exists");
    } catch (e) { console.log(TAG + " File.exists ERR: " + e); }

    // 4. Hide root/xposed/clone packages
    try {
      var blocked = [
        "com.topjohnwu.magisk","eu.chainfire.supersu","com.koushikdutta.superuser",
        "de.robv.android.xposed.installer","com.saurik.substrate","com.lsposed.manager",
        "io.virtualapp","com.parallel.space.lite","com.excelliance.multiaccounts"
      ];
      var PM = Java.use("android.app.ApplicationPackageManager");
      PM.getPackageInfo.overloads.forEach(function (ovl) {
        ovl.implementation = function () {
          var pkg = arguments[0];
          if (typeof pkg === "string" && blocked.indexOf(pkg) !== -1) {
            throw Java.use("android.content.pm.PackageManager$NameNotFoundException").$new(pkg);
          }
          return ovl.apply(this, arguments);
        };
      });
      console.log(TAG + " hooked PackageManager");
    } catch (e) { console.log(TAG + " PM ERR: " + e); }

    // 5. Sanitize getSecurityReport response (covers isEmulator, hasTestKeys, devMode too)
    try {
      var AJO = Java.use("A.J0");
      var ovl = AJO.onMethodCall.overload(
        "io.flutter.plugin.common.MethodCall",
        "io.flutter.plugin.common.MethodChannel$Result"
      );
      ovl.implementation = function (call, result) {
        var m = call.method.value;
        if (m === "getSecurityReport") {
          console.log(TAG + " getSecurityReport — sanitizing");
          var B = Java.use("java.lang.Boolean");
          var Proxy = Java.use("java.lang.reflect.Proxy");
          var IH = Java.use("java.lang.reflect.InvocationHandler");
          var H = Java.registerClass({
            name: "com.bypass.SecH" + Date.now(),
            implements: [IH],
            fields: { target: "io.flutter.plugin.common.MethodChannel$Result" },
            methods: {
              invoke: function (proxy, method, args) {
                var t = this.target.value;
                var name = method.getName();
                if (name === "success" && args !== null && args.length > 0 && args[0] !== null) {
                  try {
                    var payload = args[0];
                    if (payload !== null && payload.put !== undefined) {
                      payload.put("rootedOrJailbroken", B.valueOf(false));
                      payload.put("cloneEnvironmentDetected", B.valueOf(false));
                      payload.put("devModeEnabled", B.valueOf(false));
                      payload.put("hasTestKeys", B.valueOf(false));
                      payload.put("processNameMismatch", B.valueOf(false));
                      if (payload.containsKey("isEmulator")) payload.put("isEmulator", B.valueOf(false));
                      console.log(TAG + "  sanitized: " + payload.toString());
                    }
                  } catch (e) { console.log(TAG + "  err: " + e); }
                }
                if (name === "success") { t.success(args[0]); return null; }
                if (name === "error") { t.error(args[0], args[1], args[2]); return null; }
                if (name === "notImplemented") { t.notImplemented(); return null; }
                return null;
              }
            }
          });
          var h = H.$new();
          h.target.value = result;
          var cls = Java.use("io.flutter.plugin.common.MethodChannel$Result").class;
          var arr = Java.array("java.lang.Class", [cls]);
          var wrapped = Proxy.newProxyInstance(cls.getClassLoader(), arr, h);
          ovl.call(this, call, wrapped);
          return;
        }
        // Force these three clean
        if (m === "detectCloneApp" || m === "isDeveloperModeEnabled" || m === "isEmulator") {
          console.log(TAG + " " + m + " -> false");
          result.success(B.valueOf(false));
          return;
        }
        ovl.call(this, call, result);
      };
      console.log(TAG + " hooked A/J0");
    } catch (e) { console.log(TAG + " A/J0 ERR: " + e); }

    // 6. device_info isPhysicalDevice=true
    try {
      var Veb = Java.use("Ve.b");
      var veOvl = Veb.onMethodCall.overload(
        "io.flutter.plugin.common.MethodCall",
        "io.flutter.plugin.common.MethodChannel$Result"
      );
      veOvl.implementation = function (call, result) {
        if (call.method.value === "getDeviceInfo") {
          var B = Java.use("java.lang.Boolean");
          var Proxy = Java.use("java.lang.reflect.Proxy");
          var IH = Java.use("java.lang.reflect.InvocationHandler");
          var H = Java.registerClass({
            name: "com.bypass.VeH" + Date.now(),
            implements: [IH],
            fields: { target: "io.flutter.plugin.common.MethodChannel$Result" },
            methods: {
              invoke: function (proxy, method, args) {
                var t = this.target.value;
                var name = method.getName();
                if (name === "success" && args !== null && args.length > 0 && args[0] !== null) {
                  try {
                    var payload = args[0];
                    if (payload !== null && payload.put !== undefined) {
                      payload.put("isPhysicalDevice", B.valueOf(true));
                      console.log(TAG + "  device_info: isPhysicalDevice=true");
                    }
                  } catch (e) {}
                }
                if (name === "success") { t.success(args[0]); return null; }
                if (name === "error") { t.error(args[0], args[1], args[2]); return null; }
                if (name === "notImplemented") { t.notImplemented(); return null; }
                return null;
              }
            }
          });
          var h = H.$new();
          h.target.value = result;
          var cls = Java.use("io.flutter.plugin.common.MethodChannel$Result").class;
          var arr = Java.array("java.lang.Class", [cls]);
          var wrapped = Proxy.newProxyInstance(cls.getClassLoader(), arr, h);
          veOvl.call(this, call, wrapped);
          return;
        }
        veOvl.call(this, call, result);
      };
      console.log(TAG + " hooked Ve/b");
    } catch (e) { console.log(TAG + " Ve/b ERR: " + e); }

    console.log(TAG + " ALL HOOKS INSTALLED (minimal — no Build spoof)");
  });
}

function waitForJava(retries) {
  if (typeof Java !== "undefined" && Java.available) {
    install();
  } else if (retries > 0) {
    setTimeout(function () { waitForJava(retries - 1); }, 50);
  } else {
    console.log(TAG + " FATAL: Java never available");
  }
}
waitForJava(400);
