"""Checks for the measured, read-only part of the TR-6S port."""

import unittest

from tr6s.kit import Kit, KitError
from tr6s.pattern import Pattern, PatternError
from tr6s.transport import (BLOB_SIZES, DT1, MODEL_TR6S, Transport,
                            TransportError, checksum, encode7, make_sysex,
                            unpack7)


class TR6SPortTests(unittest.TestCase):
    def test_tr6s_sysex_frame(self):
        message = make_sysex(DT1, (0x50, 0, 0, 0x41), encode7(0, 4) + encode7(1, 4))
        self.assertEqual(message, bytes.fromhex(
            "F0 41 10 00 00 00 6D 12 50 00 00 41 00 00 00 00 00 00 00 01 6E F7"
        ))
        self.assertEqual(MODEL_TR6S, (0, 0, 0, 0x6D))
        self.assertEqual(checksum(message[8:-2]), message[-2])


    def test_measured_blob_sizes_and_write_guard(self):
        self.assertEqual(BLOB_SIZES, {"system": 754, "pattern": 24599, "kit": 1317})
        transport = Transport()
        with self.assertRaisesRegex(TransportError, "bulk writes are disabled"):
            transport.send_blob("pattern", 0, bytes(24599))
        with self.assertRaisesRegex(TransportError, "commits are disabled"):
            transport.commit("kit", 0)
        with self.assertRaisesRegex(TransportError, "not verified"):
            transport.read_blob("tone", 0)


    def test_7bit_unpacking(self):
        self.assertEqual(unpack7(bytes([0b00000101, 0, 1, 2, 3])),
                         bytes([128, 1, 130, 3]))

    def test_blob_models_keep_unverified_offsets_hidden(self):
        pattern = Pattern.from_bytes(b"TEST PATTERN    " + bytes(24599 - 16))
        self.assertEqual(pattern.name, "TEST PATTERN")
        self.assertTrue(pattern.describe()["variations_unmapped"])
        with self.assertRaisesRegex(PatternError, "not verified"):
            pattern.get_steps("A", "BD")
        kit = Kit.from_bytes(b"TEST KIT        " + bytes(1317 - 16))
        self.assertEqual(kit.name, "TEST KIT")
        with self.assertRaisesRegex(KitError, "not verified"):
            kit.get("BD", "tune")
