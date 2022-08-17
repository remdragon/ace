# This file is Copyright (c) 2022 ITAS Solutions LP. All rights reserved.
# Contact ITAS Solutions LP for licensing inquiries.

# stdlib imports:
from abc import ABCMeta, abstractmethod
import asyncio
from dataclasses import dataclass
import datetime
import itertools
import json
import logging
import math
from mypy_extensions import TypedDict
from pathlib import Path
import random
from typing import (
	Any, Callable, cast, Coroutine, Dict, List, Optional as Opt, Tuple, Union,
)
from typing_extensions import AsyncIterator, Literal
from uuid import uuid4

# 3rd-party imports:
import aiofiles # pip install aiofiles

# local imports:
import ace_util as util
from esl import ESL
from tts import TTS, TTS_VOICES, tts_voices

logger = logging.getLogger( __name__ )

CONF_VOICEMAIL_NAME = False

class SETTINGS( TypedDict ):
	type: Literal['root_voicemail']
	greeting: Opt[int]
	max_greeting_seconds: Opt[int]
	max_message_seconds: Opt[int]
	pin: str
	default_email_subject: Opt[str]
	default_email_body: Opt[str]
	format: Opt[str]
	default_sms_message: Opt[str]
	delivery: Dict[str,Any]
	branches: Dict[str,Any]
	greetingBranch: Dict[str,Any]

g_base = Path( '/usr/share/itas/ace/voicemail' )
g_meta_base: Path = g_base / 'meta' 
g_msgs_base: Path = g_base / 'msgs'

SILENCE_1_SECOND = 'silence_stream://1000' # 1000
SILENCE_2_SECONDS = 'silence_stream://2000' # 2000
SILENCE_3_SECONDS = 'silence_stream://3000' # 3000

GUEST_SAVE = '1'
GUEST_LISTEN = '2'
GUEST_RERECORD = '3'
GUEST_DELETE = '4'
GUEST_URGENT = '5'

MAIN_NEW_MSGS = '1'
MAIN_SAVED_MSGS = '2'
MAIN_GREETING = '3'
MAIN_NAME = '4'
MAIN_PASSWORD = '5'

LISTEN_REPEAT = '1'
LISTEN_SAVE = '2'
LISTEN_DELETE = '3'
LISTEN_UNDELETE = '3'
LISTEN_MARK_URGENT = '4'
LISTEN_MARK_NEW = '5'
LISTEN_ENVELOPE = '6'
LISTEN_NEXT_MSG = '7'
LISTEN_PREV_MSG = '8'
LISTEN_MAIN_MENU = '9'

GREETING_LISTEN = '1'
GREETING_RECORD = '2'
GREETING_CHOOSE = '3'
GREETING_DELETE = '4'
GREETING_RETURN = '9'

RECORD_SAVE = '1' # THIS CANNOT BE CUSTOMIZED WITHOUT CHANGING THE GREETING
RECORD_REVIEW = '2' # THIS CANNOT BE CUSTOMIZED WITHOUT CHANGING THE GREETING
RECORD_REDO = '3' # THIS CANNOT BE CUSTOMIZED WITHOUT CHANGING THE GREETING
RECORD_RETURN = '9'

AND = 'currency/and.wav'
NEGATIVE = 'currency/negative.wav'

HUNDRED = 'digits/hundred.wav'
MILLION = 'digits/million.wav'
POUND = 'digits/pound.wav'
STAR = 'digits/star.wav'
THOUSAND = 'digits/thousand.wav'
DIGITS = {
	'0': 'digits/0.wav',
	'1': 'digits/1.wav',
	'2': 'digits/2.wav',
	'3': 'digits/3.wav',
	'4': 'digits/4.wav',
	'5': 'digits/5.wav',
	'6': 'digits/6.wav',
	'7': 'digits/7.wav',
	'8': 'digits/8.wav',
	'9': 'digits/9.wav',
	'*': STAR,
	'#': POUND,
}
TEENS = {
	'10': 'digits/10.wav',
	'11': 'digits/11.wav',
	'12': 'digits/12.wav',
	'13': 'digits/13.wav',
	'14': 'digits/14.wav',
	'15': 'digits/15.wav',
	'16': 'digits/16.wav',
	'17': 'digits/17.wav',
	'18': 'digits/18.wav',
	'19': 'digits/19.wav',
}
TWENTY = 'digits/20.wav'
THIRTY = 'digits/30.wav'
FOURTY = 'digits/40.wav'
FIFTY = 'digits/50.wav'
SIXTY = 'digits/60.wav'
SEVENTY = 'digits/70.wav'
EIGHTY = 'digits/80.wav'
NINETY = 'digits/90.wav'

PLEASE_TRY_AGAIN = 'directory/dir-please_try_again.wav'
AINT_NOBODY_GOT_TIME_FOR_THAT = 'ivr/ivr-aint_nobody_got_time_for_that.wav'
MAN_THAT_IS_COLD_FOOLISH_COLD_FOOLISH = 'ivr/ivr-cold_foolish.wav'
CONGRATS_YOU_PRESSED_STAR_THAT_DOES_NOT_MEAN_YOU_ARE_A_STAR = 'ivr/ivr-congratulations_you_pressed_star.wav'
PLEASE_HOLD_WHILE_WE_CONNECT_YOU_TO_AN_ACTUAL_HUMAN_BEING = 'ivr/ivr-connect_actual_human_being.wav'
DID_YOU_MEAN_TO_PRESS_THAT_KEY = 'ivr/ivr-did_you_mean_to_press_key.wav'
I_JUST_LOVE_THE_WAY_YOU_PRESS_THOSE_TOUCHTONES = 'ivr/ivr-love_those_touch_tones.wav'
THIS_MSG_WILL_SELF_DESTRUCT_IN_54321 = 'ivr/ivr-message_self_destruct.wav'
NO_NO_NO = 'ivr/ivr-no_no_no.wav'
OH_WHATEVER = 'ivr/ivr-oh_whatever.wav'
THATS_IT_ONE_MORE_MISTAKE_AND_I_WILL_HANGUP_ON_YOUR_ASS = 'ivr/ivr-one_more_mistake.wav'
THAT_WAS_AN_INVALID_ENTRY = 'ivr/ivr-that_was_an_invalid_entry.wav'
TO_ACCEPT_PRESS = 'ivr/ivr-to_accept_press.wav'
TO_RETURN_TO_THE_PREVIOUS_MENU = 'ivr/ivr-to_return_to_previous_menu.wav'
PRESS_1_TO_SAVE_RECORDING_PRESS_2_TO_REVIEW_PRESS_3_TO_RERECORD = 'ivr/ivr-save_review_record.wav'
YES_WE_HAVE_NO_BANANAS = 'ivr/ivr-yes_we_have_no_bananas.wav'

AN_ERROR_HAS_OCCURRED_PLEASE_CONTACT_THE_ADMINISTRATOR = 'misc/error.wav'
ENGLISH = 'misc/en.wav'
ERROR = 'misc/error.wav'
ITS_TOTALLY_SOCCER_MOM_SHIT = 'misc/misc-soccer_mom.wav'
IM_SORRY = 'misc/sorry.wav'

