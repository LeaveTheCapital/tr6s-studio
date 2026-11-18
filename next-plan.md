# TR-6S Studio handoff — 2026-11-16

## Progress — 2026-11-18

- Read-only `inspect-pattern` and `diff-pattern` are in. They mirror kit inspection for a 24,504-byte blob, including `inspect-pattern --file`. No pattern field is verified: name, tempo, kit, and scale are TR-8S header candidates. Shuffle, steps, variations, and motion stay `not verified`, and their inherited offsets are candidate diff labels only. Promoting any of them still needs a differential panel capture.
- OH Pan (byte 654) and OH Delay Send (byte 656) are now verified kit fields, from E16 CC captures on kit slot 1 that each changed one byte and then restored the whole 1,312-byte blob.
- A later 2026-11-18 session verified pan, reverb send, and delay send on every remaining track (SD, LT, HC, CH) plus OH Reverb Send. Fresh full dumps of system 0, kits 0-127, and patterns 0-127 are in `backups/tr6s-baseline-20261118/` (gitignored). Native TR-6S CCs for tune/decay/level did not move kit 1 on any MIDI channel — the device was on kit 0.
- A follow-up 2026-11-18 session, with the TR-6S left on kit 0 and no `TEMP_CURRENT_KIT` or other kit/pattern select, verified native-CC tune, decay, and level on every track of **kit slot 0**. Layout matches `388 + 52*track` with tune at base+2, decay at base+3, and level at base+4. The documented receive channel is Pattern Ch 10; that channel moved kit 0 on the first probe (BD Tune).

## Progress — 2026-11-17

- Kit inspect/diff offline tests merged in PR #1 (`tests/test_tr6s_kit_inspect.py`). They cover `Kit.inspect()`, `Kit.diff()`, `inspect-kit --file`, and `diff-kit` with synthetic 1,312-byte blobs and no MIDI.
- GitHub Actions merged in PR #3 (`.github/workflows/offline-tests.yml`). It runs on pull requests and on pushes to `main`, on Python 3.12 (`requires-python` is `>=3.10`). The job never collects `tests/hardware/`.
- The inherited offline suite is repaired for the read-only TR-6S contract. Verified header, transport, and tune-offset behaviour is asserted. Tests that need unverified step, shuffle, colour, or instrument-record layouts are skipped with `not verified on TR-6S`. Tests of bulk-write serialisation are skipped with `writes disabled`.
- CI now runs the full offline suite. `OFFLINE_SCOPE` defaults to `all`, which runs `python -m pytest tests --ignore=tests/hardware`. `OFFLINE_SCOPE=verified` still runs `unittest discover -s tests -p 'test_tr6s*.py'`.
- `kit.get` and `pattern.list` (and the server pattern index) tolerate `describe()` results that no longer include per-instrument fields or variation maps.

## Where the work stands

- GitHub fork: `LeaveTheCapital/tr6s-studio`, based on `ideaCompany/tr8s-studio` commit `a62ae22`. `origin` points to the fork; `upstream` points to the TR-8S project. Current fork head before this handoff: `e7f486b`.
- Companion protocol research: `../oxi-e16-lua-scripts/docs/TR8S_STUDIO_PORT.md` and `../oxi-e16-lua-scripts/tr6s-sysex-format.md`. Current companion head before this handoff: `3d7b559`.
- This is a **read-only port**, not a working editor. The CLI supports `info`, `read-blob`, `inspect-kit`, `diff-kit`, `inspect-pattern`, and `diff-pattern`. The web UI, most tool commands, pattern steps, and bulk writes remain unported. `src/tr6s/transport.py` blocks bulk writes and commits; keep that guard in place until layouts and write behavior are verified.
- The user uses **`y` to mean a requested panel action is done**. They are taking a break; do not ask for another panel action until they return.

## Verified transport and environment

