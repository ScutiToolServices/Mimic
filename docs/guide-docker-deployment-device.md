# Mimic: Docker on a deployment machine

Run Mimic on a separate always-on machine (default `lex@scutiserver1.local`, folder `/media/ZimaOS-HD/Apps/ToolServices/Mimic`). Armory and ember_api reach it over the published port.

## Requirements on the machine

- Docker with Compose v2.
- A running TTS_Kitten2_Model service, a speech token for Mimic, and that model's admin password (used only for voice upload and delete). TTS_Audio8_Model the same way if you clone voices with `model: "audio8"`.
- The external `citadel_core` network, so Armory and ember_api can reach Mimic.
- ssh access (root over ssh is refused; use the normal user).

## 1. Publish the code (from your PC)

Run `Mimic\run.bat` and choose **Deploy** (or `run.bat deploy`). Menu:

| Option | Does |
|---|---|
| 1 | Publish code to the `live` branch |
| 2 | Copy your `.env` to the server (one ssh/tar session, one password prompt) |
| 3 | Both |
| 4, 5 | Dry runs of 1 and 2 |
| 6 | chown helper, if option 2 says `Permission denied` |
| R | Release: publish, then tag `VERSION` |

Keep your own target in the git-ignored `tools\deploy.local.ini` (copy `tools\deploy.local.example.ini`), or set
`DEPLOY_HOST`, `DEPLOY_DIR` and `DEPLOY_WEB_PORT` before running. Commit `main` first: publish reads committed `main`.

## 2. First-time setup on the machine

```bash
mkdir -p /media/ZimaOS-HD/Apps/ToolServices
git clone -b live <your-repo-url> /media/ZimaOS-HD/Apps/ToolServices/Mimic
cd /media/ZimaOS-HD/Apps/ToolServices/Mimic
```

Create `.env` (deploy option 2 copies yours, or `cp .env.example .env` and edit). The variables are listed under Settings in [guide-docker-same-device.md](guide-docker-same-device.md#settings).

## 3. Start

```bash
docker compose up -d --build
curl http://127.0.0.1:29404/health
```

Then open `/admin/` and save a connection to each model service under **Model services**, pressing **Test connection**. The address must be reachable from the container: `127.0.0.1` inside it is not the host or a sibling service, so join the model's network or use a host address. Run one replica and one worker per data volume (`mimic_data`). The health check does not call the model.

## Updating

```bash
cd /media/ZimaOS-HD/Apps/ToolServices/Mimic
git pull
docker compose up -d --build
```

`docker compose up -d --build`. Settings, saved connections, voices and audio live in the data volume and survive it. Reverse proxies, Armory and HTTP clients must allow slow CPU jobs (the model timeout defaults to 7200 s). MCP sessions must stay on one process. Do not retry speech automatically in a proxy: unseeded generation makes fresh audio and repeats expensive work. Retry an incomplete clone or delete by name after the upstream problem is fixed.

## Releasing

Before a release run `uv run pytest -q` and make `VERSION` match `pyproject.toml`. A plain publish (`run.bat`, Deploy, option 1) only updates the `live` branch; for a release run option R or `py tools\publish_live.py --release`, then `run.bat`, Build the release ZIP, builds `_zip_versions\Mimic-<VERSION>.zip`. Review the deploy scripts before running them: they push code and, for the `.env` option, credentials.

## Problems

See [Problems](guide-docker-same-device.md#problems) in the Docker-on-this-PC guide.
