# Exercise and choreography file formats

- Exercise and choreography documents are JSON files stored under
  `EXERCISES_DIR`.
- Their Draft 2020-12 JSON Schemas are in `app/schemas/`.
- `$schema` identifies the JSON Schema draft; `schema_version` identifies the
  NAOMI document format.

## Exercise config

Schema: `app/schemas/exercise-config.schema.json`  
File: `<exercise-id>/config.json`

Version 1 fields:

- Required:
  - `schema_version`: `1`.
  - `id`: the eight-character exercise ID.
  - `name`: non-empty exercise name.
  - `created_at`: timestamp string.
  - `pose_engine`: `mediapipe` or `yolo`.
  - `repetitions`: positive integer.
  - `frame_sequence`: non-negative frame IDs in playback order. Repeated IDs
    are allowed.
- Optional:
  - `video_range`.
  - `calories`.
  - `description`.
- Additional properties are allowed so existing custom config fields remain
  preserved.

Version handling:

- If an older config has no `schema_version`, the service treats it as version
  `1` when reading or writing it.
- New exercise configs store `schema_version: 1` explicitly.
- No bulk migration is required.
- Timestamps remain strings so older timezone-naive values remain valid; new
  records use UTC ISO 8601.

## Choreography

Schema: `app/schemas/choreography.schema.json`  
File: `EXERCISES_DIR/_choreographies/<choreography-id>.json`

Version 1 document fields:

- `schema_version`: `1`.
- `id`: generated eight-character choreography ID.
- `name`: non-empty choreography name.
- `initial_state`: ID of a state in this graph.
- `states`: non-empty list of states.
- `transitions`: list of transitions; it can be empty.
- `created_at` and `updated_at`: generated timestamp strings.

State fields:

- `id`: unique graph state ID, such as `s1`.
- `exercise_id`: string ID of an existing exercise (eight lowercase
  hexadecimal characters).
- `label`: non-empty display label.
- `x` and `y`: editor coordinates.

Transition fields:

- `id`: non-empty transition ID.
- `from` and `to`: state IDs in this graph.
- `label`: non-empty transition label.
- Transitions do not contain conditions or repetition counters.

Validation and version handling:

- If `schema_version` is missing on create/update requests or in a stored
  document, the service treats it as version `1`.
- Newly written choreography files store `schema_version: 1` explicitly.
- The service rejects properties that are not defined by the choreography
  schema.
- It also checks relationships the JSON Schema cannot express: referenced
  exercises exist, state and transition IDs are unique, `initial_state` names a
  state in the graph, and transition endpoints name states in the graph.
