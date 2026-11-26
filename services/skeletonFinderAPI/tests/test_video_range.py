"""Offline tests of video frame selection; OpenCV, MediaPipe and NumPy are replaced by fakes."""
import sys
import types
import unittest
from unittest.mock import patch

from tests._support import ROOT, load_module

MODEL_PATH = ROOT / "services/skeletonFinderAPI/server/third_party_pose_estimation/media_pipe_model/pose_estimation_mediapipe.py"


class FakeCapture:
    """Video of `frames` frames at `fps`; each frame is its index. Records decoded frames."""

    def __init__(self, frames, fps, seekable=True):
        self.frames, self.fps, self.seekable = frames, fps, seekable
        self.position, self.decoded = 0, []

    def isOpened(self):
        return True

    def read(self):
        if self.position >= self.frames:
            return False, None
        self.decoded.append(self.position)
        self.position += 1
        return True, self.position - 1

    def set(self, prop, value):
        if prop != "pos_frames" or not self.seekable:
            return False
        self.position = min(int(value), self.frames)
        return True

    def get(self, prop):
        return {"fps": self.fps, "pos_frames": self.position}.get(prop, 640)

    def release(self):
        pass


def load_model():
    fakes = {
        "cv2": types.SimpleNamespace(CAP_PROP_FPS="fps", CAP_PROP_POS_FRAMES="pos_frames", VideoWriter=object),
        "mediapipe": types.SimpleNamespace(solutions=types.SimpleNamespace(drawing_utils=None, pose=None)),
        "numpy": types.ModuleType("numpy"),
    }
    with patch.dict(sys.modules, fakes):
        return load_module("offline_pose_estimation", MODEL_PATH)


model = load_model()


def processed_frames(frames=300, fps=30, capture=None, **options):
    """Indices of frames sent to pose estimation."""
    model.cv2.VideoCapture = lambda source: capture or FakeCapture(frames, fps)

    def process(frame, *args):
        yield frame

    with patch.object(model, "__process_video_image", process), patch("builtins.print"):
        return list(model.evaluate_pose_from_video_mediapipe("video.mp4", is_base64encoded=False, **options))


class VideoRange(unittest.TestCase):
    def test_without_range_one_frame_per_second(self):
        self.assertEqual(processed_frames(), [0, 30, 60, 90, 120, 150, 180, 210, 240, 270])

    def test_seconds_limit_without_range(self):
        self.assertEqual(processed_frames(number_seconds_to_process=3), [0, 30, 60, 90])

    def test_range_uses_real_frame_rate(self):
        self.assertEqual(processed_frames(start_seconds=2, end_seconds=4), [60, 90, 120])
        self.assertEqual(processed_frames(fps=60, frames=600, start_seconds=2, end_seconds=4), [120, 180, 240])

    def test_sampling_uses_source_frame_rate(self):
        self.assertEqual(processed_frames(fps=25, frames=250), list(range(0, 250, 25)))
        self.assertEqual(processed_frames(fps=29.97, frames=300), list(range(0, 300, 30)))
        self.assertEqual(processed_frames(fps=60, frames=600, number_seconds_to_process=2), [0, 60, 120])

    def test_rate_not_dividing_frame_rate(self):
        self.assertEqual(processed_frames(number_frames_per_sec=4, end_seconds=0.99), [0, 8, 15, 23])

    def test_rate_above_source_frame_rate_is_rejected(self):
        with self.assertRaises(Exception):
            processed_frames(fps=25, frames=250, number_frames_per_sec=30)

    def test_range_past_video_end_gives_no_frames(self):
        self.assertEqual(processed_frames(start_seconds=20), [])

    def test_range_start_is_seeked_not_decoded(self):
        capture = FakeCapture(300, 30)
        self.assertEqual(processed_frames(capture=capture, start_seconds=2, end_seconds=4), [60, 90, 120])
        self.assertEqual(capture.decoded[0], 60)

    def test_seek_lands_before_fractional_start(self):
        capture = FakeCapture(300, 29.97)
        self.assertEqual(processed_frames(capture=capture, start_seconds=2), list(range(60, 300, 30)))
        self.assertEqual(capture.decoded[0], 59)

    def test_unseekable_video_decodes_from_start(self):
        capture = FakeCapture(300, 30, seekable=False)
        self.assertEqual(processed_frames(capture=capture, start_seconds=2, end_seconds=4), [60, 90, 120])
        self.assertEqual(capture.decoded[0], 0)

    def test_seconds_limit_counts_from_range_start(self):
        self.assertEqual(processed_frames(start_seconds=5, number_seconds_to_process=3), [150, 180, 210, 240])


if __name__ == "__main__":
    unittest.main()
