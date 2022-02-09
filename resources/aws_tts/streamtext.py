# -*- coding: utf-8 -*-
import freeswitch
import os
import sys
import importlib
import configparser

try:
	class G:
		config = configparser.ConfigParser()
		try:
			with open( '/etc/itas/ace/aws.ini', 'r' ) as f:
				config.read_file( f )
		except Exception as e1:
			freeswitch.consoleLog( 'err', f'Could not load aws.ini: {e1!r}' )
			sys.exit( -1 )
		aws_access_key = config['aws']['aws_access_key']
		aws_secret_key = config['aws']['aws_secret_key']
		aws_region_name = config['aws']['aws_region_name']
		tts_location = config['aws']['tts_location']
		tts_default_voice = config['aws']['tts_default_voice']
except Exception as e:
	freeswitch.consoleLog( 'err', repr( e ))
	sys.exit( -1 )

def ttsgen(text, voice):
	import polly
	importlib.reload(polly) # If a change is made to polly, it won't reload in FreeSWITCH unless this is done. Comes with a small performance hit.
	from polly import AWSPolly
	polly_voice = AWSPolly(
		G.aws_access_key,
		G.aws_secret_key,
		G.aws_region_name
	)
	
	ssml_text = f"<speak><prosody rate=\"-5%\">{text}</prosody></speak>"
	result, fname = polly_voice.genspeech(
		ssml_text,
		voice,
		G.tts_location
	)
	if not result:
		freeswitch.consoleLog(
			"err",
			f"Unable to generate text to speech: {fname}"
		)
		return "null.wav"
	else:
		return fname


def fsapi(session, stream, env, args):
	argsarr = args.split("|")
	if len(argsarr) < 1 or len(argsarr) > 2:
		freeswitch.consoleLog(
			"err",
			"Invalid arguments specified. Use: voice=Joanna|text=\"This is text to speech.\"\n"
		)
		return 1
	arg0 = argsarr[0].split("=", 1)
	if len(argsarr) == 2:
		arg1 = argsarr[1].split("=", 1)
	else:
		if arg0[0] != 'text': #This means only one arg was passed, and it wasn't text
			freeswitch.consoleLog(
				"err",
				"Invalid arguments specified. Use: voice=Joanna|text=\"This is text to speech.\"\n"
			)
			return 1
		else:
			arg1 = ['voice', G.tts_default_voice]
	argsdict = {
		arg0[0]: arg0[1],
		arg1[0]: arg1[1]
	}
	if not os.path.exists(G.tts_location):
		try:
			os.makedirs(G.tts_location, exist_ok=True)
		except Exception as e:
			print(f'Unable to create text to speech cache folder: {e}')
			return 1
	if 'voice' in argsdict and 'text' in argsdict:
		stream.write(
			ttsgen(
				argsdict['text'],
				argsdict['voice']
			)
		)
		return 0
	else:
		freeswitch.consoleLog(
			"err",
			"Invalid arguments specified. Use: voice=Joanna|text=\"This is text to speech.\"\n"
		)
		return 1
