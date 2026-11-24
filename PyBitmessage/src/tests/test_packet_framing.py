"""Packet framing regression tests (M4.8.9).

Run from ``PyBitmessage/src``::

    python3 -m unittest tests.test_packet_framing -v

Wire captures from public peers (2026-11-24) showed every packet we sent
carrying an 8-byte command field instead of the protocol's 12: our stream
became undecodable for the peer, which answered *our version* with an 8-byte
command frame and then reset the connection. These tests make the packet
helpers return packet *bytes* so a caller cannot re-frame the header as a
bytes object (``bytes(header) + payload`` is what produced the 16-byte
header: magic + 12-byte command).

They also pin ``CreatePacket`` itself: the command must be zero-padded to
the 12-byte field for every command we send.
"""

import os
import socket
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The protocol helpers read a minimal config; build one on the fly so the
# test does not depend on the machine's real BITMESSAGE_HOME.
_HOME = os.environ.setdefault(
    'BITMESSAGE_HOME', os.path.join(tempfile.gettempdir(), 'packet-framing-test'))
os.makedirs(_HOME, exist_ok=True)
with open(os.path.join(_HOME, 'keys.dat'), 'w') as _fh:
    _fh.write('[bitmessagesettings]\nsettingsversion = 10\nport = 18444\n'
              'socksproxytype = none\n')
with open(os.path.join(_HOME, 'defaults.ini'), 'w') as _fh:
    _fh.write('[network]\ndandelion = 0\n')

import protocol  # noqa: E402
from addresses import encodeVarint  # noqa: E402
from network.bmproto import BMProto  # noqa: E402

#: the wire header is always 24 bytes: magic(4) + command(12) + length(4) +
#: checksum(4)
WIRE_HEADER = 24

HEADER_SIZE = WIRE_HEADER


def _split(packet):
    magic, command, length, checksum = protocol.Header.unpack(packet[:HEADER_SIZE])
    return magic, command, length, checksum, packet[HEADER_SIZE:]


class CreatePacketTest(unittest.TestCase):

    def test_command_field_is_zero_padded_to_twelve_bytes(self):
        for command in ('verack', 'version', 'addr', 'inv', 'getdata', 'object'):
            with self.subTest(command=command):
                packet = protocol.CreatePacket(command, b'\x01\x02\x03')
                self.assertEqual(packet[4:16], command.encode().ljust(12, b'\x00'))
                # the length field must follow the full 12-byte command field
                self.assertEqual(
                    struct.unpack('>L', packet[16:20])[0], 3)
                self.assertEqual(len(packet), HEADER_SIZE + 3)

    def test_empty_payload_packet_is_exactly_header_sized(self):
        packet = protocol.CreatePacket('verack')
        self.assertEqual(len(packet), HEADER_SIZE)
        magic, command, length, checksum, payload = _split(packet)
        self.assertEqual(command, b'verack\x00\x00\x00\x00\x00\x00')
        self.assertEqual(length, 0)
        self.assertEqual(payload, b'')
        self.assertEqual(checksum, protocol.hashlib.sha512(b'').digest()[:4])

    def test_round_trip_through_the_protocol_parser(self):
        """A packet created here must parse back with the same command/payload."""
        payload = b'\x01\x02\x03\x04\x05'
        packet = protocol.CreatePacket('object', payload)
        magic, command, length, checksum, got = _split(packet)
        self.assertEqual(length, len(payload))
        self.assertEqual(got, payload)
        # BMProto decides packet boundaries from the header the same way
        self.assertEqual(command.rstrip(b'\x00'), b'object')


class BytesAndHelperReturnTypesTest(unittest.TestCase):
    """The helpers must hand back complete packets, never bare headers."""

    def test_addr_message_is_a_complete_packet(self):
        msg = protocol.assembleAddrMessage([(1, protocol.Peer('1.2.3.4', 8444),
                                             int(protocol.time.time()))])
        self.assertIsInstance(msg, bytes)
        self.assertEqual(msg[4:16], b'addr' + b'\x00' * 8)
        self.assertEqual(struct.unpack('>L', msg[16:20])[0], len(msg) - 24)

    def test_version_message_is_a_complete_packet(self):
        msg = protocol.assembleVersionMessage(
            '1.2.3.4', 8444, [1], False, True)
        self.assertIsInstance(msg, bytes)
        self.assertEqual(msg[4:16], b'version' + b'\x00' * 5)
        self.assertEqual(struct.unpack('>L', msg[16:20])[0], len(msg) - 24)
        self.assertGreater(len(msg), 24)

    def test_error_message_is_a_complete_packet(self):
        msg = protocol.assembleErrorMessage(errorText='boom')
        self.assertIsInstance(msg, bytes)
        self.assertEqual(msg[4:16], b'error' + b'\x00' * 7)


if __name__ == '__main__':
    unittest.main()
