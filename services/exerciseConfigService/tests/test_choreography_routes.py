"""Offline HTTP contract tests for choreographies (graphs of states)."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests._support import OfflineCase, ROOT

SERVICE_DIR = ROOT / "services/exerciseConfigService"
sys.path.insert(0, str(SERVICE_DIR))
from app import create_app  # noqa: E402
from app import storage  # noqa: E402
from app import choreography  # noqa: E402


class ChoreographyRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"EXERCISES_DIR": temporary.name})
        environment.start()
        self.addCleanup(environment.stop)
        storage_dir = patch.object(storage, "EXERCISES_DIR", temporary.name)
        storage_dir.start()
        self.addCleanup(storage_dir.stop)
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def create_exercise(self, name="Pohyb"):
        result = self.client.post("/exercise/create", json={
            "name": name,
            "pose_engine": "mediapipe",
            "frames": [{"keypoints": {"arm": [1, 2]}, "nao_angles": [0.1, 0.2]}],
        })
        self.assertEqual(result.status_code, 201)
        return result.json["id"]

    def make_doc(self, exercise_a, exercise_b, name="Trening 1"):
        return {
            "name": name,
            "initial_state": "s1",
            "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb 1", "x": 120, "y": 80},
                {"id": "s2", "exercise_id": exercise_b, "label": "Pohyb 2", "x": 120, "y": 240},
            ],
            "transitions": [
                {"id": "t1", "from": "s1", "to": "s2", "label": "Pohyb 1 hotovy"},
            ],
        }

    def test_create_get_list_update_and_delete(self):
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        self.assertEqual(self.client.get("/choreography/list").json, [])

        created_resp = self.client.post("/choreography/create", json=self.make_doc(exercise_a, exercise_b))
        self.assertEqual(created_resp.status_code, 201)
        created = created_resp.json
        choreography_id = created["id"]
        self.assertEqual(created["name"], "Trening 1")
        self.assertEqual(created["initial_state"], "s1")
        self.assertIn("created_at", created)
        self.assertIn("updated_at", created)
        stored_file = self.root / "_choreographies" / f"{choreography_id}.json"
        self.assertTrue(stored_file.is_file())

        fetched = self.client.get(f"/choreography/{choreography_id}")
        self.assertEqual((fetched.status_code, fetched.json), (200, created))

        listed = self.client.get("/choreography/list")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json), 1)
        self.assertEqual(listed.json[0]["id"], choreography_id)
        self.assertEqual(listed.json[0]["state_count"], 2)

        # existing exercises must keep working and must not list choreographies
        self.assertEqual(len(self.client.get("/exercise/list").json), 2)
        health = self.client.get("/health").json
        self.assertEqual(health["exercise_count"], 2)
        self.assertEqual(health["choreography_count"], 1)

        updated_doc = self.make_doc(exercise_a, exercise_b, name="Trening 1 (updated)")
        updated_resp = self.client.put(f"/choreography/{choreography_id}", json=updated_doc)
        self.assertEqual(updated_resp.status_code, 200)
        self.assertEqual(updated_resp.json["name"], "Trening 1 (updated)")
        self.assertEqual(updated_resp.json["id"], choreography_id)
        self.assertEqual(updated_resp.json["created_at"], created["created_at"])
        self.assertNotEqual(updated_resp.json["updated_at"], created["updated_at"])

        deleted = self.client.delete(f"/choreography/{choreography_id}")
        self.assertEqual((deleted.status_code, deleted.json), (200, {"deleted": choreography_id}))
        self.assertFalse(stored_file.exists())
        self.assertEqual(self.client.get("/choreography/list").json, [])
        self.assertEqual(self.client.get(f"/choreography/{choreography_id}").status_code, 404)
        # the exercises themselves stay untouched
        self.assertEqual(len(self.client.get("/exercise/list").json), 2)

    def test_validation_rejects_invalid_graphs_and_does_not_persist_anything(self):
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        base_doc = self.make_doc(exercise_a, exercise_b)

        invalid_docs = {
            "unknown exercise hash": {**base_doc, "states": [
                {"id": "s1", "exercise_id": "deadbeef", "label": "Ghost", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "missing exercise_id": {**base_doc, "states": [
                {"id": "s1", "label": "Pohyb 1", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "path-traversal exercise_id": {**base_doc, "states": [
                {"id": "s1", "exercise_id": "../outside", "label": "Escape", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "transition to a foreign state": {**base_doc, "transitions": [
                {"id": "t1", "from": "s1", "to": "s9", "label": "bad"},
            ]},
            "transition by exercise id instead of state id": {**base_doc, "transitions": [
                {"id": "t1", "from": exercise_a, "to": exercise_b, "label": "old model"},
            ]},
            "missing initial_state": {**base_doc, "initial_state": None},
            "initial_state not in states": {**base_doc, "initial_state": "s9"},
            "duplicate transition id": {**base_doc, "transitions": [
                {"id": "t1", "from": "s1", "to": "s2", "label": "a"},
                {"id": "t1", "from": "s2", "to": "s1", "label": "b"},
            ]},
            "duplicate state id": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb 1", "x": 0, "y": 0},
                {"id": "s1", "exercise_id": exercise_b, "label": "Pohyb 2", "x": 10, "y": 10},
            ]},
            "duplicate state label": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb", "x": 0, "y": 0},
                {"id": "s2", "exercise_id": exercise_b, "label": "Pohyb", "x": 10, "y": 10},
            ]},
            "same label with extra spaces": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb", "x": 0, "y": 0},
                {"id": "s2", "exercise_id": exercise_b, "label": "Pohyb ", "x": 10, "y": 10},
            ]},
            "blank state label": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "   ", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "unsafe state id": {**base_doc, "states": [
                {"id": "../s1", "exercise_id": exercise_a, "label": "Pohyb 1", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "old state_id field": {**base_doc, "states": [
                {"state_id": exercise_a, "label": "Pohyb 1", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "missing name": {**base_doc, "name": ""},
            "non-numeric position": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb 1", "x": "left", "y": 0},
                base_doc["states"][1],
            ]},
            "empty states": {**base_doc, "states": []},
            "non-finite x (NaN)": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb 1", "x": float("nan"), "y": 0},
                base_doc["states"][1],
            ]},
            "non-finite y (Infinity)": {**base_doc, "states": [
                {"id": "s1", "exercise_id": exercise_a, "label": "Pohyb 1", "x": 0, "y": float("inf")},
                base_doc["states"][1],
            ]},
        }
        for description, doc in invalid_docs.items():
            with self.subTest(description=description):
                result = self.client.post("/choreography/create", json=doc)
                self.assertEqual(result.status_code, 400)
                self.assertIn("errors", result.json)
                self.assertTrue(len(result.json["errors"]) > 0)
        self.assertEqual(self.client.get("/choreography/list").json, [])

        self.assertEqual(self.client.post("/choreography/create", data="not json").status_code, 400)

        # a valid choreography followed by an invalid PUT must not change the stored data
        created = self.client.post("/choreography/create", json=base_doc).json
        choreography_id = created["id"]
        bad_put = self.client.put(f"/choreography/{choreography_id}", json={**base_doc, "initial_state": None})
        self.assertEqual(bad_put.status_code, 400)
        self.assertEqual(self.client.get(f"/choreography/{choreography_id}").json, created)

    def test_unknown_or_malformed_id_returns_404(self):
        for choreography_id in ("deadbeef", "../etc", "not-hex!!"):
            with self.subTest(choreography_id=choreography_id):
                self.assertEqual(self.client.get(f"/choreography/{choreography_id}").status_code, 404)
                self.assertEqual(
                    self.client.put(f"/choreography/{choreography_id}", json={}).status_code, 404,
                )
                self.assertEqual(self.client.delete(f"/choreography/{choreography_id}").status_code, 404)

    def test_create_ignores_unknown_fields(self):
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        doc = {**self.make_doc(exercise_a, exercise_b), "extra_field": "should not be stored", "id": "ignored"}

        created = self.client.post("/choreography/create", json=doc).json
        self.assertNotIn("extra_field", created)
        self.assertNotEqual(created["id"], "ignored")

        on_disk = (self.root / "_choreographies" / f"{created['id']}.json").read_text()
        self.assertNotIn("extra_field", on_disk)

    def test_create_ignores_unknown_fields_inside_states_and_transitions(self):
        # Unknown fields must be stripped at every level, not only at the top
        # of the document.
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        doc = self.make_doc(exercise_a, exercise_b)
        doc["states"][0]["extra_state_field"] = "should not be stored"
        doc["transitions"][0]["extra_transition_field"] = "should not be stored"

        created = self.client.post("/choreography/create", json=doc).json
        self.assertNotIn("extra_state_field", created["states"][0])
        self.assertNotIn("extra_transition_field", created["transitions"][0])

        on_disk = (self.root / "_choreographies" / f"{created['id']}.json").read_text()
        self.assertNotIn("extra_state_field", on_disk)
        self.assertNotIn("extra_transition_field", on_disk)

    def test_malformed_document_in_choreographies_dir_does_not_break_listing_or_delete(self):
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        self.client.post("/choreography/create", json=self.make_doc(exercise_a, exercise_b))

        choreographies_dir = self.root / "_choreographies"
        # Simulate a manually edited file that is valid JSON but not an object.
        (choreographies_dir / "broken.json").write_text("[1, 2, 3]")

        listed = self.client.get("/choreography/list")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json), 1)

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json["choreography_count"], 1)

        # an exercise not referenced by the broken file must still be deletable
        unused = self.create_exercise("Unused")
        self.assertEqual(self.client.delete(f"/exercise/{unused}").status_code, 200)

    def test_self_loop_transition_is_allowed(self):
        # Design confirmation (SCRUM-90): a transition may connect a state to
        # itself, e.g. "retry this pose".
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        doc = self.make_doc(exercise_a, exercise_b)
        doc["transitions"].append({"id": "t2", "from": "s1", "to": "s1", "label": "Retry"})

        result = self.client.post("/choreography/create", json=doc)
        self.assertEqual(result.status_code, 201)

    def test_same_exercise_in_several_states_is_allowed(self):
        # each state has its own id, so one exercise can be repeated, e.g. rest between exercises
        exercise = self.create_exercise("Odpocinok")
        other = self.create_exercise("Cvik A")
        doc = {
            "name": "S opakovanim",
            "initial_state": "s1",
            "states": [
                {"id": "s1", "exercise_id": exercise, "label": "Odpocinok po rozcvicke", "x": 0, "y": 0},
                {"id": "s2", "exercise_id": other, "label": "Cvik A", "x": 240, "y": 0},
                {"id": "s3", "exercise_id": exercise, "label": "Odpocinok po cviku A", "x": 480, "y": 0},
            ],
            "transitions": [
                {"id": "t1", "from": "s1", "to": "s2", "label": "Hotovo"},
                {"id": "t2", "from": "s2", "to": "s3", "label": "Hotovo"},
            ],
        }

        created = self.client.post("/choreography/create", json=doc)
        self.assertEqual(created.status_code, 201)
        self.assertEqual([s["exercise_id"] for s in created.json["states"]], [exercise, other, exercise])
        self.assertEqual(self.client.delete(f"/exercise/{exercise}").status_code, 409)

    def test_deleting_exercise_used_in_choreography_is_rejected(self):
        exercise_a = self.create_exercise("Pohyb 1")
        exercise_b = self.create_exercise("Pohyb 2")
        created = self.client.post("/choreography/create", json=self.make_doc(exercise_a, exercise_b)).json

        blocked = self.client.delete(f"/exercise/{exercise_a}")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json["choreographies"], [{"id": created["id"], "name": created["name"]}])
        # the exercise itself must still exist
        self.assertEqual(self.client.get(f"/exercise/{exercise_a}").status_code, 200)

        # an exercise unused by any choreography can still be deleted freely
        unused = self.create_exercise("Unused")
        self.assertEqual(self.client.delete(f"/exercise/{unused}").status_code, 200)

        # once the choreography is gone, the exercise can be deleted too
        self.assertEqual(self.client.delete(f"/choreography/{created['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/exercise/{exercise_a}").status_code, 200)
