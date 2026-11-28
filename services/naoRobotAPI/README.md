# NAO Robot API

Flask API for sending pose and speech commands to a SoftBank NAO robot using the bundled NAOqi SDK.

## Run

From the repository root, set the robot address and start the service:

```sh
NAO_IP=127.0.0.1 NAO_PORT=9559 docker compose -f docker-compose.dev.yml up --build naorobotapi
```

Replace `127.0.0.1` with the reachable IP address of your NAO robot to use robot commands.

The API listens on `http://localhost:5000`. The container uses Python 2.7 and the bundled NAOqi libraries for `linux/amd64`.

## Endpoints

- `GET /` — health check; returns `OK`.
- `GET /tests/test` — run the robot movement demo.
- `POST /setting_pose/setPose` — set 22 joint angles: `{"angles": [/* 22 numbers */]}`.
- `POST /setting_pose/setPoseMediapipe` — send pose data in the request body.
- `POST /voiceLines/applyVoiceLine` — apply speech settings or speak text. Example: `{"voice_lines": {"lang": "English", "extractedText": "Hello"}}`.
- `POST /control/reservation` — reserve or renew robot control with `{"token":"<run_id>"}`.
- `DELETE /control/reservation` — release that reservation with the same JSON body.

Reservation tokens must be non-empty strings of at most 64 characters.

Robot-changing requests are serialized within this service process. While a
choreography has a reservation, pose, speech and test commands must include
`X-Robot-Run-Token: <run_id>`; other requests receive `409`. Translator renews
the reservation while its run is active and releases it after stopping. If
translator disappears, the reservation expires after 120 seconds. This token
coordinates commands; it is not an authentication credential. Run one robot
API process per robot, since locks and reservations are kept in process memory.
If translator cannot confirm a release, it rejects new playback with `409`
until the possible reservation has expired (up to 120 seconds).
Release also retires the token, so a delayed renewal cannot reserve the robot
again. The service remembers the most recent 1000 retired tokens in memory;
`DELETE` is safe to repeat even if the lease has expired.

Pose and speech commands need a reachable robot at `NAO_IP:NAO_PORT`. `setPoseMediapipe` currently forwards the raw request body to its handler;
