# NAO on macOS

A short guide for Apple Silicon Macs. Run all terminal commands from the repository root. Use Docker Compose 2.24.4 or newer.

## 1. Connect to a robot

Choose the robot you want to control:

| Robot | Choregraphe connection | Root `.env` |
| --- | --- | --- |
| Virtual robot on this Mac | `127.0.0.1:9559` | Leave `NAO_IP` unset; keep `NAO_PORT=9559`. |
| Physical NAO | Robot's current LAN IP, port `9559` | Set `NAO_IP` to that same IP. |

For a **physical NAO**, turn it on and press its chest button briefly to hear its IP address. Connect the Mac and robot to the same network. Check the connection with:

```sh
ping <robot-ip>
nc -vz <robot-ip> 9559
```

If you need to configure Wi-Fi, connect the robot by Ethernet first, open `http://<robot-ip>/` in a browser, and use its Network Settings. The IP may change after switching to Wi-Fi. Check the robot's actual NAOqi version before choosing a Choregraphe release; the model named in older project slides may not match the pictured software version.

## 2. Prepare the project

```sh
test -f .env || cp .env.example .env
mkdir -p data/pose-images data/exercises
```

Edit only the **root** `.env`. For a physical robot, set `NAO_IP` to its current address. For the virtual robot, leave it unset: Docker reaches Choregraphe on the Mac through `host.docker.internal`.

## 3. Start the full stack

```sh
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up --build -d
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml ps
```

The first build downloads large dependencies and a pose model. Open **http://localhost:8090** when all seven containers are running. On macOS, the NAO API uses port `15000` and the translator uses `17000`.

Check the services without moving the robot:

```sh
curl http://localhost:8000/commands
curl http://localhost:7001/health
curl http://localhost:17000/test
```

These HTTP checks show that the services are running; they do not test robot motion. If the robot's IP changes, update `NAO_IP` in `.env` and recreate the NAO API container with `docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up -d naorobotapi`.

To stop everything:

```sh
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml down
```

The NAO bridge and audio service run as `linux/amd64` containers under emulation on Apple Silicon. For general configuration and local runs without Docker, see the [root README](../README.md).
