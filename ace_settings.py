# stdlib imports:
from abc import ABCMeta, abstractmethod
import asyncio
from dataclasses import asdict, dataclass, Field, field
from flask import Response
import html
import json
import logging
from multiprocessing.synchronize import RLock as MPLock
from mypy_extensions import TypedDict
from pathlib import Path
from typing import (
	Any, cast, Dict, Generic, List, Optional as Opt, TypeVar, TYPE_CHECKING,
)
from typing_extensions import Literal # Python 3.7

# local imports:
from timed_lru_cache import timed_lru_cache
from tts import TTS, TTS_VOICES, tts_voices

logger = logging.getLogger( __name__ )

if TYPE_CHECKING:
	FIELD = Field[str]
else:
	FIELD = Field # Py37 doesn't support Field[...]

T = TypeVar( 'T' )
SettingsType = TypeVar( 'SettingsType', bound = 'Settings' )

g_settings_path: Path
g_lock: MPLock

class Editor( metaclass = ABCMeta ):
	def display( self, value: Any ) -> str:
		return str( value )
	
	@abstractmethod
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.get()' )
	
	def post( self, settings: SettingsType, fld: FIELD, data: Dict[str,Any] ) -> Any:
		return data.get( fld.name )

class BoolEditor( Editor ):
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		value: bool = getattr( settings, fld.name )
		checked = ' checked' if value else ''
		return f'<input type="checkbox" id="{fld.name}" name="{fld.name}" value="on"{checked}/>'
	
	def post( self, settings: SettingsType, fld: FIELD, data: Dict[str,Any] ) -> Any:
		#log = logger.getChild( 'BoolEdior.post' )
		posted = data.get( fld.name )
		#log.debug( 'posted=%r', posted )
		return posted == 'on'

class IntEditor( Editor ):
	def __init__( self, min: int, max: int ) -> None:
		self.min = min
		self.max = max
	
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		value: int = getattr( settings, fld.name )
		return f'<input type="number" id="{fld.name}" name="{fld.name}" step="1" min="{self.min}" max="{self.max}" value="{value}"/>'
	
	def post( self, settings: SettingsType, fld: FIELD, data: Dict[str,Any] ) -> Any:
		value = cast( str, data.get( fld.name ) or '' )
		try:
			return int( value )
		except ValueError:
			return None

class StrEditor( Editor ):
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		value = getattr( settings, fld.name )
		_value_ = html.escape( value, quote = True )
		return f'<input type="text" id="{fld.name}" name="{fld.name}" value="{_value_}"/>'

class PasswordEditor( Editor ):
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		return f'<input type="password" id="{fld.name}" name="{fld.name}"/>'

class ChoiceEditor( Editor ):
	def __init__( self, choices: List[str] ) -> None:
		self.choices = choices
	
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		value = getattr( settings, fld.name )
		options: List[str] = []
		for choice in self.choices:
			selected = ' selected' if value == choice else ''
			options.append( f'<option value="{html.escape(choice,quote=True)}"{selected}>{html.escape(choice)}</option>' )
		_options_ = '\n'.join( options )
		return f'<select id="{fld.name}" name="{fld.name}">{_options_}</select>'
	
	def post( self, settings: SettingsType, fld: FIELD, data: Dict[str,Any] ) -> Any:
		value = super().post( settings, fld, data )
		assert value in self.choices
		return value

class ListEditor( Editor ):
	def __init__( self, cols: int, rows: int ) -> None:
		self.cols = cols
		self.rows = rows
	
	def display( self, value: Any ) -> str:
		return ', '.join( value )
	
	def edit( self, settings: SettingsType, fld: FIELD ) -> str:
		value = getattr( settings, fld.name )
		lines = html.escape( '\n'.join( value ))
		return f'<textarea id="{fld.name}" name="{fld.name}" rows="{self.rows}" cols="{self.cols}">{lines}</textarea>'
	
	def post( self, settings: SettingsType, fld: FIELD, data: Dict[str,Any] ) -> Any:
		lines = data.get( fld.name ) or ''
		return list( filter( None, map( str.strip, lines.replace( '\r', '' ).split( '\n' ))))


class SettingMeta( TypedDict ):
	description: str
	editor: Editor

