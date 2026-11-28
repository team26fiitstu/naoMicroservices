# Exercise and choreography file formats

The service stores exercise and choreography documents as JSON under
`EXERCISES_DIR`. Their Draft 2020-12 schemas live in `app/schemas/`.
`$schema` identifies the JSON Schema draft; `schema_version` identifies the
NAOMI file format.

## Exercise config

`app/schemas/exercise-config.schema.json` describes each exercise's
`config.json`. Version 1 contains:

- `schema_version`: `1`.
- `id`: the eight-character exercise ID.
- `name`, `created_at`, and `pose_engine` (`mediapipe` or `yolo`).
- `repetitions`: a positive integer.
- `frame_sequence`: non-negative frame IDs in playback order. Repeated IDs are
  allowed.
- Optional `video_range`, `calories`, and `description`.

The version 1 schema allows additional config properties so existing custom
fields remain preserved; the listed fields are the service's defined contract.

Old exercise configs have no `schema_version`; the service treats a missing
version as version 1 when reading and writing them. New configs contain the
explicit version. This requires no bulk migration. Timestamps remain strings so
older timezone-naive values remain valid; new records use UTC ISO 8601.

## Choreography

`app/schemas/choreography.schema.json` describes choreography files in
`EXERCISES_DIR/_choreographies/`. Version 1 contains `schema_version`, a
generated choreography `id`, `name`, `initial_state`, `states`, `transitions`,
and generated `created_at` and `updated_at` timestamps.

Each state has a `state_id`, an `exercise_id`, a display `label`, and editor
coordinates `x` and `y`. `initial_state` and transition `from`/`to` values
refer to state IDs in the same graph. For compatibility with the current
playback service, `state_id` must equal `exercise_id`; the latter explicitly
identifies the exercise played by the state. Both fields and `schema_version`
are required in requests; missing fields and properties outside the schema are
rejected. A transition contains only its `id`, `from`, `to`, and `label`; it has
no conditions or repetition counters. States and transitions are saved as part
of the whole graph.

The service validates the complete request against the JSON Schema, then checks
relationships JSON Schema cannot express: referenced exercises exist, state
and transition IDs are unique, the initial state belongs to the graph, and
transition endpoints belong to the graph.