TOO_MANY_FAILED_ATTEMPTS = 'voicemail/vm-abort.wav'
FOR_ADVANCED_OPTIONS = 'voicemail/vm-advanced.wav'
FOR_ADVANCED_OPTIONS2 = 'voicemail/vm-advanced_alt.wav'
TO_CHANGE_YOUR_PASSWORD = 'voicemail/vm-change_password.wav'
TO_CHOOSE_GREETING = 'voicemail/vm-choose_greeting.wav'
CHOOSE_A_GREETING_BETWEEN_1_AND_9 = 'voicemail/vm-choose_greeting_choose.wav'
INVALID_VALUE = 'voicemail/vm-choose_greeting_fail.wav'
PLEASE_CHOOSE_A_PASSWORD_THAT_DOES_NOT_CONTAIN_ALL_REPEATING_OR_ALL_CONSECUTIVE_DIGITS = 'voicemail/vm-choose_password.wav'
TO_CONTINUE = 'voicemail/vm-continue.wav'
TO_DELETE_GREETING = 'voicemail/vm-delete_recording.wav'
TO_DELETE_THIS_MESSAGE = 'voicemail/vm-delete_message.wav'
DELETED = 'voicemail/vm-deleted.wav'
TO_DELETE_THE_RECORDING = 'voicemail/vm-delete_recording.wav'
EMAILED = 'voicemail/vm-emailed.wav'
PLEASE_ENTER_YOUR_ID_FOLLOWED_BY = 'voicemail/vm-enter_id.wav'
PLEASE_ENTER_YOUR_NEW_PASSWORD_THEN_PRESS_THE_POUND_KEY = 'voicemail/vm-enter_new_pin.wav'
PLEASE_ENTER_YOUR_PASSWORD_FOLLOWED_BY = 'voicemail/vm-enter_pass.wav'
LOGIN_INCORRECT = 'voicemail/vm-fail_auth.wav'
FOLLOWED_BY = 'voicemail/vm-followed_by.wav'
FOLLOWED_BY_POUND = 'voicemail/vm-followed_by_pound.wav'
TO_ADD_AN_INTRODUCTION_TO_THIS_MESSAGE = 'voicemail/vm-forward_add_intro.wav'
PLEASE_ENTER_THE_EXTENSION_TO_FORWARD_THIS_MESSAGE_TO = 'voicemail/vm-forward_enter_ext.wav'
TO_FORWARD_THE_RECORDING_TO_YOUR_EMAIL = 'voicemail/vm-forward_to_email.wav'
FROM = 'voicemail/vm-from.wav'
GOODBYE = 'voicemail/vm-goodbye.wav'
GREETING = 'voicemail/vm-greeting.wav'
HAS_BEEN_CHANGED_TO = 'voicemail/vm-has_been_changed_to.wav'
WELCOME_TO_YOUR_VOICEMAIL = 'voicemail/vm-hello.wav'
IN_FOLDER_INBOX = 'voicemail/vm-in_folder.wav'
LAST = 'voicemail/vm-last.wav'
TO_LISTEN_TO_NEW_MESSAGES = 'voicemail/vm-listen_new.wav'
TO_LISTEN_TO_SAVED_MESSAGES = 'voicemail/vm-listen_saved.wav'
TO_LISTEN_TO_GREETING = 'voicemail/vm-listen_to_recording.wav'
TO_LISTEN_TO_THE_RECORDING = 'voicemail/vm-listen_to_recording.wav'
TO_LISTEN_TO_THE_RECORDING_AGAIN = 'voicemail/vm-listen_to_recording_again.wav'
THAT_MAILBOX_IS_FULL_PLEASE_TRY_YOUR_CALL_AGAIN_LATER = 'voicemail/vm-mailbox_full.wav'
FOR_THE_MAIN_MENU = 'voicemail/vm-main_menu.wav'
FOR_THE_MAIN_MENU2 = 'voicemail/vm-main_menu_alt.wav'
TO_MARK_THIS_MESSAGE_URGENT = 'voicemail/vm-mark-urgent.wav'
MARKED_URGENT = 'voicemail/vm-marked-urgent.wav'
MARKED_NEW = 'voicemail/vm-marked_new.wav'
TO_MARK_THIS_MESSAGE_AS_NEW = 'voicemail/vm-mark_message_new.wav'
MESSAGE = 'voicemail/vm-message.wav'
MESSAGES = 'voicemail/vm-messages.wav'
MESSAGES2 = 'voicemail/vm-messages_alt.wav' # full stop
MESSAGE2 = 'voicemail/vm-message_alt.wav'
TO_HEAR_THE_MESSAGE_ENVELOPE = 'voicemail/vm-message_envelope.wav'
MESSAGE_FORWARDED = 'voicemail/vm-message_forwarded.wav'
MESSAGE_FROM = 'voicemail/vm-message_from.wav'
MESSAGE_NUMBER = 'voicemail/vm-message_number.wav'
THE_MINIMUM_PIN_LENGTH_IS = 'voicemail/vm-minimum_pin_length_is.wav'
NEW = 'voicemail/vm-new.wav'
NEXT = 'voicemail/vm-next.wav'
NOBODY_IS_CURRENTLY_LEAVING_A_MESSAGE_IN_THIS_VOICEMAIL_BOX = 'voicemail/vm-nobody_leaving_message.wav'
IS_NOT_AVAILABLE = 'voicemail/vm-not_available.wav'
THE_PERSON_YOU_ARE_TRYING_TO_REACH_IS_NOT_AVAILABLE_AND_DOES_NOT_HAVE_VOICEMAIL = 'voicemail/vm-not_available_no_voicemail.wav'
THE_EXTENSION_YOU_HAVE_DIALED_DOES_NOT_ANSWER_AND_THERE_IS_NO_VOICEMAIL_BOX_SETUP_FOR_THIS_EXTENSION = 'voicemail/vm-no_answer_no_vm.wav'
NO_MORE_MESSAGES = 'voicemail/vm-no_more_messages.wav'
YOUR_PASSWORD_HAS_BEEN_CHANGED = 'voicemail/vm-password_has_been_changed.wav'
A_PASSWORD_SUCH_AS_1111_OR_1234_IS_NOT_SECURE = 'voicemail/vm-password_is_not_secure.wav'
THE_PASSWORD_YOU_ENTERED_IS_NOT_VALID_ON_THIS_SYSTEM = 'voicemail/vm-password_not_valid.wav'
THE_PERSON_AT_EXTENSION = 'voicemail/vm-person.wav'
THE_PIN_YOU_ENTERED_IS_BELOW_THE_MINIMUM_LENGTH = 'voicemail/vm-pin_below_minimum_length.wav'
IS_NOT_AVAILABLE2 = 'voicemail/vm-play_greeting.wav'
TO_PLAY_THE_NEXT_MESSAGE = 'voicemail/vm-play_next_message.wav'
TO_PLAY_THE_PREVIOUS_MESSAGE = 'voicemail/vm-play_previous_message.wav'
PRESS = 'voicemail/vm-press.wav'
RECEIVED = 'voicemail/vm-received.wav'
RECORD_YOUR_GREETING_AT_THE_TONE_PRESS_ANY_KEY_OR_STOP_TALKING_TO_END_THE_RECORDING = 'voicemail/vm-record_greeting.wav'
RECORD_YOUR_MESSAGE_AT_THE_TONE_PRESS_ANY_KEY_OR_STOP_TALKING_TO_END_THE_RECORDING = 'voicemail/vm-record_message.wav'
AT_THE_TONE_PLEASE_RECORD_YOUR_NAME_PRESS_ANY_KEY_OR_STOP_TALKING_TO_END_THE_RECORDING = 'voicemail/vm-record_name1.wav'
TO_RECORD_YOUR_NAME = 'voicemail/vm-record_name2.wav'
TO_REPEAT_THIS_MESSAGE = 'voicemail/vm-repeat_message.wav'
TO_RERECORD = 'voicemail/vm-rerecord.wav'
TO_RETURN_THE_CALL_NOW = 'voicemail/vm-return_call.wav'
SAVED = 'voicemail/vm-saved.wav'
TO_SAVE_THIS_MESSAGE = 'voicemail/vm-save_message.wav'
TO_SAVE_THE_RECORDING = 'voicemail/vm-save_recording.wav'
SELECTED = 'voicemail/vm-selected.wav'
TO_SEND_THIS_MESSAGE_NOW = 'voicemail/vm-send_message_now.wav'
THAT_WAS_AN_INVALID_EXTENSION = 'voicemail/vm-that_was_an_invalid_ext.wav'
YOUR_RECORDING_IS_BELOW_THE_MINIMUM_ACCEPTABLE_LENGTH_PLEASE_TRY_AGAIN = 'voicemail/vm-too-small.wav'
TO_EXIT = 'voicemail/vm-to_exit.wav'
TO_EXIT2 = 'voicemail/vm-to_exit_alt.wav'
TO_FORWARD_THIS_MESSAGE = 'voicemail/vm-to_forward.wav'
TO_RECORD_A_GREETING = 'voicemail/vm-to_record_greeting.wav'
YOUR_PIN_IS_USED_TO_PREVENT_OTHERS_FROM_ACCESSING_YOUR_VM_MSGS_WOULD_YOU_LIKE_TO_CHANGE_IT_NOW = 'voicemail/vm-tutorial_change_pin.wav'
I_NEED_TO_RECORD_YOUR_FIRST_AND_LAST_NAME_THIS_RECORDING_IS_USED_THROUGHOUT_THE_SYSTEM_INCLUDING_IN_THE_COMPANY_DIRECTORY = 'voicemail/vm-tutorial_record_name.wav'
WELCOME_TO_YOUR_NEW_VOICEMAIL_TO_LISTEN_TO_A_TUTORIAL_AND_SETUP_YOUR_VM_BOX_PRESS1_TO_SKIP_PRESS2 = 'voicemail/vm-tutorial_yes_no.wav'
UNDELETED = 'voicemail/vm-undeleted.wav'
TO_UNDELETE_THIS_MESSAGE = 'voicemail/vm-undelete_message.wav'
URGENT_NEW = 'voicemail/vm-urgent-new.wav'
URGENT_SAVED = 'voicemail/vm-urgent-saved.wav'
URGENT = 'voicemail/vm-urgent.wav'
REMEMBER_THAT_YOUR_VOICEMAIL_PASSWORD_IS_ALSO_YOUR_WEB_INTERFACE_PASSWORD = 'voicemail/vm-voicemail_password_is_web_password.wav'
YOU_HAVE = 'voicemail/vm-you_have.wav'

def digits_audio( digits: str ) -> List[str]:
	audio: List[str] = [
		DIGITS[digit] for digit in digits
	]
	return audio

