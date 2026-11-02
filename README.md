# NAO microservices

Run all commands from the repository root. Copy the only environment template before starting:

```sh
cp .env.example .env
mkdir -p data/pose-images data/exercises
```

Edit the **root** `.env` for your robot and host directories. The two former nested `.env` files are no longer used. `.env` is ignored by Git; commit changes to `.env.example` when adding a setting. The old `LOCAL` flag has been replaced by `SERVICE_NETWORK`; `NO_NAMING` has no active use. Compose sets `SERVICE_NETWORK=docker` for its containers even when `.env` says `local` for host processes. The service URL variables below are optional explicit overrides.

## Docker Compose

Install Docker Compose, then run:

```sh
docker compose -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.dev.yml ps
```

Open <http://localhost:8090>. API ports are 5000 (NAO), 6001 (pose), 7000 (translator), 7001 (exercise configuration), 8000 (voice commands), and 9901 (audio transcription). Check `curl http://localhost:8000/commands` and `curl http://localhost:7001/health` before sending robot commands. Stop with `docker compose -f docker-compose.dev.yml down`.

For Apple Silicon, use `docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up --build -d` (Compose 2.24.4+). The Mac override changes the NAO and translator host ports to 15000 and 17000. See the [macOS NAO checklist](docs/nao-macos-setup.md) for the robot connection steps. The older three-service Compose file is available with `docker compose --env-file .env --project-directory . -f team-19-social-robot/docker-compose.yml up --build`; use the root `.env` there too.

## Local processes without Docker

Use Python 3.11 for the pose, translator, voice, and exercise services; the NAOqi bridge needs Python 2.7 and its bundled NAOqi SDK. Install each service's requirements in separate environments. For example:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r team-19-social-robot/skeletonFinderAPI/requirements.txt
pip install -r team-19-social-robot/exerciseConfigService/requirements.txt
pip install -r team-19-social-robot/voiceCommandAPI/requirements.txt
pip install flask flask-cors python-dotenv requests
set -a; . ./.env; set +a
python team-19-social-robot/skeletonFinderAPI/server/server.py
```

Start these in **separate terminals**, each from the repository root with `set -a; . ./.env; set +a` and the same Python environment:

```sh
python team-19-social-robot/translator/nao_pose_service.py
python team-19-social-robot/voiceCommandAPI/server.py
python team-19-social-robot/exerciseConfigService/run.py
```

Start the NAO bridge separately with Python 2.7 after installing its dependencies described in [howToRun.txt](howToRun.txt): `python2 team-19-social-robot/naoRobotAPI/server.py`. For the UI, run `cd web && npm ci --force && npm run dev` and open the URL printed by Vite. The UI's development build calls the local ports; its Compose build uses the Nginx proxy. For local audio transcription, install the `audioToTextConverter` requirements and run `python team-19-social-robot/audioToTextConverter/text_from_audio_extractor_service.py` in another terminal.

On Windows PowerShell, load `.env` into the environment before launching services, or use a tool such as `python-dotenv` to run each command with the root file. Keep all local service processes in the repository root so relative `data/` paths agree.

## Configuration

| Variable | Template default | Purpose and scenario values |
| --- | --- | --- |
| `SERVICE_NETWORK` | `local` | `local` uses `localhost` for service calls; Compose overrides to `docker` and uses service DNS names. |
| `NAO_IP` | unset: local `127.0.0.1`, Docker `host.docker.internal` | Set to the robot's current reachable LAN IP for a real robot. Local Choregraphe uses `127.0.0.1`; Docker reaches NAOqi on the host via `host.docker.internal`. |
| `NAO_PORT` | `9559` | NAOqi port for Choregraphe or a real robot. |
| `POSE_IMAGES_HOST_DIR` | `./data/pose-images` | Host directory mounted at `/images` by Compose. |
| `EXERCISES_HOST_DIR` | `./data/exercises` | Host directory mounted at `/service/exercises` by Compose. |
| `REGISTRY` | `jperdek` | Prefix for Compose image tags. |
| `TAG` | `latest` | Compose image tag. |

Optional service overrides: `POSE_API_URL` defaults to `http://<pose-host>:6001/media_pipe_pose/pose_from_image`; `POSE_FROM_VIDEO_URL` uses the corresponding `/pose_from_video`; `SET_POSE_URL` and `NAO_SET_POSE_URL` default to `http://<robot-host>:5000/setting_pose/setPose`; `VOICE_LINES_URL` uses `/voiceLines/applyVoiceLine`; `EXERCISE_CONFIG_URL` defaults to `http://<exercise-host>:7001`; `VOICE_COMMAND_API_URL` defaults to `http://<voice-host>:8000`. Hosts are `localhost` in local mode and `skeletonfinderapi`, `naorobotapi`, `exerciseconfigservice`, or `voicecommandapi` in Compose. `EXERCISES_DIR` defaults to `./data/exercises` locally and is set to `/service/exercises` by Compose. `POSE_HOST_ROOT` and `POSE_CONT_ROOT` default to `./data/pose-images` locally and `/images` in Compose. Set URL overrides only when using a custom network layout.

The robot IP must be reachable **from the NAO API process**. A container's `127.0.0.1` is the container itself, so use the robot's LAN IP for a physical robot. Choregraphe on the host needs `host.docker.internal` when the NAO API runs in Docker. `NAO_IP` does not change the internal service URLs.
