
import os
from dotenv import load_dotenv

# Load only the repository root file; container environment takes precedence.
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))
if os.environ.get("COMPOSE_NETWORK", "false").lower() != "true" and os.environ.get("NAO_IP") == "host.docker.internal":
    os.environ["NAO_IP"] = "127.0.0.1"

import sys
from flask import Flask
import flask_cors

from robot_module_testing.test_api import test_api
from robot.setting_pose.setting_pose_api import setting_pose_api
from robot.voice_lines.voice_lines_api import voice_lines_api

app = Flask(
    __name__,
    static_url_path="",
    static_folder="web/static",
    template_folder="web/templates",
)

flask_cors.CORS(app)
app.register_blueprint(test_api, url_prefix="/tests")
app.register_blueprint(setting_pose_api, url_prefix="/setting_pose")
app.register_blueprint(voice_lines_api, url_prefix="/voiceLines")


@app.route("/", methods=["GET"])
def check_if_service_is_up():
    return "OK", 200, {"content-type": "text/html"}


with app.app_context():
    print("Preparing for requests execution...")
    # g.fully_automated_product_lines_knowledge_manager = FullyAutomatedProductLinesKnowledgeManager()
    print("Preparation completed successfully!")


def launch():
    app.run(host="0.0.0.0", debug=False, port=5000)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "production":
        app.run(host="0.0.0.0", debug=False, port=5000)
    else:
        app.run(host="0.0.0.0", debug=True, port=5000)
