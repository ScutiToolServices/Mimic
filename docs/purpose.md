# Purpose

**Kind:** reference recording (+ text) → MP3 file

**Tags:** `cpu`, `mcp`, `http`, `ffmpeg`, `voice-cloning`

| | |
|---|---|
| Input | To clone a voice: a name, strict base64 of a PCM WAV (5 to 30 seconds, at most 10 MiB), exactly what it says, and `consent: true`. To speak: text, a voice, optional seed, preset and normalize. The user comes from `_meta.requester`. |
| Output | Clone: the voice `name` and its `model_voice`. Speak: an MP3 owned by the user (`file_id`, `duration_s`, `size_bytes`, `cached`). Lists and deletes cover only the user's own voices. |
| Needs | `TTS_Kitten2_Model` (CPU) and optionally `TTS_Audio8_Model` (GPU), one admin slot each, plus that model's admin password for voice upload and delete. |
| Runs on | CPU. Holds no model; ffmpeg encodes WAV to MP3. CPU speech is slow: about 0.1 to 0.2 times real time. |

**Use for:** consent-based voice cloning and speech in a cloned voice.
**Not for:** plain text to speech with built-in voices (see `Bard`), cloning without the speaker's consent. Mimic cannot verify consent, speaker count or transcript.
