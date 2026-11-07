# Changelog

## Unreleased

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
