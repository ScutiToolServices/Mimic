import io
import wave

import pytest

np = pytest.importorskip("numpy")  # optional extra "voice"

from src import voicegate  # noqa: E402
from src.errors import MimicError  # noqa: E402
from src.refclean import clean_reference  # noqa: E402

RATE = 16000


def tone(hz, seconds):
    t = np.arange(int(seconds * RATE)) / RATE
    return (0.3 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def wav_of(*parts):
    pcm = (np.concatenate(parts) * 32768).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return out.getvalue()


def samples_of(data):
    with wave.open(io.BytesIO(data)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2")


def embed(samples):
    spectrum = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(len(samples), 1 / RATE)
    return np.array([spectrum[abs(freqs - 200) < 20].sum(), spectrum[abs(freqs - 800) < 20].sum()])


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    monkeypatch.setattr(voicegate, "build_embedder", lambda path: embed)


def test_other_voice_is_silenced_and_length_kept(tmp_path):
    quiet = np.zeros(int(0.5 * RATE), dtype=np.float32)
    data = wav_of(tone(200, 4), quiet, tone(800, 1.5), quiet, tone(200, 3))
    cleaned, note = clean_reference(data, tmp_path, 0.4)
    out = samples_of(cleaned)
    assert len(out) == len(samples_of(data))
    assert not out[int(4.6 * RATE):int(5.9 * RATE)].any() and out[:int(3.9 * RATE)].any()
    assert "removed" in note


def test_single_voice_is_untouched(tmp_path):
    data = wav_of(tone(200, 6))
    assert clean_reference(data, tmp_path, 0.4)[0] == data


def test_too_little_main_voice_left_is_refused(tmp_path):
    quiet = np.zeros(int(0.5 * RATE), dtype=np.float32)
    data = wav_of(tone(200, 3), quiet, tone(800, 1.5), quiet, tone(200, 1.2))
    with pytest.raises(MimicError):
        clean_reference(data, tmp_path, 0.4)
