"""
BMConfigParser class definition and default configuration settings
"""

import io
import os
import shutil
from datetime import datetime
from threading import Event

import keystore

from six import string_types
from six.moves import configparser

try:
    import state
except ImportError:
    from pybitmessage import state

SafeConfigParser = configparser.SafeConfigParser
config_ready = Event()


class BMConfigParser(SafeConfigParser):
    """
    Singleton class inherited from :class:`configparser.SafeConfigParser`
    with additional methods specific to bitmessage config.
    """
    # pylint: disable=too-many-ancestors
    _temp = {}

    def set(self, section, option, value=None):
        if self._optcre is self.OPTCRE or value:
            if not isinstance(value, string_types):
                raise TypeError("option values must be strings")
        if not self.validate(section, option, value):
            raise ValueError("Invalid value %s" % value)
        return SafeConfigParser.set(self, section, option, value)

    def get(self, section, option, **kwargs):  # pylint: disable=arguments-differ
        """Try returning temporary value before using parent get()"""
        try:
            return self._temp[section][option]
        except KeyError:
            pass
        return SafeConfigParser.get(
            self, section, option, **kwargs)

    def setTemp(self, section, option, value=None):
        """Temporary set option to value, not saving."""
        try:
            self._temp[section][option] = value
        except KeyError:
            self._temp[section] = {option: value}

    def safeGetBoolean(self, section, option):
        """Return value as boolean, False on exceptions"""
        try:
            return self.getboolean(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError,
                ValueError, AttributeError):
            return False

    def safeGetInt(self, section, option, default=0):
        """Return value as integer, default on exceptions,
        0 if default missing"""
        try:
            return int(self.get(section, option))
        except (configparser.NoSectionError, configparser.NoOptionError,
                ValueError, AttributeError):
            return default

    def safeGetFloat(self, section, option, default=0.0):
        """Return value as float, default on exceptions,
        0.0 if default missing"""
        try:
            return self.getfloat(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError,
                ValueError, AttributeError):
            return default

    def safeGet(self, section, option, default=None):
        """
        Return value as is, default on exceptions, None if default missing
        """
        try:
            return self.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError,
                ValueError, AttributeError):
            return default

    def items(self, section, raw=False, vars=None):  # pylint: disable=redefined-builtin
        # pylint: disable=signature-differs
        """Return section variables as parent,
        but override the "raw" argument to always True"""
        return SafeConfigParser.items(self, section, True, vars)

    def _reset(self):
        """
        Reset current config.
        There doesn't appear to be a built in method for this.
        """
        self._temp = {}
        sections = self.sections()
        for x in sections:
            self.remove_section(x)

    def read(self, filenames=None):
        self._reset()
        SafeConfigParser.read(
            self, os.path.join(os.path.dirname(__file__), 'default.ini'))
        if not filenames:
            return
        if isinstance(filenames, string_types):
            filenames = [filenames]
        for filename in filenames:
            self._read_config_file(filename)

    def _read_config_file(self, filename):
        """Read one config file, transparently decrypting it if needed.

        ``configparser``'s own ``read()`` cannot be used for ``keys.dat``
        because on Android the file is encrypted (M4.5.2). Anything without
        the vault magic is treated as legacy plain text, which is also the
        migration path: the next ``save()`` writes it encrypted.
        """
        try:
            with open(filename, 'rb') as handle:
                data = handle.read()
        except (IOError, OSError):
            # configparser semantics: a missing file is not an error
            return
        if keystore.looks_encrypted(data):
            try:
                data = keystore.decrypt_blob(data)
            except Exception as exc:  # noqa: BLE001 - never brick the app
                # The vault is missing or belongs to another device. Starting
                # with an empty config would silently mint a NEW identity and
                # the user would never notice their messages go nowhere, so
                # keep the unreadable file for recovery and say it loudly.
                salvage = '%s.unreadable-%s' % (
                    filename, datetime.now().strftime('%Y%m%d%H%M%S'))
                try:
                    os.replace(filename, salvage)
                except OSError:
                    salvage = '(could not be moved)'
                print(
                    'KEYSTORE FATAL: cannot decrypt %s (%r). The matching '
                    'keys.vault must be present; a keys.dat copied from '
                    'another device cannot be opened here. The file was kept '
                    'at %s and a NEW identity will be created.'
                    % (filename, exc, salvage), flush=True)
                # Deliberately NOT raising: a phone that refuses to start is
                # worse than a phone that starts with (clearly logged) new
                # keys. `keys.dat.unreadable-*` is the recovery path.
                return
            else:
                print('KEYSTORE decrypted %s (%s)' % (
                    os.path.basename(filename), keystore.backend()),
                    flush=True)
        self.read_string(data.decode('utf-8'))

    def addresses(self, sort=False):
        """Return a list of local bitmessage addresses (from section labels)"""
        sections = [x for x in self.sections() if x.startswith('BM-')]
        if sort:
            sections.sort(key=lambda item: self.get(item, 'label').lower())
        return sections

    @staticmethod
    def _drop_plaintext_backups(directory, keep=None):
        """Remove leftover ``keys.dat.*.bak`` files.

        ``save()`` deletes its own backup, so anything still lying around came
        from a crash -- and it is a **plain-text copy of every private key**,
        which would defeat the encryption entirely (M4.5.2). Only call this
        when the live file is encrypted.
        """
        try:
            names = os.listdir(directory)
        except OSError:
            return
        for name in names:
            if not name.startswith('keys.dat.') or not name.endswith('.bak'):
                continue
            path = os.path.join(directory, name)
            if keep and os.path.abspath(path) == os.path.abspath(keep):
                continue
            try:
                os.unlink(path)
            except OSError:
                pass

    def save(self):
        """Save the runtime config onto the filesystem.

        M4.5.2: on Android the payload is encrypted by :mod:`keystore`; plain
        text is still accepted on read, so existing installs migrate on their
        first save. The write itself is atomic (temp file + ``os.replace``)
        because a half-written ``keys.dat`` loses the identity outright.
        """
        fileName = os.path.join(state.appdata, 'keys.dat')
        fileNameBak = '.'.join([
            fileName, datetime.now().strftime("%Y%j%H%M%S%f"), 'bak'])
        # create a backup copy to prevent the accidental loss due to
        # the disk write failure
        try:
            shutil.copyfile(fileName, fileNameBak)
            # The backup succeeded.
            fileNameExisted = True
        except (IOError, Exception):
            # The backup failed. This can happen if the file
            # didn't exist before.
            fileNameExisted = False

        buffer = io.StringIO()
        self.write(buffer)
        payload = buffer.getvalue().encode('utf-8')
        if keystore.enabled():
            data = keystore.encrypt_blob(payload)
            if self.safeGet('bitmessagesettings', 'keysencrypted') != 'true':
                # record it in the file itself, before it is written
                SafeConfigParser.set(
                    self, 'bitmessagesettings', 'keysencrypted', 'true')
                buffer = io.StringIO()
                self.write(buffer)
                payload = buffer.getvalue().encode('utf-8')
                data = keystore.encrypt_blob(payload)
        else:
            data = payload

        tmpName = fileName + '.tmp'
        descriptor = os.open(
            tmpName, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmpName, fileName)
        except Exception:  # noqa: BLE001 - keep the old file instead of dying
            try:
                os.unlink(tmpName)
            except OSError:
                pass
            raise
        # delete the backup
        if fileNameExisted:
            os.remove(fileNameBak)
        if keystore.enabled():
            # never leave a readable copy of the keys behind (crashes used to)
            self._drop_plaintext_backups(os.path.dirname(fileName))

    def validate(self, section, option, value):
        """Input validator interface (using factory pattern)"""
        try:
            return getattr(self, 'validate_%s_%s' % (section, option))(value)
        except AttributeError:
            return True

    @staticmethod
    def validate_bitmessagesettings_maxoutboundconnections(value):
        """Reject maxoutboundconnections that are too high or too low"""
        try:
            value = int(value)
        except ValueError:
            return False
        if value < 0 or value > 8:
            return False
        return True

    def search_addresses(self, address, searched_text):
        """Return the searched label of MyAddress"""
        return [x for x in [self.get(address, 'label').lower(),
                            address.lower()] if searched_text in x]

    def disable_address(self, address):
        """"Disabling the specific Address"""
        self.set(str(address), 'enabled', 'false')
        self.save()

    def enable_address(self, address):
        """"Enabling the specific Address"""
        self.set(address, 'enabled', 'true')
        self.save()


if not getattr(BMConfigParser, 'read_file', False):
    BMConfigParser.read_file = BMConfigParser.readfp

config = BMConfigParser()  # TODO: remove this crutch
