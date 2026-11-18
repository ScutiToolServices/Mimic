"""Keep only the dominant voice of a voice-clone reference WAV. A reference must be one speaker; a second voice or a TV
in the background poisons the clone. No enrolled voice is used here (the speaker is whoever is being cloned): the voice
that speaks most is kept, other speech segments are silenced and the clip keeps its length. Blocking: call in a worker.
Needs the optional "voice" extra (numpy, onnxruntime) and a speaker model at <voice_dir>/speaker.onnx."""

from __future__ import annotations

import io
import wave
from pathlib import Path

from src.errors import MimicError

MIN_KEPT_S = 5.0  # a reference must hold at least this much of the main voice (Mimic accepts 5 to 30 s clips)


def clean_reference(data: bytes, voice_dir: Path, threshold: float) -> tuple[bytes, str]:
    """(WAV, note). The note says what happened, or why the gate did not run; the clip then is the original."""
    try:
        import numpy as np
        from src.voicegate import RATE, build_embedder, dominant_voiceprint, drop_ranges, speech_seconds
    except ImportError:
        return data, " Voice gate skipped: the voice extra is not installed."
    embed = build_embedder(voice_dir / "speaker.onnx")
    if embed is None:
        return data, " Voice gate skipped: no speaker model is set up on this service."
    with wave.open(io.BytesIO(data), "rb") as wav:
        channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        return data, " Voice gate skipped: only 16-bit recordings are supported."
    samples = np.frombuffer(frames, dtype="<i2").reshape(-1, channels)
    mono = samples.astype(np.float32).mean(axis=1) / 32768
    if rate != RATE:  # analysis copy only; the clip itself keeps its rate (shortcut: linear interpolation, fine for judging a voice)
        mono = np.interp(np.arange(int(len(mono) * RATE / rate)) * rate / RATE, np.arange(len(mono)), mono).astype(np.float32)
    voiceprint = dominant_voiceprint(mono, embed)
    drop = drop_ranges(mono, voiceprint, embed, threshold) if voiceprint is not None else []
    if not drop:
        return data, " Voice gate ran: no other voice found."
    kept_s = speech_seconds(mono) - sum(b - a for a, b in drop) / RATE  # speech left, not clip length
    if kept_s < MIN_KEPT_S:
        raise MimicError("After keeping only the main voice, less than 5 seconds of it are left. Send a cleaner recording of one speaker.")
    cleaned = samples.copy()
    for a, b in drop:
        cleaned[int(a * rate / RATE): int(b * rate / RATE)] = 0
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(cleaned.astype("<i2").tobytes())
    return out.getvalue(), f" Voice gate removed {sum(b - a for a, b in drop) / RATE:.1f} s of other voices."
