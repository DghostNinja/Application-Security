#!/system/bin/sh

# Remount /system as read-write
mount -o remount,rw /system

# Enable TCP adbd on port 5555
setprop service.adb.tcp.port 5555
stop adbd
start adbd

# Make sure init.d exists
if [ ! -d /system/etc/init.d ]; then
    mkdir /system/etc/init.d
    chmod 755 /system/etc/init.d
fi

# Create the startup script
cat > /system/etc/init.d/99-enable-adbd-tcp <<'EOF'
#!/system/bin/sh
setprop service.adb.tcp.port 5555
stop adbd
start adbd
EOF
chmod 755 /system/etc/init.d/99-enable-adbd-tcp

# Remount /system read-only
mount -o remount,ro /system

echo "✅ ADB over TCP will be enabled at every boot!"
