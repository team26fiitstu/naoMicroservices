# -*- encoding: UTF-8 -*- 

'''Cartesian control: Multiple Effector Trajectories'''
import os
from dotenv import load_dotenv

# Standalone scripts use the same root configuration as the API service.
load_dotenv(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".env"
)))
if (os.environ.get("COMPOSE_NETWORK", "false").strip().lower() != "true"
        and os.environ.get("NAO_IP") == "host.docker.internal"):
    os.environ["NAO_IP"] = "127.0.0.1"

import sys
import motion
import almath
from naoqi import ALProxy
import math
import argparse
import qi

from sadanie import sitting_position_for_extending_legs as sit_on_chair
from sadanie import stand_up_from_chair
import put_arms_next_to_body
# from zdvihanie_na_stolicke import lift_right_leg_on_chair1
# from zdvihanie_na_stolicke import lift_right_leg_on_chair2
# from zdvihanie_na_stolicke import lift_right_leg_on_chair3

# from vratenie_v_sede import vratenie_zdvihnutych_noh_v_sede
# from zdvihanie_na_stolicke import lift_left_leg_on_chair1
from lah import vyrovna_ruky_v_lahu_vedla_tela
# from lah import poloha_lahu_vymenena_noha
from lah import prava_noha_vyrovnaj_po_zakl_lahu
from lah import prava_noha_zdvihnuta_v_lahu_naspat
from lah import lava_noha_naspat_v_lahu


NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
NAO_PORT = int(os.environ.get("NAO_PORT", 9559))


def StiffnessOn(proxy):
    # We use the "Body" name to signify the collection of all joints
    pNames = "Body"
    pStiffnessLists = 1.0
    pTimeLists = 1.0
    proxy.stiffnessInterpolation(pNames, pStiffnessLists, pTimeLists)


motion_proxy = ALProxy("ALMotion", NAO_IP, NAO_PORT)
posture_proxy = ALProxy("ALRobotPosture", NAO_IP, NAO_PORT)
memory_proxy = ALProxy("ALMemory", NAO_IP, NAO_PORT)

# PID controller parameters
Kp = 0.1  # Proportional gain
Ki = 0.1  # Integral gain
Kd = 0.05  # Derivative gain

# PID variables for both X and Y tilts
integral_x = 0
previous_error_x = 0
integral_y = 0
previous_error_y = 0


def balance_robot():
    Kp = 0.05  # Ešte menšie Kp

    tilt_x = memory_proxy.getData("Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value")

    # Použitie negatívnej hodnoty, ak robot padá dozadu
    correction_x = -Kp * tilt_x

    joints = ['RHipPitch', 'LHipPitch']  # Zameranie sa len na konkrétne kĺby
    current_angles = motion_proxy.getAngles(joints, True)

    new_angles = [
        current_angles[0] + correction_x,  # RHipPitch
        current_angles[1] + correction_x  # LHipPitch
    ]

    motion_proxy.setAngles(joints, new_angles, 0.05)  # Pomalšie nastavovanie uhlov


def raise_arm():
    # motion_proxy.wakeUp()
    # pass
    # Set stiffness to allow movement
    # motion_proxy.setStiffnesses("Body", 1.0)
    # # Define the target joint angles (in radians)
    shoulder_pitch = -1.4  # Negative value to raise the arms
    shoulder_roll = 0.0  # Zero to keep arms straight
    elbow_yaw = 0.0
    elbow_roll = 0.0
    wrist_yaw = 0.0

    # Combine the angles for both arms
    left_arm_angles = [shoulder_pitch, shoulder_roll, elbow_yaw, elbow_roll, wrist_yaw]
    right_arm_angles = [shoulder_pitch, -shoulder_roll, -elbow_yaw, -elbow_roll, -wrist_yaw]

    # print("Ahoj")
    # # Apply the joint angles
    motion_proxy.setAngles(["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw"] +
                           ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"],
                           left_arm_angles + right_arm_angles,
                           0.1)  # 0.1 is the fraction of max speed


