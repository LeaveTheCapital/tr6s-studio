"""Offline coverage for TR-6S kit inspection, kit diffs, and their CLI commands.

Synthetic 1,312-byte blobs stand in for hardware captures. Verified offsets are
the panel-checked raw bytes (reverb time/level, six tune positions, and BD
decay/pan/reverb send/delay send). Candidate labels are the TR-8S field layout
applied to those compact records. diff() leaves candidate_field empty when the
changed offset is already verified.
"""

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tr6s.cli import main
from tr6s.kit import SIZE, VERIFIED_RAW_OFFSETS, Kit, KitError


# Diff labels published by VERIFIED_RAW_OFFSETS. Track prefixes stay uppercase.
EXPECTED_VERIFIED = {
    69: "reverb_time_raw",
    70: "reverb_level_raw",
    390: "BD_tune_raw",
    391: "BD_decay_raw",
    394: "BD_pan_raw",
    395: "BD_reverb_send_raw",
    396: "BD_delay_send_raw",
    442: "SD_tune_raw",
    494: "LT_tune_raw",
    546: "HC_tune_raw",
    598: "CH_tune_raw",
    650: "OH_tune_raw",
}

# inspect() paths that move when only that verified byte is incremented.
# BD decay/pan/sends share their record offsets with the candidate layout, so
# both the verified summary and the BD candidate record must follow the byte,
# under verified key names.
INSPECT_PATHS = {
    69: (("verified", "reverb_time_raw"),),
    70: (("verified", "reverb_level_raw"),),
    390: (
        ("verified", "tune_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "tune_raw_verified"),
    ),
    391: (
        ("verified", "bd_decay_raw"),
        ("candidates", "tracks", "BD", "decay_raw_verified"),
    ),
    394: (
        ("verified", "bd_pan_raw"),
        ("candidates", "tracks", "BD", "pan_raw_verified"),
    ),
    395: (
        ("verified", "bd_reverb_send_raw"),
        ("candidates", "tracks", "BD", "reverb_send_raw_verified"),
    ),
    396: (
        ("verified", "bd_delay_send_raw"),
        ("candidates", "tracks", "BD", "delay_send_raw_verified"),
    ),
    442: (
        ("verified", "tune_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "tune_raw_verified"),
    ),
    494: (
        ("verified", "tune_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "tune_raw_verified"),
    ),
    546: (
        ("verified", "tune_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "tune_raw_verified"),
    ),
    598: (
        ("verified", "tune_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "tune_raw_verified"),
    ),
    650: (
        ("verified", "tune_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "tune_raw_verified"),
    ),
}

# Relative candidate bytes inside each 52-byte record. Tune is +2 and is not a
# candidate diff slot. The third column is the inspect() key on a non-verified track.
CANDIDATE_FIELDS = (
    (0, "tone_id_low", "tone_id_candidate"),
    (1, "tone_id_high", "tone_id_candidate"),
    (3, "decay_raw", "decay_raw_candidate"),
    (4, "level_raw", "level_raw_candidate"),
    (6, "pan_raw", "pan_raw_candidate"),
    (7, "reverb_send_raw", "reverb_send_raw_candidate"),
    (8, "delay_send_raw", "delay_send_raw_candidate"),
    (11, "lfo_raw", "lfo_raw_candidate"),
)

TRACK_BASES = {
    "BD": 388,
    "SD": 440,
    "LT": 492,
    "HC": 544,
    "CH": 596,
    "OH": 648,
}

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def kit_blob() -> bytes:
    """A 1,312-byte kit with the documented raw values and distinct candidate bytes."""
    raw = bytearray(SIZE)
    raw[0:16] = b"SLOT ONE".ljust(16)
    raw[69] = 0x08  # reverb time
    raw[70] = 0x00  # reverb level
    raw[388] = 0x34  # BD tone id, little-endian 0x1234
    raw[389] = 0x12
    raw[390] = 0x7C  # BD tune
    raw[391] = 0x00  # BD decay
    raw[392] = 0x64  # BD level candidate
    raw[394] = 0x80  # BD pan
    raw[395] = 0x00  # BD reverb send
    raw[396] = 0x00  # BD delay send
    raw[399] = 0x03  # BD lfo candidate

    def fill(base, tone_low, tone_high, decay, level, pan, reverb, delay, lfo):
        raw[base] = tone_low
        raw[base + 1] = tone_high
        raw[base + 3] = decay
        raw[base + 4] = level
        raw[base + 6] = pan
        raw[base + 7] = reverb
        raw[base + 8] = delay
        raw[base + 11] = lfo

    fill(440, 0x11, 0x21, 0x31, 0x41, 0x51, 0x61, 0x71, 0x06)
    raw[442] = 0x80  # SD tune
    fill(492, 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x07)
    raw[494] = 0x80  # LT tune
    fill(544, 0x13, 0x23, 0x33, 0x43, 0x53, 0x63, 0x73, 0x08)
    raw[546] = 0x80  # HC tune
    fill(596, 0x14, 0x24, 0x34, 0x44, 0x54, 0x64, 0x74, 0x09)
    raw[598] = 0x7B  # CH tune
    fill(648, 0x15, 0x25, 0x35, 0x45, 0x55, 0x65, 0x75, 0x0A)
    raw[650] = 0x80  # OH tune
    return bytes(raw)


def expected_report() -> dict:
    def record(base, tone, tune, decay, level, pan, reverb, delay, lfo, *, verified_motion):
        motion = "verified" if verified_motion else "candidate"
        return {
            "record_offset": base,
            "tone_id_candidate": tone,
            "tune_raw_verified": tune,
            "level_raw_candidate": level,
            "lfo_raw_candidate": lfo,
            f"decay_raw_{motion}": decay,
            f"pan_raw_{motion}": pan,
            f"reverb_send_raw_{motion}": reverb,
            f"delay_send_raw_{motion}": delay,
        }

    return {
        "verified": {
            "name": "SLOT ONE",
            "reverb_time_raw": 0x08,
            "reverb_level_raw": 0x00,
            "bd_decay_raw": 0x00,
            "bd_pan_raw": 0x80,
            "bd_reverb_send_raw": 0x00,
            "bd_delay_send_raw": 0x00,
            "tune_raw_by_track": {
                "BD": 0x7C,
                "SD": 0x80,
                "LT": 0x80,
                "HC": 0x80,
                "CH": 0x7B,
                "OH": 0x80,
            },
        },
        "candidates": {
            "source": "TR-8S bulk field offsets in confirmed compact TR-6S records",
            "tracks": {
                "BD": record(388, 0x1234, 0x7C, 0x00, 0x64, 0x80, 0x00, 0x00, 0x03,
                             verified_motion=True),
                "SD": record(440, 0x2111, 0x80, 0x31, 0x41, 0x51, 0x61, 0x71, 0x06,
                             verified_motion=False),
                "LT": record(492, 0x2212, 0x80, 0x32, 0x42, 0x52, 0x62, 0x72, 0x07,
                             verified_motion=False),
                "HC": record(544, 0x2313, 0x80, 0x33, 0x43, 0x53, 0x63, 0x73, 0x08,
                             verified_motion=False),
                "CH": record(596, 0x2414, 0x7B, 0x34, 0x44, 0x54, 0x64, 0x74, 0x09,
                             verified_motion=False),
                "OH": record(648, 0x2515, 0x80, 0x35, 0x45, 0x55, 0x65, 0x75, 0x0A,
                             verified_motion=False),
            },
        },
    }


def flip(blob: bytes, offset: int) -> tuple[Kit, int]:
    raw = bytearray(blob)
    updated = (raw[offset] + 1) & 0xFF
    raw[offset] = updated
    return Kit.from_bytes(raw), updated


def changed_paths(before, after, prefix=()):
    if isinstance(before, dict) and isinstance(after, dict):
        paths = []
        for key in before.keys() | after.keys():
            if key not in before or key not in after:
                paths.append(prefix + (key,))
                continue
            paths.extend(changed_paths(before[key], after[key], prefix + (key,)))
        return paths
    if before != after:
        return [prefix]
    return []


def dig(value, path):
    for key in path:
        value = value[key]
    return value


def run_cli(argv):
    """Run the CLI in-process. Opening the sequencer transport fails the test."""
    stdout, stderr = StringIO(), StringIO()
    with patch("tr6s.cli.SequencerTransport", side_effect=AssertionError("MIDI transport opened")):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class KitInspectTests(unittest.TestCase):
    def test_verified_offset_map_matches_panel_captures(self):
        self.assertEqual(SIZE, 1312)
        self.assertEqual(len(kit_blob()), 1312)
        self.assertEqual(VERIFIED_RAW_OFFSETS, EXPECTED_VERIFIED)
        self.assertEqual(set(INSPECT_PATHS), set(EXPECTED_VERIFIED))
        self.assertEqual(
            list(TRACK_BASES.values()),
            [388 + index * 52 for index in range(6)],
        )

    def test_inspect_splits_verified_reads_from_candidate_labels(self):
        report = Kit.from_bytes(kit_blob()).inspect()
        self.assertEqual(report, expected_report())

        bd = report["candidates"]["tracks"]["BD"]
        sd = report["candidates"]["tracks"]["SD"]
        oh = report["candidates"]["tracks"]["OH"]
        self.assertIn("decay_raw_verified", bd)
        self.assertIn("pan_raw_verified", bd)
        self.assertIn("reverb_send_raw_verified", bd)
        self.assertIn("delay_send_raw_verified", bd)
        self.assertNotIn("decay_raw_candidate", bd)
        self.assertNotIn("pan_raw_candidate", bd)
        self.assertNotIn("reverb_send_raw_candidate", bd)
        self.assertNotIn("delay_send_raw_candidate", bd)
        for record in (sd, oh):
            self.assertIn("decay_raw_candidate", record)
            self.assertIn("pan_raw_candidate", record)
            self.assertIn("reverb_send_raw_candidate", record)
            self.assertIn("delay_send_raw_candidate", record)
            self.assertNotIn("decay_raw_verified", record)
            self.assertNotIn("pan_raw_verified", record)
            self.assertNotIn("reverb_send_raw_verified", record)
            self.assertNotIn("delay_send_raw_verified", record)
        for record in (bd, sd, oh):
            self.assertIn("tune_raw_verified", record)
            self.assertIn("tone_id_candidate", record)
            self.assertIn("level_raw_candidate", record)
            self.assertIn("lfo_raw_candidate", record)
            self.assertNotIn("tune_raw_candidate", record)

    def test_inspect_and_diff_follow_one_verified_byte(self):
        blob = kit_blob()
        kit = Kit.from_bytes(blob)
        before = kit.inspect()
        for offset, label in EXPECTED_VERIFIED.items():
            with self.subTest(offset=offset, field=label):
                changed, updated = flip(blob, offset)
                after = changed.inspect()
                paths = INSPECT_PATHS[offset]
                self.assertEqual(set(changed_paths(before, after)), set(paths))
                for path in paths:
                    self.assertEqual(dig(after, path), updated)
                    self.assertNotEqual(dig(before, path), updated)
                self.assertEqual(kit.diff(changed), [{
                    "offset": offset,
                    "before": blob[offset],
                    "after": updated,
                    "verified_field": label,
                    "candidate_field": None,
                }])

    def test_diff_labels_candidate_only_offsets(self):
        blob = kit_blob()
        kit = Kit.from_bytes(blob)
        before = kit.inspect()
        seen = 0
        for track, base in TRACK_BASES.items():
            for delta, field_name, inspect_key in CANDIDATE_FIELDS:
                offset = base + delta
                if offset in EXPECTED_VERIFIED:
                    continue
                seen += 1
                with self.subTest(track=track, field=field_name, offset=offset):
                    changed, updated = flip(blob, offset)
                    self.assertEqual(kit.diff(changed), [{
                        "offset": offset,
                        "before": blob[offset],
                        "after": updated,
                        "verified_field": None,
                        "candidate_field": f"{track}_{field_name}",
                    }])
                    after = changed.inspect()
                    self.assertEqual(after["verified"], before["verified"])
                    path = ("candidates", "tracks", track, inspect_key)
                    self.assertEqual(set(changed_paths(before, after)), {path})
                    if field_name == "tone_id_low":
                        self.assertEqual(dig(after, path) & 0xFF, updated)
                        self.assertEqual(dig(after, path) >> 8, dig(before, path) >> 8)
                    elif field_name == "tone_id_high":
                        self.assertEqual(dig(after, path) >> 8, updated)
                        self.assertEqual(dig(after, path) & 0xFF, dig(before, path) & 0xFF)
                    else:
                        self.assertEqual(dig(after, path), updated)
        # Six tracks, eight candidate slots, minus BD decay/pan/reverb/delay.
        self.assertEqual(seen, 6 * len(CANDIDATE_FIELDS) - 4)

    def test_diff_leaves_unmapped_bytes_unlabelled(self):
        blob = kit_blob()
        kit = Kit.from_bytes(blob)
        before = kit.inspect()

        changed, updated = flip(blob, 0)
        self.assertEqual(changed.inspect()["verified"]["name"], "TLOT ONE")
        self.assertEqual(changed.inspect()["candidates"], before["candidates"])
        self.assertEqual(kit.diff(changed), [{
            "offset": 0,
            "before": blob[0],
            "after": updated,
            "verified_field": None,
            "candidate_field": None,
        }])

        # 71 sits just after reverb level. 393 is the unmapped gap between BD
        # level and BD pan. 1311 is the last byte of the blob.
        for offset in (71, 393, 1311):
            with self.subTest(offset=offset):
                changed, updated = flip(blob, offset)
                self.assertEqual(changed.inspect(), before)
                self.assertEqual(kit.diff(changed), [{
                    "offset": offset,
                    "before": blob[offset],
                    "after": updated,
                    "verified_field": None,
                    "candidate_field": None,
                }])

    def test_diff_reports_changes_in_offset_order(self):
        original = kit_blob()
        mutated = bytearray(original)
        # Apply out of address order; the diff follows offsets, not edit order.
        for offset in (650, 71, 443):
            mutated[offset] = (mutated[offset] + 1) & 0xFF
        rows = Kit.from_bytes(original).diff(Kit.from_bytes(mutated))
        self.assertEqual(rows, [
            {
                "offset": 71,
                "before": original[71],
                "after": mutated[71],
                "verified_field": None,
                "candidate_field": None,
            },
            {
                "offset": 443,
                "before": original[443],
                "after": mutated[443],
                "verified_field": None,
                "candidate_field": "SD_decay_raw",
            },
            {
                "offset": 650,
                "before": original[650],
                "after": mutated[650],
                "verified_field": "OH_tune_raw",
                "candidate_field": None,
            },
        ])
        reversed_rows = Kit.from_bytes(mutated).diff(Kit.from_bytes(original))
        self.assertEqual(
            [(row["offset"], row["before"], row["after"]) for row in reversed_rows],
            [(row["offset"], row["after"], row["before"]) for row in rows],
        )

    def test_diff_of_identical_kits_is_empty(self):
        kit = Kit.from_bytes(kit_blob())
        snapshot = bytes(kit.raw)
        self.assertEqual(kit.diff(kit), [])
        self.assertEqual(kit.diff(kit.copy()), [])
        self.assertEqual(bytes(kit.raw), snapshot)

    def test_rejects_kit_blobs_other_than_1312_bytes(self):
        for length in (0, 1311, 1313, 24504):
            with self.subTest(length=length):
                with self.assertRaisesRegex(KitError, f"{length} bytes, expected 1312"):
                    Kit.from_bytes(bytes(length))


class KitInspectCliTests(unittest.TestCase):
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

    def test_inspect_kit_file_matches_library_inspect(self):
        blob = kit_blob()
        library = Kit.from_bytes(blob).inspect()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kit.bin"
            path.write_bytes(blob)
            for slot in (0, 1, 127):
                with self.subTest(slot=slot):
                    code, out, err = run_cli(
                        ["inspect-kit", str(slot), "--file", str(path)]
                    )
                    report = self.assert_success(code, out, err)
                    self.assertEqual(report, {
                        "slot": slot,
                        "source": str(path),
                        **library,
                    })

    def test_diff_kit_matches_library_diff(self):
        before_blob = kit_blob()
        after_blob = bytearray(before_blob)
        after_blob[69] = (after_blob[69] + 1) & 0xFF    # verified reverb time
        after_blob[443] = (after_blob[443] + 1) & 0xFF  # candidate SD decay
        after_blob[71] = (after_blob[71] + 1) & 0xFF    # unmapped
        after_blob = bytes(after_blob)
        library = Kit.from_bytes(before_blob).diff(Kit.from_bytes(after_blob))
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.bin"
            after = Path(directory) / "after.bin"
            before.write_bytes(before_blob)
            after.write_bytes(after_blob)
            code, out, err = run_cli(["diff-kit", str(before), str(after)])
            report = self.assert_success(code, out, err)
        self.assertEqual(report, {
            "before": str(before),
            "after": str(after),
            "changed_bytes": 3,
            "changes": library,
        })
        by_offset = {row["offset"]: row for row in report["changes"]}
        self.assertEqual(by_offset[69]["verified_field"], "reverb_time_raw")
        self.assertIsNone(by_offset[69]["candidate_field"])
        self.assertIsNone(by_offset[443]["verified_field"])
        self.assertEqual(by_offset[443]["candidate_field"], "SD_decay_raw")
        self.assertIsNone(by_offset[71]["verified_field"])
        self.assertIsNone(by_offset[71]["candidate_field"])

    def test_diff_kit_identical_files_report_no_changes(self):
        blob = kit_blob()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kit.bin"
            path.write_bytes(blob)
            code, out, err = run_cli(["diff-kit", str(path), str(path)])
            report = self.assert_success(code, out, err)
        self.assertEqual(report["changed_bytes"], 0)
        self.assertEqual(report["changes"], [])

    def test_cli_file_commands_run_on_saved_fixtures(self):
        empty_path = FIXTURES / "kit_empty.bin"
        named_path = FIXTURES / "kit.bin"
        code, out, err = run_cli(["inspect-kit", "1", "--file", str(named_path)])
        named = self.assert_success(code, out, err)
        self.assertEqual(named["slot"], 1)
        self.assertEqual(named["source"], str(named_path))
        self.assertEqual(named["verified"]["name"], "TR-909")
        self.assertEqual(set(named), {"slot", "source", "verified", "candidates"})

        code, out, err = run_cli(["inspect-kit", "0", "--file", str(empty_path)])
        empty = self.assert_success(code, out, err)
        self.assertEqual(empty["verified"]["name"], "----")

        code, out, err = run_cli(["diff-kit", str(empty_path), str(named_path)])
        diff = self.assert_success(code, out, err)
        self.assertEqual(diff["before"], str(empty_path))
        self.assertEqual(diff["after"], str(named_path))
        self.assertEqual(diff["changed_bytes"], len(diff["changes"]))
        self.assertGreater(diff["changed_bytes"], 0)
        labelled = 0
        for row in diff["changes"]:
            verified = row["verified_field"]
            candidate = row["candidate_field"]
            self.assertFalse(verified and candidate)
            if row["offset"] in EXPECTED_VERIFIED:
                self.assertEqual(verified, EXPECTED_VERIFIED[row["offset"]])
                self.assertIsNone(candidate)
                labelled += 1
            else:
                self.assertIsNone(verified)
        self.assertGreater(labelled, 0)

    def test_cli_file_errors_stay_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "kit.bin"
            good.write_bytes(kit_blob())
            short = Path(directory) / "short.bin"
            short.write_bytes(b"\x00" * 10)
            missing = Path(directory) / "missing.bin"

            code, out, err = run_cli(["inspect-kit", "128", "--file", str(good)])
            self.assert_error(code, out, err, "kit slot must be 0..127")
            code, out, err = run_cli(["inspect-kit", "-1", "--file", str(good)])
            self.assert_error(code, out, err, "kit slot must be 0..127")
            code, out, err = run_cli(["inspect-kit", "1", "--file", str(missing)])
            self.assert_error(code, out, err, missing.name)
            code, out, err = run_cli(["inspect-kit", "1", "--file", str(short)])
            self.assert_error(code, out, err, "expected 1312")
            code, out, err = run_cli(["diff-kit", str(short), str(good)])
            self.assert_error(code, out, err, "expected 1312")
            code, out, err = run_cli(["diff-kit", str(good), str(missing)])
            self.assert_error(code, out, err, missing.name)


if __name__ == "__main__":
    unittest.main()
