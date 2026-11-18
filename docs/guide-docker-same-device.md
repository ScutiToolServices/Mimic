# Mimic: Docker on this PC

Run Mimic in Docker Desktop on the machine you work on, so Armory and ember_api on it can reach it.

## Requirements

- Docker with Compose v2.
- A running TTS_Kitten2_Model service, a speech token for Mimic, and that model's admin password (used only for voice upload and delete). TTS_Audio8_Model the same way if you clone voices with `model: "audio8"`.
- The external `citadel_core` network, so Armory and ember_api can reach Mimic.

## Settings

In `.env` next to `docker-compose.yml` (copy `.env.example`; fill it by hand, never commit it):

| Variable | Default | Effect |
|---|---|---|
| `SERVICE_HOST` / `SERVICE_PORT` | `127.0.0.1` / `29404` | Listen address (Compose sets the host itself). |
| `SERVICE_BIND` | `127.0.0.1` | Docker only: the address the published port listens on. Widen it only on purpose. |
| `SERVICE_ADMIN_PASSWORD` | empty | Unlocks `/admin/`, where you make the callers' tokens, and turns token checks on for `/mcp` and `/api/*`. Required when `SERVICE_HOST` is not loopback. Empty = no page and no checks (loopback only). |

Everything else (limits, timeout, data folder, model addresses and tokens) is set on the admin page. See `docs/guide-web-ui.md`.

## Start

```bash
docker compose up -d --build
curl http://127.0.0.1:29404/health
```

Then open `/admin/` and save a connection to each model service under **Model services**, pressing **Test connection**. The address must be reachable from the container: `127.0.0.1` inside it is not the host or a sibling service, so join the model's network or use a host address. Run one replica and one worker per data volume (`mimic_data`). The health check does not call the model.

## Updating

`docker compose up -d --build`. Settings, saved connections, voices and audio live in the data volume and survive it. Reverse proxies, Armory and HTTP clients must allow slow CPU jobs (the model timeout defaults to 7200 s). MCP sessions must stay on one process. Do not retry speech automatically in a proxy: unseeded generation makes fresh audio and repeats expensive work. Retry an incomplete clone or delete by name after the upstream problem is fixed.

## Problems

| Symptom | Likely cause |
|---|---|
| Calls fail with "Save a connection" | No model service connection is saved on the admin page for that voice's model. |
| 401 from the model | The speech token is wrong, or its projects list lacks the cloned voice's exact model name (see the README's token steps). |
| Clone or delete is refused | The model admin password saved on the admin page is wrong. |
| 413 | Stored audio is over the per-user quota. |
| The service refuses to start | `SERVICE_HOST` is not loopback and `SERVICE_ADMIN_PASSWORD` is empty. |
