"""Offline coverage for TR-6S kit inspection, kit diffs, and their CLI commands.

Synthetic 1,312-byte blobs stand in for hardware captures. Verified offsets are
the hardware-checked raw bytes (kit-common header fields, six tune positions,
and the compact-record / Inst FX bytes listed in EXPECTED_VERIFIED). Candidate
labels are the remaining TR-8S field layout applied to those compact records
(currently the two-byte tone id). diff() leaves candidate_field empty when the
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
    392: "BD_level_raw",
    394: "BD_pan_raw",
    395: "BD_reverb_send_raw",
    396: "BD_delay_send_raw",
    442: "SD_tune_raw",
    443: "SD_decay_raw",
    444: "SD_level_raw",
    446: "SD_pan_raw",
    447: "SD_reverb_send_raw",
    448: "SD_delay_send_raw",
    494: "LT_tune_raw",
    495: "LT_decay_raw",
    496: "LT_level_raw",
    498: "LT_pan_raw",
    499: "LT_reverb_send_raw",
    500: "LT_delay_send_raw",
    546: "HC_tune_raw",
    547: "HC_decay_raw",
    548: "HC_level_raw",
    550: "HC_pan_raw",
    551: "HC_reverb_send_raw",
    552: "HC_delay_send_raw",
    598: "CH_tune_raw",
    599: "CH_decay_raw",
    600: "CH_level_raw",
    602: "CH_pan_raw",
    603: "CH_reverb_send_raw",
    604: "CH_delay_send_raw",
    650: "OH_tune_raw",
    651: "OH_decay_raw",
    652: "OH_level_raw",
    654: "OH_pan_raw",
    655: "OH_reverb_send_raw",
    656: "OH_delay_send_raw",
    16: "kit_level_raw",
    42: "BD_color_raw",
    43: "SD_color_raw",
    44: "LT_color_raw",
    45: "HC_color_raw",
    46: "CH_color_raw",
    47: "OH_color_raw",
    68: "reverb_type_raw",
    71: "reverb_predelay_raw",
    72: "reverb_lo_cut_raw",
    73: "reverb_hi_cut_raw",
    74: "reverb_density_raw",
    108: "delay_type_raw",
    109: "delay_sync_raw",
    110: "delay_level_raw",
    111: "delay_time_raw",
    112: "delay_feedback_raw",
    114: "delay_h_damp_raw",
    128: "delay_reverb_send_raw",
    129: "delay_coarse_tune_raw",
    130: "delay_fine_tune_raw",
    161: "mfx_switch_raw",
    180: "mfx_control_assign_raw",
    181: "mfx_balance_raw",
    182: "mfx_rate_raw",
    183: "mfx_depth_raw",
    184: "mfx_resonance_raw",
    185: "mfx_manual_raw",
    210: "sidechain_depth_raw",
    211: "sidechain_gain_raw",
    212: "sidechain_pan_raw",
    213: "sidechain_reverb_send_raw",
    214: "sidechain_delay_send_raw",
    248: "kit_lfo_waveform_raw",
    249: "kit_lfo_rate_raw",
    250: "kit_lfo_sync_raw",
    393: "BD_gain_raw",
    398: "BD_lfo_dest_raw",
    399: "BD_lfo_depth_raw",
    416: "BD_attack_or_fm_depth_raw",
    417: "BD_param_37_raw",
    418: "BD_fm_decay_raw",
    419: "BD_feedback_raw",
    421: "BD_param_3f_raw",
    425: "BD_fm_note_raw",
    426: "BD_pitch_env_raw",
    427: "BD_pitch_attack_raw",
    428: "BD_pitch_decay_raw",
    965: "BD_inst_fx_param1_raw",
    445: "SD_gain_raw",
    450: "SD_lfo_dest_raw",
    451: "SD_lfo_depth_raw",
    468: "SD_attack_or_fm_depth_raw",
    469: "SD_param_37_raw",
    470: "SD_fm_decay_raw",
    471: "SD_feedback_raw",
    473: "SD_param_3f_raw",
    477: "SD_fm_note_raw",
    478: "SD_pitch_env_raw",
    479: "SD_pitch_attack_raw",
    480: "SD_pitch_decay_raw",
    997: "SD_inst_fx_param1_raw",
    497: "LT_gain_raw",
    502: "LT_lfo_dest_raw",
    503: "LT_lfo_depth_raw",
    520: "LT_attack_or_fm_depth_raw",
    521: "LT_param_37_raw",
    522: "LT_fm_decay_raw",
    523: "LT_feedback_raw",
    525: "LT_param_3f_raw",
    529: "LT_fm_note_raw",
    530: "LT_pitch_env_raw",
    531: "LT_pitch_attack_raw",
    532: "LT_pitch_decay_raw",
    1029: "LT_inst_fx_param1_raw",
    549: "HC_gain_raw",
    554: "HC_lfo_dest_raw",
    555: "HC_lfo_depth_raw",
    572: "HC_attack_or_fm_depth_raw",
    573: "HC_param_37_raw",
    574: "HC_fm_decay_raw",
    575: "HC_feedback_raw",
    577: "HC_param_3f_raw",
    581: "HC_fm_note_raw",
    582: "HC_pitch_env_raw",
    583: "HC_pitch_attack_raw",
    584: "HC_pitch_decay_raw",
    1061: "HC_inst_fx_param1_raw",
    601: "CH_gain_raw",
    606: "CH_lfo_dest_raw",
    607: "CH_lfo_depth_raw",
    624: "CH_attack_or_fm_depth_raw",
    625: "CH_param_37_raw",
    626: "CH_fm_decay_raw",
    627: "CH_feedback_raw",
    629: "CH_param_3f_raw",
    633: "CH_fm_note_raw",
    634: "CH_pitch_env_raw",
    635: "CH_pitch_attack_raw",
    636: "CH_pitch_decay_raw",
    1093: "CH_inst_fx_param1_raw",
    653: "OH_gain_raw",
    658: "OH_lfo_dest_raw",
    659: "OH_lfo_depth_raw",
    676: "OH_attack_or_fm_depth_raw",
    677: "OH_param_37_raw",
    678: "OH_fm_decay_raw",
    679: "OH_feedback_raw",
    681: "OH_param_3f_raw",
    685: "OH_fm_note_raw",
    686: "OH_pitch_env_raw",
    687: "OH_pitch_attack_raw",
    688: "OH_pitch_decay_raw",
    1125: "OH_inst_fx_param1_raw",
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
    392: (
        ("verified", "bd_level_raw"),
        ("candidates", "tracks", "BD", "level_raw_verified"),
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
    443: (
        ("verified", "sd_decay_raw"),
        ("candidates", "tracks", "SD", "decay_raw_verified"),
    ),
    444: (
        ("verified", "sd_level_raw"),
        ("candidates", "tracks", "SD", "level_raw_verified"),
    ),
    446: (
        ("verified", "sd_pan_raw"),
        ("candidates", "tracks", "SD", "pan_raw_verified"),
    ),
    447: (
        ("verified", "sd_reverb_send_raw"),
        ("candidates", "tracks", "SD", "reverb_send_raw_verified"),
    ),
    448: (
        ("verified", "sd_delay_send_raw"),
        ("candidates", "tracks", "SD", "delay_send_raw_verified"),
    ),
    494: (
        ("verified", "tune_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "tune_raw_verified"),
    ),
    495: (
        ("verified", "lt_decay_raw"),
        ("candidates", "tracks", "LT", "decay_raw_verified"),
    ),
    496: (
        ("verified", "lt_level_raw"),
        ("candidates", "tracks", "LT", "level_raw_verified"),
    ),
    498: (
        ("verified", "lt_pan_raw"),
        ("candidates", "tracks", "LT", "pan_raw_verified"),
    ),
    499: (
        ("verified", "lt_reverb_send_raw"),
        ("candidates", "tracks", "LT", "reverb_send_raw_verified"),
    ),
    500: (
        ("verified", "lt_delay_send_raw"),
        ("candidates", "tracks", "LT", "delay_send_raw_verified"),
    ),
    546: (
        ("verified", "tune_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "tune_raw_verified"),
    ),
    547: (
        ("verified", "hc_decay_raw"),
        ("candidates", "tracks", "HC", "decay_raw_verified"),
    ),
    548: (
        ("verified", "hc_level_raw"),
        ("candidates", "tracks", "HC", "level_raw_verified"),
    ),
    550: (
        ("verified", "hc_pan_raw"),
        ("candidates", "tracks", "HC", "pan_raw_verified"),
    ),
    551: (
        ("verified", "hc_reverb_send_raw"),
        ("candidates", "tracks", "HC", "reverb_send_raw_verified"),
    ),
    552: (
        ("verified", "hc_delay_send_raw"),
        ("candidates", "tracks", "HC", "delay_send_raw_verified"),
    ),
    598: (
        ("verified", "tune_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "tune_raw_verified"),
    ),
    599: (
        ("verified", "ch_decay_raw"),
        ("candidates", "tracks", "CH", "decay_raw_verified"),
    ),
    600: (
        ("verified", "ch_level_raw"),
        ("candidates", "tracks", "CH", "level_raw_verified"),
    ),
    602: (
        ("verified", "ch_pan_raw"),
        ("candidates", "tracks", "CH", "pan_raw_verified"),
    ),
    603: (
        ("verified", "ch_reverb_send_raw"),
        ("candidates", "tracks", "CH", "reverb_send_raw_verified"),
    ),
    604: (
        ("verified", "ch_delay_send_raw"),
        ("candidates", "tracks", "CH", "delay_send_raw_verified"),
    ),
    650: (
        ("verified", "tune_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "tune_raw_verified"),
    ),
    651: (
        ("verified", "oh_decay_raw"),
        ("candidates", "tracks", "OH", "decay_raw_verified"),
    ),
    652: (
        ("verified", "oh_level_raw"),
        ("candidates", "tracks", "OH", "level_raw_verified"),
    ),
    654: (
        ("verified", "oh_pan_raw"),
        ("candidates", "tracks", "OH", "pan_raw_verified"),
    ),
    655: (
        ("verified", "oh_reverb_send_raw"),
        ("candidates", "tracks", "OH", "reverb_send_raw_verified"),
    ),
    656: (
        ("verified", "oh_delay_send_raw"),
        ("candidates", "tracks", "OH", "delay_send_raw_verified"),
    ),
    16: (("verified", "kit_level_raw"),),
    68: (("verified", "reverb_type_raw"),),
    71: (("verified", "reverb_predelay_raw"),),
    72: (("verified", "reverb_lo_cut_raw"),),
    73: (("verified", "reverb_hi_cut_raw"),),
    74: (("verified", "reverb_density_raw"),),
    108: (("verified", "delay_type_raw"),),
    109: (("verified", "delay_sync_raw"),),
    110: (("verified", "delay_level_raw"),),
    111: (("verified", "delay_time_raw"),),
    112: (("verified", "delay_feedback_raw"),),
    114: (("verified", "delay_h_damp_raw"),),
    128: (("verified", "delay_reverb_send_raw"),),
    129: (("verified", "delay_coarse_tune_raw"),),
    130: (("verified", "delay_fine_tune_raw"),),
    161: (("verified", "mfx_switch_raw"),),
    180: (("verified", "mfx_control_assign_raw"),),
    181: (("verified", "mfx_balance_raw"),),
    182: (("verified", "mfx_rate_raw"),),
    183: (("verified", "mfx_depth_raw"),),
    184: (("verified", "mfx_resonance_raw"),),
    185: (("verified", "mfx_manual_raw"),),
    210: (("verified", "sidechain_depth_raw"),),
    211: (("verified", "sidechain_gain_raw"),),
    212: (("verified", "sidechain_pan_raw"),),
    213: (("verified", "sidechain_reverb_send_raw"),),
    214: (("verified", "sidechain_delay_send_raw"),),
    248: (("verified", "kit_lfo_waveform_raw"),),
    249: (("verified", "kit_lfo_rate_raw"),),
    250: (("verified", "kit_lfo_sync_raw"),),
    42: (("verified", "color_raw_by_track", "BD"),),
    43: (("verified", "color_raw_by_track", "SD"),),
    44: (("verified", "color_raw_by_track", "LT"),),
    45: (("verified", "color_raw_by_track", "HC"),),
    46: (("verified", "color_raw_by_track", "CH"),),
    47: (("verified", "color_raw_by_track", "OH"),),
    393: (
        ("verified", "gain_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "gain_raw_verified"),
    ),
    398: (
        ("verified", "lfo_dest_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "lfo_dest_raw_verified"),
    ),
    399: (
        ("verified", "lfo_depth_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "lfo_depth_raw_verified"),
    ),
    416: (
        ("verified", "attack_or_fm_depth_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "attack_or_fm_depth_raw_verified"),
    ),
    417: (
        ("verified", "param_37_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "param_37_raw_verified"),
    ),
    418: (
        ("verified", "fm_decay_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "fm_decay_raw_verified"),
    ),
    419: (
        ("verified", "feedback_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "feedback_raw_verified"),
    ),
    421: (
        ("verified", "param_3f_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "param_3f_raw_verified"),
    ),
    425: (
        ("verified", "fm_note_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "fm_note_raw_verified"),
    ),
    426: (
        ("verified", "pitch_env_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "pitch_env_raw_verified"),
    ),
    427: (
        ("verified", "pitch_attack_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "pitch_attack_raw_verified"),
    ),
    428: (
        ("verified", "pitch_decay_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "pitch_decay_raw_verified"),
    ),
    965: (
        ("verified", "inst_fx_param1_raw_by_track", "BD"),
        ("candidates", "tracks", "BD", "inst_fx_param1_raw_verified"),
    ),
    445: (
        ("verified", "gain_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "gain_raw_verified"),
    ),
    450: (
        ("verified", "lfo_dest_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "lfo_dest_raw_verified"),
    ),
    451: (
        ("verified", "lfo_depth_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "lfo_depth_raw_verified"),
    ),
    468: (
        ("verified", "attack_or_fm_depth_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "attack_or_fm_depth_raw_verified"),
    ),
    469: (
        ("verified", "param_37_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "param_37_raw_verified"),
    ),
    470: (
        ("verified", "fm_decay_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "fm_decay_raw_verified"),
    ),
    471: (
        ("verified", "feedback_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "feedback_raw_verified"),
    ),
    473: (
        ("verified", "param_3f_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "param_3f_raw_verified"),
    ),
    477: (
        ("verified", "fm_note_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "fm_note_raw_verified"),
    ),
    478: (
        ("verified", "pitch_env_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "pitch_env_raw_verified"),
    ),
    479: (
        ("verified", "pitch_attack_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "pitch_attack_raw_verified"),
    ),
    480: (
        ("verified", "pitch_decay_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "pitch_decay_raw_verified"),
    ),
    997: (
        ("verified", "inst_fx_param1_raw_by_track", "SD"),
        ("candidates", "tracks", "SD", "inst_fx_param1_raw_verified"),
    ),
    497: (
        ("verified", "gain_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "gain_raw_verified"),
    ),
    502: (
        ("verified", "lfo_dest_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "lfo_dest_raw_verified"),
    ),
    503: (
        ("verified", "lfo_depth_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "lfo_depth_raw_verified"),
    ),
    520: (
        ("verified", "attack_or_fm_depth_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "attack_or_fm_depth_raw_verified"),
    ),
    521: (
        ("verified", "param_37_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "param_37_raw_verified"),
    ),
    522: (
        ("verified", "fm_decay_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "fm_decay_raw_verified"),
    ),
    523: (
        ("verified", "feedback_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "feedback_raw_verified"),
    ),
    525: (
        ("verified", "param_3f_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "param_3f_raw_verified"),
    ),
    529: (
        ("verified", "fm_note_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "fm_note_raw_verified"),
    ),
    530: (
        ("verified", "pitch_env_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "pitch_env_raw_verified"),
    ),
    531: (
        ("verified", "pitch_attack_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "pitch_attack_raw_verified"),
    ),
    532: (
        ("verified", "pitch_decay_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "pitch_decay_raw_verified"),
    ),
    1029: (
        ("verified", "inst_fx_param1_raw_by_track", "LT"),
        ("candidates", "tracks", "LT", "inst_fx_param1_raw_verified"),
    ),
    549: (
        ("verified", "gain_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "gain_raw_verified"),
    ),
    554: (
        ("verified", "lfo_dest_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "lfo_dest_raw_verified"),
    ),
    555: (
        ("verified", "lfo_depth_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "lfo_depth_raw_verified"),
    ),
    572: (
        ("verified", "attack_or_fm_depth_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "attack_or_fm_depth_raw_verified"),
    ),
    573: (
        ("verified", "param_37_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "param_37_raw_verified"),
    ),
    574: (
        ("verified", "fm_decay_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "fm_decay_raw_verified"),
    ),
    575: (
        ("verified", "feedback_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "feedback_raw_verified"),
    ),
    577: (
        ("verified", "param_3f_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "param_3f_raw_verified"),
    ),
    581: (
        ("verified", "fm_note_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "fm_note_raw_verified"),
    ),
    582: (
        ("verified", "pitch_env_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "pitch_env_raw_verified"),
    ),
    583: (
        ("verified", "pitch_attack_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "pitch_attack_raw_verified"),
    ),
    584: (
        ("verified", "pitch_decay_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "pitch_decay_raw_verified"),
    ),
    1061: (
        ("verified", "inst_fx_param1_raw_by_track", "HC"),
        ("candidates", "tracks", "HC", "inst_fx_param1_raw_verified"),
    ),
    601: (
        ("verified", "gain_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "gain_raw_verified"),
    ),
    606: (
        ("verified", "lfo_dest_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "lfo_dest_raw_verified"),
    ),
    607: (
        ("verified", "lfo_depth_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "lfo_depth_raw_verified"),
    ),
    624: (
        ("verified", "attack_or_fm_depth_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "attack_or_fm_depth_raw_verified"),
    ),
    625: (
        ("verified", "param_37_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "param_37_raw_verified"),
    ),
    626: (
        ("verified", "fm_decay_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "fm_decay_raw_verified"),
    ),
    627: (
        ("verified", "feedback_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "feedback_raw_verified"),
    ),
    629: (
        ("verified", "param_3f_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "param_3f_raw_verified"),
    ),
    633: (
        ("verified", "fm_note_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "fm_note_raw_verified"),
    ),
    634: (
        ("verified", "pitch_env_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "pitch_env_raw_verified"),
    ),
    635: (
        ("verified", "pitch_attack_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "pitch_attack_raw_verified"),
    ),
    636: (
        ("verified", "pitch_decay_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "pitch_decay_raw_verified"),
    ),
    1093: (
        ("verified", "inst_fx_param1_raw_by_track", "CH"),
        ("candidates", "tracks", "CH", "inst_fx_param1_raw_verified"),
    ),
    653: (
        ("verified", "gain_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "gain_raw_verified"),
    ),
    658: (
        ("verified", "lfo_dest_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "lfo_dest_raw_verified"),
    ),
    659: (
        ("verified", "lfo_depth_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "lfo_depth_raw_verified"),
    ),
    676: (
        ("verified", "attack_or_fm_depth_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "attack_or_fm_depth_raw_verified"),
    ),
    677: (
        ("verified", "param_37_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "param_37_raw_verified"),
    ),
    678: (
        ("verified", "fm_decay_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "fm_decay_raw_verified"),
    ),
    679: (
        ("verified", "feedback_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "feedback_raw_verified"),
    ),
    681: (
        ("verified", "param_3f_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "param_3f_raw_verified"),
    ),
    685: (
        ("verified", "fm_note_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "fm_note_raw_verified"),
    ),
    686: (
        ("verified", "pitch_env_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "pitch_env_raw_verified"),
    ),
    687: (
        ("verified", "pitch_attack_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "pitch_attack_raw_verified"),
    ),
    688: (
        ("verified", "pitch_decay_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "pitch_decay_raw_verified"),
    ),
    1125: (
        ("verified", "inst_fx_param1_raw_by_track", "OH"),
        ("candidates", "tracks", "OH", "inst_fx_param1_raw_verified"),
    ),
}

# Relative field bytes inside each 52-byte record. Tune is +2 and is not a
# candidate diff slot. Decay and level are now verified; they remain listed
# here so the candidate-only test can skip them when they appear in
# EXPECTED_VERIFIED. The third column is the inspect() key when that byte is
# still a candidate.
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
    raw[392] = 0x64  # BD level
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
    def record(base, tone, tune, decay, level, pan, reverb, delay, lfo, *, verified=()):
        return {
            "record_offset": base,
            "tone_id_candidate": tone,
            "tune_raw_verified": tune,
            "decay_raw_verified": decay,
            "level_raw_verified": level,
            "gain_raw_verified": 0,
            "lfo_dest_raw_verified": 0,
            "lfo_depth_raw_verified": lfo,
            "attack_or_fm_depth_raw_verified": 0,
            "param_37_raw_verified": 0,
            "fm_decay_raw_verified": 0,
            "feedback_raw_verified": 0,
            "param_3f_raw_verified": 0,
            "fm_note_raw_verified": 0,
            "pitch_env_raw_verified": 0,
            "pitch_attack_raw_verified": 0,
            "pitch_decay_raw_verified": 0,
            "inst_fx_param1_raw_verified": 0,
            "pan_raw_verified": pan,
            "reverb_send_raw_verified": reverb,
            "delay_send_raw_verified": delay,
        }

    return {
        "verified": {
            "name": "SLOT ONE",
            "reverb_time_raw": 0x08,
            "reverb_level_raw": 0x00,
            "bd_decay_raw": 0x00,
            "sd_decay_raw": 0x31,
            "lt_decay_raw": 0x32,
            "hc_decay_raw": 0x33,
            "ch_decay_raw": 0x34,
            "oh_decay_raw": 0x35,
            "bd_level_raw": 0x64,
            "sd_level_raw": 0x41,
            "lt_level_raw": 0x42,
            "hc_level_raw": 0x43,
            "ch_level_raw": 0x44,
            "oh_level_raw": 0x45,
            "bd_pan_raw": 0x80,
            "bd_reverb_send_raw": 0x00,
            "bd_delay_send_raw": 0x00,
            "sd_pan_raw": 0x51,
            "sd_reverb_send_raw": 0x61,
            "sd_delay_send_raw": 0x71,
            "lt_pan_raw": 0x52,
            "lt_reverb_send_raw": 0x62,
            "lt_delay_send_raw": 0x72,
            "hc_pan_raw": 0x53,
            "hc_reverb_send_raw": 0x63,
            "hc_delay_send_raw": 0x73,
            "ch_pan_raw": 0x54,
            "ch_reverb_send_raw": 0x64,
            "ch_delay_send_raw": 0x74,
            "oh_pan_raw": 0x55,
            "oh_reverb_send_raw": 0x65,
            "oh_delay_send_raw": 0x75,
            "kit_level_raw": 0,
            "reverb_type_raw": 0,
            "reverb_predelay_raw": 0,
            "reverb_lo_cut_raw": 0,
            "reverb_hi_cut_raw": 0,
            "reverb_density_raw": 0,
            "delay_type_raw": 0,
            "delay_sync_raw": 0,
            "delay_level_raw": 0,
            "delay_time_raw": 0,
            "delay_feedback_raw": 0,
            "delay_h_damp_raw": 0,
            "delay_reverb_send_raw": 0,
            "delay_coarse_tune_raw": 0,
            "delay_fine_tune_raw": 0,
            "mfx_switch_raw": 0,
            "mfx_control_assign_raw": 0,
            "mfx_balance_raw": 0,
            "mfx_rate_raw": 0,
            "mfx_depth_raw": 0,
            "mfx_resonance_raw": 0,
            "mfx_manual_raw": 0,
            "sidechain_depth_raw": 0,
            "sidechain_gain_raw": 0,
            "sidechain_pan_raw": 0,
            "sidechain_reverb_send_raw": 0,
            "sidechain_delay_send_raw": 0,
            "kit_lfo_waveform_raw": 0,
            "kit_lfo_rate_raw": 0,
            "kit_lfo_sync_raw": 0,
            "tune_raw_by_track": {
                "BD": 0x7C,
                "SD": 0x80,
                "LT": 0x80,
                "HC": 0x80,
                "CH": 0x7B,
                "OH": 0x80,
            },
            "gain_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "lfo_dest_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "lfo_depth_raw_by_track": {"BD": 0x03, "SD": 0x06, "LT": 0x07, "HC": 0x08, "CH": 0x09, "OH": 0x0A},
            "attack_or_fm_depth_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "param_37_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "fm_decay_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "feedback_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "param_3f_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "fm_note_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "pitch_env_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "pitch_attack_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "pitch_decay_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "inst_fx_param1_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
            "color_raw_by_track": {"BD": 0, "SD": 0, "LT": 0, "HC": 0, "CH": 0, "OH": 0},
        },
        "candidates": {
            "source": "TR-8S bulk field offsets in confirmed compact TR-6S records",
            "tracks": {
                "BD": record(388, 0x1234, 0x7C, 0x00, 0x64, 0x80, 0x00, 0x00, 0x03,
                             verified=("decay", "level", "pan", "reverb_send", "delay_send")),
                "SD": record(440, 0x2111, 0x80, 0x31, 0x41, 0x51, 0x61, 0x71, 0x06,
                             verified=("decay", "level", "pan", "reverb_send", "delay_send")),
                "LT": record(492, 0x2212, 0x80, 0x32, 0x42, 0x52, 0x62, 0x72, 0x07,
                             verified=("decay", "level", "pan", "reverb_send", "delay_send")),
                "HC": record(544, 0x2313, 0x80, 0x33, 0x43, 0x53, 0x63, 0x73, 0x08,
                             verified=("decay", "level", "pan", "reverb_send", "delay_send")),
                "CH": record(596, 0x2414, 0x7B, 0x34, 0x44, 0x54, 0x64, 0x74, 0x09,
                             verified=("decay", "level", "pan", "reverb_send", "delay_send")),
                "OH": record(648, 0x2515, 0x80, 0x35, 0x45, 0x55, 0x65, 0x75, 0x0A,
                             verified=("decay", "level", "pan", "reverb_send", "delay_send")),
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

        tracks = report["candidates"]["tracks"]
        for name, record in tracks.items():
            self.assertIn("pan_raw_verified", record)
            self.assertIn("reverb_send_raw_verified", record)
            self.assertIn("delay_send_raw_verified", record)
            self.assertNotIn("pan_raw_candidate", record)
            self.assertNotIn("reverb_send_raw_candidate", record)
            self.assertNotIn("delay_send_raw_candidate", record)
            self.assertIn("tune_raw_verified", record)
            self.assertIn("tone_id_candidate", record)
            self.assertIn("decay_raw_verified", record)
            self.assertIn("level_raw_verified", record)
            self.assertIn("lfo_depth_raw_verified", record)
            self.assertIn("lfo_dest_raw_verified", record)
            self.assertIn("gain_raw_verified", record)
            self.assertNotIn("lfo_raw_candidate", record)
            self.assertNotIn("tune_raw_candidate", record)
            self.assertNotIn("decay_raw_candidate", record)
            self.assertNotIn("level_raw_candidate", record)

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
        # Six tracks, eight listed slots, minus decay, level,
        # pan/reverb/delay, and LFO depth on every track (6*6 = 36).
        self.assertEqual(seen, 6 * len(CANDIDATE_FIELDS) - 36)

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

        # 75 sits just after verified reverb density. 397 is the unmapped gap
        # between BD delay send (+8) and LFO dest (+10). 1311 is the last byte.
        for offset in (75, 397, 1311):
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
        for offset in (650, 75, 443):
            mutated[offset] = (mutated[offset] + 1) & 0xFF
        rows = Kit.from_bytes(original).diff(Kit.from_bytes(mutated))
        self.assertEqual(rows, [
            {
                "offset": 75,
                "before": original[75],
                "after": mutated[75],
                "verified_field": None,
                "candidate_field": None,
            },
            {
                "offset": 443,
                "before": original[443],
                "after": mutated[443],
                "verified_field": "SD_decay_raw",
                "candidate_field": None,
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
        after_blob[443] = (after_blob[443] + 1) & 0xFF  # verified SD decay
        after_blob[75] = (after_blob[75] + 1) & 0xFF    # unmapped
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
        self.assertEqual(by_offset[443]["verified_field"], "SD_decay_raw")
        self.assertIsNone(by_offset[443]["candidate_field"])
        self.assertIsNone(by_offset[75]["verified_field"])
        self.assertIsNone(by_offset[75]["candidate_field"])

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
