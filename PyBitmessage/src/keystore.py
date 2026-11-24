"""Private keys at rest: encrypt ``keys.dat`` (milestone M4.5.2).

Threat model
------------
``keys.dat`` holds every private key of this install. Today it is plain text
inside the app-private directory, so anything that can read that directory --
a root shell, a flawed backup, an OEM "phone clone" tool, a malicious app on a
rooted device -- gets the identity. This module encrypts the file so a *copy*
of it is useless without the device.

Design (envelope encryption)
----------------------------
* A 32-byte **master secret** is generated once.
* On Android the master is wrapped by an AES-GCM key that lives in
  **AndroidKeyStore** (alias ``pybitmessage-vault``). That key never leaves the
  TEE/StrongBox, so even root cannot export it; they can only ask the device to
  unwrap, which requires running inside this app's UID.
* Off-device (desktop, CI, unit tests) there is no secure element, so the
  master is kept in ``keys.vault`` with mode 0600. That is **not** a security
  boundary and the code says so out loud -- it exists so the format and the
  tests are identical everywhere.
* The file itself is AES-256-CBC + HMAC-SHA512, encrypt-then-MAC, with the
  encryption and MAC keys derived from the master by HMAC (key separation).

File format (self-describing so a plain-text file still loads)::

    b'#BMENC1\\n' || iv (16 B) || mac (32 B) || ciphertext (PKCS#7 padded)

Anything that does not start with the magic is treated as legacy plain text and
is encrypted on the next save (that is the migration path).
"""

import base64
import hashlib
import hmac
import os

MAGIC = b'#BMENC1\n'
VAULT_NAME = 'keys.vault'
ALIAS = 'pybitmessage-vault'

#: Labels for the HMAC-based key derivation. Distinct strings => distinct keys.
_KDF_ENC = b'pybitmessage/keys.dat/enc/v1'
_KDF_MAC = b'pybitmessage/keys.dat/mac/v1'

_master = None
_backend = None


def looks_encrypted(data):
    """True when *data* is a blob produced by :func:`encrypt_blob`."""
    return data[:len(MAGIC)] == MAGIC


def _log(message):
    print('KEYSTORE %s' % message, flush=True)


# ---------------------------------------------------------------------------
# master secret storage
# ---------------------------------------------------------------------------

def _vault_path():
    import state  # noqa: PLC0415 - imported lazily: state needs a home first

    return os.path.join(state.appdata, VAULT_NAME)


def _android_context():
    if os.environ.get('ANDROID_ARGUMENT') is None:
        return None
    try:
        from jnius import autoclass, cast

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        activity = PythonActivity.mActivity
        return cast(Context, activity) if activity is not None else None
    except Exception:  # noqa: BLE001
        return None


def _varargs(*values):
    """Return a single value for a Java ``String...`` parameter.

    pyjnius does **not** spread Python values into a varargs parameter: it
    treats whatever you pass as *one element* and wraps it. That produced
    ``ArrayStoreException: java.lang.String[] cannot be stored in an array of
    type java.lang.String[]`` on the device when a one-element array was
    handed to ``setBlockModes(String...)``. Passing the bare value lets Java
    build the one-element array itself.

    Failure modes seen on this parameter, in order (EVIDENCE §1.55):
    ``autoclass('[Ljava.lang.String;')(n)`` -> "No constructor available";
    ``autoclass('java.lang.String[]')`` -> hard JNI abort (illegal class
    name, not catchable); Python list -> ``Object[]`` -> ArrayStoreException;
    Java ``String[]`` object -> ArrayStoreException (wrapped again).
    """
    return values[0]


def _keystore_key(create):
    """Return the AndroidKeyStore AES key, creating it when *create* is set."""
    from jnius import autoclass

    KeyStore = autoclass('java.security.KeyStore')
    store = KeyStore.getInstance('AndroidKeyStore')
    store.load(None)
    if store.containsAlias(ALIAS):
        return store.getKey(ALIAS, None)
    if not create:
        return None

    KeyGenerator = autoclass('javax.crypto.KeyGenerator')
    KeyProperties = autoclass('android.security.keystore.KeyProperties')
    Builder = autoclass(
        'android.security.keystore.KeyGenParameterSpec$Builder')
    generator = KeyGenerator.getInstance('AES', 'AndroidKeyStore')
    builder = Builder(
        ALIAS,
        KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
    # varargs: pass the bare value, never a list/array (see _varargs)
    builder.setBlockModes('GCM')
    builder.setEncryptionPaddings('NoPadding')
    builder.setKeySize(256)
    generator.init(builder.build())
    return generator.generateKey()


def _android_wrap(master):
    """Encrypt *master* with the hardware-backed key; return iv||ciphertext."""
    from jnius import autoclass, cast

    Cipher = autoclass('javax.crypto.Cipher')
    Key = autoclass('java.security.Key')
    # Without the cast jnius picks Cipher.init(int, Certificate) and raises
    # "Invalid instance of 'javax/crypto/SecretKey' passed for a
    # 'java/security/cert/Certificate'" (EVIDENCE §1.55).
    key = cast(Key, _keystore_key(True))
    cipher = Cipher.getInstance('AES/GCM/NoPadding')
    cipher.init(Cipher.ENCRYPT_MODE, key)
    iv = cipher.getIV()
    wrapped = cipher.doFinal(master)
    return bytes(bytearray(iv)) + bytes(bytearray(wrapped))


def _android_unwrap(blob):
    """Reverse :func:`_android_wrap`."""
    from jnius import autoclass

    from jnius import cast

    Cipher = autoclass('javax.crypto.Cipher')
    Key = autoclass('java.security.Key')
    GCMParameterSpec = autoclass('javax.crypto.spec.GCMParameterSpec')
    key = _keystore_key(False)
    if key is None:
        raise RuntimeError('no vault key in AndroidKeyStore')
    key = cast(Key, key)
    iv = bytearray(blob[:12])
    body = bytearray(blob[12:])
    cipher = Cipher.getInstance('AES/GCM/NoPadding')
    cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv))
    return bytes(bytearray(cipher.doFinal(body)))


