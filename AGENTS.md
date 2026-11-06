# Mimic

Consent-based voice-cloning MCP service for Citadel and Ember, port 8094. Thin remote front for TTSKitten2Model on port 9250; no local model dependencies.

## Agent instructions

This file is the instruction file. `CLAUDE.md` only imports `@AGENTS.md`.

## Commands

- Windows: set `UV_CACHE_DIR=D:/User/.uv-cache`.
- Install: `uv sync`.
- Test: `uv run pytest -q` (fake model and in-process transports only).
- Run: `uv run python -m src.run`.
- Async client example: `uv run python tools/example.py --help`.

## Rules

- Never read or print `.env`, secrets or private reference data. Use uv, not pip; pnpm if Node tooling is ever needed.
- Ownership comes only from username in `_meta.requester`, using `identity.py`; trusted HTTP proxies send `X-Requester-Username`.
- `INTERNAL_API_TOKEN` guards `/mcp` and `/api/*`. Exposed binds without a nonblank token refuse startup.
- Logic lives in `service.py`, `engine.py`, `voices.py`, `store.py`. `app.py` is transport glue.
- All blocking file/WAV work runs in workers; remote calls use async httpx; ffmpeg is an asyncio subprocess. Always reap cancelled ffmpeg processes. One process/worker/replica per data folder.
- Consent must be literal true, stored with each reference. Tool descriptions and README state this requirement. Never add features to hide synthetic origin.
- Model service token is used only for speak/list/probe. Model admin password is used only for upload/delete; keep it environment-only. Token projects must include each exact namespaced model voice name returned by cloning.
- Result models end with `message`. Tool errors must never expose paths, URLs, credentials or upstream bodies/stderr.
- Public voice names are private per owner; hash names for portable file paths. Model names include owner hash and a random revision to avoid stale upstream cache after recreation.
- Keep `web/index.html`, `src/admin_api.py`, `tests/test_admin_api.py`, `src/runtime.py` byte-identical to Bard. The first three are also shared with Scribe/Reader; runtime follows Bard/Scribe/Laya. Use `admin_bridge.py` for Mimic-specific integration. Propose sibling changes in NOTES.md when task scope forbids editing them.
- Non-secret settings persist in `.data/settings.json`; model speech slot URL/token in `.data/backends.json`. Admin password unlocks `/admin/`; internal API token does not guard admin routes.
- No auto-registration. README documents Armory registration and model token scope.
- VERSION and pyproject version must match. Deploy scripts are manual future maintenance tools; never publish without authorization.
- Saved connections: the admin page also keeps a shared list of named model-service addresses (`/admin/connections/{name}`, under the reserved `_connections` key of `backends.json`, token never sent back). A slot picks one with `PUT /admin/backends/{key}` `{"connection": name}`, so editing a connection updates every slot using it; a connection a slot uses cannot be deleted (409). Slots with a plain address or an environment value still work.
