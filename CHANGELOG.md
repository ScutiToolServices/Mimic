# Changelog

## 1.0.0 — 2026-11-07

- Add consent-based private clone/list/speak/delete MCP tools and equivalent HTTP routes.
- Delegate cloning and generation to TTSKitten2Model with separate service/admin credentials.
- Keep validated reference WAVs, transcripts and consent per requester; encode MP3 with async ffmpeg.
- Add owner-scoped output quota/TTL, retryable voice lifecycle, stage progress and generous model timeout.
- Reuse Bard admin/runtime shell, model slot probe, usage, settings and deployment conventions.
