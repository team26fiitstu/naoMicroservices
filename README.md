# Repository Structure

```
naoMicroservices/
├── docs/                           # Documentation and setup guides
├── k8s/                            # Kubernetes manifests
├── samples/
│   ├── input/                      # Input files (audio, video, images)
│   │   ├── images/
│   │   └── videos/
│   ├── processed/                  # Processed data and extracted frames
│   └── exercises/                  # Example exercises
├── scripts/                        # Utility and helper scripts
├── services/                       # Backend microservices
│   ├── audioToTextConverter/
│   ├── exerciseConfigService/
│   ├── naoRobotAPI/
│   ├── skeletonFinderAPI/
│   ├── translator/
│   ├── voiceCommandAPI/
│   └── ...
├── web/                            # Web application
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── docker-compose.dev.yml
└── docker-compose.build.yml
```

# Autonomous Python tests

From the repository root, use Python 3.12 and an isolated environment. Only Flask, HTTP client, Pillow, dotenv, and pytest are needed; pose model and NAOqi packages are replaced with test stubs.

```sh
python3 -m venv /tmp/nao-offline-venv
/tmp/nao-offline-venv/bin/python -m pip install -r tests/offline/requirements.txt
/tmp/nao-offline-venv/bin/python -m pytest -q tests/offline services/translator/tests/test_arms_translator.py tests/test_environment.py
```

The final command is the complete offline test run. HTTP tests are grouped by service in `tests/offline/test_translator_routes.py`, `test_skeleton_routes.py`, and `test_robot_routes.py`. They use Flask test clients and a fake NAO interface installed before robot modules are imported. The run excludes `services/translator/tests/test_integration.py`, the older route tests requiring missing root-level media files, and the robot/model test scripts that require running services, models, or hardware. It never connects to a physical robot.

# Docker Compose

GitHub Actions publishes images to `ghcr.io/team26fiitstu` from `master`. Use `TAG=sha-<commit>` for a specific version or `TAG=latest` for the latest published set. Pull requests build changed images without publishing.

Requires Docker Engine/Desktop with Compose v2.24+. Run from the repository root:

```sh
cp .env.example .env
docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml up --build
```

On PowerShell, use `Copy-Item .env.example .env`. Open http://localhost:8090.

To use prebuilt images with the configured `REGISTRY` and `TAG`:

```sh
docker compose -f docker-compose.dev.yml pull
docker compose -f docker-compose.dev.yml up --no-build
```

Stop the services:

```sh
docker compose -f docker-compose.dev.yml down
```

View logs:

```sh
docker compose -f docker-compose.dev.yml logs -f
```

The first build downloads dependencies and the pose model. Audio transcription may download additional speech models. Choregraphe or a physical NAO must be prepared separately.

# Environment configuration

Copy the root `.env.example` to `.env` and edit only that file. Nested `.env` files are no longer used. Do not commit `.env`.

| Variable | Purpose | Default |
| --- | --- | --- |
| `NAO_IP` | NAOqi address | `host.docker.internal` |
| `NAO_PORT` | NAOqi port | `9559` |
| `REGISTRY` | Docker image namespace | `ghcr.io/team26fiitstu` |
| `TAG` | Docker image tag | `latest` |
| `EXERCISES_HOST_DIR` | Exercise directory on the host | `./exercises` |

Compose and Python service entry points read the root `.env` automatically; existing process variables take precedence. Without Docker, NAO API maps `host.docker.internal` to `127.0.0.1` for Choregraphe.

## Robot configuration

Real robot:

```
NAO_IP=10.62.44.100
NAO_PORT=9561
```

Choregraphe:

```
NAO_IP=host.docker.internal
NAO_PORT=9559
```

Apply changes:

```docker compose -f docker-compose.dev.yml up -d naorobotapi```

## Dedicated disk location

Set `EXERCISES_HOST_DIR` in the root `.env` to the existing exercise directory. The default `./exercises` creates a new empty store.
