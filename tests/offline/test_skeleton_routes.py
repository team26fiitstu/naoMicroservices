"""Offline HTTP tests for skeletonFinderAPI routes."""
import sys
import types
from unittest.mock import Mock, patch

from _support import OfflineCase, ROOT, load_module

# Model modules are replaced before the skeleton server imports its blueprints.
SKELETON_DIR = ROOT / "services/skeletonFinderAPI/server"
sys.path.insert(0, str(SKELETON_DIR))
MODEL_NAMES = {
    "third_party_pose_estimation.media_pipe_model.pose_estimation_mediapipe":
        ("evaluate_pose_mediapipe", "evaluate_pose_from_video_mediapipe"),
    "third_party_pose_estimation.yolo_model.pose_estimate":
        ("evaluate_yolo_pose_from_video",),
    "third_party_pose_estimation.yolo_model.yolo_image_only": ("process_image",),
}
for module_name, functions in MODEL_NAMES.items():
    fake = types.ModuleType(module_name)
    for function in functions:
        setattr(fake, function, Mock(side_effect=AssertionError("model called without a test stub")))
    sys.modules[module_name] = fake
skeleton = load_module("offline_skeleton_server", SKELETON_DIR / "server.py")
skeleton.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
mediapipe = sys.modules[
    "third_party_pose_estimation.media_pipe_model.media_pipe_pose_api"
]
yolo = sys.modules["third_party_pose_estimation.yolo_model.yolo_pose_api"]

class SkeletonRoutes(OfflineCase):
    def setUp(self):
        super().setUp()
        self.client = skeleton.app.test_client()

    def test_health(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_post_pose_routes(self):
        cases = (
            ("/media_pipe_pose/pose_from_image", mediapipe, "evaluate_pose_mediapipe", {"joint": 1}),
            ("/media_pipe_pose/pose_from_video", mediapipe, "evaluate_pose_from_video_mediapipe", [{"joint": 1}]),
            ("/yolo_pose/pose_from_image", yolo, "process_image", {"person": 1}),
            ("/yolo_pose/pose_from_video", yolo, "evaluate_yolo_pose_from_video", [{"person": 1}]),
        )
        for path, module, function, payload in cases:
            with self.subTest(path=path):
                with patch.object(module, function, return_value=payload) as model:
                    result = self.client.post(path, data=b"encoded")
                self.assertEqual((result.status_code, result.json), (200, payload))
                model.assert_called_once()
                with patch.object(module, function, side_effect=ValueError("bad media")):
                    self.assertEqual(self.client.post(path, data=b"bad").status_code, 500)

    def test_pose_options_reach_model_stubs(self):
        with patch.object(mediapipe, "evaluate_pose_mediapipe", return_value={}) as model:
            result = self.client.post("/media_pipe_pose/pose_from_image?min_detection_confidence=0.7&attach_visualization=1", data="encoded")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(model.call_args.args[0], "encoded")
        self.assertEqual(model.call_args.kwargs["min_detection_confidence"], 0.7)
        self.assertTrue(model.call_args.kwargs["attach_visualization"])
        with patch.object(yolo, "evaluate_yolo_pose_from_video", return_value=[]) as model:
            result = self.client.post("/yolo_pose/pose_from_video?number_frames_per_sec=2&number_seconds_to_process=5", data="encoded")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(model.call_args.kwargs["number_frames_per_sec"], 2)
        self.assertEqual(model.call_args.kwargs["number_seconds_to_process"], 5)

    def test_get_pose_routes_and_missing_path(self):
        cases = (
            ("/media_pipe_pose/pose_from_image", mediapipe, "evaluate_pose_mediapipe", {"joint": 1}),
            ("/media_pipe_pose/pose_from_video", mediapipe, "evaluate_pose_from_video_mediapipe", [{"joint": 1}]),
            ("/yolo_pose/pose_from_image", yolo, "process_image", {"person": 1}),
            ("/yolo_pose/pose_from_video", yolo, "evaluate_yolo_pose_from_video", [{"person": 1}]),
        )
        for path, module, function, payload in cases:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 500)
                file_stub = patch.object(mediapipe.Image, "open") if module is mediapipe and "image" in path else patch("builtins.open")
                with file_stub, patch.object(module, function, return_value=payload) as model:
                    result = self.client.get(path, query_string={"file_location": "fake-media"})
                self.assertEqual((result.status_code, result.json), (200, payload))
                model.assert_called_once()
                if "video" in path:
                    self.assertEqual(self.client.get(path, query_string={"file_location": "fake", "number_frames_per_sec": "bad"}).status_code, 500)