def number_audio( value: int ) -> List[str]:
	sounds: List[str] = []
	if value < 0:
		value = -value
		sounds.append( NEGATIVE )
	if value >= 1000000:
		assert( value < 1000000000 )
		newvalue: int = value % 1000000
		millions: int = math.floor( ( value - newvalue ) / 1000000 )
		value = newvalue
		sounds.extend( number_audio( millions ))
		sounds.append( MILLION )
	if value >= 1000:
		newvalue = value % 1000
		thousands: int = math.floor( ( value - newvalue ) / 1000 )
		value = newvalue
		sounds.extend( number_audio( thousands ))
		sounds.append( THOUSAND )
	if value >= 100:
		newvalue = value % 100
		hundreds: int = math.floor( ( value - newvalue ) / 100 )
		value = newvalue
		sounds.extend( number_audio( hundreds ))
		sounds.append( HUNDRED )
	decade: int
	decade_sound: str
	if value >= 90:
		decade, decade_sound = 90, NINETY
	elif value >= 80:
		decade, decade_sound = 80, EIGHTY
	elif value >= 70:
		decade, decade_sound = 70, SEVENTY
	elif value >= 60:
		decade, decade_sound = 60, SIXTY
	elif value >= 50:
		decade, decade_sound = 50, FIFTY
	elif value >= 40:
		decade, decade_sound = 40, FOURTY
	elif value >= 30:
		decade, decade_sound = 30, THIRTY
	elif value >= 20:
		decade, decade_sound = 20, TWENTY
	if decade is not None:
		sounds.append( decade_sound )
		if value > decade:
			sounds.append( DIGITS[str( value - decade )] )
		value = value - decade
	if value >= 10:
		sounds.append( TEENS[str( value )] )
	elif value > 0:
		sounds.append( DIGITS[str( value )] )
	elif not sounds:
		sounds.append( DIGITS['0'] )
	return sounds

Q = '%(150,100,'
H = '%(400,100,'
A = '440)'
C = '261.63)'
E = '329.63)'
F = '369.99)'
QA = f'{Q}{A}'
QC = f'{Q}{C}'
QE = f'{Q}{E}'
QF = f'{Q}{F}'
HE = f'{H}{E}'
TONE_FUN = f'tone_stream://{QA};{QA};{QA};{QE};{QF}:{QF}:{HE}'
TONE_BORING = f'tone_stream://{QC}'
TONE = TONE_BORING

@dataclass
class MSG:
	folder: Path
	file: str
	path: Path
	box: int
	year: int
	month: int
	day: int
	hour: int
	minute: int
	second: int
	did: str
	ani: str
	uuid: str
	priority: Literal['normal','urgent']
	status: Literal['new','saved','delete']
	
	old_priority: Opt[Literal['normal','urgent']] = None
	old_status: Opt[Literal['new','saved','delete']] = None
	
	def to_path( self ) -> Path:
		parts: List[str] = [
			str( self.box ),
			str( self.year ),
			str( self.month ),
			str( self.day ),
			str( self.hour ),
			str( self.minute ),
			str( self.second ),
			self.did,
			self.ani,
			self.uuid,
			self.priority,
			self.status,
		]
		return ( self.folder / '-'.join( parts )).with_suffix( '.wav' )

class EventHandler( metaclass = ABCMeta ):
	@abstractmethod
	def handle_event( self, event: ESL.Message ) -> None:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.handle_event()' )

