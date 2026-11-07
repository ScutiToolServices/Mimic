"""In-process HTTP and MCP calls exercise authentication and ownership without sockets."""
import base64
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from mcp.types import RequestParams

from src.app import build_app
from src.config import Settings
from tests.test_service import FakeModel, clip
from tests.seed import seed_token

TOKEN = {"X-Internal-Token": "internal", "X-Requester-Username": "ann"}
PW = {"X-Admin-Password": "admin"}


@pytest.fixture
def app(tmp_path):
    return build_app(seed_token(Settings(data_dir=tmp_path, admin_password="admin"), "internal"), model=FakeModel())


async def test_api_lifecycle_and_owner_checks(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for method, path in [("GET", "/api/voices"), ("POST", "/api/voices"), ("DELETE", "/api/voices/anna"), ("POST", "/api/speak"), ("GET", "/api/files/id"), ("POST", "/mcp")]:
            assert (await client.request(method, path)).status_code == 401
        assert (await client.get("/api/voices", headers={"X-Internal-Token": "internal"})).status_code == 401
        assert (await client.get("/health")).status_code == 200
        body = {"name": "anna", "audio": clip(), "transcript": "Hello.", "consent": True}
        assert (await client.post("/api/voices", headers=TOKEN, json={**body, "consent": False})).status_code == 400
        assert (await client.post("/api/voices", headers=TOKEN, json=body)).status_code == 200
        assert (await client.get("/api/voices", headers=TOKEN)).json()["voices"] == ["anna"]
        result = (await client.post("/api/speak", headers=TOKEN, json={"text": "Hello.", "voice": "anna"})).json()
        path = f"/api/files/{result['file_id']}"
        audio = await client.get(path, headers=TOKEN)
        assert audio.status_code == 200 and audio.content == b"mp3:Hello."
        assert audio.headers["cache-control"] == "private, no-store"
        other = {**TOKEN, "X-Requester-Username": "bo"}
        assert (await client.get(path, headers=other)).status_code == 404
        assert (await client.get("/api/voices", headers=other)).json()["voices"] == []
        assert (await client.post("/api/speak", headers=other, json={"text": "hi", "voice": "anna"})).status_code == 400
        assert (await client.delete("/api/voices/anna", headers=other)).status_code == 400
        assert (await client.delete("/api/voices/anna", headers=TOKEN)).status_code == 200
        usage = (await client.get("/admin/status", headers=PW)).json()["usage"]
        assert usage["calls"] >= 7 and usage["errors"] >= 3


async def test_admin_settings_and_slot(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/admin/settings")).status_code == 401
        assert (await client.get("/admin/", headers=PW)).status_code == 200
        changed = await client.put("/admin/settings", headers=PW, json={"values": {"max_chars": 3}})
        assert changed.status_code == 200
        assert (app.state.settings.data_dir / "settings.json").exists()
        await app.state.service.clone_voice("ann", "anna", clip(), "Hello.", True)
        result = await client.post("/api/speak", headers=TOKEN, json={"text": "Hello", "voice": "anna"})
        assert result.status_code == 400 and "limit is 3" in result.text
        slot = (await client.get("/admin/backends", headers=PW)).json()["backends"][0]
        assert slot["key"] == "kitten2" and slot["local"] is False
        assert (await client.put("/admin/backends/kitten2", headers=PW, json={"url": ""})).status_code == 422
        assert (await client.put("/admin/settings", headers=PW, json={"values": {"max_chars": 5001}})).status_code == 422
        assert (await client.put("/admin/settings", headers=PW, json={"values": []})).status_code == 422


async def test_admin_disabled_without_password(tmp_path):
    app = build_app(Settings(data_dir=tmp_path), model=FakeModel())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/admin/")).status_code == 404


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.2"])
def test_exposed_bind_requires_token(tmp_path, host):
    with pytest.raises(ValueError, match="SERVICE_ADMIN_PASSWORD"):
        build_app(Settings(data_dir=tmp_path, host=host), model=FakeModel())


async def test_tools_use_requester_and_have_consent_descriptions(app):
    mcp = app.state.mcp
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names == {"tool_mimic_cloneVoice", "tool_mimic_listVoices", "tool_mimic_speak", "tool_mimic_deleteVoice"}
    assert all("consent" in tool.description.lower() for tool in tools)
    # Exercise registered handlers with a real metadata model through FastMCP's manager.
    def context(owner):
        meta = RequestParams.Meta.model_validate({"requester": {"username": owner}})
        return SimpleNamespace(request_context=SimpleNamespace(meta=meta), report_progress=progress)
    async def progress(*args, **kwargs):
        pass
    manager = mcp._tool_manager
    async def call(name, args, owner="ann"):
        return await manager.call_tool(name, args, context=context(owner), convert_result=False)
    cloned = await call("tool_mimic_cloneVoice", {"name": "anna", "audio": clip(), "transcript": "Hello.", "consent": True})
    assert cloned.name == "anna"
    assert not (await call("tool_mimic_listVoices", {}, "bo")).voices
    for name, args in [("tool_mimic_speak", {"text": "hi", "voice": "anna"}), ("tool_mimic_deleteVoice", {"name": "anna"})]:
        with pytest.raises(Exception, match="belongs to you"):
            await call(name, args, "bo")
    with pytest.raises(Exception, match="signed-in"):
        await call("tool_mimic_listVoices", {}, "")
