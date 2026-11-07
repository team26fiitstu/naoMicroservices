# Repository Stucture

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

# Docker compose orchestration (without command API connected to LLM)

From the repository root, edit **only** the root `.env`:

```sh
cp .env.example .env
mkdir -p images exercises
docker compose --env-file .env -f docker-compose.dev.yml config --quiet
docker compose --env-file .env -f docker-compose.dev.yml up --build
```

Requires Docker Compose v2.24+. On PowerShell, use `Copy-Item .env.example .env` and `New-Item -ItemType Directory -Force images, exercises`. Compose also works without `.env` using defaults, but copy the example to change settings.

# Robot configuration

Set `NAO_IP` and `NAO_PORT` in the root `.env` for both modes. The local launcher maps `host.docker.internal` to `127.0.0.1` for Choregraphe.

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

For existing exercises, set `EXERCISES_HOST_DIR` in the same `.env` to their current folder (for example `/home/ubuntu/exercises` or `D:\service\exercises`). Default: `./exercises`.

Apply changes:

```docker compose --env-file .env -f docker-compose.dev.yml up -d naorobotapi```



# Python Installation

### Python 2.7 (Windows Installation  NAO Robot API)

- 1. Download Python 2.7 (https://www.python.org/download/releases/2.7/)
- 2. Install Python 2.7
- 3. Download Nao python SDK from https://aldebaran.com/en/support/kb/nao6/downloads/nao6-software-downloads/ and extract it + add it to path (http://doc.aldebaran.com/2-5/dev/python/install_guide.html):

```cd D:\originalRobotics\robot\robot```


- 4. Set PYTHONPATH system environment variable (premenne prostredia - systemove):

```PYTHONPATH``` ```C:\Program Files\pynaoqi\lib```


- 5. Download wheel pip, wheel setuptools, and wheel files from https://pypi.org: https://pypi.org/project/pip/20.3.4/#files
- 6. Run and install using Python2.7 and its pip:

```"C:\Python27\python.exe" .\get-pip.py "pip-20.3.4-py2.py3-none-any.whl" "setuptools-44.0.0-py2.py3-none-any.whl" "wheel-0.37.0-py2.py3-none-any.whl"```

```"C:\Python27\python.exe" -m pip install ./winDependencies/qi-1.8.3-cp27-none-win_amd64.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/almath-1.6.8-cp27-none-win_amd64.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/chardet-4.0.0-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/urllib3-1.26.3-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/idna-2.9-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/certifi-2020.6.20-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/requests-2.25.1-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/gTTS-token-1.1.4.tar.gz```
```"C:\Python27\python.exe" -m pip install ./winDependencies/click-7.1.2-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/six-1.15.0-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/backports.functools_lru_cache-1.6.1-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/soupsieve-1.9.6-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/beautifulsoup4-4.9.3-py2-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/gTTS-2.1.0-py2-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/numpy-1.16.1-cp27-cp27m-win32.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/python_dateutil-2.8.1-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/pytz-2019.3-py2.py3-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/pandas-0.23.3-cp27-cp27m-win_amd64.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/enum34-1.1.10-py2-none-any.whl```
```"C:\Python27\python.exe" -m pip install ./winDependencies/pathlib-1.0.1.tar.gz```
```"C:\Python27\python.exe" -m pip install ./winDependencies/pyzbar-0.1.7-py2.py3-none-win_amd64.whl```


- 7. Run microservice to command NAO:

```py -3 scripts/run_local.py naorobotapi C:\Python27\python.exe```



### Python 3 services

Use Python 3.12 for `skeletonfinderapi`, Python 3.11 for the other Python 3 services, Node 20 for `web`, and FFmpeg for audio. Install each service's `requirements.txt` in its own virtual environment; `translatorapi` needs `flask requests flask-cors`. The pose service also needs the YOLO weight used by its Dockerfile (`yolov7-w6-pose.pt`) in `services/skeletonFinderAPI/server/`. Pinned NAOqi, MediaPipe and TorchCodec dependencies require compatible x86-64 builds. Heavy models and a robot or Choregraphe must be prepared separately.

# Run without Docker

Run from the repository root in separate terminals. `scripts/run_local.py` loads the root `.env` for each service; use the interpreter from its prepared environment:

```sh
python3 scripts/run_local.py skeletonfinderapi .venv-skeleton/bin/python
python3 scripts/run_local.py exercise-config-service .venv-app/bin/python
python3 scripts/run_local.py voicecommandapi .venv-app/bin/python
python3 scripts/run_local.py translatorapi .venv-app/bin/python
python3 scripts/run_local.py audio-to-text-converter .venv-audio/bin/python
python3 scripts/run_local.py naorobotapi /path/to/python2.7
```

On Windows PowerShell, replace `python3` with `py -3` and `.venv-*/bin/python` with `.venv-*\Scripts\python.exe`. Install a matching Python 2.7 NAOqi SDK for `naorobotapi`. Start the web UI with `cd web`, `npm ci`, `npm run dev`.

## Dedicated disk location

`EXERCISES_HOST_DIR` in the root `.env` selects the host exercise directory. Point it to the existing directory before upgrading; the default `./exercises` is a new empty store.
