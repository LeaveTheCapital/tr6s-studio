"""
Layer 2 — TR-6S kit blob. The name, raw reverb offsets, all six tune
positions, BD Decay, BD Pan, and BD Reverb Send have been checked on hardware.
Other field offsets below
are TR-8S research and remain disabled until differential captures confirm them.

    0..15         name
    388 + i*52    instrument record, i = 0..5 in TR-6S track order
      +0..1 tone   +2 tune   +3 decay   +4 level (READ-ONLY)
      +6 pan       +7 reverb +8 delay   +11 lfo
      +28..+41     envelope/gain fields a SAMPLE tone needs (gain at +37)

Two hard-won rules, both in docs/PROTOCOL.md:

  * `level` cannot be written -- the device overwrites it with the physical
    fader position on every save.
  * Writing a SAMPLE tone id is not enough. A sample needs the envelope/gain
    fields in +28..+41, and a blank "----" slot has them all at zero, which
    makes the tone play almost inaudibly. Inherit a working record first.
    (These are not *exclusively* sample fields: measured across 839 records on
    this device, ACB instruments populate them ~43% of the time and samples
    ~95%. See SAMPLE_PARAM_OFFSETS.)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

TRACKS = ["BD", "SD", "LT", "HC", "CH", "OH"]

SIZE = 1312
REVERB_TIME_RAW_OFFSET = 69  # confirmed by a one-step panel change on kit slot 1
REVERB_LEVEL_RAW_OFFSET = 70  # confirmed by a one-step panel change on kit slot 1
BD_TUNE_RAW_OFFSET = 390  # confirmed by a one-step panel change on kit slot 1
SD_TUNE_RAW_OFFSET = 442  # confirmed by a one-step panel change on kit slot 1
LT_TUNE_RAW_OFFSET = 494  # confirmed by a one-step panel change on kit slot 1
HC_TUNE_RAW_OFFSET = 546  # confirms compact track index 3, not TR-8S index 6
CH_TUNE_RAW_OFFSET = 598  # confirmed by a one-step panel change on kit slot 1
OH_TUNE_RAW_OFFSET = 650  # confirms compact track index 5, not TR-8S index 8
BD_DECAY_RAW_OFFSET = 391  # confirmed by a one-step panel change on kit slot 1
BD_PAN_RAW_OFFSET = 394  # confirmed by a one-step right pan change on kit slot 1
BD_REVERB_SEND_RAW_OFFSET = 395  # confirmed by a one-step panel change on kit slot 1
TUNE_RAW_OFFSETS = dict(zip(TRACKS, (
    BD_TUNE_RAW_OFFSET, SD_TUNE_RAW_OFFSET, LT_TUNE_RAW_OFFSET,
    HC_TUNE_RAW_OFFSET, CH_TUNE_RAW_OFFSET, OH_TUNE_RAW_OFFSET,
)))
VERIFIED_RAW_OFFSETS = {
    REVERB_TIME_RAW_OFFSET: "reverb_time_raw",
    REVERB_LEVEL_RAW_OFFSET: "reverb_level_raw",
    BD_DECAY_RAW_OFFSET: "BD_decay_raw",
    BD_PAN_RAW_OFFSET: "BD_pan_raw",
    BD_REVERB_SEND_RAW_OFFSET: "BD_reverb_send_raw",
    **{offset: f"{track}_tune_raw" for track, offset in TUNE_RAW_OFFSETS.items()},
}
REC_BASE = 388
REC_STRIDE = 52
# Bytes carrying a sample's envelope and gain. Measured across 669 ACB and 170
# sample records from this device: none of these is exclusively a sample field
# (ACB records populate them ~43% of the time) but a SAMPLE record has them set
# ~95% of the time, and a blank "----" slot has them all at zero. So this is a
# majority vote, not a clean predicate -- it exists to catch the blank-record
# case that makes an assigned sample tone near-silent.
SAMPLE_PARAM_OFFSETS = (29, 30, 33, 35, 37, 40)
SAMPLE_PARAMS = slice(28, 42)          # copied wholesale when inheriting

FIELDS = {
    "tone": (0, 2, False),
    "tune": (2, 1, True),
    "decay": (3, 1, False),
    "level": (4, 1, False),
    "pan": (6, 1, True),
    "reverb": (7, 1, False),
    "delay": (8, 1, False),
    "lfo": (11, 1, False),
}
READONLY = {"level"}

# Per-instrument fader colour: eleven consecutive bytes in the kit header, one
# per instrument in TRACKS order, values 0..11.
#
# **[I]** Identified statistically, not by watching the machine. Across 128
# factory kits these eleven bytes are the only run of exactly eleven with a
# small shared palette, they vary per kit, and an *empty* kit carries the
# default [0,1,3,3,3,1,1,2,2,2,2] -- which groups by category (kick, snare,
# toms, rimshot/clap, hats and cymbals), the shape a factory colour scheme
# has. What each index looks like has NOT been confirmed against the panel;
# see COLOUR_NAMES.
COLOR_BASE = 42
COLOR_COUNT = 12

# **[U]** The palette itself is a guess, fitted to the default scheme above and
# to product photography. Treat the names as labels for indices, not as facts
# about the LEDs.
COLOUR_NAMES = ["red", "orange", "yellow", "green", "teal", "cyan",
                "blue", "indigo", "violet", "magenta", "pink", "white"]


class KitError(ValueError):
    pass


@dataclass
class Kit:
    raw: bytearray = field(repr=False)

    def __post_init__(self):
        if len(self.raw) != SIZE:
            raise KitError(f"kit blob is {len(self.raw)} bytes, expected {SIZE}")
        self.raw = bytearray(self.raw)

    @classmethod
    def from_bytes(cls, blob: bytes) -> "Kit":
        return cls(bytearray(blob))

    def to_bytes(self) -> bytes:
        return bytes(self.raw)

    def copy(self) -> "Kit":
        return Kit(bytearray(self.raw))

    @staticmethod
    def record_offset(inst: str) -> int:
        raise KitError("TR-6S instrument blob offsets are not verified")
        if inst not in TRACKS:
            raise KitError(f"unknown instrument {inst!r}; expected one of {TRACKS}")
        return REC_BASE + TRACKS.index(inst) * REC_STRIDE

    @property
    def name(self) -> str:
        return bytes(self.raw[0:16]).decode("ascii", "replace").rstrip()

    @name.setter
    def name(self, value: str):
        self.raw[0:16] = value[:16].ljust(16).encode("ascii", "replace")

    @property
    def reverb_time_raw(self) -> int:
        """Kit reverb time's stored byte; display mapping is not yet established."""
        return self.raw[REVERB_TIME_RAW_OFFSET]

    @property
    def reverb_level_raw(self) -> int:
        """Kit reverb level's stored byte; display mapping is not yet established."""
        return self.raw[REVERB_LEVEL_RAW_OFFSET]

    @property
    def bd_tune_raw(self) -> int:
        """BD Tune's stored byte; TR-6S signed/display mapping is unverified."""
        return self.raw[BD_TUNE_RAW_OFFSET]

    @property
    def sd_tune_raw(self) -> int:
        """SD Tune's stored byte; TR-6S signed/display mapping is unverified."""
        return self.raw[SD_TUNE_RAW_OFFSET]

    @property
    def lt_tune_raw(self) -> int:
        """LT Tune's stored byte; TR-6S signed/display mapping is unverified."""
        return self.raw[LT_TUNE_RAW_OFFSET]

    @property
    def hc_tune_raw(self) -> int:
        """HC Tune's stored byte; TR-6S signed/display mapping is unverified."""
        return self.raw[HC_TUNE_RAW_OFFSET]

    @property
    def oh_tune_raw(self) -> int:
        """OH Tune's stored byte; TR-6S signed/display mapping is unverified."""
        return self.raw[OH_TUNE_RAW_OFFSET]

    @property
    def ch_tune_raw(self) -> int:
        """CH Tune's stored byte; TR-6S signed/display mapping is unverified."""
        return self.raw[CH_TUNE_RAW_OFFSET]

    def tune_raw(self, inst: str) -> int:
        """Read a verified track's raw tune byte in compact TR-6S order."""
        try:
            return self.raw[TUNE_RAW_OFFSETS[inst]]
        except KeyError as error:
            raise KitError(f"unknown TR-6S track {inst!r}") from error

    @property
    def bd_decay_raw(self) -> int:
        """BD Decay's stored byte; display mapping is not yet established."""
        return self.raw[BD_DECAY_RAW_OFFSET]

    @property
    def bd_pan_raw(self) -> int:
        """BD Pan's stored byte; 0x80 is the tested centre position."""
        return self.raw[BD_PAN_RAW_OFFSET]

    @property
    def bd_reverb_send_raw(self) -> int:
        """BD Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[BD_REVERB_SEND_RAW_OFFSET]

    def candidate_record(self, inst: str) -> dict:
        """Inspect raw fields at TR-8S record offsets in compact TR-6S order.

        Only `tune_raw` has a confirmed TR-6S field offset. The other labels
        are candidates and must not be used to construct a device write.
        """
        if inst not in TRACKS:
            raise KitError(f"unknown TR-6S track {inst!r}")
        base = REC_BASE + TRACKS.index(inst) * REC_STRIDE
        record = {
            "record_offset": base,
            "tone_id_candidate": struct.unpack_from("<H", self.raw, base)[0],
            "tune_raw_verified": self.tune_raw(inst),
            "level_raw_candidate": self.raw[base + 4],
            "delay_send_raw_candidate": self.raw[base + 8],
            "lfo_raw_candidate": self.raw[base + 11],
        }
        record["decay_raw_verified" if inst == "BD" else "decay_raw_candidate"] = self.raw[base + 3]
        record["pan_raw_verified" if inst == "BD" else "pan_raw_candidate"] = self.raw[base + 6]
        record["reverb_send_raw_verified" if inst == "BD" else "reverb_send_raw_candidate"] = self.raw[base + 7]
        return record

    def inspect(self) -> dict:
        """Return verified reads and separately labelled bulk-layout candidates."""
        return {
            "verified": {
                "name": self.name,
                "reverb_time_raw": self.reverb_time_raw,
                "reverb_level_raw": self.reverb_level_raw,
                "bd_decay_raw": self.bd_decay_raw,
                "bd_pan_raw": self.bd_pan_raw,
                "bd_reverb_send_raw": self.bd_reverb_send_raw,
                "tune_raw_by_track": {inst: self.tune_raw(inst) for inst in TRACKS},
            },
            "candidates": {
                "source": "TR-8S bulk field offsets in confirmed compact TR-6S records",
                "tracks": {inst: self.candidate_record(inst) for inst in TRACKS},
            },
        }

    def diff(self, other: "Kit") -> list[dict]:
        """Compare kit bytes, labelling verified and candidate field positions."""
        candidate_offsets = {}
        candidate_fields = {
            0: "tone_id_low", 1: "tone_id_high", 3: "decay_raw",
            4: "level_raw", 6: "pan_raw", 7: "reverb_send_raw",
            8: "delay_send_raw", 11: "lfo_raw",
        }
        for index, track in enumerate(TRACKS):
            base = REC_BASE + index * REC_STRIDE
            for delta, field_name in candidate_fields.items():
                candidate_offsets[base + delta] = f"{track}_{field_name}"
        return [
            {"offset": offset, "before": before, "after": after,
             "verified_field": VERIFIED_RAW_OFFSETS.get(offset),
             "candidate_field": (None if offset in VERIFIED_RAW_OFFSETS
                                 else candidate_offsets.get(offset))}
            for offset, (before, after) in enumerate(zip(self.raw, other.raw))
            if before != after
        ]

    # -------------------------------------------------------------- fields

    def get(self, inst: str, field_name: str) -> int:
        off, size, signed = FIELDS[field_name]
        o = self.record_offset(inst) + off
        if size == 2:
            return struct.unpack_from("<H", self.raw, o)[0]
        v = self.raw[o]
        return v - 128 if signed else v

    def set(self, inst: str, field_name: str, value: int):
        if field_name in READONLY:
            raise KitError(
                f"'{field_name}' is device-controlled (the physical fader) and "
                f"cannot be written from software"
            )
        off, size, signed = FIELDS[field_name]
        o = self.record_offset(inst) + off
        if size == 2:
            struct.pack_into("<H", self.raw, o, value & 0xFFFF)
            return
        if signed:
            if not -128 <= value <= 127:
                raise KitError(f"{field_name} must be -128..127")
            value += 128
        elif not 0 <= value <= 255:
            raise KitError(f"{field_name} must be 0..255")
        self.raw[o] = value & 0xFF

    def color(self, inst: str) -> int:
        """The instrument's fader colour index, 0..11. See COLOR_BASE."""
        raise KitError("TR-6S colour blob offsets are not verified")
        return self.raw[COLOR_BASE + TRACKS.index(inst)]

    def set_color(self, inst: str, index: int):
        raise KitError("TR-6S colour blob offsets are not verified")
        if not 0 <= int(index) < COLOR_COUNT:
            raise KitError(f"colour must be 0..{COLOR_COUNT - 1}")
        self.raw[COLOR_BASE + TRACKS.index(inst)] = int(index)

    def colors(self) -> dict:
        return {i: self.color(i) for i in TRACKS}

    def has_sample_params(self, inst: str, minimum: int = 4) -> bool:
        """
        Whether this record looks equipped to host a SAMPLE tone.

        Heuristic by necessity -- see SAMPLE_PARAM_OFFSETS. A blank slot scores
        zero, a real sample instrument scores six.
        """
        o = self.record_offset(inst)
        return sum(1 for d in SAMPLE_PARAM_OFFSETS if self.raw[o + d]) >= minimum

    def inherit_record(self, inst: str, donor: "Kit", donor_inst: str):
        """
        Copy a whole 52-byte instrument record from a donor.

        Use this before assigning a SAMPLE tone to an instrument whose record
        currently holds ACB defaults, or the tone will be near-silent.
        """
        if not donor.has_sample_params(donor_inst):
            raise KitError(
                f"donor {donor.name!r}/{donor_inst} has empty sample parameters; "
                f"copying it would produce a silent tone"
            )
        d = donor.record_offset(donor_inst)
        o = self.record_offset(inst)
        self.raw[o:o + REC_STRIDE] = donor.raw[d:d + REC_STRIDE]

    def describe(self) -> dict:
        return {"name": self.name, "reverb_time_raw": self.reverb_time_raw,
                "reverb_level_raw": self.reverb_level_raw,
                "bd_tune_raw": self.bd_tune_raw,
                "sd_tune_raw": self.sd_tune_raw,
                "lt_tune_raw": self.lt_tune_raw,
                "hc_tune_raw": self.hc_tune_raw,
                "ch_tune_raw": self.ch_tune_raw,
                "oh_tune_raw": self.oh_tune_raw,
                "instruments_unmapped": True}
