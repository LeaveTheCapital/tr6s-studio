# TR-6S Studio handoff — 2026-11-16

## Progress — 2026-11-18

- Read-only `inspect-pattern` and `diff-pattern` are in. They mirror kit inspection for a 24,504-byte blob, including `inspect-pattern --file`. No pattern field is verified: name, tempo, kit, and scale are TR-8S header candidates. Shuffle, steps, variations, and motion stay `not verified`, and their inherited offsets are candidate diff labels only. Promoting any of them still needs a differential panel capture.
- OH Pan (byte 654) and OH Delay Send (byte 656) are now verified kit fields, from E16 CC captures on kit slot 1 that each changed one byte and then restored the whole 1,312-byte blob.

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

- Pi router: `/home/hellohenry/pi-midi-router`; service `midi-router.service`. TR-6S appeared as ALSA sequencer client `24`, MIDI 1 port `24:0`, with the OXI E16 also connected. Client numbers can change after reconnecting.
- The read-only CLI uses `aseqdump`/`aplaymidi` through `src/tr6s/sequencer.py` and automatically finds TR-6S MIDI 1. Override with `TR6S_SEQ_PORT=client:port`. This coexists with the router and E16. Avoid opening raw MIDI concurrently with the sequencer route.
- Firmware tested: `1.51`, revision `0BDE`. Model ID: `00 00 00 6D`. The utility bulk reads are DT1 requests with 4-byte 7-bit index and count. Confirmed blob sizes: system **752**, pattern **24,504**, kit **1,312** bytes.
- Earlier claims that TR-6S blobs were 754/24,599/1,317 bytes were wrong: the old `aseqdump` parser counted the client number on each continuation line as payload. That parser and the docs were fixed in the companion repo. Independent raw MIDI and corrected sequencer reads agreed byte for byte.
- `read-blob` checks playing status and refuses bulk reads while the machine is playing. Do not stop the sequencer or change routes automatically.
- `/dev/snd/seq` is now available after an execution-permission change. The Pi, TR-6S, and E16 needed no reconfiguration. Firmware during that session was still `1.51`/`0BDE`, with the TR-6S stopped.
- ALSA client numbers can change. The previously observed E16 port `28:0` was an E16 **output** connected to TR-6S MIDI 1, not proof of an E16 input. Discover the E16 **input** with `aconnect -i` before sending CCs into a loaded script.

## Local captures and useful commands

Captures are in `backups/tr6s-baseline-20261116/`, ignored by Git and **not uploaded to GitHub**. `kit-001-candidate-baseline.bin` is the restored kit slot 1 reference. `pattern-000.bin` and `system.bin` are initial reads. The directory also holds before/after kit captures for each checked parameter; every completed panel change was reversed and the full kit matched its baseline. The same folder includes an E16 CC session with `e16-` prefixes: `e16-kit-001-fresh-baseline.bin` plus change/restore pairs for Reverb Time, OH Pan, and OH Delay Send. These files stay on this Pi only, so preserve them when changing workspaces.

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
| OH Pan | 654 | E16 ch 12 CC 70 value `82`: `A6` → `A4`; value `83` restored |
| OH Delay Send | 656 | E16 ch 12 CC 74 value `111`: `E0` → `DE`; value `112` restored |

`src/tr6s/kit.py` exposes those verified reads and separately labels TR-8S-derived candidate offsets for tone ID, remaining decay/pan/sends, level, and LFO. Do not treat candidate labels as verified. Selecting kit slot 1 changed kit slot 0 at offsets 392, 444, and 600, which fit physical fader level positions. Kit selection itself can refresh these bytes, so keep selection separate from a parameter diff.

An E16 session independently confirmed Reverb Time as well: channel 11 CC 3 value `5` changed only kit 1 byte 69 from `8` to `10`; value `4` restored the entire 1,312-byte blob. The same method verified OH Pan and OH Delay Send above.

## Next work: pattern read mapping

1. Read `docs/PROTOCOL.md` in this fork alongside the companion `docs/TR8S_STUDIO_PORT.md` and `tr6s-sysex-format.md`. The TR-8S pattern header and step layout are **candidates**. `src/tr6s/pattern.py` currently allows header reads but deliberately raises on shuffle and step offsets.
2. Done, from saved blobs only. `Pattern.inspect()`, `Pattern.diff()`, `inspect-pattern` (including `--file`), and `diff-pattern` read a 24,504-byte pattern. `verified` is empty. Name (0..15), tempo (16..17, tenths of a BPM), kit (18, TR-8S 1-based decoding), and scale (19) are candidates. Shuffle (32), the variation mask (48), steps, variations, and motion stay `not verified`. Diff ranges carry `offset`, `length`, `before`/`after` bytes, hex, `verified_field`, and `candidate_field`. Step labels use inherited TR-8S order `BD SD LT MT HT RS HC CH OH CC RC`, so the TR-8S OH label is not the compact sixth track. Unmapped bytes have a null candidate label. Writers stay disabled.
3. Hardware-blocked. When the user returns, agree on a safe pattern slot to edit. Save a fresh before-blob for **that slot**; do not assume the current selected pattern is slot 0 or that `pattern-000.bin` still reflects its state. Verify the sequencer is stopped.
4. Hardware-blocked. Ask for one reversible panel change, such as toggling one known BD step in variation A. Capture after, run `diff-pattern`, then ask for the same step to be toggled back and confirm the entire blob matches baseline. A second track near the end (OH) can distinguish compact TR-6S step order from retained TR-8S positions: a compact OH hit will not carry the candidate label `A_OH_step00_velocity`. Keep changes one at a time and record the exact selected variation and step number.
5. Hardware-blocked. Map header items (tempo, kit reference, scale, shuffle), variation blocks, steps, and motion only as evidence supports them. Promote a field from candidate to verified in code and docs after a clean differential capture. Leave writers blocked until a sufficiently complete map, backups, and an explicit safe write test plan exist. Upstream observed that even an uncommitted bulk send can alter a stored slot immediately.

If returning to kit work instead, the remaining high-value candidate checks are tone selection, instrument level, LFO, non-BD decay, and the still-unverified pan/send fields (OH Reverb Send, plus pan and sends on SD, LT, HC, and CH). Field stride is already supported by the verified OH pan and delay-send offsets. The standard live parameter SysEx map in the companion docs gives addresses and nibble-encoded values, **not positions in the opaque bulk kit blob**. Individual parameter RQ1 probes gave no reply in one attempt; use bulk differential reads as the established method.

For further E16 CC checks: find the E16 **input** with `aconnect -i` and confirm the loaded script receives external channel 11/12 CC there. Do not treat `28:0` as that input. Save a fresh kit slot 1 baseline, choose one mapped CC and a nearby value whose original setting is known, send the CC to the E16 input, read and diff the kit, then send the exact original CC value and require a whole-blob match. An ordinary TR-6S CC route can be checked the same way after confirming its receive channel and CC map. Stop on an unexpected diff or failure to restore; do not infer original CC values from the bulk byte until their scaling is verified.
