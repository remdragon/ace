#region copyright


# This file is Copyright (C) 2022 ITAS Solutions LP, All Rights Reserved
# Contact ITAS Solutions LP at royce3@itas-solutions.com for licensing inquiries


#endregion copyright
#region imports


# stdlib imports:
from abc import ABCMeta, abstractmethod
import asyncio
import base64
from dataclasses import dataclass
import datetime
from enum import Enum
from itertools import chain
import json
import logging
from multiprocessing import Process
from mypy_extensions import TypedDict
from pathlib import Path
import re
import sys
import time
from typing import (
	Any, Awaitable, Callable, cast, Coroutine, Dict, List, Mapping as Map,
	Optional as Opt, Tuple, Type, TypeVar, Union,
)
from typing_extensions import Final, Literal # Python 3.7
import uuid

# 3rd-party imports:
import aiofiles # pip install aiofiles
import aiohttp # pip install aiohttp
import pydub # pip install pydub
if sys.platform != 'win32':
	from systemd.journal import JournaldLogHandler # pip install systemd

# local imports:
from ace_fields import Field
from ace_tod import match_tod
import ace_util as util
from ace_voicemail import Voicemail, MSG, SETTINGS, SILENCE_1_SECOND
import aiohttp_logging
from email_composer import Email_composer
from esl import ESL
import repo
import smtplib2
from tts import TTS, TTS_VOICES, tts_voices

if __name__ == '__main__':
	aiohttp_logging.monkey_patch()

#endregion imports
#region globals


logger = logging.getLogger( __name__ )

GOTO: Final = 'goto'
EXEC: Final = 'exec'
HUNT: Final = 'hunt'
EXECSTATE = Literal['goto','exec','hunt']

CONTINUE: Final = 'continue'
STOP: Final = 'stop'
RESULT = Literal['continue','stop']

ACE_STATE = 'ace-state'
STATE_RUNNING = 'running'
STATE_CONTINUE = 'continue'
STATE_KILL = 'kill'

class ACTION( TypedDict ):
	type: str
	name: Opt[str]

ACTIONS = List[ACTION]

class BRANCH( TypedDict ):
	name: str
	nodes: ACTIONS

BRANCHES = Dict[str,BRANCH]

class ACTION_ACD_CALL_ADD( ACTION ):
	gates: str
	priority: int
	queue_offset_seconds: int

class ACTION_ACD_CALL_GATE( ACTION ):
	gate: int
	priority: int

class ACTION_ACD_CALL_UNGATE( ACTION ):
	gate: int

class ACTION_ANSWER( ACTION ):
	pass

class ACTION_BRIDGE( ACTION ):
	dial_string: str

class ACTION_EMAIL( ACTION ):
	mailto: str
	body: str
	subject: str
	format: Literal['mp3','wav','-','']

class ACTION_GREETING( ACTION ):
	box: Union[int,str]
	greeting: Opt[str]

class ACTION_GOTO( ACTION ):
	destination: str

class ACTION_HANGUP( ACTION ):
	cause: util.CAUSE

class ACTION_IFNUM( ACTION ):
	lhs: Union[int,float,str]
	op: str
	rhs: Union[int,float,str]

class ACTION_IFSTR( ACTION ):
	lhs: str
	op: str
	rhs: str

class ACTION_IVR( ACTION ):
	terminators: str
	digit_regex: str
	variable_name: str
	branches: BRANCHES

class ACTION_LABEL( ACTION ):
	uuid: str

class ACTION_LOG( ACTION ):
	level: Literal['CONSOLE','ALERT','CRIT','ERR','WARNING','NOTICE','INFO','DEBUG']
	text: str

class ACTION_LUA( ACTION ):
	pass

class ACTION_LUAFILE( ACTION ):
	file: str

class ACTION_MOH( ACTION ):
	stream: str

class ACTION_PAGD( ACTION ):
	terminators: str
	digit_regex: str
	variable_name: str

class ACTION_PLAYBACK( ACTION ):
	sound: str

class ACTION_PLAYTTS( ACTION ):
	text: str
	voice: TTS_VOICES

class ACTION_PLAY_DTMF( ACTION ):
	dtmf: str

class ACTION_PREANNOUNCE( ACTION ):
	pass

class ACTION_PREANSWER( ACTION ):
	pass

class ACTION_PYTHON( ACTION ):
	pass

class ACTION_REPEAT( ACTION ):
	pass

class ACTION_RING( ACTION ):
	tone: str

class ACTION_ROUTE( ACTION ):
	pass

class ACTION_RXFAX( ACTION ):
	mailto: str

class ACTION_SET( ACTION ):
	variable: str
	value: str

class ACTION_SILENCE( ACTION ):
	seconds: Union[int,float]
	divisor: int # 0 == complete silence, >0 == comfort noise

class ACTION_SMS( ACTION ):
	pass

class ACTION_THROTTLE( ACTION ):
	pass

class ACTION_TOD( ACTION ):
	times: str
	hit: BRANCHES
	miss: BRANCHES

class ACTION_TONE( ACTION ):
	pass

class ACTION_TRANSFER( ACTION ):
	pass

class ACTION_VOICEMAIL( ACTION ):
	box: str
	greeting_override: str

class ACTION_VOICE_DELIVER( ACTION ):
	trusted: bool

class ACTION_WAIT( ACTION ):
	minutes: Union[int,str]
	seconds: Union[int,str]


@dataclass
class Config:
	repo_anis: repo.Repository
	repo_dids: repo.Repository
	repo_routes: repo.Repository
	did_fields: List[Field]
	flags_path: Path
	preannounce_path: Path
	vm_min_pin_length: int
	vm_box_path: Path
	vm_msgs_path: Path
	owner_user: str
	owner_group: str
	voice_deliver_ani: str
	
	# SMTP stuff:
	smtp_secure: Literal['yes','no','starttls']
	smtp_host: str
	smtp_port: Opt[int]
	smtp_timeout_seconds: int
	smtp_username: str
	smtp_password: str
	email_from: str
	
	# SMS stuff:
	sms_carrier: Literal['','thinq','twilio']
	sms_emulator: bool
	sms_thinq_account: str
	sms_thinq_username: str
	sms_thinq_api_token: str
	sms_thinq_from: str
	sms_twilio_account: str
	sms_twilio_sid: str
	sms_twilio_token: str
	sms_twilio_from: str
	
	# TTS stuff:
	vm_use_tts: bool
	aws_access_key: str
	aws_secret_key: str
	aws_region_name: str
	tts_location: Path
	tts_default_voice: TTS_VOICES


@dataclass
class PAGD:
	min_digits: int
	max_digits: int
	timeout: datetime.timedelta
	terminators: str
	digit_regex: str
	variable_name: str
	digit_timeout: datetime.timedelta
	
	digits: Opt[str] = None
	valid: Opt[bool] = None


class ElapsedTimer:
	def __init__( self, interval: Opt[datetime.timedelta] ) -> None:
		self.interval = interval
		self.t1: float = time.time() + interval.total_seconds() if interval else 0
	
	def elapsed( self ) -> bool:
		now: float = time.time()
		if self.interval is None or now < self.t1:
			return False
		self.t1 += self.interval.total_seconds()
		return True

D = TypeVar( 'D' )
T = TypeVar( 'T' )
K = TypeVar( 'K' )
V = TypeVar( 'V' )

def expect( type: Type[T], value: Opt[T], *, default: Opt[T] = None ) -> T:
	if value is None and default is not None:
		return default
	if isinstance( value, type ):
		return value
	raise ValueError( f'expecting {type.__module__}.{type.__qualname__} but got {value!r}' )

class ChannelHangup( Exception ):
	pass

def _on_event( event: ESL.Message ) -> None:
	log = logger.getChild( '_on_event' )
	evt_name = event.event_name
	if evt_name == 'CHANNEL_HANGUP':
		uuid = event.header( 'Unique-ID' )
		raise ChannelHangup( uuid )
	else:
		log.debug( 'ignoring event %r', evt_name )

def valid_route( x: Any ) -> bool:
	return isinstance( x, int )

def expired( expiration: str ) -> bool:
	#log = logger.getChild( 'expired' )
	if not expiration:
		return False
	now = datetime.datetime.now().strftime( '%Y-%m-%d %H:%M:%S' )
	#log.debug( 'comparing now=%r vs expiration=%r', now, expiration )
	return now >= expiration


#endregion globals
#region State


