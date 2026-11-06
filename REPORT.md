# Mimic build report — 2026-11-07

Built `AI/ToolServices/Mimic`, port **8094**, using Bard as template. No changes to sibling services, model services, Citadel or Brain. No repository initialization, commits, pushes, real model calls or Docker start.

## Delivered

- Four MCP tools: `tool_mimic_cloneVoice`, `tool_mimic_listVoices`, `tool_mimic_speak`, `tool_mimic_deleteVoice`.
- Equivalent private HTTP routes, owned MP3 downloads, internal-token guard and exposed-bind startup refusal.
- Consent assertion stored with reference WAV, exact transcript, creation time, duration and lifecycle state.
- Owner isolation from Bard's `_meta.requester.username`, portable hashed storage and model namespaced voice names.
- Async httpx remote adapter, separate speech/admin model credentials, safe upstream errors, two-hour timeout, stage progress and async ffmpeg MP3 output.
- Retryable pending upload/deletion, seeded cache, output TTL/quota, independent short locks for listing and existing audio downloads during slow generation.
- Bard's exact shared admin page/API/tests/runtime, Mimic model slot/probe, per-user usage and saved settings. Shared files verified byte-identical.
- Docker/Compose, Windows launch/shell scripts, Bard-derived manual deploy/ZIP tooling, uv lock, VERSION/CHANGELOG, instructions, README, docs and runnable async client example.

## Verification

`UV_CACHE_DIR=D:/User/.uv-cache; uv run pytest -q` → **131 passed, 2 warnings in 1.78 s**.

Coverage includes consent refusal, short/long/truncated/non-WAV/oversized references, owner isolation on every tool and output download, namespacing and Windows filename safety, upload/speak/delete/retry/restart, scoped credentials, 401/403/404/409/429/503/timeouts, quota/cache, lifecycle concurrency, safe filesystem/framework/ffmpeg errors and startup refusal. Real MCP JSON-RPC/session metadata was tested through in-process ASGI. Model tests use fakes/MockTransport; no network listener or real model.

Warnings remain visible: Starlette TestClient httpx deprecation, and Pydantic Settings unresolved lifespan annotation. These originate in shared tests/dependencies.

Also passed: `uv build` (source distribution and wheel), `uv run python tools/example.py --help`, Python compileall, real local ffmpeg conversion of a generated WAV, SHA-256 parity of all four required shared files.

Fresh read-only review found no critical consent/ownership flaw. Two important findings were reproduced with failing tests and fixed: existing audio/list access waiting behind generation; MCP framework validation echoing private input paths.

## Every design choice / assumption

1. Execute the supplied brief in this new folder; no worktree, git initialization or commit workflow. Brief delegates unresolved decisions to NOTES.md.
2. Accept strict base64 PCM WAV only, not paths or other audio formats; ffmpeg is output-only. 10 MiB and 5–30 seconds inclusive. Mono/stereo PCM accepted, single-speaker mono recommended. Caller attests speaker count, consent and exact transcript; software does not establish those facts.
3. Case-sensitive public names use ASCII model-name characters and a 20-character cap. Trim requester username exactly as Bard does. Hash owner directories and voice filenames to avoid traversal, Windows reserved names and case-folding collisions.
4. Model names are `<sha256(owner)[:32]>--<public-name>--<8 random hex characters>`, at most 64 characters. Recreation receives a new revision to avoid stale upstream seeded cache.
5. Refuse replacement of an active name; delete/recreate. Failed pending uploads reuse their model name. Pending/deleting voices are hidden and cannot speak. Remote deletion 404 counts as already removed.
6. Store pending reference before model upload. Distributed local/remote changes are not atomic; retries reconcile interruptions. Keep pending/deleting records until retry succeeds.
7. Serialize mutations and generation within one process; independent short file locks keep lists/downloads responsive. One worker/replica per data volume; no cross-process transaction support. Finish worker IO before releasing its lock on cancellation.
8. Keep reference clips until voice deletion; output TTL/quota does not count references. Existing generated speech survives voice deletion until output expiry. Protect/back up private data with host ACLs/permissions.
9. Model admin password stays environment-only; shared admin slot saves only speech token/URL. Preserve shared files unchanged and use Mimic adapters for async integration. Do not migrate existing clones when changing backend URL.
10. Choose 8094 after confirmed sibling defaults 8090–8093. No 8094 TCP listener found during implementation; deployment must recheck availability.
11. Default model timeout is 7200 seconds; response WAV cap is 128 MiB. CPU speech about 0.1–0.2x real time. Progress identifies waiting/completion stages, not estimated percentages. Unseeded speech stays fresh; seeded cache includes voice revision and generation options.
12. Use one speech token; scoped model API allows at most 32 exact projects. New/recreated model names require manual scope updates. No silent scope broadening or token-pool integration.
13. Keep Bard tool naming/result conventions and sanitize framework errors at MCP boundary. Missing/invalid tool arguments return a generic safe error; known service errors remain specific.
14. Registration remains manual. `Python/Citadel` does not exist at the path supplied here; registration JSON follows Lens/Bard docs. Ember proxy/card/upload integration is a separate external change.
15. Deploy/ZIP scripts are future manual maintenance tools; they require a separately configured repository/remote and reviewed deployment targets. They were not executed.