@dataclass
class Settings:
	did_categories: List[str] = field( default_factory = lambda: [ 'general', 'medical', 'shoes' ], metadata = SettingMeta(
		description = 'DID Categories',
		editor = ListEditor( rows = 10, cols = 20 ),
	))
	freeswitch_sounds: List[str] = field( default_factory = lambda: [ '/usr/share/freeswitch/sounds/en/us/callie' ], metadata = SettingMeta(
		description = 'FreeSWITCH Sound Sources',
		editor = ListEditor( rows = 10, cols = 80 ),
	))
	preannounce_path: str = field( default = '/usr/share/freeswitch/sounds/preannounce/', metadata = SettingMeta(
		description = 'PreAnnounce Recordings Path',
		editor = StrEditor(),
	))
	vm_min_pin_length: int = field( default = 4, metadata = SettingMeta(
		description = 'VM minimum PIN Length',
		editor = IntEditor( min = 1, max = 50 ),
	))
	vm_use_tts: bool = field( default = False, metadata = SettingMeta(
		description = 'VM use TTS',
		editor = BoolEditor(),
	))
	voice_deliver_ani: str = field( default = '', metadata = SettingMeta(
		description = 'Voice Delivery Caller-ID',
		editor = StrEditor(),
	))
	smtp_secure: Literal['no','starttls','yes'] = field( default = 'no', metadata = SettingMeta(
		description = 'SMTP Secure',
		editor = ChoiceEditor([ 'no', 'starttls', 'yes' ]),
	))
	smtp_host: str = field( default = '127.0.0.1', metadata = SettingMeta(
		description = 'SMTP Hostname',
		editor = StrEditor(),
	))
	smtp_port: int = field( default = 25, metadata = SettingMeta(
		description = 'SMTP Port',
		editor = IntEditor( min = 1, max = 65535 ),
	))
	smtp_timeout_seconds: int = field( default = 60, metadata = SettingMeta(
		description = 'SMTP Timeout (seconds)',
		editor = IntEditor( min = 1, max = 600 ),
	))
	smtp_username: str = field( default = '', metadata = SettingMeta(
		description = 'SMTP Username',
		editor = StrEditor(),
	))
	smtp_password: str = field( default = '', metadata = SettingMeta(
		description = 'SMTP Password',
		editor = PasswordEditor(),
	))
	smtp_email_from: str = field( default = '', metadata = SettingMeta(
		description = 'SMTP Email From',
		editor = StrEditor(),
	))
	sms_carrier: Literal['','thinq','twilio'] = field( default = '', metadata = SettingMeta(
		description = 'SMS Carrier',
		editor = ChoiceEditor([ '', 'thinq', 'twilio' ]),
	))
	sms_thinq_account: str = field( default = '', metadata = SettingMeta(
		description = 'SMS ThinQ Account',
		editor = StrEditor(),
	))
	sms_thinq_username: str = field( default = '', metadata = SettingMeta(
		description = 'SMS ThinQ User Name',
		editor = StrEditor(),
	))
	sms_thinq_api_token: str = field( default = '', metadata = SettingMeta(
		description = 'SMS ThinQ API Token',
		editor = StrEditor(),
	))
	sms_thinq_from: str = field( default = '', metadata = SettingMeta(
		description = 'SMS ThinQ From SMS #',
		editor = StrEditor(),
	))
	sms_twilio_sid: str = field( default = '', metadata = SettingMeta(
		description = 'SMS Twilio SID',
		editor = StrEditor(),
	))
	sms_twilio_token: str = field( default = '', metadata = SettingMeta(
		description = 'SMS Twilio Token',
		editor = StrEditor(),
	))
	sms_twilio_from: str = field( default = '', metadata = SettingMeta(
		description = 'SMS Twilio From SMS #',
		editor = StrEditor(),
	))
	tts_aws_access_key: str = field( default = '', metadata = SettingMeta(
		description = 'TTS AWS Access Key',
		editor = StrEditor(),
	))
	tts_aws_secret_key: str = field( default = '', metadata = SettingMeta(
		description = 'TTS AWS Secret Key',
		editor = StrEditor(),
	))
	tts_aws_region_name: str = field( default = '', metadata = SettingMeta(
		description = 'TTS AWS Region Name',
		editor = StrEditor(),
	))
	tts_aws_cache_location: str = field( default = '/var/lib/freeswitch/tts/', metadata = SettingMeta(
		description = 'TTS AWS Cache Location',
		editor = StrEditor(),
	))
	tts_aws_default_voice: TTS_VOICES = field( default = 'Joanna', metadata = SettingMeta(
		description = 'TTS AWS Default Voice',
		editor = ChoiceEditor( list( tts_voices )),
	))
	motd: str = field( default = "Don't Panic!", metadata = SettingMeta(
		description = 'MOTD',
		editor = StrEditor(),
	))
	
	def tts( self, voice: Opt[str] = None ) -> TTS:
		return TTS(
			self.tts_aws_access_key,
			self.tts_aws_secret_key,
			self.tts_aws_region_name,
			Path( self.tts_aws_cache_location ),
			self.tts_aws_default_voice,
			voice,
		)

def init( settings_path: Path, lock: MPLock ) -> None:
	global g_settings_path, g_lock
	g_settings_path = settings_path
	g_lock = lock

@timed_lru_cache( seconds = 1 )
def load() -> Settings:
	with g_lock:
		try:
			with g_settings_path.open( 'r' ) as f:
				return Settings( **json.loads( f.read() ))
		except FileNotFoundError:
			pass
		settings = Settings()
		save( settings )
		return settings

def save( settings: Settings ) -> None:
	with g_lock:
		with g_settings_path.open( 'w' ) as f:
			f.write( json.dumps(
				asdict( settings ),
				indent = 1, # make it a bit more human-readable just in case
			))

async def aload() -> Settings:
	loop = asyncio.get_running_loop()
	return await loop.run_in_executor( None, load )

async def asave( settings: Settings ) -> None:
	loop = asyncio.get_running_loop()
	await loop.run_in_executor( None, lambda: save( settings ))

