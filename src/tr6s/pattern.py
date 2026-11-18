"""
Layer 2 — TR-6S pattern blob. Header reads are provisional; the TR-8S
variation and step layout below remains disabled pending differential capture.

Nothing in this layout has a TR-6S panel diff yet. `inspect()` and `diff()`
therefore leave `verified` empty and attach these offsets only as candidates.
Shuffle, steps, variations, and motion stay not verified.

Candidate layout, inherited from the TR-8S (docs/PROTOCOL.md):

    0..15    name             16..17  tempo (tenths of a BPM)
    18       kit (1-based)    19      scale        32  shuffle
    48       variation mask
    144 + blk*2436            variation block, blk 0..9
      +4 + track*64 + step*4  4 bytes per step
        instrument tracks 0..10 : byte 0 = velocity (TR-8S order, 11 tracks)
        motion lanes 12..22     : 0 = tune, 2 = ctrl, 3 = presence mask
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

TRACKS = ["BD", "SD", "LT", "HC", "CH", "OH"]
VARIATIONS = "ABCDEFGH"

SIZE = 24504
HEADER = 144
BLOCK = 2436
NBLOCKS = 10
TRACK_BASE = 4
TRACK_STRIDE = 64
STEP_STRIDE = 4
STEPS = 16

OFF_NAME = slice(0, 16)
OFF_TEMPO = 16
OFF_KIT = 18
OFF_SCALE = 19
OFF_SHUFFLE = 32
OFF_VARIATION_MASK = 48

# Inherited TR-8S instrument order. The TR-6S panel is BD SD LT HC CH OH;
# that compact order is not established inside a pattern blob.
CANDIDATE_TR8S_TRACKS = [
    "BD", "SD", "LT", "MT", "HT", "RS", "HC", "CH", "OH", "CC", "RC",
]
# No pattern offset has a TR-6S differential capture. Kept so a later
# promotion can fill this map without changing diff()'s row shape.
VERIFIED_RAW_OFFSETS: dict[int, str] = {}

SCALES = {"8T": 0, "16T": 1, "16": 2, "32": 3}
SCALE_NAMES = {v: k for k, v in SCALES.items()}

VELOCITY = {"X": 112, "x": 100, "o": 55}
MOTION_TUNE_LANE_BASE = 12
MASK_TUNE = 0x80
MASK_CTRL = 0x09


def _char_for(v: int) -> str:
    if v >= 112:
        return "X"
    if v >= 90:
        return "x"
    if v:
        return "o"
    return "."


class PatternError(ValueError):
    pass


def candidate_field(offset: int) -> str | None:
    """TR-8S label for one pattern byte, or None when the layout names nothing.

    These labels are hypotheses for a differential capture. They are not
    verified TR-6S fields.
    """
    if offset < 0 or offset >= SIZE:
        return None
    if offset < HEADER:
        if offset < 16:
            return "name"
        if offset in (OFF_TEMPO, OFF_TEMPO + 1):
            return "tempo"
        if offset == OFF_KIT:
            return "kit"
        if offset == OFF_SCALE:
            return "scale"
        if offset == OFF_SHUFFLE:
            return "shuffle"
        if offset == OFF_VARIATION_MASK:
            return "variation_mask"
        return None
    block, within = divmod(offset - HEADER, BLOCK)
    if within < TRACK_BASE:
        return None
    track, along = divmod(within - TRACK_BASE, TRACK_STRIDE)
    step, byte = divmod(along, STEP_STRIDE)
    if step >= STEPS or track < 0:
        return None
    variation = VARIATIONS[block] if block < len(VARIATIONS) else f"block{block}"
    if track < len(CANDIDATE_TR8S_TRACKS):
        part = ("velocity", "byte1", "byte2", "byte3")[byte]
        return f"{variation}_{CANDIDATE_TR8S_TRACKS[track]}_step{step:02d}_{part}"
    motion = track - MOTION_TUNE_LANE_BASE
    if 0 <= motion < len(CANDIDATE_TR8S_TRACKS):
        part = ("tune", "decay", "ctrl", "mask")[byte]
        return f"{variation}_{CANDIDATE_TR8S_TRACKS[motion]}_motion_step{step:02d}_{part}"
    return None


def _hex_bytes(values: list[int]) -> str:
    return " ".join(f"{value:02X}" for value in values)


@dataclass
class Pattern:
    """A TR-6S pattern blob. Header reads are provisional TR-8S candidates."""

    raw: bytearray = field(repr=False)

    def __post_init__(self):
        if len(self.raw) != SIZE:
            raise PatternError(f"pattern blob is {len(self.raw)} bytes, expected {SIZE}")
        self.raw = bytearray(self.raw)

    @classmethod
    def from_bytes(cls, blob: bytes) -> "Pattern":
        return cls(bytearray(blob))

    def to_bytes(self) -> bytes:
        return bytes(self.raw)

    def copy(self) -> "Pattern":
        return Pattern(bytearray(self.raw))

    # ------------------------------------------------------------- header

    @property
    def name(self) -> str:
        return bytes(self.raw[OFF_NAME]).decode("ascii", "replace").rstrip()

    @name.setter
    def name(self, value: str):
        self.raw[OFF_NAME] = value[:16].ljust(16).encode("ascii", "replace")

    @property
    def tempo(self) -> float:
        return struct.unpack_from("<H", self.raw, OFF_TEMPO)[0] / 10.0

    @tempo.setter
    def tempo(self, bpm: float):
        if not 40.0 <= bpm <= 300.0:
            raise PatternError(f"tempo {bpm} out of range 40..300")
        struct.pack_into("<H", self.raw, OFF_TEMPO, int(round(bpm * 10)))

    @property
    def kit(self) -> int:
        """0-based kit index (the panel shows this + 1)."""
        return self.raw[OFF_KIT] - 1

    @kit.setter
    def kit(self, index: int):
        if not 0 <= index <= 127:
            raise PatternError(f"kit index {index} out of range 0..127")
        self.raw[OFF_KIT] = index + 1

    @property
    def scale(self) -> str:
        return SCALE_NAMES.get(self.raw[OFF_SCALE], str(self.raw[OFF_SCALE]))

    @scale.setter
    def scale(self, value: str):
        if value not in SCALES:
            raise PatternError(f"scale must be one of {sorted(SCALES)}")
        self.raw[OFF_SCALE] = SCALES[value]

    @property
    def shuffle(self) -> int:
        raise PatternError("TR-6S shuffle blob offset is not verified")

    @shuffle.setter
    def shuffle(self, amount: int):
        raise PatternError("TR-6S shuffle blob offset is not verified")
        if not -128 <= amount <= 127:
            raise PatternError("shuffle must be -128..127")
        self.raw[OFF_SHUFFLE] = (amount + 128) & 0xFF

    # ------------------------------------------------------------ offsets

    @staticmethod
    def _blk(variation) -> int:
        if isinstance(variation, int):
            blk = variation
        else:
            v = str(variation).upper()
            if v not in VARIATIONS:
                raise PatternError(f"variation must be one of {VARIATIONS}")
            blk = VARIATIONS.index(v)
        if not 0 <= blk < NBLOCKS:
            raise PatternError(f"variation block {blk} out of range")
        return blk

    @classmethod
    def _step_offset(cls, blk: int, track: int, step: int) -> int:
        raise PatternError("TR-6S step blob offsets are not verified")
        return (HEADER + blk * BLOCK + TRACK_BASE
                + track * TRACK_STRIDE + step * STEP_STRIDE)

    @classmethod
    def _inst_offset(cls, blk: int, inst: str, step: int) -> int:
        if inst not in TRACKS:
            raise PatternError(f"unknown instrument {inst!r}; expected one of {TRACKS}")
        return cls._step_offset(blk, TRACKS.index(inst), step)

    @classmethod
    def _motion_offset(cls, blk: int, inst: str, step: int) -> int:
        if inst not in TRACKS:
            raise PatternError(f"unknown instrument {inst!r}")
        return cls._step_offset(blk, MOTION_TUNE_LANE_BASE + TRACKS.index(inst), step)

    # -------------------------------------------------------------- steps

    def get_steps(self, variation, inst: str) -> str:
        blk = self._blk(variation)
        return "".join(_char_for(self.raw[self._inst_offset(blk, inst, s)])
                       for s in range(STEPS))

    def set_steps(self, variation, inst: str, pattern: str):
        """`pattern` is up to 16 characters of X (accent), x, o (ghost) or . """
        blk = self._blk(variation)
        if len(pattern) > STEPS:
            raise PatternError(f"{len(pattern)} steps; a variation holds {STEPS}")
        bad = set(pattern) - set("Xxo.")
        if bad:
            raise PatternError(f"illegal step characters {sorted(bad)}; use X x o .")
        for s in range(STEPS):
            ch = pattern[s] if s < len(pattern) else "."
            self.raw[self._inst_offset(blk, inst, s)] = VELOCITY.get(ch, 0)

    def clear_variation(self, variation):
        blk = self._blk(variation)
        for track in range(len(TRACKS)):
            for s in range(STEPS):
                o = self._step_offset(blk, track, s)
                self.raw[o] = 0
        for inst in TRACKS:
            for s in range(STEPS):
                o = self._motion_offset(blk, inst, s)
                self.raw[o] = self.raw[o + 2] = self.raw[o + 3] = 0

    def variation_summary(self, variation) -> dict:
        blk = self._blk(variation)
        out = {}
        for inst in TRACKS:
            steps = self.get_steps(blk, inst)
            if steps.strip("."):
                out[inst] = steps
        return out

    # ------------------------------------------------------------- motion

    def set_motion(self, variation, inst: str, step: int,
                   tune: int | None = None, ctrl: int | None = None):
        """
        Write per-step motion. `tune` is -128..127 (fine), `ctrl` is the raw
        CTRL byte. The presence mask must be set or the step is ignored.
        """
        blk = self._blk(variation)
        o = self._motion_offset(blk, inst, step)
        mask = self.raw[o + 3]
        if tune is not None:
            if not -128 <= tune <= 127:
                raise PatternError("tune must be -128..127")
            self.raw[o] = (tune + 128) & 0xFF
            mask |= MASK_TUNE
        if ctrl is not None:
            self.raw[o + 2] = ctrl & 0xFF
            mask |= MASK_CTRL
        self.raw[o + 3] = mask

    def get_motion(self, variation, inst: str, step: int) -> dict:
        blk = self._blk(variation)
        o = self._motion_offset(blk, inst, step)
        mask = self.raw[o + 3]
        return {
            "tune": self.raw[o] - 128 if mask & MASK_TUNE else None,
            "ctrl": self.raw[o + 2] if mask & MASK_CTRL else None,
            "mask": mask,
        }

    def clear_motion(self, variation, inst: str, step: int | None = None):
        """Clear motion on one step, or on every step when `step` is None."""
        blk = self._blk(variation)
        steps = range(STEPS) if step is None else [step]
        for s in steps:
            if not 0 <= s < STEPS:
                raise PatternError(f"step {s} out of range 0..{STEPS - 1}")
            o = self._motion_offset(blk, inst, s)
            self.raw[o] = self.raw[o + 2] = self.raw[o + 3] = 0

    # --------------------------------------------------------------- info

    def describe(self) -> dict:
        return {
            "name": self.name,
            "tempo": self.tempo,
            "kit": self.kit,
            "kit_panel": self.kit + 1,
            "scale": self.scale,
            "variations_unmapped": True,
        }

    def inspect(self) -> dict:
        """Provisional header reads, with TR-8S step geometry left unverified.

        `verified` stays empty until a TR-6S differential capture promotes a
        field. Shuffle, steps, variations, and motion are not verified; their
        inherited offsets are candidates only.
        """
        tempo_raw = struct.unpack_from("<H", self.raw, OFF_TEMPO)[0]
        return {
            "verified": {},
            "candidates": {
                "source": (
                    "TR-8S pattern header and step geometry. No TR-6S "
                    "differential capture has promoted these fields."
                ),
                "header": {
                    "name": {
                        "status": "candidate",
                        "offset": 0,
                        "length": 16,
                        "value": self.name,
                    },
                    "tempo": {
                        "status": "candidate",
                        "offset": OFF_TEMPO,
                        "length": 2,
                        "raw": tempo_raw,
                        "bpm": self.tempo,
                    },
                    "kit": {
                        "status": "candidate",
                        "offset": OFF_KIT,
                        "length": 1,
                        "raw": self.raw[OFF_KIT],
                        "index": self.kit,
                        "panel": self.raw[OFF_KIT],
                    },
                    "scale": {
                        "status": "candidate",
                        "offset": OFF_SCALE,
                        "length": 1,
                        "raw": self.raw[OFF_SCALE],
                        "value": self.scale,
                    },
                },
                "not_verified": {
                    "shuffle": "not verified",
                    "steps": "not verified",
                    "variations": "not verified",
                    "motion": "not verified",
                    "shuffle_candidate": {
                        "offset": OFF_SHUFFLE,
                        "length": 1,
                        "raw": self.raw[OFF_SHUFFLE],
                        "tr8s_decoding": "offset-binary, 0x80 = 0",
                    },
                    "variation_mask_candidate": {
                        "offset": OFF_VARIATION_MASK,
                        "length": 1,
                        "raw": self.raw[OFF_VARIATION_MASK],
                        "tr8s_decoding": (
                            "bitmask of variations A-H; the TR-8S recomputes "
                            "it on write"
                        ),
                    },
                    "step_geometry": {
                        "status": "not verified",
                        "inherited_from": "TR-8S",
                        "header_bytes": HEADER,
                        "block_bytes": BLOCK,
                        "blocks": NBLOCKS,
                        "variation_blocks": "A-H = blocks 0-7",
                        "later_blocks": (
                            "blocks 8-9 are unnamed here; TR-8S research calls "
                            "them candidate fill-ins"
                        ),
                        "track_order": list(CANDIDATE_TR8S_TRACKS),
                        "track_note": (
                            "Labels use inherited TR-8S order, including MT, "
                            "HT, RS, CC, and RC. Compact TR-6S order "
                            "BD SD LT HC CH OH is not established in the blob. "
                            "Track index 11, between the instruments and the "
                            "motion lanes, has no candidate name."
                        ),
                        "step_stride": STEP_STRIDE,
                        "steps": STEPS,
                        "instrument_bytes": ["velocity", "byte1", "byte2", "byte3"],
                        "motion_lane_base": MOTION_TUNE_LANE_BASE,
                        "motion_bytes": ["tune", "decay", "ctrl", "mask"],
                        "motion_note": (
                            "Motion byte 1 is the TR-8S unidentified guess "
                            "for decay, not a checked field."
                        ),
                    },
                },
            },
        }

    def diff(self, other: "Pattern") -> list[dict]:
        """Changed ranges, labelled with verified or candidate fields.

        Consecutive changed bytes that share a label become one range, in
        offset order. A byte the layout does not name has both field names
        null. `verified_field` is null for every current candidate.
        """
        ranges: list[dict] = []
        current: dict | None = None
        for offset, (before, after) in enumerate(zip(self.raw, other.raw)):
            if before == after:
                if current is not None:
                    ranges.append(_finish_range(current))
                    current = None
                continue
            verified = VERIFIED_RAW_OFFSETS.get(offset)
            candidate = None if verified else candidate_field(offset)
            if (current is not None and current["end"] == offset
                    and current["verified_field"] == verified
                    and current["candidate_field"] == candidate):
                current["end"] = offset + 1
                current["before"].append(before)
                current["after"].append(after)
                continue
            if current is not None:
                ranges.append(_finish_range(current))
            current = {
                "offset": offset,
                "end": offset + 1,
                "before": [before],
                "after": [after],
                "verified_field": verified,
                "candidate_field": candidate,
            }
        if current is not None:
            ranges.append(_finish_range(current))
        return ranges


def _finish_range(current: dict) -> dict:
    before = current["before"]
    after = current["after"]
    return {
        "offset": current["offset"],
        "length": current["end"] - current["offset"],
        "before": before,
        "after": after,
        "before_hex": _hex_bytes(before),
        "after_hex": _hex_bytes(after),
        "verified_field": current["verified_field"],
        "candidate_field": current["candidate_field"],
    }
