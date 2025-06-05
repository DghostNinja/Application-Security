Java.perform(function () {
    var Build = Java.use("android.os.Build");
    var Debug = Java.use("android.os.Debug");
    var File = Java.use("java.io.File");
    var Runtime = Java.use("java.lang.Runtime");
    var System = Java.use("java.lang.System");
    var ProcessBuilder = Java.use("java.lang.ProcessBuilder");

    // 1. Fake device properties to bypass emulator checks
    Build.FINGERPRINT.value = "samsung/beyond1xx/beyond1:10/QP1A.190711.020/XXXXXX:user/release-keys";
    Build.MODEL.value = "SM-G975F";
    Build.MANUFACTURER.value = "samsung";
    Build.BRAND.value = "samsung";
    Build.DEVICE.value = "beyond1";
    Build.PRODUCT.value = "beyond1";
    Build.HARDWARE.value = "samsungexynos9820";

    // 2. Hide debugger connection
    Debug.isDebuggerConnected.implementation = function () {
        return false;
    };

    // 3. Hide su, magisk, busybox files existence (root binaries)
    File.exists.implementation = function () {
        var path = this.getAbsolutePath();
        if (
            path.indexOf("su") !== -1 ||
            path.indexOf("magisk") !== -1 ||
            path.indexOf("busybox") !== -1 ||
            path.indexOf("supersu") !== -1 ||
            path.indexOf("xbin") !== -1
        ) {
            return false;
        }
        return this.exists();
    };

    // 4. Hide suspicious properties from getprop and System.getProperty
    var suspiciousProps = [
        "ro.debuggable",
        "ro.secure",
        "ro.build.tags",
        "ro.kernel.qemu",
        "ro.boot.selinux",
        "ro.boot.veritymode"
    ];
    System.getProperty.overload('java.lang.String').implementation = function (key) {
        if (suspiciousProps.indexOf(key) !== -1) {
            if (key === "ro.debuggable") return "0";
            if (key === "ro.secure") return "1";
            if (key === "ro.build.tags") return "release-keys";
            if (key === "ro.kernel.qemu") return "0";
            if (key === "ro.boot.selinux") return "enforcing";
            if (key === "ro.boot.veritymode") return "enforcing";
        }
        return this.getProperty(key);
    };

    // 5. Block Runtime.exec() and ProcessBuilder.start() for root commands
    var rootCmds = ["su", "which su", "id", "getprop ro.build.tags", "mount", "ps", "busybox"];

    Runtime.exec.overload('java.lang.String').implementation = function (cmd) {
        for (var i = 0; i < rootCmds.length; i++) {
            if (cmd.indexOf(rootCmds[i]) !== -1) {
                console.log("[*] Blocked Runtime.exec call: " + cmd);
                // Return dummy Process or null; frida cannot directly create Process, so skip exec
                throw new Error("Command blocked by frida script");
            }
        }
        return this.exec(cmd);
    };

    Runtime.exec.overload('[Ljava.lang.String;').implementation = function (cmdArray) {
        for (var i = 0; i < rootCmds.length; i++) {
            for (var j = 0; j < cmdArray.length; j++) {
                if (cmdArray[j].indexOf(rootCmds[i]) !== -1) {
                    console.log("[*] Blocked Runtime.exec array call: " + cmdArray.join(" "));
                    throw new Error("Command blocked by frida script");
                }
            }
        }
        return this.exec(cmdArray);
    };

    ProcessBuilder.start.implementation = function () {
        var cmdArray = this.command();
        for (var i = 0; i < rootCmds.length; i++) {
            for (var j = 0; j < cmdArray.size(); j++) {
                if (cmdArray.get(j).indexOf(rootCmds[i]) !== -1) {
                    console.log("[*] Blocked ProcessBuilder command: " + cmdArray.toString());
                    throw new Error("Command blocked by frida script");
                }
            }
        }
        return this.start();
    };

    // 6. Prevent su process check via /proc
    var FileInputStream = Java.use("java.io.FileInputStream");
    FileInputStream.$init.overload('java.io.File').implementation = function (file) {
        var path = file.getAbsolutePath();
        if (path.indexOf("/proc/") !== -1 && path.indexOf("cmdline") !== -1) {
            var data = this.readBytes();
            var content = Java.array('byte', data);
            var contentStr = "";
            for (var i = 0; i < content.length; i++) {
                contentStr += String.fromCharCode(content[i]);
            }
            if (contentStr.indexOf("su") !== -1) {
                throw new Error("Blocked su process read");
            }
        }
        return this.$init(file);
    };

    console.log("[+] Root, emulator, and debugger detection bypassed.");
});
