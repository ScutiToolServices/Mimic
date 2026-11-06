"""Failures safe for tool/HTTP output: no filesystem paths or upstream bodies."""


class MimicError(Exception):
    code = "mimic_error"


class IdentityRequired(MimicError):
    code = "identity_required"


class VoiceUnavailable(MimicError):
    code = "voice_unavailable"


class TextRejected(MimicError):
    code = "text_rejected"


class QuotaExceeded(MimicError):
    code = "quota_exceeded"


class EngineFailed(MimicError):
    code = "engine_failed"
