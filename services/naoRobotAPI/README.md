# NAO Robot API

Flask API for sending pose and speech commands to a SoftBank NAO robot using the bundled NAOqi SDK.

## Run

From the repository root, set the robot address and start the service:

```sh
NAO_IP=<robot-ip> NAO_PORT=9559 docker compose -f docker-compose.dev.yml up --build naorobotapi
```

The API listens on `http://localhost:5000`. The container uses Python 2.7 and the bundled NAOqi libraries for `linux/amd64`.

## Endpoints

- `GET /` — health check; returns `OK`.
- `GET /tests/test` — run the robot movement demo.
- `POST /setting_pose/setPose` — set 22 joint angles: `{"angles": [/* 22 numbers */]}`.
- `POST /setting_pose/setPoseMediapipe` — send pose data in the request body.
- `POST /voiceLines/applyVoiceLine` — apply speech settings or speak text. Example: `{"voice_lines": {"lang": "English", "extractedText": "Hello"}}`.

Pose and speech commands need a reachable robot at `NAO_IP:NAO_PORT`. `setPoseMediapipe` currently forwards the raw request body to its handler;