def sit_to_position_for_extending_legs():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.166035, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.16606, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-0.16606, [3, -0.693333, 0], [3, 0.426667, 0]], [-0.16606, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-0.16606, [3, -0.266667, 0], [3, 0.333333, 0]], [-0.16606, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-0.169649, [3, -0.333333, 0], [3, 0.4, 0]], [-0.163584, [3, -0.4, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.00539738, [3, -0.0266667, 0], [3, 0.386667, 0]], [0, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0, [3, -0.693333, 0], [3, 0.426667, 0]], [0, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0, [3, -0.266667, 0], [3, 0.333333, 0]], [0, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0, [3, -0.333333, 0], [3, 0.4, 0]], [0, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.084003, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.144862, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0.261799, [3, -0.693333, -0.101922], [3, 0.426667, 0.062721]],
                 [0.349066, [3, -0.426667, 0], [3, 0.266667, 0]], [0.349066, [3, -0.266667, 0], [3, 0.333333, 0]],
                 [0.349066, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.339913, [3, -0.333333, 0.00915252], [3, 0.4, -0.010983]], [0.265498, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.108662, [3, -0.0266667, 0], [3, 0.386667, 0]], [0, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0, [3, -0.693333, 0], [3, 0.426667, 0]], [0, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0, [3, -0.266667, 0], [3, 0.333333, 0]], [0, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-0.00625884, [3, -0.333333, 0], [3, 0.4, 0]], [-0.00146097, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.41675, [3, -0.0266667, 0], [3, 0.386667, 0]], [-1.38657, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-1.35088, [3, -0.693333, 0], [3, 0.426667, 0]], [-1.35088, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-1.35088, [3, -0.266667, 0], [3, 0.333333, 0]], [-1.35088, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-1.35327, [3, -0.333333, 0], [3, 0.4, 0]], [-1.35139, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-1.19571, [3, -0.0266667, 0], [3, 0.386667, 0]], [-1.39483, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-1.39483, [3, -0.693333, 0], [3, 0.426667, 0]], [-1.39483, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-1.39483, [3, -0.266667, 0], [3, 0.333333, 0]], [-1.39483, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-1.38611, [3, -0.333333, -0.000186199], [3, 0.4, 0.000223439]], [-1.38589, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.304691, [3, -0.0266667, 0], [3, 0.386667, 0]], [0.304691, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0.304691, [3, -0.693333, 0], [3, 0.426667, 0]], [0.304691, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0.304691, [3, -0.266667, 0], [3, 0.333333, 0]], [0.304691, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.304691, [3, -0.333333, 0], [3, 0.4, 0]], [0.294947, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.125205, [3, -0.0266667, 0], [3, 0.386667, 0]],
                 [-0.633555, [3, -0.386667, 0.173035], [3, 0.693333, -0.31027]],
                 [-1.32471, [3, -0.693333, 0], [3, 0.426667, 0]], [-1.32471, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-1.32471, [3, -0.266667, 0], [3, 0.333333, 0]], [-1.32471, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-1.2303, [3, -0.333333, 0], [3, 0.4, 0]], [-1.23046, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append(
        [[0.110933, [3, -0.0266667, 0], [3, 0.386667, 0]], [0, [3, -0.386667, 0.0236534], [3, 0.693333, -0.042413]],
         [-0.0872665, [3, -0.693333, 0.0216088], [3, 0.426667, -0.0132977]],
         [-0.10472, [3, -0.426667, 0], [3, 0.266667, 0]],
         [-0.0523599, [3, -0.266667, -0.0103427], [3, 0.333333, 0.0129284]],
         [-0.0349066, [3, -0.333333, 0], [3, 0.333333, 0]], [-0.0376726, [3, -0.333333, 0], [3, 0.4, 0]],
         [0.0313534, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.170305, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.750492, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-0.610865, [3, -0.693333, 0], [3, 0.426667, 0]], [-0.698132, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-0.610865, [3, -0.266667, -0.0258567], [3, 0.333333, 0.0323209]],
                 [-0.523599, [3, -0.333333, -0.0206531], [3, 0.333333, 0.0206531]],
                 [-0.486947, [3, -0.333333, -0.00718123], [3, 0.4, 0.00861748]], [-0.476203, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.0864399, [3, -0.0266667, 0], [3, 0.386667, 0]],
                 [1.04694, [3, -0.386667, -0.000144067], [3, 0.693333, 0.000258327]],
                 [1.0472, [3, -0.693333, -0.000258327], [3, 0.426667, 0.00015897]],
                 [1.11701, [3, -0.426667, 0], [3, 0.266667, 0]], [1.11701, [3, -0.266667, 0], [3, 0.333333, 0]],
                 [1.11701, [3, -0.333333, 0], [3, 0.333333, 0]], [1.04742, [3, -0.333333, 0], [3, 0.4, 0]],
                 [1.21736, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append(
        [[1.44846, [3, -0.0266667, 0], [3, 0.386667, 0]], [1.05592, [3, -0.386667, 0.120164], [3, 0.693333, -0.215466]],
         [0.441568, [3, -0.693333, 0], [3, 0.426667, 0]], [0.441568, [3, -0.426667, 0], [3, 0.266667, 0]],
         [0.441568, [3, -0.266667, 0], [3, 0.333333, 0]], [0.441568, [3, -0.333333, 0], [3, 0.333333, 0]],
         [0.45115, [3, -0.333333, 0], [3, 0.4, 0]], [0.45115, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.224837, [3, -0.0266667, 0], [3, 0.386667, 0]], [0.302179, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0.302179, [3, -0.693333, 0], [3, 0.426667, 0]], [0.302179, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0.302179, [3, -0.266667, 0], [3, 0.333333, 0]], [0.302179, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.293906, [3, -0.333333, 0], [3, 0.4, 0]], [0.294523, [3, -0.4, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.101746, [3, -0.0266667, 0], [3, 0.386667, 0]], [0.146244, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0.146244, [3, -0.693333, 0], [3, 0.426667, 0]], [0.146244, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0.146244, [3, -0.266667, 0], [3, 0.333333, 0]], [0.146244, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.145701, [3, -0.333333, 0.000319766], [3, 0.4, -0.000383719]], [0.144133, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.0847546, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.144862, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0.261799, [3, -0.693333, -0.101922], [3, 0.426667, 0.062721]],
                 [0.349066, [3, -0.426667, 0], [3, 0.266667, 0]], [0.349066, [3, -0.266667, 0], [3, 0.333333, 0]],
                 [0.349066, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.339913, [3, -0.333333, 0.00915252], [3, 0.4, -0.010983]], [0.265498, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.109758, [3, -0.0266667, 0], [3, 0.386667, 0]], [0, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0, [3, -0.693333, 0], [3, 0.426667, 0]], [0, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0, [3, -0.266667, 0], [3, 0.333333, 0]], [0, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.00632195, [3, -0.333333, -0.00147815], [3, 0.4, 0.00177378]],
                 [0.00975578, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.417099, [3, -0.0266667, 0], [3, 0.386667, 0]], [1.38657, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [1.35088, [3, -0.693333, 0], [3, 0.426667, 0]], [1.35088, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [1.35088, [3, -0.266667, 0], [3, 0.333333, 0]], [1.35088, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [1.35327, [3, -0.333333, 0], [3, 0.4, 0]], [1.35139, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[1.19875, [3, -0.0266667, 0], [3, 0.386667, 0]], [1.39483, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [1.39483, [3, -0.693333, 0], [3, 0.426667, 0]], [1.39483, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [1.39483, [3, -0.266667, 0], [3, 0.333333, 0]], [1.39483, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [1.38625, [3, -0.333333, 0], [3, 0.4, 0]], [1.39038, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.29357, [3, -0.0266667, 0], [3, 0.386667, 0]], [0.29357, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [0.29357, [3, -0.693333, 0], [3, 0.426667, 0]], [0.29357, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [0.29357, [3, -0.266667, 0], [3, 0.333333, 0]], [0.29357, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [0.293013, [3, -0.333333, 0], [3, 0.4, 0]], [0.29419, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[0.125381, [3, -0.0266667, 0], [3, 0.386667, 0]],
                 [-0.633555, [3, -0.386667, 0.173056], [3, 0.693333, -0.310307]],
                 [-1.32471, [3, -0.693333, 0], [3, 0.426667, 0]], [-1.32471, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-1.34216, [3, -0.266667, 0], [3, 0.333333, 0]], [-1.34216, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-1.24064, [3, -0.333333, 0], [3, 0.4, 0]], [-1.24462, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append(
        [[-0.117281, [3, -0.0266667, 0], [3, 0.386667, 0]], [0, [3, -0.386667, -0.024411], [3, 0.693333, 0.0437714]],
         [0.0872665, [3, -0.693333, -0.0216088], [3, 0.426667, 0.0132977]],
         [0.10472, [3, -0.426667, 0], [3, 0.266667, 0]],
         [0.0523599, [3, -0.266667, 0.0103427], [3, 0.333333, -0.0129284]],
         [0.0349066, [3, -0.333333, 0], [3, 0.333333, 0]], [0.0376726, [3, -0.333333, 0], [3, 0.4, 0]],
         [-0.00213946, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.170305, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.750492, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-0.610865, [3, -0.693333, 0], [3, 0.426667, 0]], [-0.698132, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-0.610865, [3, -0.266667, -0.0258567], [3, 0.333333, 0.0323209]],
                 [-0.523599, [3, -0.333333, -0.0206531], [3, 0.333333, 0.0206531]],
                 [-0.486947, [3, -0.333333, -0.00718123], [3, 0.4, 0.00861748]], [-0.476203, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.0877192, [3, -0.0266667, 0], [3, 0.386667, 0]],
                 [1.04694, [3, -0.386667, -0.000144067], [3, 0.693333, 0.000258327]],
                 [1.0472, [3, -0.693333, -0.000258327], [3, 0.426667, 0.00015897]],
                 [1.11701, [3, -0.426667, 0], [3, 0.266667, 0]], [1.11701, [3, -0.266667, 0], [3, 0.333333, 0]],
                 [1.11701, [3, -0.333333, 0], [3, 0.333333, 0]], [1.04742, [3, -0.333333, 0], [3, 0.4, 0]],
                 [1.21136, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append(
        [[1.44552, [3, -0.0266667, 0], [3, 0.386667, 0]], [1.05592, [3, -0.386667, 0.119813], [3, 0.693333, -0.214838]],
         [0.441568, [3, -0.693333, 0], [3, 0.426667, 0]], [0.441568, [3, -0.426667, 0], [3, 0.266667, 0]],
         [0.441568, [3, -0.266667, 0], [3, 0.333333, 0]], [0.441568, [3, -0.333333, 0], [3, 0.333333, 0]],
         [0.451164, [3, -0.333333, 0], [3, 0.4, 0]], [0.451164, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.226106, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.302179, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-0.302179, [3, -0.693333, 0], [3, 0.426667, 0]], [-0.302179, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-0.302179, [3, -0.266667, 0], [3, 0.333333, 0]], [-0.302179, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-0.294041, [3, -0.333333, 0], [3, 0.4, 0]], [-0.294739, [3, -0.4, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.04, 1.2, 3.28, 4.56, 5.36, 6.36, 7.36, 8.56])
    keys.append([[-0.0992391, [3, -0.0266667, 0], [3, 0.386667, 0]], [-0.143533, [3, -0.386667, 0], [3, 0.693333, 0]],
                 [-0.143533, [3, -0.693333, 0], [3, 0.426667, 0]], [-0.143533, [3, -0.426667, 0], [3, 0.266667, 0]],
                 [-0.143533, [3, -0.266667, 0], [3, 0.333333, 0]], [-0.143533, [3, -0.333333, 0], [3, 0.333333, 0]],
                 [-0.13878, [3, -0.333333, 0], [3, 0.4, 0]], [-0.13986, [3, -0.4, 0], [3, 0, 0]]])

    # print("CURRENTCOM")
    # current_com = motion_proxy.getCOM("Body", 2, True)
    # print(current_com)
    motion_proxy.angleInterpolationBezier(names, times, keys)


def pozdvihnutie_nohy():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([1.52])
    keys.append([[-0.161938, [3, -0.52, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([1.52])
    keys.append([[0, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([1.52])
    keys.append([[0.271206, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([1.52])
    keys.append([[-0.00625882, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([1.52])
    keys.append([[-1.35295, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([1.52])
    keys.append([[-1.38612, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([1.52])
    keys.append([[0.295002, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([1.52])
    keys.append([[-1.23553, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([1.52])
    keys.append([[0.0304205, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483302, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([1.52])
    keys.append([[1.20577, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([1.52])
    keys.append([[1.18677, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([1.52])
    keys.append([[0.658552, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([1.52])
    keys.append([[0.145482, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([1.52])
    keys.append([[0.271206, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([1.52])
    keys.append([[0.00632195, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([1.52])
    keys.append([[1.35295, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([1.52])
    keys.append([[1.38625, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([1.52])
    keys.append([[0.29203, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([1.52])
    keys.append([[-1.50797, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([1.52])
    keys.append([[0.0116141, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483302, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([1.52])
    keys.append([[1.19364, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([1.52])
    keys.append([[1.18668, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([1.52])
    keys.append([[-0.65931, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([1.52])
    keys.append([[-0.13878, [3, -0.52, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def pozdvihnutie_lavej_nohy():
    names = list()
    times = list()
    keys = list()

    # Head movements remain unchanged
    names.extend(["HeadPitch", "HeadYaw"])
    times.extend([[1.52], [1.52]])
    keys.extend([[[-0.161938, [3, -0.52, 0], [3, 0, 0]]],
                 [[0, [3, -0.52, 0], [3, 0, 0]]]])

    # Adjusting for left leg movements by mirroring right leg instructions
    # and including original left leg movements to ensure the sequence is for the left leg elevation
    names.extend(["LAnklePitch", "LAnkleRoll", "LElbowRoll", "LElbowYaw",
                  "LHand", "LHipPitch", "LHipRoll", "LHipYawPitch",
                  "LKneePitch", "LShoulderPitch", "LShoulderRoll",
                  "LWristYaw", "RAnklePitch", "RAnkleRoll",
                  "RElbowRoll", "RElbowYaw", "RHand",
                  "RHipPitch", "RHipRoll", "RHipYawPitch",
                  "RKneePitch", "RShoulderPitch", "RShoulderRoll",
                  "RWristYaw"])

    times.extend([[1.52]] * 24)

    # Keeping the keys as they are for the left side and adapting the right side
    # to match the intended movement for the left leg elevation
    keys.extend([
        # Left leg and arm (original movements)
        [[0.271206, [3, -0.52, 0], [3, 0, 0]]],
        [[-0.00625882, [3, -0.52, 0], [3, 0, 0]]],
        [[-1.35295, [3, -0.52, 0], [3, 0, 0]]],
        [[-1.38612, [3, -0.52, 0], [3, 0, 0]]],
        [[0.295002, [3, -0.52, 0], [3, 0, 0]]],
        [[-1.23553, [3, -0.52, 0], [3, 0, 0]]],
        [[0.0304205, [3, -0.52, 0], [3, 0, 0]]],
        [[-0.483302, [3, -0.52, 0], [3, 0, 0]]],
        [[1.20577, [3, -0.52, 0], [3, 0, 0]]],
        [[1.18677, [3, -0.52, 0], [3, 0, 0]]],
        [[0.658552, [3, -0.52, 0], [3, 0, 0]]],
        [[0.145482, [3, -0.52, 0], [3, 0, 0]]],
        # Right leg and arm (mirrored movements for balance, may require adjustment)
        [[0.271206, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[0.00632195, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[1.35295, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[1.38625, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[0.29203, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[-1.50797, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[0.0116141, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[-0.483302, [3, -0.52, 0], [3, 0, 0]]],  # Shared
        [[1.19364, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[1.18668, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[-0.65931, [3, -0.52, 0], [3, 0, 0]]],  # Mirrored
        [[-0.13878, [3, -0.52, 0], [3, 0, 0]]]  # Mirrored
    ])
    motion_proxy.angleInterpolationBezier(names, times, keys)


def vystretie_nohy1():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([1.76])
    keys.append([[-0.161938, [3, -0.6, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([1.76])
    keys.append([[0, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([1.76])
    keys.append([[0.277462, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([1.76])
    keys.append([[-0.00804903, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([1.76])
    keys.append([[-1.34896, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([1.76])
    keys.append([[-1.38341, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([1.76])
    keys.append([[0.295002, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([1.76])
    keys.append([[-1.23046, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([1.76])
    keys.append([[0.0210859, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([1.76])
    keys.append([[-0.479214, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([1.76])
    keys.append([[1.21362, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([1.76])
    keys.append([[1.18009, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([1.76])
    keys.append([[0.655392, [3, -0.6, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([1.76])
    keys.append([[0.14328, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([1.76])
    keys.append([[0.277462, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([1.76])
    keys.append([[0.00813022, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([1.76])
    keys.append([[1.34901, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([1.76])
    keys.append([[1.384, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([1.76])
    keys.append([[0.29203, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([1.76])
    keys.append([[-1.5049, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([1.76])
    keys.append([[0.00735523, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([1.76])
    keys.append([[-0.479214, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([1.76])
    keys.append([[0.872666, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([1.76])
    keys.append([[1.18002, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([1.76])
    keys.append([[-0.653338, [3, -0.6, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([1.76])
    keys.append([[-0.134848, [3, -0.6, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def vystretie_nohy2():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.72, 1.28])
    keys.append([[-0.17, [3, -0.253333, 0], [3, 0.186667, 0]], [-0.17, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.72, 1.28])
    keys.append([[0, [3, -0.253333, 0], [3, 0.186667, 0]], [0, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.72, 1.28])
    keys.append([[0.268914, [3, -0.253333, 0], [3, 0.186667, 0]], [0.268913, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.72, 1.28])
    keys.append([[-0.00558696, [3, -0.253333, 0], [3, 0.186667, 0]], [-0.00558696, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.72, 1.28])
    keys.append([[-1.35139, [3, -0.253333, 0], [3, 0.186667, 0]], [-1.35139, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.72, 1.28])
    keys.append([[-1.3859, [3, -0.253333, 0], [3, 0.186667, 0]], [-1.3859, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.72, 1.28])
    keys.append([[0.3, [3, -0.253333, 0], [3, 0.186667, 0]], [0.3, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.72, 1.28])
    keys.append([[-1.23046, [3, -0.253333, 0], [3, 0.186667, 0]], [-1.23046, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.72, 1.28])
    keys.append([[0.0306377, [3, -0.253333, 0], [3, 0.186667, 0]], [0.0306377, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.72, 1.28])
    keys.append([[-0.476438, [3, -0.253333, 0], [3, 0.186667, 0]], [-0.476438, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.72, 1.28])
    keys.append([[1.2156, [3, -0.253333, 0], [3, 0.186667, 0]], [1.2156, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.72, 1.28])
    keys.append([[0.45115, [3, -0.253333, 0], [3, 0.186667, 0]], [0.45115, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.72, 1.28])
    keys.append([[0.299737, [3, -0.253333, 0], [3, 0.186667, 0]], [0.299738, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.72, 1.28])
    keys.append([[0.144133, [3, -0.253333, 0], [3, 0.186667, 0]], [0.144133, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.72, 1.28])
    keys.append([[0.268914, [3, -0.253333, 0], [3, 0.186667, 0]], [0.268913, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.72, 1.28])
    keys.append([[0.00641184, [3, -0.253333, 0], [3, 0.186667, 0]], [0.00641183, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.72, 1.28])
    keys.append([[1.35139, [3, -0.253333, 0], [3, 0.186667, 0]], [1.35139, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.72, 1.28])
    keys.append([[1.39039, [3, -0.253333, 0], [3, 0.186667, 0]], [1.39039, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.72, 1.28])
    keys.append([[0.3, [3, -0.253333, 0], [3, 0.186667, 0]], [0.3, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.72, 1.28])
    keys.append([[-1.51936, [3, -0.253333, 0], [3, 0.186667, 0]], [-1.51936, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.72, 1.28])
    keys.append([[0.00645995, [3, -0.253333, 0], [3, 0.186667, 0]], [0.00645995, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.72, 1.28])
    keys.append([[-0.476438, [3, -0.253333, 0], [3, 0.186667, 0]], [-0.476438, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.72, 1.28])
    keys.append([[0.745256, [3, -0.253333, 0], [3, 0.186667, 0]], [0.642281, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.72, 1.28])
    keys.append([[0.451164, [3, -0.253333, 0], [3, 0.186667, 0]], [0.451164, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.72, 1.28])
    keys.append([[-0.300829, [3, -0.253333, 0], [3, 0.186667, 0]], [-0.300828, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.72, 1.28])
    keys.append([[-0.139861, [3, -0.253333, 0], [3, 0.186667, 0]], [-0.139861, [3, -0.186667, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


import time


def adjust_balance():
    """
    Upravuje ťažisko robota na udržanie rovnováhy.
    """
    com = motion_proxy.getCOM("Body", 2, False)

    # Presun ťažiska na základe aktuálnej polohy
    if com[1] > 0.01:  # ak je ťažisko príliš vpravo
        # Presun ťažiska doľava
        motion_proxy.changeWholeBodyCOM(0.01, 0, 0)
    elif com[1] < -0.01:  # ak je ťažisko príliš vľavo
        # Presun ťažiska doprava
        motion_proxy.changeWholeBodyCOM(-0.01, 0, 0)


def ruky_k_sebe():
    # Choregraphe bezier export in Python.
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.96, 1.56])
    keys.append([[-0.161938, [3, -0.333333, 0], [3, 0.2, 0]], [-0.161938, [3, -0.2, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.96, 1.56])
    keys.append([[0, [3, -0.333333, 0], [3, 0.2, 0]], [0, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.96, 1.56])
    keys.append([[0.32799, [3, -0.333333, 0], [3, 0.2, 0]], [0.32799, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.96, 1.56])
    keys.append([[-0.00625884, [3, -0.333333, 0], [3, 0.2, 0]], [-0.00625884, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.96, 1.56])
    keys.append([[-1.35123, [3, -0.333333, 0], [3, 0.2, 0]], [-1.35123, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.96, 1.56])
    keys.append([[-1.38112, [3, -0.333333, 0], [3, 0.2, 0]], [-1.38112, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.96, 1.56])
    keys.append([[0.295002, [3, -0.333333, 0], [3, 0.2, 0]], [0.295002, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.96, 1.56])
    keys.append([[-1.23553, [3, -0.333333, 0], [3, 0.2, 0]], [-1.23553, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.96, 1.56])
    keys.append([[-0.0276533, [3, -0.333333, 0], [3, 0.2, 0]], [-0.0276533, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.96, 1.56])
    keys.append([[-0.483302, [3, -0.333333, 0], [3, 0.2, 0]], [-0.483302, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.96, 1.56])
    keys.append([[1.07993, [3, -0.333333, 0], [3, 0.2, 0]], [1.07993, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.96, 1.56])
    keys.append([[1.18841, [3, -0.333333, 0], [3, 0.2, 0]], [1.18841, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.96, 1.56])
    keys.append([[0.299171, [3, -0.333333, 0], [3, 0.2, 0]], [0.660067, [3, -0.2, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.96, 1.56])
    keys.append([[0.149524, [3, -0.333333, 0], [3, 0.2, 0]], [0.149524, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.96, 1.56])
    keys.append([[0.32799, [3, -0.333333, 0], [3, 0.2, 0]], [0.32799, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.96, 1.56])
    keys.append([[0.00632195, [3, -0.333333, 0], [3, 0.2, 0]], [0.00632195, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.96, 1.56])
    keys.append([[1.35123, [3, -0.333333, 0], [3, 0.2, 0]], [1.35123, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.96, 1.56])
    keys.append([[1.38125, [3, -0.333333, 0], [3, 0.2, 0]], [1.38125, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.96, 1.56])
    keys.append([[0.29203, [3, -0.333333, 0], [3, 0.2, 0]], [0.29203, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.96, 1.56])
    keys.append([[-1.24323, [3, -0.333333, 0], [3, 0.2, 0]], [-1.24323, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.96, 1.56])
    keys.append([[0.0290732, [3, -0.333333, 0], [3, 0.2, 0]], [0.0290732, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.96, 1.56])
    keys.append([[-0.483302, [3, -0.333333, 0], [3, 0.2, 0]], [-0.483302, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.96, 1.56])
    keys.append([[1.07878, [3, -0.333333, 0], [3, 0.2, 0]], [1.07878, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.96, 1.56])
    keys.append([[1.18832, [3, -0.333333, 0], [3, 0.2, 0]], [1.18832, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.96, 1.56])
    keys.append([[-0.299226, [3, -0.333333, 0], [3, 0.2, 0]], [-0.660067, [3, -0.2, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.96, 1.56])
    keys.append([[-0.142853, [3, -0.333333, 0], [3, 0.2, 0]], [-0.142853, [3, -0.2, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def lower_arms_in_sitting_position():
    names = list()
    times = list()
    keys = list()

    time_to_lower_hands_in_sitting_position = 2.5

    names.append("LElbowRoll")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[-1.35098, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[-1.38858, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[0.304691, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[0.445853, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[0.29872, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[0.144133, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[1.35098, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[1.38867, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[0.29357, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[0.445859, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[-0.299802, [3, -0.533333, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([time_to_lower_hands_in_sitting_position])
    keys.append([[-0.137382, [3, -0.533333, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


# time_threshold = 0.8
time_threshold = 1.48


# Function to truncate times and keys
def truncate_times_and_keys(times, keys, threshold):
    new_times = []
    new_keys = []
    for time_list, key_list in zip(times, keys):
        # Find the index where times exceed the threshold
        index = next((i for i, t in enumerate(time_list) if t > threshold), None)

        # If such index is found, truncate; else, keep the original
        if index is not None:
            new_times.append(time_list[:index])
            new_keys.append(key_list[:index])
        else:
            new_times.append(time_list)
            new_keys.append(key_list)
    return new_times, new_keys


def pozdivhnutie_nohy_lavej2():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.164615, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.164343, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-0.164343, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.164343, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-0.164343, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.164343, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-0.164343, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.164343, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0, [3, -0.0133333, 0], [3, 0.266667, 0]], [2.42761e-05, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [2.42761e-05, [3, -0.226667, 0], [3, 0.226667, 0]], [2.42761e-05, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [2.42761e-05, [3, -0.173333, 0], [3, 0.173333, 0]], [2.42761e-05, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [2.42761e-05, [3, -0.186667, 0], [3, 0.186667, 0]], [2.42761e-05, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.270996, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.269901, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.269901, [3, -0.226667, 0], [3, 0.226667, 0]], [0.269901, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.269901, [3, -0.173333, 0], [3, 0.173333, 0]], [0.269901, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.269901, [3, -0.186667, 0], [3, 0.186667, 0]], [0.269901, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append(
        [[-0.00625882, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.00122033, [3, -0.266667, 0], [3, 0.226667, 0]],
         [-0.00122033, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.00122033, [3, -0.226667, 0], [3, 0.173333, 0]],
         [-0.00122033, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.00122033, [3, -0.173333, 0], [3, 0.186667, 0]],
         [-0.00625882, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.00625882, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.35295, [3, -0.0133333, 0], [3, 0.266667, 0]], [-1.35295, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-1.35295, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.35295, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.35295, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.35295, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.35295, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.35295, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.38612, [3, -0.0133333, 0], [3, 0.266667, 0]], [-1.38612, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-1.38612, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.38612, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.38612, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.38612, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.38612, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.38612, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.302346, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.298696, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.298696, [3, -0.226667, 0], [3, 0.226667, 0]], [0.298696, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.298696, [3, -0.173333, 0], [3, 0.173333, 0]], [0.298696, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.298696, [3, -0.186667, 0], [3, 0.186667, 0]], [0.298696, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.23046, [3, -0.0133333, 0], [3, 0.266667, 0]], [-1.41694, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-1.41694, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.41694, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.48353, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.48353, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.48334, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.48334, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.0306377, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.02861, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.02861, [3, -0.226667, 0], [3, 0.226667, 0]], [0.02861, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.02861, [3, -0.173333, 0], [3, 0.173333, 0]], [0.02861, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.02861, [3, -0.186667, 0], [3, 0.186667, 0]], [0.02861, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.476438, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [-0.478983, [3, -0.266667, 0.00254472], [3, 0.226667, -0.00216301]],
                 [-0.514872, [3, -0.226667, 0.0222713], [3, 0.226667, -0.0222713]],
                 [-0.612611, [3, -0.226667, 0], [3, 0.173333, 0]], [-0.612611, [3, -0.173333, 0], [3, 0.173333, 0]],
                 [-0.612611, [3, -0.173333, 0], [3, 0.186667, 0]], [-0.604598, [3, -0.186667, 0], [3, 0.186667, 0]],
                 [-0.604598, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.2156, [3, -0.0133333, 0], [3, 0.266667, 0]], [1.21061, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [1.21061, [3, -0.226667, 0], [3, 0.226667, 0]], [1.21061, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.14494, [3, -0.173333, 0.0301436], [3, 0.173333, -0.0301436]],
                 [1.02974, [3, -0.173333, 0.0305459], [3, 0.186667, -0.0328956]],
                 [0.954611, [3, -0.186667, 0.0293797], [3, 0.186667, -0.0293797]],
                 [0.853466, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.445853, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.445853, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.445853, [3, -0.226667, 0], [3, 0.226667, 0]], [0.445853, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.445853, [3, -0.173333, 0], [3, 0.173333, 0]], [0.445853, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.445853, [3, -0.186667, 0], [3, 0.186667, 0]], [0.445853, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.293906, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.293913, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.293913, [3, -0.226667, 0], [3, 0.226667, 0]], [0.293913, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.293913, [3, -0.173333, 0], [3, 0.173333, 0]], [0.293913, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.293913, [3, -0.186667, 0], [3, 0.186667, 0]], [0.293913, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.145482, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.145482, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.145482, [3, -0.226667, 0], [3, 0.226667, 0]], [0.145482, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.145482, [3, -0.173333, 0], [3, 0.173333, 0]], [0.145482, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.145482, [3, -0.186667, 0], [3, 0.186667, 0]], [0.145482, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.270996, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.269901, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.269901, [3, -0.226667, 0], [3, 0.226667, 0]], [0.269901, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.269901, [3, -0.173333, 0], [3, 0.173333, 0]], [0.269901, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.269901, [3, -0.186667, 0], [3, 0.186667, 0]], [0.269901, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.00632195, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.00123263, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.00123263, [3, -0.226667, 0], [3, 0.226667, 0]], [0.00123263, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.00123263, [3, -0.173333, 0], [3, 0.173333, 0]], [0.00123263, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.00632195, [3, -0.186667, 0], [3, 0.186667, 0]], [0.00632195, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.35295, [3, -0.0133333, 0], [3, 0.266667, 0]], [1.35295, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [1.35295, [3, -0.226667, 0], [3, 0.226667, 0]], [1.35295, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.35295, [3, -0.173333, 0], [3, 0.173333, 0]], [1.35295, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [1.35295, [3, -0.186667, 0], [3, 0.186667, 0]], [1.35295, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.38625, [3, -0.0133333, 0], [3, 0.266667, 0]], [1.38625, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [1.38625, [3, -0.226667, 0], [3, 0.226667, 0]], [1.38625, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.38625, [3, -0.173333, 0], [3, 0.173333, 0]], [1.38625, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [1.38625, [3, -0.186667, 0], [3, 0.186667, 0]], [1.38625, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.291937, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.29724, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.29724, [3, -0.226667, 0], [3, 0.226667, 0]], [0.29724, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.29724, [3, -0.173333, 0], [3, 0.173333, 0]], [0.29724, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.29724, [3, -0.186667, 0], [3, 0.186667, 0]], [0.29724, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.24461, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [-1.24323, [3, -0.266667, -0.00138578], [3, 0.226667, 0.00117791]],
                 [-1.17461, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.17461, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.17461, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.17461, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.17866, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.17866, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.00645995, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.00547642, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.00872665, [3, -0.226667, 0], [3, 0.226667, 0]], [0.00872665, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.00872665, [3, -0.173333, 0], [3, 0.173333, 0]], [0.00872665, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.00547642, [3, -0.186667, 0], [3, 0.186667, 0]], [0.00547642, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.476438, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [-0.478983, [3, -0.266667, 0.00254472], [3, 0.226667, -0.00216301]],
                 [-0.514872, [3, -0.226667, 0.0222713], [3, 0.226667, -0.0222713]],
                 [-0.612611, [3, -0.226667, 0], [3, 0.173333, 0]], [-0.612611, [3, -0.173333, 0], [3, 0.173333, 0]],
                 [-0.612611, [3, -0.173333, 0], [3, 0.186667, 0]], [-0.604598, [3, -0.186667, 0], [3, 0.186667, 0]],
                 [-0.604598, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.20262, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [1.21059, [3, -0.266667, -0.00797444], [3, 0.226667, 0.00677827]],
                 [1.29329, [3, -0.226667, 0], [3, 0.226667, 0]], [1.29329, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.29329, [3, -0.173333, 0], [3, 0.173333, 0]], [1.29329, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [1.28854, [3, -0.186667, 0], [3, 0.186667, 0]], [1.28854, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.44586, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.44586, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.44586, [3, -0.226667, 0], [3, 0.226667, 0]], [0.44586, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.44586, [3, -0.173333, 0], [3, 0.173333, 0]], [0.44586, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.44586, [3, -0.186667, 0], [3, 0.186667, 0]], [0.44586, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.294041, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.294048, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-0.294048, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.294048, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-0.294048, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.294048, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-0.294048, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.294048, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.134848, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.135919, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-0.135919, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.135919, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-0.135919, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.135919, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-0.135919, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.135919, [3, -0.186667, 0], [3, 0, 0]]])

    truncated_times, truncated_keys = truncate_times_and_keys(times, keys, time_threshold)

    motion_proxy.angleInterpolationBezier(names, truncated_times, truncated_keys)


def stand_up_from_sitting_on_chair():
    # Choregraphe bezier export in Python.
    names = list()
    times = list()
    keys = list()

    names.append("LShoulderPitch")
    times.append([1, 1.8])
    keys.append([[0.932006, [3, -0.346667, 0], [3, 0.266667, 0]], [0.932006, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([1.8])
    keys.append([[0.141372, [3, -0.613333, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([1, 1.8])
    keys.append([[0.932006, [3, -0.346667, 0], [3, 0.266667, 0]], [0.932006, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([1.8])
    keys.append([[-0.141372, [3, -0.613333, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)

    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-0.169649, [3, -0.4, 0], [3, 0.266667, 0]], [-0.16606, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-0.16606, [3, -0.266667, 0], [3, 0.266667, 0]], [-0.16606, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-0.16606, [3, -0.4, 0], [3, 0.426667, 0]],
                 [-0.166005, [3, -0.426667, -6.45615e-08], [3, 0.44, 6.6579e-08]],
                 [-0.166005, [3, -0.44, 0], [3, 0.466667, 0]], [-0.166005, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0, [3, -0.4, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0, [3, -0.266667, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0, [3, -0.4, 0], [3, 0.426667, 0]], [0.00269869, [3, -0.426667, -7.81799e-09], [3, 0.44, 8.0623e-09]],
                 [0.0026987, [3, -0.44, 0], [3, 0.466667, 0]], [0.00269869, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.339913, [3, -0.4, 0], [3, 0.266667, 0]], [0.349066, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.349066, [3, -0.266667, 0], [3, 0.266667, 0]], [0.349066, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.261799, [3, -0.4, 0.0780552], [3, 0.426667, -0.0832589]],
                 [-0.134877, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-0.134877, [3, -0.44, -5.82566e-08], [3, 0.466667, 6.17874e-08]],
                 [0.0768539, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-0.00625884, [3, -0.4, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0, [3, -0.266667, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0, [3, -0.4, 0], [3, 0.426667, 0]], [0.00043631, [3, -0.426667, 0], [3, 0.44, 0]],
                 [0.00043631, [3, -0.44, 9.75279e-11], [3, 0.466667, -1.03439e-10]],
                 [-0.0981274, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-1.35327, [3, -0.4, 0], [3, 0.266667, 0]], [-1.35088, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-1.35088, [3, -0.266667, 0], [3, 0.266667, 0]], [-1.35088, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-1.35088, [3, -0.4, 0], [3, 0.426667, 0]], [-1.07643, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-1.07643, [3, -0.44, 0], [3, 0.466667, 0]], [-1.07643, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-1.38611, [3, -0.4, 0], [3, 0.266667, 0]], [-1.39483, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-1.39483, [3, -0.266667, 0], [3, 0.266667, 0]], [-1.39483, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-1.39483, [3, -0.4, 0], [3, 0.426667, 0]],
                 [-0.791883, [3, -0.426667, -4.5193e-07], [3, 0.44, 4.66053e-07]],
                 [-0.791882, [3, -0.44, 0], [3, 0.466667, 0]], [-0.791883, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.304691, [3, -0.4, 0], [3, 0.266667, 0]], [0.304691, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.304691, [3, -0.266667, 0], [3, 0.266667, 0]], [0.304691, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.304691, [3, -0.4, 0], [3, 0.426667, 0]],
                 [0.299044, [3, -0.426667, 1.15597e-07], [3, 0.44, -1.19209e-07]],
                 [0.299044, [3, -0.44, 0], [3, 0.466667, 0]], [0.299044, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-1.2303, [3, -0.4, 0], [3, 0.266667, 0]], [-1.32471, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-1.32471, [3, -0.266667, 0], [3, 0.266667, 0]], [-1.32471, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-1.32471, [3, -0.4, 0], [3, 0.426667, 0]], [-0.634814, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-0.634815, [3, -0.44, 0], [3, 0.466667, 0]], [0.120077, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-0.0376726, [3, -0.4, 0], [3, 0.266667, 0]], [-0.0349066, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-0.0523599, [3, -0.266667, 0.0116355], [3, 0.266667, -0.0116355]],
                 [-0.10472, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-0.0872665, [3, -0.4, -0.0158846], [3, 0.426667, 0.0169436]],
                 [-0.00623519, [3, -0.426667, -1.00877e-09], [3, 0.44, 1.0403e-09]],
                 [-0.00623519, [3, -0.44, -1.0403e-09], [3, 0.466667, 1.10335e-09]],
                 [0.104047, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append(
        [[-0.486947, [3, -0.4, 0], [3, 0.266667, 0]], [-0.523599, [3, -0.266667, 0.0206531], [3, 0.266667, -0.0206531]],
         [-0.610865, [3, -0.266667, 0.0290888], [3, 0.266667, -0.0290888]], [-0.698132, [3, -0.266667, 0], [3, 0.4, 0]],
         [-0.610865, [3, -0.4, 0], [3, 0.426667, 0]], [-0.750492, [3, -0.426667, 0.0612924], [3, 0.44, -0.0632078]],
         [-0.984366, [3, -0.44, 0], [3, 0.466667, 0]], [-0.175861, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[1.04742, [3, -0.4, 0], [3, 0.266667, 0]], [1.11701, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [1.11701, [3, -0.266667, 0], [3, 0.266667, 0]], [1.11701, [3, -0.266667, 0], [3, 0.4, 0]],
                 [1.0472, [3, -0.4, 0], [3, 0.426667, 0]], [1.053, [3, -0.426667, 0], [3, 0.44, 0]],
                 [1.04545, [3, -0.44, 0.00754926], [3, 0.466667, -0.00800679]],
                 [-0.0767842, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.45115, [3, -0.4, 0], [3, 0.266667, 0]], [0.441568, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.441568, [3, -0.266667, 0], [3, 0.266667, 0]], [0.441568, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.441568, [3, -0.4, 0], [3, 0.426667, 0]], [1.39654, [3, -0.426667, 0], [3, 0.44, 0]],
                 [1.39654, [3, -0.44, 7.98948e-07], [3, 0.466667, -8.47369e-07]],
                 [1.38519, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.293906, [3, -0.4, 0], [3, 0.266667, 0]], [0.302179, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.302179, [3, -0.266667, 0], [3, 0.266667, 0]], [0.302179, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.302179, [3, -0.4, 0], [3, 0.426667, 0]],
                 [0.166304, [3, -0.426667, 3.22807e-08], [3, 0.44, -3.32895e-08]],
                 [0.166304, [3, -0.44, 0], [3, 0.466667, 0]], [0.166304, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.145701, [3, -0.4, 0], [3, 0.266667, 0]], [0.146244, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.146244, [3, -0.266667, 0], [3, 0.266667, 0]], [0.146244, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.146244, [3, -0.4, 0], [3, 0.426667, 0]], [0.145482, [3, -0.426667, 0], [3, 0.44, 0]],
                 [0.145482, [3, -0.44, 0], [3, 0.466667, 0]], [0.145482, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.339913, [3, -0.4, 0], [3, 0.266667, 0]], [0.349066, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.349066, [3, -0.266667, 0], [3, 0.266667, 0]], [0.349066, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.261799, [3, -0.4, 0.0780552], [3, 0.426667, -0.0832589]],
                 [-0.134877, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-0.134877, [3, -0.44, -5.82566e-08], [3, 0.466667, 6.17874e-08]],
                 [0.0775809, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.00632195, [3, -0.4, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0, [3, -0.266667, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0, [3, -0.4, 0], [3, 0.426667, 0]], [-0.00043631, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-0.00043631, [3, -0.44, -9.75279e-11], [3, 0.466667, 1.03439e-10]],
                 [0.0991166, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[1.35327, [3, -0.4, 0], [3, 0.266667, 0]], [1.35088, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [1.35088, [3, -0.266667, 0], [3, 0.266667, 0]], [1.35088, [3, -0.266667, 0], [3, 0.4, 0]],
                 [1.35088, [3, -0.4, 0], [3, 0.426667, 0]], [1.07643, [3, -0.426667, 0], [3, 0.44, 0]],
                 [1.07643, [3, -0.44, 0], [3, 0.466667, 0]], [1.07643, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[1.38625, [3, -0.4, 0], [3, 0.266667, 0]], [1.39483, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [1.39483, [3, -0.266667, 0], [3, 0.266667, 0]], [1.39483, [3, -0.266667, 0], [3, 0.4, 0]],
                 [1.39483, [3, -0.4, 0], [3, 0.426667, 0]],
                 [0.791883, [3, -0.426667, 4.5193e-07], [3, 0.44, -4.66053e-07]],
                 [0.791882, [3, -0.44, 0], [3, 0.466667, 0]], [0.791883, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.293013, [3, -0.4, 0], [3, 0.266667, 0]], [0.29357, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.29357, [3, -0.266667, 0], [3, 0.266667, 0]], [0.29357, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.29357, [3, -0.4, 0], [3, 0.426667, 0]],
                 [0.288129, [3, -0.426667, 2.60093e-07], [3, 0.44, -2.68221e-07]],
                 [0.288129, [3, -0.44, 0], [3, 0.466667, 0]], [0.288129, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-1.24064, [3, -0.4, 0], [3, 0.266667, 0]], [-1.34216, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-1.34216, [3, -0.266667, 0], [3, 0.266667, 0]], [-1.32471, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-1.32471, [3, -0.4, 0], [3, 0.426667, 0]], [-0.634814, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-0.634815, [3, -0.44, 0], [3, 0.466667, 0]], [0.120252, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.0376726, [3, -0.4, 0], [3, 0.266667, 0]], [0.0349066, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.0523599, [3, -0.266667, -0.0116355], [3, 0.266667, 0.0116355]],
                 [0.10472, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.0872665, [3, -0.4, 0.0158846], [3, 0.426667, -0.0169436]],
                 [0.00623519, [3, -0.426667, 1.00877e-09], [3, 0.44, -1.0403e-09]],
                 [0.00623519, [3, -0.44, 1.0403e-09], [3, 0.466667, -1.10335e-09]],
                 [-0.106957, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append(
        [[-0.486947, [3, -0.4, 0], [3, 0.266667, 0]], [-0.523599, [3, -0.266667, 0.0206531], [3, 0.266667, -0.0206531]],
         [-0.610865, [3, -0.266667, 0.0290888], [3, 0.266667, -0.0290888]], [-0.698132, [3, -0.266667, 0], [3, 0.4, 0]],
         [-0.610865, [3, -0.4, 0], [3, 0.426667, 0]], [-0.750492, [3, -0.426667, 0.0612924], [3, 0.44, -0.0632078]],
         [-0.984366, [3, -0.44, 0], [3, 0.466667, 0]], [-0.175861, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[1.04742, [3, -0.4, 0], [3, 0.266667, 0]], [1.11701, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [1.11701, [3, -0.266667, 0], [3, 0.266667, 0]], [1.11701, [3, -0.266667, 0], [3, 0.4, 0]],
                 [1.0472, [3, -0.4, 0], [3, 0.426667, 0]], [1.053, [3, -0.426667, 0], [3, 0.44, 0]],
                 [1.04545, [3, -0.44, 0.00754926], [3, 0.466667, -0.00800679]],
                 [-0.0780461, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[0.451164, [3, -0.4, 0], [3, 0.266667, 0]], [0.441568, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [0.441568, [3, -0.266667, 0], [3, 0.266667, 0]], [0.441568, [3, -0.266667, 0], [3, 0.4, 0]],
                 [0.441568, [3, -0.4, 0], [3, 0.426667, 0]], [1.39654, [3, -0.426667, 0], [3, 0.44, 0]],
                 [1.39654, [3, -0.44, 7.98948e-07], [3, 0.466667, -8.47369e-07]],
                 [1.38519, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-0.294041, [3, -0.4, 0], [3, 0.266667, 0]], [-0.302179, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-0.302179, [3, -0.266667, 0], [3, 0.266667, 0]], [-0.302179, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-0.302179, [3, -0.4, 0], [3, 0.426667, 0]],
                 [-0.166304, [3, -0.426667, -3.22807e-08], [3, 0.44, 3.32895e-08]],
                 [-0.166304, [3, -0.44, 0], [3, 0.466667, 0]], [-0.166304, [3, -0.466667, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([1.16, 1.96, 2.76, 3.56, 4.76, 6.04, 7.36, 8.76])
    keys.append([[-0.13878, [3, -0.4, 0], [3, 0.266667, 0]], [-0.143533, [3, -0.266667, 0], [3, 0.266667, 0]],
                 [-0.143533, [3, -0.266667, 0], [3, 0.266667, 0]], [-0.143533, [3, -0.266667, 0], [3, 0.4, 0]],
                 [-0.143533, [3, -0.4, 0], [3, 0.426667, 0]], [-0.148822, [3, -0.426667, 0], [3, 0.44, 0]],
                 [-0.148822, [3, -0.44, 0], [3, 0.466667, 0]], [-0.148822, [3, -0.466667, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def vyrovna_ruky_v_lahu():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.159824, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.159824, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.159824, [3, -0.253333, 0], [3, 0.24, 0]], [0.159824, [3, -0.24, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append(
        [[-0.00476281, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.00476281, [3, -0.266667, 0], [3, 0.253333, 0]],
         [-0.00476281, [3, -0.253333, 0], [3, 0.24, 0]], [-0.00476281, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.872242, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.872242, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.872242, [3, -0.253333, 0], [3, 0.24, 0]], [0.872242, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.0307136, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.0307136, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.0307136, [3, -0.253333, 0], [3, 0.24, 0]], [-0.0307136, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-1.52746, [3, -0.0666667, 0], [3, 0.266667, 0]],
                 [-0.808087, [3, -0.266667, -0.157876], [3, 0.253333, 0.149982]],
                 [-0.603884, [3, -0.253333, -7.02779e-08], [3, 0.24, 6.6579e-08]],
                 [-0.603884, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.885838, [3, -0.0666667, 0], [3, 0.266667, 0]],
                 [-1.05243, [3, -0.266667, 0.0639811], [3, 0.253333, -0.060782]],
                 [-1.26013, [3, -0.253333, 0], [3, 0.24, 0]], [-1.26013, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.302387, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.302387, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.302387, [3, -0.253333, 0], [3, 0.24, 0]], [0.302387, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.374947, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.374947, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.374947, [3, -0.253333, 0], [3, 0.24, 0]], [0.374947, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.107535, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.107535, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.107535, [3, -0.253333, 0], [3, 0.24, 0]], [0.107535, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.502138, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.502138, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.502138, [3, -0.253333, 0], [3, 0.24, 0]], [-0.502138, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.0894006, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.0894006, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.0894006, [3, -0.253333, 0], [3, 0.24, 0]], [-0.0894006, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[1.67289, [3, -0.0666667, 0], [3, 0.266667, 0]], [1.29329, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [1.45211, [3, -0.253333, -0.110538], [3, 0.24, 0.10472]], [1.93906, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.211384, [3, -0.0666667, 0], [3, 0.266667, 0]],
                 [0.462512, [3, -0.266667, -0.0551602], [3, 0.253333, 0.0524021]],
                 [0.534071, [3, -0.253333, 0], [3, 0.24, 0]], [0.464258, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.240344, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.385718, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.385718, [3, -0.253333, 0], [3, 0.24, 0]], [0.385718, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.654474, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.654474, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.654474, [3, -0.253333, 0], [3, 0.24, 0]], [0.654474, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.272839, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.272839, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.272839, [3, -0.253333, 0], [3, 0.24, 0]], [-0.272839, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[1.54328, [3, -0.0666667, 0], [3, 0.266667, 0]],
                 [0.808087, [3, -0.266667, 0.160581], [3, 0.253333, -0.152552]],
                 [0.603884, [3, -0.253333, 7.02779e-08], [3, 0.24, -6.6579e-08]], [0.603884, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.881086, [3, -0.0666667, 0], [3, 0.266667, 0]],
                 [1.05243, [3, -0.266667, -0.0647935], [3, 0.253333, 0.0615538]],
                 [1.26013, [3, -0.253333, 0], [3, 0.24, 0]], [1.26013, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.354675, [3, -0.0666667, 0], [3, 0.266667, 0]], [0.354675, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [0.354675, [3, -0.253333, 0], [3, 0.24, 0]], [0.354675, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.400415, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.400415, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.400415, [3, -0.253333, 0], [3, 0.24, 0]], [-0.400415, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.0782143, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.0782143, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.0782143, [3, -0.253333, 0], [3, 0.24, 0]], [-0.0782143, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.502138, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.502138, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.502138, [3, -0.253333, 0], [3, 0.24, 0]], [-0.502138, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[1.72916, [3, -0.0666667, 0], [3, 0.266667, 0]], [1.72916, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [1.72916, [3, -0.253333, 0], [3, 0.24, 0]], [1.72916, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[1.68573, [3, -0.0666667, 0], [3, 0.266667, 0]], [1.29329, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [1.45211, [3, -0.253333, -0.110538], [3, 0.24, 0.10472]], [1.93906, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[-0.24059, [3, -0.0666667, 0], [3, 0.266667, 0]],
                 [-0.462512, [3, -0.266667, 0.0501676], [3, 0.253333, -0.0476592]],
                 [-0.534071, [3, -0.253333, 0], [3, 0.24, 0]], [-0.464258, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.16, 0.96, 1.72, 2.44])
    keys.append([[0.170649, [3, -0.0666667, 0], [3, 0.266667, 0]], [-0.385718, [3, -0.266667, 0], [3, 0.253333, 0]],
                 [-0.385718, [3, -0.253333, 0], [3, 0.24, 0]], [-0.385718, [3, -0.24, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def lie_back():
    posture_proxy.goToPosture("Crouch", 1)
    # vyrovna_ruky_v_lahu()

    # # Set the target angle for the RHipPitch joint
    # target_angle = -50.0  # in degrees
    # time_list = 1.0       # duration of the movement in seconds

    # target_angle_degrees = 2  # in degrees
    # target_angle_radians = math.radians(target_angle_degrees)  # convert degrees to radians

    # # Ensure the angle is given in radians for the setAngles function
    # target_angle_rad = target_angle * almath.TO_RAD

    # motion_proxy.setAngles("RHipPitch", target_angle_rad, 0.1)  # The last parameter is the fraction of max speed
    # motion_proxy.setAngles("RKneePitch", target_angle_radians, 0.1)  # The last parameter is the fraction of max speed

    # posture_proxy.goToPosture("LyingBack", 0.5)

    # Optionally, you can disable the stiffness after the motion if you no longer need the joint to hold its position
    # motion_proxy.setStiffnesses("RKneePitch", 0.0)


def pozdvihnutie_nohy_lavej():
    names = list()
    times = list()
    keys = list()

    # Head movements remain unchanged
    names.append("HeadPitch")
    times.append([1.52])
    keys.append([[-0.161938, [3, -0.52, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([1.52])
    keys.append([[0, [3, -0.52, 0], [3, 0, 0]]])

    # Mirroring left leg movements to right leg
    names.append("RAnklePitch")
    times.append([1.52])
    keys.append([[0.271206, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([1.52])
    keys.append([[0.00625882, [3, -0.52, 0], [3, 0, 0]]])  # Note the sign change

    # names.append("RElbowRoll")
    # times.append([1.52])
    # keys.append([[1.35295, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("RElbowYaw")
    # times.append([1.52])
    # keys.append([[1.38612, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("RHand")
    # times.append([1.52])
    # keys.append([[0.295002, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([1.52])
    keys.append([[-1.23553, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([1.52])
    keys.append([[-0.0304205, [3, -0.52, 0], [3, 0, 0]]])  # Note the sign change

    # LHipYawPitch does not change because it's a central joint affecting both sides
    names.append("LHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483302, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([1.52])
    keys.append([[1.20577, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("RShoulderPitch")
    # times.append([1.52])
    # keys.append([[1.18677, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("RShoulderRoll")
    # times.append([1.52])
    # keys.append([[-0.658552, [3, -0.52, 0], [3, 0, 0]]])  # Note the sign change

    # names.append("RWristYaw")
    # times.append([1.52])
    # keys.append([[0.145482, [3, -0.52, 0], [3, 0, 0]]])

    # Mirroring right leg movements to left leg (original right leg commands now apply to left leg)
    names.append("LAnklePitch")
    times.append([1.52])
    keys.append([[0.271206, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([1.52])
    keys.append([[-0.00632195, [3, -0.52, 0], [3, 0, 0]]])  # Note the sign change

    # names.append("LElbowRoll")
    # times.append([1.52])
    # keys.append([[-1.35295, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("LElbowYaw")
    # times.append([1.52])
    # keys.append([[-1.38625, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("LHand")
    # times.append([1.52])
    # keys.append([[0.29203, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([1.52])
    keys.append([[-1.50797, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([1.52])
    keys.append([[-0.0116141, [3, -0.52, 0], [3, 0, 0]]])  # Note the sign change

    names.append("LKneePitch")
    times.append([1.52])
    keys.append([[1.19364, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("LShoulderPitch")
    # times.append([1.52])
    # keys.append([[1.18668, [3, -0.52, 0], [3, 0, 0]]])

    # names.append("LShoulderRoll")
    # times.append([1.52])
    # keys.append([[0.65931, [3, -0.52, 0], [3, 0, 0]]])  # Note the sign change

    # names.append("LWristYaw")
    # times.append([1.52])
    # keys.append([[-0.13878, [3, -0.52, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def vystretie_nohy2_nove():
    # Choregraphe bezier export in Python.
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.68])
    keys.append([[-0.161711, [3, -0.24, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.68])
    keys.append([[0.00539045, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.68])
    keys.append([[0.276778, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.68])
    keys.append([[-0.00146097, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.68])
    keys.append([[-1.35139, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.68])
    keys.append([[-1.3859, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.68])
    keys.append([[0.304691, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.68])
    keys.append([[-1.23271, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.68])
    keys.append([[0.02861, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.68])
    keys.append([[-0.478983, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.68])
    keys.append([[1.21061, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.68])
    keys.append([[1.1815, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.68])
    keys.append([[0.653404, [3, -0.24, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.68])
    keys.append([[0.144133, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.68])
    keys.append([[0.276778, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.68])
    keys.append([[0.00975578, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.68])
    keys.append([[1.35139, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.68])
    keys.append([[1.39039, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.68])
    keys.append([[0.29079, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.68])
    keys.append([[-1.50624, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.68])
    keys.append([[0.00547643, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.68])
    keys.append([[-0.478983, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.68])
    keys.append([[0.764454, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.68])
    keys.append([[1.18141, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.68])
    keys.append([[-0.654154, [3, -0.24, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.68])
    keys.append([[-0.139861, [3, -0.24, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def pozdvihnutie_nohy_nove():
    # Choregraphe bezier export in Python.
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([1.52])
    keys.append([[-0.161938, [3, -0.52, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([1.52])
    keys.append([[0, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([1.52])
    keys.append([[0.271207, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([1.52])
    keys.append([[-0.00625882, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([1.52])
    keys.append([[-1.35295, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([1.52])
    keys.append([[-1.38612, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([1.52])
    keys.append([[0.295002, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([1.52])
    keys.append([[-1.23553, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([1.52])
    keys.append([[0.0304206, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483303, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([1.52])
    keys.append([[1.20577, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([1.52])
    keys.append([[1.18677, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([1.52])
    keys.append([[0.658553, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([1.52])
    keys.append([[0.145482, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([1.52])
    keys.append([[0.271207, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([1.52])
    keys.append([[0.00632195, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([1.52])
    keys.append([[1.35295, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([1.52])
    keys.append([[1.38625, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([1.52])
    keys.append([[0.29203, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([1.52])
    keys.append([[-1.52018, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([1.52])
    keys.append([[0.0116141, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483303, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([1.52])
    keys.append([[1.19364, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([1.52])
    keys.append([[1.18668, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([1.52])
    keys.append([[-0.65931, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([1.52])
    keys.append([[-0.13878, [3, -0.52, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def vystretie_nohy1_nove():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.68, 1.48])
    keys.append([[-0.161938, [3, -0.24, 0], [3, 0.266667, 0]], [-0.161938, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.68, 1.48])
    keys.append([[0, [3, -0.24, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.68, 1.48])
    keys.append([[0.271207, [3, -0.24, 0], [3, 0.266667, 0]], [0.271207, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.68, 1.48])
    keys.append([[-0.00625882, [3, -0.24, 0], [3, 0.266667, 0]], [-0.00625882, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.68, 1.48])
    keys.append([[-1.35295, [3, -0.24, 0], [3, 0.266667, 0]], [-1.35295, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.68, 1.48])
    keys.append([[-1.38612, [3, -0.24, 0], [3, 0.266667, 0]], [-1.38612, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.68, 1.48])
    keys.append([[0.295002, [3, -0.24, 0], [3, 0.266667, 0]], [0.295002, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.68, 1.48])
    keys.append([[-1.23553, [3, -0.24, 0], [3, 0.266667, 0]], [-1.23553, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.68, 1.48])
    keys.append([[0.0304206, [3, -0.24, 0], [3, 0.266667, 0]], [0.0304206, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.68, 1.48])
    keys.append([[-0.483303, [3, -0.24, 0], [3, 0.266667, 0]], [-0.483303, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.68, 1.48])
    keys.append([[1.20577, [3, -0.24, 0], [3, 0.266667, 0]], [1.20577, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.68, 1.48])
    keys.append([[1.18677, [3, -0.24, 0], [3, 0.266667, 0]], [1.18677, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.68, 1.48])
    keys.append([[0.658553, [3, -0.24, 0], [3, 0.266667, 0]], [0.658553, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.68, 1.48])
    keys.append([[0.145482, [3, -0.24, 0], [3, 0.266667, 0]], [0.145482, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.68, 1.48])
    keys.append([[0.271207, [3, -0.24, 0], [3, 0.266667, 0]], [0.271207, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.68, 1.48])
    keys.append([[0.00632195, [3, -0.24, 0], [3, 0.266667, 0]], [0.00632195, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.68, 1.48])
    keys.append([[1.35295, [3, -0.24, 0], [3, 0.266667, 0]], [1.35295, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.68, 1.48])
    keys.append([[1.38625, [3, -0.24, 0], [3, 0.266667, 0]], [1.38625, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.68, 1.48])
    keys.append([[0.29203, [3, -0.24, 0], [3, 0.266667, 0]], [0.29203, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.68, 1.48])
    keys.append([[-1.52018, [3, -0.24, 0], [3, 0.266667, 0]], [-1.52018, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.68, 1.48])
    keys.append([[0.0116141, [3, -0.24, 0], [3, 0.266667, 0]], [0.0116141, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.68, 1.48])
    keys.append([[-0.483303, [3, -0.24, 0], [3, 0.266667, 0]], [-0.483303, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.68, 1.48])
    keys.append([[0.949459, [3, -0.24, 0], [3, 0.266667, 0]], [0.853466, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.68, 1.48])
    keys.append([[1.18668, [3, -0.24, 0], [3, 0.266667, 0]], [1.18668, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.68, 1.48])
    keys.append([[-0.65931, [3, -0.24, 0], [3, 0.266667, 0]], [-0.65931, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.68, 1.48])
    keys.append([[-0.13878, [3, -0.24, 0], [3, 0.266667, 0]], [-0.13878, [3, -0.266667, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def pozdvihnutie_nohy_nove_ruky_ostavaju():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([1.52])
    keys.append([[-0.161938, [3, -0.52, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([1.52])
    keys.append([[0, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([1.52])
    keys.append([[0.271207, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([1.52])
    keys.append([[-0.00625882, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([1.52])
    keys.append([[-1.23553, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([1.52])
    keys.append([[0.0304206, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483303, [3, -0.52, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([1.52])
    keys.append([[1.20577, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([1.52])
    keys.append([[0.271207, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([1.52])
    keys.append([[0.00632195, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([1.52])
    keys.append([[-1.52018, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([1.52])
    keys.append([[0.0116141, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([1.52])
    keys.append([[-0.483303, [3, -0.52, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([1.52])
    keys.append([[1.19364, [3, -0.52, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def vystretie_nohy1_nove_ruky_ostavaju():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.68, 1.48])
    keys.append([[-0.161938, [3, -0.24, 0], [3, 0.266667, 0]], [-0.161938, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.68, 1.48])
    keys.append([[0, [3, -0.24, 0], [3, 0.266667, 0]], [0, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.68, 1.48])
    keys.append([[0.271207, [3, -0.24, 0], [3, 0.266667, 0]], [0.271207, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.68, 1.48])
    keys.append([[-0.00625882, [3, -0.24, 0], [3, 0.266667, 0]], [-0.00625882, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.68, 1.48])
    keys.append([[-1.23553, [3, -0.24, 0], [3, 0.266667, 0]], [-1.23553, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.68, 1.48])
    keys.append([[0.0304206, [3, -0.24, 0], [3, 0.266667, 0]], [0.0304206, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.68, 1.48])
    keys.append([[-0.483303, [3, -0.24, 0], [3, 0.266667, 0]], [-0.483303, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.68, 1.48])
    keys.append([[1.20577, [3, -0.24, 0], [3, 0.266667, 0]], [1.20577, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.68, 1.48])
    keys.append([[0.271207, [3, -0.24, 0], [3, 0.266667, 0]], [0.271207, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.68, 1.48])
    keys.append([[0.00632195, [3, -0.24, 0], [3, 0.266667, 0]], [0.00632195, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.68, 1.48])
    keys.append([[-1.52018, [3, -0.24, 0], [3, 0.266667, 0]], [-1.52018, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.68, 1.48])
    keys.append([[0.0116141, [3, -0.24, 0], [3, 0.266667, 0]], [0.0116141, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.68, 1.48])
    keys.append([[-0.483303, [3, -0.24, 0], [3, 0.266667, 0]], [-0.483303, [3, -0.266667, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.68, 1.48])
    keys.append([[0.949459, [3, -0.24, 0], [3, 0.266667, 0]], [0.853466, [3, -0.266667, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def vystretie_nohy2_nove_ruky_ostavaju():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0.72])
    keys.append([[-0.17, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0.72])
    keys.append([[0, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0.72])
    keys.append([[0.268914, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0.72])
    keys.append([[-0.00558696, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0.72])
    keys.append([[-1.35139, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0.72])
    keys.append([[-1.3859, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0.72])
    keys.append([[0.3, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0.72])
    keys.append([[-1.23046, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0.72])
    keys.append([[0.0306377, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0.72])
    keys.append([[-0.476438, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0.72])
    keys.append([[1.2156, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0.72])
    keys.append([[0.45115, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0.72])
    keys.append([[0.299737, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0.72])
    keys.append([[0.144133, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0.72])
    keys.append([[0.268914, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0.72])
    keys.append([[0.00641184, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0.72])
    keys.append([[1.35139, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0.72])
    keys.append([[1.39039, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0.72])
    keys.append([[0.3, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0.72])
    keys.append([[-1.51936, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0.72])
    keys.append([[0.00645995, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0.72])
    keys.append([[-0.476438, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0.72])
    keys.append([[0.745256, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0.72])
    keys.append([[0.451164, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0.72])
    keys.append([[-0.300829, [3, -0.253333, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0.72])
    keys.append([[-0.139861, [3, -0.253333, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def pozdvihnutie_nohy_lavej_z_robotv():
    names = list()
    times = list()
    keys = list()

    names.append("HeadPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.164615, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.164343, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-0.164343, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.164343, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-0.164343, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.164343, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-0.164343, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.164343, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("HeadYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0, [3, -0.0133333, 0], [3, 0.266667, 0]], [2.42761e-05, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [2.42761e-05, [3, -0.226667, 0], [3, 0.226667, 0]], [2.42761e-05, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [2.42761e-05, [3, -0.173333, 0], [3, 0.173333, 0]], [2.42761e-05, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [2.42761e-05, [3, -0.186667, 0], [3, 0.186667, 0]], [2.42761e-05, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LAnklePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.270996, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.269901, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.269901, [3, -0.226667, 0], [3, 0.226667, 0]], [0.269901, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.269901, [3, -0.173333, 0], [3, 0.173333, 0]], [0.269901, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.269901, [3, -0.186667, 0], [3, 0.186667, 0]], [0.269901, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LAnkleRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append(
        [[-0.00625882, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.00122033, [3, -0.266667, 0], [3, 0.226667, 0]],
         [-0.00122033, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.00122033, [3, -0.226667, 0], [3, 0.173333, 0]],
         [-0.00122033, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.00122033, [3, -0.173333, 0], [3, 0.186667, 0]],
         [-0.00625882, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.00625882, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LElbowRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.35295, [3, -0.0133333, 0], [3, 0.266667, 0]], [-1.35295, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-1.35295, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.35295, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.35295, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.35295, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.35295, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.35295, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LElbowYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.38612, [3, -0.0133333, 0], [3, 0.266667, 0]], [-1.38612, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-1.38612, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.38612, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.38612, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.38612, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.38612, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.38612, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHand")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.302346, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.298696, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.298696, [3, -0.226667, 0], [3, 0.226667, 0]], [0.298696, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.298696, [3, -0.173333, 0], [3, 0.173333, 0]], [0.298696, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.298696, [3, -0.186667, 0], [3, 0.186667, 0]], [0.298696, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.23046, [3, -0.0133333, 0], [3, 0.266667, 0]], [-1.41694, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-1.41694, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.41694, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.48353, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.48353, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.48334, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.48334, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.0306377, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.02861, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.02861, [3, -0.226667, 0], [3, 0.226667, 0]], [0.02861, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.02861, [3, -0.173333, 0], [3, 0.173333, 0]], [0.02861, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.02861, [3, -0.186667, 0], [3, 0.186667, 0]], [0.02861, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LHipYawPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.476438, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [-0.478983, [3, -0.266667, 0.00254472], [3, 0.226667, -0.00216301]],
                 [-0.514872, [3, -0.226667, 0.0222713], [3, 0.226667, -0.0222713]],
                 [-0.612611, [3, -0.226667, 0], [3, 0.173333, 0]], [-0.612611, [3, -0.173333, 0], [3, 0.173333, 0]],
                 [-0.612611, [3, -0.173333, 0], [3, 0.186667, 0]], [-0.604598, [3, -0.186667, 0], [3, 0.186667, 0]],
                 [-0.604598, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LKneePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.2156, [3, -0.0133333, 0], [3, 0.266667, 0]], [1.21061, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [1.21061, [3, -0.226667, 0], [3, 0.226667, 0]], [1.21061, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.14494, [3, -0.173333, 0.0301436], [3, 0.173333, -0.0301436]],
                 [1.02974, [3, -0.173333, 0.0305459], [3, 0.186667, -0.0328956]],
                 [0.954611, [3, -0.186667, 0.0293797], [3, 0.186667, -0.0293797]],
                 [0.853466, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LShoulderPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.445853, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.445853, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.445853, [3, -0.226667, 0], [3, 0.226667, 0]], [0.445853, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.445853, [3, -0.173333, 0], [3, 0.173333, 0]], [0.445853, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.445853, [3, -0.186667, 0], [3, 0.186667, 0]], [0.445853, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LShoulderRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.293906, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.293913, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.293913, [3, -0.226667, 0], [3, 0.226667, 0]], [0.293913, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.293913, [3, -0.173333, 0], [3, 0.173333, 0]], [0.293913, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.293913, [3, -0.186667, 0], [3, 0.186667, 0]], [0.293913, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("LWristYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.145482, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.145482, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.145482, [3, -0.226667, 0], [3, 0.226667, 0]], [0.145482, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.145482, [3, -0.173333, 0], [3, 0.173333, 0]], [0.145482, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.145482, [3, -0.186667, 0], [3, 0.186667, 0]], [0.145482, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RAnklePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.270996, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.269901, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.269901, [3, -0.226667, 0], [3, 0.226667, 0]], [0.269901, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.269901, [3, -0.173333, 0], [3, 0.173333, 0]], [0.269901, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.269901, [3, -0.186667, 0], [3, 0.186667, 0]], [0.269901, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RAnkleRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.00632195, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.00123263, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.00123263, [3, -0.226667, 0], [3, 0.226667, 0]], [0.00123263, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.00123263, [3, -0.173333, 0], [3, 0.173333, 0]], [0.00123263, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.00632195, [3, -0.186667, 0], [3, 0.186667, 0]], [0.00632195, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RElbowRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.35295, [3, -0.0133333, 0], [3, 0.266667, 0]], [1.35295, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [1.35295, [3, -0.226667, 0], [3, 0.226667, 0]], [1.35295, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.35295, [3, -0.173333, 0], [3, 0.173333, 0]], [1.35295, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [1.35295, [3, -0.186667, 0], [3, 0.186667, 0]], [1.35295, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RElbowYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.38625, [3, -0.0133333, 0], [3, 0.266667, 0]], [1.38625, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [1.38625, [3, -0.226667, 0], [3, 0.226667, 0]], [1.38625, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.38625, [3, -0.173333, 0], [3, 0.173333, 0]], [1.38625, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [1.38625, [3, -0.186667, 0], [3, 0.186667, 0]], [1.38625, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHand")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.291937, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.29724, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.29724, [3, -0.226667, 0], [3, 0.226667, 0]], [0.29724, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.29724, [3, -0.173333, 0], [3, 0.173333, 0]], [0.29724, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.29724, [3, -0.186667, 0], [3, 0.186667, 0]], [0.29724, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-1.24461, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [-1.24323, [3, -0.266667, -0.00138578], [3, 0.226667, 0.00117791]],
                 [-1.17461, [3, -0.226667, 0], [3, 0.226667, 0]], [-1.17461, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-1.17461, [3, -0.173333, 0], [3, 0.173333, 0]], [-1.17461, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-1.17866, [3, -0.186667, 0], [3, 0.186667, 0]], [-1.17866, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.00645995, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.00547642, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.00872665, [3, -0.226667, 0], [3, 0.226667, 0]], [0.00872665, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.00872665, [3, -0.173333, 0], [3, 0.173333, 0]], [0.00872665, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.00547642, [3, -0.186667, 0], [3, 0.186667, 0]], [0.00547642, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RHipYawPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.476438, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [-0.478983, [3, -0.266667, 0.00254472], [3, 0.226667, -0.00216301]],
                 [-0.514872, [3, -0.226667, 0.0222713], [3, 0.226667, -0.0222713]],
                 [-0.612611, [3, -0.226667, 0], [3, 0.173333, 0]], [-0.612611, [3, -0.173333, 0], [3, 0.173333, 0]],
                 [-0.612611, [3, -0.173333, 0], [3, 0.186667, 0]], [-0.604598, [3, -0.186667, 0], [3, 0.186667, 0]],
                 [-0.604598, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RKneePitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[1.20262, [3, -0.0133333, 0], [3, 0.266667, 0]],
                 [1.21059, [3, -0.266667, -0.00797444], [3, 0.226667, 0.00677827]],
                 [1.29329, [3, -0.226667, 0], [3, 0.226667, 0]], [1.29329, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [1.29329, [3, -0.173333, 0], [3, 0.173333, 0]], [1.29329, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [1.28854, [3, -0.186667, 0], [3, 0.186667, 0]], [1.28854, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RShoulderPitch")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[0.44586, [3, -0.0133333, 0], [3, 0.266667, 0]], [0.44586, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [0.44586, [3, -0.226667, 0], [3, 0.226667, 0]], [0.44586, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [0.44586, [3, -0.173333, 0], [3, 0.173333, 0]], [0.44586, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [0.44586, [3, -0.186667, 0], [3, 0.186667, 0]], [0.44586, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RShoulderRoll")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.294041, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.294048, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-0.294048, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.294048, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-0.294048, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.294048, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-0.294048, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.294048, [3, -0.186667, 0], [3, 0, 0]]])

    names.append("RWristYaw")
    times.append([0, 0.8, 1.48, 2.16, 2.68, 3.2, 3.76, 4.32])
    keys.append([[-0.134848, [3, -0.0133333, 0], [3, 0.266667, 0]], [-0.135919, [3, -0.266667, 0], [3, 0.226667, 0]],
                 [-0.135919, [3, -0.226667, 0], [3, 0.226667, 0]], [-0.135919, [3, -0.226667, 0], [3, 0.173333, 0]],
                 [-0.135919, [3, -0.173333, 0], [3, 0.173333, 0]], [-0.135919, [3, -0.173333, 0], [3, 0.186667, 0]],
                 [-0.135919, [3, -0.186667, 0], [3, 0.186667, 0]], [-0.135919, [3, -0.186667, 0], [3, 0, 0]]])

    motion_proxy.angleInterpolationBezier(names, times, keys)


def leziaca_sekvencia_iba_lah():
    posture_proxy.goToPosture("LyingBack", 1.0)
    motion_proxy.angleInterpolationBezier(vyrovna_ruky_v_lahu_vedla_tela.names, vyrovna_ruky_v_lahu_vedla_tela.times,
                                          vyrovna_ruky_v_lahu_vedla_tela.keys)
    motion_proxy.angleInterpolationBezier(prava_noha_vyrovnaj_po_zakl_lahu.names,
                                          prava_noha_vyrovnaj_po_zakl_lahu.times, prava_noha_vyrovnaj_po_zakl_lahu.keys)

    # # #0 - OK

    # # Set the target angle for the RHipPitch joint
    # target_angle = -50.0  # in degrees
    # time_list = 1.0       # duration of the movement in seconds

    # target_angle_degrees = 2  # in degrees
    # target_angle_radians = math.radians(target_angle_degrees)  # convert degrees to radians

    # # Ensure the angle is given in radians for the setAngles function
    # target_angle_rad = target_angle * almath.TO_RAD

    # motion_proxy.setAngles("RHipPitch", target_angle_rad, 0.1)  # The last parameter is the fraction of max speed
    # motion_proxy.setAngles("RKneePitch", target_angle_radians, 0.1)  # The last parameter is the fraction of max speed


def leziaca_sekvencia():
    # -1 - OK
    posture_proxy.goToPosture("LyingBack", 1.0)
    motion_proxy.angleInterpolationBezier(vyrovna_ruky_v_lahu_vedla_tela.names, vyrovna_ruky_v_lahu_vedla_tela.times,
                                          vyrovna_ruky_v_lahu_vedla_tela.keys)
    motion_proxy.angleInterpolationBezier(prava_noha_vyrovnaj_po_zakl_lahu.names,
                                          prava_noha_vyrovnaj_po_zakl_lahu.times, prava_noha_vyrovnaj_po_zakl_lahu.keys)

    # #0 - OK

    # Set the target angle for the RHipPitch joint
    target_angle = -50.0  # in degrees
    time_list = 1.0  # duration of the movement in seconds

    target_angle_degrees = 2  # in degrees
    target_angle_radians = math.radians(target_angle_degrees)  # convert degrees to radians

    # Ensure the angle is given in radians for the setAngles function
    target_angle_rad = target_angle * almath.TO_RAD

    motion_proxy.setAngles("RHipPitch", target_angle_rad, 0.1)  # The last parameter is the fraction of max speed
    motion_proxy.setAngles("RKneePitch", target_angle_radians, 0.1)  # The last parameter is the fraction of max speed

    # #1 - OK
    motion_proxy.angleInterpolationBezier(prava_noha_zdvihnuta_v_lahu_naspat.names,
                                          prava_noha_zdvihnuta_v_lahu_naspat.times,
                                          prava_noha_zdvihnuta_v_lahu_naspat.keys)

    # #2
    # motion_proxy.angleInterpolationBezier(vyrovna_ruky_v_lahu_vedla_tela.names, vyrovna_ruky_v_lahu_vedla_tela.times, vyrovna_ruky_v_lahu_vedla_tela.keys)
    # motion_proxy.angleInterpolationBezier(poloha_lahu_vymenena_noha.names, poloha_lahu_vymenena_noha.times, poloha_lahu_vymenena_noha.keys)

    # Set the target angle for the RHipPitch joint
    target_angle = -50.0  # in degrees
    time_list = 1.0  # duration of the movement in seconds

    target_angle_degrees = 2  # in degrees
    target_angle_radians = math.radians(target_angle_degrees)  # convert degrees to radians

    # Ensure the angle is given in radians for the setAngles function
    target_angle_rad = target_angle * almath.TO_RAD

    motion_proxy.setAngles("LHipPitch", target_angle_rad, 0.1)  # The last parameter is the fraction of max speed
    motion_proxy.setAngles("LKneePitch", target_angle_radians, 0.1)  # The last parameter is the fraction of max speed

    # #3
    motion_proxy.angleInterpolationBezier(lava_noha_naspat_v_lahu.names, lava_noha_naspat_v_lahu.times,
                                          lava_noha_naspat_v_lahu.keys)

    # motion_proxy.angleInterpolationBezier(poloha_lahu_vymenena_noha.names, poloha_lahu_vymenena_noha.times, poloha_lahu_vymenena_noha.keys)

    # #4
    # posture_proxy.goToPosture("LyingBack", 1.0)


def set_stiffness_on(proxy):
    # 'Body' refers to all joints
    pNames = "Body"
    pStiffnessLists = 1.0
    pTimeLists = 1.0
    proxy.stiffnessInterpolation(pNames, pStiffnessLists, pTimeLists)


def perform_limp_walk(motion_proxy, duration=4.0):
    # Custom walk parameters for limping
    limp_walk_params = [
        ["StepHeight", 0.02], ["TorsoWy", 5.0 * almath.TO_RAD],  # Left foot
        ["StepHeight", 0.005], ["MaxStepX", 0.001], ["MaxStepFrequency", 0.0],
        ["TorsoWx", -7.0 * almath.TO_RAD], ["TorsoWy", 5.0 * almath.TO_RAD]  # Right foot
    ]

    # Apply the limp walk configuration
    motion_proxy.setWalkTargetVelocity(1.0, 0.0, 0.0, 1.0, limp_walk_params)
    time.sleep(duration)


def perform_trajectory_walk(motion_proxy, path):
    # Walk through the defined path
    for movement in path:
        motion_proxy.moveTo(movement['x'], movement['y'], movement['theta'])
        time.sleep(1)  # Time between movements for stability, adjust as necessary


def sekvencia_chodenia():
    # Ensure the robot is in a standing position
    # motion_proxy.wakeUp()

    # Custom gait parameters for stability
    move_config = [
        ["MaxStepX", 0.04],  # Reduce forward step size
        ["MaxStepY", 0.0],  # Limit lateral step size for stability
        ["MaxStepTheta", 0.0],  # Reduce rotation per step
        ["StepHeight", 0.01],  # Lower step height to maintain lower center of gravity
        ["TorsoWx", 0],  # Minor forward lean
        ["TorsoWy", 0.0]  # No lateral lean
    ]

    # Move with custom parameters: forward with adjustments for stability
    motion_proxy.move(0.5, 0, 0, move_config)

    # For demonstration, stop the movement after 5 seconds
    import time
    time.sleep(25)
    motion_proxy.stopMove()


def main():
    # posture_proxy.goToPosture("Crouch", 1.0)

    # Take one step backward

    # backward_distance = -0.25  # Negative for moving backwards, adjust the value as necessary
    # motion_proxy.moveTo(backward_distance, 0, 0)  # x, y, theta

    # sekvencia_chodenia()
    # leziaca_sekvencia_iba_lah()
    # leziaca_sekvencia()

    # posture_proxy.goToPosture("Crouch", 1.0)
    # lie_back()
    # posture_proxy.goToPosture("SitRelax", 1.0)
    # raise_arm()

    # stand_up_from_sitting_on_chair()

    # stand_up_sequence()
    # stand_up_from_sitting_on_chair()
    # stand_up_from_sitting()
    # ruky_k_sebe()
    # raise_arm()
    # lower_arms_in_sitting_position()
    # raise_arm()
    # lower_arms_in_sitting_position()
    # adjust_balance()

    # apply_balance_control()

    # vystretie_nohy2()
    # apply_balance_control()

    # names = list()
    # times = list()
    # keys = list()
    # names.append("LShoulderPitch")
    # times.append([1, 1.8])
    # keys.append([[0.932006, [3, -0.346667, 0], [3, 0.266667, 0]], [0.932006, [3, -0.266667, 0], [3, 0, 0]]])
    # names.append("LShoulderRoll")
    # times.append([1.8])
    # keys.append([[0.141372, [3, -0.613333, 0], [3, 0, 0]]])
    # names.append("RShoulderPitch")
    # times.append([1, 1.8])
    # keys.append([[0.932006, [3, -0.346667, 0], [3, 0.266667, 0]], [0.932006, [3, -0.266667, 0], [3, 0, 0]]])
    # names.append("RShoulderRoll")
    # times.append([1.8])
    # keys.append([[-0.141372, [3, -0.613333, 0], [3, 0, 0]]])
    # motion_proxy.angleInterpolationBezier(names, times, keys)
    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # raise_arm()
    motion_proxy.angleInterpolationBezier(sit_on_chair.names, sit_on_chair.times, sit_on_chair.keys)

    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # pozdivhnutie_nohy_lavej2()
    # raise_arm()

    # lower_arms_in_sitting_position()

    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair1.names, lift_right_leg_on_chair1.times, lift_right_leg_on_chair1.keys)
    # motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair2.names, lift_right_leg_on_chair2.times, lift_right_leg_on_chair2.keys)
    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)
    # pozdivhnutie_nohy_lavej2()
    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # pozdvihnutie_nohy_lavej()
    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # pozdvihnutie_nohy_lavej()
    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # isEnabled = True
    # motion_proxy.wbEnable(isEnabled)

    # vystretie_nohy2()
    # vystretie_nohy1()

    # pass
    # stand_up_from_sitting_on_chair()
    # motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    # pozdvihnutie_nohy_nove()
    # vystretie_nohy1_nove()

    # sit_to_position_for_extending_legs()
    # stand_up_from_sitting_on_chair()

    # sit_to_position_for_extending_legs()

    # motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair1.names, lift_right_leg_on_chair1.times, lift_right_leg_on_chair1.keys)
    # motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair2.names, lift_right_leg_on_chair2.times, lift_right_leg_on_chair2.keys)
    # motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair3.names, lift_right_leg_on_chair3.times, lift_right_leg_on_chair3.keys)

    # stand_up_from_sitting_on_chair()
    # sit_to_position_for_extending_legs()

    # # sit_to_position_for_extending_legs()
    # # pozdvihnutie_nohy_nove_ruky_ostavaju()
    # # vystretie_nohy1_nove_ruky_ostavaju()

    # for _ in range(10):
    #     motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair1.names, lift_right_leg_on_chair1.times, lift_right_leg_on_chair1.keys)
    #     motion_proxy.angleInterpolationBezier(lift_right_leg_on_chair2.names, lift_right_leg_on_chair2.times, lift_right_leg_on_chair2.keys)
    #     # vystretie_nohy2_nove_ruky_ostavaju()
    #     motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)

    #     pozdvihnutie_nohy_lavej_z_robotv()
    #     motion_proxy.angleInterpolationBezier(vratenie_zdvihnutych_noh_v_sede.names, vratenie_zdvihnutych_noh_v_sede.times, vratenie_zdvihnutych_noh_v_sede.keys)
    # leziaca_sekcencia()


if __name__ == "__main__":
    main()
