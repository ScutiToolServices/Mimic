"""Environment defaults; saved non-secret admin options override them."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 29404
    internal_token: str = ""
    admin_password: str = ""
    data_dir: Path = PROJECT_DIR / ".data"
    config_dir: Path | None = None  # set when the data folder was moved: the folder that keeps settings.json
    kitten2_admin_password: str = ""
    audio8_admin_password: str = ""
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
    def state_dir(self) -> Path:
        """Where settings.json and backends.json live: the first data folder, even after the data folder was moved."""
        return self.config_dir or self.data_dir

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def exposed_without_token(self) -> bool:
        return not self.internal_token.strip() and self.host not in LOOPBACK_HOSTS


def _from_environment() -> Settings:
    env = os.environ.get
    return Settings(
        host=env("SERVICE_HOST", "127.0.0.1"), port=int(env("SERVICE_PORT", "29404")),
        internal_token=env("INTERNAL_API_TOKEN", ""), admin_password=env("SERVICE_ADMIN_PASSWORD", ""),
        data_dir=Path(env("SERVICE_DATA_DIR") or PROJECT_DIR / ".data"),
        kitten2_admin_password=env("SERVICE_KITTEN2_ADMIN_PASSWORD", ""),
        audio8_admin_password=env("SERVICE_AUDIO8_ADMIN_PASSWORD", ""),
        timeout_seconds=int(env("SERVICE_TIMEOUT_SECONDS", "7200")),
        max_chars=int(env("SERVICE_MAX_CHARS", "5000")),
        ttl_seconds=int(env("SERVICE_TTL_HOURS", "24")) * 3600,
        quota_bytes=int(env("SERVICE_QUOTA_MB", "200")) * 1024 * 1024,
        ffmpeg=env("SERVICE_FFMPEG", "ffmpeg"),
    )


def with_saved_data_path(settings: Settings) -> Settings:
    """The admin page's "Data folder" setting moves stored data (audio, uploads, voices, results) to another folder.
    It is read once, here at start. Settings and saved model connections stay in the first folder, which is where this
    value is saved. A folder that cannot be written is ignored."""
    try:
        saved = json.loads((settings.data_dir / "settings.json").read_text("utf-8")).get("data_path")
    except (OSError, ValueError, AttributeError):
        return settings
    if not isinstance(saved, str) or not saved.strip():
        return settings
    target = Path(saved.strip()).expanduser()
    if not target.is_absolute():
        target = PROJECT_DIR / target
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-test"
        probe.write_text("x")
        probe.unlink()
    except OSError:
        logging.getLogger(__name__).warning("Data folder %s cannot be written; using %s", target, settings.data_dir)
        return settings
    return replace(settings, data_dir=target, config_dir=settings.data_dir)


def load_settings() -> Settings:
    return with_saved_data_path(_from_environment())
