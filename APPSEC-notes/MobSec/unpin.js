/*
 * unpin.js — native OkHttp/Android unpinning for com.innovantics.bbb.sterling
 * NOT a Flutter script. This hooks:
 *   - okhttp3.CertificatePinner   (pins are empty here, but harmless to cover)
 *   - Android conscrypt TrustManagerImpl.verifyChain  (this is what enforces
 *     the app's network_security_config system-only trust -> the "internet drops")
 *   - javax.net.ssl trust managers / SSLContext as a final fallback
 *
 * Usage (from Windows Tools dir):
 *   frida -U -f com.innovantics.bbb.sterling -l unpin.js
 * or with a running app:
 *   frida -U -n com.innovantics.bbb.sterling -l unpin.js
 */

Java.perform(function () {
    console.log('[*] Starting native unpin hooks...');

    /* --- 1) OkHttp CertificatePinner --- */
    try {
        var CP = Java.use('okhttp3.CertificatePinner');
        var cpMethods = CP.check.overloads;
        cpMethods.forEach(function (ov) {
            ov.implementation = function () {
                console.log('[+] okhttp CertificatePinner.check bypassed');
            };
        });
        try {
            CP.check$okhttp.implementation = function () {
                console.log('[+] okhttp check$okhttp bypassed');
            };
        } catch (e) {}
        console.log('[+] okhttp3.CertificatePinner hooked (' + cpMethods.length + ' overloads)');
    } catch (e) {
        console.log('[!] CertificatePinner hook failed: ' + e);
    }

    /* --- 2) Android conscrypt TrustManagerImpl.verifyChain ---
       This is the enforcement point for network_security_config.
       Returning the UNVERIFIED chain skips CA/user-cert validation. */
    try {
        var TMI = Java.use('com.android.org.conscrypt.TrustManagerImpl');

        // 6-arg: (chain, authType, host, clientAuth, ocspData, tlsSctData)
        try {
            TMI.verifyChain.overload(
                '[Ljava.security.cert.X509Certificate;',
                'java.lang.String',
                'java.lang.String',
                'boolean',
                'java.util.List',
                'java.util.List'
            ).implementation = function (unverifiedChain, authType, host, clientAuth, ocsp, tlsSct) {
                console.log('[+] verifyChain(6) bypassed for ' + host);
                return unverifiedChain;
            };
        } catch (e) {}

        // 7-arg: (+ pinnedChain) newer Android
        try {
            TMI.verifyChain.overload(
                '[Ljava.security.cert.X509Certificate;',
                'java.lang.String',
                'java.lang.String',
                'boolean',
                'java.util.List',
                'java.util.List',
                'java.util.List'
            ).implementation = function (unverifiedChain, authType, host, clientAuth, ocsp, tlsSct, pinnedChain) {
                console.log('[+] verifyChain(7) bypassed for ' + host);
                return unverifiedChain;
            };
        } catch (e) {}

        // 3-arg: (chain, authType, host) fallback
        try {
            TMI.verifyChain.overload(
                '[Ljava.security.cert.X509Certificate;',
                'java.lang.String',
                'java.lang.String'
            ).implementation = function (unverifiedChain, authType, host) {
                console.log('[+] verifyChain(3) bypassed for ' + host);
                return unverifiedChain;
            };
        } catch (e) {}

        console.log('[+] com.android.org.conscrypt.TrustManagerImpl hooked');
    } catch (e) {
        console.log('[!] TrustManagerImpl hook failed: ' + e);
    }

    /* --- 3) Fallback: replace SSLContext TrustManagers --- */
    try {
        var SSLContext = Java.use('javax.net.ssl.SSLContext');
        var X509TM = Java.use('javax.net.ssl.X509TrustManager');
        var TrustManagerArr = Java.registerClass({
            name: 'com.pentest.TrustAllX509',
            implements: [X509TM],
            methods: {
                checkClientTrusted: function (chain, authType) {},
                checkServerTrusted: function (chain, authType) {
                    console.log('[+] TrustAllX509.checkServerTrusted');
                },
                getAcceptedIssuers: function () { return []; }
            }
        });

        SSLContext.init.overload(
            '[Ljavax.net.ssl.KeyManager;',
            '[Ljavax.net.ssl.TrustManager;',
            'java.security.SecureRandom'
        ).implementation = function (km, tm, sr) {
            console.log('[+] SSLContext.init -> injecting TrustAll');
            this.init(km, [TrustManagerArr.$new()], sr);
        };
        console.log('[+] SSLContext fallback hooked');
    } catch (e) {
        console.log('[!] SSLContext fallback hook failed: ' + e);
    }

    console.log('[*] All hooks installed. Now trigger app traffic -> should appear in HTTP Toolkit.');
});
