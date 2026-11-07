# -*- coding: utf-8 -*-
import os
from naoqi import ALBroker, ALProxy
import time
import math


NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
NAO_PORT = int(os.environ.get("NAO_PORT", 9559))


class FaceTracker:
    def __init__(self, nao_ip, nao_port, target_name="Face", width=0.1, distanceX=0.0, distanceY=0.0, angleWz=0.0,
                 thresholdX=0.05, thresholdY=0.05, thresholdWz=0.1, search_angles=[-35, 35, 0],
                 search_tilt=35):
        self.NAO_IP = nao_ip
        self.NAO_PORT = nao_port
        self.targetName = target_name
        self.width = width
        self.distanceX = distanceX
        self.distanceY = distanceY
        self.angleWz = angleWz
        self.thresholdX = thresholdX
        self.thresholdY = thresholdY
        self.thresholdWz = thresholdWz
        self.search_angles = search_angles
        self.search_tilt = search_tilt
        self.last_seen = time.time()
        self.last_head_adjust = time.time()
        self.face_found = False  # Flag to keep track of whether face has been found

        # Create broker
        self.broker = ALBroker("myBroker", "0.0.0.0", 0, self.NAO_IP, self.NAO_PORT)

        # Create proxies
        self.tracker = ALProxy("ALTracker")
        self.motion = ALProxy("ALMotion")
        self.memory = ALProxy("ALMemory")
        self.speechProxy = ALProxy("ALTextToSpeech", self.NAO_IP, self.NAO_PORT)

        # Subscribe to events
        self.memory.subscribeToEvent("ALTracker/TargetLost", "ALTracker", "onTargetLost")
        self.memory.subscribeToEvent("ALTracker/TargetReached", "ALTracker", "onTargetReached")
        self.memory.subscribeToEvent("ALTracker/ActiveTargetChanged", "ALTracker", "onTargetChanged")

    def start_tracking(self):
        self.tracker.registerTarget(self.targetName, self.width)
        self.tracker.setRelativePosition([-self.distanceX, self.distanceY, self.angleWz,
                                          self.thresholdX, self.thresholdY, self.thresholdWz])
        self.tracker.track(self.targetName)

    def stop_tracking(self):
        self.tracker.stopTracker()
        self.tracker.unregisterTarget(self.targetName)
        self.memory.unsubscribeToEvent("ALTracker/TargetLost", self.tracker.getName())

    def search_for_face(self):
        if time.time() - self.last_seen > 3 and not self.face_found:
            for angle in self.search_angles:
                self.motion.setAngles("HeadYaw", math.radians(angle), 0.1)
                time.sleep(2)
                if not self.tracker.isTargetLost():
                    self.face_found = True
                    self.speechProxy.say("Poďme cvičiť!")
                    print("Face found!")
                    return True  # Return True if face is found
            self.motion.setAngles("HeadPitch", math.radians(-self.search_tilt), 0.1)
            time.sleep(0.8)
            self.motion.setAngles(["HeadYaw", "HeadPitch"], [0, 0], 0.1)
            self.last_seen = time.time()
        return False  # Return False if face is not found

    def restart_tracking(self):
        self.face_found = False  # Reset the flag
        self.stop_tracking()
        self.start_tracking()

    def __del__(self):
        self.stop_tracking()
        self.broker.shutdown()
