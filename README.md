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
│   ├── common/                     # Shared modules copied into service images
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

From the repository root, run the offline tests with Python 3.12:

```sh
python3 -m venv /tmp/nao-offline-venv
/tmp/nao-offline-venv/bin/python -m pip install -r tests/requirements-offline.txt
/tmp/nao-offline-venv/bin/python -m pytest -q
```

`pytest.ini` discovers tests in `tests/` and `services/*/tests/`. Tests in `manual/` need a prepared environment and are excluded. The offline suite uses stubs and does not connect to a robot.

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
| `HTTP_RETRY_MAX_ATTEMPTS` | Total attempts for inter-service HTTP calls | `3` |
| `HTTP_RETRY_BACKOFF_SECONDS` | Initial delay between retries | `1` |
| `HTTP_RETRY_BACKOFF_FACTOR` | Backoff multiplier after each attempt | `2` |
| `HTTP_RETRY_MAX_BACKOFF_SECONDS` | Upper bound for a single retry delay | `10` |
| `HTTP_RETRY_STATUS_CODES` | HTTP statuses that trigger a retry (comma-separated) | `429,500,502,503,504` |

Compose and Python service entry points read the root `.env` automatically; existing process variables take precedence. Without Docker, NAO API maps `host.docker.internal` to `127.0.0.1` for Choregraphe.

Shared Python modules live in `services/common/` (currently `http_retry.py`). The Docker builds of `translatorapi`, `voicecommandapi`, and `exercise-config-service` copy them from the named build context `common` into each image. When running a service directly without Docker, add `services/common` to `PYTHONPATH`:

```sh
PYTHONPATH=services/common python services/translator/nao_pose_service.py
```

The shared module is injected with Compose `additional_contexts` (`common=./services/common`), which requires Docker Compose v2.17 or newer (the v2.24+ requirement above already covers it). Tests for the shared module live in `services/common/tests/`.

All HTTP calls between services go through a shared retry helper: a temporarily unavailable peer is retried `HTTP_RETRY_MAX_ATTEMPTS` times with an exponentially growing delay. When every attempt fails, a clear error is logged and returned to the caller (typically as `502` with the failure detail).

Calls with side effects (`setPose`, `applyVoiceLine`, `POST /exercise/create`, `pose_from_video`) are not idempotent, so they pass `idempotent=False`: they are retried only when the request provably never left the client (connection refused, DNS failure, connect timeout) and never on read timeouts, aborted connections or `5xx`/`429` responses. `applyVoiceLine` is never retried (`max_attempts=1`). `GET`/`PUT`/`DELETE` and other safe calls keep the full retry behaviour.

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
