# Joint temperature logging

`naoRobotAPI` reads the temperature, temperature status, position and electric current of every NAO joint through NAOqi (`ALMemory`) and can record them in the background while an exercise runs. The endpoints only **read** sensors; they never send motion or stiffness commands.

## Endpoints

All paths are on `naoRobotAPI` (port 5000).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/temperature` | One snapshot of all joints |
| POST | `/temperature/log/start` | Start background logging |
| POST | `/temperature/log/stop` | Stop logging and return the summary |
| GET | `/temperature/log/active` | The running log, or `null` |
| GET | `/temperature/log` | Recorded logs, newest first |
| GET | `/temperature/log/<log_id>` | Download the log as CSV |
| GET | `/temperature/log/<log_id>/summary` | Summary of a finished or running log |

`POST /temperature/log/start` accepts an optional JSON body:

| Field | Default | Allowed |
| --- | --- | --- |
| `interval_s` | `1.0` | 0.2–60 seconds between samples |
| `label` | `"exercise"` | 1–64 characters, used in the `log_id` |
| `max_duration_s` | `1800` | 1–14400 seconds; logging stops automatically after this time |

Only one log can run at a time, because there is one robot. A second start returns `409` with the running log. If NAOqi is unreachable, `/temperature` and `/log/start` return `503`.

## Recording an exercise

Run from Git Bash with the stack started (`make dev-start`) and `NAO_IP`/`NAO_PORT` in `.env` pointing to the robot:

```sh
curl -X POST http://localhost:5000/temperature/log/start \
     -H "Content-Type: application/json" \
     -d '{"label": "arms-up-hold", "interval_s": 1}'

# run the exercise, e.g. from the web UI or:
curl -X POST http://localhost:7000/exercise/<exercise_id>/run

curl -X POST http://localhost:5000/temperature/log/stop
```

Logs are stored in `TEMPERATURE_LOG_HOST_DIR` from the root `.env`, by default `logs/temperature/` in the repository root. Docker Compose mounts it into the container as `TEMPERATURE_LOG_DIR`. The default directory is not committed. Each log produces:

- `<log_id>.csv`: one row per joint and sample, written as the log runs:
  `timestamp, elapsed_s, joint, temperature_c, status, position_rad, current_a`
- `<log_id>.summary.json`: written when the log stops.

## Summary

Joints are ordered by heating: first the joints that NAO flagged as hot (`status > 0`, earliest first), then by the largest temperature rise. Joints without temperature data come last.

| Field | Meaning |
| --- | --- |
| `start_c`, `max_c`, `rise_c` | First, highest and rise of the temperature in °C |
| `first_warning_s` | Seconds from the start until NAO first reported `status > 0`; `null` if never |
| `position_at_warning_rad` | Joint angle at that moment |
| `mean_current_a` | Mean absolute current over the log |

The summary also contains `interval_s`, `max_duration_s`, `duration_s`, `samples`, `read_errors` and `stop_reason` (`requested`, `max_duration` or `error`).

## Physical robot session

For every recording, write down in the Jira issue: software commit SHA or tag, date, operator, robot state (battery, starting temperature, time since the last exercise), the exercise and its settings, and the result. Keep a person responsible for the robot present and stop the exercise if NAO reports overheating or behaves unexpectedly.

## Limitations

- Choregraphe's virtual robot only provides `Temperature/Sensor/Status` (always 0); temperature, position and current are logged as empty fields. Heating can only be measured on a physical NAO.
- The running log is kept in memory. If `naoRobotAPI` restarts during a log, the CSV up to that point remains, but no summary is written.
- The Kubernetes manifest has no volume for the logs.
