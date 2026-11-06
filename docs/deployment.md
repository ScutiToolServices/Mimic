# Deployment

Native Windows: install uv/ffmpeg, set `UV_CACHE_DIR=D:/User/.uv-cache`, fill `.env` manually from the example, then run `run.bat`. `shell.bat` opens the existing uv environment. Do not expose Mimic without `INTERNAL_API_TOKEN`.

Docker: after configuring credentials and a model URL reachable from the container, manually run `docker compose up -d --build`. Compose joins existing `citadel_core` network and publishes `127.0.0.1:8094` by default. Set `MIMIC_BIND` only when a wider published bind is intended. Use one replica/worker with persistent `mimic_data` volume. Container health checks process health without calling the model. No model downloads occur in Mimic.

`MIMIC_KITTEN2_URL` must reach TTSKitten2Model from Mimic. Container `127.0.0.1` is not the host or a sibling service. Attach the model to a reachable network or configure host routing yourself. Set the model admin password and service token separately. Refer to README's exact token projects procedure after each clone/recreation.

Reverse proxy, Armory and HTTP client timeouts must permit slow CPU jobs; model timeout defaults to 7200 seconds. MCP sessions must remain on one process. Do not automatically retry speech in proxies: unseeded generation produces fresh audio and can duplicate expensive work. Retry incomplete clone/delete by name after resolving upstream failures.

Before release: `uv run pytest -q`, verify VERSION matches pyproject, then manually configure repository/remote and deploy targets. Bard-derived deploy scripts may push code or credentials; review them before running. Nothing was committed, published or deployed by this build task.
