"""Async adapter for the speech model services (KittenTTS 2, Audio8). Only voice mutation sends the model admin password."""
from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from src.admin_api import Backends, ProbeError, check
from src.config import Settings
from src.errors import EngineFailed, MimicError
from src.voices import wav_duration

MAX_OUTPUT_BYTES = 128 * 1024 * 1024


async def encode_mp3(wav: bytes, ffmpeg: str) -> bytes:
    """Encode without shell interpolation; kill/reap ffmpeg on timeout/cancellation."""
    try:
        process = await asyncio.create_subprocess_exec(
            ffmpeg, "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-f", "mp3", "pipe:1",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    except OSError:
        raise EngineFailed("ffmpeg could not be started on the Mimic host.") from None
    try:
        output, _ = await asyncio.wait_for(process.communicate(wav), timeout=120)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode or not output:
        raise EngineFailed("ffmpeg could not encode the audio.")
    return output


class KittenModel:
    """One model service, picked by `slot` ("kitten2" or "audio8"). A client per request prevents abandoned shared HTTP pools."""

    def __init__(self, settings: Settings, backends: Backends | None = None,
                 client: httpx.AsyncClient | None = None,
                 encoder: Callable[[bytes, str], Awaitable[bytes]] = encode_mp3, slot: str = "kitten2"):
        self.settings, self.backends, self.client, self.encoder, self.slot = settings, backends, client, encoder, slot

    async def _request(self, method: str, path: str, *, admin: bool = False,
                       missing_ok: bool = False, **kwargs: Any) -> bytes:
        def location():
            refresh = getattr(self.backends, "refresh", None)
            if refresh is not None:
                refresh()
            return self.backends.get(self.slot) if self.backends is not None else None
        slot = await asyncio.to_thread(location)
        if slot is None:
            raise EngineFailed("Save a connection for this model on the Mimic admin page.")
        url, token = slot
        if admin:
            token = getattr(self.settings, self.slot + "_admin_password")
            if not token:
                raise EngineFailed("Set the model service admin password before uploading or deleting a voice.")
        timeout = await asyncio.to_thread(lambda: self.settings.timeout_seconds)
        client = self.client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10), follow_redirects=False)
        try:
            async with client.stream(method, url.rstrip("/") + path, headers={"X-Internal-Token": token},
                                     timeout=httpx.Timeout(timeout, connect=10), **kwargs) as reply:
                code = reply.status_code
                if missing_ok and code == 404:
                    return b""
                if code >= 300:
                    messages = {
                        401: "Model service refused its credential (401).",
                        403: "Model token projects must include this cloned voice (403).",
                        404: "Model voice or endpoint not found (404).",
                        409: "Model voice name conflict (409).",
                        429: "Model service is busy or rate limited (429); retry later.",
                        503: "Model service unavailable (503); retry when ready.",
                    }
                    raise EngineFailed(messages.get(code, f"Model service rejected the request ({code})."))
                output = bytearray()
                async for chunk in reply.aiter_bytes():
                    if len(output) + len(chunk) > MAX_OUTPUT_BYTES:
                        raise EngineFailed("Model response exceeded the audio size limit.")
                    output.extend(chunk)
                return bytes(output)
        except httpx.TimeoutException:
            raise EngineFailed("Model service timed out. CPU speech is slow; retry later or raise the timeout.") from None
        except (httpx.HTTPError, ValueError):
            raise EngineFailed("Could not reach the model service.") from None
        finally:
            if self.client is None:
                await client.aclose()

    async def upload(self, name: str, audio: bytes, transcript: str) -> None:
        encoded = await asyncio.to_thread(lambda: base64.b64encode(audio).decode("ascii"))
        await self._request("PUT", f"/admin/voices/{name}", admin=True,
                            json={"audio_base64": encoded, "transcript": transcript})

    async def delete(self, name: str) -> None:
        await self._request("DELETE", f"/admin/voices/{name}", admin=True, missing_ok=True)

    async def list_voices(self) -> list[str]:
        import json
        data = await self._request("GET", "/v1/voices")
        try:
            voices = json.loads(data)["voices"]
            if not isinstance(voices, list) or not all(isinstance(v, str) for v in voices):
                raise ValueError
            return voices
        except (ValueError, KeyError, TypeError):
            raise EngineFailed("Model service returned an invalid voices list.") from None

    async def synthesize(self, text: str, voice: str, seed: int | None, preset: str, normalize: bool) -> tuple[bytes, float]:
        payload = {"text": text, "voice": voice, "seed": seed, "stream": False}
        if self.slot == "kitten2":  # Audio8 has no preset or normalize
            payload.update(preset=preset, normalize=normalize)
        data = await self._request("POST", "/v1/speak", json=payload)
        try:
            duration = await asyncio.to_thread(wav_duration, data)
        except MimicError:
            raise EngineFailed("Model service returned an invalid WAV recording.") from None
        ffmpeg = await asyncio.to_thread(lambda: self.settings.ffmpeg)
        try:
            return await self.encoder(data, ffmpeg), duration
        except TimeoutError:
            raise EngineFailed("ffmpeg encoding timed out.") from None


async def probe_voices(url: str, token: str) -> str:
    reply = await check(url, token, "/v1/voices")
    try:
        voices = reply.json()["voices"]
        if not isinstance(voices, list) or not all(isinstance(v, str) for v in voices):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ProbeError("Model service returned an invalid voices list.") from None
    return f"Reachable; {len(voices)} voice(s) permitted by this token. Upload/delete credentials are checked only during those operations."
