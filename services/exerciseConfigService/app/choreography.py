"""
choreography.py — storage and validation for choreographies (graphs of states)

A choreography has graph states that explicitly reference existing exercises
and connects them with transitions. It is stored as its own JSON file,
separate from any single exercise, inside EXERCISES_DIR:

  /service/exercises/
  ├── a3f9c1d2/                  ← exercise referenced by a graph state
  └── _choreographies/
      ├── c1d2e3f4.json
      └── b7e2a091.json

The "_choreographies" directory has no config.json of its own, so
list_exercises()/exercise_exists() in storage.py keep ignoring it.

Choreography document:
  {
    "schema_version": 1,
    "id": "c1d2e3f4",
    "name": "Trening 1",
    "initial_state": "s1",
    "states": [
      {"id": "s1", "exercise_id": "da48eac8", "label": "Pohyb 1", "x": 120, "y": 80},
      {"id": "s2", "exercise_id": "a3f9c1d2", "label": "Pohyb 2", "x": 120, "y": 240}
    ],
    "transitions": [
      {"id": "t1", "from": "s1", "to": "s2", "label": "Pohyb 1 hotovy"}
    ],
    "created_at": "...",
    "updated_at": "..."
  }
"""

import os
import re
import math
import json
import uuid
import tempfile
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from app import storage

CHOREOGRAPHIES_DIRNAME = "_choreographies"

# Exercise IDs and choreography IDs are both eight lowercase hexadecimal
# characters. Validate the ID before using it in a filesystem path.
_ID_RE = re.compile(r"^[0-9a-f]{8}$")

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schemas", "choreography.schema.json")
with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    CHOREOGRAPHY_SCHEMA = json.load(schema_file)
Draft202012Validator.check_schema(CHOREOGRAPHY_SCHEMA)
CHOREOGRAPHY_VALIDATOR = Draft202012Validator(CHOREOGRAPHY_SCHEMA)
CHOREOGRAPHY_INPUT_SCHEMA = {
    **CHOREOGRAPHY_SCHEMA,
    "required": [
        field for field in CHOREOGRAPHY_SCHEMA["required"]
        if field not in {"id", "created_at", "updated_at"}
    ],
}
CHOREOGRAPHY_INPUT_VALIDATOR = Draft202012Validator(CHOREOGRAPHY_INPUT_SCHEMA)


def is_valid_id(value) -> bool:
    """Return whether value has the format used by exercise and graph IDs."""
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


# =============================================================================
# Path helpers
# =============================================================================

def choreographies_dir() -> str:
    return os.path.join(storage.EXERCISES_DIR, CHOREOGRAPHIES_DIRNAME)


def choreography_path(choreography_id: str) -> str:
    return os.path.join(choreographies_dir(), f"{choreography_id}.json")


def choreography_exists(choreography_id: str) -> bool:
    return is_valid_id(choreography_id) and os.path.isfile(choreography_path(choreography_id))


def _utcnow_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# JSON helpers (atomic writes so a crash can't leave a half-written graph)
# =============================================================================

def _read_json(path: str):
    with open(path, "r") as f:
        return json.load(f)


def _iter_choreography_documents():
    """
    Yield every valid choreography document stored on disk.

    Shared by list_choreographies(), choreographies_using() and health()'s
    choreography count, so all three agree on what counts as a stored
    choreography: a *.json file in _choreographies/ whose content is a JSON
    object. A file that is valid JSON but not an object (e.g. after a manual
    edit) is skipped rather than raising, so a single bad file cannot break
    listing, usage lookups or the health check.
    """
    directory = choreographies_dir()
    if not os.path.isdir(directory):
        return

    for entry in os.scandir(directory):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        try:
            doc = _read_json(entry.path)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(doc, dict):
            continue
        yield entry, doc


def _write_json_atomic(path: str, data) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# =============================================================================
# Validation
# =============================================================================

