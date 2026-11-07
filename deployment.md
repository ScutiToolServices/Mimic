# Deploying Mimic

Mimic is one HTTP and MCP service (consent-based voice cloning) on port 8094. It runs no model itself: it needs a TTSKitten2Model connection (and optionally TTSAudio8Model) saved on its admin page.

## Requirements

- Docker with Compose v2, or native Windows with uv and ffmpeg (`set UV_CACHE_DIR=D:/User/.uv-cache`).
- A running TTSKitten2Model service, a speech token for Mimic, and that model's admin password (used only for voice upload and delete). TTSAudio8Model the same way if you clone voices with `model: "audio8"`.
- The external `citadel_core` network, so Armory and ember_api can reach Mimic.

## Settings

In `.env` next to `docker-compose.yml` (copy `.env.example`; fill it by hand, never commit it):

| Variable | Default | Effect |
|---|---|---|
| `INTERNAL_API_TOKEN` | empty | Shared token for `/mcp` and `/api/*`. Required when `MIMIC_HOST` is not loopback. |
| `MIMIC_HOST` / `MIMIC_PORT` | `127.0.0.1` / `8094` | Listen address (Compose sets the host itself). |
| `MIMIC_BIND` | `127.0.0.1` | Docker only: the address the published port listens on. Widen it only on purpose. |
| `MIMIC_ADMIN_PASSWORD` | empty | Unlocks `/admin/`. Empty = page off, so no model connection can be saved. |
| `MIMIC_KITTEN2_ADMIN_PASSWORD` | empty | Admin password of TTSKitten2Model, for voice upload and delete only. Environment only. |
| `MIMIC_AUDIO8_ADMIN_PASSWORD` | empty | The same for TTSAudio8Model. |

Everything else (limits, timeout, data folder, model addresses and tokens) is set on the admin page. See `docs/guide-web-ui.md`.

## Start

```bash
docker compose up -d --build
curl http://127.0.0.1:8094/health
```

Then open `/admin/` and save a connection to each model service under **Model services**, pressing **Test connection**. The address must be reachable from the container: `127.0.0.1` inside it is not the host or a sibling service, so join the model's network or use a host address. Run one replica and one worker per data volume (`mimic_data`). The health check does not call the model.

## Updating

`docker compose up -d --build`. Settings, saved connections, voices and audio live in the data volume and survive it. Reverse proxies, Armory and HTTP clients must allow slow CPU jobs (the model timeout defaults to 7200 s). MCP sessions must stay on one process. Do not retry speech automatically in a proxy: unseeded generation makes fresh audio and repeats expensive work. Retry an incomplete clone or delete by name after the upstream problem is fixed.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Calls fail with "Save a connection" | No model service connection is saved on the admin page for that voice's model. |
| 401 from the model | The speech token is wrong, or its projects list lacks the cloned voice's exact model name (see the README's token steps). |
| Clone or delete is refused | The model admin password env variable is empty or wrong. |
| 413 | Stored audio is over the per-user quota. |
| The service refuses to start | `MIMIC_HOST` is not loopback and `INTERNAL_API_TOKEN` is empty. |

## Releasing

Before a release run `uv run pytest -q` and make `VERSION` match `pyproject.toml`. A plain publish (`tools\deploy.bat` option 1) only updates the `live` branch; for a release run option R or `py tools\publish_live.py --release`, then `tools\make_zip.bat` builds `zip_versions\Mimic-<VERSION>.zip`. Review the deploy scripts before running them: they push code and, for the `.env` option, credentials.
