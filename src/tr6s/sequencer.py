"""Read-only TR-6S SysEx over ALSA sequencer, alongside existing MIDI routes."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .transport import BLOB_SIZES, DT1, GET_OFFSETS, TransportError, checksum, encode7, make_sysex, unpack7


def find_port() -> str:
    override = os.environ.get("TR6S_SEQ_PORT")
    if override:
        return override
    result = subprocess.run(["aconnect", "-l"], capture_output=True, text=True, check=True)
    client = None
    for line in result.stdout.splitlines():
        match = re.match(r"client\s+(\d+):\s+'([^']+)'", line)
        if match:
            client = int(match[1]) if "TR-6S" in match[2].upper() else None
            continue
        match = re.match(r"\s+(\d+)\s+'([^']+)'", line)
        if client is not None and match and "MIDI 1" in match[2].upper():
            return f"{client}:{int(match[1])}"
    raise TransportError("TR-6S MIDI 1 sequencer port not found")


def _variable_length(value: int) -> bytes:
    out = bytearray((value & 0x7F,))
    value >>= 7
    while value:
        out.insert(0, 0x80 | (value & 0x7F))
        value >>= 7
    return bytes(out)


def _midi_file(message: bytes) -> bytes:
    event = message[1:]
    track = b"\0\xF0" + _variable_length(len(event)) + event + b"\0\xFF\x2F\0"
    return b"MThd\0\0\0\x06\0\0\0\x01\0\x60MTrk" + len(track).to_bytes(4, "big") + track


class SequencerTransport:
    def __init__(self, port: str | None = None):
        self.port = port or find_port()
        self.process = None
        self._text = ""
        self._pending = bytearray()

    def __enter__(self):
        self.process = subprocess.Popen(
            ["stdbuf", "-oL", "aseqdump", "-p", self.port],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        os.set_blocking(self.process.stdout.fileno(), False)
        time.sleep(0.05)
        if self.process.poll() is not None:
            raise TransportError(self.process.stderr.read().decode(errors="replace").strip())
        return self

    def __exit__(self, *_):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def _send(self, message: bytes):
        with tempfile.TemporaryDirectory(prefix="tr6s-midi-") as directory:
            path = Path(directory) / "request.mid"
            path.write_bytes(_midi_file(message))
            result = subprocess.run(["aplaymidi", "-p", self.port, str(path)],
                                    capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise TransportError((result.stderr or result.stdout).strip())

    def _messages(self):
        try:
            chunk = os.read(self.process.stdout.fileno(), 65536)
        except BlockingIOError:
            return []
        if not chunk:
            return []
        self._text += chunk.decode(errors="replace")
        lines = self._text.split("\n")
        self._text = lines.pop()
        messages = []
        for line in lines:
            message = self._parse_line(line)
            if message is not None:
                messages.append(message)
        return messages

    def _parse_line(self, line: str) -> bytes | None:
        if "System exclusive" not in line:
            return None
        # Remove aseqdump's client:port prefix before searching for hex bytes.
        line = line.split("System exclusive", 1)[1]
        if not self._pending:
            start = re.search(r"\bF0\b", line, re.IGNORECASE)
            if not start:
                return None
            line = line[start.start():]
        for token in re.findall(r"\b[0-9A-Fa-f]{2}\b", line):
            byte = int(token, 16)
            self._pending.append(byte)
            if byte == 0xF7:
                message = bytes(self._pending)
                self._pending.clear()
                return message
        return None

    def _exchange(self, address: tuple[int, ...], data: bytes, expected: int | None,
                  timeout: float = 30.0) -> bytes:
        self._messages()  # drain stale reply text
        self._send(make_sysex(DT1, address, data))
        out = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            messages = self._messages()
            for message in messages:
                if (len(message) < 15 or message[:3] != b"\xF0\x41\x10"
                        or message[3:7] != b"\0\0\0\x6D" or message[7] != DT1
                        or checksum(message[8:-2]) != message[-2]):
                    continue
                if expected is None and message[8:12] == bytes(address):
                    return message[12:-2]
                if expected is not None and message[8:11] == b"\x50\0\x01":
                    out += unpack7(message[12:-2])
                    if len(out) >= expected:
                        return bytes(out[:expected])
            if not messages:
                time.sleep(0.005)
        raise TransportError(f"incomplete reply: {len(out)} of {expected} bytes")

    def utility(self, offset: int) -> bytes:
        return self._exchange((0x50, 0, 0, offset), b"\0", None, timeout=3)

    def info(self) -> dict:
        version = self.utility(0x13).decode("ascii", "replace")
        playing = self.utility(0x10)[0]
        return {"port": self.port, "version": version[:4],
                "revision": version[4:8], "playing": bool(playing)}

    def read_blob(self, kind: str, slot: int) -> bytes:
        if kind not in BLOB_SIZES:
            raise TransportError(f"{kind} bulk read is not verified on TR-6S")
        if self.utility(0x10)[0]:
            raise TransportError("stop TR-6S playback before a bulk read")
        return self._exchange((0x50, 0, 0, GET_OFFSETS[kind]),
                              bytes(encode7(slot, 4) + encode7(1, 4)),
                              BLOB_SIZES[kind])
