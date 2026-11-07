# Mimic

Private, consent-based voice cloning and text-to-speech MCP service for Citadel and Ember. Mimic validates and stores reference recordings, then calls **TTS_Kitten2_Model** (KittenTTS 2, port 29323) for voice registration and speech. It does not load or clone a model itself. Based on Bard; port **29404** follows Bard 29400, Scribe 29401, Reader 29402 and Lens 29403.

**Speaker consent is required.** `consent: true` means the caller states the recorded speaker agreed to cloning. Use a single speaker's 5–30 second recording and exactly what it says. Mimic stores that assertion with the reference; it cannot verify the assertion, speaker count or transcript. Output is synthetic speech.

CPU speech is slow: about **0.1–0.2 times real time** on the measured six-core machine. A minute of audio may take 5–10 minutes to generate. Default model timeout is two hours; clients, Armory and reverse proxies need matching long request timeouts. MCP reports waiting/completed stages, without invented percentage estimates. HTTP calls wait for the finished MP3; they do not stream partial speech.

## Tools

| MCP name | Service method | Result |
| --- | --- | --- |
| `tool_mimic_cloneVoice` | `clone_voice(name, audio, transcript, consent)` | `name`, `model_voice`, `duration_s`, `message` |
| `tool_mimic_listVoices` | `list_voices()` | Your voices: `name`, `created_at` (Unix seconds), `duration_s`; `message` |
| `tool_mimic_speak` | `speak(text, voice, seed?, preset?, normalize?)` | Bard-style `file_id`, `voice`, `duration_s`, `size_bytes`, `cached`, `message` |
| `tool_mimic_deleteVoice` | `delete_voice(name)` | `name`, `message` |

`audio` is **strict base64 of a PCM WAV**, not a filesystem path or data URL. Maximum decoded size: 10 MiB, duration 5–30 seconds inclusive. Mono or stereo PCM is accepted; use a clean single-speaker mono recording for model quality. Other formats are rejected. ffmpeg remains in Mimic for WAV-to-MP3 output, as in Bard.

Names are case-sensitive, 1–20 ASCII letters/digits/`_`/`.`/`-`, starting with a letter or digit. Two users can both own `anna`. The model name is `<sha256(username)[:32]>--<name>--<8 random hex characters>`, at most 64 characters and valid under `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`. It is returned as `model_voice` so the operator can update token scope. Model names are never accepted in place of the caller's public voice name.

Cloning an existing active name fails; delete it before replacing. Incomplete uploads can be retried under the same name. Lists include only active voices owned by the requester. No tool lists built-in or other owners' voices. Every tool requires the username from `_meta.requester` as forwarded by Armory.

## Setup

1. Install uv and ffmpeg on PATH. In PowerShell: `$env:UV_CACHE_DIR='D:/User/.uv-cache'`.
2. From this folder, run `uv sync`.
3. Copy `.env.example` to `.env` manually and fill credentials. Set `INTERNAL_API_TOKEN` to the shared Armory/Ember internal token. Save the reachable model address and token as connections on the Mimic admin page. Never commit actual credentials.
4. Configure separate model credentials as described below. Set `MIMIC_ADMIN_PASSWORD` to enable Mimic's admin page.
5. Run `run.bat run` (loads `.env`) or `uv run python -m src.run --dotenv`. Health: `http://127.0.0.1:29404/health`. Start Mimic before Armory.

## Model credentials and exact token steps

There are three separate credentials: Mimic's internal API token, its own admin-page password, and the model's credentials (service token plus model admin password).

1. On TTS_Kitten2_Model, configure a nonempty `KITTEN2_ADMIN_PASSWORD` and restart that service. Set **that same value** as Mimic's `MIMIC_KITTEN2_ADMIN_PASSWORD`. Only `PUT /admin/voices/{name}` and `DELETE /admin/voices/{name}` use it. Do not use it as the speech token.
2. Register a consented voice through Mimic's clone tool or `POST /api/voices`, authenticated with Mimic's internal API token and requester username. Record the returned `model_voice`. Registration uses the model admin password, so it can precede speech-token creation.
3. Open the model service admin page at `http://<model-host>:29323/admin/`, sign in with its admin password, and create a token named `mimic`. Set its **projects** list to every exact `model_voice` Mimic will speak. Built-in/public names such as `anna` are insufficient; wildcards are unsupported.
4. Equivalent HTTP request to the model service: `POST /admin/tokens`, header `X-Internal-Token: <KITTEN2_ADMIN_PASSWORD>`, JSON `{"name":"mimic","projects":["<model_voice>"],"rate":60}`. Save the returned token value once in a Mimic admin connection and pick it in the KittenTTS 2 slot. Restart Mimic when changing environment credentials; slot saves apply immediately.
5. Each new clone/recreation gets a new model name. Update the token's projects through the model Tokens card, or `PUT /admin/tokens/{token_id}` with the model admin header and `{"projects":["<all current model_voice names>"],"rate":60}`. Remove deleted names. Model API limits a scoped token to **32 projects**; this single-token Mimic deployment therefore supports at most 32 simultaneously authorized model names. For more, propose a token-pool integration; none is implemented here. Unscoped tokens (`projects: null`) allow every model voice and are broader than this scoped setup.
6. In Mimic admin, test the KittenTTS 2 slot. It calls `GET /v1/voices` with the speech token; it verifies reachability/authentication but does not upload a clip or verify model admin credentials. Then speak a short sentence with the caller's private voice name. A 403 means token projects omit the exact model voice.

