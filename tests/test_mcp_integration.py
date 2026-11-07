"""Real MCP JSON-RPC/session handling over in-process ASGI; no network sockets."""
import json

from starlette.testclient import TestClient

from src.app import build_app
from src.config import Settings
from tests.test_service import FakeModel, clip
from tests.seed import seed_token


def test_mcp_wire_metadata_isolation_lifecycle_and_consent(tmp_path):
    app = build_app(seed_token(Settings(data_dir=tmp_path, admin_password="admin"), "internal"), model=FakeModel())
    headers = {"X-Internal-Token": "internal", "Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://127.0.0.1:29404") as client:
        init = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
        assert init.status_code == 200
        headers["Mcp-Session-Id"] = init.headers["Mcp-Session-Id"]
        client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})

        def call(name, arguments, owner="ann"):
            params = {"name": name, "arguments": arguments}
            if owner is not None:
                params["_meta"] = {"requester": {"username": owner}}
            reply = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": params})
            assert reply.status_code == 200
            packets = [json.loads(line[6:]) for line in reply.text.splitlines() if line.startswith("data: ")]
            return next(packet["result"] for packet in packets if "result" in packet)

        clone = {"name": "anna", "audio": clip(), "transcript": "Hello.", "consent": True}
        denied = call("tool_mimic_cloneVoice", {**clone, "consent": False})
        assert denied["isError"] and "consent" in denied["content"][0]["text"]
        assert not call("tool_mimic_cloneVoice", clone)["isError"]
        bad = call("tool_mimic_speak", {"text": "Hi", "voice": "anna", "seed": "D:/private/path.wav"})
        assert bad["isError"] and "D:/private" not in json.dumps(bad)
        assert call("tool_mimic_listVoices", {}, None)["isError"]
        other = call("tool_mimic_listVoices", {}, "bo")
        assert json.loads(other["content"][0]["text"])["voices"] == []
        assert call("tool_mimic_speak", {"text": "Hi", "voice": "anna"}, "bo")["isError"]
        assert call("tool_mimic_deleteVoice", {"name": "anna"}, "bo")["isError"]
        assert not call("tool_mimic_cloneVoice", clone, "bo")["isError"]
        spoken = call("tool_mimic_speak", {"text": "Hi", "voice": "anna"})
        assert not spoken["isError"]
        result = json.loads(spoken["content"][0]["text"])
        assert result["voice"] == "anna" and result["file_id"]
        assert not call("tool_mimic_deleteVoice", {"name": "anna"})["isError"]
        assert call("tool_mimic_speak", {"text": "Hi", "voice": "anna"})["isError"]
        assert not call("tool_mimic_speak", {"text": "Hi", "voice": "anna"}, "bo")["isError"]