- Pi router: `/home/hellohenry/pi-midi-router`; service `midi-router.service`. Client numbers change after reconnecting. On 2026-11-18 the ports were TR-6S MIDI 1 `28:0` and OXI E16 MIDI 1 `24:0` (E16 output routed to the TR-6S).
- The read-only CLI uses `aseqdump`/`aplaymidi` through `src/tr6s/sequencer.py` and automatically finds TR-6S MIDI 1. Override with `TR6S_SEQ_PORT=client:port`. This coexists with the router and E16. Avoid opening raw MIDI concurrently with the sequencer route.
- Firmware tested: `1.51`, revision `0BDE`. Model ID: `00 00 00 6D`. The utility bulk reads are DT1 requests with 4-byte 7-bit index and count. Confirmed blob sizes: system **752**, pattern **24,504**, kit **1,312** bytes.
- Earlier claims that TR-6S blobs were 754/24,599/1,317 bytes were wrong: the old `aseqdump` parser counted the client number on each continuation line as payload. That parser and the docs were fixed in the companion repo. Independent raw MIDI and corrected sequencer reads agreed byte for byte.
- `read-blob` checks playing status and refuses bulk reads while the machine is playing. Do not stop the sequencer or change routes automatically.
- `/dev/snd/seq` is now available after an execution-permission change. The Pi, TR-6S, and E16 needed no reconfiguration. Firmware during that session was still `1.51`/`0BDE`, with the TR-6S stopped.
- ALSA client numbers can change. The previously observed E16 port `28:0` was an E16 **output** connected to TR-6S MIDI 1, not proof of an E16 input. Discover the E16 **input** with `aconnect -i` before sending CCs into a loaded script.

## Local captures and useful commands

Captures are ignored by Git and **not uploaded to GitHub**. They stay on this Pi only, so preserve them when changing workspaces.

- `backups/tr6s-baseline-20261116/` is the earlier session. `kit-001-candidate-baseline.bin` (identical to `e16-kit-001-fresh-baseline.bin`) is the restored kit slot 1 reference from that day, plus panel and E16 change/restore pairs. `pattern-000.bin` and `system.bin` are initial reads.
- `backups/tr6s-baseline-20261118/` is a full dump of system 0, kits 0-127, and patterns 0-127, plus the kit-1 E16 CC-session pairs (`kit-001-<track>-<field>-*.bin`, `cc-session-results.json`) and the kit-0 native CC session (`kit-000-*`, `kit0-native-cc-results.json`, `kit0-native-cc.log`).

```sh
cd /home/hellohenry/code/tr6s-studio
PYTHONPATH=src python3 -m tr6s.cli info
PYTHONPATH=src python3 -m tr6s.cli read-blob kit 1 /tmp/kit-001-new.bin
PYTHONPATH=src python3 -m tr6s.cli inspect-kit 1
PYTHONPATH=src python3 -m tr6s.cli inspect-kit 1 --file backups/tr6s-baseline-20261116/kit-001-candidate-baseline.bin
PYTHONPATH=src python3 -m tr6s.cli diff-kit backups/tr6s-baseline-20261116/kit-001-candidate-baseline.bin /tmp/kit-001-new.bin
PYTHONPATH=src python3 -m tr6s.cli inspect-pattern 0 --file backups/tr6s-baseline-20261116/pattern-000.bin
PYTHONPATH=src python3 -m tr6s.cli diff-pattern backups/tr6s-baseline-20261116/pattern-000.bin /tmp/pattern-000-new.bin
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_tr6s*.py' -q
PYTHONPATH=src python3 -m pytest tests --ignore=tests/hardware -q
```

`read-blob` creates a new file and refuses to overwrite one. Check `git status --short` before work; both repositories were clean when this handoff was written.

## Verified kit blob offsets

All values below are **raw stored bytes**, not fully mapped display values. The six instrument records follow compact TR-6S order `BD, SD, LT, HC, CH, OH`, starting at byte 388 with a 52-byte stride. Each Tune offset was checked by a single panel increment and restoration on kit slot 1.

