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
| `NAO_PORT` | NAOqi listening port | `9559` | `9559` | `9559` | Choregraphe: `9559`; the team's real robot profile uses `9561`. |
| `EXERCISES_HOST_DIR` | Existing or new exercise storage on the host | `./exercises` | `/home/ubuntu/exercises` for an existing Linux deployment | `D:\service\exercises` for an existing Windows local deployment | Independent of the NAO target. |

All other service addresses are derived from the run mode. `COMPOSE_NETWORK=true` is set by Compose and `false` by the local launcher. `false` is parsed as false, not as a nonempty string. In Compose, services call `skeletonfinderapi`, `naorobotapi`, `voicecommandapi`, and `exercise-config-service` through Docker DNS. Locally they call `localhost` on ports 6001, 5000, 8000, and 7001 respectively. The browser calls the published localhost ports in either mode. `images/` is an ignored data directory; exercise data uses `EXERCISES_HOST_DIR`.

For the team's real NAO profile, set `NAO_IP=10.62.44.100` and `NAO_PORT=9561` in the root `.env`; confirm the current robot address and port before connecting. Ensure the host/container can reach the robot's network. Physical hardware, robot permissions, and model weights require separate preparation. No automated test should send movement commands to a real robot.

If you already have exercises, set `EXERCISES_HOST_DIR` to their **existing** directory before starting this version. For example, use `/home/ubuntu/exercises` for the previous Linux Compose storage or `D:\service\exercises` for the previous Windows local storage. The default `./exercises` creates a new empty store; it does not move old files.

## Docker Compose

Requires Docker Engine/Desktop with Compose **v2.24 or newer**. From the repository root:

```sh
cp .env.example .env
mkdir -p images exercises
# Edit .env if the NAOqi endpoint differs.
docker compose --env-file .env -f docker-compose.dev.yml config --quiet
docker compose --env-file .env -f docker-compose.dev.yml up --build
```

Compose can still validate and start with built-in defaults when `.env` has not been created. Copy `.env.example` before changing any setting; the root `.env` remains the only user-edited configuration file.

Open `http://localhost:8090`. Stop with `docker compose --env-file .env -f docker-compose.dev.yml down`. To start only the configuration service, use `docker compose --env-file .env -f docker-compose.dev.yml up --build --no-deps exercise-config-service`. This requires its image and dependencies, but does not make a physical NAO available.

The first full build downloads Python packages and a pose model. The pinned NAOqi, MediaPipe and TorchCodec dependencies require x86-64 Linux; Compose selects `linux/amd64` for those three services, which may use emulation on ARM hosts. The audio converter also downloads large speech models at runtime. Network access, storage, and compatible CPU resources are required; those downloads are not guaranteed by checkout. The legacy `services/docker-compose.yml` includes the same root definition, so run it from the repository root with `docker compose --env-file .env -f services/docker-compose.yml up --build`.

## Run without Docker

Requires Python **3.12** for skeleton detection, Python **3.11** for translator, voice, exercise configuration and audio conversion, and Node **20** plus npm for the web frontend. Install a matching Python 3 environment per service. The pinned pose and audio dependencies need compatible x86-64 wheels for a full local stack; on an ARM host use an x86-64 environment or the Compose setup above. The skeleton service requires OpenCV system libraries; audio conversion requires FFmpeg and large WhisperX dependencies/models. The NAO adapter additionally requires **Python 2.7**, compatible `pip`/wheels and the vendor's NAOqi Python SDK (`qi`/`naoqi`) on `PYTHONPATH`; its Dockerfile uses Ubuntu 14.04 and bundled Python 2 wheels. Confirm SDK architecture and OS match your Python 2 installation. The physical NAO or Choregraphe simulator must be installed and running separately.

