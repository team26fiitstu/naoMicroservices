# NAO on macOS: connection and local services

This checklist is for an Apple Silicon Mac. The source presentation shows the sequence on slides 19–26; the network and Choregraphe steps require the physical robot.

## 1. Identify the robot and software

Check the robot's actual model and NAOqi version on its landing page before downloading Choregraphe. The presentation calls the robot “NAO V5”, but its screenshot shows **NAOqi 2.8.7.4**. SoftBank's documentation associates NAOqi 2.1 with V5 and NAOqi 2.8 with V6, so these slides do not establish which model will be available. Use the Choregraphe release that matches the robot's NAOqi generation. The Python 2.7/Linux NAOqi binaries committed under `naoRobotAPI/pynaoqi` cannot be loaded directly by macOS on Apple Silicon.

Official software documentation: <https://doc.aldebaran.com/>.

## 2. First connection with Ethernet

1. Have the robot, its charger, an Ethernet cable, and a USB-C Ethernet adapter available. Put the robot in a safe, clear area.
2. Turn the robot on and connect Ethernet to the Mac. A short press of the chest button makes the robot announce its current IP address.
3. On the Mac, open `http://<robot-ip>/` in a browser. If the page does not load, verify that the Ethernet interface has an address in the same subnet as the robot; the robot may announce a link-local `169.254.x.x` address for a direct cable. Do not assume the sample `10.62.44.100` from this repository is current.
4. The presentation lists default web credentials `nao` / `naoRobot0`. Use them only if the robot has not been reconfigured; obtain the current credentials from its owner if they do not work.
5. On the landing page, open Network Settings and join the robot to a Wi-Fi network that the Mac can also use. A phone hotspot or ordinary WPA2 network is a practical choice when institutional Wi-Fi requires browser-based or enterprise sign-in. Record the new IP; it can differ from the Ethernet IP.
6. Disconnect Ethernet, connect the Mac to the same Wi-Fi, press the chest button again, and open `http://<new-robot-ip>/`. Check `ping <new-robot-ip>` and `nc -vz <new-robot-ip> 9559` from Terminal. Network isolation on some guest Wi-Fi networks can block device-to-device access even when both devices have internet.

## 3. Choregraphe

Install the Choregraphe version matching the actual NAOqi generation. In Choregraphe, use **Connect to** → enter the newly announced IP and port `9559` → connect. The screenshots in the presentation were made on Windows; menus can differ on macOS. An older Intel-only Choregraphe build may need Rosetta on Apple Silicon, and compatibility with macOS 26 must be verified with that specific build. If it cannot run, use a supported Intel Mac or Windows machine for Choregraphe while keeping the Mac for the other services.

## 4. Local microservices without the robot

From the repository root, pass **both** Compose files in this order. The base file keeps its original Linux/Windows ports and paths; `docker-compose.mac.yml` applies Apple Silicon settings only to these commands. Docker Compose 2.24.4 or newer is required for the override file.

```sh
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up -d --build --no-deps voicecommandapi exercise-config-service
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml ps -a voicecommandapi exercise-config-service
curl http://localhost:8000/commands
curl http://localhost:7001/health
curl http://localhost:7001/exercise/list
```

`voicecommandapi` serves the preset commands on port 8000. `exercise-config-service` stores exercise data in `./data/exercises` and serves port 7001. Listing commands and exercises does **not** move the robot. Do not send `POST /command` until the robot connection and available space have been checked.

The translator can also start without the robot to verify its own API process. Its `/test` endpoint does not run a pose or contact NAO:

```sh
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up -d --build --no-deps translatorapi
curl http://localhost:17000/test
```

The full pipeline also has `skeletonfinderapi` (image/video pose detection, port 6001), `translatorapi` (pose conversion, container port 7000), `naorobotapi` (NAOqi bridge, container port 5000), and `web` (UI, port 8090). macOS Control Center often occupies host ports 5000 and 7000, so the Mac override maps them to 15000 and 17000. The skeleton image downloads a large YOLO model at build time. The NAO bridge uses Ubuntu 14.04, Python 2.7, and x86_64 Linux libraries, so it runs under `linux/amd64` emulation on Apple Silicon. Its image now builds and its HTTP root endpoint starts on this Mac; connection to NAOqi remains untested until the robot is available. Docker Desktop's Apple Virtualization framework plus Rosetta can accelerate amd64 emulation; Docker VMM currently does not support Rosetta.

When the physical robot is reachable, pass its **current** IP to Compose:

```sh
NAO_IP=<new-robot-ip> docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml up -d --build naorobotapi
curl http://localhost:15000/
```

`curl /` checks only that the API process is running; it does not prove that NAOqi can connect or that motion commands are safe. The next integration step is to build and verify `skeletonfinderapi` and `translatorapi`, then start the UI. Avoid launching the complete Compose stack until each stage has passed.

Stop the locally started services with:

```sh
docker compose -f docker-compose.dev.yml -f docker-compose.mac.yml stop naorobotapi translatorapi voicecommandapi exercise-config-service
```

Sources: the supplied presentation, repository configuration, <https://doc.aldebaran.com/>, and Docker's [Mac install](https://docs.docker.com/desktop/setup/install/mac-install/) and [virtualization settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/) documentation.
