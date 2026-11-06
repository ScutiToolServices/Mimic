"""Concurrency, portable persistence and failure recovery checks."""
import asyncio
import base64
import io
import threading
import wave

import httpx
import pytest

from src.config import Settings
from src.engine import KittenModel, encode_mp3, probe_voices
from src.errors import EngineFailed, MimicError
from src.service import MimicService, worker
from tests.test_service import FakeModel, clip


async def test_case_sensitive_names_and_windows_reserved_names(tmp_path):
    service = MimicService(Settings(data_dir=tmp_path), FakeModel())
    for name in ("Anna", "anna", "CON", "aux."):
        await service.clone_voice("Ann", name, clip(), "Hello.", True)
    assert {v.name for v in (await service.list_voices("Ann")).voices} == {"Anna", "anna", "CON", "aux."}
    await service.delete_voice("Ann", "anna")
    await service.speak("Ann", "Hi", "Anna")


async def test_service_survives_restart(tmp_path):
    model = FakeModel()
    first = MimicService(Settings(data_dir=tmp_path), model)
    await first.clone_voice("ann", "anna", clip(), "Hello.", True)
    second = MimicService(Settings(data_dir=tmp_path), model)
    assert len((await second.list_voices("ann")).voices) == 1
    assert (await second.speak("ann", "Hi", "anna")).size_bytes


async def test_delete_waits_for_speech_then_removes_voice(tmp_path):
    entered, finish = asyncio.Event(), asyncio.Event()
    class SlowModel(FakeModel):
        async def synthesize(self, *args):
            entered.set()
            await finish.wait()
            return await super().synthesize(*args)
    model = SlowModel()
    service = MimicService(Settings(data_dir=tmp_path), model)
    await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    speech = asyncio.create_task(service.speak("ann", "Hi", "anna"))
    await entered.wait()
    deletion = asyncio.create_task(service.delete_voice("ann", "anna"))
    await asyncio.sleep(0)
    assert not deletion.done()
    finish.set()
    assert (await speech).size_bytes
    await deletion
    assert not (await service.list_voices("ann")).voices


async def test_storage_errors_never_expose_paths(tmp_path, monkeypatch):
    service = MimicService(Settings(data_dir=tmp_path), FakeModel())
    def fail(*args):
        raise OSError("denied D:/private/speaker.wav")
    monkeypatch.setattr(service.voices, "save", fail)
    with pytest.raises(MimicError) as caught:
        await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    assert "D:/" not in str(caught.value) and "speaker" not in str(caught.value)


async def test_existing_audio_download_does_not_wait_for_synthesis(tmp_path):
    entered, finish = asyncio.Event(), asyncio.Event()
    class SlowModel(FakeModel):
        slow = False
        async def synthesize(self, *args):
            if self.slow:
                entered.set()
                await finish.wait()
            return await super().synthesize(*args)
    model = SlowModel()
    service = MimicService(Settings(data_dir=tmp_path), model)
    await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    ready = await service.speak("ann", "Hi", "anna")
    model.slow = True
    pending = asyncio.create_task(service.speak("ann", "Slow", "anna"))
    await entered.wait()
    try:
        stored = await asyncio.wait_for(service.audio("ann", ready.file_id), timeout=0.5)
        assert stored is not None
    finally:
        finish.set()
        await pending


async def test_voice_list_does_not_wait_for_synthesis(tmp_path):
    entered, finish = asyncio.Event(), asyncio.Event()
    class SlowModel(FakeModel):
        async def synthesize(self, *args):
            entered.set()
            await finish.wait()
            return await super().synthesize(*args)
    service = MimicService(Settings(data_dir=tmp_path), SlowModel())
    await service.clone_voice("ann", "anna", clip(), "Hello.", True)
    pending = asyncio.create_task(service.speak("ann", "Hi", "anna"))
    await entered.wait()
    try:
        result = await asyncio.wait_for(service.list_voices("ann"), timeout=0.5)
        assert [voice.name for voice in result.voices] == ["anna"]
    finally:
        finish.set()
        await pending


async def test_real_ffmpeg_encodes_local_generated_wav():
    import shutil
    if not await asyncio.to_thread(shutil.which, "ffmpeg"):
        pytest.skip("ffmpeg not installed")
    result = await encode_mp3(base64.b64decode(clip()), "ffmpeg")
    assert len(result) > 100 and (result.startswith(b"ID3") or result[0] == 255)


async def test_cancelled_file_worker_finishes_before_returning():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def operation():
        started.set()
        release.wait(5)
        finished.set()
    task = asyncio.create_task(worker(operation))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


@pytest.mark.parametrize("transcript", ["", "  ", "a" * 2001])
async def test_invalid_transcript(tmp_path, transcript):
    service = MimicService(Settings(data_dir=tmp_path), FakeModel())
    with pytest.raises(MimicError, match="transcript"):
        await service.clone_voice("ann", "anna", clip(), transcript, True)


async def test_encoder_failure_hides_stderr(monkeypatch):
    class Process:
        returncode = 1
        async def communicate(self, data=None):
            return b"", b"error D:/private/clip.wav"
    async def spawn(*args, **kwargs):
        return Process()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(EngineFailed) as caught:
        await encode_mp3(b"wav", "ffmpeg")
    assert "D:/" not in str(caught.value)


async def test_encoder_missing_is_safe(monkeypatch):
    async def spawn(*args, **kwargs):
        raise FileNotFoundError("D:/private/ffmpeg.exe")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(EngineFailed, match="could not be started"):
        await encode_mp3(b"wav", "ffmpeg")


async def test_model_probe_uses_service_token(monkeypatch):
    import src.admin_api
    real_client = httpx.AsyncClient
    seen = []
    def reply(request):
        seen.append(request)
        return httpx.Response(200, json={"voices": ["v"]})
    monkeypatch.setattr(src.admin_api.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(reply), **kw))
    assert "1 voice" in await probe_voices("http://model:9250", "speech")
    assert seen[0].url.path == "/v1/voices" and seen[0].headers["X-Internal-Token"] == "speech"
