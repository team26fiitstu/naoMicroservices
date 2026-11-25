# Running a choreography

The formatted NAOMI document is maintained in
[`naomi-documents/vystupy/choreography-run/main.tex`](https://github.com/team26fiitstu/naomi-documents/tree/main/vystupy/choreography-run).
This page is a quick reference for translator developers.

A choreography is a graph of saved exercises. The graph comes from
`GET /choreography/<id>` in exerciseConfigService. Starting a run loads the
graph once and schedules its initial exercise in the background. Translator
plays the saved frame order, repetitions, voice lines and poses. A successful
performance changes the run from `performing` to `waiting`.

| Action | Request | Result |
| --- | --- | --- |
| Start | `POST /choreography/<id>/run` | `202` with a new `run_id`; performs the initial state asynchronously. |
| Find active run | `GET /run/current` | `200` with run data, or `404` when none is active. |
| Inspect run | `GET /run/<run_id>` | `200` with current state, status, outgoing transitions, playback report and error. |
| Follow transition | `POST /run/<run_id>/signal` with `{"transition_id":"go"}` | `202` when waiting and `go` starts at the current state; schedules the target exercise. |
| Move without playback | `POST /run/<run_id>/goto` with `{"state_id":"<exercise_id>"}` | `200` with the chosen state; sends no speech or motion. |
| Stop | `POST /run/<run_id>/stop` | `200` with status `stopped`; prevents further playback between robot commands. |

`<id>`, `<run_id>` and `<exercise_id>` are placeholders. `go` is an example
transition ID from the stored graph. It is not a special command.

All successful responses use the same shape:

```json
{
  "run_id": "<run_id>",
  "choreography_id": "<id>",
  "state_id": "<exercise_id>",
  "status": "waiting",
  "outgoing_transitions": [
    {"id": "go", "from": "<exercise_id>", "to": "<next_exercise_id>", "label": "Continue"}
  ],
  "playback": null,
  "error": null
}
```

`playback` is filled after an exercise attempt. A failed start ends in
`stopped`; a failed signal leaves the source state in `waiting` and sets
`error`. Partial robot motion or speech cannot be undone. Poll `GET /run/<run_id>`
for the outcome rather than treating `202` as completed playback.

`400` means invalid input, `404` an unknown ID or no active run, `409` a
conflicting operation, and `502` a failed choreography fetch or invalid graph.
An empty or unavailable exercise is discovered in the worker and reported in
the run's `error` field. Only one run may be active in a translator process.
State and locks are process-local and are lost on restart. A physical NAO test
is still required before live use.
