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

    def make_doc(self, state_a, state_b, name="Trening 1"):
        return {
            "name": name,
            "initial_state": state_a,
            "states": [
                {"state_id": state_a, "label": "Pohyb 1", "x": 120, "y": 80},
                {"state_id": state_b, "label": "Pohyb 2", "x": 120, "y": 240},
            ],
            "transitions": [
                {"id": "t1", "from": state_a, "to": state_b, "label": "Pohyb 1 hotovy"},
            ],
        }

    def test_create_get_list_update_and_delete(self):
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        self.assertEqual(self.client.get("/choreography/list").json, [])

        created_resp = self.client.post("/choreography/create", json=self.make_doc(state_a, state_b))
        self.assertEqual(created_resp.status_code, 201)
        created = created_resp.json
        choreography_id = created["id"]
        self.assertEqual(created["name"], "Trening 1")
        self.assertEqual(created["initial_state"], state_a)
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

        updated_doc = self.make_doc(state_a, state_b, name="Trening 1 (updated)")
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
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        base_doc = self.make_doc(state_a, state_b)

        invalid_docs = {
            "unknown exercise ID": {**base_doc, "states": [
                {"state_id": "deadbeef", "label": "Ghost", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "transition to a foreign state": {**base_doc, "transitions": [
                {"id": "t1", "from": state_a, "to": "deadbeef", "label": "bad"},
            ]},
            "missing initial_state": {**base_doc, "initial_state": None},
            "initial_state not in states": {**base_doc, "initial_state": "deadbeef"},
            "duplicate transition id": {**base_doc, "transitions": [
                {"id": "t1", "from": state_a, "to": state_b, "label": "a"},
                {"id": "t1", "from": state_b, "to": state_a, "label": "b"},
            ]},
            "duplicate state_id": {**base_doc, "states": [
                {"state_id": state_a, "label": "Pohyb 1", "x": 0, "y": 0},
                {"state_id": state_a, "label": "Pohyb 1 again", "x": 10, "y": 10},
            ]},
            "missing name": {**base_doc, "name": ""},
            "non-numeric position": {**base_doc, "states": [
                {"state_id": state_a, "label": "Pohyb 1", "x": "left", "y": 0},
                base_doc["states"][1],
            ]},
            "empty states": {**base_doc, "states": []},
            "path-traversal state_id": {**base_doc, "states": [
                {"state_id": "../outside", "label": "Escape", "x": 0, "y": 0},
                base_doc["states"][1],
            ]},
            "non-finite x (NaN)": {**base_doc, "states": [
                {"state_id": state_a, "label": "Pohyb 1", "x": float("nan"), "y": 0},
                base_doc["states"][1],
            ]},
            "non-finite y (Infinity)": {**base_doc, "states": [
                {"state_id": state_a, "label": "Pohyb 1", "x": 0, "y": float("inf")},
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
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        doc = {**self.make_doc(state_a, state_b), "extra_field": "should not be stored", "id": "ignored"}

        created = self.client.post("/choreography/create", json=doc).json
        self.assertNotIn("extra_field", created)
        self.assertNotEqual(created["id"], "ignored")

        on_disk = (self.root / "_choreographies" / f"{created['id']}.json").read_text()
        self.assertNotIn("extra_field", on_disk)

    def test_create_ignores_unknown_fields_inside_states_and_transitions(self):
        # Unknown fields must be stripped at every level, not only at the top
        # of the document.
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        doc = self.make_doc(state_a, state_b)
        doc["states"][0]["extra_state_field"] = "should not be stored"
        doc["transitions"][0]["extra_transition_field"] = "should not be stored"

        created = self.client.post("/choreography/create", json=doc).json
        self.assertNotIn("extra_state_field", created["states"][0])
        self.assertNotIn("extra_transition_field", created["transitions"][0])

        on_disk = (self.root / "_choreographies" / f"{created['id']}.json").read_text()
        self.assertNotIn("extra_state_field", on_disk)
        self.assertNotIn("extra_transition_field", on_disk)

    def test_malformed_document_in_choreographies_dir_does_not_break_listing_or_delete(self):
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        self.client.post("/choreography/create", json=self.make_doc(state_a, state_b))

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
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        doc = self.make_doc(state_a, state_b)
        doc["transitions"].append({"id": "t2", "from": state_a, "to": state_a, "label": "Retry"})

        result = self.client.post("/choreography/create", json=doc)
        self.assertEqual(result.status_code, 201)

    def test_deleting_exercise_used_in_choreography_is_rejected(self):
        state_a = self.create_exercise("Pohyb 1")
        state_b = self.create_exercise("Pohyb 2")
        created = self.client.post("/choreography/create", json=self.make_doc(state_a, state_b)).json

        blocked = self.client.delete(f"/exercise/{state_a}")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json["choreographies"], [{"id": created["id"], "name": created["name"]}])
        # the exercise itself must still exist
        self.assertEqual(self.client.get(f"/exercise/{state_a}").status_code, 200)

        # an exercise unused by any choreography can still be deleted freely
        unused = self.create_exercise("Unused")
        self.assertEqual(self.client.delete(f"/exercise/{unused}").status_code, 200)

        # once the choreography is gone, the exercise can be deleted too
        self.assertEqual(self.client.delete(f"/choreography/{created['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/exercise/{state_a}").status_code, 200)
