# NAO microservices

Edit **only the repository root `.env`**. From a fresh checkout:

```sh
cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env`. The two former files `services/.env` and `services/naoRobotAPI/.env` are no longer used. The root `.env` is ignored by Git. Do not commit robot addresses or credentials.

## Configuration

| Setting in `.env` | Purpose | Default in `.env.example` | Compose example | Local example | Choregraphe / real NAO |
| --- | --- | --- | --- | --- | --- |
| `NAO_IP` | NAOqi target for `naorobotapi` | `host.docker.internal` | `host.docker.internal` resolves to the Docker host | Launcher maps that value to `127.0.0.1` | Choregraphe: keep default. Real NAO: use its reachable IP address. |
| `NAO_PORT` | NAOqi listening port | `9559` | `9559` | `9559` | Choregraphe: `9559`; real NAO: use the port configured on that robot (often `9559`). |

All other service addresses are derived from the run mode. `COMPOSE_NETWORK=true` is set by Compose and `false` by the local launcher. `false` is parsed as false, not as a nonempty string. In Compose, services call `skeletonfinderapi`, `naorobotapi`, `voicecommandapi`, and `exercise-config-service` through Docker DNS. Locally they call `localhost` on ports 6001, 5000, 8000, and 7001 respectively. The browser calls the published localhost ports in either mode. `images/` and `exercises/` are local, ignored data directories; Compose mounts them into the services.

For a real NAO, change only `NAO_IP` and, if needed, `NAO_PORT` in the root `.env`. Ensure the host/container can reach the robot's network. Physical hardware, robot permissions, and model weights require separate preparation. No automated test should send movement commands to a real robot.

## Docker Compose

Requires Docker Engine/Desktop with Compose v2. From the repository root:

```sh
cp .env.example .env
mkdir -p images exercises
# Edit .env if the NAOqi endpoint differs.
docker compose --env-file .env -f docker-compose.dev.yml config --quiet
docker compose --env-file .env -f docker-compose.dev.yml up --build
```

Open `http://localhost:8090`. Stop with `docker compose --env-file .env -f docker-compose.dev.yml down`. To start only the configuration service, use `docker compose --env-file .env -f docker-compose.dev.yml up --build --no-deps exercise-config-service`. This requires its image and dependencies, but does not make a physical NAO available.

The first full build downloads Python packages and a pose model. The audio converter also downloads large speech models at runtime. Network access, storage, and compatible CPU resources are required; those downloads are not guaranteed by checkout. The legacy `services/docker-compose.yml` includes the same root definition, so run it from the repository root with `docker compose --env-file .env -f services/docker-compose.yml up --build`.

## Run without Docker

Requires Python **3.12** for skeleton detection, Python **3.11** for translator, voice, exercise configuration and audio conversion, and Node **20** plus npm for the web frontend. Install a matching Python 3 environment per service. The skeleton service requires OpenCV system libraries; audio conversion requires FFmpeg and large WhisperX dependencies/models. The NAO adapter additionally requires **Python 2.7**, compatible `pip`/wheels and the vendor's NAOqi Python SDK (`qi`/`naoqi`) on `PYTHONPATH`; its Dockerfile uses Ubuntu 14.04 and bundled Python 2 wheels. Confirm SDK architecture matches your Python 2 installation. The physical NAO or Choregraphe simulator must be installed and running separately.

From the repository root, first copy and edit `.env` as above, then create `images/` and `exercises/`. Install Python 3 dependencies in separate virtual environments using each service's `requirements.txt`. The translator uses `flask requests flask-cors`; the NAO adapter uses its `requirements.txt` plus the NAOqi SDK and compatible Python 2 dependencies provided as compatible wheels in `services/naoRobotAPI/compatDep` (the existing adapter README contains unrelated upstream text). For example, on macOS/Linux:

```sh
python3.12 -m venv .venv-skeleton
.venv-skeleton/bin/pip install -r services/skeletonFinderAPI/requirements.txt
python3.11 -m venv .venv-app
.venv-app/bin/pip install flask requests flask-cors
.venv-app/bin/pip install -r services/exerciseConfigService/requirements.txt -r services/voiceCommandAPI/requirements.txt
python3.11 -m venv .venv-audio
.venv-audio/bin/pip install -r services/audioToTextConverter/requirements.txt
mkdir -p images exercises
```

Use the corresponding `Scripts/python.exe` paths on Windows. In **separate terminals**, from the repository root, run:

```sh
python3 scripts/run_local.py skeletonfinderapi .venv-skeleton/bin/python
python3 scripts/run_local.py exercise-config-service .venv-app/bin/python
python3 scripts/run_local.py voicecommandapi .venv-app/bin/python
python3 scripts/run_local.py translatorapi .venv-app/bin/python
python3 scripts/run_local.py audio-to-text-converter .venv-audio/bin/python
python3 scripts/run_local.py naorobotapi /path/to/python2.7
```

The last command requires the compatible NAOqi SDK and either Choregraphe or a reachable robot. The script reads only the root `.env` and passes its values to the child process. It maps the example's `host.docker.internal` to `127.0.0.1` for local Choregraphe; a real robot IP passes through unchanged. For the web UI, run `cd web && npm ci && npm run dev` in another terminal; the Vite development URL is printed by npm. Runtime service ports are 5000 (NAO), 6001 (pose), 7000 (translator), 7001 (exercise), 8000 (voice), and 9901 (audio).

## Verification and limits

`python3 -m unittest discover -s tests -p 'test_environment.py'` checks local/Compose address selection without calling a robot. `docker compose --env-file .env -f docker-compose.dev.yml config --quiet` validates Compose. Full image builds and end-to-end use require external packages/models, plus Choregraphe or a real NAO for motion. The frontend's optional LLM integration uses separate credentials and is outside this setup.
