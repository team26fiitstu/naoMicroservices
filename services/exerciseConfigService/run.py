
import os
from dotenv import load_dotenv

# Load only the repository root file; container environment takes precedence.
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))
if "EXERCISES_DIR" not in os.environ:
    storage = os.environ.get("EXERCISES_HOST_DIR", "exercises")
    os.environ["EXERCISES_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", storage))

from app import create_app
from flask_cors import CORS

app = create_app()
CORS(app) #added

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7001, debug=False)