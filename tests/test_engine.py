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


def slots(tmp_path, token="speech"):
    backends = Backends(tmp_path / "backends.json")
    backends.set("kitten2", "http://model:9250", token)
    return backends


@pytest.mark.parametrize("status,words", [(401, "credential"), (403, "projects"), (404, "not found"), (409, "conflict"), (429, "busy"), (503, "unavailable")])
@pytest.mark.parametrize("operation", ["upload", "speak", "voices", "delete"])
async def test_model_errors_are_safe(tmp_path, status, words, operation):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(status, text="secret /home/model http://private")))
    model = KittenModel(Settings(data_dir=tmp_path, kitten2_admin_password="admin"), slots(tmp_path), client=client)
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
        model = KittenModel(Settings(data_dir=tmp_path), slots(tmp_path), client=client)
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
        model = KittenModel(Settings(data_dir=tmp_path, kitten2_admin_password="admin"), slots(tmp_path), client=client, encoder=encode)
        await model.upload("v", b"wav", "hi")
        assert await model.list_voices() == ["v"]
        assert await model.synthesize("hi", "v", 3, "stable", False) == (b"mp3", 5)
        await model.delete("v")
    assert [r.headers["X-Internal-Token"] for r in seen] == ["admin", "speech", "speech", "admin"]
    assert json.loads(seen[2].content) == {"text": "hi", "voice": "v", "seed": 3, "preset": "stable", "normalize": False, "stream": False}


async def test_missing_model_admin_password_never_falls_back(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("No request expected"))) as client:
        model = KittenModel(Settings(data_dir=tmp_path), slots(tmp_path), client=client)
        with pytest.raises(EngineFailed, match="admin password"):
            await model.upload("v", b"wav", "hi")
        with pytest.raises(EngineFailed, match="admin password"):
            await model.delete("v")


async def test_saved_slot_is_read_live(tmp_path):
    seen = []
    def reply(request):
        seen.append((request.url.host, request.headers["X-Internal-Token"]))
        return httpx.Response(200, json={"voices": []})
    backends = slots(tmp_path, "old")
    backends.set("kitten2", "http://old:9250", "old")
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        model = KittenModel(Settings(data_dir=tmp_path), backends=backends, client=client)
        await model.list_voices()
        backends.set("kitten2", "http://new:9250", "new")
        await model.list_voices()
    assert seen == [("old", "old"), ("new", "new")]


@pytest.mark.parametrize("body", [b"not WAV", b"RIFF"])
async def test_bad_model_audio_is_safe(tmp_path, body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))) as client:
        model = KittenModel(Settings(data_dir=tmp_path), slots(tmp_path), client=client)
        with pytest.raises(EngineFailed, match="WAV"):
            await model.synthesize("hi", "v", None, "stable", True)


async def test_the_audio8_slot_uses_its_own_address_token_and_payload(tmp_path):
    seen = []

    def handler(req):
        seen.append((str(req.url), req.headers["x-internal-token"], json.loads(req.content or b"{}")))
        return httpx.Response(200, content=base64.b64decode(clip()))

    backends = Backends(tmp_path / "b.json")
    backends.set("audio8", "http://gpu:9200", "g")
    backends.set("kitten2", "http://cpu:9250", "c")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        async def encode(wav, ffmpeg):
            return b"mp3"
        model = KittenModel(Settings(data_dir=tmp_path, audio8_admin_password="a8"), backends=backends, client=client, encoder=encode, slot="audio8")
        await model.synthesize("hi", "v", 3, "expressive", False)
        await model.upload("v", b"wav", "hi")
    assert seen[0] == ("http://gpu:9200/v1/speak", "g", {"text": "hi", "voice": "v", "seed": 3, "stream": False})
    assert seen[1][:2] == ("http://gpu:9200/admin/voices/v", "a8")


async def test_without_a_saved_connection_the_model_is_not_called(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("No request expected"))) as client:
        model = KittenModel(Settings(data_dir=tmp_path), Backends(tmp_path / "none.json"), client=client)
        with pytest.raises(EngineFailed, match="admin page"):
            await model.list_voices()
