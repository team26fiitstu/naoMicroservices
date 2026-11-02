# NAO Microservices

Services for controlling a NAO robot, recognizing poses, managing exercises, and using the web interface.

## Quick start

From the repository root, prepare the shared configuration and data directories:

```sh
cp .env.example .env
mkdir -p data/pose-images data/exercises
```

The repository uses one `.env` file, in its root. Leave `NAO_IP` unset for a virtual robot in Choregraphe; set it to the robot's LAN IP for a physical NAO. The default NAOqi port is `9559`.

## Docker Compose

**Linux / Windows**

```sh
docker compose -f docker-compose.dev.yml up --build -d
```

**Apple Silicon** (Docker Compose 2.24.4+)

```sh
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up --build -d
```

Open **http://localhost:8090**. To check the services, run:

```sh
curl http://localhost:8000/commands
curl http://localhost:7001/health
```

Use the same Compose files with `ps` to inspect containers or `down` to stop them. On Apple Silicon, the NAO and translator APIs are exposed on host ports `15000` and `17000` instead of `5000` and `7000`. See [macOS robot setup](docs/nao-macos-setup.md) for Choregraphe and physical robot connection steps.

## Without Docker

Use Python 3.11 for the pose, translator, voice, and exercise services. Install each service's requirements in a virtual environment. In a separate terminal for each service, load the root `.env` with `set -a; . ./.env; set +a`, then run the corresponding command:

| Service | Command |
| --- | --- |
| Pose detection | `python team-19-social-robot/skeletonFinderAPI/server/server.py` |
| Pose translation | `python team-19-social-robot/translator/nao_pose_service.py` |
| Voice commands | `python team-19-social-robot/voiceCommandAPI/server.py` |
| Exercise configuration | `python team-19-social-robot/exerciseConfigService/run.py` |

Keep these terminals in the repository root so relative data paths work. The NAO bridge needs Python 2.7 and its bundled SDK; see [howToRun.txt](howToRun.txt). For the UI, run `cd web && npm ci --force && npm run dev`. For audio transcription, install `team-19-social-robot/audioToTextConverter/requirements.txt` and run `text_from_audio_extractor_service.py` from that service's directory.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SERVICE_NETWORK` | `local` | Uses `localhost` for service calls. Compose sets `docker` to use container names. Replaces `LOCAL` and `NO_NAMING`. |
| `NAO_IP` | Unset | Defaults to `127.0.0.1` locally or `host.docker.internal` in Compose. Set the LAN IP for a physical robot. |
| `NAO_PORT` | `9559` | NAOqi port for virtual or physical robot. |
| `POSE_IMAGES_HOST_DIR` | `./data/pose-images` | Compose pose-image mount. |
| `EXERCISES_HOST_DIR` | `./data/exercises` | Compose exercise-data mount. |
| `REGISTRY` | `jperdek` | Docker image registry. |
| `TAG` | `latest` | Docker image tag. |

For a custom network layout, you can override `POSE_API_URL`, `POSE_FROM_VIDEO_URL`, `SET_POSE_URL`, `NAO_SET_POSE_URL`, `VOICE_LINES_URL`, `EXERCISE_CONFIG_URL`, `VOICE_COMMAND_API_URL`, `EXERCISES_DIR`, `POSE_HOST_ROOT`, and `POSE_CONT_ROOT`. Normally leave them unset: service addresses follow `SERVICE_NETWORK` automatically. A container reaches Choregraphe on the Mac through `host.docker.internal`, not `127.0.0.1`.
