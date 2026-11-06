"""Mimic-specific options; shared runtime implementation remains unchanged."""
from src.config import Settings
from src.runtime import Config, LiveSettings, Setting

FIELDS = {"max_chars": ("max_chars", int), "ttl_seconds": ("ttl_hours", lambda h: h * 3600),
          "quota_bytes": ("quota_mb", lambda m: m * 1024 * 1024), "timeout_seconds": ("timeout_seconds", int),
          "ffmpeg": ("ffmpeg", str)}


def schema(base: Settings) -> list[Setting]:
    return [Setting("max_chars", "Longest text (characters)", "int", base.max_chars, minimum=1, maximum=5000),
            Setting("ttl_hours", "Keep speech audio (hours)", "int", base.ttl_seconds // 3600, minimum=1, maximum=8760),
            Setting("quota_mb", "Speech audio per user (MiB)", "int", base.quota_bytes // (1024 * 1024), minimum=1, maximum=100000),
            Setting("timeout_seconds", "Model timeout (seconds)", "int", base.timeout_seconds, minimum=60, maximum=86400,
                    help="CPU speech runs at about 0.1–0.2 times real time."),
            Setting("ffmpeg", "ffmpeg executable", "text", base.ffmpeg, blank=False),
        Setting("data_path", "Data folder", "text", "", restart=True,
                help=f"Where stored data (speech audio and cloned voices) goes. Empty = {base.state_dir}. Applies after a restart; files already stored are not moved. "
                     f"Settings and saved model connections stay in the standard folder.")]


def make_config(base: Settings) -> Config | None:
    return Config(base.state_dir / "settings.json", schema(base)) if base.admin_password else None


def live(base: Settings, config: Config | None):
    return LiveSettings(base, config, FIELDS) if config else base
