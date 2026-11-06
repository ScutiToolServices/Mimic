# Mimic decisions and execution ledger

Binding spec: ../_mimic_brief.md. All writes remain in this folder. No git init, commit, push, Docker start, real model calls or secret-file reads.

## Choices / assumptions

- Ruling: execute the supplied brief directly, in this new folder, without a git worktree or commits. The brief explicitly chooses this scope and delegates unclear design choices here.
- Base64 input is a strict PCM WAV, at most 10 MiB, 5–30 seconds inclusive. Other formats are rejected; ffmpeg remains for output encoding only. Speaker count, consent truth and transcript accuracy must be attested by the caller; software cannot establish them.
- Public voice names use the model's ASCII name characters, with a 20-character cap. Case-sensitive usernames and names follow Bard. Owner directories use SHA-256; model names use 32 owner-hash characters, `--`, public name, `--`, and 8 random hex characters (at most 64 characters). New registrations receive new model names to avoid stale seeded model cache after deletion/recreation.
- Existing active names are refused; delete before replacing. Incomplete upload/delete records remain private on disk and can be retried with the same public name. Only active voices appear in lists or can speak. Model 404 during deletion counts as already removed.
- Serialize voice mutations and speech within one process, protecting quota and clone/speak/delete races. Lists and existing MP3 downloads use separate short storage locks and remain responsive during generation. Run one worker and one Mimic replica per data volume; cross-process transactions are not supported. File work runs in worker threads; complete each worker operation before releasing its lock on cancellation.
- Clone stores WAV, transcript, consent, creation time and pending record before upload. Remote success activates record. Distributed calls are not atomic; retry pending uploads or deletions after interruption. Deleting a voice does not erase previously generated audio; Bard's TTL/quota applies to output audio.
- Keep model admin password environment-only, separate from Mimic admin password and saved speech slot token. Shared admin files remain byte-identical to Bard; proposed shared fixes belong below rather than changing siblings.
- Port 8094 follows Bard 8090, Scribe 8091, Reader 8092, Lens 8093. No 8094 TCP listener found during implementation; availability must be checked again at deployment.
- Default model request timeout: 7200 seconds, output WAV capped at 128 MiB. CPU generation is about 0.1–0.2x real time; progress reports stages, not invented percentages or completion estimates.
- No automatic Armory/Citadel registration. Existing Ember UI/proxy integration for a new extension is unverified and may require work outside this task.
- Reuse Bard deploy/ZIP scripts for future manual maintenance; do not execute them in this task. They require a separately initialized repository and remote.
- Voice filenames are SHA-256 of public names, preserving case-sensitive naming on Windows and allowing reserved names such as CON without filesystem conflicts.
- Model scoped-token API accepts at most 32 projects; with one speech token, at most 32 exact model voice names can be authorized simultaneously. New clones require manual scope updates; never silently broaden scope.
- Python/Citadel is absent at the workspace path stated in the brief. Registration JSON follows the existing Lens/Bard documentation; live Armory schema, timeout configuration, permission workflow and Ember proxy integration could not be checked here.
- Mimic's MCP boundary sanitizes framework validation and unexpected exceptions, since FastMCP otherwise echoes invalid input values before service handlers run. Safe model/service errors retain their specific messages.

## Plan / ledger

1. Copy shared Bard files and reusable storage/identity/middleware/text preparation; add failing service tests.
2. Implement strict settings, owner voice persistence, model adapter, consent and speech lifecycle.
3. Add MCP/HTTP/admin integration and fake-backed tests.
4. Add deployment files, registration instructions and non-blocking example; run full suite and final fresh-context review.

Pre-flight: voice record model name is the only model-facing identifier; requester username is the only owner authority. Tool results end with message. HTTP audio remains owner-scoped.

Task 1: complete — shared files copied directly from Bard; service tests first failed on missing src.config, then 22 passed after implementation.
Task 2: complete — model tests first failed on missing src.engine; fake-backed adapter/status/timeout/credential tests pass. Copied runtime test changed only expected service port from 8090 to 8094.
Task 3: complete — app tests first failed on missing src.app; real MCP JSON-RPC/session/requester test passes through in-process ASGI without sockets. All four shared files verified byte-identical to Bard.
Task 4: implementation complete — deployment/docs/example added. Final command results recorded below after verification.

Final verification (2026-11-07): `UV_CACHE_DIR=D:/User/.uv-cache; uv run pytest -q` → **131 passed, 2 warnings in 1.78 s**. Warnings originate in shared tests/dependencies: Starlette TestClient's httpx deprecation and Pydantic Settings' unresolved lifespan annotation. No warnings suppressed. `uv build` produced both source archive and wheel; `uv run python tools/example.py --help` and `uv run python -m compileall -q src tools` passed. Real local ffmpeg encoded a generated WAV successfully; no real speaker recording or model service used. Final SHA-256 comparison confirmed all four required shared files match Bard. No `.git` or actual `.env` created in Mimic. No git commands, commits, pushes, Docker start or real model calls performed.

Final review: fresh read-only reviewer found no critical consent/ownership issue. Important fixes: independent output/list storage locks keep reads responsive during long synthesis; sanitized MCP boundary prevents framework validation echoing private input paths. Each reproduced with failing regression and passed after fix. Windows filename collision also reproduced and fixed with hashed names.

Final: minor (deferred): owner voice list does not expose model_voice, so a lost successful clone response requires operator sidecar recovery or deletion/recreation to recover token-scope registration. Documented in README; no expanded list schema added.
Final: Ruling: keep real model/audio quality, Docker execution, deployed Armory and Ember integration unverified — brief forbids real model calls/Docker start and limits writes to Mimic; operator must validate those deployment-specific steps.

## Proposals outside Mimic (not applied)

- Shared admin API reads some Backends files directly on its async routes; synchronize an upstream improvement across Bard/Scribe/Reader later. Mimic preserves the required shared files exactly, and wraps route execution through its own adapter to offload these shared synchronous reads.
- Add explicit Mimic audio proxy/card and file-upload handoff in Citadel/Ember after confirming the current repository location. This task leaves all external registration and integration unchanged.
