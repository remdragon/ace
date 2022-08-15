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
from pathlib import Path
import re
import time
from typing import (
	Any, Awaitable, Callable, cast, Coroutine, Dict, List, Optional as Opt,
	Tuple, Type, TypeVar, Union,
)
from typing_extensions import Final, Literal # Python 3.7
import uuid

# 3rd-party imports:
import aiohttp # pip install aiohttp
import pydub # pip install pydub

# local imports:
from ace_tod import match_tod
import ace_util as util
from ace_voicemail import Voicemail, MSG, SETTINGS
from email_composer import Email_composer
from esl import ESL
import repo
import smtplib2
from tts import TTS, TTS_VOICES, tts_voices


#endregion imports
#region globals


logger = logging.getLogger( __name__ )

PARAMS = Dict[str,Any]

GOTO: Final = 'goto'
EXEC: Final = 'exec'
HUNT: Final = 'hunt'
EXECSTATE = Literal['goto','exec','hunt']

CONTINUE: Final = 'continue'
STOP: Final = 'stop'
RESULT = Literal['continue','stop']

@dataclass
class Config:
	did_path: Path # TODO FIXME: repo.Repository
	ani_path: Path # TODO FIXME: repo.Repository
	repo_routes: repo.Repository
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

T = TypeVar( 'T' )

def expect( type: Type[T], data: Dict[str,Any], name: str, *, required: bool = False, default: Opt[T] = None ) -> T:
	value = data.get( name )
	if value is None:
		return default if default is not None else type()
	if isinstance( value, type ):
		return value
	raise ValueError( f'expecting {name!r} of type {str(type)!r} but got {value!r}' )

def _on_event( event: ESL.Message ) -> None:
	log = logger.getChild( '_on_event' )
	log.warning( 'event %r TODO FIXME: check for hangup or channel teardown event and throw a call ended exception...', event.event_name )

def valid_route( x: Any ) -> bool:
	return isinstance( x, int )

#endregion globals
#region State


