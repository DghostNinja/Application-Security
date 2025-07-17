#!/bin/bash

# Prompt for domain input
read -p "Enter the target domain (e.g., example.com): " domain

# Validate: only accept domain or URL starting with http(s)
if ! [[ "$domain" =~ ^(https?://)?[a-zA-Z0-9.-]+\.[a-z]{2,}$ ]]; then
    echo "[!] Invalid domain format. Use something like: example.com or https://example.com"
    exit 1
fi

# Strip protocol if included
clean_domain=$(echo "$domain" | sed -E 's~https?://~~' | cut -d/ -f1)

# Create recon directory
mkdir -p recon
cd recon || exit

echo "[*] Running Subfinder..."
subfinder -d "$clean_domain" -silent | sort -u > subs.txt

# Always include the original domain in subs.txt
echo "$clean_domain" >> subs.txt
sort -u subs.txt -o subs.txt
echo "[+] Total domains to probe: $(wc -l < subs.txt)"

echo "[*] Probing with httpx..."
cat subs.txt | httpx -silent -title -status-code -tech-detect > live-sub.txt

echo "[*] Running Waybackurls..."
cat subs.txt | waybackurls | sort -u > wayback.tmp

echo "[*] Running GAU..."
cat subs.txt | gau | sort -u > gau.tmp

# Combine and deduplicate only after both are finished
cat wayback.tmp gau.tmp | sort -u > way.txt
rm wayback.tmp gau.tmp

echo "[*] Probing historic URLs with httpx..."
cat way.txt | httpx -silent -title -status-code -tech-detect > live-history.txt

echo "[*] Running ParamSpider..."
paramspider -d "$clean_domain" > params.txt

echo "[✔] Recon complete for $clean_domain. Files saved in ./recon 🎯"
