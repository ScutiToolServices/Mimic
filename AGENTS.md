# Mimic

Consent-based voice-cloning MCP service for Citadel and Ember, port 29404. Thin remote front for TTS_Kitten2_Model on port 29323; no local model dependencies.

## Agent instructions

This file is the instruction file. `CLAUDE.md` only imports `@AGENTS.md`.

## Commands

- Windows: set `UV_CACHE_DIR=D:/User/.uv-cache`.
- Install: `uv sync`.
- Test: `uv run pytest -q` (fake model and in-process transports only).
- Run: `run.bat run`, or `uv run python -m src.run` (add `--dotenv` to load `.env`).
- Async client example: `uv run python tools/example.py --help`.

## Rules
- Follow the `tool-service-parity` skill and `AI/ToolServices/_docs/SHARED-FEATURES.md` (what must match in every tool service) and `AI/ToolServices/_docs/SERVICE-SPECIFIC.md` (what differs on purpose). A change to a shared feature goes to every tool service; a new difference goes into `SERVICE-SPECIFIC.md` in the same change.

- Data folder: `Settings.data_dir` holds speech audio and cloned voices; the admin setting `data_path` (restart, `src/config.py` `with_saved_data_path`) moves it at the next start and keeps `settings.json` and `backends.json` in `Settings.state_dir` (the first folder). No `.env` variable; `SERVICE_DATA_DIR` is read only as the base folder (Docker).
- Never read or print `.env`, secrets or private reference data. Use uv, not pip; pnpm if Node tooling is ever needed.
- Ownership comes only from username in `_meta.requester`, using `identity.py`; trusted HTTP proxies send `X-Requester-Username`.
- Tokens guard `/mcp` and `/api/*` (header `X-Internal-Token`). With `SERVICE_ADMIN_PASSWORD` set, each caller gets its own token from the admin page (`GET/POST /admin/tokens`, `DELETE /admin/tokens/{id}`; `src/tokens.py` keeps them hashed in `tokens.json` in the state folder; `src/middleware.py` checks them and answers 401, or 429 over a token's calls-per-minute). No admin password = no checks, so an exposed bind without one must refuse to start. `src/tokens.py`, `src/middleware.py`, `tests/test_tokens.py` and `tests/seed.py` are the same in all five tool services.
- Logic lives in `service.py`, `engine.py`, `voices.py`, `store.py`. `app.py` is transport glue.
- All blocking file/WAV work runs in workers; remote calls use async httpx; ffmpeg is an asyncio subprocess. Always reap cancelled ffmpeg processes. One process/worker/replica per data folder.
- Consent must be literal true, stored with each reference. Tool descriptions and README state this requirement. Never add features to hide synthetic origin.
- Model service token is used only for speak/list/probe. Model admin password is used only for upload/delete; keep it environment-only. Token projects must include each exact namespaced model voice name returned by cloning.
- Result models end with `message`. Tool errors must never expose paths, URLs, credentials or upstream bodies/stderr.
- Public voice names are private per owner; hash names for portable file paths. Model names include owner hash and a random revision to avoid stale upstream cache after recreation.
- Keep `web/index.html`, `src/admin_api.py`, `tests/test_admin_api.py`, `src/runtime.py` byte-identical to Bard. The first three are also shared with Scribe/Reader; runtime follows Bard/Scribe/Laya. Use `admin_bridge.py` for Mimic-specific integration. Propose sibling changes to the user when task scope forbids editing them.
- Non-secret settings persist in `.data/settings.json`; model speech slot URL/token in `.data/backends.json`. Admin password unlocks `/admin/`; tokens do not guard admin routes.
- No auto-registration. README documents Armory registration and model token scope.
- VERSION and pyproject version must match. Deploy scripts are manual future maintenance tools; never publish without authorization.
- Saved connections: the admin page also keeps a shared list of named model-service addresses (`/admin/connections/{name}`, under the reserved `_connections` key of `backends.json`, token never sent back). A slot picks one with `PUT /admin/backends/{key}` `{"connection": name}`, so editing a connection updates every slot using it; a connection a slot uses cannot be deleted (409). Addresses and tokens are saved only on the admin page (there are no environment variables for them); a slot with no address runs in this service, or fails when it has no local engine.
- Two speech models: `kitten2` (TTS_Kitten2_Model, CPU) and `audio8` (TTS_Audio8_Model, GPU), each its own admin slot (address and token saved on the admin page only; env has just `SERVICE_AUDIO8_ADMIN_PASSWORD`, optional). `cloneVoice`/`POST /api/voices` take `model` (default `kitten2`); the voice record keeps it, so speak and delete route to that model. Old records without `model` are `kitten2`. `preset` and `normalize` are kitten2 only (refused for audio8 voices). Audio8 `temperature` is not exposed yet.
- Behaviour changes update `README.md`, `deployment.md`, the guides in `docs/`, `.env.example`, `AGENTS.md` and `CHANGELOG.md` in the same commit.
- Commit with the noreply author email `214214011+scutiii2@users.noreply.github.com` (another address is rejected on push). Push `main`, then run `python tools/publish_live.py`. Build Docker only when the Dockerfile or the dependencies changed.
