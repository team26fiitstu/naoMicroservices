import json
from flask import Blueprint

from robot_module_testing.movement_test import NAOController
from .test import TestAlMotionBasic
from .movement_test import test as movement_test


def application_json_response(payload, status):
    return json.dumps(payload), status, {"content-type": "application/json"}


def text_response(payload, status = 200):
    return payload, status, {"content-type": "plain_text"}


test_api = Blueprint("test_api", __name__, template_folder="templates")


def not_moving_robot():
    # This kind of access seems to not work, connection is successful, but robot in choregraphe does not move
    test = TestAlMotionBasic()
    print("Running test")
    test.run_test()
    print("Finished")


@test_api.route("/test", methods=["GET"])
def test_method():
    # not_moving_robot() # not working
    print("Running test")
    movement_test()
    print("Finished")
    return application_json_response({"success": True}, 200)