def _file_wrap(master):
    """Wrap *master* with a plain 0600 file (no secure element available)."""
    wrapped = base64.b64encode(master)
    path = _vault_path()
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    # Write then chmod: creating with 0600 via os.open is racy on some FS.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(wrapped)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return wrapped


def _file_unwrap(blob):
    return base64.b64decode(blob)


def _load_master():
    """Return the 32-byte master secret, creating the vault on first use."""
    global _master, _backend
    if _master is not None:
        return _master

    path = _vault_path()
    on_android = _android_context() is not None
    if on_android:
        try:
            if os.path.exists(path):
                with open(path, 'rb') as handle:
                    _master = _android_unwrap(handle.read())
                _backend = 'AndroidKeyStore'
            else:
                _master = os.urandom(32)
                wrapped = _android_wrap(_master)
                with open(path, 'wb') as handle:
                    handle.write(wrapped)
                _backend = 'AndroidKeyStore'
            _log('vault via %s' % _backend)
            return _master
        except Exception as exc:  # noqa: BLE001 - never block startup
            _log('AndroidKeyStore unavailable (%r); falling back to a file.'
                 ' keys.dat encryption will NOT resist a directory copy.' % (
                     exc,))

    if os.path.exists(path):
        with open(path, 'rb') as handle:
            raw = handle.read()
        _master = _file_unwrap(raw) if raw[:1] != b'#' else _android_unwrap(raw)
    else:
        _master = os.urandom(32)
        _file_wrap(_master)
    if len(_master) != 32:
        raise ValueError('vault holds %d bytes, expected 32' % len(_master))
    _backend = 'file'
    _log('vault via flat file (no secure element on this platform)')
    return _master


def enabled():
    """Should ``save()`` write an encrypted ``keys.dat``?

    On by default on Android (that is the product requirement: C4). Left off
    on the desktop unless ``BITMESSAGE_KEYSTORE=1``, so a developer's existing
    plain-text ``keys.dat`` keeps working -- the encryption exists to protect a
    *device*, and a flat vault file on a laptop buys nothing.
    """
    if os.environ.get('ANDROID_ARGUMENT') is not None:
        return True
    return os.environ.get('BITMESSAGE_KEYSTORE') == '1'


def backend():
    """Human-readable name of the vault backend in use (for logs/evidence)."""
    _load_master()
    return _backend


# ---------------------------------------------------------------------------
# payload encryption
# ---------------------------------------------------------------------------

def _subkeys():
    master = _load_master()
    enc_key = hmac.new(master, _KDF_ENC, hashlib.sha512).digest()[:32]
    mac_key = hmac.new(master, _KDF_MAC, hashlib.sha512).digest()[:32]
    return enc_key, mac_key


def _aes_cbc(key, iv, data, encrypt):
    from pyelliptic.cipher import Cipher

    cipher = Cipher(key, iv, 1 if encrypt else 0, ciphername='aes-256-cbc')
    return cipher.ciphering(data)


def encrypt_blob(plain):
    """Encrypt *plain* bytes into the self-describing container."""
    enc_key, mac_key = _subkeys()
    iv = os.urandom(16)
    ciphertext = _aes_cbc(enc_key, iv, plain, True)
    mac = hmac.new(mac_key, iv + ciphertext, hashlib.sha512).digest()[:32]
    return MAGIC + iv + mac + ciphertext


def decrypt_blob(blob):
    """Inverse of :func:`encrypt_blob`; raises ValueError on tampering."""
    if not looks_encrypted(blob):
        raise ValueError('not an encrypted keys.dat')
    body = blob[len(MAGIC):]
    if len(body) < 16 + 32:
        raise ValueError('truncated encrypted keys.dat')
    iv, mac, ciphertext = body[:16], body[16:48], body[48:]
    enc_key, mac_key = _subkeys()
    expected = hmac.new(mac_key, iv + ciphertext, hashlib.sha512).digest()[:32]
    if not hmac.compare_digest(mac, expected):
        raise ValueError('keys.dat failed authentication (wrong device or '
                         'tampered file)')
    return _aes_cbc(enc_key, iv, ciphertext, False)


def reset_cache():
    """Forget the cached master secret (tests, and after wiping ``appdata``)."""
    global _master, _backend
    _master = None
    _backend = None