| Field | Offset | Observation |
| --- | ---: | --- |
| Reverb Time | 69 | `08` → `09` for one increment |
| Reverb Level | 70 | `00` → `01` |
| BD Tune | 390 | `7C` → `7D` |
| SD Tune | 442 | `80` → `81` |
| LT Tune | 494 | `80` → `81` |
| HC Tune | 546 | `80` → `81`; TR-8S HC would be 702 |
| CH Tune | 598 | `7B` → `7C` |
| OH Tune | 650 | `80` → `81`; TR-8S OH would be 806 |
| BD Decay | 391 | `00` → `01` |
| BD Pan | 394 | centre `80` → right `81` |
| BD Reverb Send | 395 | `00` → `01` |
| BD Delay Send | 396 | `00` → `01` |
| SD Pan | 446 | E16 ch 12 CC 40 value `63`: `80` → `7E`; value `64` restored |
| SD Reverb Send | 447 | E16 ch 12 CC 43: `41` (65) → `40`; CC cannot hit 65 (32→64, 33→66); SysEx DT1 `10 01 11 0E` value 65 restored |
| SD Delay Send | 448 | E16 ch 12 CC 44 value `111`: `E0` → `DE`; value `112` restored |
| LT Pan | 498 | E16 ch 12 CC 20: `7F` (127) → `7E`; off-grid; SysEx DT1 `10 01 12 0C` value 127 restored |
| LT Reverb Send | 499 | E16 ch 12 CC 23 value `63`: `80` → `7E`; value `64` restored |
| LT Delay Send | 500 | E16 ch 12 CC 24 value `111`: `E0` → `DE`; value `112` restored |
| HC Pan | 550 | E16 ch 12 CC 50 value `63`: `80` → `7E`; value `64` restored |
| HC Reverb Send | 551 | E16 ch 12 CC 53 value `126`: `FF` → `FC`; value `127` restored |
| HC Delay Send | 552 | E16 ch 12 CC 54: `BD` (189) → `BC`; off-grid (94→188, 95→190); SysEx DT1 `10 01 13 10` value 189 restored |
| CH Pan | 602 | E16 ch 12 CC 60 value `82`: `A6` → `A4`; value `83` restored |
| CH Reverb Send | 603 | E16 ch 12 CC 63 value `63`: `80` → `7E`; value `64` restored |
| CH Delay Send | 604 | E16 ch 12 CC 64 value `1`: `00` → `02`; value `0` restored |
| OH Pan | 654 | E16 ch 12 CC 70 value `82`: `A6` → `A4`; value `83` restored |
| OH Reverb Send | 655 | E16 ch 12 CC 73 value `63`: `80` → `7E`; value `64` restored |
| OH Delay Send | 656 | E16 ch 12 CC 74 value `111`: `E0` → `DE`; value `112` restored |
| SD Decay | 443 | native ch 10 CC 28 on current kit 0: `80` → `7E`; CC 64 restored |
| LT Decay | 495 | native ch 10 CC 47 on current kit 0: `02` → `00`; CC 1 restored |
| HC Decay | 547 | native ch 10 CC 59 on current kit 0: `80` → `7E`; CC 64 restored |
| CH Decay | 599 | native ch 10 CC 62 on current kit 0: `2A` → `28`; CC 21 restored |
| OH Decay | 651 | native ch 10 CC 81 on current kit 0: `80` → `7E`; CC 64 restored |
| BD Level | 392 | native ch 10 CC 24 on current kit 0: `00` → `02`; CC 0 restored |
| SD Level | 444 | native ch 10 CC 29 on current kit 0: `FF` → `FC`; CC 127 restored |
| LT Level | 496 | native ch 10 CC 48 on current kit 0: `00` → `02`; CC 0 restored |
| HC Level | 548 | native ch 10 CC 60 on current kit 0: `00` → `02`; CC 0 restored |
| CH Level | 600 | native ch 10 CC 63 on current kit 0: `D0` → `CE`; CC 104 restored |
| OH Level | 652 | native ch 10 CC 82 on current kit 0: `00` → `02`; CC 0 restored |

`src/tr6s/kit.py` exposes those verified reads and separately labels TR-8S-derived candidate offsets for tone ID and LFO. Do not treat candidate labels as verified. Selecting a kit can refresh fader-level bytes in the selected (and sometimes previously selected) kit; keep selection separate from a parameter diff. Native level CCs written to the *current* kit did persist through a bulk read in the kit-0 session when faders were not moved.

