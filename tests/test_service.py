"""Behavioral tests use a fake model and real owner-scoped persistence."""
import base64
import io
import re
import wave
from dataclasses import replace

import pytest

from src.config import Settings
from src.errors import MimicError
from src.service import MimicService


def clip(seconds=5):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * int(8000 * seconds))
    return base64.b64encode(stream.getvalue()).decode()


class FakeModel:
    def __init__(self):
        self.voices = {}
        self.calls = []
        self.fail = False

    async def upload(self, name, audio, transcript):
        self.calls.append(("upload", name))
        if self.fail:
            raise MimicError("Model unavailable (503).")
        self.voices[name] = (audio, transcript)

    async def delete(self, name):
        self.calls.append(("delete", name))
        if self.fail:
            raise MimicError("Model unavailable (503).")
        self.voices.pop(name, None)

    async def synthesize(self, text, voice, seed, preset, normalize):
        assert voice in self.voices
        self.calls.append(("speak", voice, seed, preset, normalize))
        return b"mp3:" + text.encode(), 1.0


@pytest.fixture
def service(tmp_path):
    return MimicService(Settings(data_dir=tmp_path), FakeModel())


async def test_consent_refusal_has_no_side_effects(service, tmp_path):
    for consent in (False, "true", 1):
        with pytest.raises(MimicError, match="consent"):
            await service.clone_voice("ann", "anna", clip(), "Hello.", consent)
    assert not service.model.calls
    assert not list(tmp_path.rglob("*.wav"))


@pytest.mark.parametrize("audio", [clip(4.9), clip(30.1), base64.b64encode(b"not WAV").decode(), "%%%", clip()[:-12], "A" * (14 * 1024 * 1024)])
async def test_bad_clip_rejected_before_upload(service, audio):
    with pytest.raises(MimicError):
        await service.clone_voice("ann", "anna", audio, "Hello.", True)
    assert not service.model.calls


@pytest.mark.parametrize("seconds", [5, 30])
async def test_duration_boundaries(service, seconds):
    result = await service.clone_voice("ann", "anna", clip(seconds), "Hello.", True)
    assert result.duration_s == seconds


async def test_upload_then_speak_list_and_delete(service, tmp_path):
    cloned = await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", cloned.model_voice)
    assert "ann" not in cloned.model_voice.split("--")[0]
    listed = await service.list_voices("ann")
    assert [(v.name, v.duration_s) for v in listed.voices] == [("anna", 5)]
    assert listed.voices[0].created_at
    assert b"Hello." in next(tmp_path.rglob("voices/*/*.json")).read_bytes()
    assert next(tmp_path.rglob("*.wav")).read_bytes().startswith(b"RIFF")
    spoken = await service.speak("ann", "Hello.", "anna", 42, "expressive", False)
    assert spoken.size_bytes > 0 and not spoken.cached
    assert service.model.calls[-1] == ("speak", cloned.model_voice, 42, "expressive", False)
    await service.delete_voice("ann", "anna")
    assert not (await service.list_voices("ann")).voices
    assert cloned.model_voice not in service.model.voices
    with pytest.raises(MimicError):
        await service.speak("ann", "Hello.", "anna")


async def test_every_tool_is_owner_scoped(service):
    first = await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    assert not (await service.list_voices("bo")).voices
    with pytest.raises(MimicError):
        await service.speak("bo", "Hello.", "anna")
    with pytest.raises(MimicError):
        await service.delete_voice("bo", "anna")
    second = await service.clone_voice("bo", "anna", clip(), "Hello.", True)
    assert first.model_voice != second.model_voice
    await service.delete_voice("bo", "anna")
    assert len((await service.list_voices("ann")).voices) == 1
    spoken = await service.speak("ann", "Hello.", "anna")
    assert await service.audio("bo", spoken.file_id) is None
    assert await service.audio("ann", spoken.file_id) is not None
    for owner in ("", "  "):
        for call in (service.list_voices(owner), service.speak(owner, "hi", "anna"), service.delete_voice(owner, "anna"), service.clone_voice(owner, "anna", clip(), "Hello.", True)):
            with pytest.raises(MimicError, match="signed-in"):
                await call


