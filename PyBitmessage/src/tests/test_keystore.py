"""Tests for private-key at-rest encryption (milestone M4.5.2).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_keystore -v

The desktop has no secure element, so these tests exercise the *file* vault
backend; the crypto container and the config migration are identical to what
the Android Keystore backend produces (only the wrapping of the 32-byte master
secret differs, and that part cannot run off-device).
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_HOME = tempfile.mkdtemp(prefix='keystore-test-')
os.environ['BITMESSAGE_HOME'] = _HOME
os.environ.pop('ANDROID_ARGUMENT', None)


def setUpModule():  # noqa: N802 - unittest hook name
    import state
    state.appdata = _HOME + os.sep


class VaultTest(unittest.TestCase):

    def setUp(self):
        import keystore
        import state
        state.appdata = _HOME + os.sep
        keystore.reset_cache()
        for name in os.listdir(_HOME):
            path = os.path.join(_HOME, name)
            if os.path.isfile(path):
                os.unlink(path)
        self.keystore = keystore

    def test_master_is_created_once_and_persisted(self):
        first = self.keystore._load_master()
        self.assertEqual(len(first), 32)
        vault = os.path.join(_HOME, 'keys.vault')
        self.assertTrue(os.path.exists(vault), 'vault must be on disk')
        # a fresh process (cache dropped) must get the same secret back
        self.keystore.reset_cache()
        second = self.keystore._load_master()
        self.assertEqual(first, second, 'master must survive a restart')

    def test_vault_is_not_world_readable(self):
        self.keystore._load_master()
        mode = os.stat(os.path.join(_HOME, 'keys.vault')).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_blob_roundtrip_and_detection(self):
        plain = b'[bitmessagesettings]\nport = 8444\n'
        blob = self.keystore.encrypt_blob(plain)
        self.assertTrue(self.keystore.looks_encrypted(blob))
        self.assertEqual(blob[:8], self.keystore.MAGIC)
        self.assertEqual(self.keystore.decrypt_blob(blob), plain)
        self.assertNotIn(b'port = 8444', blob, 'plaintext leaked into blob')

    def test_each_encryption_uses_a_fresh_iv(self):
        plain = b'same payload'
        self.assertNotEqual(
            self.keystore.encrypt_blob(plain),
            self.keystore.encrypt_blob(plain),
            'identical ciphertexts mean a reused IV')

    def test_tampering_is_rejected(self):
        blob = bytearray(self.keystore.encrypt_blob(b'secret'))
        blob[-1] ^= 0xFF
        with self.assertRaises(ValueError):
            self.keystore.decrypt_blob(bytes(blob))

    def test_truncated_blob_is_rejected(self):
        with self.assertRaises(ValueError):
            self.keystore.decrypt_blob(self.keystore.MAGIC + b'short')

    def test_another_vault_cannot_open_the_blob(self):
        blob = self.keystore.encrypt_blob(b'secret')
        # simulate "the file came from a different device"
        os.unlink(os.path.join(_HOME, 'keys.vault'))
        self.keystore.reset_cache()
        self.keystore._load_master()          # a brand new master
        with self.assertRaises(ValueError):
            self.keystore.decrypt_blob(blob)

    def test_enabled_defaults_off_on_desktop(self):
        os.environ.pop('BITMESSAGE_KEYSTORE', None)
        os.environ.pop('ANDROID_ARGUMENT', None)
        self.assertFalse(self.keystore.enabled())
        os.environ['ANDROID_ARGUMENT'] = '/dev/null'
        try:
            self.assertTrue(self.keystore.enabled(),
                            'must be on for Android (C4)')
        finally:
            os.environ.pop('ANDROID_ARGUMENT', None)


class ConfigMigrationTest(unittest.TestCase):
    """``BMConfigParser`` must encrypt on save and still read old files."""

    def setUp(self):
        import keystore
        import state
        state.appdata = _HOME + os.sep
        keystore.reset_cache()
        for name in os.listdir(_HOME):
            path = os.path.join(_HOME, name)
            if os.path.isfile(path):
                os.unlink(path)
        self.keystore = keystore
        self.path = os.path.join(_HOME, 'keys.dat')
        os.environ['BITMESSAGE_KEYSTORE'] = '1'
        from bmconfigparser import BMConfigParser
        self.parser_class = BMConfigParser

    def tearDown(self):
        os.environ.pop('BITMESSAGE_KEYSTORE', None)

    def _write_plain(self, address='BM-2cXrmLDcoGry6Z4kRWqCthD7kuhRxkzaWx'):
        with open(self.path, 'w') as handle:
            handle.write(
                '[bitmessagesettings]\nport = 8444\nkeysencrypted = False\n'
                '\n[%s]\nlabel = phone\nprivenc = 4f3a9c\n'
                'privsig = 88bd11\n' % address)
        return address

    def test_plaintext_file_is_still_readable(self):
        address = self._write_plain()
        config = self.parser_class()
        config.read(self.path)
        self.assertEqual(config.get('bitmessagesettings', 'port'), '8444')
        self.assertEqual(config.get(address, 'privenc'), '4f3a9c')

    def test_save_encrypts_and_sets_the_flag(self):
        self._write_plain()
        config = self.parser_class()
        config.read(self.path)
        config.set('bitmessagesettings', 'port', '8445')
        config.save()

        raw = open(self.path, 'rb').read()
        self.assertTrue(self.keystore.looks_encrypted(raw))
        self.assertNotIn(b'privsig', raw, 'private key leaked in clear')
        self.assertNotIn(b'port = 8445', raw)

        reloaded = self.parser_class()
        reloaded.read(self.path)
        self.assertEqual(reloaded.get('bitmessagesettings', 'port'), '8445')
        self.assertEqual(
            reloaded.get('bitmessagesettings', 'keysencrypted'), 'true')

    def test_encrypted_file_survives_repeated_saves(self):
        self._write_plain()
        for port in ('8446', '8447', '8448'):
            config = self.parser_class()
            config.read(self.path)
            config.set('bitmessagesettings', 'port', port)
            config.save()
        final = self.parser_class()
        final.read(self.path)
        self.assertEqual(final.get('bitmessagesettings', 'port'), '8448')

    def test_unreadable_file_is_preserved_not_destroyed(self):
        blob = self.keystore.encrypt_blob(b'[bitmessagesettings]\nport = 1\n')
        with open(self.path, 'wb') as handle:
            handle.write(blob)
        # a different vault => cannot decrypt
        os.unlink(os.path.join(_HOME, 'keys.vault'))
        self.keystore.reset_cache()
        self.keystore._load_master()

        config = self.parser_class()
        config.read(self.path)          # must not raise
        salvage = [n for n in os.listdir(_HOME)
                   if n.startswith('keys.dat.unreadable-')]
        self.assertTrue(salvage, 'the unreadable file must be kept')
        self.assertFalse(os.path.exists(self.path))

    def test_plaintext_backups_are_removed(self):
        """A crashed save can leave keys.dat.*.bak -- plain text, must go."""
        self._write_plain()
        stale = os.path.join(_HOME, 'keys.dat.20261124120000000000.bak')
        with open(stale, 'w') as handle:
            handle.write('[bitmessagesettings]\nprivsig = deadbeef\n')
        config = self.parser_class()
        config.read(self.path)
        config.save()
        self.assertFalse(os.path.exists(stale),
                         'plain-text backup must not survive a save')

    def test_no_leftover_temp_file(self):
        self._write_plain()
        config = self.parser_class()
        config.read(self.path)
        config.save()
        self.assertFalse(os.path.exists(self.path + '.tmp'))


def tearDownModule():  # noqa: N802 - unittest hook name
    shutil.rmtree(_HOME, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
