"use strict";
var TAG = "[PROBE]";
function install() {
  Java.perform(function () {
    var AJO = Java.use("A.J0");
    var ovl = AJO.onMethodCall.overload("io.flutter.plugin.common.MethodCall", "io.flutter.plugin.common.MethodChannel$Result");
    var IH = Java.use("java.lang.reflect.InvocationHandler");
    ovl.implementation = function (call, result) {
      if (call.method.value === "getSecurityReport") {
        var H = Java.registerClass({
          name: "com.probe.H" + Date.now(), implements: [IH],
          fields: { target: "io.flutter.plugin.common.MethodChannel$Result" },
          methods: {
            invoke: function (proxy, method, args) {
              var t = this.target.value;
              var n = method.getName();
              if (n === "success" && args && args.length > 0 && args[0]) {
                var p = args[0];
                try { console.log(TAG + " P1 typeof=" + typeof p); } catch (e) { console.log(TAG + " P1 err " + e); }
                try { console.log(TAG + " P2 class=" + p.getClass().getName()); } catch (e) { console.log(TAG + " P2 err " + e); }
                try { console.log(TAG + " P3 typeof put=" + typeof p.put); } catch (e) { console.log(TAG + " P3 err " + e); }
                try { p.put("devModeEnabled", Java.use("java.lang.Boolean").valueOf(false)); console.log(TAG + " P4 direct put OK: " + p.toString()); } catch (e) { console.log(TAG + " P4 err " + e); }
                try {
                  var ObjectCls = Java.use("java.lang.Object");
                  var cl = p.getClass();
                  var m = cl.getMethod("put", Java.array("java.lang.Class", [ObjectCls.class, ObjectCls.class]));
                  m.invoke(p, Java.array("java.lang.Object", ["devModeEnabled", Java.use("java.lang.Boolean").valueOf(false)]));
                  console.log(TAG + " P5 reflect put OK: " + p.toString());
                } catch (e) { console.log(TAG + " P5 err " + e); }
              }
              if (n === "success") { t.success(args[0]); return null; }
              if (n === "error") { t.error(args[0], args[1], args[2]); return null; }
              if (n === "notImplemented") { t.notImplemented(); return null; }
              return null;
            }
          }
        });
        var h = H.$new();
        h.target.value = result;
        var cls = Java.use("io.flutter.plugin.common.MethodChannel$Result").class;
        var wrapped = Java.use("java.lang.reflect.Proxy").newProxyInstance(cls.getClassLoader(), Java.array("java.lang.Class", [cls]), h);
        ovl.call(this, call, wrapped);
        return;
      }
      ovl.call(this, call, result);
    };
    console.log(TAG + " hooked");
  });
}
function w(r) { if (typeof Java !== "undefined" && Java.available) install(); else if (r > 0) setTimeout(function(){w(r-1);}, 50); }
w(400);
