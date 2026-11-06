"""Environment defaults; saved non-secret admin options override them."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8094
    internal_token: str = ""
    admin_password: str = ""
    data_dir: Path = PROJECT_DIR / ".data"
    kitten2_url: str = "http://127.0.0.1:9250"
    kitten2_token: str = ""
    kitten2_admin_password: str = ""
    timeout_seconds: int = 7200
    max_chars: int = 5000
    ttl_seconds: int = 86400
    quota_bytes: int = 200 * 1024 * 1024
    ffmpeg: str = "ffmpeg"

    def __post_init__(self):
        if not 1 <= self.port <= 65535 or not 1 <= self.max_chars <= 5000:
            raise ValueError("Invalid port or text limit.")
        if min(self.timeout_seconds, self.ttl_seconds, self.quota_bytes) <= 0:
            raise ValueError("Timeout, retention and quota must be positive.")

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def exposed_without_token(self) -> bool:
        return not self.internal_token.strip() and self.host not in LOOPBACK_HOSTS


def load_settings() -> Settings:
    load_dotenv(PROJECT_DIR / ".env")
    env = os.environ.get
    return Settings(
        host=env("MIMIC_HOST", "127.0.0.1"), port=int(env("MIMIC_PORT", "8094")),
        internal_token=env("INTERNAL_API_TOKEN", ""), admin_password=env("MIMIC_ADMIN_PASSWORD", ""),
        data_dir=Path(env("MIMIC_DATA_DIR") or PROJECT_DIR / ".data"),
        kitten2_url=env("MIMIC_KITTEN2_URL", "http://127.0.0.1:9250"),
        kitten2_token=env("MIMIC_KITTEN2_TOKEN", ""),
        kitten2_admin_password=env("MIMIC_KITTEN2_ADMIN_PASSWORD", ""),
        timeout_seconds=int(env("MIMIC_TIMEOUT_SECONDS", "7200")),
        max_chars=int(env("MIMIC_MAX_CHARS", "5000")),
        ttl_seconds=int(env("MIMIC_TTL_HOURS", "24")) * 3600,
        quota_bytes=int(env("MIMIC_QUOTA_MB", "200")) * 1024 * 1024,
        ffmpeg=env("MIMIC_FFMPEG", "ffmpeg"),
    )
