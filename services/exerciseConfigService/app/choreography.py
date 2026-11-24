"""
choreography.py — storage and validation for choreographies (graphs of states)

A choreography references existing exercises ("states") by their hash and
connects them with transitions. It is stored as its own JSON file, separate
from any single exercise, inside EXERCISES_DIR:

  /service/exercises/
  ├── a3f9c1d2/                  ← exercise (state), unaffected
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
    "initial_state": "da48eac8",
    "states": [
      {"state_id": "da48eac8", "label": "Pohyb 1", "x": 120, "y": 80}
    ],
    "transitions": [
      {"id": "t1", "from": "da48eac8", "to": "a3f9c1d2", "label": "Pohyb 1 hotovy"}
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

from app import storage

CHOREOGRAPHIES_DIRNAME = "_choreographies"

# Exercise ids and choreography ids are both uuid4().hex[:8]: 8 lowercase hex
# characters. Validating the format (rather than only checking existence on
# disk) also blocks path-traversal values such as "../outside" from ever
# reaching os.path.join()-based lookups.
_HASH_RE = re.compile(r"^[0-9a-f]{8}$")


def is_valid_hash(value) -> bool:
    return isinstance(value, str) and bool(_HASH_RE.match(value))


# =============================================================================
# Path helpers
# =============================================================================

def choreographies_dir() -> str:
    return os.path.join(storage.EXERCISES_DIR, CHOREOGRAPHIES_DIRNAME)


def choreography_path(choreography_id: str) -> str:
    return os.path.join(choreographies_dir(), f"{choreography_id}.json")


def is_valid_id(choreography_id) -> bool:
    return is_valid_hash(choreography_id)


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


def validate_choreography(doc) -> list:
    """
    Validate a choreography document.
    Returns a list of human-readable error strings; empty list means valid.
    """
    errors = []

    if not isinstance(doc, dict):
        return ["document must be a JSON object"]

    name = doc.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("'name' is required and must be a non-empty string")

    schema_version = doc.get("schema_version", 1)
    if schema_version != 1:
        errors.append("'schema_version' must be 1")

    states = doc.get("states")
    state_ids = set()
    if not isinstance(states, list) or len(states) == 0:
        errors.append("'states' must be a non-empty list")
        states = []

    for index, state in enumerate(states):
        if not isinstance(state, dict):
            errors.append(f"states[{index}] must be an object")
            continue
        state_id = state.get("state_id")
        label = state.get("label")
        x = state.get("x")
        y = state.get("y")

        if not is_valid_hash(state_id):
            errors.append(f"states[{index}].state_id is required and must be an 8-character hex exercise id")
        else:
            if state_id in state_ids:
                errors.append(f"duplicate state_id '{state_id}'")
            state_ids.add(state_id)
            if not storage.exercise_exists(state_id):
                errors.append(f"state_id '{state_id}' does not reference an existing exercise")

        if not isinstance(label, str) or not label:
            errors.append(f"states[{index}].label is required and must be a string")
        if not _is_finite_number(x):
            errors.append(f"states[{index}].x must be a finite number")
        if not _is_finite_number(y):
            errors.append(f"states[{index}].y must be a finite number")

    initial_state = doc.get("initial_state")
    if not isinstance(initial_state, str) or not initial_state:
        errors.append("'initial_state' is required")
    elif initial_state not in state_ids:
        errors.append(f"'initial_state' ('{initial_state}') must be one of the choreography's states")

    transitions = doc.get("transitions", [])
    if not isinstance(transitions, list):
        errors.append("'transitions' must be a list")
        transitions = []

    transition_ids = set()
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            errors.append(f"transitions[{index}] must be an object")
            continue
        t_id = transition.get("id")
        t_from = transition.get("from")
        t_to = transition.get("to")
        t_label = transition.get("label")

        if not isinstance(t_id, str) or not t_id:
            errors.append(f"transitions[{index}].id is required and must be a string")
        else:
            if t_id in transition_ids:
                errors.append(f"duplicate transition id '{t_id}'")
            transition_ids.add(t_id)

        if not isinstance(t_from, str) or t_from not in state_ids:
            errors.append(f"transitions[{index}].from ('{t_from}') must reference a state of this choreography")
        if not isinstance(t_to, str) or t_to not in state_ids:
            errors.append(f"transitions[{index}].to ('{t_to}') must reference a state of this choreography")
        if not isinstance(t_label, str) or not t_label:
            errors.append(f"transitions[{index}].label is required and must be a string")

    return errors


# =============================================================================
# CRUD operations
# =============================================================================

def _sanitize_doc(doc: dict) -> dict:
    """
    Keep only the fields that make up a choreography document. The request
    body is otherwise stored as-is, so unknown/extra fields sent by a client
    would end up persisted in the file; this keeps stored documents clean.
    """
    return {
        "name": doc.get("name"),
        "initial_state": doc.get("initial_state"),
        "states": doc.get("states"),
        "transitions": doc.get("transitions", []),
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

    _write_json_atomic(choreography_path(choreography_id), stored)
    return stored


def get_choreography(choreography_id: str) -> dict:
    if not choreography_exists(choreography_id):
        raise FileNotFoundError(f"Choreography '{choreography_id}' not found")
    return _read_json(choreography_path(choreography_id))


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
    """Return [{id, name}] for every choreography that references exercise_id as a state."""
    result = []
    for entry, doc in _iter_choreography_documents():
        state_ids = {
            state.get("state_id")
            for state in doc.get("states", [])
            if isinstance(state, dict)
        }
        if exercise_id in state_ids:
            result.append({"id": doc.get("id", entry.name[:-5]), "name": doc.get("name", "")})

    return result


def choreography_count() -> int:
    """Number of valid choreography documents stored on disk (used by /health)."""
    return sum(1 for _ in _iter_choreography_documents())
