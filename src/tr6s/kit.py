"""
Layer 2 — TR-6S kit blob. The name, kit-common header fields listed in
VERIFIED_RAW_OFFSETS, all six tune positions, decay, level, gain, pan,
reverb send, delay send, LFO dest/depth, and the SysEx-mapped instrument
and Inst FX parameter bytes on every track have been checked on hardware.
Other field offsets below are TR-8S research and remain disabled until
differential captures confirm them.

    0..15         name
    16            kit level
    42..47        BD..OH fader colour (six TR-6S tracks)
    68..74        reverb type/time/level/predelay/lo-hi cut/density
    108..114      delay type/sync/level/time/feedback and high damp (114)
    128..130      delay reverb send, coarse tune (0xC9+step), fine tune
    161, 180..185 MFX switch, control assign, balance/rate/depth/res/manual
    210..214      sidechain depth/gain/pan/reverb send/delay send
    248..250      kit LFO waveform/rate/sync
    388 + i*52    instrument record, i = 0..5 in TR-6S track order
      +0..1 tone   +2 tune   +3 decay   +4 level   +5 gain
      +6 pan       +7 reverb +8 delay   +10 lfo dest  +11 lfo depth
      +28 attack/FM depth  +29 param 0x37  +30 FM decay  +31 feedback
      +33 param 0x3F  +37 FM note (not gain)  +38..+40 pitch env/attack/decay
    960 + i*32    Inst FX record; parameter 1 at +5

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
    ~95%. See SAMPLE_PARAM_OFFSETS. Instrument gain itself is record +5 /
    SysEx param 0x0A; +37 is FM note / SysEx 0x47, not gain.)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

TRACKS = ["BD", "SD", "LT", "HC", "CH", "OH"]

SIZE = 1312
REVERB_TIME_RAW_OFFSET = 69  # panel on kit 1; SysEx 10 00 01 01 nibble2 on kit 0
REVERB_LEVEL_RAW_OFFSET = 70  # panel on kit 1; SysEx 10 00 01 03 nibble2 on kit 0
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

# Live SysEx DT1 on kit slot 0, 2026-11-18: one-step change, restore, whole-blob
# match. Addresses are 10 00 <page> <param>. Width is one stored byte.
KIT_LEVEL_RAW_OFFSET = 16  # 10 00 00 10 byte1
REVERB_TYPE_RAW_OFFSET = 68  # 10 00 01 00 byte1
REVERB_PREDELAY_RAW_OFFSET = 71  # 10 00 01 05 byte1
REVERB_LO_CUT_RAW_OFFSET = 72  # 10 00 01 06 byte1
REVERB_HI_CUT_RAW_OFFSET = 73  # 10 00 01 07 byte1
REVERB_DENSITY_RAW_OFFSET = 74  # 10 00 01 08 byte1
DELAY_TYPE_RAW_OFFSET = 108  # 10 00 02 00 byte1
DELAY_SYNC_RAW_OFFSET = 109  # 10 00 02 01 byte1
DELAY_LEVEL_RAW_OFFSET = 110  # 10 00 02 02 nibble2
DELAY_TIME_RAW_OFFSET = 111  # 10 00 02 04 nibble2
DELAY_FEEDBACK_RAW_OFFSET = 112  # 10 00 02 06 nibble2
DELAY_H_DAMP_RAW_OFFSET = 114  # 10 00 02 09 byte1
DELAY_REVERB_SEND_RAW_OFFSET = 128  # 10 00 02 1C nibble2
DELAY_COARSE_TUNE_RAW_OFFSET = 129  # 10 00 02 1E; stored byte = 0xC9 + step
DELAY_FINE_TUNE_RAW_OFFSET = 130  # 10 00 02 20 fine (1..201, nibble-encoded)
MFX_SWITCH_RAW_OFFSET = 161  # 10 00 03 01 byte1
MFX_CONTROL_ASSIGN_RAW_OFFSET = 180  # 10 00 03 26 byte1
MFX_BALANCE_RAW_OFFSET = 181  # 10 00 03 27 nibble2
MFX_RATE_RAW_OFFSET = 182  # 10 00 03 29 nibble2
MFX_DEPTH_RAW_OFFSET = 183  # 10 00 03 2B nibble2
MFX_RESONANCE_RAW_OFFSET = 184  # 10 00 03 2D nibble2
MFX_MANUAL_RAW_OFFSET = 185  # 10 00 03 2F nibble2
SIDECHAIN_DEPTH_RAW_OFFSET = 210  # 10 00 04 02 nibble2
SIDECHAIN_GAIN_RAW_OFFSET = 211  # 10 00 04 04 nibble2
SIDECHAIN_PAN_RAW_OFFSET = 212  # 10 00 04 06 nibble2
SIDECHAIN_REVERB_SEND_RAW_OFFSET = 213  # 10 00 04 08 nibble2
SIDECHAIN_DELAY_SEND_RAW_OFFSET = 214  # 10 00 04 0A nibble2
KIT_LFO_WAVEFORM_RAW_OFFSET = 248  # 10 00 05 00 byte1
KIT_LFO_RATE_RAW_OFFSET = 249  # 10 00 05 01 nibble2
KIT_LFO_SYNC_RAW_OFFSET = 250  # 10 00 05 03 byte1

# Record-relative SysEx mappings, same delta on every compact track.
RECORD_FIELD_DELTAS = {
    "gain": 5,              # 1@ 0A nibble2
    "lfo_dest": 10,         # 1@ 13 byte1
    "lfo_depth": 11,        # 1@ 14 nibble2
    "attack_or_fm_depth": 28,  # 1@ 35 nibble2
    "param_37": 29,         # 1@ 37 nibble2
    "fm_decay": 30,         # 1@ 39 nibble2
    "feedback": 31,         # 1@ 3B nibble2
    "param_3f": 33,         # 1@ 3F nibble2
    "fm_note": 37,          # 1@ 47 nibble2; not instrument gain
    "pitch_env": 38,        # 1@ 49 nibble2
    "pitch_attack": 39,     # 1@ 4B nibble2
    "pitch_decay": 40,      # 1@ 4D nibble2
}


def _record_offsets(delta: int) -> dict[str, int]:
    return {track: REC_BASE + index * REC_STRIDE + delta
            for index, track in enumerate(TRACKS)}


GAIN_RAW_OFFSETS = _record_offsets(5)
LFO_DEST_RAW_OFFSETS = _record_offsets(10)
LFO_DEPTH_RAW_OFFSETS = _record_offsets(11)
ATTACK_OR_FM_DEPTH_RAW_OFFSETS = _record_offsets(28)
PARAM_37_RAW_OFFSETS = _record_offsets(29)
FM_DECAY_RAW_OFFSETS = _record_offsets(30)
FEEDBACK_RAW_OFFSETS = _record_offsets(31)
PARAM_3F_RAW_OFFSETS = _record_offsets(33)
FM_NOTE_RAW_OFFSETS = _record_offsets(37)
PITCH_ENV_RAW_OFFSETS = _record_offsets(38)
PITCH_ATTACK_RAW_OFFSETS = _record_offsets(39)
PITCH_DECAY_RAW_OFFSETS = _record_offsets(40)

# Inst FX records occupy 960..1312 as 11 x 32-byte slots (TR-8S-sized tail).
# The six TR-6S tracks are the first six: BD at 960, then SD, LT, HC, CH, OH.
INST_FX_REC_BASE = 960
INST_FX_REC_STRIDE = 32
INST_FX_PARAM1_RAW_OFFSETS = {
    track: INST_FX_REC_BASE + index * INST_FX_REC_STRIDE + 5
    for index, track in enumerate(TRACKS)
}  # 2@ 09 nibble2
COLOR_RAW_OFFSETS = {track: 42 + index for index, track in enumerate(TRACKS)}  # 00 42..47 byte1

VERIFIED_RAW_OFFSETS.update({
    KIT_LEVEL_RAW_OFFSET: "kit_level_raw",
    REVERB_TYPE_RAW_OFFSET: "reverb_type_raw",
    REVERB_PREDELAY_RAW_OFFSET: "reverb_predelay_raw",
    REVERB_LO_CUT_RAW_OFFSET: "reverb_lo_cut_raw",
    REVERB_HI_CUT_RAW_OFFSET: "reverb_hi_cut_raw",
    REVERB_DENSITY_RAW_OFFSET: "reverb_density_raw",
    DELAY_TYPE_RAW_OFFSET: "delay_type_raw",
    DELAY_SYNC_RAW_OFFSET: "delay_sync_raw",
    DELAY_LEVEL_RAW_OFFSET: "delay_level_raw",
    DELAY_TIME_RAW_OFFSET: "delay_time_raw",
    DELAY_FEEDBACK_RAW_OFFSET: "delay_feedback_raw",
    DELAY_H_DAMP_RAW_OFFSET: "delay_h_damp_raw",
    DELAY_REVERB_SEND_RAW_OFFSET: "delay_reverb_send_raw",
    DELAY_COARSE_TUNE_RAW_OFFSET: "delay_coarse_tune_raw",
    DELAY_FINE_TUNE_RAW_OFFSET: "delay_fine_tune_raw",
    MFX_SWITCH_RAW_OFFSET: "mfx_switch_raw",
    MFX_CONTROL_ASSIGN_RAW_OFFSET: "mfx_control_assign_raw",
    MFX_BALANCE_RAW_OFFSET: "mfx_balance_raw",
    MFX_RATE_RAW_OFFSET: "mfx_rate_raw",
    MFX_DEPTH_RAW_OFFSET: "mfx_depth_raw",
    MFX_RESONANCE_RAW_OFFSET: "mfx_resonance_raw",
    MFX_MANUAL_RAW_OFFSET: "mfx_manual_raw",
    SIDECHAIN_DEPTH_RAW_OFFSET: "sidechain_depth_raw",
    SIDECHAIN_GAIN_RAW_OFFSET: "sidechain_gain_raw",
    SIDECHAIN_PAN_RAW_OFFSET: "sidechain_pan_raw",
    SIDECHAIN_REVERB_SEND_RAW_OFFSET: "sidechain_reverb_send_raw",
    SIDECHAIN_DELAY_SEND_RAW_OFFSET: "sidechain_delay_send_raw",
    KIT_LFO_WAVEFORM_RAW_OFFSET: "kit_lfo_waveform_raw",
    KIT_LFO_RATE_RAW_OFFSET: "kit_lfo_rate_raw",
    KIT_LFO_SYNC_RAW_OFFSET: "kit_lfo_sync_raw",
})
for _table, _label in (
    (GAIN_RAW_OFFSETS, "gain_raw"),
    (LFO_DEST_RAW_OFFSETS, "lfo_dest_raw"),
    (LFO_DEPTH_RAW_OFFSETS, "lfo_depth_raw"),
    (ATTACK_OR_FM_DEPTH_RAW_OFFSETS, "attack_or_fm_depth_raw"),
    (PARAM_37_RAW_OFFSETS, "param_37_raw"),
    (FM_DECAY_RAW_OFFSETS, "fm_decay_raw"),
    (FEEDBACK_RAW_OFFSETS, "feedback_raw"),
    (PARAM_3F_RAW_OFFSETS, "param_3f_raw"),
    (FM_NOTE_RAW_OFFSETS, "fm_note_raw"),
    (PITCH_ENV_RAW_OFFSETS, "pitch_env_raw"),
    (PITCH_ATTACK_RAW_OFFSETS, "pitch_attack_raw"),
    (PITCH_DECAY_RAW_OFFSETS, "pitch_decay_raw"),
    (INST_FX_PARAM1_RAW_OFFSETS, "inst_fx_param1_raw"),
    (COLOR_RAW_OFFSETS, "color_raw"),
):
    VERIFIED_RAW_OFFSETS.update(
        {offset: f"{track}_{_label}" for track, offset in _table.items()}
    )

# Bytes carrying a sample's envelope and related params. Measured across 669
# ACB and 170 sample records from this device: none of these is exclusively a
# sample field (ACB records populate them ~43% of the time) but a SAMPLE record
# has them set ~95% of the time, and a blank "----" slot has them all at zero.
# So this is a majority vote, not a clean predicate -- it exists to catch the
# blank-record case that makes an assigned sample tone near-silent.
# SysEx later paired several of these deltas: +29 param 0x37, +30 FM decay,
# +33 param 0x3F, +35 unused in this list, +37 FM note (not gain), +40 pitch decay.
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

# Per-instrument fader colour. SysEx 10 00 00 42..47 (byte1) verified the six
# TR-6S track colours at offsets 42..47 (COLOR_RAW_OFFSETS). A longer
# statistically identified run still exists in the header (values 0..11);
# bytes after OH are not SysEx-checked. COLOUR_NAMES remain an unverified
# label for the index, not a fact about the LEDs. color()/set_color stay
# disabled so bulk colour writes are not exposed.
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


    def _raw_from(self, table: dict[str, int], inst: str) -> int:
        try:
            return self.raw[table[inst]]
        except KeyError as error:
            raise KitError(f"unknown TR-6S track {inst!r}") from error

    def gain_raw(self, inst: str) -> int:
        """Instrument gain (record +5 / SysEx 0x0A); display mapping unverified."""
        return self._raw_from(GAIN_RAW_OFFSETS, inst)

    def lfo_dest_raw(self, inst: str) -> int:
        """LFO destination (record +10 / SysEx 0x13, one-byte)."""
        return self._raw_from(LFO_DEST_RAW_OFFSETS, inst)

    def lfo_depth_raw(self, inst: str) -> int:
        """LFO depth (record +11 / SysEx 0x14)."""
        return self._raw_from(LFO_DEPTH_RAW_OFFSETS, inst)

    def attack_or_fm_depth_raw(self, inst: str) -> int:
        """Attack or FM depth (record +28 / SysEx 0x35)."""
        return self._raw_from(ATTACK_OR_FM_DEPTH_RAW_OFFSETS, inst)

    def param_37_raw(self, inst: str) -> int:
        """Instrument param SysEx 0x37 at record +29; display name unverified."""
        return self._raw_from(PARAM_37_RAW_OFFSETS, inst)

    def fm_decay_raw(self, inst: str) -> int:
        """FM decay (record +30 / SysEx 0x39)."""
        return self._raw_from(FM_DECAY_RAW_OFFSETS, inst)

    def feedback_raw(self, inst: str) -> int:
        """Feedback (record +31 / SysEx 0x3B)."""
        return self._raw_from(FEEDBACK_RAW_OFFSETS, inst)

    def param_3f_raw(self, inst: str) -> int:
        """Instrument param SysEx 0x3F at record +33; display name unverified."""
        return self._raw_from(PARAM_3F_RAW_OFFSETS, inst)

    def fm_note_raw(self, inst: str) -> int:
        """FM note (record +37 / SysEx 0x47). This is not instrument gain."""
        return self._raw_from(FM_NOTE_RAW_OFFSETS, inst)

    def pitch_env_raw(self, inst: str) -> int:
        """Pitch envelope (record +38 / SysEx 0x49)."""
        return self._raw_from(PITCH_ENV_RAW_OFFSETS, inst)

    def pitch_attack_raw(self, inst: str) -> int:
        """Pitch attack (record +39 / SysEx 0x4B)."""
        return self._raw_from(PITCH_ATTACK_RAW_OFFSETS, inst)

    def pitch_decay_raw(self, inst: str) -> int:
        """Pitch decay (record +40 / SysEx 0x4D)."""
        return self._raw_from(PITCH_DECAY_RAW_OFFSETS, inst)

    def inst_fx_param1_raw(self, inst: str) -> int:
        """Inst FX parameter 1 (record 960+32*track +5 / SysEx 2@ 09)."""
        return self._raw_from(INST_FX_PARAM1_RAW_OFFSETS, inst)

    def color_raw(self, inst: str) -> int:
        """Fader colour index for a TR-6S track (header 42..47 / SysEx 00 42..47)."""
        return self._raw_from(COLOR_RAW_OFFSETS, inst)

    @property
    def kit_level_raw(self) -> int:
        return self.raw[KIT_LEVEL_RAW_OFFSET]

    @property
    def reverb_type_raw(self) -> int:
        return self.raw[REVERB_TYPE_RAW_OFFSET]

    @property
    def reverb_predelay_raw(self) -> int:
        return self.raw[REVERB_PREDELAY_RAW_OFFSET]

    @property
    def reverb_lo_cut_raw(self) -> int:
        return self.raw[REVERB_LO_CUT_RAW_OFFSET]

    @property
    def reverb_hi_cut_raw(self) -> int:
        return self.raw[REVERB_HI_CUT_RAW_OFFSET]

    @property
    def reverb_density_raw(self) -> int:
        return self.raw[REVERB_DENSITY_RAW_OFFSET]

    @property
    def delay_type_raw(self) -> int:
        return self.raw[DELAY_TYPE_RAW_OFFSET]

    @property
    def delay_sync_raw(self) -> int:
        return self.raw[DELAY_SYNC_RAW_OFFSET]

    @property
    def delay_level_raw(self) -> int:
        return self.raw[DELAY_LEVEL_RAW_OFFSET]

    @property
    def delay_time_raw(self) -> int:
        return self.raw[DELAY_TIME_RAW_OFFSET]

    @property
    def delay_feedback_raw(self) -> int:
        return self.raw[DELAY_FEEDBACK_RAW_OFFSET]

    @property
    def delay_h_damp_raw(self) -> int:
        return self.raw[DELAY_H_DAMP_RAW_OFFSET]

    @property
    def delay_reverb_send_raw(self) -> int:
        return self.raw[DELAY_REVERB_SEND_RAW_OFFSET]

    @property
    def delay_coarse_tune_raw(self) -> int:
        """Delay coarse tune stored byte; value is 0xC9 plus the step."""
        return self.raw[DELAY_COARSE_TUNE_RAW_OFFSET]

    @property
    def delay_fine_tune_raw(self) -> int:
        return self.raw[DELAY_FINE_TUNE_RAW_OFFSET]

    @property
    def mfx_switch_raw(self) -> int:
        return self.raw[MFX_SWITCH_RAW_OFFSET]

    @property
    def mfx_control_assign_raw(self) -> int:
        return self.raw[MFX_CONTROL_ASSIGN_RAW_OFFSET]

    @property
    def mfx_balance_raw(self) -> int:
        return self.raw[MFX_BALANCE_RAW_OFFSET]

    @property
    def mfx_rate_raw(self) -> int:
        return self.raw[MFX_RATE_RAW_OFFSET]

    @property
    def mfx_depth_raw(self) -> int:
        return self.raw[MFX_DEPTH_RAW_OFFSET]

    @property
    def mfx_resonance_raw(self) -> int:
        return self.raw[MFX_RESONANCE_RAW_OFFSET]

    @property
    def mfx_manual_raw(self) -> int:
        return self.raw[MFX_MANUAL_RAW_OFFSET]

    @property
    def sidechain_depth_raw(self) -> int:
        return self.raw[SIDECHAIN_DEPTH_RAW_OFFSET]

    @property
    def sidechain_gain_raw(self) -> int:
        return self.raw[SIDECHAIN_GAIN_RAW_OFFSET]

    @property
    def sidechain_pan_raw(self) -> int:
        return self.raw[SIDECHAIN_PAN_RAW_OFFSET]

    @property
    def sidechain_reverb_send_raw(self) -> int:
        return self.raw[SIDECHAIN_REVERB_SEND_RAW_OFFSET]

    @property
    def sidechain_delay_send_raw(self) -> int:
        return self.raw[SIDECHAIN_DELAY_SEND_RAW_OFFSET]

    @property
    def kit_lfo_waveform_raw(self) -> int:
        return self.raw[KIT_LFO_WAVEFORM_RAW_OFFSET]

    @property
    def kit_lfo_rate_raw(self) -> int:
        return self.raw[KIT_LFO_RATE_RAW_OFFSET]

    @property
    def kit_lfo_sync_raw(self) -> int:
        return self.raw[KIT_LFO_SYNC_RAW_OFFSET]

    def candidate_record(self, inst: str) -> dict:
        """Inspect raw fields at TR-8S record offsets in compact TR-6S order.

        Tune, decay, level, gain, pan, both sends, LFO dest/depth, and the
        SysEx-mapped instrument/Inst FX parameter bytes are verified on every
        track. Tone ID stays a candidate and must not be used to construct a
        device write.
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
            "gain_raw_verified": self.gain_raw(inst),
            "lfo_dest_raw_verified": self.lfo_dest_raw(inst),
            "lfo_depth_raw_verified": self.lfo_depth_raw(inst),
            "attack_or_fm_depth_raw_verified": self.attack_or_fm_depth_raw(inst),
            "param_37_raw_verified": self.param_37_raw(inst),
            "fm_decay_raw_verified": self.fm_decay_raw(inst),
            "feedback_raw_verified": self.feedback_raw(inst),
            "param_3f_raw_verified": self.param_3f_raw(inst),
            "fm_note_raw_verified": self.fm_note_raw(inst),
            "pitch_env_raw_verified": self.pitch_env_raw(inst),
            "pitch_attack_raw_verified": self.pitch_attack_raw(inst),
            "pitch_decay_raw_verified": self.pitch_decay_raw(inst),
            "inst_fx_param1_raw_verified": self.inst_fx_param1_raw(inst),
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
                "kit_level_raw": self.kit_level_raw,
                "reverb_type_raw": self.reverb_type_raw,
                "reverb_predelay_raw": self.reverb_predelay_raw,
                "reverb_lo_cut_raw": self.reverb_lo_cut_raw,
                "reverb_hi_cut_raw": self.reverb_hi_cut_raw,
                "reverb_density_raw": self.reverb_density_raw,
                "delay_type_raw": self.delay_type_raw,
                "delay_sync_raw": self.delay_sync_raw,
                "delay_level_raw": self.delay_level_raw,
                "delay_time_raw": self.delay_time_raw,
                "delay_feedback_raw": self.delay_feedback_raw,
                "delay_h_damp_raw": self.delay_h_damp_raw,
                "delay_reverb_send_raw": self.delay_reverb_send_raw,
                "delay_coarse_tune_raw": self.delay_coarse_tune_raw,
                "delay_fine_tune_raw": self.delay_fine_tune_raw,
                "mfx_switch_raw": self.mfx_switch_raw,
                "mfx_control_assign_raw": self.mfx_control_assign_raw,
                "mfx_balance_raw": self.mfx_balance_raw,
                "mfx_rate_raw": self.mfx_rate_raw,
                "mfx_depth_raw": self.mfx_depth_raw,
                "mfx_resonance_raw": self.mfx_resonance_raw,
                "mfx_manual_raw": self.mfx_manual_raw,
                "sidechain_depth_raw": self.sidechain_depth_raw,
                "sidechain_gain_raw": self.sidechain_gain_raw,
                "sidechain_pan_raw": self.sidechain_pan_raw,
                "sidechain_reverb_send_raw": self.sidechain_reverb_send_raw,
                "sidechain_delay_send_raw": self.sidechain_delay_send_raw,
                "kit_lfo_waveform_raw": self.kit_lfo_waveform_raw,
                "kit_lfo_rate_raw": self.kit_lfo_rate_raw,
                "kit_lfo_sync_raw": self.kit_lfo_sync_raw,
                "tune_raw_by_track": {inst: self.tune_raw(inst) for inst in TRACKS},
                "gain_raw_by_track": {inst: self.gain_raw(inst) for inst in TRACKS},
                "lfo_dest_raw_by_track": {inst: self.lfo_dest_raw(inst) for inst in TRACKS},
                "lfo_depth_raw_by_track": {inst: self.lfo_depth_raw(inst) for inst in TRACKS},
                "attack_or_fm_depth_raw_by_track": {
                    inst: self.attack_or_fm_depth_raw(inst) for inst in TRACKS
                },
                "param_37_raw_by_track": {inst: self.param_37_raw(inst) for inst in TRACKS},
                "fm_decay_raw_by_track": {inst: self.fm_decay_raw(inst) for inst in TRACKS},
                "feedback_raw_by_track": {inst: self.feedback_raw(inst) for inst in TRACKS},
                "param_3f_raw_by_track": {inst: self.param_3f_raw(inst) for inst in TRACKS},
                "fm_note_raw_by_track": {inst: self.fm_note_raw(inst) for inst in TRACKS},
                "pitch_env_raw_by_track": {inst: self.pitch_env_raw(inst) for inst in TRACKS},
                "pitch_attack_raw_by_track": {inst: self.pitch_attack_raw(inst) for inst in TRACKS},
                "pitch_decay_raw_by_track": {inst: self.pitch_decay_raw(inst) for inst in TRACKS},
                "inst_fx_param1_raw_by_track": {
                    inst: self.inst_fx_param1_raw(inst) for inst in TRACKS
                },
                "color_raw_by_track": {inst: self.color_raw(inst) for inst in TRACKS},
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
