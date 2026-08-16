# Unified Crypto Suite - Burp Suite Extension
# ================================================
# One extension that merges three tools:
#   1. mentor.py                     - AES-CBC encrypt/decrypt (key + IV, hex/base64)
#   2. decrypt_plugin.py             - "Crypto Suite (Java)" Burp tab
#   3. aes_cryptojs_burp_extensionNONCE.py - CryptoJS "Salted__" AES-256 + token/nonce derivation
#
# Features
#   - Standard AES-CBC mode (raw Key + IV), output as Hex / Base64 / Both
#   - CryptoJS mode (OpenSSL "Salted__" AES-256-CBC, passphrase-based)
#   - Key Source: manual key/passphrase OR SHA256(token + '.' + nonce)
#   - Auto-capture Bearer token + nonce headers from live traffic (read-only)
#   - Right-click any request/response -> send selection to the tool
#   - JSON pretty-printing on decrypt
#
# Runs on Jython 2.7 (javax.crypto only, no external dependencies).
# Burp -> Extensions -> Add -> Extension type: Python -> select this file.

from burp import IBurpExtender, ITab, IContextMenuFactory, IHttpListener
from javax.swing import (
    JPanel, JTextArea, JTextField, JLabel, JButton, JScrollPane, JSplitPane,
    JCheckBox, JComboBox, JMenuItem, Box, BoxLayout, BorderFactory, SwingUtilities
)
from javax.swing.border import EmptyBorder
from java.awt import BorderLayout, Color, Font, Dimension, GridBagLayout, GridBagConstraints, Insets
from java.awt.event import ActionListener
from java.lang import Throwable
from javax.crypto import Cipher
from javax.crypto.spec import SecretKeySpec, IvParameterSpec
from java.security import MessageDigest, SecureRandom
from java.util import ArrayList
import base64, binascii, json

try:
    from burp import IContextMenuInvocation
except Exception:
    IContextMenuInvocation = None

# --- Theme ---------------------------------------------------------------
C_BG     = Color(30,  30,  46)
C_PANEL  = Color(45,  45,  68)
C_INPUT  = Color(55,  55,  80)
C_TEXT   = Color(220, 220, 235)
C_GREEN  = Color(80,  200, 120)
C_RED    = Color(220,  80,  80)
C_YELLOW = Color(255, 200,  80)
C_CYAN   = Color(80,  200, 220)
C_BLUE   = Color(100, 150, 255)
C_BORDER = Color(70,  70,  100)
WHITE    = Color.WHITE

MODE_STD   = 0
MODE_CRYPTOJS = 1
SRC_MANUAL = 0
SRC_DERIVE = 1


# --- Low-level helpers (javax.crypto only) -------------------------------

def _java_bytes(b):
    return [x if x < 128 else x - 256 for x in bytearray(b)]


def _from_java_bytes(java_arr):
    return bytes(bytearray([x & 0xFF for x in java_arr]))


def _md5(data):
    md = MessageDigest.getInstance("MD5")
    return _from_java_bytes(md.digest(_java_bytes(data)))


def _sha256_hex(data):
    md = MessageDigest.getInstance("SHA-256")
    return binascii.hexlify(bytearray(_from_java_bytes(md.digest(_java_bytes(data))))).decode('ascii')


def _random_bytes(n):
    sr = SecureRandom()
    return bytes(bytearray([sr.nextInt(256) for _ in range(n)]))


def _decode_bin(s):
    """Decode a string as hex, else base64, else plain UTF-8 text."""
    s = _strip_wrappers(s)
    try:
        return binascii.unhexlify(s)
    except Exception:
        pass
    try:
        return base64.b64decode(''.join(s.split()))
    except Exception:
        pass
    return s.encode('utf-8')


def _decode_key_bytes(s, sizes=(16, 24, 32)):
    """Parse a key/IV: hex if obvious, base64 only if it decodes to one of
    the given byte lengths, otherwise plain UTF-8 text. Printable key/IV
    strings like 'yA32x7Qz9vBk4mR8' or 'BE/s3V0HtpPsE+1x' must stay plain
    text -- they would be mis-decoded as base64 otherwise."""
    s = _strip_wrappers(s)
    try:
        if len(s) % 2 == 0:
            return binascii.unhexlify(s)
    except Exception:
        pass
    if ('=' in s) or ('+' in s) or ('/' in s):
        try:
            decoded = base64.b64decode(s)
            if len(decoded) in sizes:
                return decoded
        except Exception:
            pass
    return s.encode('utf-8')


