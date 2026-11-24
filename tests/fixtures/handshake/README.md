"""Handshake fixtures captured from real PyBitmessage nodes (2026-11-24).

Each file is one complete, framed packet (magic + 12-byte command + length +
checksum + payload), taken off the wire:

* ``client_version.bin`` -- 129 B, what our node sends first when dialling.
* ``server_version.bin`` -- 153 B, what a peer answers with (loopback capture,
  i.e. the same code on both ends).
* ``server_verack.bin``  -- 24 B, an empty verack.
* ``client_verack.bin``  -- empty on purpose: the captured node **never sent
  its own verack** in reply to a full version+verack, which is the defect
  tracked as M4.8.9 (see PyBitmessage-android/EVIDENCE.md).

``scripts/handshake_probe.py`` feeds these through ``BMProto`` in isolation.
"""
