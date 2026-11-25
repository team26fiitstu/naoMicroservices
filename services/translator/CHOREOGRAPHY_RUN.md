# Running a choreography

**Translator** runs choreographies. **exerciseConfigService** stores each
choreography as a graph and serves it through
`GET /choreography/<choreography_id>`. Each state in the graph points to a saved
exercise through its `state_id`.

Imagine a choreography with two saved exercises. A transition named `go`
leads from the first exercise to the second. If the first exercise is current,
sending `go` plays the second one. The transition stores the first exercise's
ID in `from` and the second exercise's ID in `to`.

The stored graph has `schema_version: 1`, `id`, `initial_state`, `states`, and
`transitions`. Each transition has an `id`, `from`, `to`, and `label`.

In the API examples, names in angle brackets are placeholders, not values to
send literally. Replace `<choreography_id>` and `<target_exercise_id>` with the
real IDs of a saved graph and exercise. Those IDs are eight lowercase
hexadecimal characters. Send JSON for requests with a body.

## Run a graph

| Action | Request | What happens |
| --- | --- | --- |
| Start | `POST /choreography/<choreography_id>/run` | Loads the graph and plays its `initial_state`. No request body is needed. |
| Follow a transition | `POST /choreography/<choreography_id>/run/signal` with `{"transition_id":"go"}` | Plays the target exercise if the transition starts at the current state. |
| Set the state directly | `PUT /choreography/<choreography_id>/run/state` with `{"state_id":"<target_exercise_id>"}` | Moves the current state to any state in the graph. Sends no speech or motion command. |
| Read the state | `GET /choreography/<choreography_id>/run` | Returns the current state. |
| Stop | `DELETE /choreography/<choreography_id>/run` | Ends the run. Later signals are rejected. |

Start and a successful signal return `200` with the new state and a playback
report. For example:

```json
{
  "state": {
    "choreography_id": "<choreography_id>",
    "state_id": "<target_exercise_id>",
    "active": true
  },
  "playback": {
    "exercise_id": "<target_exercise_id>",
    "repetitions": 1,
    "frames_per_rep": 1,
    "total_poses_sent": 2,
    "results": [
      {"rep": 0, "frame_index": 0, "type": "voice", "status": "ok"},
      {"rep": 0, "frame_index": 0, "type": "pose", "status": "ok"}
    ]
  }
}
```

The state `GET` and direct-state `PUT` return only the `state` object shown above. `DELETE`
returns the same fields with `active: false`. The name `total_poses_sent` comes
from the existing exercise API; it counts entries in `results`, including voice
commands.

## Playback order

Translator requests `GET /exercise/<state_id>/frames`, which returns frames in
the saved `frame_sequence` order. It plays that sequence for the exercise's
stored `repetitions`. On each frame, it sends any `voice_lines` before
`nao_angles`.

The graph is loaded once, at start. Editing the graph later does not change an
active run. Exercise frames and repetitions are fetched when that exercise is
played.

## Errors and state after failure

Error responses contain an `error` message. Translator reports choreography
playback as successful only when the robot confirms every command.

| Status | When it is returned |
| --- | --- |
| `400` | The choreography ID format, a required JSON field, or the exercise's stored repetition count is invalid. |
| `404` | The choreography, transition, state, or target exercise is unknown. |
| `409` | No run is active; a run is already active; a transition starts at another state; or a conflicting request or playback is in progress. A second stop also returns `409`. |
| `422` | The target exercise has no frames. |
| `502` | exerciseConfigService cannot be reached, returns invalid graph or exercise data, or robot playback fails. |

If a robot call fails, translator stops playback at that command and returns
`502` with `partial_playback: true` and the attempted `playback` report. A
failed signal leaves the source `state_id` current. A failed start creates no
active run; for a robot failure its response has `state: null`. Speech or
movement already sent to the robot cannot be undone. Retrying a signal may
repeat those commands.

## Concurrent runs and restarts

Runs have separate states by choreography ID. Within one translator process,
requests for the same ID do not overlap: a request arriving while that run is
busy receives `409`. Only one choreography or standalone exercise can play on
the robot at a time. A competing choreography playback receives `409`; the
existing `POST /exercise/<id>/run` waits for the current playback to finish.
State reads, direct changes, and stops for other IDs remain available.

Run state and locks live in translator memory. A restart loses active runs, and
separate translator processes do not share them. Use one process for run control
until shared storage and distributed locking are added. Other robot control
routes do not use the playback lock and need separate coordination.

The existing `POST /exercise/<id>/run` keeps its response shape and its
behavior of returning HTTP `200` with individual robot errors in `results`.
