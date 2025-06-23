#!/bin/bash

# Set Burp Suite IP and port
BURP_IP="192.168.122.1"
BURP_PORT="8080"

# Download Burp certificate
echo "Downloading Burp certificate from Burp Suite..."
curl -o cert.der http://$BURP_IP:$BURP_PORT/cert || { echo "Failed to download certificate. Ensure Burp Suite is running and listening on $BURP_IP:$BURP_PORT."; exit 1; }

# Convert the Burp certificate to PEM format
echo "Converting certificate from DER to PEM format..."
openssl x509 -inform der -in cert.der -out burpcert.pem || { echo "Failed to convert certificate format"; exit 1; }

# Generate the subject hash and rename the certificate
HASH=$(openssl x509 -inform PEM -subject_hash_old -in burpcert.pem | head -1)
echo "Renaming certificate to match subject hash: $HASH"
mv burpcert.pem "$HASH.0" || { echo "Failed to rename certificate"; exit 1; }

# Display certificate info for verification
echo "Displaying certificate subject information for verification..."
openssl x509 -inform PEM -subject -in "$HASH.0"

# List connected ADB devices
echo "Checking for connected ADB devices..."
adb devices || { echo "ADB is not working correctly"; exit 1; }

# Ensure ADB root and remount system as read-write
echo "Ensuring ADB root and remounting system as read-write..."
adb root || echo "Warning: Unable to switch to ADB root, continuing..."
adb remount || { echo "Failed to remount system as read-write"; exit 1; }

# Push the Burp certificate to the Android device
echo "Pushing the Burp certificate to the Android device..."
adb push "$HASH.0" /system/etc/security/cacerts/ || { echo "Failed to push certificate"; exit 1; }

# Fix permissions on the pushed certificate
echo "Fixing permissions on the certificate..."
adb shell "su -c 'chmod 644 /system/etc/security/cacerts/$HASH.0'" || { echo "Failed to set permissions"; exit 1; }

# Remount the system as read-only
echo "Remounting the Android system as read-only..."
adb remount || { echo "Failed to remount system as read-only"; exit 1; }

echo "Certificate setup complete!"
echo "Written by Ghost(Badmus)"
