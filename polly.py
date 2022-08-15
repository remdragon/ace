# -*- coding: utf-8 -*-
"""
	__init__
	A library to get text to speech from AWS cloud engine.
"""

# stdlib imports:
import hashlib
import logging
import os
from pathlib import Path
from typing_extensions import Final, Literal
import wave

# 3rd-party imports:
import boto3 # pip install boto3

logger = logging.getLogger( __name__ )

AWS_POLLY_VOICES = Literal['Aditi','Amy','Astrid','Bianca','Brian','Camila','Carla','Carmen','Celine','Chantal','Conchita','Cristiano','Dora','Emma','Enrique','Ewa','Filiz','Gabrielle','Geraint','Giorgio','Gwyneth','Hans','Ines','Ivy','Jacek','Jan','Joanna','Joey','Justin','Karl','Kendra','Kevin','Kimberly','Lea','Liv','Lotte','Lucia','Lupe','Mads','Maja','Marlene','Mathieu','Matthew','Maxim','Mia','Miguel','Mizuki','Naja','Nicole','Olivia','Penelope','Raveena','Ricardo','Ruben','Russell','Salli','Seoyeon','Takumi','Tatyana','Vicki','Vitoria','Zeina','Zhiyu','Aria','Ayanda','Arlet','Hannah','Arthur','Daniel','Liam','Pedro','Kajal']
aws_polly_voices =        ('Aditi','Amy','Astrid','Bianca','Brian','Camila','Carla','Carmen','Celine','Chantal','Conchita','Cristiano','Dora','Emma','Enrique','Ewa','Filiz','Gabrielle','Geraint','Giorgio','Gwyneth','Hans','Ines','Ivy','Jacek','Jan','Joanna','Joey','Justin','Karl','Kendra','Kevin','Kimberly','Lea','Liv','Lotte','Lucia','Lupe','Mads','Maja','Marlene','Mathieu','Matthew','Maxim','Mia','Miguel','Mizuki','Naja','Nicole','Olivia','Penelope','Raveena','Ricardo','Ruben','Russell','Salli','Seoyeon','Takumi','Tatyana','Vicki','Vitoria','Zeina','Zhiyu','Aria','Ayanda','Arlet','Hannah','Arthur','Daniel','Liam','Pedro','Kajal')

class AWSPolly:
	sample_rate: Final = '8000'
	"""
	Implements API for Amazon Polly Cloud TTS service
	"""

	def __init__( self, aws_access_key: str, aws_secret_key: str, aws_region_name: str ) -> None:
		self.aws_access_key = aws_access_key
		self.aws_secret_key = aws_secret_key
		self.aws_region_name = aws_region_name
		self.channels = 1
		self.sampwidth = 2
	
	def genspeech( self,
		text: str,
		voice: AWS_POLLY_VOICES,
		recpath: Path,
	) -> Path:
		log = logger.getChild( 'AWSPolly.genspeech' )
		namestr = f'polly-{text}-{voice}'
		fhash = hashlib.sha224(
			namestr.encode( 'utf-8' )
		).hexdigest()
		filename: Path = recpath / f'{fhash}.wav'
		if filename.is_file():
			log.debug( 'using cached filename=%r for text=%r', filename, text )
			return filename
		recpath.mkdir( mode = 755, parents = True, exist_ok = True )
		polly_client = boto3.client(
			'polly',
			aws_access_key_id = self.aws_access_key,
			aws_secret_access_key = self.aws_secret_key,
			region_name = self.aws_region_name
		)
		log.debug( 'requesting new tts content for text=%r', text )
		polly_response = polly_client.synthesize_speech(
			VoiceId = voice,
			OutputFormat = 'pcm',
			SampleRate = self.sample_rate,
			TextType = 'ssml',
			Text = text
		)
		wavframes = polly_response['AudioStream'].read()
		with wave.open( str( filename ), 'wb' ) as waveout:
			waveout.setnchannels( self.channels )
			waveout.setsampwidth( self.sampwidth )
			waveout.setframerate( int( self.sample_rate ))
			waveout.setnframes( 0 )
			waveout.setcomptype( 'NONE', 'NONE' )
			waveout.writeframesraw( wavframes )
		return filename
