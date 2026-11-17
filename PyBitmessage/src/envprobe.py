# pylint: disable=broad-except,import-error
"""Runtime capability probe (milestone M2.1.1).

Prints a handful of ``PROBE <name> = OK/FAIL (...)`` lines so that the Android
logcat can be grepped:

    adb logcat -d | grep PROBE

Design rules:

* **never raise** -- a probe that crashes the app is useless;
* only stdlib + project code, no new dependencies;
* one line per capability, plus a final ``PROBE summary`` line.

The results decide gate ``G2.1`` in ``MILESTONES.md``: if RIPEMD-160 or the
OpenSSL/pyelliptic layer is unavailable, the whole Android port gets more
expensive, so this runs before any feature work.
"""

import hashlib
import sys

PREFIX = 'PROBE'


def _report(name, fn):
    """Run ``fn`` and print one PROBE line. Returns True on success."""
    try:
        detail = fn()
    except Exception as exc:  # noqa: BLE001 - must never break startup
        print('%s %s = FAIL (%s: %s)' % (PREFIX, name, type(exc).__name__, exc))
        return False
    print('%s %s = OK (%s)' % (PREFIX, name, detail))
    return True


def _python():
    return '%s %s' % (sys.version.split()[0], sys.platform)


def _openssl_version():
    import ssl
    return ssl.OPENSSL_VERSION


def _ripemd160():
    digest = hashlib.new('ripemd160')
    digest.update(b'bitmessage')
    return digest.hexdigest()[:16]


def _import_pyelliptic():
    """pyelliptic lives next to the entry point, but try both layouts."""
    try:
        import pyelliptic  # noqa: F401
        return pyelliptic
    except ImportError:
        from pybitmessage import pyelliptic  # noqa: F401
        return pyelliptic


def _openssl_layer():
    pyelliptic = _import_pyelliptic()
    lib = pyelliptic.OpenSSL
    return 'lib=%s' % getattr(lib, '_lib', lib)


def _ecc_sign():
    pyelliptic = _import_pyelliptic()
    ecc = pyelliptic.ECC(curve='secp256k1')
    payload = b'probe'
    signature = ecc.sign(payload)
    if not ecc.verify(signature, payload):
        raise ValueError('signature verification returned False')
    return 'sign/verify ok (%d byte sig)' % len(signature)


def _ecies():
    """Full ECIES roundtrip: this is what msg/pubkey encryption needs."""
    pyelliptic = _import_pyelliptic()
    ecc = pyelliptic.ECC(curve='secp256k1')
    payload = b'bitmessage probe'
    ciphertext = pyelliptic.ECC.encrypt(payload, ecc.get_pubkey())
    if ecc.decrypt(ciphertext) != payload:
        raise ValueError('decrypt mismatch')
    return 'encrypt/decrypt ok (%d bytes)' % len(ciphertext)


def _sqlite3():
    import sqlite3
    conn = sqlite3.connect(':memory:')
    try:
        version = conn.execute('select sqlite_version()').fetchone()[0]
    finally:
        conn.close()
    return version


def _msgpack():
    """Mirror the real fallback chain used by helper_msgcoding."""
    try:
        import msgpack
        return 'msgpack %s' % getattr(msgpack, '__version__', '?')
    except ImportError:
        pass
    try:
        import umsgpack
        return 'umsgpack %s (fallback)' % getattr(umsgpack, '__version__', '?')
    except ImportError:
        pass
    import fallback.umsgpack.umsgpack as bundled
    return 'bundled umsgpack %s (fallback)' % getattr(
        bundled, '__version__', '?')


def _pycryptodome():
    from Crypto import __version__ as version
    return 'pycryptodome %s' % version


def run():
    """Run all probes and print a summary. Safe to call from any entry point."""
    checks = [
        ('python', _python),
        ('openssl_runtime', _openssl_version),
        ('ripemd160', _ripemd160),
        ('openssl_layer', _openssl_layer),
        ('ecc_sign', _ecc_sign),
        ('ecies', _ecies),
        ('sqlite3', _sqlite3),
        ('msgpack', _msgpack),
        ('pycryptodome', _pycryptodome),
    ]
    results = [_report(name, fn) for name, fn in checks]
    print(
        '%s summary: %d/%d ok, failed=%s' % (
            PREFIX,
            sum(results),
            len(results),
            ','.join(
                name for (name, _), ok in zip(checks, results) if not ok
            ) or 'none',
        )
    )
    return results
