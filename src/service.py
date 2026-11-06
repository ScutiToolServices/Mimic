"""Consent and ownership boundary; serialize lifecycle changes with generation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Callable
from typing import Protocol

from src.config import Settings
from src.contract import CloneResult, DeleteResult, SpeakResult, VoiceInfo, VoiceList
from src.errors import IdentityRequired, MimicError, VoiceUnavailable
from src.store import AudioStore
from src.text_prep import prepare
from src.voices import VoiceStore, decode_clip, validate_name


class Model(Protocol):
    async def upload(self, name: str, audio: bytes, transcript: str) -> None: ...
    async def delete(self, name: str) -> None: ...
    async def synthesize(self, text: str, voice: str, seed: int | None, preset: str, normalize: bool) -> tuple[bytes, float]: ...


async def worker(call: Callable, *args):
    """On cancellation finish filesystem operation before caller releases its lock."""
    task = asyncio.create_task(asyncio.to_thread(call, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise MimicError("Private storage could not be read or updated.") from None


class MimicService:
    def __init__(self, settings: Settings, model: Model):
        self.settings, self.model = settings, model
        self.voices = VoiceStore(settings.data_dir / "voices")
        self.store = AudioStore(settings.audio_dir, lambda: settings.ttl_seconds, lambda: settings.quota_bytes)
        self._lock = asyncio.Lock()
        self._audio_lock = asyncio.Lock()
        self._voice_lock = asyncio.Lock()

    async def _voice_worker(self, call: Callable, *args):
        """Keep record reads atomic with writes, without waiting for remote generation."""
        async with self._voice_lock:
            return await worker(call, *args)

    @staticmethod
    def owner(owner: str) -> str:
        if not isinstance(owner, str) or not owner.strip():
            raise IdentityRequired("No signed-in user was sent with this request.")
        return owner.strip()

    async def clone_voice(self, owner: str, name: str, audio: str, transcript: str, consent: bool) -> CloneResult:
        owner = self.owner(owner)
        if consent is not True:
            raise MimicError("Explicit speaker consent is required: consent must be true.")
        validate_name(name)
        if not isinstance(transcript, str) or not transcript.strip() or len(transcript) > 2000:
            raise MimicError("Provide the exact transcript, 1 to 2000 characters.")
        data, duration = await worker(decode_clip, audio)
        async with self._lock:
            record = await self._voice_worker(self.voices.read, owner, name)
            if record and record["state"] != "pending":
                raise MimicError("Voice already exists or deletion is pending; delete it before cloning again.")
            record = record or self.voices.new(owner, name, transcript, duration)
            record.update(transcript=transcript, duration_s=duration, consent=True)
            await self._voice_worker(self.voices.save, owner, record, data)
            await self.model.upload(record["model_voice"], data, transcript)
            record["state"] = "active"
            await self._voice_worker(self.voices.save, owner, record)
        return CloneResult(name=name, model_voice=record["model_voice"], duration_s=duration,
                           message="Consented synthetic voice stored. Add model_voice to the model token's projects before speaking.")

    async def list_voices(self, owner: str) -> VoiceList:
        owner = self.owner(owner)
        rows = await self._voice_worker(self.voices.list, owner)
        return VoiceList(voices=[VoiceInfo(name=r["name"], created_at=r["created_at"], duration_s=r["duration_s"]) for r in rows],
                         message=f"{len(rows)} consented cloned voice(s) owned by you.")

    async def _record(self, owner: str, name: str, active: bool = True) -> dict:
        validate_name(name)
        record = await self._voice_worker(self.voices.read, owner, name)
        if not record or (active and record["state"] != "active"):
            raise VoiceUnavailable("No available cloned voice with that name belongs to you.")
        return record

    async def speak(self, owner: str, text: str, voice: str, seed: int | None = None,
                    preset: str = "stable", normalize: bool = True) -> SpeakResult:
        owner = self.owner(owner)
        if preset not in ("stable", "expressive") or type(normalize) is not bool:
            raise MimicError("Use preset stable or expressive and a boolean normalize.")
        if seed is not None and (type(seed) is not int or not 0 <= seed <= 2**62):
            raise MimicError("Seed must be an integer from 0 to 2**62.")
        async with self._lock:
            record = await self._record(owner, voice)
            limit = await worker(lambda: self.settings.max_chars)
            clean = prepare(text, limit)
            key = json.dumps([record["model_voice"], clean, seed, preset, normalize, uuid.uuid4().hex if seed is None else ""])
            file_id = hashlib.sha256(key.encode()).hexdigest()[:32]
            async with self._audio_lock:
                stored = await worker(self.store.get, owner, file_id)
            cached = stored is not None
            if stored is None:
                mp3, duration = await self.model.synthesize(clean, record["model_voice"], seed, preset, normalize)
                async with self._audio_lock:
                    stored = await worker(self.store.put, owner, file_id, mp3, voice, duration)
        return SpeakResult(file_id=file_id, voice=voice, duration_s=stored.duration_s, size_bytes=stored.size_bytes,
                           cached=cached, message=f"Synthetic speech ready ({stored.duration_s:.1f} s). The player is shown in chat.")

    async def delete_voice(self, owner: str, name: str) -> DeleteResult:
        owner = self.owner(owner)
        async with self._lock:
            record = await self._record(owner, name, active=False)
            record["state"] = "deleting"
            await self._voice_worker(self.voices.save, owner, record)
            await self.model.delete(record["model_voice"])
            await self._voice_worker(self.voices.remove, owner, name)
        return DeleteResult(name=name, message="Consented cloned voice deleted; existing speech follows its audio retention policy.")

    async def audio(self, owner: str, file_id: str):
        owner = self.owner(owner)
        async with self._audio_lock:
            return await worker(self.store.get, owner, file_id)
