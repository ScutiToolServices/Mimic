"""Private voice records and strict WAV validation. Call filesystem methods in workers."""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import re
import time
import uuid
import wave
from pathlib import Path

from src.errors import MimicError

MAX_CLIP_BYTES = 10 * 1024 * 1024
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,19}\Z")


def validate_name(name: str) -> None:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise MimicError("Voice name must be 1–20 ASCII letters, digits, dots, underscores or hyphens; start with a letter or digit.")


def decode_clip(audio: str) -> tuple[bytes, float]:
    if not isinstance(audio, str) or len(audio) > 4 * ((MAX_CLIP_BYTES + 2) // 3):
        raise MimicError("Reference WAV must be at most 10 MiB.")
    try:
        data = base64.b64decode(audio, validate=True)
    except (ValueError, binascii.Error):
        raise MimicError("Send strict base64 containing a PCM WAV recording.") from None
    if len(data) > MAX_CLIP_BYTES:
        raise MimicError("Reference WAV must be at most 10 MiB.")
    seconds = wav_duration(data)
    if not 5 <= seconds <= 30:
        raise MimicError("Reference WAV must last 5 to 30 seconds.")
    return data, seconds


def wav_duration(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            frames, channels, width, rate = wav.getnframes(), wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            if wav.getcomptype() != "NONE" or not frames or not rate or channels not in (1, 2):
                raise ValueError
            if len(wav.readframes(frames)) != frames * channels * width:
                raise ValueError
            return frames / rate
    except (wave.Error, EOFError, ValueError, OverflowError):
        raise MimicError("Recording must be a complete, uncompressed PCM WAV.") from None


class VoiceStore:
    """JSON is the durable state marker; pending/deleting voices are never public."""

    def __init__(self, root: Path):
        self.root = root

    def owner_dir(self, owner: str) -> Path:
        return self.root / hashlib.sha256(owner.encode()).hexdigest()

    def read(self, owner: str, name: str) -> dict | None:
        validate_name(name)
        try:
            return json.loads((self.owner_dir(owner) / f"{self._key(name)}.json").read_text("utf-8"))
        except FileNotFoundError:
            return None

    def list(self, owner: str) -> list[dict]:
        rows = []
        for path in self.owner_dir(owner).glob("*.json"):
            row = json.loads(path.read_text("utf-8"))
            if row["state"] == "active":
                rows.append(row)
        return sorted(rows, key=lambda row: row["name"])

    def save(self, owner: str, record: dict, data: bytes | None = None) -> None:
        folder = self.owner_dir(owner)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            folder.chmod(0o700)
        except OSError:
            pass
        name = self._key(record["name"])
        if data is not None:
            self._write(folder / f"{name}.wav", data)
        self._write(folder / f"{name}.json", json.dumps(record).encode())

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        temp = path.with_name(path.name + ".tmp")
        temp.write_bytes(data)
        try:
            temp.chmod(0o600)
        except OSError:
            pass
        os.replace(temp, path)

    @staticmethod
    def new(owner: str, name: str, transcript: str, duration: float) -> dict:
        prefix = hashlib.sha256(owner.encode()).hexdigest()[:32]
        return {"name": name, "model_voice": f"{prefix}--{name}--{uuid.uuid4().hex[:8]}",
                "transcript": transcript, "consent": True, "duration_s": duration,
                "created_at": time.time(), "state": "pending"}

    def remove(self, owner: str, name: str) -> None:
        folder = self.owner_dir(owner)
        key = self._key(name)
        (folder / f"{key}.wav").unlink(missing_ok=True)
        (folder / f"{key}.json").unlink(missing_ok=True)

    @staticmethod
    def _key(name: str) -> str:
        """Hash names for Windows reserved names, trailing dots and case sensitivity."""
        return hashlib.sha256(name.encode()).hexdigest()
