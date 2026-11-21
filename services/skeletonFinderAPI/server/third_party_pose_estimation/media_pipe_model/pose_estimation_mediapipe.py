import base64
import io
import tempfile
import time
from typing import Dict, Iterator, List, Union

# Taken from https://github.com/Ahmed-AI-01/Nao_Mimc/blob/main/Pose_est.py

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


def __should_extract_frame(frame_number: int, fps: int = 30, number_frames_per_sec: int = 1):
    if int(fps // number_frames_per_sec) == 0:
        if frame_number % fps == 0:
            return True
        else:
            return False
    for frame_occurrence in range(0, int(fps), int(fps // number_frames_per_sec)):
        if (frame_occurrence == 0 and frame_number % fps == 0) or (
                frame_occurrence != 0 and frame_number % frame_occurrence == 0):
            return True
    return False


def __process_video_image(orig_image, out: cv2.VideoWriter, total_fps: float,
                          fps_list: List[float], time_list: list[float],
                          min_detection_confidence: float = 0.5,
                          min_tracking_confidence: float = 0.5,
                          is_base64encoded: bool = True,
                          attach_visualization: bool = False) -> Iterator[Dict]:
    img = cv2.cvtColor(orig_image, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img)
    # image = cv2.cvtColor(orig_image, cv2.COLOR_BGR2RGB)  # convert frame to RGB
    start_time = time.time()
    pose_configuration = evaluate_pose_mediapipe(img_pil, min_detection_confidence,
                                                 min_tracking_confidence, is_base64encoded, attach_visualization)
    yield pose_configuration

    end_time = time.time()  # Calculatio for FPS
    fps = 1 / (end_time - start_time)
    total_fps += fps
    fps_list.append(total_fps)  # append FPS in list
    time_list.append(end_time - start_time)  # append time in list
    if attach_visualization:
        # im0 = image[0].permute(1, 2, 0) * 255  # Change format [b, c, h, w] to [h, w, c] for displaying the image.
        # im0 = im0.cpu().numpy().astype(np.uint8)
        # im0 = cv2.cvtColor(im0, cv2.COLOR_RGB2BGR)  # reshape image format to (BGR)
        out.write(orig_image)


def evaluate_pose_from_video_mediapipe(source: str, min_detection_confidence: float = 0.5,
                                       min_tracking_confidence: float = 0.5, number_frames_per_sec: int = 1,
                                       number_seconds_to_process: int = -1, video_frame_per_second: int = 30,
                                       is_base64encoded: bool = True,
                                       attach_visualization: bool = False,
                                       start_seconds: float = 0, end_seconds: float = -1) -> Iterator[Dict]:
    """Pose per sampled frame; start_seconds/end_seconds limit range, negative end means until end."""
    source = base64.b64decode(source) if is_base64encoded else source
    if number_frames_per_sec > video_frame_per_second:
        raise Exception("Number of frames per sec to extract cannot be higher as fps!")
    elif number_frames_per_sec < 1:
        raise Exception("Number of frames per sec to extract should be at least 1")
    frame_count = 0  # count no of frames
    total_fps = 0  # count total fps
    time_list = []  # list to store time
    fps_list = []  # list to store fps

    if isinstance(source, bytes):
        tfile = tempfile.NamedTemporaryFile(delete=True)
        tfile.write(source)
        cap = cv2.VideoCapture(tfile.name)
        tfile.close()
    elif source.isnumeric():
        cap = cv2.VideoCapture(int(source))  # pass video to videocapture object
    else:
        cap = cv2.VideoCapture(source)  # pass video to videocapture object

    if not cap.isOpened():  # check if videocapture not opened
        print('Error while trying to read video. Please check path again')
        raise SystemExit()
    else:
        # range in real seconds, so frame time uses video's own fps; sampling keeps video_frame_per_second
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if not video_fps or video_fps <= 0:
            video_fps = video_frame_per_second
        range_start_frame = None
        frame_width = int(cap.get(3))  # get video frame width
        frame_height = int(cap.get(4))  # get video frame height

        # vid_write_image = letterbox(cap.read()[1], (frame_width), stride=64, auto=True)[0]  # init videowriter
        # resize_height, resize_width = vid_write_image.shape[:2]
        out = None
        if attach_visualization:
            resize_height, resize_width = frame_width, frame_height
            out = cv2.VideoWriter(f"{source}_keypoint.mp4",
                                  cv2.VideoWriter_fourcc(*'mp4v'), video_frame_per_second,
                                  (resize_width, resize_height))

        processed = 0
        frame_number = 0

        while cap.isOpened:  # loop until cap opened or video not complete
            print("Frame {} Processing".format(frame_number + 1))

            ret, frame = cap.read()  # get frame and success from video capture
            if ret:  # if success is true, means frame exist
                frame_number = frame_number + 1
                frame_time = (frame_number - 1) / video_fps
                if frame_time < start_seconds:
                    continue
                if 0 <= end_seconds < frame_time:
                    break
                if range_start_frame is None:
                    range_start_frame = frame_number - 1
                # sampling and seconds limit count from range start
                range_frame = frame_number - 1 - range_start_frame
                if number_seconds_to_process != -1 and range_frame / video_frame_per_second > number_seconds_to_process:
                    print("Number seconds exceeded given threshold of " + str(number_seconds_to_process))
                    break
                if __should_extract_frame(range_frame, video_frame_per_second, number_frames_per_sec):
                    for image_config in __process_video_image(frame, out,
                                                              total_fps, fps_list, time_list,
                                                              min_detection_confidence,
                                                              min_tracking_confidence, is_base64encoded,
                                                              attach_visualization):
                        yield image_config
                    frame_count += 1
                    processed = processed + 1

            else:
                break

        cap.release()
        # cv2.destroyAllWindows()
        if frame_count:
            avg_fps = total_fps / frame_count
            print(f"Average FPS: {avg_fps:.3f}")


def __evaluate_pose_mediapipe_pil_image(orig_image: Image, min_detection_confidence: float = 0.5,
                                        min_tracking_confidence: float = 0.5,
                                        attach_visualization: bool = False) -> Dict:
    pose_configuration = {}
    image = cv2.cvtColor(np.array(orig_image), cv2.COLOR_BGR2RGB)  # convert frame to RGB

    # Setup mediapipe_pose instance
    with mp_pose.Pose(min_detection_confidence=min_detection_confidence,
                      min_tracking_confidence=min_tracking_confidence) as pose:
        # Recolor image to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        # Make detection
        results = pose.process(image)

        # Recolor back to BGR
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Define the names of the landmarks
        # based on https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
        pose_names = ["Nose", "Left eye (inner)", "left eye", "left eye (outer)", "Right eye (inner)",
                      "Right eye", "Right eye (outer)", "Left ear", "Right ear", "Mouth (left)", "Mouth (right)",
                      "Left shoulder", "Right shoulder", "Left elbow", "Right elbow", "Left wrist", "Right wrist",
                      "Left pinky", "Right pinky", "Left index", "Right index", "Left thumb", "Right thumb",
                      "Left hip", "Right hip", "Left knee", "Right knee", "Left ankle", "Right ankle", "Left heel",
                      "Right heel", "Left foot index", "Right foot index"]

        # Extract landmarks
        try:
            pose_landmarks = results.pose_landmarks.landmark
            # Upper body points are from 11 to 16 and 23 to 28
            # upper_body_landmarks = pose_landmarks[11:16]

            # Print and write each landmark's name and coordinates
            for i, landmark in enumerate(pose_landmarks):
                try:
                    pose_configuration[pose_names[i]] = {}
                    pose_configuration[pose_names[i]]["x"] = landmark.x
                    pose_configuration[pose_names[i]]["y"] = landmark.y
                    pose_configuration[pose_names[i]]["z"] = landmark.z
                except Exception as e:
                    print("Cannot get human body landmarks using mediapipe: " + str(e))
                    pose_configuration[pose_names[i]] = "Cannot get due to error."
        except Exception as ee:
            print("Cannot get human body landmarks using mediapipe: " + str(ee))

        if attach_visualization:
            # Render detections
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                      mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                                      mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
                                      )
            visualization_image = Image.fromarray(np.uint8(image)).convert('RGB')
            visualization_byte_array = io.BytesIO()
            visualization_image.save(visualization_byte_array, format='PNG')
            pose_configuration["visualization_base64"] = base64.b64encode(
                visualization_byte_array.getvalue()).decode("utf-8")
    return pose_configuration


def evaluate_pose_mediapipe(orig_image: Union[Image, str], min_detection_confidence: float = 0.5,
                            min_tracking_confidence: float = 0.5, is_base64encoded: bool = True,
                            attach_visualization: bool = False) -> Dict:
    if isinstance(orig_image, str) or isinstance(orig_image, bytes):
        orig_image = base64.b64decode(orig_image) if is_base64encoded else orig_image
        with Image.open(io.BytesIO(orig_image)) as img:
            return __evaluate_pose_mediapipe_pil_image(img, min_detection_confidence,
                                                       min_tracking_confidence, attach_visualization)
    return __evaluate_pose_mediapipe_pil_image(orig_image, min_detection_confidence,
                                               min_tracking_confidence, attach_visualization)
