# -*- coding: utf-8 -*-
import os
from naoqi import ALProxy
import dotenv
import time
from flask import g
import string

if os.environ.get("LOCAL", "True") == "True":
    dotenv.load_dotenv()

def set_to_nao_speed_range(current_speed):
    if 0 > int(current_speed) > 100:
        raise Exception("Exceeded allowed limits")
    return int(int(current_speed) * 350 / 100 + 50)

def set_voice_lines(voice_lines_config):
    if "speech_proxy" not in g:
        NAO_IP = os.environ.get("NAO_IP", "127.0.0.1")
        NAO_PORT = int(os.environ.get("NAO_PORT", 9559))
        g.speech_proxy = ALProxy("ALTextToSpeech", NAO_IP, NAO_PORT)
    if "speed" in voice_lines_config:
        g.speech_proxy.setParameter("speed", int(set_to_nao_speed_range(voice_lines_config["speed"])))
    elif "lang" not in voice_lines_config or voice_lines_config["lang"] == "English":
        g.speech_proxy.setParameter("speed", 80)
    elif voice_lines_config["lang"] == "sk":
        g.speech_proxy.setParameter("speed", 100)

    lang = voice_lines_config["lang"] if "lang" in voice_lines_config else "English"
    lang = "English" if not lang else lang

    if voice_lines_config and "extractedText" in voice_lines_config and "Nothing so far" not in voice_lines_config["extractedText"]:
        if "wait" in voice_lines_config and voice_lines_config["wait"]:
            time.sleep(float(voice_lines_config["wait"]))
        text = unicode(voice_lines_config["extractedText"]).encode('utf8', 'replace')
        try:
            g.speech_proxy.say("" + text, lang)
        except:
            lang = lang.encode('utf8', 'replace')
            g.speech_proxy.say(voice_lines_config["extractedText"].encode('utf8', 'replace'), lang)
    else:
        # one time to say
        if "voice_lines_configs" in voice_lines_config:
            for _, voice_line_config in voice_lines_config["voice_lines_configs"].items():
                if "wait" in voice_line_config and voice_line_config["wait"]:
                    time.sleep(float(voice_line_config["wait"]))
                text = unicode(voice_line_config["translation"]).encode('utf8', 'replace')
                try:
                    g.speech_proxy.say("" + text, lang)
                except:
                    lang = lang.encode('utf8', 'replace')
                    g.speech_proxy.say(voice_line_config["translation"].encode('utf8', 'replace'), lang)
        else:
            print("Voice lines are not available in config")
 