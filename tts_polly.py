# -*- coding: utf-8 -*-

# stdlib imports:
import asyncio
import configparser
import importlib
import logging
import os
from pathlib import Path
from typing import cast, List, Optional as Opt, Union
from typing_extensions import Literal
import sys

# local imports:
import polly
from polly import AWS_POLLY_VOICES, aws_polly_voices

logger = logging.getLogger( __name__ )

class TTS:
	aws_access_key: str
	aws_secret_key: str
	aws_region_name: str
	tts_location: Path
	tts_default_voice: AWS_POLLY_VOICES
	
	def __init__( self, voice: Opt[str] = None ) -> None:
		voice = voice or self.tts_default_voice
		assert voice in aws_polly_voices, f'invalid or unrecognized voice={voice!r}'
		self.voice: AWS_POLLY_VOICES = cast( AWS_POLLY_VOICES, voice )
		
		self.text: List[str] = []
	
	def say( self, text: str ) -> None:
		self.text.append( text )
	
	def digits( self, digits: Union[int,str] ) -> None:
		self.say( f'<say-as interpret-as="digits">{digits}</say-as>' )
	
	async def generate( self ) -> Path:
		log = logger.getChild( 'TTS.generate' )
		x = polly.AWSPolly(
			aws_access_key = self.aws_access_key,
			aws_secret_key = self.aws_secret_key,
			aws_region_name = self.aws_region_name,
		)
		
		text = ' '.join( self.text )
		ssml_text = f'<speak><prosody rate="-5%">{text}</prosody></speak>'
		log.debug( 'ssml_text=%r', ssml_text )
		
		loop = asyncio.get_running_loop()
		path = await loop.run_in_executor( None,
			lambda: x.genspeech( ssml_text, self.voice, self.tts_location )
		)
		return path
