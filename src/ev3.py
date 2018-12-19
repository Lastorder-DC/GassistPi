#-*- coding: utf-8 -*-

import struct
import time
import bluetooth
import pexpect
import subprocess
import sys
import socket

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
        out = subprocess.check_output("sudo rfkill unblock bluetooth", shell = True)
        self.child = pexpect.spawn("bluetoothctl", echo = False, encoding='utf-8')
        self.get_output("pairable on",1)
        self.get_output("agent NoInputNoOutput",1)
        self.get_output("default-agent",1)
        self.get_output("scan on")

    def get_output(self, command, pause = 0):
        """Run a command in bluetoothctl prompt, return output as a list of lines."""
        self.child.send(command + "\n")
        time.sleep(pause)
        start_failed = self.child.expect(["bluetooth", pexpect.EOF])

        if start_failed:
            raise BluetoothctlError("Bluetoothctl failed after running " + command)
        return self.child.before.split("\r\n")

    def pair(self, mac_address):
        """Try to pair with a device by mac address."""
        try:
            print("Try to pair with ",mac_address)
            out = self.get_output("pair " + mac_address, 10)
            print(out)
        except BluetoothctlError as e:
            print(e)
            return None
        else:
            res = self.child.expect(["Failed to pair", "Request PIN code", pexpect.EOF])
            if res == 1:
                print("PIN should be 1234 in order to connect..")
                out = self.get_output("1234", 4)
            else:
                return False

            res = self.child.expect(["Failed to pair", "Pairing successful", pexpect.EOF])
            if res == 1:
                print("Pairing is done!")
                return True
            else:
                print("Pairing failed...")
                return False

class EV3():
    def __init__(self):
        print("Connecting to nearby EV3...")
        retry_cnt = 0
        while True:
            found = 0
            num = 0
            nearby_devices=bluetooth.discover_devices(duration=15)
            for i in nearby_devices:
                print(i)
                if bluetooth.lookup_name(i) == 'MyEV3':
                    self.addr = nearby_devices[num]
                    found = 1
                else:
                    if nearby_devices[num][0:8] == '00:16:53' and found==0:
                        self.addr = nearby_devices[num]
                        found = 1
                num += 1

            if found == 1:
                print('You have selected', bluetooth.lookup_name(self.addr))
                try:
                    bl=Bluetoothctl()
                    bl.pair(self.addr)
                    print('Connect Success')
                    break
                    
                except bluetooth.btcommon.BluetoothError as err:
                    print('Not Connect')
                    pass
            else:
                retry_cnt = retry_cnt + 1
                print("EV3 not found. retrying... (",retry_cnt," / ?)")
        self._sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self._sock.connect((self.addr, 1))
        print('socket connected!')

    def __del__(self):
        try:
            if isinstance(self._sock, bluetooth.BluetoothSocket):
                self._sock.close()
        except AttributeError:
            print("Socket was not opened, ignore close")

    def send_direct_cmd(self, ops: bytes, local_mem: int=0, global_mem: int=0) -> bytes:
        cmd = b''.join([
            struct.pack('<h', len(ops) + 5),
            struct.pack('<h', 42),
            _DIRECT_COMMAND_REPLY,
            struct.pack('<h', local_mem*1024 + global_mem),
            ops
        ])
        self._sock.send(cmd)
        #print('Sent', cmd)
        reply = self._sock.recv(5 + global_mem)
        #print('Recv', reply)
        return reply


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
        ops = b''
        if port & PORT_A != 0:
            ops = ops + b''.join([
                opOutput_Speed,
                self.LCX(0),
                self.LCX(PORT_A),
                self.LCX(speed)
            ])

        if port & PORT_B != 0:
            ops = ops + b''.join([
                opOutput_Speed,
                self.LCX(0),
                self.LCX(PORT_B),
                self.LCX(speed)
            ])

        if port & PORT_C != 0:
            ops = ops + b''.join([
                opOutput_Speed,
                self.LCX(0),
                self.LCX(PORT_C),
                self.LCX(speed)
            ])

        if port & PORT_D != 0:
            ops = ops + b''.join([
                opOutput_Speed,
                self.LCX(0),
                self.LCX(PORT_D),
                self.LCX(speed)
            ])

        ops = ops + b''.join([
            opOutput_Start,
            self.LCX(0),
            self.LCX(port)
        ])
        self.send_direct_cmd(ops)

    def stop(self) -> None:
        ops = b''.join([
            opOutput_Stop,
            self.LCX(0),
            self.LCX(PORT_A + PORT_B + PORT_C + PORT_D),
            self.LCX(0)
        ])
        self.send_direct_cmd(ops)

    def tone(self, vol, hz, time):
        ops = b''.join([
            opSound,
            cmdTone,
            self.LCX(vol),    # VOLUME
            self.LCX(hz),  # FREQUENCY
            self.LCX(time), # DURATION
        ])
        self.send_direct_cmd(ops)

    def executeCmd(cmd):
        print("Command executed -", cmd)
        if cmd == "Forward":
            self.move(FORWARD,PORT_A+PORT_D)
        elif cmd == "Backward":
            self.move(BACKWARD,PORT_A+PORT_D)
        elif cmd == "Left":
            self.move(FORWARD,PORT_A)
            self.move(BACKWARD,PORT_D)
        elif cmd == "Right":
            self.move(BACKWARD,PORT_A)
            self.move(FORWARD,PORT_D)
        elif cmd == "Stop":
            self.stop()

    def find_device(self):
        # Return address once the first EV3 device found
        try:
            nearby_devices = bluetooth.discover_devices(duration=10, lookup_names=True)
        except bluetooth.BluetoothError as e:
            #print("BT ERROR", e)
            return None
        except UnicodeDecodeError as e:
            #print("Unexpected Unicode Error!", e)
            return None

        for addr, name in nearby_devices:
            print(addr, name)
            if name is not None and name.startswith("MicEV3"):
                #print("Found!", addr, name)
                self.addr = addr
                break
        self.discovery_once = True
        return self.addr



