"""Entrypoint refuses unsafe bind before invoking Uvicorn."""
import pytest

from src.config import Settings, load_settings
from src import run


def test_main_refuses_exposed_bind_without_token(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "load_settings", lambda: Settings(host="0.0.0.0", data_dir=tmp_path))
    monkeypatch.setattr(run.uvicorn, "run", lambda *a, **kw: pytest.fail("Must refuse before server startup"))
    with pytest.raises(SystemExit, match="INTERNAL_API_TOKEN"):
        run.main()


def test_environment_defaults_and_separate_credentials(tmp_path, monkeypatch):
    import src.config
    # Never load any actual .env during tests.
    monkeypatch.setenv("MIMIC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MIMIC_KITTEN2_ADMIN_PASSWORD", "model-admin")
    monkeypatch.setenv("MIMIC_ADMIN_PASSWORD", "mimic-admin")
    settings = load_settings()
    assert settings.port == 29404 and settings.timeout_seconds == 7200
    assert (settings.kitten2_admin_password, settings.admin_password) == ("model-admin", "mimic-admin")