@pytest.mark.parametrize("name", ["../anna", "a/b", "a\\b", "", "a" * 21, "é", " anna", ".anna"])
async def test_names_cannot_escape_storage(service, name):
    with pytest.raises(MimicError):
        await service.clone_voice("../ann", name, clip(), "Hello.", True)


async def test_pending_upload_and_delete_retry(service):
    service.model.fail = True
    with pytest.raises(MimicError):
        await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    assert not (await service.list_voices("ann")).voices
    service.model.fail = False
    first = await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    assert service.model.calls[0][1] == first.model_voice
    with pytest.raises(MimicError, match="exists"):
        await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    service.model.fail = True
    with pytest.raises(MimicError):
        await service.delete_voice("ann", "anna")
    assert not (await service.list_voices("ann")).voices
    service.model.fail = False
    await service.delete_voice("ann", "anna")
    second = await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    assert first.model_voice != second.model_voice


async def test_seeded_cache_is_private_and_unseeded_calls_are_fresh(service):
    await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    one = await service.speak("ann", "Hello.", "anna", 42)
    two = await service.speak("ann", "Hello.", "anna", 42)
    assert one.file_id == two.file_id and two.cached
    three = await service.speak("ann", "Hello.", "anna")
    four = await service.speak("ann", "Hello.", "anna")
    assert three.file_id != four.file_id


async def test_quota_is_enforced(service):
    service = MimicService(replace(service.settings, quota_bytes=1), service.model)
    await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    with pytest.raises(MimicError, match="storage"):
        await service.speak("ann", "Hello.", "anna")


class LabelledModel(FakeModel):
    def __init__(self, label):
        super().__init__()
        self.label = label

    async def synthesize(self, text, voice, seed, preset, normalize):
        mp3, seconds = await super().synthesize(text, voice, seed, preset, normalize)
        return self.label.encode() + mp3, seconds


async def test_a_voice_stays_on_the_model_chosen_when_it_was_cloned(tmp_path):
    kitten, audio8 = LabelledModel("k:"), LabelledModel("a:")
    svc = MimicService(Settings(data_dir=tmp_path), {"kitten2": kitten, "audio8": audio8})
    cloned = await svc.clone_voice("ana", "gpu", clip(), "hello", True, "audio8")
    await svc.clone_voice("ana", "cpu", clip(), "hello", True)
    assert cloned.model == "audio8" and len(audio8.voices) == 1 and len(kitten.voices) == 1
    assert {v.name: v.model for v in (await svc.list_voices("ana")).voices} == {"gpu": "audio8", "cpu": "kitten2"}
    spoken = await svc.speak("ana", "Hi there", "gpu", seed=1)
    assert svc.store.get("ana", spoken.file_id) and [c[0] for c in audio8.calls] == ["upload", "speak"]
    assert [c[0] for c in kitten.calls] == ["upload"]
    await svc.delete_voice("ana", "gpu")
    assert not audio8.voices and len(kitten.voices) == 1


async def test_unknown_model_and_kitten_only_options_on_audio8_are_refused(tmp_path):
    svc = MimicService(Settings(data_dir=tmp_path), {"kitten2": FakeModel(), "audio8": FakeModel()})
    with pytest.raises(MimicError, match="Unknown model"):
        await svc.clone_voice("ana", "v", clip(), "hello", True, "nope")
    await svc.clone_voice("ana", "v", clip(), "hello", True, "audio8")
    with pytest.raises(MimicError, match="only to kitten2"):
        await svc.speak("ana", "Hi", "v", preset="expressive")
    with pytest.raises(MimicError, match="only to kitten2"):
        await svc.speak("ana", "Hi", "v", normalize=False)