Deferred minor: owner list omits `model_voice`; if clone response is lost, recover its model name from the private sidecar as operator, or delete/recreate. README documents this recovery.

## Not verified

Real KittenTTS registration/generation, cloned-voice quality, semantic transcript correctness/speaker consent, GPU/CPU performance on this host, actual model-token setup, deployed Armory config/permissions/timeouts, Ember chat playback/upload handoff, Docker build/start, deploy/SSH/ZIP publication and future port availability. Two upstream test warnings remain. No external setup was attempted.

## Exact manual registration and model token procedure

1. Configure TTSKitten2Model with nonempty `KITTEN2_ADMIN_PASSWORD` and restart it. In Mimic save its reachable address as an admin-page connection and set `MIMIC_KITTEN2_ADMIN_PASSWORD` to that same model admin password. Set `INTERNAL_API_TOKEN` to Armory's shared internal token. Optionally set a separate `MIMIC_ADMIN_PASSWORD` for Mimic's page. Run `uv run python -m src.run`.
2. Clone a consented voice with the requester username and save returned `model_voice`. Upload uses the model admin credential and can precede speech-token creation.
3. On the model, create speech token using its admin Tokens card, or `POST /admin/tokens` with `X-Internal-Token: <KITTEN2_ADMIN_PASSWORD>` and body `{"name":"mimic","projects":["<exact model_voice>"],"rate":60}`. Save the returned token in a Mimic admin connection and pick it in the KittenTTS 2 slot; it applies at once. Never use the model admin password as speech token.
4. Include **every exact namespaced model voice name** in token projects, at most 32 per scoped token. Public names and wildcards do not work. Update after each clone/recreation using model Tokens card or `PUT /admin/tokens/{token_id}` with model admin header and `{"projects":["<all current model_voice names>"],"rate":60}`. Remove deleted names. Probe Mimic's slot, then speak a short sentence; 403 means the exact voice is absent from projects.
5. Add the following entry beside `bard` in Armory's `configs/config_extensions.json`, preserving its existing outer object:

```json
"mimic": {
  "label": "Mimic",
  "description": "Consented private voice cloning and synthetic speech. CPU generation is slow.",
  "url": "http://127.0.0.1:8094/mcp",
  "headers": {"X-Internal-Token": "${INTERNAL_API_TOKEN}"},
  "forward_requester": true
}
```

6. For Docker peers on existing `citadel_core`, use `http://mimic:8094/mcp`; ensure the model URL is reachable from Mimic too. Start Mimic before restarting Armory. Restart Armory for discovery, enable the extension for intended users, and verify all calls forward `_meta.requester.username`. Configure client/proxy/Armory timeouts for long CPU jobs, preserving MCP sessions on one process.
7. Verify/add Mimic-specific file-upload and audio proxy/card support in Citadel/Ember separately. Fetch `/api/files/{file_id}` with the same internal token and requester username; Bard's existing audio proxy does not automatically route to Mimic. All such outside-folder changes remain proposals in NOTES.md.
