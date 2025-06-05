Java.perform(function () {
    var Build = Java.use("android.os.Build");
    var Debug = Java.use("android.os.Debug");

    // Bypass "Build.FINGERPRINT" and related emulator checks
    Build.FINGERPRINT.value = "samsung/SM-G975F";
    Build.MODEL.value = "SM-G975F";
    Build.MANUFACTURER.value = "samsung";
    Build.BRAND.value = "samsung";
    Build.DEVICE.value = "beyond1";
    Build.PRODUCT.value = "beyond1";

    // Bypass Debug checks
    Debug.isDebuggerConnected.implementation = function () {
        return false;
    };

    // Optional: Bypass common root file checks
    var File = Java.use("java.io.File");
    File.exists.implementation = function () {
        var name = this.getAbsolutePath();
        if (
            name.indexOf("su") !== -1 ||
            name.indexOf("busybox") !== -1 ||
            name.indexOf("magisk") !== -1
        ) {
            return false;
        }
        return this.exists();
    };

    console.log("[+] Root and emulator checks bypassed.");
});