def _strip_wrappers(s):
    """Drop whitespace and common wrapping chars copied along with payloads."""
    s = s.strip()
    s = s.lstrip("\"'")
    s = s.rstrip("\"'{}")
    return s.strip()


def _normalize_key(key):
    for size in (16, 24, 32):
        if len(key) == size:
            return key
        if len(key) < size:
            return key.ljust(size, b'\0')
    return key[:32]


def _normalize_iv(iv):
    if len(iv) < 16:
        return iv.ljust(16, b'\0')
    return iv[:16]


def derive_session_crypto_key(token, nonce):
    return _sha256_hex(("%s.%s" % (token, nonce)).encode('utf-8'))


def _evp_bytes_to_key(password, salt, key_len=32, iv_len=16):
    """OpenSSL EVP_BytesToKey (MD5) - the KDF OpenSSL/CryptoJS use."""
    derived = b""
    prev = b""
    while len(derived) < key_len + iv_len:
        prev = _md5(prev + password + salt)
        derived += prev
    return derived[:key_len], derived[key_len:key_len + iv_len]


def _extract_token_and_nonce(headers, nonce_header_name="x-client-request-nonce"):
    """Scan raw HTTP header lines for a Bearer token and a nonce header."""
    token = None
    nonce = None
    nonce_header_name = nonce_header_name.lower()
    for h in headers:
        if ":" not in h:
            continue
        name, _, value = h.partition(":")
        name = name.strip().lower()
        value = value.strip()
        if name == "authorization":
            if value.lower().startswith("bearer "):
                token = value[7:].strip()
            elif value:
                token = value.strip()
        elif name == nonce_header_name:
            nonce = value
    return token, nonce


def _pretty_print(text):
    try:
        return json.dumps(json.loads(text), indent=2)
    except Exception:
        return text


def _find_json(text):
    """Extract the first balanced JSON object/array from a blob of text,
    skipping any leading/nested gibberish (e.g. a hex-encoded encrypted
    field). Returns the JSON substring, or '' if none is found."""
    start = -1
    i = 0
    n = len(text)
    while i < n:
        if text[i] in '{[':
            start = i
            break
        i += 1
    if start == -1:
        return ''
    depth = 0
    in_str = False
    esc = False
    i = start
    while i < n:
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in '{[':
                depth += 1
            elif ch in '}]':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return ''


def _extract_json(text):
    """Return the extracted JSON pretty-printed; fall back to the raw
    substring if it does not parse."""
    sub = _find_json(text)
    if not sub:
        raise ValueError("No JSON object/array found in the output.")
    return _pretty_print(sub)


# --- AES primitives ------------------------------------------------------

def _cipher_op(key_bytes, iv_bytes, mode):
    cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
    key_spec = SecretKeySpec(_java_bytes(key_bytes), "AES")
    iv_spec = IvParameterSpec(_java_bytes(iv_bytes))
    cipher.init(mode, key_spec, iv_spec)
    return cipher


def aes_cbc_encrypt(plain_bytes, key_bytes, iv_bytes):
    cipher = _cipher_op(key_bytes, iv_bytes, Cipher.ENCRYPT_MODE)
    try:
        return _from_java_bytes(cipher.doFinal(_java_bytes(plain_bytes)))
    except Throwable as t:
        raise ValueError("Encryption failed: %s" % str(t))


def aes_cbc_decrypt(ct_bytes, key_bytes, iv_bytes):
    cipher = _cipher_op(key_bytes, iv_bytes, Cipher.DECRYPT_MODE)
    try:
        return _from_java_bytes(cipher.doFinal(_java_bytes(ct_bytes)))
    except Throwable as t:
        raise ValueError("Decryption failed: %s" % str(t))


FIXED_SALT = b"\x00\x01\x02\x03\x04\x05\x06\x07"


def _decode_salt_input(s):
    """Parse a known salt for reproducible CryptoJS output: 16 hex digits
    (8 bytes) or exactly 8 plain-text characters. Empty = built-in fixed salt."""
    s = _strip_wrappers(s.strip())
    if not s:
        return FIXED_SALT
    if s.lower().startswith("0x"):
        s = s[2:]
    if len(s) == 16:
        try:
            return binascii.unhexlify(s)
        except Exception:
            pass
    b = s.encode('utf-8')
    if len(b) != 8:
        raise ValueError(
            "Known salt must be exactly 8 bytes: 16 hex digits or 8 characters."
        )
    return b


