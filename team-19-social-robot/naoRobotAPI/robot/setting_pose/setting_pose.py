import os
from naoqi import ALProxy

import dotenv

dotenv.load_dotenv()


def set_nao_pose(angles):
    NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
    NAO_PORT = int(os.environ.get("NAO_PORT", 9559))
    nao_motion = ALProxy("ALMotion", NAO_IP, NAO_PORT)

    nao_motion.stiffnessInterpolation("Body", 1.0, 1.0)

    joints = [
        "LShoulderPitch", "LShoulderRoll", "LElbowRoll", "LElbowYaw", "LWristYaw",
        "RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RElbowYaw", "RWristYaw",
        "LHipRoll", "LHipPitch", "LKneePitch", "LAnklePitch", "LAnkleRoll",
        "RHipRoll", "RHipPitch", "RKneePitch", "RAnklePitch", "RAnkleRoll",
        "HeadYaw", "HeadPitch"
    ]

    duration = 3.0
    times = [duration] * len(joints)

    nao_motion.angleInterpolation(joints, angles, times, True)


def set_nao_pose_mediapipe(joint_angles, stand_pose_first = False, is_motion_absolute = True):
    NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
    NAO_PORT = int(os.environ.get("NAO_PORT", 9559))
    nao_motion = ALProxy("ALMotion", NAO_IP, NAO_PORT)

    # Define joint names and corresponding angles
    joint_names = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw",
                   "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]

    for pose_name, pose_configuration in joint_angles.items():
        # Extract the numerical values from each line
        values = [pose_configuration["x"], pose_configuration["y"], pose_configuration["z"]]
        joint_angles.extend(values)

    # Set the time for each motion to take in seconds
    time_lists = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]  # Adjust these times as needed

    # Make the robot go to the posture named "Stand"
    if stand_pose_first:
        nao_motion.goToPosture("Stand", 0.5)
    # Execute the motion interpolation
    nao_motion.angleInterpolation(joint_names, joint_angles, time_lists, is_motion_absolute)