class State( metaclass = ABCMeta ):
	config: Config
	repo_anis: repo.AsyncRepository
	repo_dids: repo.AsyncRepository
	repo_routes: repo.AsyncRepository
	
	# operational values:
	route: int
	goto_uuid: Opt[str] = None
	
	def __init__( self, esl: ESL ) -> None:
		self.esl = esl
		self.state = EXEC
	
	@abstractmethod
	async def can_continue( self ) -> bool:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.can_continue()' )
	
	async def expand( self, s: str ) -> str:
		log = logger.getChild( 'State.expand' )
		log.debug( 'input=%r', s )
		if s:
			ar: List[str] = re.split( r'\$\${([^}]+)}', s )
			for i in range( 1, len( ar ), 2 ):
				r1 = await self.esl.global_getvar( ar[i] )
				ar[i] = r1.value
			s = ''.join( ar )
			ar = re.split( r'\${([^}]+)}', s )
			
			if isinstance( self, CallState ):
				# call context
				for i in range( 1, len( ar ), 2 ):
					r2 = await self.esl.uuid_getvar( self.uuid, ar[i] )
					ar[i] = r2 or ''
			elif isinstance( self, NotifyState ):
				# voicemail notify context
				for i in range( 1, len( ar ), 2 ):
					r3 = getattr( self.msg, ar[i], '' )
					ar[i] = str( r3 ) if r3 is not None else ''
			else:
				assert False, f'invalid state={self!r}'
			s = ''.join( ar )
		log.debug( 'output=%r', s )
		return s
	
	async def tonumber( self, data: Map[str,Any], name: str, *, expand: bool = False, default: Opt[Union[int,float]] = None ) -> Union[int,float]:
		value = data.get( name )
		if value is None:
			if default is not None:
				return default
		else:
			if expand:
				value = await self.expand( str( value ))
			try:
				return int( value )
			except ValueError:
				pass
			try:
				return float( value )
			except ValueError:
				pass
		raise ValueError( f'Expecting {name!r} of type convertable to int/float but got {value!r}' )
	
	async def toint( self, data: Map[str,Any], name: str, *, expand: bool = False, default: Opt[int] = None ) -> int:
		value = data.get( name )
		if value is None:
			if default is not None:
				return default
		else:
			if expand:
				value = await self.expand( str( value ))
			try:
				return int( value )
			except ValueError:
				pass
		raise ValueError( f'Expecting {name!r} of type convertable to int/float but got {value!r}' )
	
	async def load_route( self, route: int ) -> Dict[str,Any]:
		return await self.repo_routes.get_by_id( route )
	
	async def exec_branch( self, action: ACTION, which: str, pagd: Opt[PAGD], *, log: logging.Logger ) -> RESULT:
		branch: BRANCH = cast( BRANCH, expect( dict, action.get( which ), default = {} ))
		return await self._exec_branch( which, branch, pagd, log = log )
	
	async def _exec_branch( self, which: str, branch: BRANCH, pagd: Opt[PAGD], *, log: logging.Logger ) -> RESULT:
		name: Opt[str] = branch.get( 'name' )
		nodes: ACTIONS = expect( list, branch.get( 'nodes' ) or [] )
		if which:
			log.info( 'executing %s branch %r', which, name )
		return await self.exec_actions( nodes, pagd )
	
	async def exec_actions( self, actions: ACTIONS, pagd: Opt[PAGD] = None ) -> RESULT:
		for action in actions or []:
			r = await self.exec_action( action, pagd )
			if r != CONTINUE: return r
			if pagd and pagd.digits: return CONTINUE
		return CONTINUE
	
	async def exec_action( self, action: ACTION, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.exec_action' )
		action_type = expect( str, action.get( 'type' ), default = '' )
		if not action_type:
			log.error( 'action.type is missing' ) # TODO FIXME: diagnostic info?
			return CONTINUE
		fname = f'action_{action_type}'
		f: Opt[Callable[[ACTION,Opt[PAGD]],Awaitable[RESULT]]] = getattr( self, fname, None )
		if not f or not callable( f ):
			log.error( 'action invalid or unavailable in this context: %r', action_type )
			return CONTINUE
		log.debug( 'executing %r', fname )
		r = await f( action, pagd )
		log.debug( '%s -> %r', fname, r )
		if r not in ( CONTINUE, STOP ):
			log.error( '%s returned %r but should have returned %r or %r',
				fname, r, CONTINUE, STOP,
			)
			r = CONTINUE # assume CONTINUE for now..
		if r == CONTINUE:
			if not await self.can_continue():
				return STOP
		return r
	
	async def exec_top_actions( self, actions: ACTIONS ) -> RESULT:
		log = logger.getChild( 'State.exec_top_actions' )
		while True:
			r = await self.exec_actions( actions )
			if self.state == GOTO:
				self.state = HUNT
			else:
				return r
	
	async def action_goto( self, action: ACTION_GOTO, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_goto' )
		if self.state == HUNT: return CONTINUE
		
		self.goto_uuid = expect( str, action.get( 'destination' ))
		log.info( 'destination=%r', self.goto_uuid )
		self.state = GOTO
		return STOP
	
	async def action_ifnum( self, action: ACTION_IFNUM, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_ifnum' )
		
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'trueBranch', pagd, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'falseBranch', pagd, log = log )
		
		lhs: Union[int,float] = await self.tonumber( action, 'lhs', expand = True )
		op: str = await self.expand( expect( str, action.get( 'op' )))
		rhs: Union[int,float] = await self.tonumber( action, 'rhs', expand = True )
		
		result: Opt[bool] = None
		if op == '<=':
			result =( lhs <= rhs )
		elif op == '<':
			result =( lhs < rhs )
		elif op == '=':
			result =( lhs == rhs )
		elif op == '!=':
			result =( lhs != rhs )
		elif op == '>':
			result =( lhs > rhs )
		elif op == '>=':
			result =( lhs >= rhs )
		else:
			result = False
			log.warning( 'invalid op=%r, defaulting to %r', op, result )
		log.info( 'lhs=%r op=%r rhs=%r result=%r', lhs, op, rhs, result )
		
		which = 'trueBranch' if result else 'falseBranch'
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def action_ifstr( self, action: ACTION_IFSTR, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_ifstr' )
		
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'trueBranch', pagd, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'falseBranch', pagd, log = log )
		
		lhs: str = await self.expand( expect( str, action.get( 'lhs' )))
		op: str = await self.expand( expect( str, action.get( 'op' )))
		rhs: str = await self.expand( expect( str, action.get( 'rhs' )))
		if not expect( bool, action.get( 'case' ), default = False ):
			lhs = lhs.lower()
			rhs = rhs.lower()
		
		result: Opt[bool] = None
		if op == '<=':
			result =( lhs <= rhs )
		elif op == '<':
			result =( lhs < rhs )
		elif op == '=':
			result =( lhs == rhs )
		elif op == '!=':
			result =( lhs != rhs )
		elif op == '>':
			result =( lhs > rhs )
		elif op == '>=':
			result =( lhs >= rhs )
		elif op == 'begins-with':
			result = lhs.startswith( rhs )
		elif op == 'contains':
			result =( rhs in lhs )
		elif op == 'ends-with':
			result = lhs.endswith( rhs )
		else:
			result = False
			log.warning( 'invalid op=%r, defaulting to %r', op, result )
		log.info( 'lhs=%r op=%r rhs=%r result=%r', lhs, op, rhs, result )
		
		which = 'trueBranch' if result else 'falseBranch'
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def action_label( self, action: ACTION_LABEL, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_label' )
		try:
			label_uuid = action['uuid']
		except KeyError:
			log.error( 'label missing "uuid"' )
		else:
			if self.state == HUNT and self.goto_uuid == label_uuid:
				log.info( 'HIT name=%r', action.get( 'name' ))
				self.state = EXEC
			else:
				log.info( 'PASS name=%r', action.get( 'name' ))
		return CONTINUE
	
	async def action_log( self, action: ACTION_LOG, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_log' )
		if self.state == HUNT: return CONTINUE
		
		raise NotImplementedError( 'how to invoke freeswitch logging via ESL?' )
		#level
		#level = getattr( logging, action.get( 'level' ) or 'DEBUG', logging.DEBUG )
		#text = await self.expand( action.get( 'text' ) or '?' )
		#log.log( level, text )
		
		return CONTINUE
	
	async def action_lua( self, action: ACTION_LUA, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_lua' )
		if self.state == HUNT: return CONTINUE
		
		#source = ( action.get( 'source' ) or '' ).strip()
		#if not source:
		#	log.error( 'cannot execute lua code: source is empty' )
		#	return CONTINUE
		
		log.error( 'TODO FIXME: inline lua not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_laufile( self, action: ACTION_LUAFILE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_luafile' )
		if self.state == HUNT: return CONTINUE
		
		file = ( action.get( 'file' ) or '' ).strip()
		if not file:
			log.error( 'cannot execute lua file: no filename provided' ) # TODO FIXME: log some of this stuff to freeswitch console?
			return CONTINUE
		
		log.error( 'TODO FIXME: lua file not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_python( self, action: ACTION_PYTHON, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_python' )
		if self.state == HUNT: return CONTINUE
		
		log.error( 'TODO FIXME: python not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_repeat( self, action: ACTION_REPEAT, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_repeat' )
		count: int = await self.toint( action, 'count', default = 0 )
		nodes = cast( ACTIONS, expect( list, action.get( 'nodes' ), default = [] ))
		i: int = 0
		while count == 0 or i < count:
			if self.state != HUNT:
				log.info( 'starting loop %r of %s', i, count or 'infinite' )
			if STOP == await self.exec_actions( nodes ):
				return STOP
			if self.state == HUNT: return CONTINUE
			i += 1
		return CONTINUE
	
	async def _sms_thinq( self, smsto: str, message: str ) -> RESULT:
		log = logger.getChild( 'State._sms_thinq' )
		
		url = f'https://api.thinq.com/account/{self.config.sms_thinq_account}/product/origination/sms/send'
		if self.config.sms_emulator: # enable this for testing with sms_emulators.py
			url = 'http://127.0.0.1:8080/thinq/send'
		auth = base64.b64encode(
			f'{self.config.sms_thinq_username}:{self.config.sms_thinq_api_token}'.encode( 'utf-8' )
		).decode( 'us-ascii' )
		
		headers = {
			'Authorization': 'Basic {auth}',
		}
		formdata = {
			'from_did': self.config.sms_thinq_from,
			'to_did': smsto,
			'message': message,
		}
		async with aiohttp.ClientSession() as session:
			async with session.post( url, headers = headers, data = formdata ) as rsp:
				try:
					text = await rsp.text()
				except Exception as e1:
					log.error( 'sms to %r failure: %r', e1 )
				try:
					jdata = json.loads( text ) # TODO FIXME: json decoding failure
				except Exception as e2:
					log.error( 'sms to %r failure: %r decoding json=%r', smsto, e2, text )
				guid = jdata.get( 'guid' ) if isinstance( jdata, dict ) else None
				if guid:
					log.info( 'sms to %r success (guid=%r)', smsto, guid )
				else:
					log.error( 'sms to %r failure: %r', smsto, jdata )
		return CONTINUE
	
	async def _sms_twilio( self, smsto: str, message: str ) -> RESULT:
		log = logger.getChild( 'State._sms_twilio' )
		
		url = f'https://api.twilio.com/2010-04-01/Accounts/{self.config.sms_twilio_account}/Messages.json'
		if self.config.sms_emulator: # enable this for testing with sms_emulators.py
			url = 'http://127.0.0.1:8080/twilio/send'
		auth = base64.b64encode(
			f'{self.config.sms_twilio_sid}:{self.config.sms_twilio_token}'.encode( 'utf-8' )
		).decode( 'us-ascii' )
		
		headers = {
			'Authorization': 'Basic {auth}',
		}
		formdata = {
			'From': self.config.sms_thinq_from,
			'To': f'+1{smsto}',
			'Body': message,
		}
		async with aiohttp.ClientSession() as session:
			async with session.post( url, headers = headers, data = formdata ) as rsp:
				try:
					text = await rsp.text()
				except Exception as e1:
					log.error( 'sms to %r failure: %r', e1 )
				try:
					jdata = json.loads( text ) # TODO FIXME: json decoding failure
				except Exception as e2:
					log.error( 'sms to %r failure: %r decoding json=%r', smsto, e2, text )
				status = jdata.get( 'status' )
				if status == 'queued':
					log.info( 'sms to %r success: status=%r', smsto, status )
				else:
					errmsg = jdata.get( 'message' )
					if errmsg:
						log.error( 'sms to %r failure: %r %r', smsto, status, errmsg )
					else:
						log.error( 'sms to %r failure: %r', smsto, jdata )
		return CONTINUE
	
	async def action_sms( self, action: ACTION_SMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_sms' )
		if self.state == HUNT: return CONTINUE
		
		smsto: str = str( action.get( 'smsto' ) or '' ).strip() # TODO FIXME: thinq expects 'XXXXXXXXXX'
		message: str = str( action.get( 'message' ) or '' ).strip()
		if not message:
			settings = cast( Opt[SETTINGS], getattr( self, 'settings', None ))
			message = ( settings.get( 'default_sms_message' ) if settings else '' ) or 'You have a new voicemail'
		
		message = message.replace( '\n', '\\n' )
		message = await self.expand( message )
		
		if not smsto:
			log.warning( 'cannot send sms - no recipient' )
			return CONTINUE
		
		if self.config.sms_carrier == 'thinq':
			return await self._sms_thinq( smsto, message )
		elif self.config.sms_carrier == 'twilio':
			return await self._sms_twilio( smsto, message )
		else:
			log.error( 'cannot send sms, invalid sms_carrier=%r', self.config.sms_carrier )
			return CONTINUE
	
	async def action_tod( self, action: ACTION_TOD, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_tod' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'hit', pagd, log = log ):
				return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'miss', pagd, log = log )
		
		which = 'miss'
		if match_tod( expect( str, action.get( 'times' ))):
			# make sure holiday params match too
			log.warning( 'TODO FIXME: implement holidays' )
			which = 'hit'
		
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def action_wait( self, action: ACTION_WAIT, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_wait' )
		if self.state == HUNT: return CONTINUE
		
		minutes: int = await self.toint( action, 'minutes', default = 0 )
		seconds = minutes * 60 + await self.toint( action, 'seconds', default = 0 )
		
		if isinstance( self, CallState ) and pagd is not None:
			params2 = ACTION_SILENCE(
				type = 'silence',
				name = '',
				seconds = seconds,
				divisor = 0,
			)
			log.info( 'executing silence instead (b/c pagd is active)' )
			return await self.action_silence( params2, pagd )
		else:
			log.info( 'waiting for %r second(s)', seconds )
			await asyncio.sleep( seconds )
		
		return CONTINUE


#endregion State
#region CallState


class CallState( State ):
	uuid: str
	box: Opt[int] = None # set to an integer if we're inside of a specific voicemail box
	hangup_on_exit: bool = True
	
	def __init__( self, esl: ESL, uuid: str, did: str, ani: str ) -> None:
		super().__init__( esl )
		self.uuid = uuid
		self.did = did
		self.ani = ani
	
	async def can_continue( self ) -> bool:
		log = logger.getChild( 'CallState.can_continue' )
		if not await self.esl.uuid_exists( self.uuid ):
			log.debug( 'uuid_exists -> false' )
			return False
		if await self.esl.uuid_getvar( self.uuid, 'bridge_uuid' ):
			log.debug( 'bridge_uuid ~= nil' )
			return False
		return True
	
	async def try_ani( self ) -> Opt[Union[int,str]]:
		log = logger.getChild( 'CallState.try_ani' )
		
		try:
			data = await self.repo_anis.get_by_id( self.ani )
		except repo.ResourceNotFound as e:
			log.debug( 'no config found for ani %r', self.ani )
			return None
		
		# first check for DID overrides
		overrides = str( data.get( 'overrides' ) or '' )
		for override in overrides.split( '\n' ):
			#log.debug( 'override=' .. override )
			override, _, comment = map( str.strip, override.partition( '#' ))
			#log.debug( 'override=' .. override .. ', comment=' .. comment )
			did2, _, override = map( str.strip, override.partition( ' ' ))
			if did2 == self.did:
				#log.debug( 'matched did2=' .. did2 )
				route_, _, exp = map( str.strip, override.partition( ' ' ))
				#log.debug( 'route=%r, exp=%r', route_, exp )
				if not expired( exp ):
					log.debug( 'ani=%r did=%r -> route=%r', self.ani, self.did, route_ )
					await self.esl.uuid_setvar( self.uuid, 'route', route_ )
					try:
						return int( route_ )
					except ValueError:
						log.warning( 'unable to convert route %r to an integer', route_ )
			#else:
			#	log.debug( 'ignoring did2=' .. did2 )
		
		route = cast( Opt[int], data.get( 'route' ))
		if isinstance( route, int ):
			log.debug( 'ani=%r did=* -> route=%r', self.ani, route )
			await self.esl.uuid_setvar( self.uuid, 'route', str( route ))
			return route
		elif route is not None:
			log.warning( 'invalid route=%r', route )
		
		return None
	
	async def try_did( self ) -> Tuple[Opt[Union[int,str]],Opt[Dict[str,Any]]]:
		log = logger.getChild( 'CallState.try_did' )
		try:
			data = await self.repo_dids.get_by_id( self.did )
		except repo.ResourceNotFound as e:
			log.debug( 'no config found for did %r', self.did )
			return None, None
		
		route: Opt[Union[int,str]] = data.get( 'route' ) or None
		log.debug( 'route=%r', route )
		if route is not None:
			await self.esl.uuid_setvar( self.uuid, 'route', str( route ))
		
		for fld in self.config.did_fields:
			value = str( data.get( fld.field ) or '' ).strip()
			if value is not None:
				log.debug( 'setting field %r to %r', fld.field, value )
				await self.esl.uuid_setvar( self.uuid, fld.field, value )
			#else:
			#	log.debug( 'skipping field %r b/c value %r', fld.field, value )
		
		variables = str( data.get( 'variables' ) or '' )
		for variable in variables.split( '\n' ):
			field, _, value = map( str.strip, variable.partition( '=' ))
			if field and value:
				log.debug( 'setting variable %r to %r', field, value )
				await self.esl.uuid_setvar( self.uuid, field, value )
		return route, data
	
	async def load_flag( self, flag_name: str ) -> Opt[str]:
		flag_path = self.config.flags_path / f'{flag_name}.flag'
		try:
			async with aiofiles.open( str( flag_path ), 'r' ) as f:
				flag = await f.read()
		except FileNotFoundError as e:
			raise repo.ResourceNotFound( str( flag_path )).with_traceback( e.__traceback__ ) from None
		return flag.strip() or None
	
	async def try_wav( self, filename: str ) -> bool:
		log = logger.getChild( 'CallState.try_wav' )
		path = self.config.preannounce_path / f'{filename}.wav'
		if not path.is_file():
			log.debug( 'path not found: %r', str( path ))
			return False
		log.debug( 'found path: %r', str( path ))
		await self.esl.uuid_setvar( self.uuid, 'preannounce_wav', str( path ))
		return True
	
	async def set_preannounce( self, didinfo: Dict[str,Any] ) -> None:
		log = logger.getChild( 'CallState.set_preannounce' )
		preannounce = 'default.wav'
		
		global_flag = await self.load_flag( 'global_flag' )
		
		if global_flag:
			if await self.try_wav( f'global_{global_flag}' ):
				return
		
		category = ( didinfo.get( 'category' ) or '' ).strip()
		if category:
			cat_flag = await self.load_flag( f'category_{category}' )
			if cat_flag:
				if await self.try_wav( f'category_{category}_{cat_flag}' ):
					return
		
		did_flag = ( didinfo.get( 'flag' ) or '' ).strip()
		if did_flag:
			if await self.try_wav( f'{self.did}_{did_flag}' ):
				return
		
		#holiday = holidays.today()
		#if holiday ~= nil then
		#	holname = string.upper( holiday.name )
		#	holname = holname:gsub( ' ', '' )
		#	if await self.try_wav( uuid, did .. '_' .. holname ) then return end
		#	if await self.try_wav( uuid, did .. '_HOLIDAY' ) then return end
		#else
		#	log.debug( 'not a holiday' )
		#end
		
		async def _uuid_getint( key: str, default: int ) -> int:
			value = await self.esl.uuid_getvar( self.uuid, key )
			if value is None:
				return default
			try:
				return int( value )
			except ValueError as e:
				log.warning( 'Could not convert %r value %r to int: %r', key, value, e )
				return default
		
		# BEGIN bushrs stuff
		# DOW table: Sun=1 Mon=2 Tue=3 Wed=4 Thu=5 Fri=6 Sat=7
		bushrs_start = await _uuid_getint( 'bushrs_start', 8 )
		bushrs_end = await _uuid_getint( 'bushrs_end', 17 )
		bushrs_dow = await self.esl.uuid_getvar( self.uuid, 'bushrs_dow' ) or '23456' # M-F
		now = datetime.datetime.now()
		now_dow = str(( now.weekday() + 1 ) % 7 + 1 ) # now.weekday() MON=0 ... SUN=6, we need SUN=1 ... SAT=7
		log.debug( 'bushrs_dow=%r, now_dow=%r', bushrs_dow, now_dow )
		tod = 'AFTHRS'
		if now_dow in bushrs_dow:
			if now.hour >= bushrs_start and now.hour < bushrs_end:
				tod = 'BUSHRS'
			else:
				log.debug( 'hour mismatch' )
		else:
			log.debug( 'dow mismatch' )
		
		if await self.try_wav( f'{self.did}_{tod}' ):
			return
		
		if await self.try_wav( str( self.did )):
			return
		
		if await self.try_wav( 'default' ):
			return
		
		log.debug( 'no preannounce recording found' )
	
	async def _pagd( self, action: Union[ACTION_IVR,ACTION_PAGD], success: Callable[[str],Coroutine[Any,Any,Opt[RESULT]]] ) -> RESULT:
		log = logger.getChild( 'CallState._pagd' )
		timeout = datetime.timedelta( seconds = await self.tonumber( action, 'timeout', default = 3 ))
		pagd = PAGD(
			min_digits = await self.toint( action, 'min_digits', default = 1 ),
			max_digits = await self.toint( action, 'max_digits', default = 1 ),
			timeout = datetime.timedelta( milliseconds = 50 ), # don't want to apply pagd.timeout to every node under greeting branch
			terminators = expect( str, action.get( 'terminators' ), default = '' ),
			digit_regex = expect( str, action.get( 'digit_regex' ), default = '' ),
			variable_name = expect( str, action.get( 'variable_name' ), default = '' ),
			digit_timeout = datetime.timedelta( seconds = await self.tonumber( action, 'digit_timeout', default = timeout.total_seconds() ))
		)
		max_attempts = await self.toint( action, 'max_attempts', default = 3 )
		attempt: int = 1
		r: RESULT
		while attempt <= max_attempts:
			if not pagd.digits:
				r = await self.exec_branch( action, 'greetingBranch', pagd, log = log )
				if r == STOP: return STOP
				if not pagd.digits:
					r = await self.action_silence( ACTION_SILENCE(
						type = 'silence',
						name = '',
						seconds = 3,
						divisor = 0,
					), pagd )
					log.info( 'back from post-greeting auto-silence with r=%r, digits=%r, valid=%r',
						r, pagd.digits, pagd.valid
					)
					if r == STOP: return STOP
			else:
				log.info( 'skipped greeting branch because digits=%r, valid=%r',
					pagd.digits, pagd.valid,
				)
			
			if pagd.digits and pagd.valid:
				result = await success( pagd.digits )
				if result is not None:
					return result
			if attempt < max_attempts:
				if pagd.digits:
					pagd.digits = None
					r = await self.exec_branch( action, 'invalidBranch', pagd, log = log )
					if r == STOP: return STOP
				else:
					r = await self.exec_branch( action, 'timeoutBranch', pagd, log = log )
					if r == STOP: return STOP
			else:
				r = await self.exec_branch( action, 'failureBranch', None, log = log )
				return r
			attempt += 1
		return CONTINUE

	async def _playback( self, sound: str, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState._playback' )
		if pagd is not None:
			min_digits = pagd.min_digits
			max_digits = pagd.max_digits
			max_attempts = 1
			timeout = pagd.timeout
			terminators = pagd.terminators
			error = ''
			digit_regex = ''
			variable_name = pagd.variable_name
			digit_timeout = pagd.digit_timeout
			
			if min_digits < 1:
				min_digits = 1
			if max_digits < 1:
				max_digits = 1
			if timeout.total_seconds() <= 0:
				timeout = datetime.timedelta( seconds = 0.1 ) # FS defaults 0 to some greater timeout value
			
			#session:flushDigits()
			log.info( 'executing playAndGetDigits mindig=%r maxdig=%r #atts=%r timeout=%r term=%r snd=%r err=%r re=%r var=%r dig_timeout=%r',
				min_digits,
				max_digits,
				max_attempts,
				timeout,
				terminators,
				sound,
				error,
				digit_regex,
				variable_name,
				digit_timeout
			)
			digits_: List[str] = []
			async for event in self.esl.play_and_get_digits( self.uuid,
				min_digits = min_digits,
				max_digits = max_digits,
				tries = max_attempts,
				timeout = timeout,
				terminators = terminators,
				file = sound,
				invalid_file = error,
				var_name = variable_name,
				regexp = digit_regex,
				digit_timeout = digit_timeout,
				digits = digits_,
			):
				_on_event( event )
			pagd.digits = ''.join( digits_ )
			log.info( 'got digits=%r', pagd.digits )
			
			pagd.valid = True
			if pagd.digit_regex:
				log.debug( 'call regex( %r, %r )', pagd.digits, pagd.digit_regex )
				pagd.valid = await self.esl.regex( pagd.digits, pagd.digit_regex )
			
			log.info( 'got digits=%r valid=%r', pagd.digits, pagd.valid )
			return CONTINUE
		else:
			log.debug( 'executing break all' )
			await self.esl.uuid_break( self.uuid, 'all' )
			
			log.info( 'executing playback %r', sound )
			async for event in self.esl.playback( self.uuid, sound ):
				_on_event( event )
			
			return CONTINUE
	
	async def action_acd_call_add( self, action: ACTION_ACD_CALL_ADD, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_add' )
		if self.state == HUNT: return CONTINUE
		
		gates: str = expect( str, action.get( 'gates' ))
		priority: int = await self.toint( action, 'priority' )
		queue_offset_seconds: int = await self.toint( action, 'queue_offset_seconds', default = 0 )
		
		r = await self.esl.luarun(
			'itas/acd.lua',
			'call',
			'add',
			self.uuid,
			self.did,
			gates,
			str( priority ),
			str( queue_offset_seconds ),
		)
		log.debug( 'result: %r', r )
		
		return CONTINUE
	
	async def action_acd_call_gate( self, action: ACTION_ACD_CALL_GATE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_gate' )
		if self.state == HUNT: return CONTINUE
		
		gate: str = str( action.get( 'gate' ) or '' )
		priority: int = await self.toint( action, 'priority' )
		
		r = await self.esl.luarun(
			'itas/acd.lua',
			'call',
			'gate',
			self.uuid,
			gate,
			str( priority ),
		)
		log.debug( 'result: %r', r )
		
		return CONTINUE
	
	async def action_acd_call_ungate( self, action: ACTION_ACD_CALL_UNGATE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_ungate' )
		if self.state == HUNT: return CONTINUE
		
		gate: str = str( action.get( 'gate' ) or '' )
		
		r = await self.esl.luarun(
			'itas/acd.lua',
			'call',
			'ungate',
			self.uuid,
			gate,
		)
		log.debug( 'result: %r', r )
		
		return CONTINUE
	
	async def action_answer( self, action: ACTION_ANSWER, pagd: Opt[PAGD] ) -> RESULT:
		#log = logger.getChild( 'CallState.action_answer' )
		if self.state == HUNT: return CONTINUE
		
		if not await util.answer( self.esl, self.uuid, 'ace_eso.CallState.action_answer' ):
			return STOP
		
		return CONTINUE
	
	async def _bridge( self, action: ACTION_BRIDGE ) -> str:
		log = logger.getChild( 'CallState._bridge' )
		
		timeout_seconds: int = await self.toint( action, 'timeout', default = 0 )
		timeout: Opt[datetime.timedelta] = (
			datetime.timedelta( seconds = timeout_seconds )
			if timeout_seconds
			else None
		)
		
		bridge_uuid: str = str( uuid.uuid4() )
		try:
			await self.esl.filter( 'Unique-ID', bridge_uuid )
		except Exception:
			log.exception( 'Unable to filter for bridge_uuid: %r' )
			return '-ERR filter failed'
		
		originate_timeout: Opt[Union[int,float]] = (
			time.time() + timeout.total_seconds()
			if timeout is not None
			else None
		)
		originate_timer = ElapsedTimer( timeout )
		exists_timer = ElapsedTimer( datetime.timedelta( seconds = 6 ))
		
		try:
			dial_string: str = expect( str, action.get( 'dial_string' ))
			chanvars = { 'origination_uuid': bridge_uuid }
			origin = '&playback(silence_stream://-1)'
			dialplan = str( action.get( 'dialplan' ) or '' )
			context = str( action.get( 'context' ) or '' )
			cid_name = str( action.get( 'cid_name' ) or '' )
			cid_num = str( action.get( 'cid_num' ) or '' )
			
			try:
				r = await self.esl.originate( dial_string,
					origin = origin,
					dialplan = dialplan,
					context = context,
					cid_name = cid_name,
					cid_num = cid_num,
					timeout = timeout,
					chanvars = chanvars,
					expand = True,
					bgapi = True,
				)
			except Exception:
				log.exception( 'Error trying to originate for bridge:' )
				return '-ERR originate failed'
			log.debug( 'originate -> %r', r )
			
			terminators = ( 'CHANNEL_DESTROY', 'CHANNEL_HANGUP', 'CHANNEL_UNBRIDGE' )
			
			answered = False
			while not answered:
				async for event in self.esl.events():
					evt_name = event.event_name
					evt_uuid = event.header( 'Unique-ID' )
					if evt_uuid != bridge_uuid:
						continue
					if evt_name == 'CHANNEL_ANSWER':
						log.info( 'bridge proceeding on %r', evt_name )
						answered = True
						break
					elif evt_name in terminators:
						return '-ERR NO_ANSWER'
				if originate_timer.elapsed():
					r = await self.esl.uuid_kill( bridge_uuid, 'ORIGINATOR_CANCEL' )
					log.info( 'timeout before CHANNEL_ANSWER, uuid_kill -> %r', r )
					return '-ERR NO_ANSWER'
				if exists_timer.elapsed():
					if not await self.esl.uuid_exists( self.uuid ):
						r = await self.esl.uuid_kill( bridge_uuid, 'ORIGINATOR_CANCEL' )
						log.info( 'aleg disappeared, uuid_kill -> %r', r )
						return '-ERR aleg uuid disappeared'
			
			try:
				await self.esl._uuid_bridge( self.uuid, bridge_uuid )
			except Exception as e:
				log.error( 'uuid_bridge failed: %r', e )
				return f'-ERR bridge failed: {e!r}'
			else:
				log.info( 'uuid_bridge success' )
			
			# now we need to stay right here while the call remains bridged
			exists_timer = ElapsedTimer( datetime.timedelta( seconds = 6 ))
			while True:
				async for event in self.esl.events():
					evt_name = event.event_name
					evt_uuid = event.header( 'Unique-ID' )
					if evt_name in terminators:
						if evt_uuid == self.uuid:
							log.info( 'bridge termination detected by %s on aleg', evt_name )
							return '+OK'
						elif evt_uuid == bridge_uuid:
							log.info( 'bridge termination detected by %s on bridge uuid', evt_name )
							return '+OK'
				if exists_timer.elapsed():
					if not await self.esl.uuid_exists( self.uuid ):
						log.info( 'bridge termination detected by uuid_exists(aleg)==false' )
						return '+OK'
					elif not await self.esl.uuid_exists( bridge_uuid ):
						log.info( 'bridge termination detected by uuid_exists(bleg)==false' )
						return '+OK'
		finally:
			await self.esl.filter_delete( 'Unique-ID', bridge_uuid )
	
	async def action_bridge( self, action: ACTION_BRIDGE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_bridge' )
		if self.state == HUNT: return CONTINUE
		
		if not await util.answer( self.esl, self.uuid, 'action_bridge' ):
			return STOP
		
		result = await self._bridge( action )
		
		if result[:3] == '+OK':
			return CONTINUE
		
		# origination failed:
		which = 'timeoutBranch' if 'NO_ANSWER' in result else 'failBranch'
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def _greeting( self, action: ACTION_GREETING, box: int, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState._greeting' )
		greeting: int = await self.toint( action, 'greeting', default = 1 )
		vm = Voicemail( self.esl, self.uuid )
		if greeting < 1 or greeting > 9:
			settings = vm.load_box_settings( box )
			if not settings:
				log.error( 'invalid box=%r (unable to load settings)', box )
				return CONTINUE
			greeting = await self.toint( action, 'greeting', default = 1 )
		path = vm.box_greeting_path( box, greeting )
		if not path or not path.is_file():
			log.error( 'invalid or non-existing greeting path: %r', path )
			return CONTINUE
		return await self._playback( str( path ), pagd )
	
	async def action_greeting( self, action: ACTION_GREETING, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_greeting' )
		if self.state == HUNT: return CONTINUE
		
		box: int = await self.toint( action, 'box', default = 0 )
		if not box: # "current" box
			if not self.box:
				log.error( 'current box requested but not currently inside the digit map of a voicemail box' )
				return CONTINUE
			box = self.box
		
		return await self._greeting( action, box, pagd )
	
	async def action_greeting2( self, action: ACTION_GREETING, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_greeting2' )
		if self.state == HUNT: return CONTINUE
		
		box: Opt[int] = await self.toint( action, 'box' )
		if not box:
			log.error( 'no box # specified' )
			return CONTINUE
		
		return await self._greeting( action, box, pagd )
	
	async def action_hangup( self, action: ACTION_HANGUP, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_hangup' )
		if self.state == HUNT: return CONTINUE
		
		cause: util.CAUSE = cast( util.CAUSE, expect( str, action.get( 'cause' ), default = 'NORMAL_CLEARING' ))
		if cause not in util.causes:
			log.warning( f'unrecognized hangup cause={cause!r}' )
		await util.hangup( self.esl, self.uuid, cause, 'action_hangup' )
		return STOP
	
	async def action_ivr( self, action: ACTION_IVR, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_ivr' )
		
		if pagd is not None:
			log.error( 'cannot execute a PAGD in the greeting path on another PAGD or an IVR' )
			return CONTINUE
		
		branches: BRANCHES = expect( dict, action.get( 'branches' ))
		
		if self.state == HUNT:
			for digits, branch in branches.items():
				if STOP == await self._exec_branch( digits, branch, None, log = log ): return STOP
				if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'failureBranch', None, log = log )
		
		async def _success( digits: str ) -> Opt[RESULT]:
			log.info( 'got digits=%r', digits )
			branch: BRANCH = cast( BRANCH, expect( dict, branches.get( digits ), default = {} ))
			if branch:
				return await self._exec_branch( digits, branch, None, log = log )
			else:
				log.error( 'no branch found for digits=%r', digits )
				return None
		
		return await self._pagd( action, _success )
	
	async def _broadcast( self, stream: Opt[str], *, default: str, log: logging.Logger ) -> RESULT:
		log2 = log.getChild( '_broadcast' )
		if self.state == HUNT: return CONTINUE
		
		stream = await self.expand(( stream or '' ).strip() or default )
		
		log.debug( 'breaking' )
		await self.esl.uuid_break( self.uuid, 'all' )
		
		log.info( 'playing %r', stream )
		await self.esl.uuid_broadcast( self.uuid, stream, 'aleg' )
		
		return CONTINUE
	
	async def action_moh( self, action: ACTION_MOH, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_moh' )
		return await self._broadcast( action.get( 'stream' ), default = '$${hold_music}', log = log )
	
	async def action_pagd( self, action: ACTION_PAGD, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_pagd' )
		
		if pagd is not None:
			log.error( 'cannot execute a PAGD in the greeting path on another PAGD or an IVR' )
			return CONTINUE
		
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'successBranch', None, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			
			return await self.exec_branch( action, 'failureBranch', None, log = log )
		
		async def _success( digits: str ) -> Opt[RESULT]:
			return await self.exec_branch( action, 'successBranch', None, log = log )
		
		return await self._pagd( action, _success )
	
	async def action_playback( self, action: ACTION_PLAYBACK, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_playback' )
		if self.state == HUNT: return CONTINUE
		
		sound = expect( str, action.get( 'sound' ), default = 'ivr/ivr-invalid_sound_prompt.wav' )
		log.info( 'sound=%r', sound )
		return await self._playback( sound, pagd )
	
	async def action_playtts( self, action: ACTION_PLAYTTS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_playtts' )
		if self.state == HUNT: return CONTINUE
		
		text = await self.expand( action.get( 'text' ) or '' )
		if not text:
			log.error( 'tts node has no text prompt' )
			text = 'Error'
		tts = TTS( action.get( 'voice' ))
		tts.say( text )
		stream = await tts.generate()
		r = await self._playback( str( stream ), pagd )
		log.info( 'done playing %r using voice %r: result=%r',
			text, tts.voice, r,
		)
		return r
	
	async def action_play_dtmf( self, action: ACTION_PLAY_DTMF, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_play_dtmf' )
		if self.state == HUNT: return CONTINUE
		
		dtmf = action.get( 'dtmf' ) or ''
		if dtmf:
			r = await self.esl.uuid_send_dtmf( self.uuid, dtmf )
			log.info( 'uuid_send_dtmf( %r, %r ) -> %r', self.uuid, dtmf, r )
		else:
			log.error( 'no dtmf digits specified' )
		return CONTINUE
	
	async def action_preannounce( self, action: ACTION_PREANNOUNCE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_preannounce' )
		if self.state == HUNT: return CONTINUE
		
		sound = ( await self.expand( '${preannounce_wav}' )).strip()
		if not sound:
			log.warning( 'no preannounce path' )
			return CONTINUE
		log.info( 'sound=%r', sound )
		return await self._playback( sound, pagd )
	
	async def action_preanswer( self, action: ACTION_PREANSWER, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_preanswer' )
		if self.state == HUNT: return CONTINUE
		
		log.info( 'pre-answering' )
		if not await util.pre_answer( self.esl, self.uuid, 'ace_eso.CallState.action_preanswer' ):
			return STOP
		
		return CONTINUE
	
	async def action_ring( self, action: ACTION_RING, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_ring' )
		return await self._broadcast( action.get( 'tone' ), default = '$${us-ring}', log = log )
	
	async def action_route( self, action: ACTION_ROUTE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.route' )
		if self.state == HUNT: return CONTINUE
		
		route: int = await self.toint( action, 'route' )
		if not valid_route( route ):
			log.warning( 'invalid route=%r', route )
			return CONTINUE
		log.info( 'loading route=%r', route )
		routedata = await self.load_route( route )
		old_route = self.route
		log.info( 'executing route=%r', route )
		result = await self.exec_top_actions(
			expect( list, routedata.get( 'nodes' ), default = [] )
		)
		self.route = old_route
		return result
	
	async def action_rxfax( self, action: ACTION_RXFAX, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_rxfax' )
		if self.state == HUNT: return CONTINUE
		
		mailto = expect( str, action.get( 'mailto' ), default = '' ).strip()
		if not mailto:
			log.warning( 'cannot rxfax b/x action.mailto=%r', mailto )
			return STOP
		
		# generate a fax image path that doesn't exist already
		counter: int = 0
		path: Opt[Path] = None
		while path is None or path.is_file():
			path = Path( '/tmp' ) / f'fax_{self.did}_{self.ani}_{self.uuid}_{counter}.tif'
			counter += 1
		
		await self.esl.uuid_setvar( self.uuid, 'ace_rxfax_path', str( path ))
		await self.esl.uuid_setvar( self.uuid, 'ace_rxfax_mailto', mailto )
		# TODO FIXME: calculate time spent receiving fax and expression it as an injection variable
		subject = str( action.get( 'subject' ) or '' ).strip()
		if not subject:
			subject = 'fax received at {did} from {ani}'
		body = str( action.get( 'body' ) or '' ).strip()
		if not body:
			body = 'See attached'
		
		result = await self.esl.uuid_transfer( self.uuid, '', 'ace_rxfax', 'xml', 'default' )
		log.info( 'uuid_transfer result=%r', result )
		return STOP
	
	async def action_set( self, action: ACTION_SET, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_set' )
		if self.state == HUNT: return CONTINUE
		
		variable: str = str( await self.expand( action.get( 'variable' ) or '' ))
		value: str = str( await self.expand( action.get( 'value' ) or '' ))
		r = await self.esl.uuid_setvar( self.uuid, variable, value )
		log.info( 'uuid_setvar( %r, %r, %r ) -> %r', self.uuid, variable, value, r )
		return CONTINUE
	
	async def action_silence( self, action: ACTION_SILENCE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_silence' )
		if self.state == HUNT: return CONTINUE
		
		seconds = await self.tonumber( action, 'seconds', default = 0 )
		divisor = await self.tonumber( action, 'divisor', default = 0 )
		duration = -1 if seconds < 0 else seconds * 1000
		stream = f'silence_stream://{duration}!r,{divisor!r}'
		log.info( '%s', stream )
		return await self._playback( stream, pagd )
	
	async def action_throttle( self, action: ACTION_THROTTLE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_throttle' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'allowedBranch', pagd, log = log ):
				return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'throttledBranch', pagd, log = log )
		
		try:
			throttle_id = await self.esl.uuid_getvar( self.uuid, 'throttle_id' ) or self.did
		except Exception as e:
			log.error( 'Error trying to get throttle_id (defaulting to did): %r', e )
			throttle_id = self.did
		
		try:
			throttle_limit = int( await self.esl.uuid_getvar( self.uuid, 'throttle_limit' ) or '?' )
		except Exception as e:
			throttle_limit = 10
			log.error( 'Error trying to get throttle_limit (defaulting to %r): %r',
				throttle_limit, e,
			)
		
		try:
			await self.esl.uuid_setvar( self.uuid, 'limit_ignore_transfer', 'true' )
		except Exception as e:
			log.error( 'Error trying to set limit_ignore_transfer: %r', e )
		
		backend = 'hash'
		realm = 'inbound'
		
		try:
			async for event in self.esl.limit( self.uuid, backend, realm, throttle_id ):
				_on_event( event )
		except Exception as e:
			log.error( 'Error trying to execute limit app: %r', e )
		
		try:
			usage = int( await self.esl.uuid_getvar( self.uuid, 'limit_usage' ) or '?' )
		except Exception as e:
			usage = 0
			log.error( 'Error trying to get limit_usage (defaulting to %r: %r',
				usage, e,
			)
		
		log.info( 'uuid=%r, usage=%r', self.uuid, usage )
		which = 'allowedBranch'
		if usage > throttle_limit:
			which = 'throttledBranch'
			r = await self.esl.uuid_limit_release( self.uuid, backend, realm, throttle_id )
			log.debug( 'uuid_limit_release( %r, %r, %r, %r ) -> %r',
				self.uuid, backend, realm, throttle_id, r,
			)
		
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def action_tone( self, action: ACTION_TONE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_tone' )
		if self.state == HUNT: return CONTINUE
		
		tone = str( action.get( 'tone' ) or '' ).strip()
		if not tone:
			log.error( 'Cannot play tone b/c tone=%r', tone )
			return CONTINUE
		
		loops = await self.toint( action, 'loops', default = 1 )
		stream = f'tone_stream://{tone};loops={loops}'
		log.info( 'stream=%r', stream )
		return await self._playback( stream, pagd )
	
	async def action_transfer( self, action: ACTION_TRANSFER, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_transfer' )
		if self.state == HUNT: return CONTINUE
		
		leg = cast( Literal['','-bleg','-both'], str( action.get( 'leg' ) or '' ).strip() )
		assert leg in ( '', '-bleg', '-both' ), f'invalid leg={leg!r}'
		dest = str( action.get( 'dest' ) or '' ).strip()
		dialplan = cast( Literal['','xml','inline'], str( action.get( 'dialplan' ) or '' ).strip() )
		assert dialplan in ( '', 'xml', 'inline' ), f'invalid dialplan={dialplan!r}'
		context = str( action.get( 'context' ) or '' ).strip()
		log.info( 'leg=%r dest=%r dialplan=%r context=%r',
			leg, dest, dialplan, context,
		)
		result = await self.esl.uuid_transfer( self.uuid, leg, dest, dialplan, context )
		log.info( 'result=%r', result )
		self.hangup_on_exit = False
		return STOP
	
	async def _guest_greeting( self, action: ACTION_VOICEMAIL, box: int, settings: SETTINGS, vm: Voicemail ) -> Opt[str]:
		log = logger.getChild( 'CallState._guest_greeting' )
		
		try:
			active_greeting = int( settings.get( 'greeting' ) or '' )
		except ValueError:
			active_greeting = 1
		
		async def _make_greeting_branch( greeting: int ) -> BRANCH:
			path = vm.box_greeting_path( box, greeting )
			if path is None or not path.is_file():
				playlist = await vm._the_person_at_extension_is_not_available_record_at_the_tone( box )
				greeting_branch = BRANCH( name = '', nodes = cast( ACTIONS, list(
					ACTION_PLAYBACK( type = 'playback', name = '', sound = sound ) for sound in playlist
				)))
			else:
				greeting_branch = BRANCH( name = '', nodes = cast( ACTIONS, [
					ACTION_PLAYBACK( type = 'playback', name = '', sound = str( path ))
				]))
			return greeting_branch
		
		which: str = ''
		greeting_branch: BRANCH
		greeting_override = str( action.get( 'greeting_override' ) or '' )
		if greeting_override == 'A': # play active greeting
			greeting_branch = await _make_greeting_branch( active_greeting )
		elif greeting_override == 'X': # play no greeting at all
			return ''
		elif greeting_override.isnumeric():
			greeting_branch = await _make_greeting_branch( int( greeting_override ))
		else:
			if greeting_override:
				log.warning( 'invalid greeting_override=%r', greeting_override )
			which = 'greetingBranch'
			greeting_branch = cast( BRANCH, settings.get( which ) or {} )
		
		if not greeting_branch.get( 'nodes' ):
			# this can happen if:
			# 1) greeting_override == 'A'
			# 2) default behavior was requested but no greeting behavior was defined in the voicemail box
			which = ''
			greeting_branch = { 'name': '', 'nodes': [
				ACTION_GREETING( type = 'greeting', name = '', box = box, greeting = str( active_greeting ))
			]}
		
		pagd = PAGD(
			min_digits = 1,
			max_digits = 1,
			timeout = datetime.timedelta( seconds = 0.1 ), # TODO FIXME: customizable?
			terminators = '',
			digit_regex = '',
			variable_name = '',
			digit_timeout = datetime.timedelta( seconds = 0.1 ), # TODO FIXME: customizable?
		)
		if STOP == await self._exec_branch( which, greeting_branch, pagd, log = log ):
			return STOP
		if not pagd.digits:
			if STOP == await self.action_silence( ACTION_SILENCE(
				type = 'silence',
				name = '',
				seconds = 0.25, # TODO FIXME: customizable
				divisor = 0,
			), pagd ):
				return STOP
		return pagd.digits
	
	async def action_voicemail( self, action: ACTION_VOICEMAIL, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_voicemail' )
		if self.state == HUNT: return CONTINUE
		
		box: Opt[int] = await self.toint( action, 'box', expand = True )
		if box is None:
			log.warning( 'invalid box=%r', action.get( 'box' ))
			return CONTINUE
		
		vm = Voicemail( self.esl, self.uuid )
		
		_ = await util.answer( self.esl, self.uuid, 'CallState.action_voicemail' )
		
		if box == 0:
			if not await vm.checkin():
				return STOP
			return CONTINUE
		
		settings_: Opt[SETTINGS] = await vm.load_box_settings( box )
		if settings_ is None:
			stream = await vm._the_person_you_are_trying_to_reach_is_not_available_and_does_not_have_voicemail()
			await vm.play_menu([ stream ])
			# TODO FIXME: do we want to forceably hangup the call here?
			# TODO FIXME: or add a "no box" branch to the voicemail node in the editor?
			await vm.goodbye()
			return STOP
		settings: SETTINGS = settings_
		
		branches: BRANCHES = settings.get( 'branches' ) or {}
		digit: Opt[str] = None
		while True: # this loop only exists to serve replay of greeting in the case of "invalid entry"
			if not digit:
				digit = await self._guest_greeting( action, box, settings, vm )
			if digit is None:
				return STOP
			if digit == '*':
				# user pressed * during the above recording, time to try to log them into their box
				if await vm.login( box, settings ):
					log.debug( 'login success, calling admin_main_menu for box=%r', box )
					await vm.admin_main_menu( box, settings )
					log.debug( 'back from admin_main_menu from box=%r', box )
				log.debug( 'hanging up and terminating script' )
				await util.hangup( self.esl, self.uuid, 'NORMAL_CLEARING', 'CallState.action_voicemail' )
				return STOP
			if digit and digit in '1234567890':
				branch = branches.get( digit )
				if branch:
					old_box: Opt[int] = self.box
					try:
						self.box = box
						r = await self._exec_branch( digit, branch, None, log = log )
					finally:
						self.box = old_box
					return r
				else:
					digit = await vm.play_menu([ 'ivr/ivr-that_was_an_invalid_entry.wav' ])
					continue
			# no diversions selected, record message:
			if digit and digit != '#':
				log.warning( 'invalid digit=%r', digit )
			if await vm.guest( self.did, self.ani, box, settings, self.notify ):
				await util.hangup( self.esl, self.uuid, 'NORMAL_CLEARING', 'CallState.action_voicemail' )
			return STOP
		
		return CONTINUE
	
	async def notify( self, box: int, settings: SETTINGS, msg: MSG ) -> None:
		log = logger.getChild( 'CallState.notify' )
		try:
			state = NotifyState( self.esl, box, msg, settings )
			delivery = settings.get( 'delivery' ) or {}
			nodes = delivery.get( 'nodes' ) or []
			await state.exec_top_actions( nodes )
		except Exception:
			log.exception( 'Unexpected error during voicemail notify:' )


#endregion CallState
#region NotifyState


class NotifyState( State ):
	def __init__( self, esl: ESL, box: int, msg: MSG, settings: SETTINGS ) -> None:
		super().__init__( esl )
		self.box = box
		self.msg = msg
		self.settings = settings
	
	async def can_continue( self ) -> bool:
		return self.msg.status == 'new' and self.msg.path.is_file()
	
	async def action_email( self, action: ACTION_EMAIL, pagd: Opt[PAGD] ) -> RESULT:
		# TODO FIXME: might we have a use for this in CallState too?
		log = logger.getChild( 'NotifyState.action_email' )
		if self.state == HUNT: return CONTINUE
		
		ec = Email_composer()
		ec.to = expect( str, action.get( 'mailto' ), default = '' )
		cc = ''
		bcc: List[str] = []
		ec.from_ = self.config.email_from
		ec.subject = expect( str, action.get( 'subject' ), default = '' )
		ec.text = expect( str, action.get( 'body' ), default = '' )
		fmt: str = expect( str, action.get( 'format' ), default = '' )
		file: Opt[Path] = None
		if self.msg is not None:
			file = self.msg.path
		
		if not ec.to:
			log.warning( 'cannot send email - no recipient' )
			return CONTINUE
		
		
		if self.settings:
			if not ec.subject:
				ec.subject = self.settings.get( 'default_email_subject' ) or ''
			if not ec.text:
				ec.text = self.settings.get( 'default_email_body' ) or ''
			if not fmt:
				fmt = self.settings.get( 'format' ) or ''
		if not fmt:
			fmt = 'mp3'
		
		ec.subject = await self.expand( ec.subject )
		ec.text = await self.expand( ec.text )
		
		if file and fmt == 'mp3':
			mp3_file = file.with_suffix( '.mp3' )
			pydub.AudioSegment.from_wav( str( file )).export( str( mp3_file ), format = 'mp3' )
			file = mp3_file
		
		if self.config.smtp_secure == 'yes':
			smtp: Union[smtplib2.SMTP,smtplib2.SMTP_SSL] = smtplib2.SMTP_SSL(
				self.config.smtp_host,
				self.config.smtp_port or 465,
				timeout = self.config.smtp_timeout_seconds,
			)
		else:
			smtp = smtplib2.SMTP(
				self.config.smtp_host,
				self.config.smtp_port or 587,
				timeout = self.config.smtp_timeout_seconds,
			)
		
		if self.config.smtp_username or self.config.smtp_password:
			assert self.config.smtp_username and self.config.smtp_password
			smtp.login( self.config.smtp_username, self.config.smtp_password )
		
		smtp.sendmail( ec.from_, list( chain( ec.to, ec.cc, bcc )), ec.as_bytes() )
		
		return CONTINUE
	
	async def _voice_deliver( self, action: ACTION_VOICE_DELIVER, number: str ) -> Tuple[bool,Opt[str]]:
		log = logger.getChild( 'NotifyState._voice_deliver' )
		
		timeout = datetime.timedelta( seconds = await self.toint( action, 'timeout', default = 0 ))
		if timeout.total_seconds() <= 0:
			timeout = datetime.timedelta( seconds = 60 )
		
		dest = f'loopback/{number}/default'
		cid_name = str( action.get( 'cid_name' ) or '' ).strip() or f'VMBox {self.box}'
		cid_num = str( action.get( 'cid_num' ) or '' ).strip() or self.config.voice_deliver_ani
		context = str( action.get( 'context' ) or '' ).strip() or 'default'
		trusted = expect( bool, action.get( 'trusted' ))
		
		origination_uuid = str( uuid.uuid4() )
		
		chanvars = {
			'origination_uuid': origination_uuid,
			'direction': 'outbound',
			'origination_caller_id_number': cid_num,
			'outbound_caller_id_number': cid_num,
			'origination_caller_id_name': cid_name,
			'outbound_caller_id_name': cid_name,
			'call_timeout': str( int( timeout.total_seconds() )),
			'bridge_answer_timeout': str( int( timeout.total_seconds() )),
			'context': context,
			'domain_name': context,
			'domain': context,
		}
		
		try:
			r = await self.esl.originate(
				dest = dest,
				origin = '&playback(silence_stream://-1)',
				dialplan = '',
				context = context,
				cid_name = cid_name,
				cid_num = cid_num,
				timeout = timeout,
				chanvars = chanvars,
			)
		except Exception:
			log.exception( 'Error trying to originate:' )
		log.debug( 'originate -> %r', r )
		
		await asyncio.sleep( 1 )
		
		answered, reason = await self._uuid_wait_for_answer( origination_uuid, timeout )
		
		if not answered:
			return False, reason
		
		vm = Voicemail( self.esl, origination_uuid )
		await vm.voice_deliver( self.box, self.msg, trusted, self.settings )
		
		return True, None
	
	async def _uuid_wait_for_answer( self, uuid: str, timeout: datetime.timedelta ) -> Tuple[bool,Opt[str]]:
		timer = ElapsedTimer( timeout )
		while True:
			if not await self.esl.uuid_exists( uuid ):
				return False, '-ERR uuid no longer exists'
			if await self.esl.uuid_getchanvar( uuid, 'Answer-State' ) == 'answered':
				return True, None
			if timer.elapsed():
				return False, '-ERR timeout before answer'
			await asyncio.sleep( 0.5 )
	
	async def action_voice_deliver( self, action: ACTION_VOICE_DELIVER, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'NotifyState.action_voice_deliver' )
		if self.state == HUNT: return CONTINUE
		
		number = str( action.get( 'number' ) or '' ).strip()
		path = self.msg.path
		
		if not number:
			log.error( 'cannot voice deliver - no number' )
			return CONTINUE
		
		if not self.msg.path.is_file():
			log.warning( 'cannot voice deliver - wave file no longer exists' )
			return CONTINUE
		
		ok, reason = await self._voice_deliver( action, number )
		log.info( 'ok=%r, reason=%r', ok, reason )
		
		return CONTINUE


#endregion NotifyState
#region bootstrap

def normalize_phone_number( phone: str ) -> str:
	phone = re.sub( r'[^\d]', '', phone )
	if len( phone ) == 11 and phone[0] == '1':
		phone = phone[1:]
	return phone

async def _handler( reader: asyncio.StreamReader, writer: asyncio.StreamWriter ) -> None:
	log = logger.getChild( '_handler' )
	esl = ESL()
	try:
		headers = await esl.connect_from( reader, writer )
		
		await asyncio.sleep( 0.5 ) # wait for media to establish
		
		#for k, v in headers.items():
		#	print( f'{k!r}: {v!r}' )
		uuid = headers['Unique-ID']
		did = headers['Caller-Destination-Number']
		ani = headers['Caller-ANI']
		log.debug( 'uuid=%r raw did=%r ani=%r', uuid, did, ani )
		
		did = normalize_phone_number( did )
		ani = normalize_phone_number( ani )
		log.debug( 'uuid=%r normalized did=%r ani=%r', uuid, did, ani )
		
		log.debug( 'calling myevents' )
		await esl.myevents()
		
		#await esl.linger() # TODO FIXME: I'm probably going to want this...
		
		state = CallState( esl, uuid, did, ani )
		
		route = await state.try_ani()
		if route is None:
			route, didinfo = await state.try_did()
			if didinfo is not None:
				await state.set_preannounce( didinfo )
		
		if not route:
			log.error( 'no route to execute: route=%r', route )
			await util.hangup( esl, uuid, 'UNALLOCATED_NUMBER', 'ace_engine._handler#1' )
			return
		
		route_ = str( route or '' )
		if route_.startswith( 'V' ):
			try:
				box = int( route_[1:] )
			except ValueError:
				log.error( 'Could not interpret %r as an integer voicemail box #', route_[1:] )
				await util.hangup( esl, uuid, 'UNALLOCATED_NUMBER', 'ace_engine._handler#2' )
				return
			routedata = {
				#'type': 'root_route',
				'nodes': [{
					'type': 'voicemail',
					'box': box,
				}]
			}
		else:
			try:
				routedata = state.config.repo_routes.get_by_id( route )
			except repo.ResourceNotFound:
				log.error( 'route does not exist: route=%r', route )
				await util.hangup( esl, uuid, 'UNALLOCATED_NUMBER', 'ace_engine._handler#3' )
				return
		
		nodes = cast( ACTIONS, routedata.get( 'nodes' ) or [] )
		r = await state.exec_top_actions( nodes )
		log.info( 'route %r exited with %r', route, r )
		
		if state.hangup_on_exit:
			cause: Final = 'NORMAL_CLEARING'
			log.debug( 'hanging up call with %r because route exited with %r', cause, r )
			await esl.uuid_kill( uuid, cause )
			await esl.uuid_setvar( uuid, ACE_STATE, STATE_KILL )
		else:
			#cause = 'NORMAL_CLEARING'
			#log.debug( 'hanging up call with %r because route exited with %r and we have no way to signal inband lua yet', cause, r )
			await esl.uuid_setvar( uuid, ACE_STATE, STATE_CONTINUE )
	
	except ChannelHangup as e:
		log.warning( repr( e ))
	except Exception:
		log.exception( 'Unexpected error:' )
	finally:
		log.warn( 'closing down client' )
		await esl.close()

async def _server(
	config: Config,
) -> None:
	util.on_event = _on_event
	
	State.config = config
	State.repo_anis = repo.AsyncRepository( config.repo_anis )
	State.repo_dids = repo.AsyncRepository( config.repo_dids )
	State.repo_routes = repo.AsyncRepository( config.repo_routes )
	
	TTS.aws_access_key = config.aws_access_key
	TTS.aws_secret_key = config.aws_secret_key
	TTS.aws_region_name = config.aws_region_name
	TTS.tts_location = config.tts_location
	TTS.tts_default_voice = config.tts_default_voice
	await Voicemail.init(
		box_path = config.vm_box_path,
		msgs_path = config.vm_msgs_path,
		owner_user = config.owner_user,
		owner_group = config.owner_group,
		min_pin_length = config.vm_min_pin_length,
		use_tts = config.vm_use_tts,
		on_event = _on_event,
	)
	server = await asyncio.start_server( _handler, '127.0.0.1', 8022 )
	async with server:
		await server.serve_forever()

def _main(
	config: Config
) -> None:
	if sys.platform != 'win32':
		journald_handler = JournaldLogHandler()
		journald_handler.setFormatter(
			logging.Formatter( '[%(levelname)s] %(message)s' )
		)
		logger.addHandler( journald_handler )
	logging.basicConfig(
		level = logging.DEBUG,
		#level = DEBUG9,
		format = '%(asctime)s:%(levelname)s:%(name)s:%(message)s',
	)
	#print( 'repo_routes=}' )
	asyncio.run( _server( config ) )

def start( config: Config ) -> None:
	eso_process = Process(
		target = _main,
		args = ( config, ),
		daemon = True,
	)
	eso_process.start()

#endregion bootstrap
