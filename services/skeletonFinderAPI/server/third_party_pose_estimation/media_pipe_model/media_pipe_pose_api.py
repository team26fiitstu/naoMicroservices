import json
from typing import Dict, Union, List

from PIL import Image
from flask import Blueprint, request

from .pose_estimation_mediapipe import evaluate_pose_mediapipe, evaluate_pose_from_video_mediapipe


def application_json_response(payload: Union[Dict, List], status: int):
    return json.dumps(payload), status, {"content-type": "application/json"}


def text_response(payload: str, status: int = 200):
    return payload, status, {"content-type": "plain_text"}


media_pipe_pose_api = Blueprint("media_pipe_pose_api", __name__, template_folder="templates")


@media_pipe_pose_api.route("/pose_from_image", methods=["GET"])
def pose_from_image_local():
    file_location = request.args.get("file_location", "")
    if file_location:
        attach_visualization = bool(request.args.get("attach_visualization", ""))
        min_detection_confidence = float(request.args.get("min_detection_confidence", "0.5"))
        min_tracking_confidence = float(request.args.get("min_tracking_confidence", "0.5"))
        with Image.open(file_location) as evaluated_image:
            evaluation_response = evaluate_pose_mediapipe(evaluated_image, is_base64encoded=False,
                                                          min_detection_confidence=min_detection_confidence,
                                                          min_tracking_confidence=min_tracking_confidence,
                                                          attach_visualization=attach_visualization)
        return application_json_response(evaluation_response, 200)
    return application_json_response({
        "Error": "File path does not specified. "
                 "Please specify location of file (using file_location request parameter)"
                 " on disk or mounted docker volume."
    }, 500)


@media_pipe_pose_api.route("/pose_from_video", methods=["GET"])
def pose_from_video_local():
    file_location = request.args.get("file_location", "")
    if file_location:
        attach_visualization = bool(request.args.get("attach_visualization", ""))
        number_frames_per_sec = int(request.args.get("number_frames_per_sec", 1))
        number_seconds_to_process = int(request.args.get("number_seconds_to_process", -1))
        start_seconds = float(request.args.get("start_seconds", 0))
        end_seconds = float(request.args.get("end_seconds", -1))
        evaluation_response = list(evaluate_pose_from_video_mediapipe(file_location, is_base64encoded=False,
                                                                      number_frames_per_sec=number_frames_per_sec,
                                                                      number_seconds_to_process=
                                                                      number_seconds_to_process,
                                                                      attach_visualization=attach_visualization,
                                                                      start_seconds=start_seconds,
                                                                      end_seconds=end_seconds))
        return application_json_response(evaluation_response, 200)
    return application_json_response({
        "Error": "File path does not specified. "
                 "Please specify location of file (using file_location request parameter)"
                 " on disk or mounted docker volume."
    }, 500)


@media_pipe_pose_api.route("/pose_from_image", methods=["POST"])
def pose_from_image():
    encoded_image = request.get_data().decode("utf-8", "ignore")
    attach_visualization = bool(request.args.get("attach_visualization", ""))
    min_detection_confidence = float(request.args.get("min_detection_confidence", "0.5"))
    min_tracking_confidence = float(request.args.get("min_tracking_confidence", "0.5"))
    evaluation_response = evaluate_pose_mediapipe(encoded_image, is_base64encoded=True,
                                                  min_detection_confidence=min_detection_confidence,
                                                  min_tracking_confidence=min_tracking_confidence,
                                                  attach_visualization=attach_visualization)
    return application_json_response(evaluation_response, 200)


@media_pipe_pose_api.route("/pose_from_video", methods=["POST"])
def pose_from_video():
    encoded_video = request.get_data().decode("utf-8", "ignore")
    attach_visualization = bool(request.args.get("attach_visualization", ""))
    number_frames_per_sec = int(request.args.get("number_frames_per_sec", 1))
    number_seconds_to_process = int(request.args.get("number_seconds_to_process", -1))
    start_seconds = float(request.args.get("start_seconds", 0))
    end_seconds = float(request.args.get("end_seconds", -1))
    evaluation_response = list(evaluate_pose_from_video_mediapipe(encoded_video, is_base64encoded=True,
                                                                  number_frames_per_sec=number_frames_per_sec,
                                                                  number_seconds_to_process=number_seconds_to_process,
                                                                  attach_visualization=attach_visualization,
                                                                  start_seconds=start_seconds,
                                                                  end_seconds=end_seconds))
    return application_json_response(evaluation_response, 200)
