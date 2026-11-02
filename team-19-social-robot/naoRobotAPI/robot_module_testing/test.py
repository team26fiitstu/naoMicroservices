import qi
import sys
import argparse
import os
import dotenv

dotenv.load_dotenv()


class TestAlMotionBasic():
    def set_positions(self, session):
        motionProxy = session.service("ALMotion")

        motionProxy.setStiffnesses("Head", 1.0)

        names = "HeadPitch"
        angleLists = 0.349
        timeLists = 1.0
        isAbsolute = True
        motionProxy.angleInterpolation(names, angleLists, timeLists, isAbsolute)

    def run_test(self):
        NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
        NAO_PORT = int(os.environ.get("NAO_PORT", 9559))
        parser = argparse.ArgumentParser()
        parser.add_argument("--ip", type=str, default=NAO_IP,
                            help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
        parser.add_argument("--port", type=int, default=NAO_PORT,
                            help="Naoqi port number")

        args = parser.parse_args()
        session = qi.Session()
        try:
            session.connect("tcp://" + args.ip + ":" + str(args.port))
        except RuntimeError:
            print ("Can't connect to Naoqi at ip \"" + args.ip + "\" on port " + str(args.port) + ".\n"
                                                                                                  "Please check your script arguments. Run with -h option for help.")
            sys.exit(1)
        self.set_positions(session)


if __name__ == "__main__":
    TestAlMotionBasic().run_test()