def _is_finite_number(value) -> bool:
    """True for plain ints/floats, excluding bool, NaN and +/-Infinity.

    NaN/Infinity would pass isinstance(value, (int, float)) but are not
    valid JSON literals, so a browser cannot parse the stored document
    back; they must be rejected here instead of only checking the type.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _schema_errors(doc, validator=CHOREOGRAPHY_VALIDATOR) -> list:
    errors = validator.iter_errors(doc)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or 'document'}: {error.message}"
        for error in sorted(errors, key=lambda item: tuple(str(part) for part in item.absolute_path))
    ]


def validate_choreography(doc) -> list:
    """
    Validate the graph body and its exercise references.
    Returns human-readable errors; empty list means valid.
    """
    if not isinstance(doc, dict):
        return ["document must be a JSON object"]

    request_doc = dict(doc)
    request_doc.setdefault("schema_version", 1)
    errors = _schema_errors(request_doc, CHOREOGRAPHY_INPUT_VALIDATOR)
    if errors:
        return errors
    graph = _sanitize_doc(request_doc)
    if not graph["name"].strip():
        errors.append("name must not be blank")

    states = graph["states"]
    state_ids = set()
    for state in states:
        state_id = state["id"]
        exercise_id = state["exercise_id"]
        if state_id in state_ids:
            errors.append(f"duplicate state ID '{state_id}'")
        state_ids.add(state_id)
        if not storage.exercise_exists(exercise_id):
            errors.append(f"exercise ID '{exercise_id}' does not reference an existing exercise")
        if not _is_finite_number(state["x"]):
            errors.append(f"state '{state_id}' x must be a finite number")
        if not _is_finite_number(state["y"]):
            errors.append(f"state '{state_id}' y must be a finite number")

    initial_state = graph["initial_state"]
    if initial_state not in state_ids:
        errors.append(f"initial_state '{initial_state}' must be one of the graph's state IDs")

    transition_ids = set()
    for transition in graph["transitions"]:
        transition_id = transition["id"]
        if transition_id in transition_ids:
            errors.append(f"duplicate transition ID '{transition_id}'")
        transition_ids.add(transition_id)

        if transition["from"] not in state_ids:
            errors.append(f"transition '{transition_id}' from must reference a state ID in this graph")
        if transition["to"] not in state_ids:
            errors.append(f"transition '{transition_id}' to must reference a state ID in this graph")

    return errors


# =============================================================================
# CRUD operations
# =============================================================================

def _sanitize_state(state) -> dict:
    """Keep the state fields defined by the choreography schema."""
    return {
        "id": state["id"],
        "exercise_id": state["exercise_id"],
        "label": state["label"],
        "x": state["x"],
        "y": state["y"],
    }


def _sanitize_transition(transition) -> dict:
    """Keep only id, from, to, label from a single transition entry."""
    return {
        "id": transition["id"],
        "from": transition["from"],
        "to": transition["to"],
        "label": transition["label"],
    }


def _sanitize_doc(doc: dict) -> dict:
    """
    Keep the client-owned fields from a schema-validated choreography body.
    Generated metadata is added by create_choreography/replace_choreography.
    """
    return {
        "schema_version": doc.get("schema_version", 1),
        "name": doc["name"],
        "initial_state": doc["initial_state"],
        "states": [_sanitize_state(state) for state in doc["states"]],
        "transitions": [_sanitize_transition(transition) for transition in doc["transitions"]],
    }


def create_choreography(doc: dict) -> dict:
    """Create a new choreography. Caller must validate `doc` beforehand."""
    choreography_id = uuid.uuid4().hex[:8]
    now = _utcnow_isoformat()

    stored = _sanitize_doc(doc)
    stored["schema_version"] = 1
    stored["id"] = choreography_id
    stored["created_at"] = now
    stored["updated_at"] = now

    schema_errors = _schema_errors(stored)
    if schema_errors:
        raise ValueError("invalid choreography: " + "; ".join(schema_errors))

    _write_json_atomic(choreography_path(choreography_id), stored)
    return stored


def get_choreography(choreography_id: str) -> dict:
    if not choreography_exists(choreography_id):
        raise FileNotFoundError(f"Choreography '{choreography_id}' not found")
    doc = _read_json(choreography_path(choreography_id))
    if isinstance(doc, dict):
        doc.setdefault("schema_version", 1)
    return doc


def replace_choreography(choreography_id: str, doc: dict) -> dict:
    """Replace the whole graph. Caller must validate `doc` beforehand."""
    if not choreography_exists(choreography_id):
        raise FileNotFoundError(f"Choreography '{choreography_id}' not found")

    existing = _read_json(choreography_path(choreography_id))

    stored = _sanitize_doc(doc)
    stored["schema_version"] = 1
    stored["id"] = choreography_id
    stored["created_at"] = existing.get("created_at", _utcnow_isoformat())
    stored["updated_at"] = _utcnow_isoformat()

    schema_errors = _schema_errors(stored)
    if schema_errors:
        raise ValueError("invalid choreography: " + "; ".join(schema_errors))

    _write_json_atomic(choreography_path(choreography_id), stored)
    return stored


def delete_choreography(choreography_id: str) -> None:
    if not choreography_exists(choreography_id):
        raise FileNotFoundError(f"Choreography '{choreography_id}' not found")
    os.remove(choreography_path(choreography_id))


def list_choreographies() -> list:
    """Return a summary list: [{id, name, state_count, created_at, updated_at}]"""
    result = []
    for entry, doc in _iter_choreography_documents():
        if "id" not in doc:
            continue
        result.append({
            "id": doc["id"],
            "name": doc.get("name", ""),
            "state_count": len(doc.get("states", [])),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
        })

    result.sort(key=lambda x: x["updated_at"], reverse=True)
    return result


def choreographies_using(exercise_id: str) -> list:
    """Return [{id, name}] for each choreography referencing exercise_id."""
    result = []
    for entry, doc in _iter_choreography_documents():
        exercise_ids = {
            state.get("exercise_id")
            for state in doc.get("states", [])
            if isinstance(state, dict)
        }
        if exercise_id in exercise_ids:
            result.append({"id": doc.get("id", entry.name[:-5]), "name": doc.get("name", "")})

    return result


def choreography_count() -> int:
    """Number of valid choreography documents stored on disk (used by /health)."""
    return sum(1 for _ in _iter_choreography_documents())
