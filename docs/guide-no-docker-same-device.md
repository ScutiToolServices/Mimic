# Mimic: without Docker, on Windows

Run Mimic directly with Python: one process, no load balancer, listening on `127.0.0.1:8094`.

## Requirements

- Windows with uv (`winget install astral-sh.uv`) and ffmpeg. If uv reports a cross-drive cache error, `set UV_CACHE_DIR=D:/User/.uv-cache`.
- A running TTSKitten2Model service, a speech token for Mimic, and that model's admin password (used only for voice upload and delete). TTSAudio8Model the same way if you clone voices with `model: "audio8"`.

## Start

`run.bat` loads `.env` in this folder (copy `.env.example`) through `--dotenv` and prints the names it loaded, never the values; a real environment variable wins over it. A plain `uv run python -m src.run` does not read `.env`. The variables are listed under Settings in [guide-docker-same-device.md](guide-docker-same-device.md#settings); the ones that name Docker or Compose do not apply here.

Double-click `run.bat`, or run it in a terminal from `Mimic\`. Choose **1 Run the service** in the menu, or run `run.bat run` to skip the menu. It runs `uv sync` to create or update `.venv`, then starts `python -m src.run`.

```bash
uv sync
uv run python -m src.run
```

## Check

```bash
curl http://127.0.0.1:8094/health
```

Then open `/admin/` and save a connection to each model service under **Model services**, pressing **Test connection**. The health check does not call the model.

## Stop

Ctrl+C in the terminal. Do not run this and the Docker stack together: both use port 8094.

## Tests

```bash
uv run pytest -q
```
