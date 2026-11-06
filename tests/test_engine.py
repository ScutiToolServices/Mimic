"""No real model/network: verify credentials, bounded output and safe failures."""
import base64
import json

import httpx
import pytest

from src.admin_api import Backends, ProbeError
from src.config import Settings
from src.engine import KittenModel, probe_voices
from src.errors import EngineFailed
from tests.test_service import clip


@pytest.mark.parametrize("status,words", [(401, "credential"), (403, "projects"), (404, "not found"), (409, "conflict"), (429, "busy"), (503, "unavailable")])
@pytest.mark.parametrize("operation", ["upload", "speak", "voices", "delete"])
async def test_model_errors_are_safe(tmp_path, status, words, operation):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(status, text="secret /home/model http://private")))
    model = KittenModel(Settings(data_dir=tmp_path, kitten2_admin_password="admin"), client=client)
    try:
        if status == 404 and operation == "delete":
            await model.delete("voice")
            return
        with pytest.raises(EngineFailed, match=words) as caught:
            if operation == "upload":
                await model.upload("voice", b"wav", "hi")
            elif operation == "delete":
                await model.delete("voice")
            elif operation == "voices":
                await model.list_voices()
            else:
                await model.synthesize("hi", "voice", None, "stable", True)
        assert all(value not in str(caught.value) for value in ("secret", "/home", "http://"))
    finally:
        await client.aclose()


@pytest.mark.parametrize("error,words", [(httpx.ReadTimeout("/secret"), "timed out"), (httpx.ConnectError("http://private"), "reach")])
async def test_connection_errors(tmp_path, error, words):
    def fail(request):
        raise error
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        model = KittenModel(Settings(data_dir=tmp_path), client=client)
        with pytest.raises(EngineFailed, match=words):
            await model.list_voices()


async def test_separate_credentials_and_wav_encoding(tmp_path):
    seen = []
    def reply(request):
        seen.append(request)
        if request.url.path == "/v1/speak":
            return httpx.Response(200, content=base64.b64decode(clip()), headers={"Content-Type": "audio/wav"})
        return httpx.Response(200, json={"voices": ["v"]})
    async def encode(data, executable):
        assert data.startswith(b"RIFF") and executable == "ffmpeg"
        return b"mp3"
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        model = KittenModel(Settings(data_dir=tmp_path, kitten2_token="speech", kitten2_admin_password="admin"), client=client, encoder=encode)
        await model.upload("v", b"wav", "hi")
        assert await model.list_voices() == ["v"]
        assert await model.synthesize("hi", "v", 3, "stable", False) == (b"mp3", 5)
        await model.delete("v")
    assert [r.headers["X-Internal-Token"] for r in seen] == ["admin", "speech", "speech", "admin"]
    assert json.loads(seen[2].content) == {"text": "hi", "voice": "v", "seed": 3, "preset": "stable", "normalize": False, "stream": False}


async def test_missing_model_admin_password_never_falls_back(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("No request expected"))) as client:
        model = KittenModel(Settings(data_dir=tmp_path, kitten2_token="speech"), client=client)
        with pytest.raises(EngineFailed, match="admin password"):
            await model.upload("v", b"wav", "hi")
        with pytest.raises(EngineFailed, match="admin password"):
            await model.delete("v")


async def test_saved_slot_is_read_live(tmp_path):
    seen = []
    def reply(request):
        seen.append((request.url.host, request.headers["X-Internal-Token"]))
        return httpx.Response(200, json={"voices": []})
    backends = Backends(tmp_path / "backends.json", {"kitten2": {"url": "http://old:9250", "token": "old"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        model = KittenModel(Settings(data_dir=tmp_path), backends=backends, client=client)
        await model.list_voices()
        backends.set("kitten2", "http://new:9250", "new")
        await model.list_voices()
    assert seen == [("old", "old"), ("new", "new")]


@pytest.mark.parametrize("body", [b"not WAV", b"RIFF"])
async def test_bad_model_audio_is_safe(tmp_path, body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))) as client:
        model = KittenModel(Settings(data_dir=tmp_path), client=client)
        with pytest.raises(EngineFailed, match="WAV"):
            await model.synthesize("hi", "v", None, "stable", True)