def cryptojs_encrypt(plain_bytes, passphrase, salt=None):
    if salt is None:
        salt = _random_bytes(8)
    elif len(salt) != 8:
        raise ValueError("Salt must be exactly 8 bytes.")
    key, iv = _evp_bytes_to_key(passphrase.encode('utf-8'), salt)
    ct = aes_cbc_encrypt(plain_bytes, key, iv)
    return base64.b64encode(b"Salted__" + salt + ct).decode('utf-8')


def cryptojs_decrypt(payload_b64, passphrase):
    try:
        raw = base64.b64decode(''.join(_strip_wrappers(payload_b64).split()))
    except Exception:
        raise ValueError("Ciphertext is not valid base64.")
    if len(raw) < 16 or raw[:8] != b"Salted__":
        raise ValueError("Not a CryptoJS payload (missing 'Salted__' header).")
    salt, ct = raw[8:16], raw[16:]
    key, iv = _evp_bytes_to_key(passphrase.encode('utf-8'), salt)
    try:
        return aes_cbc_decrypt(ct, key, iv)
    except Exception:
        raise ValueError(
            "Decryption produced empty output -- the key/token/nonce "
            "pairing likely does not match this ciphertext."
        )


# --- Swing builders ------------------------------------------------------

class _Action(ActionListener):
    def __init__(self, fn):
        self._fn = fn

    def actionPerformed(self, event):
        self._fn()


def _label(text, color=None):
    lbl = JLabel(text)
    lbl.setForeground(color if color else C_YELLOW)
    lbl.setFont(Font("SansSerif", Font.BOLD, 12))
    return lbl


def _spacer(n):
    return Box.createVerticalStrut(n)


def _mk_field(text=""):
    f = JTextField(text)
    f.setFont(Font("Monospaced", Font.PLAIN, 12))
    f.setBackground(C_INPUT)
    f.setForeground(C_TEXT)
    f.setCaretColor(C_TEXT)
    f.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(C_BORDER, 1),
        EmptyBorder(4, 6, 4, 6)
    ))
    return f


def _mk_area(text="", editable=True, color=None):
    ta = JTextArea(text)
    ta.setFont(Font("Monospaced", Font.PLAIN, 12))
    ta.setBackground(C_INPUT)
    ta.setForeground(color if color else C_TEXT)
    ta.setCaretColor(C_TEXT)
    ta.setEditable(editable)
    ta.setLineWrap(True)
    ta.setWrapStyleWord(True)
    ta.setBorder(EmptyBorder(6, 8, 6, 8))
    return ta


def _scrolled(component, w, h):
    scroll = JScrollPane(component)
    scroll.setBorder(BorderFactory.createLineBorder(C_BORDER, 1))
    scroll.setPreferredSize(Dimension(w, h))
    scroll.setMinimumSize(Dimension(180, 60))
    return scroll


def _mk_button(text, bg, on_click=None):
    btn = JButton(text)
    btn.setBackground(bg)
    btn.setForeground(WHITE)
    btn.setFont(Font("SansSerif", Font.BOLD, 13))
    btn.setFocusPainted(False)
    btn.setOpaque(True)
    btn.setMinimumSize(btn.getPreferredSize())
    if on_click:
        btn.addActionListener(_Action(on_click))
    return btn


def _mk_check(text, on_change=None):
    cb = JCheckBox(text)
    cb.setBackground(C_PANEL)
    cb.setForeground(C_TEXT)
    cb.setFont(Font("SansSerif", Font.PLAIN, 12))
    if on_change:
        cb.addActionListener(_Action(on_change))
    return cb


def _mk_combo(items, on_change=None):
    combo = JComboBox()
    for item in items:
        combo.addItem(item)
    combo.setBackground(C_INPUT)
    combo.setForeground(C_TEXT)
    combo.setFont(Font("SansSerif", Font.PLAIN, 12))
    if on_change:
        combo.addActionListener(_Action(on_change))
    return combo


# --- Main extension ------------------------------------------------------

