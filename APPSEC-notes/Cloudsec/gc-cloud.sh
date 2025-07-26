#!/bin/bash

set -e

echo "🔧 Updating package index..."
sudo apt update

echo "📦 Installing dependencies..."
sudo apt install -y apt-transport-https ca-certificates gnupg curl

echo "📥 Adding Google Cloud SDK source to APT..."
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | \
  sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list

echo "🔐 Importing Google Cloud public GPG key..."
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

echo "📥 Updating package index again..."
sudo apt update

echo "🚀 Installing Google Cloud SDK (gcloud)..."
sudo apt install -y google-cloud-sdk

echo "✅ Installation complete! Run 'gcloud auth login' to get started."
