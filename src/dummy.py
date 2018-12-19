#-*- coding: utf-8 -*-

import struct
import time
import bluetooth
import pexpect
import subprocess
import sys

_DIRECT_COMMAND_REPLY     = b'\x00'
_DIRECT_COMMAND_NO_REPLY  = b'\x80'

opOutput_Stop             = b'\xA3'
opOutput_Power            = b'\xA4'
opOutput_Speed            = b'\xA5'
opOutput_Start            = b'\xA6'
opSound                   = b'\x94'

cmdTone                   = b'\x01'

PORT_1                    = b'\x00'
PORT_2                    = b'\x01'
PORT_3                    = b'\x02'
PORT_4                    = b'\x03'
PORT_A_SENSOR             = b'\x10'
PORT_B_SENSOR             = b'\x11'
PORT_C_SENSOR             = b'\x12'
PORT_D_SENSOR             = b'\x13'

PORT_A                    = 1
PORT_B                    = 2
PORT_C                    = 4
PORT_D                    = 8
PORTS_ALL                 = 15

class Bluetoothctl:
    def __init__(self):
        print("Bluetoothctl __init__")

    def get_output(self, command, pause = 0):
        print("Bluetoothctl get_output(",command,pause,")")
        
        return ""

    def pair(self, mac_address):
        print("Bluetoothctl pair(",mac_address,")")
        
        return True

class EV3():
    def __init__(self):
        print("EV3 __init__")

    def __del__(self):
        print("EV3 __del__")

    def send_direct_cmd(self, ops: bytes, local_mem: int=0, global_mem: int=0):
        print("EV3 send_direct_cmd(",ops,local_mem,global_mem,")")

    def LCX(self, value: int) -> bytes:
        """create a LC0, LC1, LC2, LC4, dependent from the value"""
        if   value >=    -32 and value <      0:
            return struct.pack('b', 0x3F & (value + 64))
        elif value >=      0 and value <     32:
            return struct.pack('b', value)
        elif value >=   -127 and value <=   127:
            return b'\x81' + struct.pack('<b', value)
        elif value >= -32767 and value <= 32767:
            return b'\x82' + struct.pack('<h', value)
        else:
            return b'\x83' + struct.pack('<i', value)

    def move(self, speed: int, port) -> None:
        print("EV3 move(",speed,port,")")

    def stop(self) -> None:
        print("EV3 stop")

    def tone(self, vol, hz, time):
        print("EV3 move(",vol,hz,time,")")

    def find_device(self):
        print("EV3 find_device")