## Exact Armory registration (manual; not applied)

1. Start Mimic, set the same `INTERNAL_API_TOKEN` in Armory, and confirm Armory can reach Mimic.
2. Add this entry beside `bard` in Armory's `configs/config_extensions.json` (preserve its surrounding existing object):

```json
"mimic": {
  "label": "Mimic",
  "description": "Consented private voice cloning and synthetic speech. CPU generation is slow.",
  "url": "http://127.0.0.1:29404/mcp",
  "headers": {"X-Internal-Token": "${INTERNAL_API_TOKEN}"},
  "forward_requester": true
}
```

3. For Docker peers on `citadel_core`, use `http://mimic:29404/mcp`. Loopback refers to the calling container itself; it will not reach a sibling container. TTS_Kitten2_Model must likewise have an address reachable from Mimic, not container loopback.
4. Restart Armory so it connects to the extension and discovers the four `tool_mimic_*` tools. Ensure its request timeout/reverse proxy allows long CPU jobs. Keep MCP sessions on one Mimic process.
5. Enable/select the `mimic` extension for the intended users using the existing Citadel/Armory extension workflow. Verify Armory forwards `_meta.requester: {"username":"<signed-in username>"}` for **every** tool. Missing identity is refused.
6. Voice cloning needs a client-side file-to-base64 handoff. Audio playback needs the existing file proxy pattern to fetch Mimic's `/api/files/{file_id}` with both internal token and requester username. Bard's Ember route `/api/bard/audio/{file_id}` does not automatically point to Mimic. No Citadel/Ember UI, permissions, route or setting changes were made; verify/add a Mimic proxy/card integration separately before promising automatic chat playback.
## HTTP API and async example

All `/api/*` routes require `X-Internal-Token` when configured and `X-Requester-Username`. These headers are for trusted server proxies, not identity claims from untrusted browsers. MCP uses `_meta.requester` instead. An exposed bind without a nonblank internal token refuses startup.

| Method | Route | Body / response |
| --- | --- | --- |
| POST | `/api/voices` | `{name,audio,transcript,consent}` → clone result |
| GET | `/api/voices` | `{voices: string[], details: [{name,created_at,duration_s}], message}`; requester only |
| DELETE | `/api/voices/{name}` | Delete caller's reference and remote voice |
| POST | `/api/speak` | `{text,voice,seed?,preset?,normalize?}` → Bard-style speech result |
| GET | `/api/files/{file_id}` | Private MP3, owner checked; invalid/foreign/expired ID returns 404 |
| GET | `/health` | Public process health; does not call the model |

`preset` is `stable` (default) or `expressive`. `normalize` defaults true; use false for non-English text because model normalization is English-tuned. `seed` is 0 through `2**62`; seeded calls cache by owner, model revision, cleaned text, seed, preset and normalization. Unseeded calls generate fresh audio. Markdown cleanup and 5,000 cleaned-character cap follow Bard.

Runnable non-blocking example (service/model must already be configured):

```powershell
$env:MIMIC_EXAMPLE_TOKEN = '<shared internal token>'
uv run python tools/example.py --owner ann --voice anna --text 'Hello. This is synthetic speech.'
```

To clone first, add `--clip reference.wav --transcript 'Exactly what the recording says.' --consent`. The example prints `model_voice` and stops: authorize that model name in token projects, then run without `--clip` to speak. File IO uses `asyncio.to_thread`, requests use async httpx; credentials never print. Output defaults to `example-output.mp3` in this folder.

## Storage and failure recovery

