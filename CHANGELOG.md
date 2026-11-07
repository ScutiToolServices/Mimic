# Changelog

## Unreleased

- Default service port moves from 8094 to 29404. Update any explicit port in your real `.env`, saved model-service connections in `backends.json`, and browser or MCP client configurations once; model-service connection ports also move to the new model port blocks. Docker users who used the Compose default receive the new host and container ports together; explicit host-port overrides remain in effect until changed.
- Model connection labels, Docker CONNECT hosts and documentation use the purpose-prefixed model-service names. Update saved model-service connections to the renamed load balancer hosts using the current connection defaults.

## 1.0.0 — 2026-11-07

- Add consent-based private clone/list/speak/delete MCP tools and equivalent HTTP routes.
- Delegate cloning and generation to TTS_Kitten2_Model with separate service/admin credentials.
- Keep validated reference WAVs, transcripts and consent per requester; encode MP3 with async ffmpeg.
- Add owner-scoped output quota/TTL, retryable voice lifecycle, stage progress and generous model timeout.
- Reuse Bard admin/runtime shell, model slot probe, usage, settings and deployment conventions.
