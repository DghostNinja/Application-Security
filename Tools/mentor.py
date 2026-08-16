#!/usr/bin/env python3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import binascii
import base64
import os
import sys

# Install with - pip install prompt_toolkit
# Use prompt_toolkit for advanced input
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory

# ANSI colors
RESET   = "\033[0m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"

# Valid AES defaults (16 bytes)
DEFAULT_KEY = base64.b64decode("nA8H4B8Y14cnwe9eF1o+XZiNNk3sP3Inir2GIJo8/Fk=")
DEFAULT_IV  = b"ZqdzK9f3u9WG2OlP"

# Keep history for nicer editing
history = InMemoryHistory()

def read_with_default(prompt_text, default_bytes):
    """
    Prompt user for input. Press Enter to use default.
    Accepts hex, base64, or plain UTF-8 text.
    """
    s = prompt(f"{prompt_text} (press Enter to use default): ", history=history).strip()
    if s == "":
        return default_bytes
    try:
        return binascii.unhexlify(s)
    except (binascii.Error, ValueError):
        pass
    decoded = b64_padded(s)
    if decoded is not None:
        return decoded
    try:
        return s.encode("latin-1")
    except UnicodeEncodeError:
        return s.encode("utf-8")

def decode_ciphertext(s):
    """
    Try to decode input as hex or base64 (padding-tolerant).
    """
    try:
        return binascii.unhexlify(s)
    except (binascii.Error, ValueError):
        pass
    decoded = b64_padded(s)
    if decoded is not None:
        return decoded
    raise ValueError("Input is not valid hex or base64.")

def normalize_key(key):
    valid = [16, 24, 32]
    klen = len(key)
    if klen in valid:
        return key
    # Truncate to the previous valid size, or pad to the next
    for size in valid:
        if klen < size:
            return key.ljust(size, b'\0')
    return key[:32]

def normalize_iv(iv):
    if len(iv) == 16:
        return iv
    if len(iv) < 16:
        return iv.ljust(16, b'\0')
    return iv[:16]

def b64_padded(s):
    """
    Tolerant base64 decode: re-adds missing '=' padding (some sources/clipboards
    drop trailing '='), then decodes. Returns bytes or None if invalid.
    """
    s = s.strip()
    if len(s) % 4 == 2:
        s += "=="
    elif len(s) % 4 == 3:
        s += "="
    try:
        return base64.b64decode(s)
    except Exception:
        return None

def split_gcm_blob(s):
    """
    Split a 'base64(nonce):base64(ciphertext):base64(tag)' string.
    Returns (nonce, ciphertext, tag) or None if it isn't valid.
    """
    parts = s.split(":")
    if len(parts) != 3:
        return None
    try:
        nonce = b64_padded(parts[0])
        ct = b64_padded(parts[1])
        tag = b64_padded(parts[2])
        if nonce is None or ct is None or tag is None:
            return None
        return nonce, ct, tag
    except Exception:
        return None

def gcm_decrypt(ed, key):
    """
    Decrypt AES-GCM data. Accepts the 3-part format directly, or wrapped
    one level in base64 (nonce:ct:tag base64-encoded as a whole blob).
    Returns the plaintext bytes, or None if the input isn't GCM format.
    """
    blob = split_gcm_blob(ed)
    if blob is None:
        try:
            wrapped = base64.b64decode(ed).decode()
        except Exception:
            return None
        blob = split_gcm_blob(wrapped)
    if blob is None:
        return None
    nonce, ct, tag = blob
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ct, tag)

def gcm_encrypt(pt, key):
    """
    Encrypt with AES-GCM. Returns 'base64(nonce):base64(ct):base64(tag)'.
    """
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(pt)
    return (base64.b64encode(nonce).decode() + ":"
            + base64.b64encode(ct).decode() + ":"
            + base64.b64encode(tag).decode())

def encrypt_flow():
    plaintext = read_pasted("Enter plaintext to encrypt").encode("utf-8")
    key = normalize_key(read_with_default("Enter key", DEFAULT_KEY))
    mode = prompt("[C]BC / [G]CM mode ? ", history=history).strip().lower() or "c"

    if mode == "g":
        blob = gcm_encrypt(plaintext, key)
        print(f"\n{YELLOW}Encrypted output (nonce:ct:tag, no IV needed):{RESET}")
        print(f"{MAGENTA}GCM blob  :{RESET} {blob}")
        return

    iv  = normalize_iv(read_with_default("Enter IV", DEFAULT_IV))

    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

    print(f"\n{YELLOW}Encrypted output:{RESET}")
    print(f"{MAGENTA}Hex     :{RESET} {binascii.hexlify(ciphertext).decode()}")
    print(f"{BLUE}Base64  :{RESET} {base64.b64encode(ciphertext).decode()}")

def sanitize_input(s):
    """
    Clean up pasted ciphertext:
      - remove all whitespace (terminal line-wrapping inserts newlines)
      - decode JSON-style \\uXXXX escapes (e.g. \\u003d -> '=')
    Base64 + colons never contain whitespace, so this is lossless.
    """
    s = "".join(s.split())
    try:
        import re
        s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)
    except Exception:
        pass
    return s

def read_pasted(label):
    """
    Read a possibly multi-line paste line by line. Line-wrapping is harmless:
    each wrapped fragment is collected, then joined. Press Enter on an empty
    line to finish.
    """
    print(f"{CYAN}{label}{RESET}")
    print(f"{CYAN}(paste it all, then press Enter on an empty line to finish){RESET}")
    lines = []
    while True:
        line = prompt("  ", history=history)
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines)

def decrypt_flow():
    raw = sanitize_input(read_pasted("Enter ciphertext (hex/base64, or GCM nonce:ct:tag)"))
    key = normalize_key(read_with_default("Enter key", DEFAULT_KEY))

    try:
        gcm_pt = gcm_decrypt(raw, key)
    except Exception:
        gcm_pt = None
    if gcm_pt is not None:
        print(f"\n{YELLOW}Decrypted output (AES-GCM):{RESET}")
        _print_plaintext(gcm_pt)
        return

    if split_gcm_blob(raw) is not None:
        print(f"{RED}[Error] GCM authentication failed:{RESET} wrong key or tampered data.")
        return

    iv  = normalize_iv(read_with_default("Enter IV", DEFAULT_IV))

    ciphertext = decode_ciphertext(raw)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext_padded = cipher.decrypt(ciphertext)
    plaintext = unpad(plaintext_padded, AES.block_size)

    print(f"\n{YELLOW}Decrypted output (AES-CBC):{RESET}")
    _print_plaintext(plaintext)

def _print_plaintext(plaintext):
    try:
        print(f"{GREEN}{plaintext.decode('utf-8')}{RESET}")
    except UnicodeDecodeError:
        print(f"{CYAN}Hex bytes:{RESET} {binascii.hexlify(plaintext).decode()}")

def main():
    print(f"{CYAN}AES-CBC / AES-GCM Encrypt / Decrypt Tool (Ctrl+C to quit){RESET}\n")

    while True:
        try:
            choice = prompt("[E]ncrypt / [D]ecrypt ? ", history=history).strip().lower()

            if choice == "e":
                encrypt_flow()
            elif choice == "d":
                decrypt_flow()
            else:
                print(f"{RED}Invalid option. Choose E or D.{RESET}")

            print("\n" + "-" * 50 + "\n")

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Exiting (Ctrl+C). Bye 👋{RESET}")
            sys.exit(0)
        except Exception as e:
            print(f"{RED}[Error]{RESET} {e}\n")

if __name__ == "__main__":
    main()
