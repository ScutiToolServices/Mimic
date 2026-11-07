# Mimic admin page

Set `SERVICE_ADMIN_PASSWORD`, restart, then open `http://127.0.0.1:29404/admin/`.
Sign in with Mimic's admin password. This is separate from the model service admin password and from the callers' tokens.

- Status reports remote KittenTTS 2, consent/ownership policy and slow CPU generation.
- Usage reports calls, errors and mean time per requester since this process started.
- Model services has one required remote slot, KittenTTS 2. Save the reachable URL and **speech service token**. Token projects must include every namespaced `model_voice`; the model admin password is not entered here. Test connection checks `/v1/voices` with the service token. It does not prove upload/delete access or model readiness for generation.
- Settings edits character cap, output retention/quota, model timeout and ffmpeg executable. Saves go to `.data/settings.json`; slot saves go to `.data/backends.json`. Saved values beat environment defaults. Credentials are never returned by admin APIs.
- Try it uses a token from the **Tokens** card and a requester username, separate from admin sign-in. The panel lists only that requester's active consented clones. Choose one and enter text; allow long waits on CPU. Cancellation stops the client request; the remote model may finish work already admitted. Successful MP3s play and download through `/api/files/{file_id}`.

Clone/delete through MCP or the documented HTTP API; the shared admin page is unchanged and does not provide a clone-upload form. Do not place a model admin password in the public API token field. Reference recordings require speaker consent and exact transcripts. Output is synthetic.

Shared files are byte-identical to Bard: `web/index.html`, `src/admin_api.py`, `tests/test_admin_api.py`, `src/runtime.py`. Mimic-specific logic is supplied through slots, status, settings, playground descriptor and `admin_bridge.py`. Do not modify siblings during this task.

## Tokens

The **Tokens** card makes one token per caller (Armory, another service). Enter a name, optionally a calls-per-minute limit and an expiry in days, and press **Create token**. The token is shown once: copy it into the caller's configuration (for Armory, the extension's `X-Internal-Token` header). **Revoke** cuts a caller off at once. Tokens are stored as hashes in `tokens.json` beside `settings.json`. With no token, every call to `/mcp` and `/api/*` is refused; `/health` and `/admin` need none.

## Connect to this service

The **Connect to this service** card lists the addresses other services can use: the address you opened the page with, the same PC (`127.0.0.1`), another Docker container on the same network, and a Docker container calling this PC (`host.docker.internal`), then every endpoint with its method and a **Copy** button. Calls need a token from the **Tokens** card in `X-Internal-Token`; HTTP routes also need `X-Requester-Username`.
