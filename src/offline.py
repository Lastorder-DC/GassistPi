import snowboydecoder
import sys
import signal
import requests
from time import sleep
from espeakng import ESpeakNG
esng                      = ESpeakNG()
esng.voice                = 'korean'
interrupted               = False
is_quit                   = False

def executeCmd(cmd):
    global interrupted
    global esng
    print("Command executed -", cmd)
    try:
        if cmd == "Abort":
            requests.get("http://127.0.0.1:8088/stop?key=r0bogram")
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DONG)
            interrupted = True
        elif cmd == "Forward":
            requests.get("http://127.0.0.1:8088/forward?key=r0bogram")
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
        elif cmd == "Backward":
            requests.get("http://127.0.0.1:8088/backward?key=r0bogram")
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
        elif cmd == "Left":
            requests.get("http://127.0.0.1:8088/left?key=r0bogram")
            sleep(0.75)
            requests.get("http://127.0.0.1:8088/stop?key=r0bogram")
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
        elif cmd == "Right":
            requests.get("http://127.0.0.1:8088/right?key=r0bogram")
            sleep(0.75)
            requests.get("http://127.0.0.1:8088/stop?key=r0bogram")
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
        elif cmd == "Stop":
            requests.get("http://127.0.0.1:8088/stop?key=r0bogram")
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
    except Exception:
        #esng.say("연결 오류")
        snowboydecoder.play_audio_file(snowboydecoder.DETECT_DONG)

def signal_handler(signal, frame):
    global interrupted
    global is_quit
    interrupted = True
    is_quit = True

def interrupt_callback():
    global interrupted
    return interrupted

def quit_detect():
    global interrupted
    
    interrupted = True

def quit_all():
    global interrupted
    global is_quit
    
    interrupted = True
    is_quit = True

def main():
    global interrupted
    global is_quit

    snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
    while True:
        models = ["resources/heyrobo.pmdl","resources/abort.pmdl"]
        sensitivity = [0.5]*len(models)
        detector = snowboydecoder.HotwordDetector(models, sensitivity=sensitivity)
        callbacks = [lambda: quit_detect(),
                     lambda: quit_detect()]

        detector.start(detected_callback=callbacks,
                       interrupt_check=interrupt_callback,
                       sleep_time=0.03)
        
        #quit if aborted here
        if is_quit:
            snowboydecoder.play_audio_file(snowboydecoder.DETECT_DONG)
            break;
        else:
            interrupted = False
        
        models = ["resources/forward.pmdl","resources/backward.pmdl","resources/left.pmdl","resources/right.pmdl","resources/stop.pmdl","resources/abort.pmdl"]

        # capture SIGINT signal, e.g., Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)

        sensitivity = [0.5]*len(models)
        detector = snowboydecoder.HotwordDetector(models, sensitivity=sensitivity)
        callbacks = [lambda: executeCmd("Forward"),
                     lambda: executeCmd("Backward"),
                     lambda: executeCmd("Left"),
                     lambda: executeCmd("Right"),
                     lambda: executeCmd("Stop"),
                     lambda: executeCmd("Abort")]

        snowboydecoder.play_audio_file(snowboydecoder.DETECT_DING)
        print('Listening... Press Ctrl+C to exit')

        # main loop
        # make sure you have the same numbers of callbacks and models
        detector.start(detected_callback=callbacks,
                       interrupt_check=interrupt_callback,
                       sleep_time=0.03)
        print("Heyrobo aborted")
        interrupted = False
        
    detector.terminate()
