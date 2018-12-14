#!/usr/bin/env python

# Copyright (C) 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
from kodijson import Kodi, PLAYER_VIDEO
try:
    import RPi.GPIO as GPIO
except Exception as e:
    if str(e) == 'No module named \'RPi\'':
        GPIO = None
import argparse
import json
import os.path
import pathlib2 as pathlib
import os
import subprocess
import re
import psutil
import logging
import time
import random
import snowboydecoder
import sys
import signal
import requests
import google.oauth2.credentials
from google.assistant.library import Assistant
from google.assistant.library.event import EventType
from google.assistant.library.file_helpers import existing_file
from google.assistant.library.device_helpers import register_device
from kodijson import Kodi, PLAYER_VIDEO
from actions import configuration
from actions import custom_action
from actions import vlcplayer
from threading import Thread
if GPIO!=None:
    from indicator import assistantindicator
    from indicator import stoppushbutton
    GPIOcontrol=True
else:
    GPIOcontrol=False
from pathlib import Path


try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


WARNING_NOT_REGISTERED = """
    This device is not registered. This means you will not be able to use
    Device Actions or see your device in Assistant Settings. In order to
    register this device follow instructions at:

    https://developers.google.com/assistant/sdk/guides/library/python/embed/register-device
"""

logging.basicConfig(filename='/tmp/GassistPi.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

ROOT_PATH = os.path.realpath(os.path.join(__file__, '..', '..'))
USER_PATH = os.path.realpath(os.path.join(__file__, '..', '..','..'))

#Login with default kodi/kodi credentials
#kodi = Kodi("http://localhost:8080/jsonrpc")
#Login with custom credentials
# Kodi("http://IP-ADDRESS-OF-KODI:8080/jsonrpc", "username", "password")
kodiurl=("http://"+str(configuration['Kodi']['ip'])+":"+str(configuration['Kodi']['port'])+"/jsonrpc")
kodi = Kodi(kodiurl, configuration['Kodi']['username'], configuration['Kodi']['password'])
if configuration['Kodi']['Kodi_Control']=='Enabled':
    kodicontrol=True
else:
    kodicontrol=False


mutestopbutton=True

#Check if custom wakeword has been enabled
if configuration['Wakewords']['Custom_Wakeword']=='Enabled':
    custom_wakeword=True
else:
    custom_wakeword=False

models=configuration['Wakewords']['Custom_wakeword_models']

# Check if VLC is paused
def checkvlcpaused():
    state=vlcplayer.state()
    if str(state)=="State.Paused":
        currentstate=True
    else:
        currentstate=False
    return currentstate

class Myassistant():

    def __init__(self):
        self.interrupted=False
        self.can_start_conversation=False
        self.assistant=None
        self.sensitivity = [0.5]*len(models)
        self.callbacks = [self.detected]*len(models)
        self.detector = snowboydecoder.HotwordDetector(models, sensitivity=self.sensitivity)
        self.t1 = Thread(target=self.start_detector)
        if GPIOcontrol:
            self.t2 = Thread(target=self.pushbutton)

    def signal_handler(self,signal, frame):
        self.interrupted = True

    def interrupt_callback(self,):
        return self.interrupted

    def buttonsinglepress(self):
        if os.path.isfile("{}/.mute".format(USER_PATH)):
            os.system("sudo rm {}/.mute".format(USER_PATH))
            assistantindicator('unmute')
            if configuration['Wakewords']['Ok_Google']=='Disabled':
                self.assistant.set_mic_mute(True)
            else:
                self.assistant.set_mic_mute(False)
            # if custom_wakeword:
            #     self.t1.start()
            subprocess.Popen(["aplay", "{}/sample-audio-files/Mic-On.wav".format(ROOT_PATH)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("Turning on the microphone")
        else:
            open('{}/.mute'.format(USER_PATH), 'a').close()
            assistantindicator('mute')
            self.assistant.set_mic_mute(True)
            # if custom_wakeword:
            #     self.thread_end(t1)
            subprocess.Popen(["aplay", "{}/sample-audio-files/Mic-Off.wav".format(ROOT_PATH)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("Turning off the microphone")

    def buttondoublepress(self):
        print('Stopped')
        stop()

    def buttontriplepress(self):
        print("Create your own action for button triple press")

    def pushbutton(self):
        if GPIOcontrol:
            while mutestopbutton:
                time.sleep(.1)
                if GPIO.event_detected(stoppushbutton):
                    GPIO.remove_event_detect(stoppushbutton)
                    now = time.time()
                    count = 1
                    GPIO.add_event_detect(stoppushbutton,GPIO.RISING)
                    while time.time() < now + 1:
                         if GPIO.event_detected(stoppushbutton):
                             count +=1
                             time.sleep(.25)
                    if count == 2:
                        self.buttonsinglepress()
                        GPIO.remove_event_detect(stoppushbutton)
                        GPIO.add_event_detect(stoppushbutton,GPIO.FALLING)
                    elif count == 3:
                        self.buttondoublepress()
                        GPIO.remove_event_detect(stoppushbutton)
                        GPIO.add_event_detect(stoppushbutton,GPIO.FALLING)
                    elif count == 4:
                        self.buttontriplepress()
                        GPIO.remove_event_detect(stoppushbutton)
                        GPIO.add_event_detect(stoppushbutton,GPIO.FALLING)


    def process_device_actions(self,event, device_id):
        if 'inputs' in event.args:
            for i in event.args['inputs']:
                if i['intent'] == 'action.devices.EXECUTE':
                    for c in i['payload']['commands']:
                        for device in c['devices']:
                            if device['id'] == device_id:
                                if 'execution' in c:
                                    for e in c['execution']:
                                        if 'params' in e:
                                            yield e['command'], e['params']
                                        else:
                                            yield e['command'], None


    def process_event(self,event):
        """Pretty prints events.
        Prints all events that occur with two spaces between each new
        conversation and a single space between turns of a conversation.
        Args:
            event(event.Event): The current event to process.
        """
        print(event)
        if event.type == EventType.ON_START_FINISHED:
            self.can_start_conversation = True
            if GPIOcontrol:
                self.t2.start()
            if os.path.isfile("{}/.mute".format(USER_PATH)):
                assistantindicator('mute')
            if (configuration['Wakewords']['Ok_Google']=='Disabled' or os.path.isfile("{}/.mute".format(USER_PATH))):
                self.assistant.set_mic_mute(True)
            if custom_wakeword:
                self.t1.start()

        if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
            self.can_start_conversation = False
            subprocess.Popen(["aplay", "{}/sample-audio-files/Fb.wav".format(ROOT_PATH)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if kodicontrol:
                status=mutevolstatus()
                vollevel=status[1]
                with open('{}/.volume.json'.format(USER_PATH), 'w') as f:
                       json.dump(vollevel, f)
                kodi.Application.SetVolume({"volume": 0})
            if GPIOcontrol:
                assistantindicator('listening')
            if vlcplayer.is_vlc_playing():
                if os.path.isfile("{}/.mediavolume.json".format(USER_PATH)):
                    vlcplayer.set_vlc_volume(15)
                else:
                    currentvolume=vlcplayer.get_vlc_volume()
                    print(currentvolume)
                    with open('{}/.mediavolume.json'.format(USER_PATH), 'w') as vol:
                       json.dump(currentvolume, vol)
                    vlcplayer.set_vlc_volume(15)
            print()

        if (event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT or event.type == EventType.ON_NO_RESPONSE):
            self.can_start_conversation = True
            if GPIOcontrol:
                assistantindicator('off')
            if kodicontrol:
                with open('{}/.volume.json'.format(USER_PATH), 'r') as f:
                       vollevel = json.load(f)
                       kodi.Application.SetVolume({"volume": vollevel})

            if (configuration['Wakewords']['Ok_Google']=='Disabled' or os.path.isfile("{}/.mute".format(USER_PATH))):
                  self.assistant.set_mic_mute(True)
            if os.path.isfile("{}/.mute".format(USER_PATH)):
                if GPIOcontrol:
                    assistantindicator('mute')
            if vlcplayer.is_vlc_playing():
                with open('{}/.mediavolume.json'.format(USER_PATH), 'r') as vol:
                    oldvolume = json.load(vol)
                vlcplayer.set_vlc_volume(int(oldvolume))

        if (event.type == EventType.ON_RESPONDING_STARTED and event.args and not event.args['is_error_response']):
            if GPIOcontrol:
                assistantindicator('speaking')

        if event.type == EventType.ON_RESPONDING_FINISHED:
            if GPIOcontrol:
                assistantindicator('off')

        if event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED:
            if GPIOcontrol:
                assistantindicator('off')

        print(event)

        if (event.type == EventType.ON_CONVERSATION_TURN_FINISHED and
                event.args and not event.args['with_follow_on_turn']):
            self.can_start_conversation = True
            if GPIOcontrol:
                assistantindicator('off')
            if (configuration['Wakewords']['Ok_Google']=='Disabled' or os.path.isfile("{}/.mute".format(USER_PATH))):
                self.assistant.set_mic_mute(True)
            if os.path.isfile("{}/.mute".format(USER_PATH)):
                if GPIOcontrol:
                    assistantindicator('mute')
            if kodicontrol:
                with open('{}/.volume.json'.format(USER_PATH), 'r') as f:
                       vollevel = json.load(f)
                       kodi.Application.SetVolume({"volume": vollevel})

            if vlcplayer.is_vlc_playing():
                with open('{}/.mediavolume.json'.format(USER_PATH), 'r') as vol:
                    oldvolume= json.load(vol)
                vlcplayer.set_vlc_volume(int(oldvolume))
            print()

        if event.type == EventType.ON_DEVICE_ACTION:
            for command, params in event.actions:
                print('Do command', command, 'with params', str(params))


    def register_device(self,project_id, credentials, device_model_id, device_id):
        """Register the device if needed.
        Registers a new assistant device if an instance with the given id
        does not already exists for this model.
        Args:
           project_id(str): The project ID used to register device instance.
           credentials(google.oauth2.credentials.Credentials): The Google
                    OAuth2 credentials of the user to associate the device
                    instance with.
           device_model_id: The registered device model ID.
           device_id: The device ID of the new instance.
        """
        base_url = '/'.join([DEVICE_API_URL, 'projects', project_id, 'devices'])
        device_url = '/'.join([base_url, device_id])
        session = google.auth.transport.requests.AuthorizedSession(credentials)
        r = session.get(device_url)
        print(device_url, r.status_code)
        if r.status_code == 404:
            print('Registering....')
            r = session.post(base_url, data=json.dumps({
                'id': device_id,
                'model_id': device_model_id,
                'client_type': 'SDK_LIBRARY'
            }))
            if r.status_code != 200:
                raise Exception('failed to register device: ' + r.text)
            print('\rDevice registered.')


    def detected(self):
        if self.can_start_conversation == True:
            self.assistant.set_mic_mute(False)
            self.assistant.start_conversation()
            print('Assistant is listening....')

    def start_detector(self):
        self.detector.start(detected_callback=self.callbacks,
            interrupt_check=self.interrupt_callback,
            sleep_time=0.03)

    def main(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('--device-model-id', '--device_model_id', type=str,
                            metavar='DEVICE_MODEL_ID', required=False,
                            help='the device model ID registered with Google')
        parser.add_argument('--project-id', '--project_id', type=str,
                            metavar='PROJECT_ID', required=False,
                            help='the project ID used to register this device')
        parser.add_argument('--device-config', type=str,
                            metavar='DEVICE_CONFIG_FILE',
                            default=os.path.join(
                                os.path.expanduser('~/.config'),
                                'googlesamples-assistant',
                                'device_config_library.json'
                            ),
                            help='path to store and read device configuration')
        parser.add_argument('--credentials', type=existing_file,
                            metavar='OAUTH2_CREDENTIALS_FILE',
                            default=os.path.join(
                                os.path.expanduser('~/.config'),
                                'google-oauthlib-tool',
                                'credentials.json'
                            ),
                            help='path to store and read OAuth2 credentials')
        parser.add_argument('-v', '--version', action='version',
                            version='%(prog)s ' + Assistant.__version_str__())

        args = parser.parse_args()
        with open(args.credentials, 'r') as f:
            credentials = google.oauth2.credentials.Credentials(token=None,
                                                                **json.load(f))

        device_model_id = None
        last_device_id = None
        try:
            with open(args.device_config) as f:
                device_config = json.load(f)
                device_model_id = device_config['model_id']
                last_device_id = device_config.get('last_device_id', None)
        except FileNotFoundError:
            pass

        if not args.device_model_id and not device_model_id:
            raise Exception('Missing --device-model-id option')

        # Re-register if "device_model_id" is given by the user and it differs
        # from what we previously registered with.
        should_register = (
            args.device_model_id and args.device_model_id != device_model_id)

        device_model_id = args.device_model_id or device_model_id
        with Assistant(credentials, device_model_id) as assistant:
            self.assistant = assistant
            subprocess.Popen(["aplay", "{}/sample-audio-files/Startup.wav".format(ROOT_PATH)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            events = assistant.start()
            device_id = assistant.device_id
            print('device_model_id:', device_model_id)
            print('device_id:', device_id + '\n')

            # Re-register if "device_id" is different from the last "device_id":
            if should_register or (device_id != last_device_id):
                if args.project_id:
                    register_device(args.project_id, credentials,
                                    device_model_id, device_id)
                    pathlib.Path(os.path.dirname(args.device_config)).mkdir(
                        exist_ok=True)
                    with open(args.device_config, 'w') as f:
                        json.dump({
                            'last_device_id': device_id,
                            'model_id': device_model_id,
                        }, f)
                else:
                    print(WARNING_NOT_REGISTERED)

            for event in events:
                self.process_event(event)
                usrcmd=event.args
                if custom_action(usrcmd,'armv7'):
                    assistant.stop_conversation()


        if custom_wakeword:
            self.detector.terminate()


if __name__ == '__main__':
    try:
        Myassistant().main()
    except Exception as error:
        logger.exception(error)
