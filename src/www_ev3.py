PORT_A                    = 1
PORT_B                    = 2
PORT_C                    = 4
PORT_D                    = 8
PORTS_ALL                 = 15
FORWARD                   = 20
BACKWARD                  = -20
TURN                      = 8

from ev3 import EV3
from flask import Flask
wwwapp = Flask(__name__)

ev3 = EV3()

@wwwapp.route("/")
def rootpage():
    return "VoiceModule v0.1 by Robogram!"

@wwwapp.route("/forward")
def cmd_forward():
    try:
        ev3.move(FORWARD,PORT_A+PORT_D)
    except Exception:
        return "Failure"
    return "Success"

@wwwapp.route("/backward")
def cmd_backward():
    try:
        ev3.move(BACKWARD,PORT_A+PORT_D)
    except Exception:
        return "Failure"
    return "Success"

@wwwapp.route("/stop")
def cmd_stop():
    try:
        ev3.stop()
    except Exception:
        return "Failure"
    return "Success"

@wwwapp.route("/left")
def cmd_left():
    try:
        ev3.move(FORWARD - TURN,PORT_A)
        ev3.move(BACKWARD + TURN,PORT_D)
    except Exception:
        return "Failure"
    return "Success"

@wwwapp.route("/right")
def cmd_right():
    try:
        ev3.move(BACKWARD + TURN,PORT_A)
        ev3.move(FORWARD - TURN,PORT_D)
    except Exception:
        return "Failure"
    return "Success"
    
if __name__ == '__main__':
    wwwapp.run(host='0.0.0.0', port=8088)
