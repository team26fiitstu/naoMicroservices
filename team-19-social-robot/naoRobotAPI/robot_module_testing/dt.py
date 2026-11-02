# -*- encoding: UTF-8 -*- 

'''Cartesian control: Multiple Effector Trajectories'''
import os
from naoqi import ALProxy
import dotenv

dotenv.load_dotenv()

NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
NAO_PORT = int(os.environ.get("NAO_PORT", 9559))


motionProxy = ALProxy("ALMotion", NAO_IP, NAO_PORT)
postureProxy = ALProxy("ALRobotPosture", NAO_IP, NAO_PORT)
memory_proxy = ALProxy("ALMemory", NAO_IP, NAO_PORT)


def left_leg_down():
    names = list()
    times = list()
    keys = list()

    names.append("LAnkleRoll")
    times.append([3])
    keys.append([0.331613])

    names.append("LHipRoll")
    times.append([3])
    keys.append([-0.331613])

    names.append("RAnkleRoll")
    times.append([3])
    keys.append([0.331613])

    names.append("RHipRoll")
    times.append([3])
    keys.append([-0.331613])

    motionProxy.angleInterpolationBezier(names, times, keys)

    motionProxy.setAngles(["RKneePitch"], 1.4, 0.12)  # 100 deg
    motionProxy.setAngles(["RAnklePitch"], -0.65, 0.12)  # -50 deg
    motionProxy.setAngles(["RHipPitch"],  -0.8, 0.12)  # -60 deg
    # lift opposite arm for stability
    motionProxy.setAngles(["LShoulderRoll"], 1.3264502315, 0.15)
    motionProxy.setAngles(["LElbowRoll"], 1.3264502315, 0.15)


def left_leg_up():
    motionProxy.setAngles(
        ["RAnklePitch"], -0.1745329252, 0.2)  # back to -10 deg
    postureProxy.goToPosture("StandInit", 0.2)


def right_leg_down():
    names = list()
    times = list()
    keys = list()

    names.append("LAnkleRoll")
    times.append([2])
    keys.append([-0.331613])

    names.append("LHipRoll")
    times.append([2])
    keys.append([0.331613])

    names.append("RAnkleRoll")
    times.append([2])
    keys.append([-0.331613])

    names.append("RHipRoll")
    times.append([2])
    keys.append([0.331613])

    motionProxy.angleInterpolationBezier(names, times, keys)


    motionProxy.setAngles(["LKneePitch"], 1.4, 0.12)  # 100 degrees
    motionProxy.setAngles(["LAnklePitch"], -0.65, 0.12)  # -50 deg
    motionProxy.setAngles(["LHipPitch"], -0.8, 0.12)  # -60 deg

    # lift opposite arm for stability
    motionProxy.setAngles(["RShoulderRoll"], -1.3264502315, 0.15)
    motionProxy.setAngles(["RElbowRoll"], -1.3264502315, 0.15)

def right_leg_up():
    motionProxy.setAngles(["LAnklePitch"], -0.1745329252, 0.2)
    postureProxy.goToPosture("StandInit", 0.2)


right_leg_down()
right_leg_up()

# left_leg_down()
# left_leg_up()