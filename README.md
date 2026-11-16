# TR-6S Studio (port in progress)

This is a work-in-progress adaptation of [ideaCompany/tr8s-studio](https://github.com/ideaCompany/tr8s-studio) for the Roland TR-6S. The code snapshot comes from upstream commit `a62ae22c5f7816a75db61722fc006c536d4f096b` and retains its MIT license.

The first verified layer is read-only SysEx transport. The model ID is `00 00 00 6D`, and bulk reads use the measured TR-6S sizes: system 754 bytes, pattern 24,599 bytes, and kit 1,317 bytes. These values and the utility addresses were verified on firmware 1.51 / revision 0BDE in the companion [TR-6S port notes](../oxi-e16-lua-scripts/docs/TR8S_STUDIO_PORT.md).

## Read a raw blob

Install this package in a Python environment, then run:

```sh
tr6s info
tr6s read-blob pattern 0 /tmp/tr6s-pattern-000.bin
tr6s read-blob kit 0 /tmp/tr6s-kit-000.bin
tr6s read-blob system 0 /tmp/tr6s-system.bin
```

The device must be stopped for a bulk read. Set `TR6S_PORT` to the ALSA rawmidi node if automatic discovery does not find it. The output path must not already exist.

## Current limits

TR-8S Studio's pattern and kit editors still use TR-8S offsets. The TR-6S blobs have different lengths, and their internal offsets have not been established through differential captures. Bulk writes, commits, sample uploads, and tone deletion are disabled in the transport. The web interface and the remaining tool commands have not yet been adapted or validated for the TR-6S. Do not treat them as a working TR-6S editor.

The next step is to capture pairs of TR-6S blobs around one panel change at a time and map the pattern and kit fields. See the port notes linked above for the proposed sequence and cautions.

## Source transfer note

This workspace could not reach GitHub from the shell. The local tree was reconstructed from upstream text files through the GitHub connector, rather than cloned with Git. Upstream binary screenshots, MIDI examples, and test fixtures are absent. The `upstream` remote records the source URL, but this is not a GitHub fork yet.
