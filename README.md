# NAO microservices

Run commands from the repository root:

```sh
cp .env.example .env
mkdir -p data/pose-images data/exercises
```

Edit only the root `.env`. For a physical robot, set `NAO_IP` to its current LAN address. For the Choregraphe virtual robot, leave `NAO_IP` unset and use port `9559`.

## Docker Compose

```sh
# Linux / Windows
docker compose -f docker-compose.dev.yml up --build -d

# Apple Silicon (Docker Compose 2.24.4+)
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up --build -d
```

Open `http://localhost:8090`. Check `curl http://localhost:8000/commands` and `curl http://localhost:7001/health`. Use the same `-f` arguments with `docker compose ... ps` or `docker compose ... down` to inspect or stop the stack. On Apple Silicon, the NAO and translator APIs use host ports `15000` and `17000` instead of `5000` and `7000`. See [macOS robot setup](docs/nao-macos-setup.md) for connection steps.

## Without Docker

Use Python 3.11 for the pose, translator, voice, and exercise services. Install their requirements in a virtual environment, load the root `.env` in each terminal (`set -a; . ./.env; set +a`), then run:

```sh
python team-19-social-robot/skeletonFinderAPI/server/server.py
python team-19-social-robot/translator/nao_pose_service.py
python team-19-social-robot/voiceCommandAPI/server.py
python team-19-social-robot/exerciseConfigService/run.py
```

Run each command in a separate terminal from the repository root. The NAO bridge needs Python 2.7 and its bundled SDK; see [howToRun.txt](howToRun.txt). For the UI, run `cd web && npm ci --force && npm run dev`. Audio transcription is optional: install `team-19-social-robot/audioToTextConverter/requirements.txt` and run its `text_from_audio_extractor_service.py`.

## Environment variables

| Variable | Default | Use |
| --- | --- | --- |
| `SERVICE_NETWORK` | `local` | Service calls use `localhost`; Compose overrides this to `docker` and uses container names. Replaces `LOCAL` and `NO_NAMING`. |
| `NAO_IP` | Unset | Local Choregraphe: `127.0.0.1`; Choregraphe with Compose: `host.docker.internal`; real robot: its LAN IP. Compose supplies the host default when unset. |
| `NAO_PORT` | `9559` | NAOqi port for virtual or physical robot. |
| `POSE_IMAGES_HOST_DIR` | `./data/pose-images` | Compose pose-image mount. |
| `EXERCISES_HOST_DIR` | `./data/exercises` | Compose exercise-data mount. |
| `REGISTRY` / `TAG` | `jperdek` / `latest` | Docker image names. |

Optional overrides for custom network layouts: `POSE_API_URL`, `POSE_FROM_VIDEO_URL`, `SET_POSE_URL`, `NAO_SET_POSE_URL`, `VOICE_LINES_URL`, `EXERCISE_CONFIG_URL`, `VOICE_COMMAND_API_URL`, `EXERCISES_DIR`, `POSE_HOST_ROOT`, and `POSE_CONT_ROOT`. Normally leave them unset; service URLs are derived from `SERVICE_NETWORK`. The NAO API process must be able to reach `NAO_IP`; a container cannot reach host Choregraphe through its own `127.0.0.1`.
