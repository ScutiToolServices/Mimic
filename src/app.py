"""MCP tools, owned MP3 downloads and Bard's shared admin shell."""
from __future__ import annotations

import asyncio
import hmac
import os
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from src.admin_api import Slot, Usage, register
from src.admin_bridge import AdminRefreshMiddleware, CachedBackends
from src.config import PROJECT_DIR, Settings
from src.contract import CloneResult, DeleteResult, SpeakResult, VoiceList
from src.engine import KittenModel, probe_voices
from src.errors import EngineFailed, IdentityRequired, MimicError, QuotaExceeded
from src.identity import owner_from_context
from src.middleware import InternalTokenMiddleware
from src.mcp_api import PublicToolError, SafeFastMCP
from src.options import live, make_config
from src.service import MimicService, Model, worker

INSTRUCTIONS = (
    "Clone voices only with the speaker's consent. Recordings must be one speaker, PCM WAV, 5–30 seconds, "
    "with an exact transcript. All tools use the requester's private voices. Audio is synthetic. "
    "CPU speech is slow (about 0.1–0.2 times real time); wait for completion. "
    "tool_mimic_speak returns an audio file for chat playback."
)
PLAYGROUND = {"operations": [{
    "label": "Speak in a consented cloned voice", "route": "/api/speak", "method": "POST", "encoding": "json", "response": "json",
    "fields": [
        {"key": "X-Requester-Username", "label": "Requester username", "type": "text", "location": "header", "required": True, "default": "playground"},
        {"key": "text", "label": "Text (CPU speech is slow)", "type": "textarea", "required": True, "default": "Hello from Mimic. This is synthetic speech."},
        {"key": "voice", "label": "Your consented cloned voice", "type": "select", "options": [], "required": True},
    ],
    "lookup": {"route": "/api/voices", "key": "voices", "field": "voice"},
    "followup": {"route": "/api/files/{file_id}", "method": "GET", "response": "audio"},
}]}


class StrictInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class CloneIn(StrictInput):
    name: str = Field(min_length=1, max_length=20)
    audio: str = Field(max_length=4 * ((10 * 1024 * 1024 + 2) // 3))
    transcript: str = Field(min_length=1, max_length=2000)
    consent: bool
    model: Literal["kitten2", "audio8"] = "kitten2"


class SpeakIn(StrictInput):
    text: str = Field(max_length=100000)
    voice: str = Field(min_length=1, max_length=20)
    seed: int | None = Field(None, ge=0, le=2**62)
    preset: Literal["stable", "expressive"] = "stable"
    normalize: bool = True


CONNECT = {
    "host": "mimic",
    "port": 29404,
    "paths": [
        {
            "label": "MCP, for Armory",
            "method": "POST",
            "path": "/mcp"
        },
        {
            "label": "Voices",
            "method": "GET",
            "path": "/api/voices"
        },
        {
            "label": "Clone a voice",
            "method": "POST",
            "path": "/api/voices"
        },
        {
            "label": "Delete a voice",
            "method": "DELETE",
            "path": "/api/voices/{name}"
        },
        {
            "label": "Speak",
            "method": "POST",
            "path": "/api/speak"
        },
        {
            "label": "Audio file",
            "method": "GET",
            "path": "/api/files/{file_id}"
        },
        {
            "label": "Health, no token",
            "method": "GET",
            "path": "/health"
        }
    ]
}


def build_app(base: Settings, model: Model | dict[str, Model] | None = None):
    if base.exposed_without_token:
        raise ValueError("Mimic refuses to start: SERVICE_HOST is exposed and INTERNAL_API_TOKEN is empty.")
    config = make_config(base)
    settings = live(base, config)
    backends = CachedBackends(base.state_dir / "backends.json")
    usage = Usage()
    model = model or {"kitten2": KittenModel(settings, backends), "audio8": KittenModel(settings, backends, slot="audio8")}
    service = MimicService(settings, model)
    mcp = SafeFastMCP(name="mimic", instructions=INSTRUCTIONS, host=base.host, port=base.port)

    async def invoke(owner, tool, function, *args, **kwargs):
        async with usage.track(owner, tool):
            return await function(owner, *args, **kwargs)

    async def tool_call(ctx, tool, function, *args):
        try:
            owner = owner_from_context(ctx)
            if ctx is not None and tool in ("clone", "speak", "delete"):
                note = "Waiting for private voice operation. CPU speech may take many minutes." if tool == "speak" else "Validating consented voice operation; waiting for model service."
                await ctx.report_progress(0, 1, note)
            result = await invoke(owner, tool, function, *args)
            if ctx is not None and tool in ("clone", "speak", "delete"):
                await ctx.report_progress(1, 1, "Operation completed.")
            return result
        except MimicError as error:
            raise PublicToolError(str(error)) from None

    @mcp.tool(meta={"keywords": ["clone", "voice", "consent"], "display_label": "Registering consented voice"})
    async def tool_mimic_cloneVoice(
        name: Annotated[str, Field(max_length=20, description="Private voice name, 1–20 ASCII name characters.")],
        audio: Annotated[str, Field(max_length=4 * ((10 * 1024 * 1024 + 2) // 3), description="Strict base64 PCM WAV; 5–30 seconds, one speaker, at most 10 MiB.")],
        transcript: Annotated[str, Field(max_length=2000, description="Exactly what the speaker says in the recording.")],
        consent: Annotated[bool, Field(strict=True, description="Must be true: speaker agreed to voice cloning.")],
        model: Annotated[Literal["kitten2", "audio8"], Field(description="Which speech model keeps this voice: kitten2 (CPU, default) or audio8 (GPU, faster).")] = "kitten2",
        ctx: Context = None,
    ) -> CloneResult:
        """Register your private synthetic voice from a WAV and exact transcript. Explicit speaker consent is required. The voice stays on the model you pick."""
        return await tool_call(ctx, "clone", service.clone_voice, name, audio, transcript, consent, model)

    @mcp.tool(meta={"keywords": ["voices", "consent"], "display_label": "Listing your voices"},
              annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    async def tool_mimic_listVoices(ctx: Context = None) -> VoiceList:
        """List only your consented cloned voices, their creation times and reference clip lengths."""
        return await tool_call(ctx, "list", service.list_voices)

    @mcp.tool(meta={"keywords": ["speak", "tts", "voice", "audio"], "display_label": "Generating synthetic speech (slow on CPU)"})
    async def tool_mimic_speak(
        text: Annotated[str, Field(max_length=100000, description="Text to speak; Markdown is stripped, code fences skipped.")],
        voice: Annotated[str, Field(max_length=20, description="One of your consented cloned voice names.")],
        seed: Annotated[int | None, Field(ge=0, le=2**62)] = None,
        preset: Literal["stable", "expressive"] = "stable", normalize: bool = True,
        ctx: Context = None,
    ) -> SpeakResult:
        """Generate synthetic MP3 using your consented cloned voice. CPU speech is slow (0.1–0.2x real time); wait for the player."""
        return await tool_call(ctx, "speak", service.speak, text, voice, seed, preset, normalize)

    @mcp.tool(meta={"keywords": ["delete", "voice", "consent"], "display_label": "Deleting your cloned voice"},
              annotations=ToolAnnotations(destructiveHint=True))
    async def tool_mimic_deleteVoice(name: Annotated[str, Field(max_length=20)], ctx: Context = None) -> DeleteResult:
        """Delete your consented cloned voice and reference recording from Mimic and the model service."""
        return await tool_call(ctx, "delete", service.delete_voice, name)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        return JSONResponse({"ok": True, "service": "Mimic", "ready": bool(backends.get("kitten2") or backends.get("audio8"))})

    def failure(error: MimicError) -> Response:
        code = 401 if isinstance(error, IdentityRequired) else 413 if isinstance(error, QuotaExceeded) else 503 if isinstance(error, EngineFailed) else 400
        return JSONResponse({"error": error.code, "message": str(error)}, status_code=code)

    async def body(request: Request, schema):
        # Bound the whole upload before JSON/base64 decoding, even without Content-Length.
        limit = 15 * 1024 * 1024 if schema is CloneIn else 512 * 1024
        payload = bytearray()
        async for chunk in request.stream():
            if len(payload) + len(chunk) > limit:
                raise MimicError("Request body exceeds the size limit.")
            payload.extend(chunk)
        try:
            return await worker(schema.model_validate_json, bytes(payload))
        except MimicError:
            raise MimicError("Invalid request. Check required fields, types and limits.") from None

    @mcp.custom_route("/api/voices", methods=["GET", "POST"])
    async def voices(request: Request) -> Response:
        owner = request.headers.get("x-requester-username", "").strip()
        try:
            service.owner(owner)
            if request.method == "GET":
                result = await invoke(owner, "list", service.list_voices)
                return JSONResponse({"voices": [v.name for v in result.voices], "details": [v.model_dump() for v in result.voices], "message": result.message})
            data = await body(request, CloneIn)
            result = await invoke(owner, "clone", service.clone_voice, **data.model_dump())
            return JSONResponse(result.model_dump())
        except MimicError as error:
            return failure(error)

    @mcp.custom_route("/api/voices/{name}", methods=["DELETE"])
    async def delete(request: Request) -> Response:
        try:
            result = await invoke(request.headers.get("x-requester-username", "").strip(), "delete", service.delete_voice, request.path_params["name"])
            return JSONResponse(result.model_dump())
        except MimicError as error:
            return failure(error)

    @mcp.custom_route("/api/speak", methods=["POST"])
    async def speak(request: Request) -> Response:
        owner = request.headers.get("x-requester-username", "").strip()
        try:
            service.owner(owner)
            data = await body(request, SpeakIn)
            result = await invoke(owner, "speak", service.speak, **data.model_dump())
            return JSONResponse(result.model_dump())
        except MimicError as error:
            return failure(error)

    @mcp.custom_route("/api/files/{file_id}", methods=["GET"])
    async def audio(request: Request) -> Response:
        try:
            stored = await service.audio(request.headers.get("x-requester-username", ""), request.path_params["file_id"])
        except MimicError as error:
            return failure(error)
        if stored is None:
            return JSONResponse({"error": "file_not_found"}, status_code=404)
        return FileResponse(stored.path, media_type="audio/mpeg", headers={"Cache-Control": "private, no-store",
                            "X-Content-Type-Options": "nosniff", "Content-Disposition": f'inline; filename="mimic-{stored.file_id[:8]}.mp3"'})

    if config is not None:
        async def status():
            return [{"label": "Engine", "value": "KittenTTS 2 model service"},
                    {"label": "Engine 2", "value": "Audio8 model service (GPU)"},
                    {"label": "Speech", "value": "Synthetic; kitten2 on CPU about 0.1–0.2x real time"},
                    {"label": "Voice operations", "value": "Serialized; private to requester; speaker consent required"},
                    {"label": "kitten2 admin credential", "value": "set" if base.kitten2_admin_password else "missing (uploads/deletes disabled)"},
                    {"label": "audio8 admin credential", "value": "set" if base.audio8_admin_password else "missing (uploads/deletes disabled)"}]

        register(mcp, connect=CONNECT, service="Mimic", admin_password=base.admin_password, usage=usage, backends=backends,
                 slots=[Slot("kitten2", "KittenTTS 2", "Remote voice cloning and speech. Token projects must include each model voice name. Model admin password is environment-only.",
                             probe_voices, "http://127.0.0.1:29323", local=False),
                        Slot("audio8", "Audio8", "Remote voice cloning and speech on a GPU (TTS_Audio8_Model). Token projects must include each model voice name. Model admin password is environment-only.",
                             probe_voices, "http://127.0.0.1:29322", local=False)], status=status, playground=PLAYGROUND)

        @mcp.custom_route("/admin/settings", methods=["GET", "PUT"])
        async def admin_settings(request: Request) -> Response:
            given = request.headers.get("x-admin-password", "").encode()
            if not hmac.compare_digest(given, base.admin_password.encode()):
                return JSONResponse({"detail": "Wrong admin password."}, status_code=401)
            if request.method == "PUT":
                try:
                    values = (await request.json())["values"]
                    if not isinstance(values, dict):
                        raise ValueError
                    await asyncio.to_thread(config.set, values)
                except (ValueError, KeyError, TypeError):
                    return JSONResponse({"detail": "Send valid settings as {\"values\": {...}}."}, status_code=422)
                except OSError:
                    return JSONResponse({"detail": "Settings could not be saved."}, status_code=503)
            return JSONResponse({"service": "Mimic", "settings": await asyncio.to_thread(config.describe)})

    app = mcp.streamable_http_app()
    if config is not None:
        web = Path(os.environ.get("SERVICE_WEB_DIR") or PROJECT_DIR / "web")
        app.router.routes.append(Mount("/admin", StaticFiles(directory=web, html=True)))
    app.add_middleware(AdminRefreshMiddleware, backends=backends)
    app.add_middleware(InternalTokenMiddleware, token=base.internal_token)
    app.state.service, app.state.mcp, app.state.settings = service, mcp, base
    return app
