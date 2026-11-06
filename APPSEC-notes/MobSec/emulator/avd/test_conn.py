import frida
d = frida.get_usb_device(timeout=10)
print("OK:", d.name)
