
import os
from dotenv import load_dotenv

# Load only the repository root file; container environment takes precedence.
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")))

import sys
from flask import Flask
import flask_cors

from third_party_pose_estimation.media_pipe_model.media_pipe_pose_api import media_pipe_pose_api
from third_party_pose_estimation.yolo_model.yolo_pose_api import yolo_pose_api


app = Flask(
    __name__,
    static_url_path="",
    static_folder="web/static",
    template_folder="web/templates",
)

flask_cors.CORS(app)
app.register_blueprint(media_pipe_pose_api, url_prefix="/media_pipe_pose")
app.register_blueprint(yolo_pose_api, url_prefix="/yolo_pose")


@app.route("/", methods=["GET"])
def check_if_service_is_up():
    return "OK!!", 200, {"content-type": "text/html"}


with app.app_context():
    print("Preparing for requests execution...")
    # g.fully_automated_product_lines_knowledge_manager = FullyAutomatedProductLinesKnowledgeManager()
    print("Preparation completed successfully!")


def launch():
    app.run(host="0.0.0.0", debug=False, port=6001)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "production":
        app.run(host="0.0.0.0", debug=False, port=6001)
    else:
        app.run(host="0.0.0.0", debug=True, port=6001)
