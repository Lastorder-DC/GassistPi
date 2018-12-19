#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Example 2: STT - getVoice2Text """

from __future__ import print_function

import grpc

import gigagenieRPC_pb2
import gigagenieRPC_pb2_grpc

from ev3 import EV3

import os
import datetime
import hmac
import hashlib
from time import sleep

import pyaudio
import audioop
from six.moves import queue
import wave

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 512

# Config for GiGA Genie gRPC
CLIENT_ID = 'Y2xpZW50X2lkMTUzOTMyNTQ5NzY3MQ=='
CLIENT_KEY = 'Y2xpZW50X2tleTE1MzkzMjU0OTc2NzE='
CLIENT_SECRET = 'Y2xpZW50X3NlY3JldDE1MzkzMjU0OTc2NzE='
HOST = 'gate.gigagenie.ai'
PORT = 4080

PORT_A					= 1
PORT_B					= 2
PORT_C					= 4
PORT_D					= 8
PORTS_ALL			= 15
FORWARD				= 20
BACKWARD			= -20

ev3 = None

### COMMON : Client Credentials ###
def getMetadata():
	timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
	message = CLIENT_ID + ':' + timestamp

	signature = hmac.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

	metadata = [('x-auth-clientkey', CLIENT_KEY),
				('x-auth-timestamp', timestamp),
				('x-auth-signature', signature)]

	return metadata

def credentials(context, callback):
	callback(getMetadata(), None)

def getCredentials():
	with open('../data/ca-bundle.pem', 'rb') as f:
		trusted_certs = f.read()
	sslCred = grpc.ssl_channel_credentials(root_certificates=trusted_certs)

	authCred = grpc.metadata_call_credentials(credentials)

	return grpc.composite_channel_credentials(sslCred, authCred)

### END OF COMMON ###

### STT
# MicrophoneStream - original code in https://goo.gl/7Xy3TT
class MicrophoneStream(object):
	"""Opens a recording stream as a generator yielding the audio chunks."""
	def __init__(self, rate, chunk):
		self._rate = rate
		self._chunk = chunk

		# Create a thread-safe buffer of audio data
		self._buff = queue.Queue()
		self.closed = True

	def __enter__(self):
		self._audio_interface = pyaudio.PyAudio()
		self._audio_stream = self._audio_interface.open(
			format=pyaudio.paInt16,
			channels=1, rate=self._rate,
			input=True, frames_per_buffer=self._chunk,
			# Run the audio stream asynchronously to fill the buffer object.
			# This is necessary so that the input device's buffer doesn't
			# overflow while the calling thread makes network requests, etc.
			stream_callback=self._fill_buffer,
                        input_device_index=1
		)

		self.closed = False

		return self

	def __exit__(self, type, value, traceback):
		self._audio_stream.stop_stream()
		self._audio_stream.close()
		self.closed = True
		# Signal the generator to terminate so that the client's
		# streaming_recognize method will not block the process termination.
		self._buff.put(None)
		self._audio_interface.terminate()

	def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
		"""Continuously collect data from the audio stream, into the buffer."""
		self._buff.put(in_data)
		return None, pyaudio.paContinue

	def generator(self):
		while not self.closed:
			# Use a blocking get() to ensure there's at least one chunk of
			# data, and stop iteration if the chunk is None, indicating the
			# end of the audio stream.
			chunk = self._buff.get()
			if chunk is None:
				return
			data = [chunk]

			# Now consume whatever other data's still buffered.
			while True:
				try:
					chunk = self._buff.get(block=False)
					if chunk is None:
						return
					data.append(chunk)
				except queue.Empty:
					break

			yield b''.join(data)
# [END audio_stream]

def print_rms(rms):
	out = ''
	for _ in range(int(round(rms/30))):
		out = out + '*'
	
	print (out)

def play_file(fname):
	# create an audio object
	wf = wave.open(fname, 'rb')
	p = pyaudio.PyAudio()
	chunk = 1024

	# open stream based on the wave object which has been input.
	stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
					channels=wf.getnchannels(),
					rate=wf.getframerate(),
					output=True)

	# read data (based on the chunk size)
	data = wf.readframes(chunk)

	# play stream (looping from beginning of file to the end)
	while len(data) > 0:
		# writing to the stream is what *actually* plays the sound.
		stream.write(data)
		data = wf.readframes(chunk)

		# cleanup stuff.
	stream.close()
	p.terminate() 

def generate_request():

	with MicrophoneStream(RATE, CHUNK) as stream:
		audio_generator = stream.generator()
	
		for content in audio_generator:
			message = gigagenieRPC_pb2.reqVoice()
			message.audioContent = content
			yield message
			
			rms = audioop.rms(content,2)
			#print_rms(rms)

def getVoice2Text():	
	global ev3
	print ("Ctrl+\ to quit ...")
	while 1:
		channel = grpc.secure_channel('{}:{}'.format(HOST, PORT), getCredentials())
		stub = gigagenieRPC_pb2_grpc.GigagenieStub(channel)
		request = generate_request()
		resultText = ''
		for response in stub.getVoice2Text(request):
			if response.resultCd == 200: # partial
				#print('resultCd=%d | recognizedText= %s' 
				#	  % (response.resultCd, response.recognizedText))
				resultText = response.recognizedText
				if resultText.find("앞") != -1 or resultText.find("뒤") != -1 or resultText.find("전진") != -1 or resultText.find("후진") != -1 or resultText.find("오른") != -1 or resultText.find("왼") != -1 or resultText.find("멈춰") != -1 or resultText.find("정지") != -1:
					break
			elif response.resultCd == 201: # final
				#print('resultCd=%d | recognizedText= %s' 
				#	  % (response.resultCd, response.recognizedText))
				resultText = response.recognizedText
				break
			else:
				#print('resultCd=%d | recognizedText= %s' 
				#	  % (response.resultCd, response.recognizedText))
				break
		print ("TEXT: %s" % (resultText))
		if resultText.find("앞") != -1 or resultText.find("전진") != -1:
			print("앞으로")
			ev3.stop()
			sleep(0.2)
			ev3.move(FORWARD,PORT_A+PORT_D)
			sleep(1.5)
			ev3.stop()
			sleep(0.2)
		elif resultText.find("뒤") != -1 or resultText.find("후진") != -1:
			print("뒤로")
			ev3.stop()
			sleep(0.2)
			ev3.move(BACKWARD,PORT_A+PORT_D)
			sleep(1.5)
			ev3.stop()
			sleep(0.2)
		elif not resultText.find("오른") == -1:
			print("오른쪽으로")
			ev3.stop()
			sleep(0.2)
			ev3.move(FORWARD,PORT_A)
			ev3.move(BACKWARD,PORT_D)
			sleep(0.75)
			ev3.stop()
			sleep(0.2)
		elif not resultText.find("왼") == -1:
			print("왼쪽으로")
			ev3.stop()
			sleep(0.2)
			ev3.move(BACKWARD,PORT_A)
			ev3.move(FORWARD,PORT_D)
			sleep(0.75)
			ev3.stop()
			sleep(0.2)
		elif resultText.find("멈춰") != -1 or resultText.find("정지") != -1:
			print("정지")
			ev3.stop()
			sleep(0.2)
	return resultText

def main():
	global ev3
	ev3 = EV3()
	play_file("../data/sample_sound.wav")
	# STT
	text = getVoice2Text()

if __name__ == '__main__':
	main()