if __name__=="__main__":

    #devices = bluetooth.discover_devices(duration=3, lookup_names=True)
    #addr ='00:16:53:50:5B:E1'

    ev3 = EV3()
    ports = [0,0,0,0]
    port = 0
    key = ''
    power = 0
    while True:
        print("> ", end='')
        key = input()
        if key == 't':
            ev3.tone(1,440,1000)
        elif key =='w':
            power += 10
        elif key == 's':
            power -= 10
        elif key == 'z':
            power = 0
        elif key == 'a':
            if ports[0] == 1:
                ports[0] = 0
                print("Port A disabled.")
            else:
                ports[0] = 1
                print("Port A enabled.")
            #continue
        elif key == 'b':
            if ports[1] == 1:
                ports[1] = 0
                print("Port B disabled.")
            else:
                ports[1] = 1
                print("Port B enabled.")
            #continue
        elif key == 'c':
            if ports[2] == 1:
                ports[2] = 0
                print("Port C disabled.")
            else:
                ports[2] = 1
                print("Port C enabled.")
            #continue
        elif key == 'd':
            if ports[3] == 1:
                ports[3] = 0
                print("Port D disabled.")
            else:
                ports[3] = 1
                print("Port D enabled.")
            #continue
        elif key=='q':
            ev3.stop()
            break
        port = ports[3] * PORT_D + ports[2] * PORT_C + ports[1] * PORT_B + ports[0] * PORT_A
        print("PORT A - ",ports[0]," PORT B - ",ports[1]," PORT C - ",ports[2]," PORT D - ",ports[3]," SPEED - ",power)
        if port == 0:
            print("No ports enabled - Nothing sent.")
            continue
        else:
            ev3.move(power, 0, port)
