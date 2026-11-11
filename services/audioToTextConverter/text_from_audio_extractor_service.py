#!/usr/bin/env python3
"""
text_from_audio_extractor_service.py

Flask microservice that:
    - /translate/<audio_format>: extracts audio as text from audio file.

"""

import os
from dotenv import load_dotenv

# Load only the repository root file; container environment takes precedence.
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))

import base64

import flask_cors
import whisperx
from flask import Flask, request, jsonify, g



# =========================
# CONFIG
# =========================

app = Flask(__name__,
            static_url_path="",
    static_folder="web/static",
    template_folder="web/templates",
)

flask_cors.CORS(app)



# =========================
# ROUTES
# =========================

@app.route("/test", methods=["GET"])
def test():
    return "NAO Pose Service is running."

def extract_text_from_audio(request):
    """
    Accep
    """
    audio_and_metadata = request.get_json(silent=True)
    if not audio_and_metadata:
        return jsonify({"error": "No file and metadata to translate provided"}), 400

    device = audio_and_metadata.get("device", "cpu")
    print(audio_and_metadata)
    audio_in_base64 = audio_and_metadata.get("audio_file", "")
    if "base64," in audio_in_base64:
        audio_in_base64 = audio_in_base64.split("base64,")[1]
    audio_file = base64.b64decode(audio_in_base64)
    audio_path = audio_and_metadata.get("audio_path", None)
    if not audio_file and not audio_path:
        return jsonify({"error": "No file to translate provided"}), 400
    batch_size = audio_and_metadata.get("batch_size", 16)  # reduce if low on GPU mem
    compute_type = audio_and_metadata.get("compute_type", "int8") # change to "int8" if low on GPU mem (may reduce accuracy)
    model = audio_and_metadata.get("model", "base")  # "large-v2" # "base"
    language = audio_and_metadata.get("language", "sk")
    with_details = audio_and_metadata.get("with_details", False)
    g.model = whisperx.load_model(model, device, compute_type=compute_type, language=language)

    helper_audio_name = "helper.weba"
    with open(helper_audio_name, "wb") as file:
        file.write(audio_file)


    #if isinstance(audio_file, str):
    audio = whisperx.load_audio(helper_audio_name)
    os.remove(helper_audio_name)

    result = g.model.transcribe(audio, batch_size=batch_size)
    print(result)
    translation = ""
    for result_part in result["segments"]:
        translation += result_part["text"] + " "
    translation = translation.strip()

    if with_details:
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

    return jsonify({"translation": translation, "details": result}), 200




# =========================
# EXERCISE CRUD PROXIES
# =========================

@app.route("/translate/<audio_format>", methods=["POST"])
def exercise_list(audio_format):
    if audio_format == "webm":
        response, response_code = extract_text_from_audio(request)
        return response, response_code
    raise Exception("Not supported audio format to process")


with app.app_context():
    print("Preparing for requests execution...")
    #g.model = whisperx.load_model(model, device, compute_type=compute_type, language="sk")
    print("Preparation completed successfully!")

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9901, debug=False)
