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
```

The device must be stopped for a bulk read. The CLI uses the TR-6S MIDI 1 ALSA sequencer port so it can coexist with the Pi's MIDI router and connected E16. Set `TR6S_SEQ_PORT` to a `client:port` value if automatic discovery does not find it. The output path must not already exist.

## Current limits

TR-8S Studio's pattern and kit editors still use TR-8S offsets. The TR-6S blobs have the same lengths, but their internal offsets have not been established through differential captures. Bulk writes, commits, sample uploads, and tone deletion are disabled in the transport. The web interface and the remaining tool commands have not yet been adapted or validated for the TR-6S. Do not treat them as a working TR-6S editor.

The next step is to capture pairs of TR-6S blobs around one panel change at a time and map the pattern and kit fields. See the port notes linked above for the proposed sequence and cautions.

## Source

This is a GitHub fork of `ideaCompany/tr8s-studio` at upstream commit `a62ae22c5f7816a75db61722fc006c536d4f096b`. The original binary assets and test fixtures are retained in the fork.
