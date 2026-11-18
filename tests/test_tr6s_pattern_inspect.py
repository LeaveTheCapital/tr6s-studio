"""Offline coverage for TR-6S pattern inspection, pattern diffs, and their CLI.

No pattern offset has a TR-6S panel capture. Name, tempo, kit, and scale are
TR-8S header candidates. Shuffle, steps, variations, and motion stay
"not verified"; inherited offsets may appear only as candidate labels.
"""

import json
import struct
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tr6s.cli import main
from tr6s.pattern import (
    BLOCK,
    CANDIDATE_TR8S_TRACKS,
    HEADER,
    MOTION_TUNE_LANE_BASE,
    SIZE,
    STEP_STRIDE,
    TRACK_BASE,
    TRACK_STRIDE,
    VERIFIED_RAW_OFFSETS,
    Pattern,
    PatternError,
    candidate_field,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pattern.bin"
NOTES_FIXTURE = ROOT / "notes" / "pattern_000.bin"


def at(block: int, track: int, step: int = 0, byte: int = 0) -> int:
    return (HEADER + block * BLOCK + TRACK_BASE
            + track * TRACK_STRIDE + step * STEP_STRIDE + byte)


def pattern_blob() -> bytes:
    raw = bytearray(SIZE)
    raw[0:16] = b"PANEL CHECK".ljust(16)
    struct.pack_into("<H", raw, 16, 1340)  # 134.0 BPM, TR-8S tenths
    raw[18] = 2                            # panel kit 2
    raw[19] = 2                            # scale "16"
    raw[32] = 0x80
    raw[48] = 0x01
    raw[at(0, 0)] = 112                    # candidate A BD step 0 velocity
    return bytes(raw)


def flip(blob: bytes, *offsets: int) -> tuple[Pattern, dict[int, int]]:
    raw = bytearray(blob)
    updated = {}
    for offset in offsets:
        value = (raw[offset] + 1) & 0xFF
        raw[offset] = value
        updated[offset] = value
    return Pattern.from_bytes(raw), updated


def run_cli(argv):
    stdout, stderr = StringIO(), StringIO()
    with patch("tr6s.cli.SequencerTransport", side_effect=AssertionError("MIDI transport opened")):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class PatternInspectTests(unittest.TestCase):
    def test_no_pattern_offset_is_verified(self):
        self.assertEqual(SIZE, 24504)
        self.assertEqual(len(pattern_blob()), 24504)
        self.assertEqual(VERIFIED_RAW_OFFSETS, {})
        self.assertEqual(CANDIDATE_TR8S_TRACKS, [
            "BD", "SD", "LT", "MT", "HT", "RS", "HC", "CH", "OH", "CC", "RC",
        ])
        self.assertNotIn("MT", ["BD", "SD", "LT", "HC", "CH", "OH"])

    def test_inspect_keeps_header_provisional_and_steps_unverified(self):
        report = Pattern.from_bytes(pattern_blob()).inspect()
        self.assertEqual(report["verified"], {})
        header = report["candidates"]["header"]
        self.assertEqual(header["name"], {
            "status": "candidate", "offset": 0, "length": 16, "value": "PANEL CHECK",
        })
        self.assertEqual(header["tempo"], {
            "status": "candidate", "offset": 16, "length": 2, "raw": 1340, "bpm": 134.0,
        })
        self.assertEqual(header["kit"], {
            "status": "candidate", "offset": 18, "length": 1,
            "raw": 2, "index": 1, "panel": 2,
        })
        self.assertEqual(header["scale"], {
            "status": "candidate", "offset": 19, "length": 1, "raw": 2, "value": "16",
        })
        withheld = report["candidates"]["not_verified"]
        self.assertEqual(withheld["shuffle"], "not verified")
        self.assertEqual(withheld["steps"], "not verified")
        self.assertEqual(withheld["variations"], "not verified")
        self.assertEqual(withheld["motion"], "not verified")
        self.assertEqual(withheld["shuffle_candidate"]["offset"], 32)
        self.assertEqual(withheld["shuffle_candidate"]["raw"], 0x80)
        self.assertEqual(withheld["variation_mask_candidate"]["offset"], 48)
        self.assertEqual(withheld["variation_mask_candidate"]["raw"], 0x01)
        geometry = withheld["step_geometry"]
        self.assertEqual(geometry["status"], "not verified")
        self.assertEqual(geometry["inherited_from"], "TR-8S")
        self.assertEqual(geometry["track_order"], CANDIDATE_TR8S_TRACKS)
        self.assertNotIn("steps", report["verified"])
        self.assertNotIn("variations", report)

    def test_existing_readers_still_refuse_unverified_layout(self):
        pattern = Pattern.from_bytes(pattern_blob())
        described = pattern.describe()
        self.assertEqual(described["name"], "PANEL CHECK")
        self.assertTrue(described["variations_unmapped"])
        self.assertNotIn("variations", described)
        with self.assertRaisesRegex(PatternError, "not verified"):
            _ = pattern.shuffle
        with self.assertRaisesRegex(PatternError, "not verified"):
            pattern.shuffle = 0
        with self.assertRaisesRegex(PatternError, "not verified"):
            pattern.get_steps("A", "BD")

    def test_diff_labels_header_candidates_and_leaves_verified_empty(self):
        blob = pattern_blob()
        pattern = Pattern.from_bytes(blob)
        expected = {
            0: "name",
            16: "tempo",
            17: "tempo",
            18: "kit",
            19: "scale",
            32: "shuffle",
            48: "variation_mask",
        }
        for offset, label in expected.items():
            with self.subTest(offset=offset, field=label):
                changed, updated = flip(blob, offset)
                self.assertEqual(pattern.diff(changed), [{
                    "offset": offset,
                    "length": 1,
                    "before": [blob[offset]],
                    "after": [updated[offset]],
                    "before_hex": f"{blob[offset]:02X}",
                    "after_hex": f"{updated[offset]:02X}",
                    "verified_field": None,
                    "candidate_field": label,
                }])
                self.assertEqual(changed.inspect()["verified"], {})
                self.assertEqual(
                    changed.inspect()["candidates"]["not_verified"]["shuffle"],
                    "not verified",
                )

    def test_diff_groups_a_run_and_splits_on_a_different_label(self):
        blob = pattern_blob()
        pattern = Pattern.from_bytes(blob)
        changed, updated = flip(blob, 0, 1, 16, 17, 18, 19, 20, 21)
        self.assertEqual(pattern.diff(changed), [
            {
                "offset": 0,
                "length": 2,
                "before": [blob[0], blob[1]],
                "after": [updated[0], updated[1]],
                "before_hex": f"{blob[0]:02X} {blob[1]:02X}",
                "after_hex": f"{updated[0]:02X} {updated[1]:02X}",
                "verified_field": None,
                "candidate_field": "name",
            },
            {
                "offset": 16,
                "length": 2,
                "before": [blob[16], blob[17]],
                "after": [updated[16], updated[17]],
                "before_hex": f"{blob[16]:02X} {blob[17]:02X}",
                "after_hex": f"{updated[16]:02X} {updated[17]:02X}",
                "verified_field": None,
                "candidate_field": "tempo",
            },
            {
                "offset": 18,
                "length": 1,
                "before": [blob[18]],
                "after": [updated[18]],
                "before_hex": f"{blob[18]:02X}",
                "after_hex": f"{updated[18]:02X}",
                "verified_field": None,
                "candidate_field": "kit",
            },
            {
                "offset": 19,
                "length": 1,
                "before": [blob[19]],
                "after": [updated[19]],
                "before_hex": f"{blob[19]:02X}",
                "after_hex": f"{updated[19]:02X}",
                "verified_field": None,
                "candidate_field": "scale",
            },
            {
                "offset": 20,
                "length": 2,
                "before": [blob[20], blob[21]],
                "after": [updated[20], updated[21]],
                "before_hex": f"{blob[20]:02X} {blob[21]:02X}",
                "after_hex": f"{updated[20]:02X} {updated[21]:02X}",
                "verified_field": None,
                "candidate_field": None,
            },
        ])

    def test_diff_does_not_bridge_an_unchanged_byte(self):
        blob = pattern_blob()
        changed, _updated = flip(blob, 0, 2)
        rows = Pattern.from_bytes(blob).diff(changed)
        self.assertEqual([row["offset"] for row in rows], [0, 2])
        self.assertTrue(all(row["candidate_field"] == "name" for row in rows))
        self.assertTrue(all(row["length"] == 1 for row in rows))

    def test_diff_labels_inherited_step_and_motion_geometry(self):
        blob = pattern_blob()
        pattern = Pattern.from_bytes(blob)
        oh = CANDIDATE_TR8S_TRACKS.index("OH")
        compact_sixth = 5  # BD SD LT HC CH OH would land here; TR-8S calls it RS
        cases = {
            at(0, 0): "A_BD_step00_velocity",
            at(0, 0, 0, 1): "A_BD_step00_byte1",
            at(0, oh): "A_OH_step00_velocity",
            at(0, compact_sixth): "A_RS_step00_velocity",
            at(1, 0, 3): "B_BD_step03_velocity",
            at(7, 10, 15, 3): "H_RC_step15_byte3",
            at(0, MOTION_TUNE_LANE_BASE, 0, 0): "A_BD_motion_step00_tune",
            at(0, MOTION_TUNE_LANE_BASE, 0, 1): "A_BD_motion_step00_decay",
            at(0, MOTION_TUNE_LANE_BASE, 0, 2): "A_BD_motion_step00_ctrl",
            at(0, MOTION_TUNE_LANE_BASE, 0, 3): "A_BD_motion_step00_mask",
            at(0, MOTION_TUNE_LANE_BASE + oh, 1, 3): "A_OH_motion_step01_mask",
            at(8, 0): "block8_BD_step00_velocity",
            at(9, 1, 2, 2): "block9_SD_step02_byte2",
        }
        self.assertEqual(candidate_field(at(0, 11)), None)
        self.assertEqual(candidate_field(SIZE - 1), None)
        self.assertEqual(candidate_field(HEADER), None)  # block preamble
        for offset, label in cases.items():
            with self.subTest(offset=offset, field=label):
                self.assertEqual(candidate_field(offset), label)
                changed, updated = flip(blob, offset)
                row = pattern.diff(changed)[0]
                self.assertEqual(row["offset"], offset)
                self.assertEqual(row["length"], 1)
                self.assertEqual(row["before"], [blob[offset]])
                self.assertEqual(row["after"], [updated[offset]])
                self.assertIsNone(row["verified_field"])
                self.assertEqual(row["candidate_field"], label)
                self.assertEqual(changed.inspect()["verified"], {})

    def test_four_step_bytes_stay_separate_labels(self):
        blob = pattern_blob()
        base = at(0, 0)
        changed, _updated = flip(blob, base, base + 1, base + 2, base + 3)
        rows = Pattern.from_bytes(blob).diff(changed)
        self.assertEqual(
            [row["candidate_field"] for row in rows],
            [
                "A_BD_step00_velocity",
                "A_BD_step00_byte1",
                "A_BD_step00_byte2",
                "A_BD_step00_byte3",
            ],
        )
        self.assertEqual(sum(row["length"] for row in rows), 4)

    def test_diff_of_identical_patterns_is_empty_and_does_not_mutate(self):
        pattern = Pattern.from_bytes(pattern_blob())
        snapshot = bytes(pattern.raw)
        self.assertEqual(pattern.diff(pattern), [])
        self.assertEqual(pattern.diff(pattern.copy()), [])
        self.assertEqual(bytes(pattern.raw), snapshot)

    def test_rejects_pattern_blobs_other_than_24504_bytes(self):
        for length in (0, 24503, 24505, 1312):
            with self.subTest(length=length):
                with self.assertRaisesRegex(PatternError, f"{length} bytes, expected 24504"):
                    Pattern.from_bytes(bytes(length))


class PatternInspectCliTests(unittest.TestCase):
    def assert_success(self, code, out, err):
        self.assertEqual(code, 0, err or out)
        self.assertEqual(err, "")
        self.assertTrue(out.endswith("\n"))
        return json.loads(out)

    def assert_error(self, code, out, err, text):
        self.assertEqual(code, 1, out)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "), err)
        self.assertIn(text, err)

    def test_inspect_pattern_file_matches_library_inspect(self):
        blob = pattern_blob()
        library = Pattern.from_bytes(blob).inspect()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pattern.bin"
            path.write_bytes(blob)
            for slot in (0, 1, 127):
                with self.subTest(slot=slot):
                    code, out, err = run_cli(
                        ["inspect-pattern", str(slot), "--file", str(path)]
                    )
                    report = self.assert_success(code, out, err)
                    self.assertEqual(report, {
                        "slot": slot,
                        "source": str(path),
                        **library,
                    })

    def test_diff_pattern_matches_library_diff(self):
        before_blob = pattern_blob()
        after_pattern, _updated = flip(before_blob, 16, 17, at(0, 0), 21)
        after_blob = after_pattern.to_bytes()
        library = Pattern.from_bytes(before_blob).diff(after_pattern)
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.bin"
            after = Path(directory) / "after.bin"
            before.write_bytes(before_blob)
            after.write_bytes(after_blob)
            code, out, err = run_cli(["diff-pattern", str(before), str(after)])
            report = self.assert_success(code, out, err)
        self.assertEqual(report, {
            "before": str(before),
            "after": str(after),
            "changed_bytes": sum(row["length"] for row in library),
            "ranges": library,
        })
        by_offset = {row["offset"]: row for row in report["ranges"]}
        self.assertEqual(by_offset[16]["length"], 2)
        self.assertEqual(by_offset[16]["candidate_field"], "tempo")
        self.assertIsNone(by_offset[16]["verified_field"])
        self.assertEqual(by_offset[at(0, 0)]["candidate_field"], "A_BD_step00_velocity")
        self.assertIsNone(by_offset[21]["candidate_field"])
        self.assertEqual(report["changed_bytes"], 4)
        self.assertEqual(len(report["ranges"]), 3)

    def test_diff_pattern_identical_files_report_no_changes(self):
        blob = pattern_blob()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pattern.bin"
            path.write_bytes(blob)
            code, out, err = run_cli(["diff-pattern", str(path), str(path)])
            report = self.assert_success(code, out, err)
        self.assertEqual(report["changed_bytes"], 0)
        self.assertEqual(report["ranges"], [])

    def test_saved_fixtures_share_the_sakura_candidate_header(self):
        self.assertEqual(FIXTURE.read_bytes(), NOTES_FIXTURE.read_bytes())
        code, out, err = run_cli(["inspect-pattern", "0", "--file", str(FIXTURE)])
        report = self.assert_success(code, out, err)
        header = report["candidates"]["header"]
        self.assertEqual(report["verified"], {})
        self.assertEqual(header["name"]["value"], "Sakura")
        self.assertEqual(header["name"]["status"], "candidate")
        self.assertEqual(header["tempo"]["bpm"], 190.0)
        self.assertEqual(header["tempo"]["raw"], 1900)
        self.assertEqual(header["kit"]["raw"], 90)
        self.assertEqual(header["kit"]["index"], 89)
        self.assertEqual(header["kit"]["panel"], 90)
        self.assertEqual(header["scale"]["value"], "16")
        withheld = report["candidates"]["not_verified"]
        self.assertEqual(withheld["shuffle"], "not verified")
        self.assertEqual(withheld["steps"], "not verified")
        self.assertEqual(withheld["shuffle_candidate"]["raw"], 128)

        code, out, err = run_cli(["inspect-pattern", "0", "--file", str(NOTES_FIXTURE)])
        notes = self.assert_success(code, out, err)
        self.assertEqual(notes["candidates"], report["candidates"])
        self.assertEqual(notes["source"], str(NOTES_FIXTURE))

        code, out, err = run_cli(["diff-pattern", str(FIXTURE), str(NOTES_FIXTURE)])
        diff = self.assert_success(code, out, err)
        self.assertEqual(diff["changed_bytes"], 0)
        self.assertEqual(diff["ranges"], [])

    def test_cli_file_errors_stay_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "pattern.bin"
            good.write_bytes(pattern_blob())
            short = Path(directory) / "short.bin"
            short.write_bytes(b"\x00" * 10)
            missing = Path(directory) / "missing.bin"

            code, out, err = run_cli(["inspect-pattern", "128", "--file", str(good)])
            self.assert_error(code, out, err, "pattern slot must be 0..127")
            code, out, err = run_cli(["inspect-pattern", "-1", "--file", str(good)])
            self.assert_error(code, out, err, "pattern slot must be 0..127")
            code, out, err = run_cli(["inspect-pattern", "0", "--file", str(missing)])
            self.assert_error(code, out, err, missing.name)
            code, out, err = run_cli(["inspect-pattern", "0", "--file", str(short)])
            self.assert_error(code, out, err, "expected 24504")
            code, out, err = run_cli(["diff-pattern", str(short), str(good)])
            self.assert_error(code, out, err, "expected 24504")
            code, out, err = run_cli(["diff-pattern", str(good), str(missing)])
            self.assert_error(code, out, err, missing.name)


if __name__ == "__main__":
    unittest.main()
