# TR-6S Studio (port in progress)

This is a work-in-progress adaptation of [ideaCompany/tr8s-studio](https://github.com/ideaCompany/tr8s-studio) for the Roland TR-6S. The code snapshot comes from upstream commit `a62ae22c5f7816a75db61722fc006c536d4f096b` and retains its MIT license.

The first verified layer is read-only SysEx transport. The model ID is `00 00 00 6D`, and bulk reads return system 752 bytes, pattern 24,504 bytes, and kit 1,312 bytes on firmware 1.51 / revision 0BDE. The earlier larger sizes in the companion [TR-6S port notes](../oxi-e16-lua-scripts/docs/TR8S_STUDIO_PORT.md) came from an ALSA sequencer text-parser error; that parser has been corrected.

## Read a raw blob

Install this package in a Python environment, then run:

```sh
tr6s info
tr6s read-blob pattern 0 /tmp/tr6s-pattern-000.bin
tr6s read-blob kit 0 /tmp/tr6s-kit-000.bin
tr6s read-blob system 0 /tmp/tr6s-system.bin
tr6s inspect-kit 1
tr6s inspect-kit 1 --file /tmp/tr6s-kit-001.bin
tr6s diff-kit /tmp/kit-before.bin /tmp/kit-after.bin
tr6s inspect-pattern 0
tr6s inspect-pattern 0 --file /tmp/tr6s-pattern-000.bin
tr6s diff-pattern /tmp/pattern-before.bin /tmp/pattern-after.bin
```

The device must be stopped for a bulk read. The CLI uses the TR-6S MIDI 1 ALSA sequencer port so it can coexist with the Pi's MIDI router and connected E16. Set `TR6S_SEQ_PORT` to a `client:port` value if automatic discovery does not find it. The output path must not already exist.

`inspect-kit` groups the hardware-confirmed name, raw reverb values, six raw tune values, BD Decay, BD Pan, BD Reverb Send, and BD Delay Send under `verified`. It shows tone ID, the other decay, pan, and send bytes, level, and LFO bytes under `candidates`. Those candidate labels come from TR-8S bulk offsets applied to the confirmed compact TR-6S records; their meanings have not yet been checked by TR-6S panel changes. The command reads only and does not expose an editor.

`diff-kit` reports changed offsets between two saved kit blobs and labels a field as `verified_field` or `candidate_field`. A candidate label is a pointer for the next panel check, not a confirmed TR-6S field.

`inspect-pattern` reads a 24,504-byte pattern. `verified` is empty: no pattern field has a TR-6S differential capture yet. `candidates.header` shows name, tempo, kit, and scale from the TR-8S header offsets, each with `"status": "candidate"`. Shuffle, steps, variations, and motion stay `"not verified"`. The inherited step geometry is listed there only as a candidate, using TR-8S track order `BD SD LT MT HT RS HC CH OH CC RC`. Compact TR-6S order is not established in the pattern blob, so an OH label in a diff is the TR-8S OH position, not the sixth compact track.

`diff-pattern` compares two saved pattern blobs and emits changed ranges in offset order. Consecutive bytes that share a label form one range. Each range looks like:

```json
{"offset": 148, "length": 1, "before": [0], "after": [112], "before_hex": "00", "after_hex": "70", "verified_field": null, "candidate_field": "A_BD_step00_velocity"}
```

`before` and `after` are the raw bytes. `verified_field` is null until a capture promotes an offset. `candidate_field` is null when the layout has no name for that byte. A candidate label is a hypothesis for the next panel check, not a confirmed TR-6S field. The commands read only.

BD Decay is now confirmed at offset 391: one panel increment changed only `00` to `01`, and reversing it restored the full 1,312-byte baseline. The inspector marks this raw field as verified.

BD Pan is confirmed at offset 394: one increment right from centre changed only `80` to `81`, and moving left restored the entire kit blob. The inspector marks its raw byte as verified.

BD Reverb Send is confirmed at offset 395: one panel increment changed only `00` to `01`, and reversing it restored the full kit blob. The inspector marks this raw byte as verified.

BD Delay Send is confirmed at offset 396: one panel increment changed only `00` to `01`, and reversing it restored the full kit blob. The inspector marks this raw byte as verified.

## Current limits

TR-8S Studio's pattern and kit editors still use TR-8S offsets. Kit tune, decay, pan, and send offsets that have been checked on the TR-6S are the verified kit fields above. Pattern name, tempo, kit, scale, shuffle, steps, and motion have not been established through TR-6S differential captures; `inspect-pattern` and `diff-pattern` keep those labels as candidates. Bulk writes, commits, sample uploads, and tone deletion are disabled in the transport. The web interface and the remaining tool commands have not yet been adapted or validated for the TR-6S. Do not treat them as a working TR-6S editor.

The next step is a hardware pattern capture: one reversible panel change, then `diff-pattern` against the before-blob. See `next-plan.md`. Kit fields that are still candidates are tone selection, instrument level, LFO, and one non-BD decay, pan, or send.

Differential captures on kit slot 1 have confirmed raw Reverb Time at offset 69 (`08` to `09` for one increment) and raw Reverb Level at offset 70 (`00` to `01`). Each change affected exactly one byte, and the full blob matched its baseline after restoration. Both fields are exposed for reading; their display-value mappings remain to be verified.

A BD Tune increment on the same kit changed only byte 390 (`7C` to `7D`), and the full blob matched baseline after the knob was restored. This agrees with the TR-8S record base `388` plus its tune field offset `2`, but it does not establish the remaining instrument records or signed value mapping. The raw byte is available as `Kit.bd_tune_raw`.

An SD Tune increment changed only byte 442 (`80` to `81`), and the full blob matched baseline after restoration. The 52-byte gap from BD Tune matches the first two TR-8S instrument records. The raw byte is available as `Kit.sd_tune_raw`.

HC Tune changed only byte 546 (`80` to `81`), and the blob matched baseline after restoration. This is the fourth consecutive 52-byte record (`388 + 3 × 52 + 2`). The TR-8S HC position would be byte 702, so the TR-6S uses compact track order at least through HC. The raw byte is available as `Kit.hc_tune_raw`.

OH Tune changed only byte 650 (`80` to `81`), then the full blob matched baseline after restoration. It is the sixth consecutive 52-byte record (`388 + 5 × 52 + 2`). Together with the HC capture, this supports compact six-track kit order. The raw byte is available as `Kit.oh_tune_raw`.

LT Tune changed only byte 494 (`80` to `81`) and returned to a full baseline match after restoration. This verifies the third compact record. The raw byte is available as `Kit.lt_tune_raw`.

CH Tune changed only byte 598 (`7B` to `7C`) and returned to a full baseline match after restoration. This confirms the fifth compact record and completes a direct tune-offset check for all six TR-6S tracks. `Kit.tune_raw(track)` reads these raw bytes; the signed/display mapping and other instrument fields remain unverified.

## Source

This is a GitHub fork of `ideaCompany/tr8s-studio` at upstream commit `a62ae22c5f7816a75db61722fc006c536d4f096b`. The original binary assets and test fixtures are retained in the fork.
