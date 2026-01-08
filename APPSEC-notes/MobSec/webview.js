Java.perform(function () {
    const Application = Java.use("android.app.Application");

    Application.onCreate.implementation = function () {
        console.log("[+] Application.onCreate()");

        this.onCreate();

        try {
            const WebView = Java.use("android.webkit.WebView");
            WebView.setWebContentsDebuggingEnabled(true);
            console.log("[+] WebView debugging ENABLED");
        } catch (e) {
            console.log("[-] Failed to enable WebView debugging: " + e);
        }
    };
});