From the repository root, first copy and edit `.env` as above, then create `images/` and `exercises/`. Install Python 3 dependencies in separate virtual environments using each service's `requirements.txt`. The translator uses `flask requests flask-cors`; the NAO adapter uses its `requirements.txt` plus the NAOqi SDK and compatible Python 2 dependencies provided as compatible wheels in `services/naoRobotAPI/compatDep` (the existing adapter README contains unrelated upstream text). For example, on a compatible x86-64 Linux host:

```sh
python3.12 -m venv .venv-skeleton
.venv-skeleton/bin/pip install -r services/skeletonFinderAPI/requirements.txt
python3.11 -m venv .venv-app
.venv-app/bin/pip install flask requests flask-cors
.venv-app/bin/pip install -r services/exerciseConfigService/requirements.txt -r services/voiceCommandAPI/requirements.txt
python3.11 -m venv .venv-audio
.venv-audio/bin/pip install -r services/audioToTextConverter/requirements.txt
mkdir -p images exercises
curl -fL https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7-w6-pose.pt -o services/skeletonFinderAPI/server/yolov7-w6-pose.pt
```

In **separate terminals**, from the repository root, run:

```sh
python3 scripts/run_local.py skeletonfinderapi .venv-skeleton/bin/python
python3 scripts/run_local.py exercise-config-service .venv-app/bin/python
python3 scripts/run_local.py voicecommandapi .venv-app/bin/python
python3 scripts/run_local.py translatorapi .venv-app/bin/python
python3 scripts/run_local.py audio-to-text-converter .venv-audio/bin/python
python3 scripts/run_local.py naorobotapi /path/to/python2.7
```

On Windows PowerShell, install the same dependencies with the matching Python versions and use PowerShell paths:

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv-skeleton
py -3.11 -m venv .venv-app
py -3.11 -m venv .venv-audio
& .\.venv-skeleton\Scripts\python.exe -m pip install -r services\skeletonFinderAPI\requirements.txt
& .\.venv-app\Scripts\python.exe -m pip install flask requests flask-cors
& .\.venv-app\Scripts\python.exe -m pip install -r services\exerciseConfigService\requirements.txt -r services\voiceCommandAPI\requirements.txt
& .\.venv-audio\Scripts\python.exe -m pip install -r services\audioToTextConverter\requirements.txt
New-Item -ItemType Directory -Force images, exercises | Out-Null
Invoke-WebRequest https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7-w6-pose.pt -OutFile services\skeletonFinderAPI\server\yolov7-w6-pose.pt
```

In separate PowerShell windows, use `py -3 scripts/run_local.py skeletonfinderapi .\.venv-skeleton\Scripts\python.exe`, then the same command with `exercise-config-service`, `voicecommandapi`, and `translatorapi` using `.\.venv-app\Scripts\python.exe`, and `audio-to-text-converter` using `.\.venv-audio\Scripts\python.exe`. For `naorobotapi`, install a compatible Windows Python 2.7 NAOqi SDK, set `$env:PYTHONPATH` to its `lib` directory, install the Python 2 dependencies, then pass the Python 2 executable as the second argument. Edit only the root `.env` for its robot address and port.

The last command requires the compatible NAOqi SDK and either Choregraphe or a reachable robot. The script reads only the root `.env` and passes its values to the child process. It maps the example's `host.docker.internal` to `127.0.0.1` for local Choregraphe; a real robot IP passes through unchanged. For the web UI, run `cd web && npm ci && npm run dev` in another terminal; the Vite development URL is printed by npm. Runtime service ports are 5000 (NAO), 6001 (pose), 7000 (translator), 7001 (exercise), 8000 (voice), and 9901 (audio).

## Verification and limits

`python3 -m unittest discover -s tests -p 'test_environment.py'` checks local/Compose address selection without calling a robot. `docker compose --env-file .env -f docker-compose.dev.yml config --quiet` validates Compose. Full image builds and end-to-end use require external packages/models, plus Choregraphe or a real NAO for motion. The frontend's optional LLM integration uses separate credentials and is outside this setup.
