# -*- coding: utf-8 -*-
"""
	__init__
	A library to get text to speech from AWS cloud engine.
"""

import hashlib
import os


class AWSPolly(object):
	"""
	Implements API for Amazon Polly Cloud TTS service
	"""

	def __init__(self, aws_access_key, aws_secret_key, aws_region_name):
		self.aws_access_key = aws_access_key
		self.aws_secret_key = aws_secret_key
		self.aws_region_name = aws_region_name
		self.output_format = 'pcm'
		self.sample_rate = '8000'
		self.text_type = 'ssml'
		self.channels = 1
		self.sampwidth = 2


	def genspeech(self, text, voice, recpath):
		namestr = f"polly-{text}-{voice}"
		fhash = hashlib.sha224(
			namestr.encode('utf-8')
		).hexdigest()
		fname = f"{fhash}.wav"
		filename = os.path.join(
			recpath,
			fname
		)
		if not os.path.isdir(recpath):
			os.mkdir(
				recpath,
				755
			)
		if os.path.isfile(filename):
			return [True, filename]
		import boto3 # pip install boto3
		import wave
		polly_client = boto3.client(
			'polly',
			aws_access_key_id = self.aws_access_key,
			aws_secret_access_key = self.aws_secret_key,
			region_name = self.aws_region_name
		)
		polly_response = polly_client.synthesize_speech(
			VoiceId = voice,
			OutputFormat = self.output_format,
			SampleRate = self.sample_rate,
			TextType = self.text_type,
			Text = text
		)
		wavframes = polly_response['AudioStream'].read()
		try:
			waveout = wave.open(filename, 'wb')
			waveout.setnchannels(self.channels)
			waveout.setsampwidth(self.sampwidth)
			waveout.setframerate(int(self.sample_rate))
			waveout.setnframes(0)
			waveout.setcomptype('NONE', 'NONE')
			waveout.writeframesraw(wavframes)
			waveout.close()
			return [True, filename]
		except (Exception) as e:
			return [False, e]