class State( metaclass = ABCMeta ):
	config: Config
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
					ar[i] = getattr( self.msg, ar[i], '' )
			else:
				assert False, f'invalid state={self!r}'
			s = ''.join( ar )
		log.debug( 'output=%r', s )
		return s
	
	async def tonumber( self, data: Dict[str,Any], name: str, *, expand: bool = False, default: Opt[Union[int,float]] = None ) -> Union[int,float]:
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
	
	async def toint( self, data: Dict[str,Any], name: str, *, expand: bool = False, default: Opt[int] = None ) -> int:
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
	
	async def exec_branch( self, params: PARAMS, which: str, pagd: Opt[PAGD], *, log: logging.Logger ) -> RESULT:
		branch: Dict[str,Any] = expect( dict, params, which, default = {} )
		return await self._exec_branch( which, branch, pagd, log = log )
	
	async def _exec_branch( self, which: str, branch: Dict[str,Any], pagd: Opt[PAGD], *, log: logging.Logger ) -> RESULT:
		name: Opt[str] = branch.get( 'name' )
		nodes: List[Any] = expect( list, branch, 'nodes', default = [] )
		log.info( 'executing %s branch %r', which, name )
		return await self.exec_actions( nodes, pagd )
	
	async def exec_actions( self, actions: List[PARAMS], pagd: Opt[PAGD] = None ) -> RESULT:
		for action in actions or []:
			r = await self.exec_action( action, pagd )
			if r != CONTINUE: return r
			if pagd and pagd.digits: return CONTINUE
		return CONTINUE
	
	async def exec_action( self, action: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.exec_action' )
		action_type = expect( str, action, 'type', default = '' )
		if not action_type:
			log.error( 'action.type is missing' ) # TODO FIXME: diagnostic info?
			return CONTINUE
		fname = f'action_{action_type}'
		f: Opt[Callable[[PARAMS,Opt[PAGD]],Awaitable[RESULT]]] = getattr( self, fname, None )
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
	
	async def exec_top_actions( self, actions: List[PARAMS] ) -> RESULT:
		log = logger.getChild( 'State.exec_top_actions' )
		while True:
			r = await self.exec_actions( actions )
			if self.state == GOTO:
				self.state = HUNT
			else:
				return r
	
	async def action_goto( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_goto' )
		if self.state == HUNT: return CONTINUE
		
		self.goto_uuid = expect( str, params, 'destination' )
		log.info( 'destination=%r', self.goto_uuid )
		self.state = GOTO
		return STOP
	
	async def action_ifnum( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_ifnum' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( params, 'trueBranch', pagd, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( params, 'falseBranch', pagd, log = log )
		
		lhs: Union[int,float] = await self.tonumber( params, 'lhs', expand = True )
		op: str = await self.expand( expect( str, params, 'op' ))
		rhs: Union[int,float] = await self.tonumber( params, 'rhs', expand = True )
		
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
		return await self.exec_branch( params, which, pagd, log = log )
	
	async def action_ifstr( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_ifstr' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( params, 'trueBranch', pagd, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( params, 'falseBranch', pagd, log = log )
		
		lhs: str = await self.expand( expect( str, params, 'lhs' ))
		op: str = await self.expand( expect( str, params, 'op' ))
		rhs: str = await self.expand( expect( str, params, 'rhs' ))
		if not expect( bool, params, 'case', default = False ):
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
		return await self.exec_branch( params, which, pagd, log = log )
	
	async def action_label( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_label' )
		try:
			label_uuid = params['uuid']
		except KeyError:
			log.error( 'label missing "uuid"' )
		else:
			if self.state == HUNT and self.goto_uuid == label_uuid:
				log.info( 'HIT name=%r', params.get( 'name' ))
				self.state = EXEC
			else:
				log.info( 'PASS name=%r', params.get( 'name' ))
		return CONTINUE
	
	async def action_log( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_log' )
		if self.state == HUNT: return CONTINUE
		
		level = getattr( logging, params.get( 'level' ) or 'DEBUG', logging.DEBUG )
		text = await self.expand( params.get( 'text' ) or '?' )
		log.log( level, text )
		
		return CONTINUE
	
	async def action_lua( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_lua' )
		if self.state == HUNT: return CONTINUE
		
		#source = ( params.get( 'source' ) or '' ).strip()
		#if not source:
		#	log.error( 'cannot execute lua code: source is empty' )
		#	return CONTINUE
		
		log.error( 'TODO FIXME: inline lua not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_laufile( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_luafile' )
		if self.state == HUNT: return CONTINUE
		
		file = ( params.get( 'file' ) or '' ).strip()
		if not file:
			log.error( 'cannot execute lua file: no filename provided' ) # TODO FIXME: log some of this stuff to freeswitch console?
			return CONTINUE
		
		log.error( 'TODO FIXME: lua file not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_python( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_python' )
		if self.state == HUNT: return CONTINUE
		
		log.error( 'TODO FIXME: python not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_repeat( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_repeat' )
		count: int = await self.toint( params, 'count', default = 0 )
		nodes = expect( list, params, 'nodes', default = [] )
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
	
	async def action_sms( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_sms' )
		if self.state == HUNT: return CONTINUE
		
		smsto: str = str( params.get( 'smsto' ) or '' ).strip() # TODO FIXME: thinq expects 'XXXXXXXXXX'
		message: str = str( params.get( 'message' ) or '' ).strip()
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
	
	async def action_tod( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_tod' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( params, 'hit', pagd, log = log ):
				return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( params, 'miss', pagd, log = log )
		
		which = 'miss'
		if match_tod( expect( str, params, 'times' )):
			# make sure holiday params match too
			log.warning( 'TODO FIXME: implement holidays' )
			which = 'hit'
		
		return await self.exec_branch( params, which, pagd, log = log )
	
	async def action_wait( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_wait' )
		if self.state == HUNT: return CONTINUE
		
		minutes: int = await self.toint( params, 'minutes', default = 0 )
		seconds = minutes * 60 + await self.toint( params, 'seconds', default = 0 )
		
		if isinstance( self, CallState ) and pagd is not None:
			params2: PARAMS = {
				'seconds': seconds,
				'divisor': 0,
			}
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
	
	async def _pagd( self, params: PARAMS, success: Callable[[str],Coroutine[Any,Any,Opt[RESULT]]] ) -> RESULT:
		log = logger.getChild( 'CallState._pagd' )
		timeout = datetime.timedelta( seconds = await self.tonumber( params, 'timeout', default = 3 ))
		pagd = PAGD(
			min_digits = await self.toint( params, 'min_digits', default = 1 ),
			max_digits = await self.toint( params, 'max_digits', default = 1 ),
			timeout = datetime.timedelta( milliseconds = 50 ), # don't want to apply pagd.timeout to every node under greeting branch
			terminators = expect( str, params, 'terminators', default = '' ),
			digit_regex = expect( str, params, 'digit_regex', default = '' ),
			variable_name = expect( str, params, 'variable_name', default = '' ),
			digit_timeout = datetime.timedelta( seconds = await self.tonumber( params, 'digit_timeout', default = timeout.total_seconds() ))
		)
		max_attempts = await self.toint( params, 'max_attempts', default = 3 )
		attempt: int = 1
		r: RESULT
		while attempt <= max_attempts:
			if not pagd.digits:
				r = await self.exec_branch( params, 'greetingBranch', pagd, log = log )
				if r == STOP: return STOP
				if not pagd.digits:
					r = await self.action_silence( { 'seconds': 3 }, pagd )
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
					r = await self.exec_branch( params, 'invalidBranch', pagd, log = log )
					if r == STOP: return STOP
				else:
					r = await self.exec_branch( params, 'timeoutBranch', pagd, log = log )
					if r == STOP: return STOP
			else:
				r = await self.exec_branch( params, 'failureBranch', None, log = log )
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
			async for event in self.esl.play_and_get_digits(
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
			async for event in self.esl.playback( sound ):
				_on_event( event )
			
			return CONTINUE
	
	async def action_acd_call_add( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_add' )
		if self.state == HUNT: return CONTINUE
		
		gates: str = expect( str, params, 'gates' )
		priority: int = await self.toint( params, 'priority' )
		queue_offset_seconds: int = await self.toint( params, 'queue_offset_seconds', default = 0 )
		
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
	
	async def action_acd_call_gate( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_gate' )
		if self.state == HUNT: return CONTINUE
		
		gate: str = expect( str, params, 'gate' )
		priority: int = await self.toint( params, 'priority' )
		
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
	
	async def action_acd_call_ungate( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_ungate' )
		if self.state == HUNT: return CONTINUE
		
		gate: str = expect( str, params, 'gate' )
		
		r = await self.esl.luarun(
			'itas/acd.lua',
			'call',
			'ungate',
			self.uuid,
			gate,
		)
		log.debug( 'result: %r', r )
		
		return CONTINUE
	
	async def action_answer( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		#log = logger.getChild( 'CallState.action_answer' )
		if self.state == HUNT: return CONTINUE
		
		if not util.answer( self.esl, self.uuid, 'ace_eso.CallState.action_answer' ):
			return STOP
		
		return CONTINUE
	
	async def _bridge( self, params: PARAMS ) -> str:
		log = logger.getChild( 'CallState._bridge' )
		
		timeout_seconds: int = await self.toint( params, 'timeout', default = 0 )
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
			dial_string = expect( str, params, 'dial_string' )
			chanvars = { 'origination_uuid': bridge_uuid }
			origin = '&playback(silence_stream://-1)'
			dialplan = str( params.get( 'dialplan' ) or '' )
			context = str( params.get( 'context' ) or '' )
			cid_name = str( params.get( 'cid_name' ) or '' )
			cid_num = str( params.get( 'cid_num' ) or '' )
			
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
	
	async def action_bridge( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_bridge' )
		if self.state == HUNT: return CONTINUE
		
		if not await util.answer( self.esl, self.uuid, 'action_bridge' ):
			return STOP
		
		result = await self._bridge( params )
		
		if result[:3] == '+OK':
			return CONTINUE
		
		# origination failed:
		which = 'timeoutBranch' if 'NO_ANSWER' in result else 'failBranch'
		return await self.exec_branch( params, which, pagd, log = log )
	
	async def _greeting( self, params: PARAMS, box: int, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState._greeting' )
		greeting: int = await self.toint( params, 'greeting', default = 1 )
		vm = Voicemail( self.esl, self.uuid )
		if greeting < 1 or greeting > 9:
			settings = vm.load_box_settings( box )
			if not settings:
				log.error( 'invalid box=%r (unable to load settings)', box )
				return CONTINUE
			greeting = await self.toint( params, 'greeting', default = 1 )
		path = vm.box_greeting_path( box, greeting )
		if not path or not path.is_file():
			log.error( 'invalid or non-existing greeting path: %r', path )
			return CONTINUE
		return await self._playback( str( path ), pagd )
	
	async def action_greeting( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_greeting' )
		if self.state == HUNT: return CONTINUE
		
		box: int = await self.toint( params, 'box', default = 0 )
		if not box: # "current" box
			if not self.box:
				log.error( 'current box requested but not currently inside the digit map of a voicemail box' )
				return CONTINUE
			box = self.box
		
		return await self._greeting( params, box, pagd )
	
	async def action_greeting2( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_greeting2' )
		if self.state == HUNT: return CONTINUE
		
		box: Opt[int] = await self.toint( params, 'box' )
		if not box:
			log.error( 'no box # specified' )
			return CONTINUE
		
		return await self._greeting( params, box, pagd )
	
	async def action_hangup( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_hangup' )
		if self.state == HUNT: return CONTINUE
		
		cause: util.CAUSE = cast( util.CAUSE, expect( str, params, 'cause', default = 'NORMAL_CLEARING' ))
		if cause not in util.causes:
			log.warning( f'unrecognized hangup cause={cause!r}' )
		await util.hangup( self.esl, self.uuid, cause, 'action_hangup' )
		return STOP
	
	async def action_ivr( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_ivr' )
		
		if pagd is not None:
			log.error( 'cannot execute a PAGD in the greeting path on another PAGD or an IVR' )
			return CONTINUE
		
		branches: Dict[str,Any] = expect( dict, params, 'branches' )
		
		if self.state == HUNT:
			for digits, branch in branches.items():
				if STOP == await self._exec_branch( digits, branch, None, log = log ): return STOP
				if self.state != HUNT: return CONTINUE
			return await self.exec_branch( params, 'failureBranch', None, log = log )
		
		async def _success( digits: str ) -> Opt[RESULT]:
			log.info( 'got digits=%r', digits )
			branch: Dict[str,Any] = expect( dict, branches, digits, default = {} )
			if branch:
				return await self._exec_branch( digits, branch, None, log = log )
			else:
				log.error( 'no branch found for digits=%r', digits )
				return None
		
		return await self._pagd( params, _success )
	
	async def _broadcast( self, params: PARAMS, key: str, *, default: str, log: logging.Logger ) -> RESULT:
		log2 = log.getChild( '_broadcast' )
		if self.state == HUNT: return CONTINUE
		
		stream: str = await self.expand( expect( str, params, key, default = default ))
		
		log.debug( 'breaking' )
		await self.esl.uuid_break( self.uuid, 'all' )
		
		log.info( 'playing %r', stream )
		await self.esl.uuid_broadcast( self.uuid, stream, 'aleg' )
		
		return CONTINUE
	
	async def action_moh( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_moh' )
		return await self._broadcast( params, 'stream', default = '$${hold_music}', log = log )
	
	async def action_pagd( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_pagd' )
		
		if pagd is not None:
			log.error( 'cannot execute a PAGD in the greeting path on another PAGD or an IVR' )
			return CONTINUE
		
		if self.state == HUNT:
			if STOP == await self.exec_branch( params, 'successBranch', None, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			
			return await self.exec_branch( params, 'failureBranch', None, log = log )
		
		async def _success( digits: str ) -> Opt[RESULT]:
			return await self.exec_branch( params, 'successBranch', None, log = log )
		
		return await self._pagd( params, _success )
	
	async def action_playback( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_playback' )
		if self.state == HUNT: return CONTINUE
		
		sound = expect( str, params, 'sound', default = 'ivr/ivr-invalid_sound_prompt.wav' )
		log.info( 'sound=%r', sound )
		return await self._playback( sound, pagd )
	
	async def action_playtts( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_playtts' )
		if self.state == HUNT: return CONTINUE
		
		text = await self.expand( params.get( 'text' ) or '' )
		if not text:
			log.error( 'tts node has no text prompt' )
			text = 'Error'
		tts = TTS( params.get( 'voice' ))
		tts.say( text )
		stream = await tts.generate()
		r = await self._playback( str( stream ), pagd )
		log.info( 'done playing %r using voice %r: result=%r',
			text, tts.voice, r,
		)
		return r
	
	async def action_play_dtmf( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_play_dtmf' )
		if self.state == HUNT: return CONTINUE
		
		dtmf = params.get( 'dtmf' ) or ''
		if dtmf:
			r = await self.esl.uuid_send_dtmf( self.uuid, dtmf )
			log.info( 'uuid_send_dtmf( %r, %r ) -> %r', self.uuid, dtmf, r )
		else:
			log.error( 'no dtmf digits specified' )
		return CONTINUE
	
	async def action_preannounce( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_preannounce' )
		if self.state == HUNT: return CONTINUE
		
		sound = ( await self.expand( '${preannounce_wav}' )).strip()
		if not sound:
			log.warning( 'no preannounce path' )
			return CONTINUE
		log.info( 'sound=%r', sound )
		return await self._playback( sound, pagd )
	
	async def action_preanswer( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_preanswer' )
		if self.state == HUNT: return CONTINUE
		
		log.info( 'pre-answering' )
		if not await util.pre_answer( self.esl, self.uuid, 'ace_eso.CallState.action_preanswer' ):
			return STOP
		
		return CONTINUE
	
	async def action_ring( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_ring' )
		return await self._broadcast( params, 'tone', default = '$${us-ring}', log = log )
	
	async def action_route( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.route' )
		if self.state == HUNT: return CONTINUE
		
		route: int = await self.toint( params, 'route' )
		if not valid_route( route ):
			log.warning( 'invalid route=%r', route )
			return CONTINUE
		log.info( 'loading route=%r', route )
		routedata = await self.load_route( route )
		old_route = self.route
		log.info( 'executing route=%r', route )
		result = await self.exec_top_actions(
			expect( list, routedata, 'nodes', default = [] )
		)
		self.route = old_route
		return result
	
	async def action_rxfax( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_rxfax' )
		if self.state == HUNT: return CONTINUE
		
		mailto = expect( str, params, 'mailto', default = '' ).strip()
		if not mailto:
			log.warning( 'cannot rxfax b/x params.mailto=%r', mailto )
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
		subject = str( params.get( 'subject' ) or '' ).strip()
		if not subject:
			subject = 'fax received at {did} from {ani}'
		body = str( params.get( 'body' ) or '' ).strip()
		if not body:
			body = 'See attached'
		
		result = await self.esl.uuid_transfer( self.uuid, '', 'ace_rxfax', 'xml', 'default' )
		log.info( 'uuid_transfer result=%r', result )
		return STOP
	
	async def action_set( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_set' )
		if self.state == HUNT: return CONTINUE
		
		variable: str = str( await self.expand( params.get( 'variable' ) or '' ))
		value: str = str( await self.expand( params.get( 'value' ) or '' ))
		r = await self.esl.uuid_setvar( self.uuid, variable, value )
		log.info( 'uuid_setvar( %r, %r, %r ) -> %r', self.uuid, variable, value, r )
		return CONTINUE
	
	async def action_silence( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_silence' )
		if self.state == HUNT: return CONTINUE
		
		seconds = await self.tonumber( params, 'seconds', default = 0 )
		divisor = await self.tonumber( params, 'divisor', default = 0 )
		duration = -1 if seconds < 0 else seconds * 1000
		stream = f'silence_stream://{duration}!r,{divisor!r}'
		log.info( '%s', stream )
		return await self._playback( stream, pagd )
	
	async def action_throttle( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_throttle' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( params, 'allowedBranch', pagd, log = log ):
				return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( params, 'throttledBranch', pagd, log = log )
		
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
			async for event in self.esl.limit( backend, realm, throttle_id ):
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
		
		return await self.exec_branch( params, which, pagd, log = log )
	
	async def action_tone( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_tone' )
		if self.state == HUNT: return CONTINUE
		
		tone = str( params.get( 'tone' ) or '' ).strip()
		if not tone:
			log.error( 'Cannot play tone b/c tone=%r', tone )
			return CONTINUE
		
		loops = await self.toint( params, 'loops', default = 1 )
		stream = f'tone_stream://{tone};loops={loops}'
		log.info( 'stream=%r', stream )
		return await self._playback( stream, pagd )
	
	async def action_transfer( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_transfer' )
		if self.state == HUNT: return CONTINUE
		
		leg = cast( Literal['','-bleg','-both'], str( params.get( 'leg' ) or '' ).strip() )
		assert leg in ( '', '-bleg', '-both' ), f'invalid leg={leg!r}'
		dest = str( params.get( 'dest' ) or '' ).strip()
		dialplan = cast( Literal['','xml','inline'], str( params.get( 'dialplan' ) or '' ).strip() )
		assert dialplan in ( '', 'xml', 'inline' ), f'invalid dialplan={dialplan!r}'
		context = str( params.get( 'context' ) or '' ).strip()
		log.info( 'leg=%r dest=%r dialplan=%r context=%r',
			leg, dest, dialplan, context,
		)
		result = await self.esl.uuid_transfer( self.uuid, leg, dest, dialplan, context )
		log.info( 'result=%r', result )
		self.hangup_on_exit = False
		return STOP
	
	async def action_voicemail( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_voicemail' )
		if self.state == HUNT: return CONTINUE
		
		box: Opt[int] = await self.toint( params, 'box', expand = True )
		if box is None:
			log.warning( 'invalid box=%r', params.get( 'box' ))
			return CONTINUE
		
		vm = Voicemail( self.esl, self.uuid )
		
		if box == 0:
			if not await vm.checkin():
				return STOP
		else:
			while True:
				result, settings = await vm.guest( self.did, self.ani, box, self.notify )
				assert False, 'TODO FIXME: finish converting this code...'
		
		return CONTINUE
	
	async def notify( self, box: int, settings: SETTINGS, msg: MSG ) -> None:
		state = NotifyState( self.esl, box, msg, settings )
		delivery = settings.get( 'delivery' ) or {}
		nodes = delivery.get( 'nodes' ) or []
		await self.exec_top_actions( nodes )


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
	
	async def action_email( self, params: PARAMS ) -> RESULT:
		# TODO FIXME: might we have a use for this in CallState too?
		log = logger.getChild( 'NotifyState.action_email' )
		if self.state == HUNT: return CONTINUE
		
		ec = Email_composer()
		to: str = expect( str, params, 'mailto', default = '' )
		cc = ''
		bcc = ''
		ec.from_ = self.config.email_from
		ec.subject = expect( str, params, 'subject', default = '' )
		ec.text = expect( str, params, 'body', default = '' )
		fmt: str = expect( str, params, 'format', default = '' )
		file: Opt[Path] = None
		if self.msg is not None:
			file = self.msg.path
		
		if to == '':
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
		
		smtp.sendmail( ec.from_, list( chain( to, cc, bcc )), ec.as_bytes() )
		
		return CONTINUE
	
	async def _voice_deliver( self, params: PARAMS, number: str ) -> Tuple[bool,Opt[str]]:
		log = logger.getChild( 'NotifyState._voice_deliver' )
		
		timeout = datetime.timedelta( seconds = await self.toint( params, 'timeout', default = 0 ))
		if timeout.total_seconds() <= 0:
			timeout = datetime.timedelta( seconds = 60 )
		
		dest = f'loopback/{number}/default'
		cid_name = str( params.get( 'cid_name' ) or '' ).strip() or f'VMBox {self.box}'
		cid_num = str( params.get( 'cid_num' ) or '' ).strip() or self.config.voice_deliver_ani
		context = str( params.get( 'context' ) or '' ).strip() or 'default'
		trusted = expect( bool, params, 'trusted' )
		
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
	
	async def action_voice_deliver( self, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'NotifyState.action_voice_deliver' )
		if self.state == HUNT: return CONTINUE
		
		number = str( params.get( 'number' ) or '' ).strip()
		path = self.msg.path
		
		if not number:
			log.error( 'cannot voice deliver - no number' )
			return CONTINUE
		
		if not self.msg.path.is_file():
			log.warning( 'cannot voice deliver - wave file no longer exists' )
			return CONTINUE
		
		ok, reason = await self._voice_deliver( params, number )
		log.info( 'ok=%r, reason=%r', ok, reason )
		
		return CONTINUE


#endregion NotifyState
#region bootstrap


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
		log.debug( 'did=%r ani=%r uuid=%r', did, ani, uuid )
		
		log.debug( 'calling myevents' )
		await esl.myevents()
		
		#await esl.linger() # TODO FIXME: I'm probably going to want this...
		
		state = CallState( esl, uuid, did, ani )
		
		if True:
			async for event in esl.answer():
				log.debug( 'answer event %r', event.event_name )
			await asyncio.sleep( 0.5 )
		
		if True:
			await esl.uuid_break( uuid, 'all' )
			await esl.uuid_broadcast( uuid, 'tone_stream://$${us-ring};loops=-1', 'aleg' )
			log.debug( 'sleeping...' )
			await asyncio.sleep( 12 )
		
		if True:
			await esl.uuid_break( uuid, 'all' )
			await esl.uuid_broadcast( uuid, '$${hold_music}', 'aleg' )
			log.debug( 'sleeping...' )
			await asyncio.sleep( 12 )
		
		if True:
			log.debug( 'break...' )
			await esl.uuid_break( uuid, 'all' )
			
			async for event in esl.events():
				log.debug( 'drained event %r', event.event_name )
			
			log.debug( 'playback...' )
			async for event in esl.playback( 'ivr/ivr-welcome.wav' ):
				log.debug( 'playback event %r', event.event_name )
		
		if True:
			log.debug( 'draining events...' )
			async for event in esl.events():
				log.debug( 'drained event %r', event.event_name )
			
			log.debug( 'pagd...' )
			digits_: List[str] = []
			async for event in esl.play_and_get_digits(
				min_digits = 1,
				max_digits = 10,
				tries = 1,
				timeout = datetime.timedelta( seconds = 5 ),
				terminators = '#',
				file = 'ivr/ivr-please_enter_pin_followed_by_pound.wav',
				digits = digits_,
			):
				pass
			digits = ''.join( digits_ )
			log.debug( 'digits=%r', digits )
		
		if True:
			async for event in esl.events():
				log.debug( 'drained event %r', event.event_name )
			
			log.debug( 'record...' )
			async for event in esl.record(
				path = Path( '/tmp/test.wav' ),
				time_limit = datetime.timedelta( seconds = 30 ),
			):
				log.debug( f'record event_name=%r', event.event_name )
		
		log.debug( 'issuing hangup' )
		async for event in esl.hangup():
			log.debug( 'hangup event %r', event.event_name )
		
		#try:
		#	while True:
		#		log.warn( 'waiting for events...' )
		#		data = ( await reader.read( 4096 )).decode( 'us-ascii' )
		#		if not data: # == EOF
		#			break
		#		log.warn( f'{data=}' )
		#		#writer.write( b'foo\n' )
		#		#await writer.drain()
		#except ConnectionAbortedError:
		#	log.exception( 'Lost connection:' )
	except Exception:
		log.exception( 'Unexpected error:' )
	finally:
		log.warn( 'closing down client' )
		await esl.close()

async def _server(
	config: Config,
) -> None:
	State.config = config
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
	logging.basicConfig(
		level = logging.DEBUG,
		#level = DEBUG9,
		format = '%(asctime)s:%(levelname)s:%(name)s:%(message)s',
	)
	#print( 'repo_routes=}' )
	asyncio.run( _server( config ) )

def start( config: Config ) -> None:
	eso_process = Process(
		target = lambda: _main( config ),
		daemon = True,
	)
	eso_process.start()

#endregion bootstrap
