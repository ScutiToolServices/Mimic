# Changelog

## Unreleased

- Model connection labels, Docker CONNECT hosts and documentation use the purpose-prefixed model-service names. Update saved model-service connections to the renamed load balancer hosts at their existing ports.

## 1.0.0 — 2026-11-07

- Add consent-based private clone/list/speak/delete MCP tools and equivalent HTTP routes.
- Delegate cloning and generation to TTS_Kitten2_Model with separate service/admin credentials.
- Keep validated reference WAVs, transcripts and consent per requester; encode MP3 with async ffmpeg.
- Add owner-scoped output quota/TTL, retryable voice lifecycle, stage progress and generous model timeout.
- Reuse Bard admin/runtime shell, model slot probe, usage, settings and deployment conventions.
