"""
Layer 2 — TR-6S kit blob. The name, raw reverb offsets, all six tune
positions, decay and level on every track, and pan / reverb send /
delay send on every track have been checked on hardware.
Other field offsets below
are TR-8S research and remain disabled until differential captures confirm them.

    0..15         name
    388 + i*52    instrument record, i = 0..5 in TR-6S track order
      +0..1 tone   +2 tune   +3 decay   +4 level
      +6 pan       +7 reverb +8 delay   +11 lfo
      +28..+41     envelope/gain fields a SAMPLE tone needs (gain at +37)

Notes from hardware checks (also in docs/PROTOCOL.md and next-plan.md):

  * Native TR-6S CCs (MIDI implementation chart: tune/decay/level/CTRL) affect
    only the currently selected kit, on receive channel 10 (Pattern Ch). E16
    Lua SysEx writes are addressed to a specific kit slot and do not depend
    on which kit is selected.
  * `level` is writable with a native CC on the current kit and that byte
    survives a subsequent bulk read if the faders are not moved. Selecting a
    kit can still refresh level bytes from the physical faders. Bulk writers
    stay disabled.
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
SD_DECAY_RAW_OFFSET = 443  # native ch10 CC28 on current kit 0: 128 -> 126; CC 64 restored
LT_DECAY_RAW_OFFSET = 495  # native ch10 CC47 on current kit 0: 2 -> 0; CC 1 restored
HC_DECAY_RAW_OFFSET = 547  # native ch10 CC59 on current kit 0: 128 -> 126; CC 64 restored
CH_DECAY_RAW_OFFSET = 599  # native ch10 CC62 on current kit 0: 42 -> 40; CC 21 restored
OH_DECAY_RAW_OFFSET = 651  # native ch10 CC81 on current kit 0: 128 -> 126; CC 64 restored
BD_LEVEL_RAW_OFFSET = 392  # native ch10 CC24 on current kit 0: 0 -> 2; CC 0 restored
SD_LEVEL_RAW_OFFSET = 444  # native ch10 CC29 on current kit 0: 255 -> 252; CC 127 restored
LT_LEVEL_RAW_OFFSET = 496  # native ch10 CC48 on current kit 0: 0 -> 2; CC 0 restored
HC_LEVEL_RAW_OFFSET = 548  # native ch10 CC60 on current kit 0: 0 -> 2; CC 0 restored
CH_LEVEL_RAW_OFFSET = 600  # native ch10 CC63 on current kit 0: 208 -> 206; CC 104 restored
OH_LEVEL_RAW_OFFSET = 652  # native ch10 CC82 on current kit 0: 0 -> 2; CC 0 restored
BD_PAN_RAW_OFFSET = 394  # confirmed by a one-step right pan change on kit slot 1
BD_REVERB_SEND_RAW_OFFSET = 395  # confirmed by a one-step panel change on kit slot 1
BD_DELAY_SEND_RAW_OFFSET = 396  # confirmed by a one-step panel change on kit slot 1
SD_PAN_RAW_OFFSET = 446  # E16 ch12 CC40 value 63: 128 -> 126; value 64 restored
SD_REVERB_SEND_RAW_OFFSET = 447  # E16 ch12 CC43: 65 -> 64; exact byte restored via SysEx
SD_DELAY_SEND_RAW_OFFSET = 448  # E16 ch12 CC44 value 111: 224 -> 222; value 112 restored
LT_PAN_RAW_OFFSET = 498  # E16 ch12 CC20: 127 -> 126; exact byte restored via SysEx
LT_REVERB_SEND_RAW_OFFSET = 499  # E16 ch12 CC23 value 63: 128 -> 126; value 64 restored
LT_DELAY_SEND_RAW_OFFSET = 500  # E16 ch12 CC24 value 111: 224 -> 222; value 112 restored
HC_PAN_RAW_OFFSET = 550  # E16 ch12 CC50 value 63: 128 -> 126; value 64 restored
HC_REVERB_SEND_RAW_OFFSET = 551  # E16 ch12 CC53 value 126: 255 -> 252; value 127 restored
HC_DELAY_SEND_RAW_OFFSET = 552  # E16 ch12 CC54: 189 -> 188; exact byte restored via SysEx
CH_PAN_RAW_OFFSET = 602  # E16 ch12 CC60 value 82: 166 -> 164; value 83 restored
CH_REVERB_SEND_RAW_OFFSET = 603  # E16 ch12 CC63 value 63: 128 -> 126; value 64 restored
CH_DELAY_SEND_RAW_OFFSET = 604  # E16 ch12 CC64 value 1: 0 -> 2; value 0 restored
OH_PAN_RAW_OFFSET = 654  # E16 ch12 CC70 value 82: 166 -> 164; value 83 restored the blob
OH_REVERB_SEND_RAW_OFFSET = 655  # E16 ch12 CC73 value 63: 128 -> 126; value 64 restored
OH_DELAY_SEND_RAW_OFFSET = 656  # E16 ch12 CC74 value 111: 224 -> 222; value 112 restored
TUNE_RAW_OFFSETS = dict(zip(TRACKS, (
    BD_TUNE_RAW_OFFSET, SD_TUNE_RAW_OFFSET, LT_TUNE_RAW_OFFSET,
    HC_TUNE_RAW_OFFSET, CH_TUNE_RAW_OFFSET, OH_TUNE_RAW_OFFSET,
)))
DECAY_RAW_OFFSETS = dict(zip(TRACKS, (
    BD_DECAY_RAW_OFFSET, SD_DECAY_RAW_OFFSET, LT_DECAY_RAW_OFFSET,
    HC_DECAY_RAW_OFFSET, CH_DECAY_RAW_OFFSET, OH_DECAY_RAW_OFFSET,
)))
LEVEL_RAW_OFFSETS = dict(zip(TRACKS, (
    BD_LEVEL_RAW_OFFSET, SD_LEVEL_RAW_OFFSET, LT_LEVEL_RAW_OFFSET,
    HC_LEVEL_RAW_OFFSET, CH_LEVEL_RAW_OFFSET, OH_LEVEL_RAW_OFFSET,
)))
VERIFIED_RAW_OFFSETS = {
    REVERB_TIME_RAW_OFFSET: "reverb_time_raw",
    REVERB_LEVEL_RAW_OFFSET: "reverb_level_raw",
    BD_DECAY_RAW_OFFSET: "BD_decay_raw",
    SD_DECAY_RAW_OFFSET: "SD_decay_raw",
    LT_DECAY_RAW_OFFSET: "LT_decay_raw",
    HC_DECAY_RAW_OFFSET: "HC_decay_raw",
    CH_DECAY_RAW_OFFSET: "CH_decay_raw",
    OH_DECAY_RAW_OFFSET: "OH_decay_raw",
    BD_LEVEL_RAW_OFFSET: "BD_level_raw",
    SD_LEVEL_RAW_OFFSET: "SD_level_raw",
    LT_LEVEL_RAW_OFFSET: "LT_level_raw",
    HC_LEVEL_RAW_OFFSET: "HC_level_raw",
    CH_LEVEL_RAW_OFFSET: "CH_level_raw",
    OH_LEVEL_RAW_OFFSET: "OH_level_raw",
    BD_PAN_RAW_OFFSET: "BD_pan_raw",
    BD_REVERB_SEND_RAW_OFFSET: "BD_reverb_send_raw",
    BD_DELAY_SEND_RAW_OFFSET: "BD_delay_send_raw",
    SD_PAN_RAW_OFFSET: "SD_pan_raw",
    SD_REVERB_SEND_RAW_OFFSET: "SD_reverb_send_raw",
    SD_DELAY_SEND_RAW_OFFSET: "SD_delay_send_raw",
    LT_PAN_RAW_OFFSET: "LT_pan_raw",
    LT_REVERB_SEND_RAW_OFFSET: "LT_reverb_send_raw",
    LT_DELAY_SEND_RAW_OFFSET: "LT_delay_send_raw",
    HC_PAN_RAW_OFFSET: "HC_pan_raw",
    HC_REVERB_SEND_RAW_OFFSET: "HC_reverb_send_raw",
    HC_DELAY_SEND_RAW_OFFSET: "HC_delay_send_raw",
    CH_PAN_RAW_OFFSET: "CH_pan_raw",
    CH_REVERB_SEND_RAW_OFFSET: "CH_reverb_send_raw",
    CH_DELAY_SEND_RAW_OFFSET: "CH_delay_send_raw",
    OH_PAN_RAW_OFFSET: "OH_pan_raw",
    OH_REVERB_SEND_RAW_OFFSET: "OH_reverb_send_raw",
    OH_DELAY_SEND_RAW_OFFSET: "OH_delay_send_raw",
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

    def decay_raw(self, inst: str) -> int:
        """Read a verified track's raw decay byte in compact TR-6S order."""
        try:
            return self.raw[DECAY_RAW_OFFSETS[inst]]
        except KeyError as error:
            raise KitError(f"unknown TR-6S track {inst!r}") from error

    def level_raw(self, inst: str) -> int:
        """Read a verified track's raw level byte in compact TR-6S order."""
        try:
            return self.raw[LEVEL_RAW_OFFSETS[inst]]
        except KeyError as error:
            raise KitError(f"unknown TR-6S track {inst!r}") from error

    @property
    def sd_decay_raw(self) -> int:
        """SD Decay's stored byte; display mapping is not yet established."""
        return self.raw[SD_DECAY_RAW_OFFSET]

    @property
    def lt_decay_raw(self) -> int:
        """LT Decay's stored byte; display mapping is not yet established."""
        return self.raw[LT_DECAY_RAW_OFFSET]

    @property
    def hc_decay_raw(self) -> int:
        """HC Decay's stored byte; display mapping is not yet established."""
        return self.raw[HC_DECAY_RAW_OFFSET]

    @property
    def ch_decay_raw(self) -> int:
        """CH Decay's stored byte; display mapping is not yet established."""
        return self.raw[CH_DECAY_RAW_OFFSET]

    @property
    def oh_decay_raw(self) -> int:
        """OH Decay's stored byte; display mapping is not yet established."""
        return self.raw[OH_DECAY_RAW_OFFSET]

    @property
    def bd_level_raw(self) -> int:
        """BD Level's stored byte. Native CC can write it on the current kit."""
        return self.raw[BD_LEVEL_RAW_OFFSET]

    @property
    def sd_level_raw(self) -> int:
        """SD Level's stored byte. Native CC can write it on the current kit."""
        return self.raw[SD_LEVEL_RAW_OFFSET]

    @property
    def lt_level_raw(self) -> int:
        """LT Level's stored byte. Native CC can write it on the current kit."""
        return self.raw[LT_LEVEL_RAW_OFFSET]

    @property
    def hc_level_raw(self) -> int:
        """HC Level's stored byte. Native CC can write it on the current kit."""
        return self.raw[HC_LEVEL_RAW_OFFSET]

    @property
    def ch_level_raw(self) -> int:
        """CH Level's stored byte. Native CC can write it on the current kit."""
        return self.raw[CH_LEVEL_RAW_OFFSET]

    @property
    def oh_level_raw(self) -> int:
        """OH Level's stored byte. Native CC can write it on the current kit."""
        return self.raw[OH_LEVEL_RAW_OFFSET]

    @property
    def bd_pan_raw(self) -> int:
        """BD Pan's stored byte; 0x80 is the tested centre position."""
        return self.raw[BD_PAN_RAW_OFFSET]

    @property
    def bd_reverb_send_raw(self) -> int:
        """BD Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[BD_REVERB_SEND_RAW_OFFSET]

    @property
    def bd_delay_send_raw(self) -> int:
        """BD Delay Send's stored byte; display mapping is unverified."""
        return self.raw[BD_DELAY_SEND_RAW_OFFSET]

    @property
    def oh_pan_raw(self) -> int:
        """OH Pan's stored byte; display mapping is unverified."""
        return self.raw[OH_PAN_RAW_OFFSET]

    @property
    def oh_delay_send_raw(self) -> int:
        """OH Delay Send's stored byte; display mapping is unverified."""
        return self.raw[OH_DELAY_SEND_RAW_OFFSET]

    @property
    def oh_reverb_send_raw(self) -> int:
        """OH Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[OH_REVERB_SEND_RAW_OFFSET]

    @property
    def sd_pan_raw(self) -> int:
        """SD Pan's stored byte; display mapping is unverified."""
        return self.raw[SD_PAN_RAW_OFFSET]

    @property
    def sd_reverb_send_raw(self) -> int:
        """SD Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[SD_REVERB_SEND_RAW_OFFSET]

    @property
    def sd_delay_send_raw(self) -> int:
        """SD Delay Send's stored byte; display mapping is unverified."""
        return self.raw[SD_DELAY_SEND_RAW_OFFSET]

    @property
    def lt_pan_raw(self) -> int:
        """LT Pan's stored byte; display mapping is unverified."""
        return self.raw[LT_PAN_RAW_OFFSET]

    @property
    def lt_reverb_send_raw(self) -> int:
        """LT Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[LT_REVERB_SEND_RAW_OFFSET]

    @property
    def lt_delay_send_raw(self) -> int:
        """LT Delay Send's stored byte; display mapping is unverified."""
        return self.raw[LT_DELAY_SEND_RAW_OFFSET]

    @property
    def hc_pan_raw(self) -> int:
        """HC Pan's stored byte; display mapping is unverified."""
        return self.raw[HC_PAN_RAW_OFFSET]

    @property
    def hc_reverb_send_raw(self) -> int:
        """HC Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[HC_REVERB_SEND_RAW_OFFSET]

    @property
    def hc_delay_send_raw(self) -> int:
        """HC Delay Send's stored byte; display mapping is unverified."""
        return self.raw[HC_DELAY_SEND_RAW_OFFSET]

    @property
    def ch_pan_raw(self) -> int:
        """CH Pan's stored byte; display mapping is unverified."""
        return self.raw[CH_PAN_RAW_OFFSET]

    @property
    def ch_reverb_send_raw(self) -> int:
        """CH Reverb Send's stored byte; display mapping is unverified."""
        return self.raw[CH_REVERB_SEND_RAW_OFFSET]

    @property
    def ch_delay_send_raw(self) -> int:
        """CH Delay Send's stored byte; display mapping is unverified."""
        return self.raw[CH_DELAY_SEND_RAW_OFFSET]

    def candidate_record(self, inst: str) -> dict:
        """Inspect raw fields at TR-8S record offsets in compact TR-6S order.

        Tune, decay, level, pan, reverb send, and delay send are verified on
        every track. Tone ID and LFO stay candidates and must not be used to
        construct a device write.
        """
        if inst not in TRACKS:
            raise KitError(f"unknown TR-6S track {inst!r}")
        base = REC_BASE + TRACKS.index(inst) * REC_STRIDE
        return {
            "record_offset": base,
            "tone_id_candidate": struct.unpack_from("<H", self.raw, base)[0],
            "tune_raw_verified": self.tune_raw(inst),
            "decay_raw_verified": self.decay_raw(inst),
            "level_raw_verified": self.level_raw(inst),
            "lfo_raw_candidate": self.raw[base + 11],
            "pan_raw_verified": self.raw[base + 6],
            "reverb_send_raw_verified": self.raw[base + 7],
            "delay_send_raw_verified": self.raw[base + 8],
        }

    def inspect(self) -> dict:
        """Return verified reads and separately labelled bulk-layout candidates."""
        return {
            "verified": {
                "name": self.name,
                "reverb_time_raw": self.reverb_time_raw,
                "reverb_level_raw": self.reverb_level_raw,
                "bd_decay_raw": self.bd_decay_raw,
                "sd_decay_raw": self.sd_decay_raw,
                "lt_decay_raw": self.lt_decay_raw,
                "hc_decay_raw": self.hc_decay_raw,
                "ch_decay_raw": self.ch_decay_raw,
                "oh_decay_raw": self.oh_decay_raw,
                "bd_level_raw": self.bd_level_raw,
                "sd_level_raw": self.sd_level_raw,
                "lt_level_raw": self.lt_level_raw,
                "hc_level_raw": self.hc_level_raw,
                "ch_level_raw": self.ch_level_raw,
                "oh_level_raw": self.oh_level_raw,
                "bd_pan_raw": self.bd_pan_raw,
                "bd_reverb_send_raw": self.bd_reverb_send_raw,
                "bd_delay_send_raw": self.bd_delay_send_raw,
                "sd_pan_raw": self.sd_pan_raw,
                "sd_reverb_send_raw": self.sd_reverb_send_raw,
                "sd_delay_send_raw": self.sd_delay_send_raw,
                "lt_pan_raw": self.lt_pan_raw,
                "lt_reverb_send_raw": self.lt_reverb_send_raw,
                "lt_delay_send_raw": self.lt_delay_send_raw,
                "hc_pan_raw": self.hc_pan_raw,
                "hc_reverb_send_raw": self.hc_reverb_send_raw,
                "hc_delay_send_raw": self.hc_delay_send_raw,
                "ch_pan_raw": self.ch_pan_raw,
                "ch_reverb_send_raw": self.ch_reverb_send_raw,
                "ch_delay_send_raw": self.ch_delay_send_raw,
                "oh_pan_raw": self.oh_pan_raw,
                "oh_reverb_send_raw": self.oh_reverb_send_raw,
                "oh_delay_send_raw": self.oh_delay_send_raw,
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
