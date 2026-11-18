"""Result models. `message` comes last: ember shows it first."""

from __future__ import annotations

from pydantic import BaseModel


class SpeakResult(BaseModel):
    file_id: str
    voice: str
    duration_s: float
    size_bytes: int
    cached: bool
    message: str


class VoiceInfo(BaseModel):
    name: str
    model: str = "kitten2"
    created_at: float
    duration_s: float


class VoiceList(BaseModel):
    voices: list[VoiceInfo]
    message: str


class CloneResult(BaseModel):
    name: str
    model: str = "kitten2"
    model_voice: str
    duration_s: float
    voice_gate: bool = False  # other voices were silenced in the reference before it was stored
    message: str


class DeleteResult(BaseModel):
    name: str
    message: str
