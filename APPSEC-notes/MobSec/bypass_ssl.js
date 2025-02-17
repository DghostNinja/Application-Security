Java.perform(function () {
    console.log("[*] Starting SSL Pinning Bypass");

    var sslContext = Java.use("javax.net.ssl.SSLContext");
    var trustManager = Java.use("javax.net.ssl.X509TrustManager");
    var hostnameVerifier = Java.use("javax.net.ssl.HostnameVerifier");

    // Hook SSLContext.init
    sslContext.init.overload(
        "[Ljavax.net.ssl.KeyManager;", "[Ljavax.net.ssl.TrustManager;", "java.security.SecureRandom"
    ).implementation = function (keyManager, trustManager, secureRandom) {
        console.log("[+] Hooked SSLContext.init()");

        var trustManagers = Java.array("javax.net.ssl.TrustManager", [Java.use("android.net.http.X509TrustManagerExtensions").$new()]);

        this.init(keyManager, trustManagers, secureRandom);
    };

    // Hook HostnameVerifier
    hostnameVerifier.verify.overload("java.lang.String", "javax.net.ssl.SSLSession").implementation = function (host, session) {
        console.log("[+] Bypassing Hostname Verification for: " + host);
        return true;
    };

    console.log("[*] SSL Pinning Bypassed!");
});