An earlier E16 session independently confirmed Reverb Time as well: channel 11 CC 3 value `5` changed only kit 1 byte 69 from `8` to `10`; value `4` restored the entire 1,312-byte blob.

### E16 CC scaling (2026-11-18)

Pan / reverb send / delay send are not native TR-6S CCs (Roland MIDI implementation chart). They were sent to the OXI E16 input (`24:0`) on MIDI channel 12, where the on-device Lua script converts them to kit-addressed SysEx. Note On channel 11, note 1 sets the script's `kit_number` to slot 1 (used in the SysEx address) without itself changing the TR-6S selected kit.

Scaling for these flags=0 0-255 fields is `floor(CC * 255 / 127)`, which often matches `2 * CC` in the mid range but not at the top (`CC 127` → 255). Some stored bulk bytes sit between two CC encodings (65, 127, 189). In that case a one-step CC still moved only the expected offset; the exact original byte was written back with a live-parameter SysEx DT1 `F0 41 10 00 00 00 6D 12  10 <kit> <inst> <param>  <hi-nibble> <lo-nibble>  <checksum> F7`, where inst is `10` BD … `15` OH and param is `0C` pan, `0E` reverb send, `10` delay send (also `04` tune, `06` decay, `08` level).

Native TR-6S CCs (tune/decay/level from the MIDI implementation chart) sent to TR-6S MIDI 1 on every channel 1-16 produced no kit-1 diffs, including after a documented `TEMP_CURRENT_KIT` (`01 00 00 00`) select of kit 1. The device was actually on kit 0, so those CCs could not edit slot 1. That select did refresh kit 1's LT/HC/CH/OH level bytes to the physical fader positions, matching the 2026-11-16 kit-001 baseline (`496=0`, `548=0`, `600=209`, `652=0`). Pattern 0 and system 0 were byte-identical between the 16th and 18th dumps.

### Native CCs and kit selection (2026-11-18, kit 0)

**Native CCs affect only the currently selected kit.** E16 Lua SysEx writes are addressed to a kit slot (`10 <kit> <inst> <param>`) and work regardless of which kit is selected (the earlier pan/send results on slot 1 still stand).

With the TR-6S left on kit 0 (no kit or pattern select sent), Pattern Ch 10 moved kit 0 immediately. Tune, decay, and level CCs for all six instruments each changed exactly the predicted compact-record byte and were restored. Kit 0's layout is the same `388 + 52*track` map already verified on kit 1.

Native CC scaling (MIDI implementation chart):

- Tune: stored byte = `CC * 2` (centre CC 64 → 128).
- Decay and level: stored byte = `CC * 2`, except CC 127 → 255.
- CH Tune was off-grid (stored 141; CC 70 encodes 140). The change CC still moved only offset 598; the exact byte was restored with SysEx DT1 `10 00 14 04`.

Level CCs were not overridden by physical faders during this session: every level byte moved as predicted and restored, including SD Level 255 and CH Level 208. Fader refresh was previously seen when a kit was *selected*, not when a level CC was sent to the already-current kit.

CTRL CCs (96/97/102/106/107/108 on ch 10) are assignment-dependent on this kit and were not promoted as named verified fields. All leftovers were restored; final kit 0 matched the session baseline (`sha256 9e3c179e057b3013cf4d7e6df22ded65e52a4bdb88cfa4a9b1b83ea67c91552a`). Observed mappings:

- BD CTRL CC 96 → record +28 (offset 416), scaling `CC * 2`; restored with CC 66.
- SD CTRL CC 97 → SD Reverb Send (447); restored with CC 0.
- LT CTRL CC 102 → record +28 (offset 520), off-grid 131; restored with SysEx `10 00 12 35` (companion name: Attack / TSV name: LT FM Depth).
- HC CTRL CC 106 → offset 1061, off-grid 127; restored with SysEx `10 00 23 09` (HC Inst FX Param 1). Offset 1061 sits at +5 of a 32-byte tail record starting at 1056 (tail records appear at 1024, 1056, 1088, …).
- CH CTRL CC 107 → offset 1093 (1088+5); restored with CC 29 (byte 58). Likely CH Inst FX Param 1 (`10 00 24 09`).
- OH CTRL CC 108 first moved OH record +29 (offset 677, byte 110). Restore used SysEx `10 00 15 37` for +29 and `10 00 25 09` (OH Inst FX Param 1) for tail offset 1125.