References live in `.data/voices/<full-owner-sha256>/<voice-name-sha256>.wav` with a JSON sidecar containing name, model name, transcript, consent, creation time, duration and state. SHA-256 filenames preserve case sensitivity and avoid Windows reserved names. Generated MP3s use Bard's owner-hashed `.data/audio/` layout, 24-hour TTL and 200 MiB per-user quota. References are kept until deletion; output TTL/quota does not count references. Protect and back up the entire data volume; it contains voice recordings and saved speech tokens. POSIX permissions are tightened on reference files; configure Windows ACLs through normal host administration.

Clips are saved with `pending` state before model upload; successful uploads become `active`. Retrying a failed upload reuses its pending model name. Deletion marks a record `deleting` before the remote call; it disappears from lists and cannot speak while deletion is pending. Retry deletion after failures; a remote 404 means already removed. A pending reference can also be deleted. Distributed calls cannot be atomic: interruption can leave a remote voice plus pending/deleting local record. Retrying reconciles it. Only local active records authorize speech.

Operations are serialized to protect voice lifecycle and quotas. Run **one worker and one replica per data folder**. Changing backend URL does not migrate voices; keep the slot pointed at the model that holds the registered voices, or delete/re-register against the correct backend. Existing generated speech survives voice deletion until ordinary output TTL/sweep; deletion removes the reference/transcript/consent record and remote cloned voice.

Lists and existing audio downloads use short independent storage locks, so they remain responsive while speech is being generated. If a successful clone response is lost, an operator can recover only its `model_voice` field from that owner's JSON sidecar, or delete/recreate the private name to get a new registration result. The owner list intentionally reports name/time/duration only; it does not currently recover the model name.

401/403/404/409/429/503, timeouts, connection errors, invalid model WAVs and ffmpeg failures become clear, safe errors without upstream body, paths, URLs or credentials. Speech response WAVs are capped at 128 MiB. Ordinary errors are HTTP 400, identity 401, output quota 413, model failure 503.

## Settings and admin

| Variable | Default | Purpose |
| --- | --- | --- |
| `INTERNAL_API_TOKEN` | empty | Shared guard for `/mcp` and `/api/*`; required off loopback |
| `MIMIC_HOST`, `MIMIC_PORT` | `127.0.0.1`, `29404` | Listen address |
| `MIMIC_ADMIN_PASSWORD` | empty | Enables Mimic `/admin/`; separate from internal/model credentials |
| `MIMIC_AUDIO8_ADMIN_PASSWORD` | empty | Optional. Admin password of TTS_Audio8_Model, for voices cloned with `model: "audio8"` |
| `MIMIC_KITTEN2_ADMIN_PASSWORD` | empty | Model admin password; upload/delete only |
| `MIMIC_TIMEOUT_SECONDS` | `7200` | Long model request timeout |
| `MIMIC_MAX_CHARS` | `5000` | Cleaned text cap, at most model limit |
| `MIMIC_TTL_HOURS` | `24` | Output audio retention |
| `MIMIC_QUOTA_MB` | `200` | Per-owner output storage in MiB |
| `MIMIC_FFMPEG` | `ffmpeg` | MP3 encoder executable |

With Mimic's admin password set, `/admin/` reuses Bard's exact shared page/API/runtime files. `X-Admin-Password` guards status, per-user usage, model-service slot/probe, and settings. Non-secret settings save to `.data/settings.json` and win over environment values. Model slot URL/token save to `.data/backends.json`; the token is never returned. Model admin password remains environment-only. Usage resets on restart. Without the admin password, page/API are absent. See [admin guide](docs/guide-web-ui.md).

## Deployment and tests

See [deployment](deployment.md). Docker tooling follows Bard, with ffmpeg but no local model weights. No Docker build/start is required for fake-backed tests:

```powershell
$env:UV_CACHE_DIR='D:/User/.uv-cache'
uv run pytest -q
```

Tests use fake models and in-process HTTP transports, no real model or network listeners. Shared Bard tests cover admin/runtime/storage/text/identity behavior. Additional tests cover consent, clips, ownership on every tool, namespacing, lifecycle, error statuses/timeouts, concurrency and exposed-bind startup refusal.

`run.bat` (Deploy and ZIP options), `tools/publish_live.py` and `tools/make_zip.py` preserve Bard's future manual release workflow. They require an initialized Mimic repository and configured remote; this task initializes nothing and publishes nothing. VERSION and pyproject version are 1.0.0. Never run deploy scripts before reviewing their configured target and authorizing publication.

## Documentation

- [Purpose: input, output and what it is for](docs/purpose.md)
- [Changelog](CHANGELOG.md)
- [Docker on this PC](docs/guide-docker-same-device.md)
- [Docker on another machine](docs/guide-docker-deployment-device.md)
- [Run without Docker](docs/guide-no-docker-same-device.md)