class BurpExtender(IBurpExtender, ITab, IContextMenuFactory, IHttpListener):

    def registerExtenderCallbacks(self, callbacks):
        self._cb = callbacks
        self._hlp = callbacks.getHelpers()
        callbacks.setExtensionName("Unified Crypto Suite")
        callbacks.registerContextMenuFactory(self)
        self._build_ui()
        callbacks.addSuiteTab(self)
        callbacks.registerHttpListener(self)
        callbacks.printOutput("[*] Unified Crypto Suite loaded.")

    # ---- Tab -----------------------------------------------------------------
    def getTabCaption(self):
        return "Crypto Suite"

    def getUiComponent(self):
        return self._main_panel

    # ---- Build UI ------------------------------------------------------------

    def _build_ui(self):
        self._main_panel = JPanel(BorderLayout())
        self._main_panel.setBackground(C_BG)
        self._main_panel.add(self._build_header(), BorderLayout.NORTH)

        left = self._build_keys_panel()
        left_scroll = JScrollPane(left)
        left_scroll.setBorder(BorderFactory.createMatteBorder(0, 0, 0, 1, C_BORDER))
        left_scroll.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_NEVER)
        right = self._build_crypto_panel()

        split = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, left_scroll, right)
        split.setDividerLocation(330)
        split.setResizeWeight(0.0)
        split.setContinuousLayout(True)
        split.setDividerSize(6)
        split.setBackground(C_BG)
        self._main_panel.add(split, BorderLayout.CENTER)

        self._status_area = JTextArea(1, 80)
        self._status_area.setFont(Font("Monospaced", Font.PLAIN, 11))
        self._status_area.setBackground(Color(20, 20, 35))
        self._status_area.setForeground(C_GREEN)
        self._status_area.setEditable(False)
        self._status_area.setLineWrap(True)
        self._status_area.setWrapStyleWord(True)
        self._status_area.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createMatteBorder(1, 0, 0, 0, C_BORDER),
            EmptyBorder(5, 12, 5, 12)
        ))
        self._status_area.setText("[*] Ready.")
        self._main_panel.add(self._status_area, BorderLayout.SOUTH)

        self._sync_visibility()

    def _build_header(self):
        header = JPanel(BorderLayout())
        header.setBackground(Color(20, 20, 35))
        header.setBorder(EmptyBorder(8, 16, 8, 16))
        title = JLabel("  Crypto Suite")
        title.setForeground(C_CYAN)
        title.setFont(Font("SansSerif", Font.BOLD, 16))
        sub = JLabel("AES-CBC / CryptoJS Salted__ / Token+Nonce derive")
        sub.setForeground(Color(120, 120, 160))
        sub.setFont(Font("SansSerif", Font.PLAIN, 11))
        header.add(title, BorderLayout.WEST)
        header.add(sub, BorderLayout.EAST)
        return header

    # ---- Left: Keys & Options ------------------------------------------------

    def _build_keys_panel(self):
        panel = JPanel()
        panel.setLayout(BoxLayout(panel, BoxLayout.Y_AXIS))
        panel.setBackground(C_PANEL)
        panel.setBorder(EmptyBorder(16, 16, 16, 16))

        panel.add(_label("CIPHER MODE", C_CYAN))
        panel.add(_spacer(10))
        self._cipher_combo = _mk_combo(
            ["Standard AES-CBC (Key + IV)", "CryptoJS AES (Passphrase / Salted__)"],
            self._sync_visibility
        )
        panel.add(self._cipher_combo)
        panel.add(_spacer(16))

        panel.add(_label("KEY SOURCE", C_CYAN))
        panel.add(_spacer(10))
        self._source_combo = _mk_combo(
            ["Manual key / passphrase", "Derive SHA256 from Token + Nonce"],
            self._sync_visibility
        )
        panel.add(self._source_combo)
        panel.add(_spacer(12))

        self._auto_capture_check = _mk_check(
            "Auto-capture Token + Nonce from traffic",
            self._sync_visibility
        )
        panel.add(self._auto_capture_check)
        panel.add(_spacer(6))

        self._nonce_header_label = _label("Nonce header name:")
        panel.add(self._nonce_header_label)
        panel.add(_spacer(4))
        self._nonce_header_field = _mk_field("X-Client-Request-Nonce")
        panel.add(self._nonce_header_field)
        panel.add(_spacer(14))

        self._key_label = _label("Key / Passphrase:")
        panel.add(self._key_label)
        panel.add(_spacer(4))
        self._key_field = _mk_field("")
        panel.add(self._key_field)
        panel.add(_spacer(14))

        self._iv_label = _label("IV (16 bytes):")
        panel.add(self._iv_label)
        panel.add(_spacer(4))
        self._iv_field = _mk_field("")
        panel.add(self._iv_field)
        panel.add(_spacer(14))

        self._token_label = _label("Bearer Token:")
        panel.add(self._token_label)
        panel.add(_spacer(4))
        self._token_field = _mk_field("")
        panel.add(self._token_field)
        panel.add(_spacer(10))

        self._nonce_label = _label("Nonce:")
        panel.add(self._nonce_label)
        panel.add(_spacer(4))
        self._nonce_field = _mk_field("")
        panel.add(self._nonce_field)
        panel.add(_spacer(8))

        self._derive_btn = _mk_button("Derive Key", Color(80, 80, 160), self._do_derive_key)
        panel.add(self._derive_btn)
        panel.add(_spacer(8))

        self._derived_label = _label("Derived key (SHA256 hex):", C_GREEN)
        panel.add(self._derived_label)
        panel.add(_spacer(4))
        self._derived_area = _mk_area("", False, C_GREEN)
        self._derived_scroll = _scrolled(self._derived_area, 300, 50)
        panel.add(self._derived_scroll)
        panel.add(_spacer(14))

        info = JTextArea(
            "Standard: AES-CBC, key 16/24/32 bytes; key/IV accept\n"
            "hex, base64 or plain text. CryptoJS: OpenSSL 'Salted__'\n"
            "AES-256; key field is used as the passphrase. Tick\n"
            "'Known salt' below if the app uses a fixed salt (same\n"
            "text+passphrase then always gives the same output).\n"
            "Derive: key = SHA256(token + '.' + nonce).\n"
            "Auto-capture pulls Bearer token + nonce from traffic\n"
            "(read-only). Right-click a request/response ->\n"
            "  Send selection to Crypto Suite."
        )
        info.setEditable(False)
        info.setOpaque(False)
        info.setBackground(C_PANEL)
        info.setForeground(Color(150, 150, 190))
        info.setFont(Font("Monospaced", Font.PLAIN, 11))
        info.setLineWrap(True)
        info.setWrapStyleWord(True)
        info_scroll = JScrollPane(info)
        info_scroll.setBorder(None)
        info_scroll.setPreferredSize(Dimension(280, 120))
        info_scroll.setMaximumSize(Dimension(32767, 120))
        info_scroll.setOpaque(False)
        info_scroll.getViewport().setOpaque(False)
        info_scroll.setHorizontalScrollBarPolicy(JScrollPane.HORIZONTAL_SCROLLBAR_NEVER)
        info_scroll.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED)
        panel.add(info_scroll)
        panel.setPreferredSize(Dimension(330, 520))
        return panel

    # ---- Right: Encrypt / Decrypt ---------------------------------------------

    def _build_crypto_panel(self):
        panel = JPanel(GridBagLayout())
        panel.setBackground(C_BG)
        panel.setBorder(EmptyBorder(14, 14, 14, 14))
        panel.setMinimumSize(Dimension(240, 0))

        def row_index(component, y, weighty=0.0, fill=GridBagConstraints.HORIZONTAL):
            g = GridBagConstraints()
            g.gridx = 0
            g.gridy = y
            g.gridwidth = 1
            g.weightx = 1.0
            g.weighty = weighty
            g.fill = fill
            g.insets = Insets(2, 2, 2, 2)
            panel.add(component, g)

        hdr = JPanel(BorderLayout())
        hdr.setOpaque(False)
        hdr.add(_label("INPUT", C_BLUE), BorderLayout.WEST)
        hdr.add(self._text_hint(), BorderLayout.EAST)
        row_index(hdr, 0)

        self._input_area = _mk_area()
        row_index(_scrolled(self._input_area, 500, 170), 1, weighty=1.0, fill=GridBagConstraints.BOTH)

        btn_row = JPanel()
        btn_row.setLayout(BoxLayout(btn_row, BoxLayout.X_AXIS))
        btn_row.setBackground(C_BG)
        self._encrypt_btn = _mk_button("  Encrypt  ", Color(50, 150, 80), self._do_encrypt)
        self._decrypt_btn = _mk_button("  Decrypt  ", Color(50, 100, 200), self._do_decrypt)
        clear_btn = _mk_button("  Clear  ", Color(100, 60, 60), self._do_clear)
        copy_btn = _mk_button("  Copy  ", Color(90, 90, 120), self._do_copy)
        json_btn = _mk_button("  Extract JSON  ", Color(120, 90, 60), self._do_extract_json)
        json_btn.setToolTipText("Pulls the JSON out of the decrypted output, "
                                "skipping any leading/nested gibberish "
                                "(e.g. an embedded hex-encrypted field), and "
                                "pretty-prints it so it is easy to read and copy.")
        btn_row.add(self._encrypt_btn)
        btn_row.add(Box.createHorizontalStrut(8))
        btn_row.add(self._decrypt_btn)
        btn_row.add(Box.createHorizontalStrut(8))
        btn_row.add(clear_btn)
        btn_row.add(Box.createHorizontalStrut(8))
        btn_row.add(copy_btn)
        btn_row.add(Box.createHorizontalStrut(8))
        btn_row.add(json_btn)
        btn_row.add(Box.createHorizontalGlue())
        row_index(btn_row, 2)

        fmt_row = JPanel()
        fmt_row.setLayout(BoxLayout(fmt_row, BoxLayout.X_AXIS))
        fmt_row.setBackground(C_BG)
        fmt_row.add(_label("Cipher output format:"))
        fmt_row.add(Box.createHorizontalStrut(8))
        self._format_combo = _mk_combo(["Hex", "Base64", "Hex + Base64"])
        self._format_combo.setSelectedIndex(2)
        fmt_row.add(self._format_combo)
        fmt_row.add(Box.createHorizontalGlue())
        row_index(fmt_row, 3)

        salt_row = JPanel()
        salt_row.setLayout(BoxLayout(salt_row, BoxLayout.X_AXIS))
        salt_row.setBackground(C_BG)
        self._salt_check = _mk_check("Known salt (reproducible CryptoJS):")
        self._salt_check.setBackground(C_BG)
        salt_hint = ("Tick this ONLY for apps that use a fixed / known salt "
                     "(the OpenSSL 'Salted__' header embeds the salt).\n"
                     "OFF (default): every Encrypt click makes a NEW random salt, "
                     "so the same text gives DIFFERENT ciphertext each time.\n"
                     "ON: the same text + same passphrase always gives the SAME "
                     "ciphertext -- useful to reproduce an app's output.\n"
                     "Salt value: leave empty for the built-in fixed salt, or type "
                     "the app's salt as 8 characters or 16 hex digits.")
        self._salt_check.setToolTipText(salt_hint)
        self._salt_field = _mk_field("")
        self._salt_field.setToolTipText(salt_hint)
        salt_row.add(self._salt_check)
        salt_row.add(Box.createHorizontalStrut(4))
        salt_row.add(self._salt_field)
        salt_row.add(Box.createHorizontalGlue())
        row_index(salt_row, 4)

        out_hdr = JPanel(BorderLayout())
        out_hdr.setOpaque(False)
        out_hdr.add(_label("OUTPUT", C_GREEN), BorderLayout.WEST)
        self._pretty_check = _mk_check("Pretty-print JSON on decrypt")
        self._pretty_check.setBackground(C_BG)
        out_hdr.add(self._pretty_check, BorderLayout.EAST)
        row_index(out_hdr, 5)

        self._output_area = _mk_area("", False, C_GREEN)
        row_index(_scrolled(self._output_area, 500, 210), 6, weighty=1.0, fill=GridBagConstraints.BOTH)
        return panel

    def _text_hint(self):
        hint = JLabel("Plaintext to encrypt, or ciphertext to decrypt (hex / base64)")
        hint.setForeground(Color(120, 120, 160))
        hint.setFont(Font("SansSerif", Font.PLAIN, 11))
        hint.setMinimumSize(Dimension(0, 0))
        return hint

    # ---- Field visibility ------------------------------------------------------

    def _sync_visibility(self):
        cipher_std = self._cipher_combo.getSelectedIndex() == MODE_STD
        manual = self._source_combo.getSelectedIndex() == SRC_MANUAL
        capture = self._auto_capture_check.isSelected()

        self._nonce_header_label.setVisible(capture)
        self._nonce_header_field.setVisible(capture)

        self._key_label.setVisible(manual)
        self._key_field.setVisible(manual)

        self._iv_label.setVisible(cipher_std and manual)
        self._iv_field.setVisible(cipher_std and manual)

        show_salt = not cipher_std
        self._salt_check.setVisible(show_salt)
        self._salt_field.setVisible(show_salt)

        show_derive = not manual
        for w in (self._token_label, self._token_field, self._nonce_label,
                  self._nonce_field, self._derive_btn, self._derived_label,
                  self._derived_scroll):
            w.setVisible(show_derive)

    # ---- Key resolution ----------------------------------------------------------

    def _resolve_key_iv(self):
        """Returns (is_standard, key, iv_or_None)."""
        cipher_std = self._cipher_combo.getSelectedIndex() == MODE_STD
        manual = self._source_combo.getSelectedIndex() == SRC_MANUAL

        if manual:
            material = self._key_field.getText().strip()
            if not material:
                raise ValueError("Provide a key/passphrase (or switch to 'Derive' mode).")
        else:
            token = self._token_field.getText().strip()
            nonce = self._nonce_field.getText().strip()
            if not token or not nonce:
                raise ValueError("Derive mode requires both a Bearer Token and a Nonce.")
            material = derive_session_crypto_key(token, nonce)

        if cipher_std:
            key = _normalize_key(_decode_key_bytes(material))
            iv = _normalize_iv(_decode_key_bytes(self._iv_field.getText(), sizes=(16,)))
            return (True, key, iv)
        return (False, material, None)

    # ---- Actions ----------------------------------------------------------------

    def _do_encrypt(self):
        try:
            text = self._input_area.getText()
            if not text:
                self._set_status("[!] Input is empty.", C_RED)
                return
            is_std, key, iv = self._resolve_key_iv()
            if is_std:
                ct = aes_cbc_encrypt(text.encode('utf-8'), key, iv)
                fmt = self._format_combo.getSelectedIndex()
                parts = []
                if fmt in (0, 2):
                    parts.append("HEX: " + binascii.hexlify(ct).decode())
                if fmt in (1, 2):
                    parts.append("BASE64: " + base64.b64encode(ct).decode())
                out = "\n\n".join(parts)
            else:
                salt = None
                if self._salt_check.isSelected():
                    salt = _decode_salt_input(self._salt_field.getText())
                out = cryptojs_encrypt(text.encode('utf-8'), key, salt)
            self._output_area.setText(out)
            self._set_status("[+] Encryption successful.", C_GREEN)
        except Exception as ex:
            self._output_area.setText("")
            self._show_error(ex)

    def _do_decrypt(self):
        try:
            raw = self._input_area.getText().strip()
            if not raw:
                self._set_status("[!] Input is empty.", C_RED)
                return
            is_std, key, iv = self._resolve_key_iv()
            if is_std:
                plain = aes_cbc_decrypt(_decode_bin(raw), key, iv)
            else:
                plain = cryptojs_decrypt(raw, key)
            text = plain.decode('utf-8', 'replace')
            if self._pretty_check.isSelected():
                text = _pretty_print(text)
            self._output_area.setText(text)
            self._set_status("[+] Decryption successful.", C_GREEN)
        except Exception as ex:
            self._output_area.setText("")
            self._show_error(ex)

    def _do_derive_key(self):
        try:
            token = self._token_field.getText().strip()
            nonce = self._nonce_field.getText().strip()
            if not token or not nonce:
                self._set_status("[!] Derive requires both a Bearer Token and a Nonce.", C_RED)
                return
            self._derived_area.setText(derive_session_crypto_key(token, nonce))
            self._set_status("[+] Derived: SHA256(token + '.' + nonce).", C_GREEN)
        except Exception as ex:
            self._show_error(ex)

    def _do_clear(self):
        self._input_area.setText("")
        self._output_area.setText("")
        self._set_status("[*] Cleared.", C_CYAN)

    def _do_copy(self):
        text = self._output_area.getText()
        if text:
            from java.awt import Toolkit
            from java.awt.datatransfer import StringSelection
            copy = StringSelection(text)
            Toolkit.getDefaultToolkit().getSystemClipboard().setContents(copy, None)
            self._set_status("[+] Output copied.", C_CYAN)

    def _do_extract_json(self):
        try:
            text = self._output_area.getText()
            if not text:
                self._set_status("[!] Output is empty.", C_RED)
                return
            self._output_area.setText(_extract_json(text))
            self._set_status("[+] JSON extracted and pretty-printed.", C_GREEN)
        except Exception as ex:
            self._show_error(ex)

    def _set_status(self, msg, color=None):
        self._status_area.setForeground(color if color else C_GREEN)
        self._status_area.setText(msg)

    def _show_error(self, ex):
        msg = str(ex)
        self._set_status("[ERROR] " + msg, C_RED)
        self._cb.printError("[Unified Crypto Suite] " + msg)

    # ---- Auto-capture (read-only) -------------------------------------------------

    def processHttpMessage(self, toolFlag, messageIsRequest, messageInfo):
        if not messageIsRequest:
            return
        try:
            if not self._auto_capture_check.isSelected():
                return
            analyzed = self._hlp.analyzeRequest(messageInfo)
            headers = list(analyzed.getHeaders())
            nonce_header = self._nonce_header_field.getText().strip() or "x-client-request-nonce"
            token, nonce = _extract_token_and_nonce(headers, nonce_header)
            if not token and not nonce:
                return
            try:
                host = messageInfo.getHttpService().getHost()
            except Exception:
                host = "?"
            SwingUtilities.invokeLater(lambda: self._apply_captured(token, nonce, host))
        except Exception as ex:
            self._cb.printError("[Unified Crypto Suite] capture error: %s" % str(ex))

    def _apply_captured(self, token, nonce, host):
        changed = []
        if token:
            self._token_field.setText(token)
            changed.append("token")
        if nonce:
            self._nonce_field.setText(nonce)
            changed.append("nonce")
        if changed:
            self._source_combo.setSelectedIndex(SRC_DERIVE)
            self._set_status(
                "[+] Auto-captured %s from %s" % (" + ".join(changed), host),
                C_CYAN
            )

    # ---- Context menu ------------------------------------------------------------

    VALID_CONTEXTS = [
        "CONTEXT_MESSAGE_EDITOR_REQUEST",
        "CONTEXT_MESSAGE_EDITOR_RESPONSE",
        "CONTEXT_PROXY_HISTORY",
        "CONTEXT_TARGET_SITE_MAP_TABLE",
        "CONTEXT_REPEATER_REQUEST",
        "CONTEXT_REPEATER_RESPONSE",
        "CONTEXT_PROXY_MESSAGE_EDITOR_REQUEST",
        "CONTEXT_PROXY_MESSAGE_EDITOR_RESPONSE",
    ]
    REQUEST_CONTEXTS = [
        "CONTEXT_MESSAGE_EDITOR_REQUEST",
        "CONTEXT_REPEATER_REQUEST",
        "CONTEXT_PROXY_MESSAGE_EDITOR_REQUEST",
    ]

    @staticmethod
    def _ctx_values(names):
        vals = []
        if IContextMenuInvocation is not None:
            for name in names:
                try:
                    v = getattr(IContextMenuInvocation, name, None)
                    if v is not None:
                        vals.append(v)
                except Exception:
                    pass
        return vals

    def _is_valid_context(self, invocation):
        ctx = invocation.getInvocationContext()
        return ctx in self._ctx_values(self.VALID_CONTEXTS)

    def createMenuItems(self, invocation):
        items = ArrayList()
        try:
            if not self._is_valid_context(invocation):
                return items
        except Exception:
            return items
        item = JMenuItem("Send selection to Crypto Suite")

        class SendAction(ActionListener):
            def __init__(self, ext, inv):
                self._ext = ext
                self._inv = inv

            def actionPerformed(self, e):
                try:
                    self._ext._send_selection(self._inv)
                except Exception as ex:
                    self._ext._show_error(ex)

        item.addActionListener(SendAction(self, invocation))
        items.add(item)
        return items

    def _send_selection(self, invocation):
        msgs = invocation.getSelectedMessages()
        if not msgs:
            return
        msg = msgs[0]
        bounds = invocation.getSelectionBounds()
        ctx = invocation.getInvocationContext()
        is_req = ctx in self._ctx_values(self.REQUEST_CONTEXTS)

        req = msg.getRequest()
        resp = msg.getResponse()
        if is_req and req is not None:
            full, use_request = req, True
        elif resp is not None:
            full, use_request = resp, False
        elif req is not None:
            full, use_request = req, True
        else:
            return

        text = None
        if bounds and len(bounds) == 2:
            sel = full[bounds[0]:bounds[1]]
            if sel:
                text = self._hlp.bytesToString(sel)
        if not text:
            analyzed = (self._hlp.analyzeRequest(full) if use_request
                        else self._hlp.analyzeResponse(full))
            text = self._hlp.bytesToString(full[analyzed.getBodyOffset():])
        if not text:
            return
        self._input_area.setText(text.strip())
        self._set_status("[+] Selection sent. Set key/token then click Decrypt.", C_CYAN)