class Voicemail:
	min_pin_length: int = 4
	use_tts: bool = False
	
	def __init__( self, esl: ESL, uuid: str ) -> None:
		self.esl = esl
		self.uuid = uuid
	
	_event_handler: Opt[EventHandler] = None
	
	def _on_event( self, event: ESL.Message ) -> None:
		if self._event_handler:
			self._event_handler.handle_event( event )
	
	@staticmethod
	async def init( *,
		box_path: Path,
		msgs_path: Path,
		owner_user: str,
		owner_group: str,
		min_pin_length: int,
		use_tts: bool,
		on_event: Callable[[ESL.Message],None],
	) -> None:
		global g_meta_base, g_msgs_base
		g_meta_base = box_path
		g_msgs_base = msgs_path
		await util.mkdirp( g_meta_base )
		await util.chown( g_meta_base, owner_user, owner_group )
		await util.chmod( g_meta_base, 0o775 )
		
		await util.mkdirp( g_msgs_base )
		await util.chown( g_msgs_base, owner_user, owner_group )
		await util.chmod( g_msgs_base, 0o775 )
		
		Voicemail.min_pin_length = min_pin_length
		Voicemail.use_tts = use_tts
		
		class X( EventHandler ):
			def handle_event( self, event: ESL.Message ) -> None:
				on_event( event )
		Voicemail._event_handler = X()
	
	async def scandir( self, path: Path, mask: str ) -> AsyncIterator[Path]:
		async for file in util.glob( path, mask ):
			yield file
	
	async def play( self, sounds: List[str],
		min_digits: int,
		max_digits: int,
		max_attempts: int,
		timeout: datetime.timedelta,
		terminators: str,
		error: str,
		digit_regex: str,
		variable_name: str,
		digit_timeout: datetime.timedelta,
	) -> str:
		log = logger.getChild( 'Voicemail.play' )
		async def _play( path: str, local_timeout: datetime.timedelta ) -> str:
			log = logger.getChild( 'Voicemail.play._play' )
			log.debug( 'playing %r', path )
			max_attempts = 1
			log.info( 'executing playAndGetDigits mindig=%r maxdig=%r #atts=%r timeout=%r term=%r snd=%r err=%r re=%r var=%r dig_timeout=%r',
				min_digits,
				max_digits,
				max_attempts,
				local_timeout,
				terminators,
				path,
				error,
				digit_regex,
				variable_name,
				digit_timeout
			)
			digits_: List[str] = []
			async for event in self.esl.play_and_get_digits( self.uuid,
				min_digits,
				max_digits,
				max_attempts,
				local_timeout,
				terminators,
				path,
				error,
				digit_regex,
				variable_name,
				digit_timeout,
				digits = digits_,
			):
				self._on_event( event )
			digits = ''.join( digits_ )
			log.debug( 'digits=%r', digits )
			return digits
		#session:flushDigits()
		#session:setInputCallback( 'input_callback', '' )
		digits: Opt[str] = None
		local_timeout = datetime.timedelta( milliseconds = 1 )
		for attempt in range( max_attempts ):
			for i, param in enumerate( sounds ):
				if isinstance( param, list ):
					for j, sound in enumerate( param ):
						if i == len( sounds ) - 1 and j == len( param ) - 1:
							local_timeout = timeout
						digits = await _play( sound, local_timeout )
						if digits:
							log.debug( 'returning digits=%r', digits )
							return digits
				elif isinstance( param, str ):
					if i == len( sounds ) - 1: local_timeout = timeout
					digits = await _play( param, local_timeout )
					if digits:
						log.debug( 'returning digits=%r', digits )
						return digits
				elif isinstance( param, ( int, float )):
					await asyncio.sleep( param )
				else:
					log.error( 'invalid param=%r', param )
				if digits:
					log.debug( 'returning digits=%r', digits )
					return digits
		digits = ''
		log.debug( 'returning digits=%r', digits )
		return digits
	
	async def play_menu( self, sounds: List[str], max_attempts: int = 1 ) -> str:
		min_digits: int = 1
		max_digits: int = 1
		if max_attempts < 1:
			max_attempts = 1
		timeout = datetime.timedelta( seconds = 0.01 ) # maybe this should be longer?
		terminators: str = ''
		error: str = ''
		digit_regex: str = ''
		variable_name: str = ''
		digit_timeout = datetime.timedelta( seconds = 0.01 )
		
		return await self.play( sounds,
			min_digits,
			max_digits,
			max_attempts,
			timeout,
			terminators,
			error,
			digit_regex,
			variable_name,
			digit_timeout,
		)
	
	async def play_box( self, sounds: List[str] ) -> str:
		min_digits: int = 2
		max_digits: int = 20
		max_attempts: int = 3
		timeout = datetime.timedelta( seconds = 3 )
		terminators: str = '#'
		error: str = ''
		digit_regex: str = ''
		variable_name: str = ''
		digit_timeout = datetime.timedelta( seconds = 3 )
		return await self.play( sounds,
			min_digits,
			max_digits,
			max_attempts,
			timeout,
			terminators,
			error,
			digit_regex,
			variable_name,
			digit_timeout,
		)
	
	async def play_pin( self, sounds: List[str], digit_regex: str = '' ) -> str:
		#session:flushDigits()
		min_digits: int = 1
		max_digits: int = 20
		max_attempts: int = 1
		timeout = datetime.timedelta( seconds = 3 )
		terminators: str = '#'
		error: str = ''
		variable_name: str = ''
		digit_timeout = datetime.timedelta( seconds = 3 )
		return await self.play( sounds,
			min_digits,
			max_digits,
			max_attempts,
			timeout,
			terminators,
			error,
			digit_regex or '\\d+',
			variable_name,
			digit_timeout,
		)
	
	async def load_file_into_memory( self, path: Path ) -> Opt[str]:
		if not path.is_file():
			return None
		async with aiofiles.open( str( path ), 'r' ) as f:
			content = await f.read()
		return content
	
	def box_meta_path( self, box: int ) -> Path:
		return g_meta_base / str( box )
	
	def box_msgs_path( self, box: int ) -> Path:
		return g_msgs_base / str( box )
	
	def box_settings_path( self, box: int ) -> Path:
		return g_meta_base / f'{box}.box'
	
	def box_greeting_path( self, box: int, greeting: Union[int,str] ) -> Opt[Path]:
		# NOTE: greeting can be a temporary suffix when recording a new greeting that hasn't been accepted yet
		if greeting == 0: return None
		return self.box_meta_path( box ) / f'greeting{greeting}.wav'
	
	async def load_box_settings( self, box: int ) -> Opt[SETTINGS]:
		log = logger.getChild( 'Voicemail.load_box_settings' )
		path = self.box_settings_path( box )
		raw = await self.load_file_into_memory( path )
		if raw is None:
			log.debug( 'load_box_settings failed b/c file does not exist: %r', str( path ))
			return None
		try:
			result: SETTINGS = json.loads( raw )
		except Exception as e:
			log.warning( 'Could not parse json at %r: %r', str( path ), e )
			return None
		return result
	
	async def save_box_settings( self, box: int, settings: SETTINGS ) -> None:
			path: Path = self.box_settings_path( box )
			raw: str = json.dumps( settings )
			async with aiofiles.open( str( path ), 'w' ) as f:
				await f.write( raw )
	
	async def goodbye( self ) -> None:
		if self.use_tts:
			x = TTS()
			x.say( 'Goodbye.' )
			stream: str = str( await x.generate() )
		else:
			stream = GOODBYE
		await self.play_menu([ stream, SILENCE_2_SECONDS ])
		await util.hangup( self.esl, self.uuid, 'NORMAL_CLEARING', 'ace_voicemail.Voicemail.goodbye' )
	
	async def _the_person_you_are_trying_to_reach_is_not_available_and_does_not_have_voicemail( self ) -> str:
		if self.use_tts:
			x = TTS()
			x.say( 'The person you are trying to reach is not available and does not have a voicemail setup' )
			return str( await x.generate() )
		else:
			return THE_PERSON_YOU_ARE_TRYING_TO_REACH_IS_NOT_AVAILABLE_AND_DOES_NOT_HAVE_VOICEMAIL
	
	async def _record_your_message_at_the_tone_press_any_key_or_stop_talking_to_end_the_recording( self ) -> str:
		if self.use_tts:
			x = TTS()
			x.say( 'Record your message at the tone. Press any key, or stop talking, to end the recording.' )
			return str( await x.generate() )
		else:
			return RECORD_YOUR_MESSAGE_AT_THE_TONE_PRESS_ANY_KEY_OR_STOP_TALKING_TO_END_THE_RECORDING
	
	async def _the_person_at_extension_is_not_available_record_at_the_tone( self, box: int ) -> List[str]:
		if self.use_tts:
			x = TTS()
			x.say( 'The person at ' )
			x.digits( box )
			x.say( ' is not available. Record your message at the tone. Press any key, or stop talking, to end the recording.' )
			playlist: List[str] = [ str( await x.generate() ) ]
		else:
			playlist = [ THE_PERSON_AT_EXTENSION ]
			playlist.extend( digits_audio( str( box )))
			playlist.extend([
				IS_NOT_AVAILABLE, # IS_NOT_AVAILABLE2
				SILENCE_1_SECOND,
			])
		playlist.append( await self._record_your_message_at_the_tone_press_any_key_or_stop_talking_to_end_the_recording() )
		return playlist
	
	async def guest( self, did: str, ani: str, box: int, settings: SETTINGS, notify: Callable[[int,SETTINGS,MSG],Coroutine[Any,Any,None]], greeting_override: Opt[int] = None ) -> bool:
		log = logger.getChild( 'Voicemail.guest' )
		
		now: str = datetime.datetime.now().strftime( '%Y-%m-%d-%H-%M-%S' )
		uuid: str = str( uuid4() ).replace( '-', '' )
		folder: Path = self.box_msgs_path( box )
		#log.debug( 'mkdirp( %s )', repr( folder ))
		await util.mkdirp( folder )
		#log.debug( 'mkdirp( %s ) -> %s, %s', repr( folder ), repr( ok ), repr( err ))
		stem: str = f'{box}-{now}-{did}-{ani}-{uuid}'
		base_name: Path = folder / stem
		tmp_name: Path = folder / f'{stem}-tmp.wav'
		
		max_message_time = datetime.timedelta( seconds = settings.get( 'max_message_seconds' ) or 120 )
		silence_threshold: int = 30
		silence_seconds: int = 5
		priority: str = 'normal'
		
		def _guest_save() -> None:
			if not tmp_name.is_file():
				log.debug( 'not launching guest_save hook b/c file does not exist: %s', repr( tmp_name ))
			else:
				asyncio.get_running_loop().call_soon( lambda: self.guest_save( box, settings, stem, priority, notify ))
		
		if self.use_tts:
			x = TTS()
			x.say( 'To send this message now, press ' )
			x.digits( GUEST_SAVE )
			x.say( ', to listen to the recording, press ' )
			x.digits( GUEST_LISTEN )
			x.say( ', to re-record, press' )
			x.digits( GUEST_RERECORD )
			x.say( ', to delete this message, press ' )
			x.digits( GUEST_DELETE )
			if settings.get( 'allow_guest_urgent' ):
				x.say( ', to mark this message urgent, press ' )
				x.digits( GUEST_URGENT )
			stream = str( await x.generate() )
			menu: List[str] = [ stream ]
		else:
			menu = [
				TO_SEND_THIS_MESSAGE_NOW,
				PRESS,
				DIGITS[GUEST_SAVE],
				
				TO_LISTEN_TO_THE_RECORDING,
				PRESS,
				DIGITS[GUEST_LISTEN],
				
				TO_RERECORD,
				PRESS,
				DIGITS[GUEST_RERECORD],
				
				TO_DELETE_THIS_MESSAGE,
				PRESS,
				DIGITS[GUEST_DELETE],
			]
			if settings.get( 'allow_guest_urgent' ):
				menu.extend([
					TO_MARK_THIS_MESSAGE_URGENT,
					PRESS,
					DIGITS[GUEST_URGENT],
				])
		menu.append( SILENCE_3_SECONDS )
		
		while True:
			async for event in self.esl.playback( self.uuid, TONE ):
				self._on_event( event )
			
			log.debug( 'box %r RECORDING', box )
			async for event in self.esl.record( self.uuid, tmp_name,
				max_message_time,
				silence_threshold,
				silence_seconds,
			):
				self._on_event( event )
			
			digit = ''
			count: int = 1
			
			while digit != GUEST_RERECORD:
				digit = await self.play_menu( menu )
				if digit == GUEST_LISTEN:
					log.debug( 'listening to own message' )
					await self.play_menu([ str( tmp_name )]) # TODO FIXME: collect digit?
				elif digit == GUEST_RERECORD:
					log.debug( 'rerecording' )
					# do nothing, let it fall through
				elif digit == GUEST_DELETE:
					log.debug( 'deleted message' )
					await self.play_menu([
						DELETED, #THIS_MSG_WILL_SELF_DESTRUCT_IN_54321, # DELETED
						SILENCE_1_SECOND,
						GOODBYE,
						SILENCE_2_SECONDS,
					])
					await util.hangup( self.esl, self.uuid, 'NORMAL_CLEARING', 'ace_voicemail.Voicemail.guest' )
					asyncio.get_running_loop().call_soon( self.guest_delete, tmp_name )
					return False
				elif digit == GUEST_SAVE or count >= 10:
					log.debug( 'guest saved message' )
					_guest_save()
					await self.play_menu([
						SAVED,
						SILENCE_1_SECOND,
					])
					await self.goodbye()
					return False
				elif digit == GUEST_URGENT and settings.get( 'allow_guest_urgent' ):
					log.debug( 'marked message urgent' )
					priority = 'urgent'
					await self.play_menu([
						MARKED_URGENT,
						SILENCE_1_SECOND,
					])
				elif digit is not None and digit != '':
					await self.play_invalid_value( digit )
					digit = ''
				count = count + 1
		_guest_save()
		return True, None

	async def play_invalid_value( self, digit: Opt[str] ) -> None:
		if self.use_tts:
			x = TTS()
			x.say( 'Invalid selection, please try again' )
			stream: str = str( await x.generate() )
		else:
			options: List[str] = [
				IM_SORRY,
				INVALID_VALUE,
				DID_YOU_MEAN_TO_PRESS_THAT_KEY,
				I_JUST_LOVE_THE_WAY_YOU_PRESS_THOSE_TOUCHTONES,
				AINT_NOBODY_GOT_TIME_FOR_THAT,
				MAN_THAT_IS_COLD_FOOLISH_COLD_FOOLISH,
				NO_NO_NO,
				OH_WHATEVER,
				THATS_IT_ONE_MORE_MISTAKE_AND_I_WILL_HANGUP_ON_YOUR_ASS,
				PLEASE_TRY_AGAIN,
				THAT_WAS_AN_INVALID_ENTRY,
				YES_WE_HAVE_NO_BANANAS,
			]
			if digit == '*':
				options.append(
					CONGRATS_YOU_PRESSED_STAR_THAT_DOES_NOT_MEAN_YOU_ARE_A_STAR
				)
			stream = random.choice( options )
		await self.play_menu([ stream, SILENCE_1_SECOND ])
	
	async def guest_save( self, box: int, settings: SETTINGS, file: str, priority: str, notify: Callable[[int,SETTINGS,MSG],Coroutine[Any,Any,None]] ) -> None:
		log = logger.getChild( 'Voicemail.guest_save' )
		log.debug( 'guest_save_hook: file=%r', file )
		msgs_path: Path = self.box_msgs_path( box )
		base_name: Path = msgs_path / file
		tmp_file: str = f'{file}-tmp.wav'
		new_file: str = f'{file}-{priority}-new.wav'
		tmp_name: Path = msgs_path / tmp_file
		new_name: Path = msgs_path / new_file
		ok = False
		reason = ''
		waits = 0
		while waits < 60:
			log.debug( 'ATTEMPTING TO RENAME %r to %r', str( tmp_name ), str( new_name ))
			try:
				await aiofiles.os.rename( tmp_name, new_name )
			except Exception as e:
				log.warning( 'UNABLE TO RENAME %r to %r: %r', str( tmp_name ), str( new_name ), e )
				waits += 1
				log.debug( 'WAITING 1 SECOND' )
				await asyncio.sleep( 1 )
			else:
				log.debug( 'file renamed - all done here' )
				# trigger notification if any...
				
				msg = self.parse_recording_path( msgs_path, new_name.name )
				
				asyncio.get_running_loop().call_soon( notify, box, settings, msg )
				return
		log.warning( 'GIVING UP TRYING TO RENAME FILE' )
	
	async def guest_delete( self, tmp_name: Path ) -> None:
		log = logger.getChild( 'Voicemail.guest_delete' )
		log.debug( 'tmp_name=%r', tmp_name )
		waits: int = 0
		while waits < 10:
			log.debug( 'ATTEMPTING TO DELETE %r', tmp_name )
			try:
				await aiofiles.os.remove( tmp_name )
			except Exception:
				log.warning( 'UNABLE TO DELETE %r:', str( tmp_name ), exc_info = True )
				waits = waits + 1
				log.debug( 'WAITING 1 SECOND' )
				await asyncio.sleep( 1 )
			else:
				log.debug( 'file deleted - all done here' )
				return
	
	async def _please_enter_your_mailbox_followed_by_pound( self ) -> List[str]:
		if self.use_tts:
			x = TTS()
			x.say( 'Please enter your mailbox number followed by pound' )
			return [ str( await x.generate() )]
		else:
			return [ PLEASE_ENTER_YOUR_ID_FOLLOWED_BY, POUND ]
	
	async def _please_enter_your_password_followed_by_pound( self ) -> List[str]:
		if self.use_tts:
			x = TTS()
			x.say( 'Please enter your password followed by pound' )
			return [ str( await x.generate() )]
		else:
			return [ PLEASE_ENTER_YOUR_PASSWORD_FOLLOWED_BY, POUND ]
	
	async def _login_incorrect( self ) -> List[str]:
		if self.use_tts:
			x = TTS()
			x.say( 'Login incorrect' )
			return [ str( await x.generate() ), SILENCE_2_SECONDS ]
		else:
			return [ LOGIN_INCORRECT, SILENCE_2_SECONDS ]
	
	async def too_many_failed_attempts( self ) -> str:
		if self.use_tts:
			x = TTS()
			x.say( 'Too many failed attempts' )
			stream: str = str( await x.generate() )
		else:
			stream = TOO_MANY_FAILED_ATTEMPTS
		return await self.play_menu([ stream ])
	
	async def login( self, box: int, settings: SETTINGS, playlist: Opt[List[str]] = None ) -> Opt[bool]:
		log = logger.getChild( 'Voicemail.login' )
		if playlist is None:
			playlist = await self._please_enter_your_password_followed_by_pound()
		incorrect: List[str] = []
		await util.answer( self.esl, self.uuid, 'ace_voicemail.Voicemail.login' )
		pin: str = settings['pin']
		digits: Opt[str] = ''
		for i in range( 3 ):
			if digits == '':
				digits = await self.play_pin( playlist )
				if digits is None:
					log.debug( 'login failure due to call terminator detected' )
					return None
			if pin is not None and digits == str( pin ):
				log.debug( 'correct pin received - login successful' )
				return True
			if not incorrect: incorrect = await self._login_incorrect()
			digits = await self.play_menu( incorrect )
		await self.too_many_failed_attempts()
		await self.goodbye()
		log.debug( 'login failure due to too many failed attempts' )
		return False
	
	async def checkin( self ) -> bool:
		log = logger.getChild( 'Voicemail.checkin' )
		await util.answer( self.esl, self.uuid, 'ace_voicemail.Voicemail.checkin' )
		mailbox_prompt: List[str] = await self._please_enter_your_mailbox_followed_by_pound()
		password_prompt: List[str] = await self._please_enter_your_password_followed_by_pound()
		incorrect: List[str] = []
		for i in range( 3 ):
			box_ = await self.play_box( mailbox_prompt )
			if box_ is None:
				return False
			if not box_:
				continue
			try:
				box = int( box_ )
			except ValueError:
				continue
			pin: Opt[str] = await self.play_pin( password_prompt )
			if pin is None:
				return False
			settings: Opt[SETTINGS] = await self.load_box_settings( box )
			pwd: Opt[str] = None
			if settings is not None: pwd = settings['pin']
			log.debug( 'box=%r, pin=%r, pwd=%r',
				box, pin, pwd,
			)
			if settings is not None and pin == pwd:
				return await self.admin_main_menu( box, settings )
			if incorrect is None: incorrect = await self._login_incorrect()
			await self.play_menu( incorrect )
		await self.too_many_failed_attempts()
		await self.goodbye()
		return False
	
	async def _main_menu( self ) -> List[str]:
		if self.use_tts:
			x = TTS()
			x.say( 'Welcome to your voicemail.' )
			x.say( 'To listen to new messages, press ' )
			x.digits( MAIN_NEW_MSGS )
			x.say( '. To listen to saved messages, press ' )
			x.digits( MAIN_SAVED_MSGS )
			x.say( '. To record a greeting, press ' )
			x.digits( MAIN_GREETING )
			x.say( '.' )
			if CONF_VOICEMAIL_NAME:
				x.say( 'To record your name, press ' )
				x.digits( MAIN_NAME )
				x.say( '.' )
			x.say( 'To change your password, press ' )
			x.digits( MAIN_PASSWORD )
			x.say( '.' )
			stream = str( await x.generate() )
			return [ stream, SILENCE_3_SECONDS ]
		else:
			playlist: List[str] = [
				WELCOME_TO_YOUR_VOICEMAIL,
				SILENCE_1_SECOND,
				TO_LISTEN_TO_NEW_MESSAGES,
				PRESS,
				DIGITS[MAIN_NEW_MSGS],
				SILENCE_1_SECOND,
				TO_LISTEN_TO_SAVED_MESSAGES,
				PRESS,
				DIGITS[MAIN_SAVED_MSGS],
				SILENCE_1_SECOND,
				TO_RECORD_A_GREETING,
				PRESS,
				DIGITS[MAIN_GREETING],
				SILENCE_1_SECOND,
			]
			if CONF_VOICEMAIL_NAME:
				playlist.extend([
					TO_RECORD_YOUR_NAME,
					PRESS,
					DIGITS[MAIN_NAME],
					SILENCE_1_SECOND,
				])
			playlist.extend([
				TO_CHANGE_YOUR_PASSWORD,
				PRESS,
				DIGITS[MAIN_PASSWORD],
				SILENCE_3_SECONDS,
			])
			return playlist
	
	async def _for_the_main_menu_press( self ) -> List[str]:
		if self.use_tts:
			x = TTS()
			x.say( 'For the main menu, press ' )
			x.digits( LISTEN_MAIN_MENU )
			x.say( '.' )
			return [ str( await x.generate() )]
		else:
			return [
				FOR_THE_MAIN_MENU,
				PRESS,
				DIGITS[LISTEN_MAIN_MENU],
			]
	
	async def admin_main_menu( self, box: int, settings: SETTINGS ) -> bool:
		log = logger.getChild( 'Voicemail.admin_main_menu' )
		assert settings # this function should be called with settings already loaded...
		log.debug( 'generating main menu' )
		menu = await self._main_menu()
		while True:
			log.debug( 'calling play_menu' )
			digit: Opt[str] = await self.play_menu( menu )
			log.debug( 'digit=%r', digit )
			if digit is None:
				return False
			elif digit == MAIN_NEW_MSGS:
				await self.admin_listen_new( box, settings )
			elif digit == MAIN_SAVED_MSGS:
				await self.admin_listen_saved( box, settings )
			elif digit == MAIN_GREETING:
				await self.admin_greetings( box, settings )
			elif CONF_VOICEMAIL_NAME and digit == MAIN_NAME:
				await self.admin_change_name( box, settings )
			elif digit == MAIN_PASSWORD:
				await self.admin_change_password( box, settings )
			else:
				await self.play_invalid_value( digit )
				digit = ''
	
	async def voice_deliver( self, box: int, msg: MSG, trusted: bool, settings: SETTINGS ) -> None:
		log = logger.getChild( 'ace_voicemail.Voicemail.voice_deliver' )
		
		x = TTS()
		x.say( 'You have a new message in your voicemail box number ' )
		x.digits( box )
		if trusted:
			x.say( '. To listen now, press any digit.' )
		else:
			x.say( '. To listen now, enter your pin number followed by pound.' )
		intro: str = str( await x.generate() )
		
		if trusted:
			max_attempts: int = 3
			digits: str = await self.play_menu([ intro ], max_attempts )
			if not digits:
				return
		else:
			if not await self.login( box, settings, [ intro ] ): # TODO FIXME: make this optional...
				return
		
		prevnext: bool = False
		digit: Opt[str] = await self.admin_listen_msg( msg, None, prevnext )
		
		msgs: List[MSG] = [ msg ]
		await self.admin_listen_finalize( msgs )
		
		if digit == LISTEN_MAIN_MENU:
			await self.admin_main_menu( box, settings )
	
	async def admin_listen_new( self, box: int, settings: SETTINGS ) -> None:
		await self.admin_listen( box, settings,
			'*-new.wav', 'urgent new', 'new', URGENT_NEW, NEW,
		)
	
	async def admin_listen_saved( self, box: int, settings: Opt[SETTINGS] ) -> None:
		await self.admin_listen( box, settings,
			'*-saved.wav', 'urgent saved', 'saved', URGENT_SAVED, SAVED,
		)
	
	def parse_recording_path( self, msgs_path: Path, file: str ) -> MSG:
		parts = file.split( '-' )
		msg = MSG(
			file = file,
			folder = msgs_path,
			path = msgs_path / file,
			box = int( parts[0] ),
			year = int( parts[1] ),
			month = int( parts[2] ),
			day = int( parts[3] ),
			hour = int( parts[4] ),
			minute = int( parts[5] ),
			second = int( parts[6] ),
			did = parts[7],
			ani = parts[8],
			uuid = parts[9],
			priority = cast( Literal['normal','urgent'], parts[10] ),
			status = cast( Literal['new','saved'], parts[11].split( '.', 1 )[0] ),
		)
		return msg
	
	async def _no_more_messages( self ) -> str:
		if self.use_tts:
			x = TTS()
			x.say( 'No more messages' )
			return str( await x.generate() )
		else:
			return NO_MORE_MESSAGES
	
	async def admin_listen( self,
		box: int,
		settings: Opt[SETTINGS],
		mask: str,
		urgent_x: str,
		nonurgent_x: str,
		URGENT_X: str,
		NONURGENT_X: str,
	) -> None:
		if settings is None:
			settings = await self.load_box_settings( box )
		msgs_path: Path = self.box_msgs_path( box )
		files: List[Path] = []
		async for file in util.glob( msgs_path, mask ):
			files.append( file )
		urgent: List[MSG] = []
		normal: List[MSG] = []
		sound: Opt[Any] = None
		
		# separate them into urgent vs non-urgent
		for file in files:
			msg = self.parse_recording_path( msgs_path, file.name )
			if msg.priority == 'urgent':
				urgent.append( msg )
			else:
				normal.append( msg )
		# put them back in single msgs list with urgent messages first
		msgs = list( itertools.chain( urgent, normal ))
		
		if self.use_tts:
			x = TTS()
			x.say( 'You have ' )
			x.digits( len( urgent ))
			x.say( f' {urgent_x} messages and ' )
			x.digits( len( normal ))
			x.say( f' {nonurgent_x} messages.' )
			intro: List[str] = [ str( await x.generate() )]
		else:
			intro = [
				YOU_HAVE,
			]
			intro.extend(
				number_audio( len( urgent ))
			)
			intro.extend([
				URGENT_X,
				MESSAGES, # MESSAGES2 here?
				AND,
			])
			intro.extend(
				number_audio( len( normal )),
			)
			intro.extend([
				NONURGENT_X,
				MESSAGES2, # MESSAGES here?
			])
		await self.play_menu( intro )
		
		if not msgs:
			menu = await self._for_the_main_menu_press()
			menu.append( SILENCE_3_SECONDS )
			digit1: str = ''
			while digit1 != LISTEN_MAIN_MENU:
				digit1 = await self.play_menu( menu ) # TODO FIXME: you have made an invalid selection...
				if digit1 == '': digit1 = await self.play_menu( intro )
			return #digit1 is not None
		
		msg_num: int = 1
		loop: bool = True
		while loop:
			msg = msgs[msg_num]
			
			prevnext: bool = True
			digit2: Opt[str] = await self.admin_listen_msg( msg, msg_num, prevnext )
			if digit2 is None: # session !ready
				loop = False
			elif digit2 == LISTEN_NEXT_MSG:
				if msg_num >= len( msgs ):
					msg_num = len( msgs )
					digit2 = await self.play_menu([ await self._no_more_messages() ])
					#if digit2 == '': # TODO FIXME: test if commenting this out is correct
					#	digit2 = await _menu()
				else:
					msg_num = msg_num + 1
			elif digit2 == LISTEN_PREV_MSG:
				if msg_num <= 1:
					msg_num = 1
					digit2 = await self.play_menu([ await self._no_more_messages() ])
					#if digit2 == '': # TODO FIXME: test if commenting this out is correct
					#	digit2 = await _menu()
				else:
					msg_num = msg_num - 1
			elif digit2 == LISTEN_MAIN_MENU:
				loop = False
		
		await self.admin_listen_finalize( msgs )
	
	async def admin_listen_msg( self, msg: MSG, msg_num: Opt[int], prevnext: bool ) -> Opt[str]:
		if msg.old_priority is None: msg.old_priority = msg.priority
		if msg.old_status is None: msg.old_status = msg.status
		
		envelope = None
		async def _envelope() -> List[str]:
			if self.use_tts:
				x = TTS()
				x.say( 'Message from ' )
				x.digits( msg.ani )
				return [ str( await x.generate() )]
			else:
				return list( itertools.chain(
					[ MESSAGE_FROM ],
					digits_audio( msg.ani ),
				))
		
		msgsounds: List[str] = []
		if msg_num is not None:
			if self.use_tts:
				x = TTS()
				x.say( 'Message number ' )
				x.digits( msg_num )
				msgsounds.append( str( await x.generate() ))
			else:
				msgsounds.append( MESSAGE_NUMBER )
				msgsounds.extend( number_audio( msg_num ))
		if msg.priority == 'urgent':
			if self.use_tts:
				x = TTS()
				x.say( 'urgent' )
				msgsounds.append( str( await x.generate() ))
			else:
				msgsounds.append( URGENT )
		if len( msgsounds ) > 0:
			msgsounds.append( SILENCE_1_SECOND )
		msgsounds.append( str( msg.path ))
		
		async def _menu() -> Opt[str]:
			menu: List[str] = []
			
			if msg.status != 'delete':
				if self.use_tts:
					x = TTS()
					x.say( 'To repeat this message, press ' )
					x.digits( LISTEN_REPEAT )
					x.say( '. To save this message, press ' )
					x.digits( LISTEN_SAVE )
					x.say( '.' )
					menu.append( str( await x.generate() ))
				else:
					menu.extend([
						TO_REPEAT_THIS_MESSAGE,
						PRESS,
						DIGITS[LISTEN_REPEAT],
						
						TO_SAVE_THIS_MESSAGE,
						PRESS,
						DIGITS[LISTEN_SAVE],
					])
			
			if msg.status == 'delete':
				if self.use_tts:
					x = TTS()
					x.say( 'To undelete this message, press ' )
					x.digits( LISTEN_UNDELETE )
					x.say( '.' )
					menu.append( str( await x.generate() ))
				else:
					menu.extend([
						TO_UNDELETE_THIS_MESSAGE,
						PRESS,
						DIGITS[LISTEN_UNDELETE],
					])
			else:
				if self.use_tts:
					x = TTS()
					x.say( 'To delete this message, press ' )
					x.digits( LISTEN_DELETE )
					x.say( '.' )
					menu.append( str( await x.generate() ))
				else:
					menu.extend([
						TO_DELETE_THIS_MESSAGE,
						PRESS,
						DIGITS[LISTEN_DELETE],
					])
				
				if msg.priority != 'urgent':
					if self.use_tts:
						x = TTS()
						x.say( 'To mark this message urgent, press ' )
						x.digits( LISTEN_MARK_URGENT )
						x.say( '.' )
						menu.append( str( await x.generate() ))
					else:
						menu.extend([
							TO_MARK_THIS_MESSAGE_URGENT,
							PRESS,
							DIGITS[LISTEN_MARK_URGENT],
						])
			
				if self.use_tts:
					x = TTS()
					x.say( 'To hear the message envelope, press ' )
					x.digits( LISTEN_ENVELOPE )
					x.say( '.' )
					menu.append( str( await x.generate() ))
				else:
					menu.extend([
						TO_HEAR_THE_MESSAGE_ENVELOPE,
						PRESS,
						DIGITS[LISTEN_ENVELOPE],
					])
			
			if prevnext:
				if self.use_tts:
					x = TTS()
					x.say( 'To play the next message, press ' )
					x.digits( LISTEN_NEXT_MSG )
					x.say( '. To play the previous message, press ' )
					x.digits( LISTEN_PREV_MSG )
					x.say( '.' )
					menu.append( str( await x.generate() ))
				else:
					menu.extend([
						TO_PLAY_THE_NEXT_MESSAGE,
						PRESS,
						DIGITS[LISTEN_NEXT_MSG],
						
						TO_PLAY_THE_PREVIOUS_MESSAGE,
						PRESS,
						DIGITS[LISTEN_PREV_MSG],
					])
			menu.extend( await self._for_the_main_menu_press() )
			
			x = TTS()
			x.say( 'If you are finished, simply hangup' )
			menu.append( str( await x.generate() ))
			
			menu.append( SILENCE_3_SECONDS )
			
			digit: Opt[str] = await self.play_menu( menu )
			return digit
		
		digit: Opt[str] = await self.play_menu( msgsounds )
		if digit is None:
			return None
		elif digit == '':
			digit = await _menu()
		
		_on_save: List[str] = []
		_on_delete: List[str] = []
		_on_undelete: List[str] = []
		_on_urgent: List[str] = []
		_on_new: List[str] = []
		
		idle_count:int = 0
		while True:
			if digit is None:
				return None
			elif digit == '':
				digit = await _menu()
			if digit == LISTEN_REPEAT:
				digit = await self.play_menu( msgsounds )
				# if they don't press anything, next loop will play menu again
			elif digit == LISTEN_SAVE:
				msg.status = 'saved'
				if not _on_save:
					if self.use_tts:
						x = TTS()
						x.say( 'Saved.' )
						_on_save = [ str( await x.generate() ), SILENCE_1_SECOND ]
					else:
						_on_save = [ SAVED, SILENCE_1_SECOND ]
				digit = await self.play_menu( _on_save )
				if digit == '':
					digit = await _menu()
			elif msg.status != 'delete' and digit == LISTEN_DELETE:
				msg.status = 'delete'
				if not _on_delete:
					if self.use_tts:
						x = TTS()
						x.say( 'Deleted.' )
						_on_delete = [ str( await x.generate() ), SILENCE_1_SECOND ]
					else:
						_on_delete = [
							DELETED,
							SILENCE_1_SECOND,
						]
				digit = await self.play_menu( _on_delete )
				if digit == '':
					digit = await _menu()
			elif msg.status == 'delete' and digit == LISTEN_UNDELETE:
				msg.status = msg.old_status
				if not _on_undelete:
					if self.use_tts:
						x = TTS()
						x.say( 'Undeleted.' )
						_on_undelete = [ str( await x.generate() ), SILENCE_1_SECOND ]
					else:
						_on_undelete = [ UNDELETED, SILENCE_1_SECOND ]
				digit = await self.play_menu( _on_undelete )
				if digit == '':
					digit = await _menu()
			elif digit == LISTEN_MARK_URGENT:
				msg.priority = 'urgent'
				if not _on_urgent:
					if self.use_tts:
						x = TTS()
						x.say( 'Marked urgent.' )
						_on_urgent = [ str( await x.generate() ), SILENCE_1_SECOND ]
					else:
						_on_urgent = [ MARKED_URGENT, SILENCE_1_SECOND ]
				digit = await self.play_menu( _on_urgent )
				if digit == '':
					digit = await _menu()
			elif digit == LISTEN_MARK_NEW:
				msg.status = 'new'
				if _on_new is None:
					if self.use_tts:
						x = TTS()
						x.say( 'Marked new.' )
						_on_new = [ await x.generate(), SILENCE_1_SECOND ]
					else:
						_on_new = [ MARKED_NEW, SILENCE_1_SECOND ]
				digit = await self.play_menu( _on_new )
				if digit == '':
					digit = await _menu()
			elif digit == LISTEN_ENVELOPE:
				if envelope is None:
					envelope = await _envelope()
				digit = await self.play_menu( envelope )
				if digit == '':
					digit = await _menu()
			elif prevnext and digit == LISTEN_NEXT_MSG:
				return digit
			elif prevnext and digit == LISTEN_PREV_MSG:
				return digit
			elif digit == LISTEN_MAIN_MENU:
				return digit
			elif digit != '':
				await self.play_invalid_value( digit )
				digit = ''
			elif digit == '':
				idle_count = idle_count + 1
				if idle_count >= 3:
					await self.goodbye()
					return None
	
	async def admin_listen_finalize( self, msgs: List[MSG] ) -> None:
		log = logger.getChild( 'Voicemail.admin_listen_finalize' )
		for msg in msgs:
			# TODO FIXME: may need to spawn a hook for any rename failures
			old_priority = msg.old_priority or msg.priority
			old_status = msg.old_status or msg.status
			if msg.priority != old_priority or msg.status != old_status:
				if msg.status == 'delete':
					log.debug( 'deleting %r', msg.path )
					try:
						await aiofiles.os.remove( msg.path )
					except Exception as e:
						log.warning( 'Error deleting %r: %r', msg.path, e )
				else:
					new_path = msg.to_path()
					log.warning( 'renaming %r to %r', str( msg.path ), str( new_path ))
					try:
						await aiofiles.os.rename( msg.path, new_path )
					except Exception as e:
						log.warning( 'Error renaming %r to %r: %r',
							str( msg.path ), str( new_path ), e
						)
	
	async def admin_greetings( self, box: int, settings: SETTINGS ) -> None:
		log = logger.getChild( 'Voicemail.admin_greetings' )
		if settings is None:
			settings = await self.load_box_settings( box )
		
		if self.use_tts:
			x = TTS()
			x.say( 'Choose a greeting between 1 and 9. To return to the previous menu, press star.' )
			menu: List[str] = [ str( await x.generate() ), SILENCE_3_SECONDS ]
		else:
			menu = [
				CHOOSE_A_GREETING_BETWEEN_1_AND_9,
				TO_RETURN_TO_THE_PREVIOUS_MENU,
				PRESS,
				STAR,
				SILENCE_3_SECONDS,
			]
		
		while True:
			digit: str = await self.play_menu( menu )
			if digit in '123456789':
				greeting = int( digit ) # TODO FIXME: ValueEror
				await self.admin_greeting( box, settings, greeting )
			elif digit == '*':
				log.info( 'box %r user cancelled with *', box )
				return
			else:
				await self.play_invalid_value( digit )
				digit = ''
	
	async def _error_greeting_file_missing( self ) -> str:
		if self.use_tts:
			x = TTS()
			x.say( 'Error, greeting file missing' )
			return str( await x.generate() )
		else:
			return ERROR
	
	async def record_greeting( self, box: int, settings: SETTINGS, greeting: int, path: Path ) -> bool:
		log = logger.getChild( 'Voicemail.record_greeting' )
		meta_path = self.box_meta_path( box )
		try:
			await util.mkdirp( meta_path )
		except Exception as e:
			log.error( 'Error creating %r: %r', str( meta_path ), e)
		async def _record() -> Path:
			tmp_uuid: str = str( uuid4() )
			tmp_path: Opt[Path] = self.box_greeting_path( box, f'-tmp-{tmp_uuid}' )
			assert tmp_path is not None # this should only happen if greeting == 0
			if self.use_tts:
				x = TTS()
				x.say( 'Record your greeting at the tone, press any key or stop talking to end the recording.' )
				stream: str = str( await x.generate() )
			else:
				stream = RECORD_YOUR_GREETING_AT_THE_TONE_PRESS_ANY_KEY_OR_STOP_TALKING_TO_END_THE_RECORDING
			_ = await self.play_menu([ stream, SILENCE_1_SECOND ])
			async for event in self.esl.playback( self.uuid, TONE ):
				self._on_event( event )
			
			log.debug( 'box %r RECORDING GREETING %r to %r',
				box, greeting, str( path ),
			)
			max_greeting_length = datetime.timedelta( seconds = settings.get( 'max_greeting_seconds' ) or 120 )
			silence_threshold: int = 30
			silence_seconds: int = 5
			async for event in self.esl.record( self.uuid, tmp_path, max_greeting_length, silence_threshold, silence_seconds ):
				self._on_event( event )
			log.debug( 'box %r RECORDED GREETING %r to %r',
				box, greeting, str( path )
			)
			return tmp_path
		
		async def _remove_tmp_path( tmp_path: Path ) -> None:
			log = logger.getChild( 'Voicemail.record_greeting._remove_tmp_path' )
			if tmp_path is not None and tmp_path.is_file():
				try:
					await aiofiles.os.remove( tmp_path )
				except Exception as e:
					log.error( 'box %r greeting %r error deleting tmp_path=%r: %s'
						, box, greeting, str( tmp_path ), e
					)
		
		tmp_path: Path = await _record()
		if self.use_tts:
			x = TTS()
			x.say( 'Press ' )
			x.digits( RECORD_SAVE )
			x.say( ' to save the greeting, press ' )
			x.digits( RECORD_REVIEW )
			x.say( ' to review, press ' )
			x.digits( RECORD_REDO )
			x.say( ' to re-record. To return to the previous menu, press ' )
			x.digits( RECORD_RETURN )
			menu: List[str] = [ str( await x.generate() )]
		else:
			menu = [
				PRESS_1_TO_SAVE_RECORDING_PRESS_2_TO_REVIEW_PRESS_3_TO_RERECORD,
				TO_RETURN_TO_THE_PREVIOUS_MENU,
				PRESS,
				DIGITS[RECORD_RETURN],
			]
		menu.append( SILENCE_3_SECONDS )
		
		digit: str = ''
		while True:
			if digit == '':
				digit = await self.play_menu( menu )
			if digit is None: # session went !ready...
				return False
			if digit == RECORD_SAVE:
				if path.is_file():
					try:
						await aiofiles.os.remove( path )
					except Exception as e1:
						log.error( 'record_greeting: box %r greeting %r unable to delete old greeting: %r'
							, box, greeting, e1
						)
				try:
					await aiofiles.os.rename( tmp_path, path )
				except Exception as e2:
					log.error( 'record_greeting: box %r greeting %r could not rename %r to %r: %r'
						, box, greeting, str( tmp_path ), str( path ), e2
					)
				return True
			elif digit == RECORD_REVIEW:
				stream: str = str( tmp_path )
				if not tmp_path.is_file():
					stream = await self._error_greeting_file_missing()
				_ = await self.play_menu([ stream, SILENCE_1_SECOND ])
				digit = ''
			elif digit == RECORD_REDO:
				await _remove_tmp_path( tmp_path )
				tmp_path = await _record()
				if tmp_path is None: return False
				digit = ''
			elif digit == RECORD_RETURN:
				await _remove_tmp_path( tmp_path )
				return True
			else:
				await self.play_invalid_value( digit )
	
	async def _an_error_has_occurred_please_contact_the_administrator( self ) -> str:
		if self.use_tts:
			x = TTS()
			x.say( 'An error has occurred, please contact the administrator' )
			return str( await x.generate() )
		else:
			return AN_ERROR_HAS_OCCURRED_PLEASE_CONTACT_THE_ADMINISTRATOR
	
	async def admin_greeting( self, box: int, settings: SETTINGS, greeting: int ) -> bool:
		log = logger.getChild( 'Voicemail.admin_greeting' )
		log.info( 'box %r greeting %r', box, greeting )
		assert greeting >= 1 and greeting <= 9
		path: Opt[Path] = self.box_greeting_path( box, greeting )
		assert path is not None
		if not path.is_file():
			log.info( 'box %r greeting %r greeting does not exist on entry - auto-recording 1st time', box, greeting )
			if not await self.record_greeting( box, settings, greeting, path ):
				log.info( 'box %r greeting %r session !ready during recording', box, greeting )
				return False
		
		if self.use_tts:
			x = TTS()
			x.say( 'To listen to greeting ' )
			x.digits( greeting )
			x.say( ', press ' )
			x.digits( GREETING_LISTEN )
			x.say( '. To re-record the greeting, press ' )
			x.digits( GREETING_RECORD )
			x.say( '. To make the greeting active, press ' )
			x.digits( GREETING_CHOOSE )
			x.say( '. To delete the greeting, press ' )
			x.digits( GREETING_DELETE )
			x.say( '. To return to the previos menu, press ' )
			x.digits( GREETING_RETURN )
			x.say( '.' )
			menu: List[str] = [ str( await x.generate() )]
		else:
			menu = [
				TO_LISTEN_TO_GREETING,
				DIGITS[str( greeting )],
				PRESS,
				DIGITS[GREETING_LISTEN],
				SILENCE_1_SECOND,
				
				TO_RECORD_A_GREETING,
				PRESS,
				DIGITS[GREETING_RECORD],
				SILENCE_1_SECOND,
				
				TO_CHOOSE_GREETING,
				PRESS,
				DIGITS[GREETING_CHOOSE],
				SILENCE_1_SECOND,
				
				TO_DELETE_GREETING,
				PRESS,
				DIGITS[GREETING_DELETE],
				SILENCE_1_SECOND,
				
				TO_RETURN_TO_THE_PREVIOUS_MENU,
				PRESS,
				DIGITS[GREETING_RETURN],
			]
		menu.append( SILENCE_3_SECONDS )
		
		digit: str = ''
		while True:
			if digit == '':
				digit = await self.play_menu( menu )
			if digit is None:
				log.info( 'box %r greeting %r session !ready during menu',
					box, greeting,
				)
				return False
			elif digit == GREETING_LISTEN:
				stream = str( path )
				if not path.is_file():
					stream = await self._error_greeting_file_missing()
				digit = await self.play_menu( [ stream, SILENCE_1_SECOND ])
			elif digit == GREETING_RECORD:
				if not await self.record_greeting( box, settings, greeting, path ):
					log.info( 'box %r greeting %r session !ready during recording',
						box, greeting
					)
					return False
				digit = ''
			elif digit == GREETING_CHOOSE:
				settings['greeting'] = int( greeting ) # TODO FIXME: ValueError
				await self.save_box_settings( box, settings )
				
				if self.use_tts:
					x = TTS()
					x.say( 'Greeting ' )
					x.digits( greeting )
					x.say( ' activated.' )
					playlist: List[str] = [ str( await x.generate() )]
				else:
					playlist = [
						GREETING,
						DIGITS[str( greeting )],
						SELECTED,
						SILENCE_1_SECOND,
					]
				playlist.append( SILENCE_1_SECOND )
				
				digit = await self.play_menu( playlist )
			elif digit == GREETING_DELETE:
				try:
					await aiofiles.os.remove( path )
				except Exception as e:
					log.error( 'Error trying to delete %r: %r',
						str( path ), e,
					)
					stream = await self._an_error_has_occurred_please_contact_the_administrator()
				else:
					if self.use_tts:
						x = TTS()
						x.say( 'Deleted.' )
						stream = str( await x.generate() )
					else:
						stream = DELETED
				digit = await self.play_menu([ stream, SILENCE_1_SECOND ])
			elif digit == GREETING_RETURN:
				log.info( 'box %r greeting %r user return to previous menu',
					box, greeting,
				)
				return True
			else:
				log.info( 'box %r greeting %r invalid digit=%r',
					box, greeting, digit,
				)
				await self.play_invalid_value( digit )
				digit = ''
		log.info( 'box %r greeting %r session went !ready during while loop',
			box, greeting,
		)
		return False
	
	async def admin_change_name( self, box: int, settings: SETTINGS ) -> bool:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.admin_change_name()' )
	
	async def admin_change_password( self, box: int, settings: SETTINGS ) -> bool:
		if self.use_tts:
			x = TTS()
			x.say( 'Please enter your new password and press pound,' )
			x.say( 'or to cancel press star.' )
			menu: List[str] = [ str( await x.generate() )]
		else:
			menu = [
				PLEASE_ENTER_YOUR_NEW_PASSWORD_THEN_PRESS_THE_POUND_KEY,
				SILENCE_1_SECOND,
				TO_EXIT,
				PRESS,
				DIGITS['*'],
			]
		menu.append( SILENCE_3_SECONDS )
		
		while True:
			#session:flushDigits()
			digits: Opt[str] = await self.play_pin( menu, '[\\d\\*]+' )
			if digits is None:
				return False
			elif '*' in digits:
				return True
			elif len( digits ) < self.min_pin_length:
				if self.use_tts:
					x = TTS()
					x.say( 'The password you entered is below the minimum length of ' )
					x.digits( self.min_pin_length )
					x.say( ', please try again' )
					playlist: List[str] = [ str( await x.generate() )]
				else:
					playlist = [
						THE_PIN_YOU_ENTERED_IS_BELOW_THE_MINIMUM_LENGTH,
						SILENCE_1_SECOND,
						THE_MINIMUM_PIN_LENGTH_IS,
						DIGITS[str( self.min_pin_length )],
						PLEASE_TRY_AGAIN,
					]
				digits = await self.play_menu( playlist )
			else:
				settings['pin'] = digits
				await self.save_box_settings( box, settings )
				
				if self.use_tts:
					x = TTS()
					x.say( 'Your password has been changed.' )
					stream: str = str( await x.generate() )
				else:
					stream = YOUR_PASSWORD_HAS_BEEN_CHANGED
				
				_ = await self.play_menu([ stream, SILENCE_1_SECOND ])
				return True
