# Changelog

## Unreleased

### Playground works behind a path-prefix proxy

The Try it panel built its request URLs from the page origin, so behind ServiceHub (`/s/<id>/`) it called the hub's root and got 404 Not Found. It now resolves routes against the service root (`../` from the admin page). Same-origin checking is unchanged.


### Playground: no token to paste, model picker, autoplay and batch

The playground signs in with a temporary caller token made from the admin session (named `playground (temporary)`, revoked on sign-out), so the service token field is gone. Choices such as voices load by themselves, and a strip above the form shows which models are connected. Services whose lookup reply carries `models` get a Model picker that narrows the choices. Operations with a text field and audio back get an Autoplay toggle and a "One request per line" toggle that sends each line as its own request and plays the results in order.

`GET /api/voices` now also returns `models` (voice names grouped by kitten2 and audio8).

### Model connections page redesign

Each model slot now shows its state first (saved connection, direct address, runs in this service, or not connected) with the address and whether a token is saved. Editing opens in place: pick a source (saved connection, direct address or in this service) and only the fields for that source appear. A slot that has not been connected opens its editor. Test connection also updates the slot's state. Saved connections are a table with credentials and the slots using them; Add connection opens the form only on request, and a connection in use has its Delete button disabled. The admin API is unchanged.

### Admin navigation

The admin page now has seven sidebar pages: Overview, Playground, Access tokens, Model connections, Runtime & settings, Usage and Connect & API. Overview reads live health and service status; links and browser history select pages. The sidebar collapses to an icon rail and remembers its display preference. Existing connections, tokens, settings and public Playground authentication keep their behavior.

### Breaking: model admin passwords move to the admin page

`SERVICE_KITTEN2_ADMIN_PASSWORD` and `SERVICE_AUDIO8_ADMIN_PASSWORD` are no longer read. Open `/admin/`, and on each model slot (or saved connection) enter the **Model admin password** next to the address; the page requires it when you save an address. Remove the two variables from your `.env` and Compose environment. The admin page, `admin_api.py` and its test are the same in all five tool services; the field only appears for slots that declare it (Mimic).

### Breaking: callers use admin-page tokens, not `INTERNAL_API_TOKEN`

`INTERNAL_API_TOKEN` is no longer read. Set `SERVICE_ADMIN_PASSWORD`, open `/admin/`, make one token per caller on the new **Tokens** card (stored hashed in `tokens.json` in the data folder; sent in `X-Internal-Token`) and put it in the caller's configuration (Armory: the extension's `headers`). A token can carry a calls-per-minute limit and an expiry, and **Revoke** cuts a caller off at once. Without an admin password there are no checks, and the service refuses to start on a non-loopback host.

### Breaking: common service environment variables

Service-owned environment variables now use `SERVICE_*`. Old names are no longer read.
Rename old names once in your real `.env`, Compose `environment:` block, and CI/secret settings.

| Old name | New name |
|---|---|
| `MIMIC_ADMIN_PASSWORD` | `SERVICE_ADMIN_PASSWORD` |
| `MIMIC_AUDIO8_ADMIN_PASSWORD` | `SERVICE_AUDIO8_ADMIN_PASSWORD` |
| `MIMIC_BIND` | `SERVICE_BIND` |
| `MIMIC_DATA_DIR` | `SERVICE_DATA_DIR` |
| `MIMIC_EXAMPLE_TOKEN` | `SERVICE_EXAMPLE_TOKEN` |
| `MIMIC_FFMPEG` | `SERVICE_FFMPEG` |
| `MIMIC_HOST` | `SERVICE_HOST` |
| `MIMIC_KITTEN2_ADMIN_PASSWORD` | `SERVICE_KITTEN2_ADMIN_PASSWORD` |
| `MIMIC_MAX_CHARS` | `SERVICE_MAX_CHARS` |
| `MIMIC_PORT` | `SERVICE_PORT` |
| `MIMIC_QUOTA_MB` | `SERVICE_QUOTA_MB` |
| `MIMIC_TIMEOUT_SECONDS` | `SERVICE_TIMEOUT_SECONDS` |
| `MIMIC_TTL_HOURS` | `SERVICE_TTL_HOURS` |
| `MIMIC_WEB_DIR` | `SERVICE_WEB_DIR` |

`SERVICE_KITTEN2_ADMIN_PASSWORD` and `SERVICE_AUDIO8_ADMIN_PASSWORD` keep the model names
because they authenticate different upstream models; `SERVICE_ADMIN_PASSWORD` unlocks Mimic itself.

- Default service port moves from 8094 to 29404. Update any explicit port in your real `.env`, saved model-service connections in `backends.json`, and browser or MCP client configurations once; model-service connection ports also move to the new model port blocks. Docker users who used the Compose default receive the new host and container ports together; explicit host-port overrides remain in effect until changed.
- Model connection labels, Docker CONNECT hosts and documentation use the purpose-prefixed model-service names. Update saved model-service connections to the renamed load balancer hosts using the current connection defaults.

## 1.0.0 — 2026-11-07

- Add consent-based private clone/list/speak/delete MCP tools and equivalent HTTP routes.
- Delegate cloning and generation to TTS_Kitten2_Model with separate service/admin credentials.
- Keep validated reference WAVs, transcripts and consent per requester; encode MP3 with async ffmpeg.
- Add owner-scoped output quota/TTL, retryable voice lifecycle, stage progress and generous model timeout.
- Reuse Bard admin/runtime shell, model slot probe, usage, settings and deployment conventions.