SysEx probes that were undone also confirmed instrument-record addresses already in the companion map: `0x0A` writes base+5 (Instrument Gain), `0x14` writes base+11 (LFO Depth), `0x35` writes base+28, and `0x37` writes base+29 (checked on OH). Those offsets are not yet promoted in `kit.py`.

A 2026-11-18 pre-select dump of kit 1 differed from the 16th only in those four level bytes (all 255). After the select, the final kit 1 blob matched the 16th baseline again. Kit 0 also changed at fader-related offsets when kit 1 was selected.

## Next work: pattern read mapping

1. Read `docs/PROTOCOL.md` in this fork alongside the companion `docs/TR8S_STUDIO_PORT.md` and `tr6s-sysex-format.md`. The TR-8S pattern header and step layout are **candidates**. `src/tr6s/pattern.py` currently allows header reads but deliberately raises on shuffle and step offsets.
2. Done, from saved blobs only. `Pattern.inspect()`, `Pattern.diff()`, `inspect-pattern` (including `--file`), and `diff-pattern` read a 24,504-byte pattern. `verified` is empty. Name (0..15), tempo (16..17, tenths of a BPM), kit (18, TR-8S 1-based decoding), and scale (19) are candidates. Shuffle (32), the variation mask (48), steps, variations, and motion stay `not verified`. Diff ranges carry `offset`, `length`, `before`/`after` bytes, hex, `verified_field`, and `candidate_field`. Step labels use inherited TR-8S order `BD SD LT MT HT RS HC CH OH CC RC`, so the TR-8S OH label is not the compact sixth track. Unmapped bytes have a null candidate label. Writers stay disabled.
3. Hardware-blocked. When the user returns, agree on a safe pattern slot to edit. Save a fresh before-blob for **that slot**; do not assume the current selected pattern is slot 0 or that `pattern-000.bin` still reflects its state. Verify the sequencer is stopped.
4. Hardware-blocked. Ask for one reversible panel change, such as toggling one known BD step in variation A. Capture after, run `diff-pattern`, then ask for the same step to be toggled back and confirm the entire blob matches baseline. A second track near the end (OH) can distinguish compact TR-6S step order from retained TR-8S positions: a compact OH hit will not carry the candidate label `A_OH_step00_velocity`. Keep changes one at a time and record the exact selected variation and step number.
5. Hardware-blocked. Map header items (tempo, kit reference, scale, shuffle), variation blocks, steps, and motion only as evidence supports them. Promote a field from candidate to verified in code and docs after a clean differential capture. Leave writers blocked until a sufficiently complete map, backups, and an explicit safe write test plan exist. Upstream observed that even an uncommitted bulk send can alter a stored slot immediately.

If returning to kit work instead, the remaining high-value candidate checks are tone selection, LFO, and instrument gain (base+5, SysEx `0x0A`, confirmed only by an undone probe). Tune, decay, level, pan, and both sends are verified on all six tracks. CTRL remains assignment-dependent. The standard live parameter SysEx map in the companion docs gives addresses and nibble-encoded values, **not positions in the opaque bulk kit blob**, though several of those addresses have now been paired with compact-record offsets via differential bulk reads. Individual parameter RQ1 probes gave no reply in one attempt; use bulk differential reads as the established method.

For further E16 CC checks: send to the E16 **input** (on 2026-11-18, `24:0`; confirm with `aconnect -i`). Do not treat a previous `28:0` as that input. Set the script kit_number with Note On channel 11. Save a fresh kit slot 1 baseline, choose one mapped CC, send a nearby value, read and diff, then restore. If the stored byte is off the 7-bit CC grid, restore the exact byte with the live-parameter SysEx DT1 rather than aborting. Stop on an unexpected multi-byte diff or a failed exact restore.
