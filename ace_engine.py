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
from multiprocessing.synchronize import RLock as MPLock
from mypy_extensions import TypedDict
from pathlib import Path, PurePosixPath
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

# local imports:
import ace_car
from ace_fields import Field
import ace_logging
import ace_settings
from ace_tod import match_tod
import ace_util as util
from ace_voicemail import LoadBoxError, Voicemail, MSG, BOXSETTINGS, SILENCE_1_SECOND
import aiohttp_logging
import auditing
from dhms import dhms
from email_composer import Email_composer
from esl import ESL
import repo
import smtplib2
from tts import TTS, TTS_VOICES, tts_voices


#endregion imports
#region globals


logger = logging.getLogger( __name__ )

SMS_EMULATOR = False # only enable for debugging

GOTO: Final = 'goto'
EXEC: Final = 'exec'
HUNT: Final = 'hunt'
EXECSTATE = Literal['goto','exec','hunt']

CONTINUE: Final = 'continue'
STOP: Final = 'stop'
RESULT = Literal['continue','stop']

ACE_STATE = 'ace-state'
class AceState( Enum ):
	ACD_ADD = 'acd-add'
	ACD_GATE = 'acd-gate'
	ACD_UNGATE = 'acd-ungate'
	ANSWER = 'answer'
	BRIDGE = 'bridge'
	GREETING = 'greeting'
	HANGUP = 'hangup'
	IVR = 'ivr'
	MOH = 'moh'
	PAGD = 'pagd'
	PLAYBACK = 'playback'
	PLAYDTMF = 'playdtmf'
	PLAYTTS = 'playtts'
	PREANNOUNCE = 'preannounce'
	PREANSWER = 'preanswer'
	RING = 'ring'
	ROUTE = 'route'
	RXFAX = 'rxfax'
	SILENCE = 'silence'
	THROTTLE = 'throttle'
	TONE = 'tone'
	TRANSFER = 'transfer'
	VMADMIN = 'vmadmin'
	VMCHECKIN = 'vmcheckin'
	VMGUESTGRT = 'vmguestgrt'
	VMGUESTMSG = 'vmguestmsg'
	VMLOGIN = 'vmlogin'

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
	settings_path: Path
	settings_mplock: MPLock
	
	repo_anis: repo.AsyncRepository
	repo_dids: repo.AsyncRepository
	repo_routes: repo.AsyncRepository
	repo_car: repo.AsyncRepository # car == call activity report
	car_mplock: MPLock
	
	did_fields: List[Field]
	flags_path: Path
	vm_box_path: PurePosixPath
	vm_msgs_path: PurePosixPath
	owner_user: str
	owner_group: str
	
	engine_logfile: Path
	loglevels: Dict[str,str]


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

class AcdConnected( Exception ):
	def __init__( self, agent: Opt[str] = None ) -> None:
		self.agent = agent
	def __repr__( self ) -> str:
		cls = type( self )
		return f'{cls.__module__}.{cls.__qualname__}(agent={self.agent!r})'

def _on_event( event: ESL.Message ) -> None:
	log = logger.getChild( '_on_event' )
	evt_name = event.event_name
	if evt_name == 'CHANNEL_HANGUP':
		uuid = event.header( 'Unique-ID' )
		log.info( 'caught CHANNEL_HANGUP - raising ChannelHangup' )
		raise ChannelHangup( uuid )
	elif evt_name == 'CUSTOM':
		evt_name = event.header( 'Event-Subclass' )
		if evt_name == 'teledigm-acd':
			acd_event = event.header( 'acd-event' )
			evt_name = f'acd_{acd_event}'
			if evt_name == 'acd_connected':
				agent = event.header( 'acd-agent' )
				raise AcdConnected( agent = agent )
		log.debug( 'ignoring event %r', evt_name )
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


def _parse_csv_to_list( data: Opt[str] ) -> List[Dict[str,str]]:
	log = logger.getChild( '_parse_csv_to_list' )
	rows: List[Dict[str,str]] = []
	lines = re.split( r'\r\n?|\n\r?', ( data or '' ).strip() )
	log.warning( 'lines=%r', lines )
	if lines and lines[-1].startswith( '+OK' ):
		lines = lines[:-1]
	if lines:
		hdrs = lines[0].split( ',' )
		for line in lines[1:]:
			row = { key: val for key, val in zip( hdrs, line.split( ',' ))}
			rows.append( row )
	return rows


class State( metaclass = ABCMeta ):
	config: Config
	
	# operational values:
	route: int
	goto_uuid: Opt[str] = None
	
	def __init__( self, esl: ESL, uuid: str ) -> None:
		self.esl = esl
		self.uuid = uuid
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
			
			out: List[str] = []
			while True:
				m = re.search( r'\${([A-Za-z]+)\(([^\(\){}]*)\)}', s )
				if not m:
					break
				#log.debug( 'm.group(1)=%r m.group(2)=%r', m.group(1), m.group(2) )
				start = m.start()
				end = m.end()
				if start:
					out.append( s[:start] )
				try:
					args = json.loads( f'[{m.group(2)}]' )
				except Exception as e1:
					log.exception( 'Error parsing argument list %r:', m.group(2) )
					out.append( f'?{e1!r}?' )
				func = getattr( self, f'_api_{m.group(1)}', None )
				#log.debug( 'func=%r args=%r', func, args )
				if not func:
					out.append( f'?{m.group(1)}?' )
				else:
					try:
						out.append( str( await func( *args )))
					except Exception as e2:
						log.exception( 'Error calling %r with args=%r:', func, args )
						out.append( f'?{e2!r}?' )
				s = s[end:]
			if out:
				out.append( s )
				s = ''.join( out )
			
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
	
	async def _AgentsInGate( self, gate: int ) -> List[Dict[str,str]]:
		r = await self.esl.lua( 'itas/acd.lua', 'nolog', 'agent', 'list', 'gate', str( gate ))
		body = r.reply.body if r.reply else ''
		return _parse_csv_to_list( body )
	
	async def _CallsInGate( self, gate: int ) -> List[Dict[str,str]]:
		r = await self.esl.lua( 'itas/acd.lua', 'nolog', 'call', 'list', 'gate', str( gate ))
		body = r.reply.body if r.reply else ''
		return _parse_csv_to_list( body )
	
	async def _api_AgentsInGate( self, gate: int ) -> int:
		agents = await self._AgentsInGate( gate )
		return len( agents )
	
	async def _api_AgentsReady( self, gate: int ) -> int:
		agents = await self._AgentsInGate( gate )
		return len([ agent for agent in agents if agent['state'] == 'READY' ])
	
	async def _api_CallsInQueue( self, gate: int ) -> int:
		calls = await self._CallsInGate( gate )
		return len( calls )
	
	async def _api_EstWait( self, gate: int, limit: int = 10 ) -> int:
		log = logger.getChild( 'State._api_EstWait' )
		r = await self.esl.lua( 'itas/acd.lua', 'nolog', 'gate', 'estwait', str( gate ), str( limit ))
		body = r.reply.body if r.reply else ''
		try:
			estwait = int( body[3:].strip() ) if body else 0
		except Exception as e:
			log.exception( 'Error parsing estwait body %r: %r', body, e )
			estwait = 0
		return estwait
	
	async def tonumber( self, data: Map[str,Any], name: str, *, expand: bool = False, default: Opt[Union[int,float]] = None ) -> Union[int,float]:
		value = data.get( name )
		if value is None:
			if default is not None:
				return default
		else:
			if expand:
				value = await self.expand( str( value ))
			if isinstance( value, ( int, float )):
				return value
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
			if isinstance( value, int ):
				return value
			try:
				return int( value )
			except ValueError:
				pass
		raise ValueError( f'Expecting {name!r} of type convertable to int/float but got {value!r}' )
	
	async def car_activity( self, msg: str ) -> None:
		await ace_car.activity(
			self.config.repo_car,
			self.config.car_mplock,
			self.uuid,
			msg,
		)
	
	async def load_route( self, route: int ) -> Dict[str,Any]:
		return await self.config.repo_routes.get_by_id( route )
	
	async def exec_branch( self, action: ACTION, which: str, pagd: Opt[PAGD], *, log: logging.Logger ) -> RESULT:
		branch: BRANCH = cast( BRANCH, expect( dict, action.get( which ), default = {} ))
		return await self._exec_branch( which, branch, pagd, log = log )
	
	async def _exec_branch( self, which: str, branch: BRANCH, pagd: Opt[PAGD], *, log: logging.Logger ) -> RESULT:
		name: Opt[str] = branch.get( 'name' )
		nodes: ACTIONS = expect( list, branch.get( 'nodes' ) or [] )
		if which:
			log.info( 'executing %s branch %r', which, name )
			await self.car_activity( f'executing {which} branch {name!r}' )
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
			await self.car_activity(
				f'ERROR: cannot execute action named {action.get("name")!r} missing "type"'
			)
			return CONTINUE
		fname = f'action_{action_type}'
		f: Opt[Callable[[ACTION,Opt[PAGD]],Awaitable[RESULT]]] = getattr( self, fname, None )
		if not f or not callable( f ):
			log.error( 'action invalid or unavailable in this context: %r', action_type )
			await self.car_activity(
				f'ERROR: action {action_type!r} invalid or unavailable in this context'
			)
			return CONTINUE
		log.debug( 'executing %r', fname )
		await self.car_activity(
			f'exec_action: executing {action_type!r} action named {action.get("name")!r}'
		)
		r = await f( action, pagd )
		log.debug( '%s -> %r', fname, r )
		if r not in ( CONTINUE, STOP ):
			log.error( '%s returned %r but should have returned %r or %r',
				fname, r, CONTINUE, STOP,
			)
			await self.car_activity(
				f'ERROR: ACE bug - action {action_type!r} returned {r!r}'
				f' but should have returned {CONTINUE!r} or {STOP!r}'
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
		await self.car_activity( f'goto initiated, looking for {self.goto_uuid!r}' )
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
		await self.car_activity( f'ifnum lhs={lhs!r} op={op!r} rhs={rhs!r} result={result!r} branch={which!r}' )
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
		await self.car_activity( f'ifstr lhs={lhs!r} op={op!r} rhs={rhs!r} result={result!r} branch={which!r}' )
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
				await self.car_activity( f'goto found {self.goto_uuid!r}' )
				self.state = EXEC
			else:
				log.info( 'PASS name=%r', action.get( 'name' ))
		return CONTINUE
	
	async def action_log( self, action: ACTION_LOG, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_log' )
		if self.state == HUNT: return CONTINUE
		
		level = action.get( 'level' ) or 'DEBUG'
		text = await self.expand( action.get( 'text' ) or '?' )
		log.debug( 'level=%r text=%r', level, text )
		await self.esl.log( level, text )
		await self.car_activity( f'[{level}] {text}' )
		
		return CONTINUE
	
	async def action_lua( self, action: ACTION_LUA, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_lua' )
		if self.state == HUNT: return CONTINUE
		
		#source = ( action.get( 'source' ) or '' ).strip()
		#if not source:
		#	log.error( 'cannot execute lua code: source is empty' )
		#	return CONTINUE
		
		log.error( 'TODO FIXME: inline lua not implemented in current version of ace' )
		await self.car_activity( f'ERROR: TODO FIXME: inline lua not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_laufile( self, action: ACTION_LUAFILE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_luafile' )
		if self.state == HUNT: return CONTINUE
		
		file = ( action.get( 'file' ) or '' ).strip()
		if not file:
			log.error( 'cannot execute lua file: no filename provided' ) # TODO FIXME: log some of this stuff to freeswitch console?
			await self.car_activity( f'ERROR: cannot execute lua b/c file={file!r}' )
			return CONTINUE
		
		log.error( 'TODO FIXME: lua file not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_python( self, action: ACTION_PYTHON, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_python' )
		if self.state == HUNT: return CONTINUE
		
		log.error( 'TODO FIXME: python not implemented in current version of ace' )
		await self.car_activity( f'ERROR: TODO FIXME: python not implemented in current version of ace' )
		
		return CONTINUE
	
	async def action_repeat( self, action: ACTION_REPEAT, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_repeat' )
		count: int = await self.toint( action, 'count', default = 0 )
		nodes = cast( ACTIONS, expect( list, action.get( 'nodes' ), default = [] ))
		i: int = 1
		while count == 0 or i <= count:
			if self.state != HUNT:
				log.info( 'starting loop %r of %s', i, count or 'infinite' )
				await self.car_activity( f'repeat node starting loop {i!r} of {count or "infinite"!r}' )
			if STOP == await self.exec_actions( nodes ):
				return STOP
			if self.state == HUNT: return CONTINUE
			i += 1
		return CONTINUE
	
	async def _sms_thinq( self, smsto: str, message: str, settings: ace_settings.Settings ) -> RESULT:
		log = logger.getChild( 'State._sms_thinq' )
		
		url = f'https://api.thinq.com/account/{settings.sms_thinq_account}/product/origination/sms/send'
		if SMS_EMULATOR: # enable this for testing with sms_emulators.py
			url = 'http://127.0.0.1:8080/thinq/send'
		auth = base64.b64encode(
			f'{settings.sms_thinq_username}:{settings.sms_thinq_api_token}'.encode( 'utf-8' )
		).decode( 'us-ascii' )
		
		headers = {
			'Authorization': f'Basic {auth}',
		}
		formdata = {
			'from_did': settings.sms_thinq_from,
			'to_did': smsto,
			'message': message,
		}
		async with aiohttp.ClientSession() as session:
			async with session.post( url, headers = headers, data = formdata ) as rsp:
				try:
					text = await rsp.text()
				except Exception as e1:
					log.error( 'sms to %r failure: %r', smsto, e1 )
					await self.car_activity( f'ERROR: sms to {smsto!r} failed: {e1!r}' )
				else:
					try:
						jdata = json.loads( text ) # TODO FIXME: json decoding failure
					except Exception as e2:
						log.error( 'sms to %r failure: %r decoding json=%r', smsto, e2, text )
						await self.car_activity( f'ERROR: sms to {smsto!r} got {e2!r} decoding response {text!r}' )
					else:
						guid = jdata.get( 'guid' ) if isinstance( jdata, dict ) else None
						if guid:
							log.info( 'sms to %r success (guid=%r)', smsto, guid )
							await self.car_activity( f'sms to {smsto!r} success (guid={guid!r})' )
						else:
							log.error( 'sms to %r failure: %r', smsto, jdata )
							await self.car_activity( f'ERROR: sms to {smsto!r} failed: {jdata!r}' )
		return CONTINUE
	
	async def _sms_twilio( self, smsto: str, message: str, settings: ace_settings.Settings ) -> RESULT:
		log = logger.getChild( 'State._sms_twilio' )
		
		url = f'https://api.twilio.com/2010-04-01/Accounts/{settings.sms_twilio_sid}/Messages.json'
		if SMS_EMULATOR: # enable this for testing with sms_emulators.py
			url = 'http://127.0.0.1:8080/twilio/send'
		auth = base64.b64encode(
			f'{settings.sms_twilio_sid}:{settings.sms_twilio_token}'.encode( 'utf-8' )
		).decode( 'us-ascii' )
		
		headers = {
			'Authorization': f'Basic {auth}',
		}
		formdata = {
			'From': settings.sms_twilio_from,
			'To': f'+1{smsto}',
			'Body': message,
		}
		async with aiohttp.ClientSession() as session:
			async with session.post( url, headers = headers, data = formdata ) as rsp:
				try:
					text = await rsp.text()
				except Exception as e1:
					log.error( 'sms to %r failure: %r', smsto, e1 )
					await self.car_activity( f'ERROR: sms to {smsto!r} failed: {e1!r}' )
				else:
					try:
						jdata = json.loads( text ) # TODO FIXME: json decoding failure
					except Exception as e2:
						log.error( 'sms to %r failure: %r decoding json=%r', smsto, e2, text )
						await self.car_activity( f'ERROR: sms to {smsto!r} got {e2!r} decoding response {text!r}' )
					else:
						status = jdata.get( 'status' )
						if status == 'queued':
							log.info( 'sms to %r success: status=%r', smsto, status )
							await self.car_activity( f'sms to {smsto!r} success: status={status!r}' )
						else:
							errmsg = jdata.get( 'message' )
							if errmsg:
								log.error( 'sms to %r failure: %r %r', smsto, status, errmsg )
								await self.car_activity( f'ERROR: sms to {smsto!r} failure: {status!r} {errmsg!r}' )
							else:
								log.error( 'sms to %r failure: %r', smsto, jdata )
								await self.car_activity( f'ERROR: sms to {smsto!r} failure: {jdata!r}' )
		return CONTINUE
	
	async def action_sms( self, action: ACTION_SMS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_sms' )
		if self.state == HUNT: return CONTINUE
		
		settings = await ace_settings.aload()
		
		smsto: str = str( action.get( 'smsto' ) or '' ).strip() # TODO FIXME: thinq expects 'XXXXXXXXXX'
		message: str = str( action.get( 'message' ) or '' ).strip()
		if not message:
			boxsettings = cast( Opt[BOXSETTINGS], getattr( self, 'settings', None ))
			if boxsettings:
				message = ( boxsettings.get( 'default_sms_message' ) or '' ).strip()
			if not message:
				message = ( settings.sms_message or '' ).strip()
				if not message:
					message = 'New VM Message from ${ani} Pls call ${did} to check your VM'
		
		message = message.replace( '\n', '\\n' ) # TODO FIXME: why is this necessary?
		message = await self.expand( message )
		
		if not smsto:
			log.warning( 'cannot send sms - no recipient' )
			await self.car_activity( f'ERROR: cannot send sms b/c smsto={smsto!r}' )
			return CONTINUE
		
		if settings.sms_carrier == 'thinq':
			return await self._sms_thinq( smsto, message, settings )
		elif settings.sms_carrier == 'twilio':
			return await self._sms_twilio( smsto, message, settings )
		else:
			log.error( 'cannot send sms, invalid sms_carrier=%r', settings.sms_carrier )
			await self.car_activity( f'ERROR: cannot send sms b/c sms_carrier={settings.sms_carrier!r}' )
			return CONTINUE
	
	async def action_tod( self, action: ACTION_TOD, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'State.action_tod' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'hit', pagd, log = log ):
				return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'miss', pagd, log = log )
		
		which = 'miss'
		if match_tod( expect( str, action.get( 'times' ) or '' )):
			# make sure holiday params match too
			log.warning( 'TODO FIXME: implement holidays' )
			which = 'hit'
		
		await self.car_activity( f'tod executing {which!r} branch' )
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
			await self.car_activity( 'action_wait: playing silence for {seconds!r} second(s) b/c pagd is active' )
			return await self.action_silence( params2, pagd )
		else:
			log.info( 'waiting for %r second(s)', seconds )
			await self.car_activity( f'waiting for {seconds!r} second(s)' )
			done = time.time() + seconds
			while True:
				remaining = done - time.time()
				if remaining < 0.05:
					break
				timeout_seconds = remaining * 0.5 if remaining > 0.5 else remaining
				async for event in self.esl.events( timeout = timeout_seconds ):
					_on_event( event )
		
		return CONTINUE


#endregion State
#region CallState


class CallState( State ):
	box: Opt[int] = None # set to an integer if we're inside of a specific voicemail box
	hangup_on_exit: bool = True
	
	def __init__( self, esl: ESL, uuid: str, did: str, ani: str ) -> None:
		super().__init__( esl, uuid )
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
	
	async def set_state( self, state: AceState ) -> None:
		await self.esl.uuid_setvar( self.uuid, ACE_STATE, state.value )
	
	async def try_ani( self ) -> Opt[Union[int,str]]:
		log = logger.getChild( 'CallState.try_ani' )
		
		try:
			data = await self.config.repo_anis.get_by_id( self.ani )
		except repo.ResourceNotFound as e:
			log.debug( 'no config found for ani %r', self.ani )
			await self.car_activity( f'no ANI config for {self.ani!r}' )
			return None
		
		# first check for DID overrides
		overrides = str( data.get( 'overrides' ) or '' )
		for lineno, override in enumerate( overrides.split( '\n' ), start = 1 ):
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
					await self.car_activity( f'ANI {self.ani!r} override line # {lineno!r} -> route {route_!r}' )
					await self.esl.uuid_setvar( self.uuid, 'route', route_ )
					try:
						return int( route_ ) # TODO FIXME: ability to send to a voicemail box, too?
					except ValueError:
						log.warning( 'unable to convert route %r to an integer', route_ )
			#else:
			#	log.debug( 'ignoring did2=' .. did2 )
		
		route = cast( Opt[int], data.get( 'route' ))
		if isinstance( route, int ):
			log.debug( 'ani=%r did=* -> route=%r', self.ani, route )
			await self.car_activity( f'ANI {self.ani!r} no override match, using default route={route!r}' )
			await self.esl.uuid_setvar( self.uuid, 'route', str( route ))
			return route
		elif route is not None:
			await self.car_activity( f'ERROR ani {self.ani} has invalid route={route!r}' )
			log.warning( 'invalid route=%r', route )
		
		await self.car_activity( f'config found for ANI {self.ani}, but no matching overrides and no default route specified' )
		return None
	
	async def try_did( self, ani_route: Opt[Union[int,str]] ) -> Tuple[Opt[Union[int,str]],Opt[Dict[str,Any]]]:
		log = logger.getChild( 'CallState.try_did' )
		try:
			data = await self.config.repo_dids.get_by_id( self.did )
		except repo.ResourceNotFound as e:
			log.debug( 'no config found for did %r', self.did )
			await self.car_activity( f'no DID config for {self.did!r}' )
			return None, None
		
		acct_num = data.get( 'acct' )
		acct_name = data.get( 'name' )
		if acct_num is not None or acct_name:
			await self.esl.uuid_setvar( self.uuid, 'ace-acct-num', str( acct_num or '' ))
			await self.esl.uuid_setvar( self.uuid, 'ace-acct-name', str( acct_name or '' ))
			await self.config.repo_car.update( self.uuid,
				{
					'acct_num': acct_num,
					'acct_name': acct_name,
				},
				audit = auditing.NoAudit(),
			)
		
		if ani_route:
			log.debug( 'DID config ignoring route b/c ani_route=%r', ani_route )
			await self.car_activity( f'DID config ignoring route b/c ani_route={ani_route!r}' )
			route: Opt[Union[int,str]] = ani_route
		else:
			route = data.get( 'route' ) or None
			log.debug( 'DID config got route=%r', route )
			await self.car_activity( f'DID config got route={route!r}' )
		
		for fld in self.config.did_fields:
			value = str( data.get( fld.field ) or '' ).strip()
			if value is not None:
				log.debug( 'setting field %r to %r', fld.field, value )
				await self.car_activity( f'DID config setting channel variable {fld.field!r}={value!r}' )
				await self.esl.uuid_setvar( self.uuid, fld.field, value )
			#else:
			#	log.debug( 'skipping field %r b/c value %r', fld.field, value )
		
		variables = str( data.get( 'variables' ) or '' )
		for variable in variables.split( '\n' ):
			field, _, value = map( str.strip, variable.partition( '=' ))
			if field and value:
				log.debug( 'setting variable %r to %r', field, value )
				await self.car_activity( f'DID config setting channel variable {field!r}={value!r}' )
				await self.esl.uuid_setvar( self.uuid, field, value )
		
		await self.car_activity( f'DID config returning route={route!r}' )
		return route, data
	
	async def load_flag( self, flag_name: str ) -> Opt[str]:
		flag_path = self.config.flags_path / f'{flag_name}.flag'
		try:
			async with aiofiles.open( str( flag_path ), 'r' ) as f:
				flag = await f.read()
		except FileNotFoundError as e:
			#raise repo.ResourceNotFound( str( flag_path )).with_traceback( e.__traceback__ ) from None
			return None
		return flag.strip() or None
	
	async def try_wav( self, filename: str ) -> Opt[Path]:
		log = logger.getChild( 'CallState.try_wav' )
		settings = await ace_settings.aload()
		path = Path( settings.preannounce_path ) / f'{filename}.wav'
		path_ = str( path )
		if not path.is_file():
			log.debug( 'path not found: %r', str( path ))
			await self.car_activity( f'try_wav: preannounce path not found: {path_!r}' )
			return None
		log.debug( 'found path: %r', path_ )
		return path
	
	async def set_preannounce( self, didinfo: Dict[str,Any] ) -> None:
		log = logger.getChild( 'CallState.set_preannounce' )
		
		path: Opt[Path] = None
		
		async def _setvar( key: str, val: str ) -> None:
			await self.car_activity( f'set_preannounce: setting channel variable {key!r}={val!r}' )
			await self.esl.uuid_setvar( self.uuid, key, val )
		
		global_flag = await self.load_flag( 'global_flag' )
		
		if global_flag:
			await _setvar( 'ace-global_flag', global_flag )
			if not path:
				path2 = await self.try_wav( f'global_{global_flag}' )
				if path2:
					path = path2
		else:
			await self.car_activity( 'set_preannounce: global flag not set' )
		
		category = ( didinfo.get( 'category' ) or '' ).strip()
		if category:
			await _setvar( 'ace-category', category )
			cat_flag = await self.load_flag( f'category_{category}' )
			if cat_flag:
				await _setvar( 'ace-category_flag', cat_flag )
				if not path:
					path2 = await self.try_wav( f'category_{category}_{cat_flag}' )
					if path2:
						path = path2
			else:
				await self.car_activity( f'set_preannounce: category flag {category!r} not set' )
		else:
			await self.car_activity( 'set_preannounce: no category configured' )
		
		acct = str( didinfo.get( 'acct' ) or '' ).strip()
		if acct:
			acct_flag = ( didinfo.get( 'acct_flag' ) or '' ).strip()
			if acct_flag:
				await _setvar( 'ace-acct_flag', acct_flag )
				if not path:
					path2 = await self.try_wav( f'{acct}_{acct_flag}' )
					if path2:
						path = path2
			else:
				await self.car_activity( 'set_preannounce: acct # flag not set' )
		else:
			await self.car_activity( 'set_preannounce: acct # not set' )
		
		did_flag = ( didinfo.get( 'did_flag' ) or '' ).strip()
		if did_flag:
			await _setvar( 'ace-did_flag', did_flag )
			if not path:
				path2 = await self.try_wav( f'{self.did}_{did_flag}' )
				if path2:
					path = path2
		else:
			await self.car_activity( 'set_preannounce: did flag not set' )
		
		#holiday = holidays.today()
		#if holiday ~= nil then
		#	holname = string.upper( holiday.name )
		#	holname = holname:gsub( ' ', '' )
		#	if await self.try_wav( uuid, did .. '_' .. holname ) then return end
		#	if await self.try_wav( uuid, did .. '_HOLIDAY' ) then return end
		#else
		#	log.debug( 'not a holiday' )
		#end
		
		async def _uuid_gethhmm( key: str, default: str ) -> str:
			value = await self.esl.uuid_getvar( self.uuid, key )
			if value is None:
				return default
			m = re.match( r'^(\d\d?):(\d\d)', value )
			if m:
				hr = int( m.group( 1 ))
				mn = int( m.group( 2 ))
				return f'{hr:02}:{mn:02}'
			try:
				h = int( value )
			except ValueError as e:
				log.warning( 'Could not convert %r value %r to an integer or an HH:MM timestamp: %r', key, value, e )
				return default
			else:
				return f'{h:02}:00'
		
		# BEGIN bushrs stuff
		# DOW table: Sun=1 Mon=2 Tue=3 Wed=4 Thu=5 Fri=6 Sat=7
		if not path:
			bushrs_start = await _uuid_gethhmm( 'bushrs_start', '08:00' ) # TODO FIXME: support 'HH:MM'
			bushrs_end = await _uuid_gethhmm( 'bushrs_end', '17:00' )
			bushrs_dow = await self.esl.uuid_getvar( self.uuid, 'bushrs_dow' ) or '23456' # M-F
			now = datetime.datetime.now()
			now_dow = str(( now.weekday() + 1 ) % 7 + 1 ) # now.weekday() MON=0 ... SUN=6, we need SUN=1 ... SAT=7
			log.debug( 'bushrs_dow=%r, now_dow=%r', bushrs_dow, now_dow )
			tod = 'AFTHRS'
			if now_dow in bushrs_dow:
				now_hhmm = f'{now.hour:02}:{now.minute:02}'
				if now_hhmm >= bushrs_start and now_hhmm <= bushrs_end:
					tod = 'BUSHRS'
				else:
					log.debug( 'hour mismatch' )
			else:
				log.debug( 'dow mismatch' )
			
			tod_preannounce: str = ( await self.esl.uuid_getvar( self.uuid, f'{tod.lower()}_preannounce' ) or '' ).strip()
			path2 = await self.try_wav( tod_preannounce or f'{self.did}_{tod}' )
			if path2:
				path = path2
		
		if not path:
			path2 = await self.try_wav( str( self.did ))
			if path2:
				path = path2
		
		if not path:
			path2 = await self.try_wav( 'default' )
			if path2:
				path = path2
		
		if path:
			path_ = str( path )
			varname = 'ace-preannounce_wav'
			await _setvar( varname, path_ )
		else:
			log.debug( 'no preannounce recording found' )
			await self.car_activity( 'set_preannounce: no preannounce recording found' )
	
	async def _pagd( self, action_type: str, action: Union[ACTION_IVR,ACTION_PAGD], success: Callable[[str],Coroutine[Any,Any,Opt[RESULT]]] ) -> RESULT:
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
				await self.car_activity( f'{action_type} beginning greeting attempt {attempt!r} of {max_attempts!r}' )
				r = await self.exec_branch( action, 'greetingBranch', pagd, log = log )
				if r == STOP: return STOP
				if not pagd.digits:
					await self.car_activity( f'{action_type} post-greeting auto-silence b/c digits={pagd.digits!r}' )
					r = await self.action_silence( ACTION_SILENCE(
						type = 'silence',
						name = '',
						seconds = 3,
						divisor = 0,
					), pagd )
					log.info( 'back from post-greeting auto-silence with r=%r, digits=%r, valid=%r',
						r, pagd.digits, pagd.valid
					)
					await self.car_activity( f'{action_type} post-greeting auto-silence result={r!r}, digits={pagd.digits!r}, valid={pagd.valid!r}' )
					if r == STOP: return STOP
			else:
				log.info( 'skipped greeting branch because digits=%r, valid=%r',
					pagd.digits, pagd.valid,
				)
				await self.car_activity( f'{action_type} skipped greeting b/c digits={pagd.digits!r}, valid={pagd.valid!r}' )
			
			if pagd.digits and pagd.valid:
				result = await success( pagd.digits )
				if result is not None:
					return result
			if attempt < max_attempts:
				if pagd.digits:
					pagd.digits = None
					await self.car_activity( f'{action_type} executing invalid branch b/c digits={pagd.digits!r}' )
					r = await self.exec_branch( action, 'invalidBranch', pagd, log = log )
					if r == STOP: return STOP
				else:
					await self.car_activity( f'{action_type} executing timeout branch b/c digits={pagd.digits!r}' )
					r = await self.exec_branch( action, 'timeoutBranch', pagd, log = log )
					if r == STOP: return STOP
			else:
				await self.car_activity( f'{action_type} executing failure branch b/c attempt {attempt!r} of max_attempts {max_attempts!r}' )
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
				dhms( timeout ),
				terminators,
				sound,
				error,
				digit_regex,
				variable_name,
				dhms( digit_timeout ),
			)
			digits_: List[str] = []
			await self.car_activity( '_playback: '
				f'PlayAndGetDigits(min={min_digits!r}'
				f',max={max_digits!r}'
				f',tries={max_attempts!r}'
				f',timeout={dhms(timeout)}'
				f',term={terminators!r}'
				f',file={sound!r}'
				f',err={error!r}'
				f',var={variable_name!r}'
				f',re={digit_regex!r}'
				f',dig_timeout={dhms(digit_timeout)}'
				')'
			)
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
			#log.info( 'got digits=%r', pagd.digits )
			await self.car_activity( f'_playback: PlayAndGetDigits(file={sound!r}, ...) -> digits={pagd.digits!r}' )
			
			pagd.valid = True
			if pagd.digit_regex:
				log.debug( 'call regex( %r, %r )', pagd.digits, pagd.digit_regex )
				pagd.valid = await self.esl.regex( pagd.digits, pagd.digit_regex )
				await self.car_activity( f'_playback: digits {pagd.digits!r} vs digit regex {pagd.digit_regex!r} -> valid={pagd.valid!r}' )
			log.info( 'got digits=%r valid=%r', pagd.digits, pagd.valid )
			return CONTINUE
		else:
			log.debug( 'executing break all' )
			await self.esl.uuid_break( self.uuid, 'all' )
			
			log.info( 'executing playback %r', sound )
			await self.car_activity( f'_playback: playback( sound={sound!r} )' )
			async for event in self.esl.playback( self.uuid, sound ):
				_on_event( event )
			
			return CONTINUE
	
	async def action_acd_call_add( self, action: ACTION_ACD_CALL_ADD, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_add' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.ACD_ADD )
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
		await self.car_activity( f'call queued to acd gates={gates!r} at priority={priority!r} and queue_offset_seconds={queue_offset_seconds!r} with result={r!r}' )
		
		return CONTINUE
	
	async def action_acd_call_gate( self, action: ACTION_ACD_CALL_GATE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_gate' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.ACD_GATE )
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
		await self.car_activity( f'call queued to addl acd gate={gate!r} at priority={priority!r} with result={r!r}' )
		
		return CONTINUE
	
	async def action_acd_call_ungate( self, action: ACTION_ACD_CALL_UNGATE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_acd_call_ungate' )
		if self.state == HUNT: return CONTINUE
		
		gate: str = str( action.get( 'gate' ) or '' )
		
		await self.set_state( AceState.ACD_UNGATE )
		r = await self.esl.luarun(
			'itas/acd.lua',
			'call',
			'ungate',
			self.uuid,
			gate,
		)
		log.debug( 'result: %r', r )
		await self.car_activity( f'call removed from acd gate={gate!r} with result={r!r}' )
		
		return CONTINUE
	
	async def action_answer( self, action: ACTION_ANSWER, pagd: Opt[PAGD] ) -> RESULT:
		#log = logger.getChild( 'CallState.action_answer' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.ANSWER )
		if not await util.answer( self.esl, self.uuid, 'ace_eso.CallState.action_answer' ):
			return STOP
		await self.car_activity( f'answer supervision sent' )
		
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
		except Exception as e1:
			log.exception( 'Unable to filter for bridge_uuid: %r' )
			await self.car_activity( f'ERROR: could not bridge because filter failed: {e1!r}' )
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
			
			await self.car_activity( f'initiating originate(dial_string={dial_string!r}, origin={origin!r}, dialplan={dialplan!r}, context={context!r}, cid_name={cid_name!r}, cid_num={cid_num!r}, timeout={timeout!r}, chanvars={chanvars!r})' )
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
			except Exception as e2:
				log.exception( 'Error trying to originate for bridge:' )
				await self.car_activity( f'ERROR: originate(dial_string={dial_string!r}, ...) -> {e2!r}' )
				return '-ERR originate failed'
			log.debug( 'originate -> %r', r )
			await self.car_activity( f'originate(dial_string={dial_string!r}, ...) -> {r!r}' )
			
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
						await self.car_activity( f'bridge proceeding on event {evt_name!r}' )
						answered = True
						break
					elif evt_name in terminators:
						await self.car_activity( f'ERROR: bridge failed because got event {evt_name!r} waiting for answer' )
						return '-ERR NO_ANSWER'
				if originate_timer.elapsed():
					r = await self.esl.uuid_kill( bridge_uuid, 'ORIGINATOR_CANCEL' )
					log.info( 'timeout before CHANNEL_ANSWER, uuid_kill -> %r', r )
					await self.car_activity( 'ERROR: bridge failed because timeout waiting for originate to be answered' )
					return '-ERR NO_ANSWER'
				if exists_timer.elapsed():
					if not await self.esl.uuid_exists( self.uuid ):
						r = await self.esl.uuid_kill( bridge_uuid, 'ORIGINATOR_CANCEL' )
						log.info( 'aleg disappeared, uuid_kill -> %r', r )
						await self.car_activity( 'ERROR: bridge failed because aleg disappeared' )
						return '-ERR aleg uuid disappeared'
			
			try:
				await self.esl._uuid_bridge( self.uuid, bridge_uuid )
			except Exception as e3:
				log.error( 'uuid_bridge failed: %r', e3 )
				await self.car_activity( f'ERROR: uuid_bridge failed b/c {e3!r}' )
				return f'-ERR bridge failed: {e3!r}'
			else:
				log.info( 'uuid_bridge success' )
				await self.car_activity( 'originate successfully bridged' )
			
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
		
		await self.car_activity( 'auto-answering call b/c bridge requested' )
		if not await util.answer( self.esl, self.uuid, 'action_bridge' ):
			return STOP
		
		result = await self._bridge( action )
		
		if result[:3] == '+OK':
			await self.car_activity( f'bridge succeeded with {result!r}' )
			return CONTINUE
		
		# origination failed:
		which = 'timeoutBranch' if 'NO_ANSWER' in result else 'failBranch'
		await self.car_activity( f'ERROR: bridge failed with {result!r}, executing branch {which!r}' )
		await self.set_state( AceState.BRIDGE )
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def _greeting( self, action: ACTION_GREETING, box: int, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState._greeting' )
		greeting: int = await self.toint( action, 'greeting', default = 1 )
		settings = await ace_settings.aload()
		await self.set_state( AceState.GREETING )
		vm = Voicemail( self.esl, self.uuid, settings )
		if greeting < 1 or greeting > 9:
			try:
				boxsettings: BOXSETTINGS = await vm.load_box_settings( box )
			except LoadBoxError as e:
				log.error( 'invalid box=%r (%r)', box, e )
				await self.car_activity( f'ERROR: Could not playing greeting for vm box {box!r} b/c {e!r}' )
				return CONTINUE
			greeting = await self.toint( action, 'greeting', default = 1 )
		path = vm.box_greeting_path( box, greeting )
		if path and Path( path ).is_file():
			sound: str = str( path )
			await self.car_activity( f'playing vm box {box!r} greeting at {sound!r}' )
		else:
			log.error( 'invalid or non-existing greeting path: %r', path )
			await self.car_activity( f'ERROR: invalid or non-existing vm box {box!r} greeting path {path!r}' )
			sound = await vm._error_greeting_file_missing( box, greeting )
		return await self._playback( sound, pagd )
	
	async def action_greeting( self, action: ACTION_GREETING, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_greeting' )
		if self.state == HUNT: return CONTINUE
		
		box: int = await self.toint( action, 'box', default = 0 )
		if not box: # "current" box
			if not self.box:
				log.error( 'current box requested but not currently inside the digit map of a voicemail box' )
				await self.car_activity( 'ERROR: current vm box greeting requested but not currently inside the digit map of a voicemail box' )
				return CONTINUE
			box = self.box
		
		return await self._greeting( action, box, pagd )
	
	async def action_greeting2( self, action: ACTION_GREETING, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_greeting2' )
		if self.state == HUNT: return CONTINUE
		
		box: Opt[int] = await self.toint( action, 'box' )
		if not box:
			log.error( 'no box # specified' )
			await self.car_activity( f'ERROR: cannot play greeting b/c box={box!r}' )
			return CONTINUE
		
		return await self._greeting( action, box, pagd )
	
	async def action_hangup( self, action: ACTION_HANGUP, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_hangup' )
		if self.state == HUNT: return CONTINUE
		
		cause: util.CAUSE = cast( util.CAUSE, expect( str, action.get( 'cause' ), default = 'NORMAL_CLEARING' ))
		if cause not in util.causes:
			log.warning( f'unrecognized hangup cause={cause!r}' )
			await self.car_activity( f'WARNING: unrecognized hangup cause={cause!r}' )
		await self.car_activity( f'Hanging up call with cause={cause!r}' )
		await self.set_state( AceState.HANGUP )
		try:
			await util.hangup( self.esl, self.uuid, cause, 'action_hangup' )
		except Exception as e:
			await self.car_activity( f'ERROR: hangup failed with {e!r}' )
		return STOP
	
	async def action_ivr( self, action: ACTION_IVR, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_ivr' )
		
		if pagd is not None:
			log.error( 'cannot execute a PAGD in the greeting path of another PAGD/IVR' )
			await self.car_activity( f'ERROR: cannot execute a PAGD in the greeting path of another PAGD/IVR' )
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
				await self.car_activity( f'IVR executing branch {branch.get("name")!r} from digits={digits!r}' )
				return await self._exec_branch( digits, branch, None, log = log )
			else:
				log.error( 'no branch found for digits=%r', digits )
				await self.car_activity( f'IVR does not have a branch for digits={digits!r}' )
				return None
		
		_ = await util.answer( self.esl, self.uuid, 'CallState.action_ivr' )
		
		await self.set_state( AceState.IVR )
		return await self._pagd( 'IVR', action, _success )
	
	async def _broadcast( self, action_type: str, stream: Opt[str], *, default: str, log: logging.Logger ) -> RESULT:
		log2 = log.getChild( '_broadcast' )
		if self.state == HUNT: return CONTINUE
		
		stream = await self.expand(( stream or '' ).strip() or default )
		
		log.debug( 'breaking' )
		await self.esl.uuid_break( self.uuid, 'all' )
		
		# check for events: if acd picked up the call, we don't want to queue more music...
		async for event in self.esl.events( timeout = 0.01 ):
			_on_event( event )
		
		log.info( 'playing %r', stream )
		await self.car_activity( f'broadcasting stream {stream!r}' )
		await self.esl.uuid_broadcast( self.uuid, stream, 'aleg' )
		
		return CONTINUE
	
	async def action_moh( self, action: ACTION_MOH, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_moh' )
		await self.set_state( AceState.MOH )
		return await self._broadcast( 'MOH', action.get( 'stream' ), default = '$${hold_music}', log = log )
	
	async def action_pagd( self, action: ACTION_PAGD, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_pagd' )
		
		if pagd is not None:
			log.error( 'cannot execute a PAGD in the greeting path on another PAGD or an IVR' )
			await self.car_activity( f'ERROR: cannot execute a PAGD in the greeting path of another PAGD/IVR' )
			return CONTINUE
		
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'successBranch', None, log = log ): return STOP
			if self.state != HUNT: return CONTINUE
			
			return await self.exec_branch( action, 'failureBranch', None, log = log )
		
		async def _success( digits: str ) -> Opt[RESULT]:
			await self.car_activity( f'PAGD executing success branch on digits={digits!r}' )
			return await self.exec_branch( action, 'successBranch', None, log = log )
		
		_ = await util.answer( self.esl, self.uuid, 'CallState.action_pagd' )
		
		await self.set_state( AceState.PAGD )
		return await self._pagd( 'PAGD', action, _success )
	
	async def action_playback( self, action: ACTION_PLAYBACK, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_playback' )
		if self.state == HUNT: return CONTINUE
		
		try:
			sound = expect( str, action.get( 'sound' ) )
			log.info( 'sound=%r', sound )
			await self.car_activity( f'playback executing with sound={sound!r}' )
		except ValueError as e:
			sound = 'ivr/ivr-invalid_sound_prompt.wav'
			await self.car_activity( f'playback using default sound={sound!r} b/c {e!r}' )
		await self.set_state( AceState.PLAYBACK )
		return await self._playback( sound, pagd )
	
	async def action_playtts( self, action: ACTION_PLAYTTS, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_playtts' )
		if self.state == HUNT: return CONTINUE
		
		settings = await ace_settings.aload()
		
		text = await self.expand( action.get( 'text' ) or '' )
		if not text:
			log.error( 'tts node has no text prompt' )
			text = 'Error'
			await self.car_activity( f'ERROR: TTS node defaulting to {text!r} b/c no text provided' )
		voice = action.get( 'voice' )
		await self.car_activity( f'TTS initiated with voice={voice!r}, text={text!r}' )
		tts = settings.tts( action.get( 'voice' ))
		tts.say( text )
		stream = await tts.generate()
		r = await self._playback( str( stream ), pagd )
		log.info( 'done playing %r using voice %r: result=%r',
			text, tts.voice, r,
		)
		await self.car_activity( f'TTS result={r!r}' )
		await self.set_state( AceState.PLAYTTS )
		return r
	
	async def action_play_dtmf( self, action: ACTION_PLAY_DTMF, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_play_dtmf' )
		if self.state == HUNT: return CONTINUE
		
		dtmf = action.get( 'dtmf' ) or ''
		if dtmf:
			await self.set_state( AceState.PLAYDTMF )
			r = await self.esl.uuid_send_dtmf( self.uuid, dtmf )
			log.info( 'uuid_send_dtmf( %r, %r ) -> %r', self.uuid, dtmf, r )
			await self.car_activity( f'uuid_send_dtmf({dtmf!r}) -> {r!r}' )
		else:
			log.error( 'no dtmf digits specified' )
			await self.car_activity( f'ERROR: cannot send dtmf digits b/c dtmf_digits={dtmf!r}' )
		return CONTINUE
	
	async def action_preannounce( self, action: ACTION_PREANNOUNCE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_preannounce' )
		if self.state == HUNT: return CONTINUE
		
		sound = ( await self.expand( '${ace-preannounce_wav}' )).strip()
		if not sound:
			log.warning( 'no preannounce path' )
			await self.car_activity( f'ERROR: cannot play preannounce b/c ${{ace-preannounce_wav}}={sound!r}' )
			return CONTINUE
		log.info( 'sound=%r', sound )
		await self.car_activity( f'playing ${{ace-preannounce_wav}}={sound!r}' )
		await self.set_state( AceState.PREANNOUNCE )
		return await self._playback( sound, pagd )
	
	async def action_preanswer( self, action: ACTION_PREANSWER, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_preanswer' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.PREANSWER )
		log.info( 'pre-answering' )
		await self.car_activity( 'pre-answering call' )
		if not await util.pre_answer( self.esl, self.uuid, 'ace_eso.CallState.action_preanswer' ):
			return STOP
		
		return CONTINUE
	
	async def action_ring( self, action: ACTION_RING, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_ring' )
		await self.set_state( AceState.RING )
		await self.car_activity( 'playing ringtone to caller' )
		return await self._broadcast( 'RING', action.get( 'tone' ), default = '$${us-ring}', log = log )
	
	async def action_route( self, action: ACTION_ROUTE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.route' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.ROUTE )
		route: int = await self.toint( action, 'route' )
		if not valid_route( route ):
			log.warning( 'invalid route=%r', route )
			await self.car_activity( f'ERROR: Cannot send call to another route b/c invalid route={route!r}' )
			return CONTINUE
		log.info( 'loading route=%r', route )
		try:
			routedata = await self.load_route( route ) # TODO FIXME: this can fail...
		except repo.ResourceNotFound as e:
			log.warning( 'unable to execute route %r: %r', route, e )
			await self.car_activity( f'ERROR: unable to execute route {route!r}: {e!r}' )
			return CONTINUE
		#old_route = self.route
		log.info( 'executing route=%r', route )
		await self.car_activity( f'executing route {route!r}' )
		result = await self.exec_top_actions(
			expect( list, routedata.get( 'nodes' ), default = [] )
		)
		await self.car_activity( f'route {route!r} returned with result={result!r}' )
		#self.route = old_route
		return result
	
	async def action_rxfax( self, action: ACTION_RXFAX, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_rxfax' )
		if self.state == HUNT: return CONTINUE
		
		mailto = expect( str, action.get( 'mailto' ), default = '' ).strip()
		if not mailto:
			log.warning( 'cannot rxfax b/c action.mailto=%r', mailto )
			await self.car_activity( f'ERROR: cannot rxfax b/c action.mailto={mailto!r}' )
			return STOP
		
		await self.set_state( AceState.RXFAX )
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
		
		await self.car_activity( 'initiating rxfax' )
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
		await self.car_activity( f'set channel variable {variable!r}={value!r}' )
		return CONTINUE
	
	async def action_silence( self, action: ACTION_SILENCE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_silence' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.SILENCE )
		seconds = await self.tonumber( action, 'seconds', default = 0 )
		divisor = await self.toint( action, 'divisor', default = 0 )
		duration = -1 if seconds < 0 else int( seconds * 1000 )
		stream = f'silence_stream://{duration!r},{divisor!r}'
		log.info( '%s', stream )
		await self.car_activity( f'playing silence {stream!r}' )
		return await self._playback( stream, pagd )
	
	async def action_throttle( self, action: ACTION_THROTTLE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_throttle' )
		if self.state == HUNT:
			if STOP == await self.exec_branch( action, 'allowedBranch', pagd, log = log ):
				return STOP
			if self.state != HUNT: return CONTINUE
			return await self.exec_branch( action, 'throttledBranch', pagd, log = log )
		
		await self.set_state( AceState.THROTTLE )
		try:
			throttle_id = await self.esl.uuid_getvar( self.uuid, 'throttle_id' ) or self.did
		except Exception as e:
			throttle_id = self.did
			log.error( 'Error trying to get throttle_id (defaulting to did): %r', e )
			await self.car_activity( f'throttle_id defaulting to {throttle_id!r} because channel variable throttle_id -> {e!r}' )
		
		try:
			throttle_limit = int( await self.esl.uuid_getvar( self.uuid, 'throttle_limit' ) or '?' )
		except Exception as e:
			throttle_limit = 10
			log.error( 'Error trying to get throttle_limit (defaulting to %r): %r',
				throttle_limit, e,
			)
			await self.car_activity( f'throttle_limit defaulting to {throttle_limit} because channel variable throttle_limit -> {e!r}' )
		
		try:
			await self.esl.uuid_setvar( self.uuid, 'limit_ignore_transfer', 'true' )
		except Exception as e:
			log.error( 'Error trying to set limit_ignore_transfer: %r', e )
			await self.car_activity( f'ERROR: trying to set limit_ignore_transfer -> {e!r}' )
		
		backend = 'hash'
		realm = 'inbound'
		
		try:
			async for event in self.esl.limit( self.uuid, backend, realm, throttle_id ):
				_on_event( event )
		except Exception as e:
			log.error( 'Error trying to execute limit app: %r', e )
			await self.car_activity( f'ERROR: trying to execute limit app -> {e!r}' )
		
		try:
			usage = int( await self.esl.uuid_getvar( self.uuid, 'limit_usage' ) or '?' )
		except Exception as e:
			usage = 0
			log.error( 'Error trying to get limit_usage (defaulting to %r: %r',
				usage, e,
			)
			await self.car_activity( f'ERROR trying to query limit_usage -> {e!r}' )
		
		log.info( 'uuid=%r, usage=%r', self.uuid, usage )
		which = 'allowedBranch'
		if usage > throttle_limit:
			which = 'throttledBranch'
			r = await self.esl.uuid_limit_release( self.uuid, backend, realm, throttle_id )
			log.debug( 'uuid_limit_release( %r, %r, %r, %r ) -> %r',
				self.uuid, backend, realm, throttle_id, r,
			)
			await self.car_activity( f'call throttled, uuid_limit_release -> {r!r}' )
		else:
			await self.car_activity( f'call NOT throttled b/c usage {usage!r} < throttle_limit {throttle_limit!r}' )
		
		return await self.exec_branch( action, which, pagd, log = log )
	
	async def action_tone( self, action: ACTION_TONE, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_tone' )
		if self.state == HUNT: return CONTINUE
		
		tone = str( action.get( 'tone' ) or '' ).strip()
		if not tone:
			log.error( 'Cannot play tone b/c tone=%r', tone )
			await self.car_activity( f'ERROR: cannot play tone b/c tone={tone!r}' )
			return CONTINUE
		
		await self.set_state( AceState.TONE )
		loops = await self.toint( action, 'loops', default = 1 )
		stream = f'tone_stream://{tone};loops={loops}'
		log.info( 'stream=%r', stream )
		await self.car_activity( f'playing tone {stream!r}' )
		return await self._playback( stream, pagd )
	
	async def action_transfer( self, action: ACTION_TRANSFER, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_transfer' )
		if self.state == HUNT: return CONTINUE
		
		await self.set_state( AceState.TRANSFER )
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
		await self.car_activity( f'uuid_transfer( uuid={self.uuid!r}, leg={leg!r}, dest={dest!r}, dialplan={dialplan!r}, context={context!r}) -> {result!r}' )
		self.hangup_on_exit = False
		return STOP
	
	async def _guest_greeting( self, action: ACTION_VOICEMAIL, box: int, boxsettings: BOXSETTINGS, vm: Voicemail ) -> Opt[str]:
		log = logger.getChild( 'CallState._guest_greeting' )
		
		try:
			active_greeting = int( boxsettings.get( 'greeting' ) or '' )
		except ValueError as e:
			active_greeting = 1
			await self.car_activity( f'ERROR trying to get vm box {box!r} active greeting: {e!r}' )
		
		async def _make_greeting_branch( greeting: int ) -> BRANCH:
			path = vm.box_greeting_path( box, greeting )
			if path is None or not Path( path ).is_file():
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
			await self.car_activity( f'_guest_greeting: playing active_greeting={active_greeting!r} b/c greeting_override={greeting_override!r}' )
			greeting_branch = await _make_greeting_branch( active_greeting )
		elif greeting_override == 'X': # play no greeting at all
			await self.car_activity( f'_guest_greeting: not playing any greeting b/c greeting_override={greeting_override!r}' )
			return ''
		elif greeting_override.isnumeric():
			greeting = int( greeting_override )
			await self.car_activity( f'_guest_greeting: playing greeting={greeting!r} b/c greeting_override={greeting_override!r}' )
			greeting_branch = await _make_greeting_branch( greeting )
		else:
			if greeting_override:
				log.warning( 'invalid greeting_override=%r', greeting_override )
				await self.car_activity( f'_guest_greeting: ERROR: invalid greeting_override={greeting_override!r}' )
			which = 'greetingBranch'
			await self.car_activity( '_guest_greeting: choosing greeting branch' )
			greeting_branch = cast( BRANCH, boxsettings.get( which ) or {} )
		
		if not greeting_branch.get( 'nodes' ):
			# this can happen if:
			# 1) greeting_override == 'A'
			# 2) default behavior was requested but no greeting behavior was defined in the voicemail box
			which = ''
			await self.car_activity( f'_guest_greeting: playing active_greeting={active_greeting!r} b/c greeting branch is empty' )
			greeting_branch = await _make_greeting_branch( active_greeting )
		
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
			return None
		#if not pagd.digits:
		#	silence_seconds = 0.25 # TODO FIXME: customizable
		#	await self.car_activity( f'_guest_greeting: playing {silence_seconds!r}s of silence after greeting b/c digits={pagd.digits!r}' )
		#	if STOP == await self.action_silence( ACTION_SILENCE(
		#		type = 'silence',
		#		name = '',
		#		seconds = silence_seconds,
		#		divisor = 0,
		#	), pagd ):
		#		return None
		digits = pagd.digits or ''
		await self.car_activity( f'_guest_greeting: vm guest greeting returning with digits={digits!r}' )
		return digits
	
	async def action_voicemail( self, action: ACTION_VOICEMAIL, pagd: Opt[PAGD] ) -> RESULT:
		log = logger.getChild( 'CallState.action_voicemail' )
		if self.state == HUNT: return CONTINUE
		
		box: Opt[int] = await self.toint( action, 'box', expand = True )
		if box is None:
			box_ = action.get( 'box' )
			log.warning( 'invalid box=%r', box_ )
			await self.car_activity( f'action_voicemail: ERROR trying to send call to voicemail: invalid box={box_!r}' )
			return CONTINUE
		
		settings = await ace_settings.aload()
		vm = Voicemail( self.esl, self.uuid, settings )
		
		_ = await util.answer( self.esl, self.uuid, 'CallState.action_voicemail' )
		
		if box == 0:
			await self.set_state( AceState.VMCHECKIN )
			await self.car_activity( f'action_voicemail: Executing voicemail checkin logic b/c box={box!r}' )
			if not await vm.checkin():
				return STOP
			return CONTINUE
		
		await self.set_state( AceState.VMGUESTGRT )
		try:
			boxsettings: BOXSETTINGS = await vm.load_box_settings( box )
		except LoadBoxError as e:
			await self.car_activity(
				f'action_voicemail: ERROR - box {box!r} could not be loaded: {e!r}'
			)
			stream = await vm._the_person_you_are_trying_to_reach_is_not_available_and_does_not_have_voicemail()
			await vm.play_menu([ stream ])
			# TODO FIXME: do we want to forceably hangup the call here?
			# TODO FIXME: or add a "no box" branch to the voicemail node in the editor?
			await self.set_state( AceState.HANGUP )
			await vm.goodbye()
			return STOP
		await self.car_activity(
			f'action_voicemail: Loaded settings for vm box {box!r} named {boxsettings.get("name")!r}'
		)
		
		old_box: Opt[int] = self.box
		try:
			self.box = box
			branches: BRANCHES = boxsettings.get( 'branches' ) or {}
			digit: Opt[str] = None
			while True: # this loop only exists to serve replay of greeting in the case of "invalid entry"
				if not digit:
					digit = await self._guest_greeting( action, box, boxsettings, vm )
				if digit is None:
					return STOP
				if digit == '*':
					await self.set_state( AceState.VMLOGIN )
					await self.car_activity( 'action_voicemail: caller pressed * during vm greeting, prompting for login' )
					if await vm.login( box, boxsettings ):
						await self.car_activity( f'action_voicemail: caller logged into box {box!r} successfully, transferring to admin_main_menu' )
						await self.set_state( AceState.VMADMIN )
						await vm.admin_main_menu( box, boxsettings )
						await self.car_activity( f'action_voicemail: caller back from vm box {box!r} admin mode' )
					else:
						await self.car_activity( f'action_voicemail: caller failed to log into box {box!r}' )
					await self.car_activity( 'action_voicemail: hangup and terminating script' )
					await self.set_state( AceState.HANGUP )
					await util.hangup( self.esl, self.uuid, 'NORMAL_CLEARING', 'CallState.action_voicemail' )
					return STOP
				if digit and digit in '1234567890':
					branch = branches.get( digit )
					if branch:
						await self.car_activity( f'action_voicemail: caller pressed {digit!r} during vm greeting, executing branch logic' )
						r = await self._exec_branch( digit, branch, None, log = log )
						return r
					else:
						await self.car_activity( f'action_voicemail: caller pressed {digit!r} during vm greeting, but there is no logic for that digit' )
						digit = await vm.play_menu([ 'ivr/ivr-that_was_an_invalid_entry.wav' ])
						continue
				# no diversions selected, record message:
				if digit and digit != '#':
					log.warning( 'invalid digit=%r', digit )
				await self.car_activity( f'action_voicemail: vm box {box!r} greeting finished, preparing to record new message now' )
				await self.set_state( AceState.VMGUESTMSG )
				if await vm.guest( self.did, self.ani, box, boxsettings, self.notify ):
					await self.set_state( AceState.HANGUP )
					await util.hangup( self.esl, self.uuid, 'NORMAL_CLEARING', 'CallState.action_voicemail' )
				return STOP
		finally:
			self.box = old_box
		
		return CONTINUE
	
	async def notify( self, box: int, boxsettings: BOXSETTINGS, msg: MSG ) -> None:
		log = logger.getChild( 'CallState.notify' )
		try:
			settings = await ace_settings.aload()
			await self.car_activity( f'notify starting for box {box!r} named {boxsettings.get("name")!r}' )
			state = NotifyState( self.esl, self.uuid, box, msg, boxsettings, settings.vm_checkin )
			delivery = boxsettings.get( 'delivery' ) or {}
			nodes = delivery.get( 'nodes' ) or []
			await state.exec_top_actions( nodes )
			await self.car_activity( 'notify process complete' )
		except Exception as e:
			log.exception( 'Unexpected error during voicemail notify:' )
			await self.car_activity( f'notification terminated with an error: {e!r}' )


#endregion CallState
#region NotifyState


class NotifyState( State ):
	def __init__( self, esl: ESL, uuid: str, box: int, msg: MSG, boxsettings: BOXSETTINGS, checkin: str ) -> None:
		super().__init__( esl, uuid )
		self.box = box
		self.msg = msg
		self.boxsettings = boxsettings
		self.checkin = checkin
	
	async def can_continue( self ) -> bool:
		return self.msg.status == 'new' and Path( self.msg.path ).is_file()
	
	async def action_email( self, action: ACTION_EMAIL, pagd: Opt[PAGD] ) -> RESULT:
		# TODO FIXME: might we have a use for this in CallState too?
		log = logger.getChild( 'NotifyState.action_email' )
		if self.state == HUNT: return CONTINUE
		
		settings = await ace_settings.aload()
		
		ec = Email_composer()
		ec.to = expect( str, action.get( 'mailto' ), default = '' )
		cc = ''
		bcc: List[str] = []
		ec.from_ = settings.smtp_email_from
		ec.subject = expect( str, action.get( 'subject' ), default = '' )
		ec.text = expect( str, action.get( 'body' ), default = '' )
		fmt: str = expect( str, action.get( 'format' ), default = '' )
		file: Opt[Path] = None
		content_type = 'audio/wav'
		if self.msg is not None:
			file = Path( self.msg.path )
		
		if not ec.to:
			log.warning( 'cannot send email - no recipient' )
			await self.car_activity( f'ERROR: cannot send email - no recipient' )
			return CONTINUE
		
		
		if self.boxsettings:
			if not ec.subject.strip():
				ec.subject = self.boxsettings.get( 'default_email_subject' ) or ''
				if not ec.subject.strip():
					ec.subject = settings.smtp_email_subject or ''
					if not ec.subject.strip():
						ec.subject = 'New ${box} VM message from ${ani}'
			if not ec.text.strip():
				ec.text = self.boxsettings.get( 'default_email_body' ) or ''
				if not ec.text.strip():
					ec.text = settings.smtp_email_body or ''
					if not ec.text.strip():
						ec.text = 'You have a new VM message from ${ani}.\n\nPlease listen to the attached file to hear your message.'
			if not fmt:
				fmt = self.boxsettings.get( 'format' ) or ''
		if not fmt:
			fmt = 'mp3'
		
		ec.subject = await self.expand( ec.subject )
		ec.text = await self.expand( ec.text )
		
		if file and fmt == 'mp3':
			mp3_file = file.with_suffix( '.mp3' )
			pydub.AudioSegment.from_wav( str( file )).export( str( mp3_file ), format = 'mp3' )
			file = mp3_file
			content_type = 'audio/mpeg'
		
		if file:
			with file.open( 'rb' ) as f:
				ec.attach( f, file.name, content_type )
		
		if settings.smtp_secure == 'yes':
			smtp: Union[smtplib2.SMTP,smtplib2.SMTP_SSL] = smtplib2.SMTP_SSL(
				settings.smtp_host,
				settings.smtp_port or 465,
				timeout = settings.smtp_timeout_seconds,
			)
		else:
			smtp = smtplib2.SMTP(
				settings.smtp_host,
				settings.smtp_port or 587,
				timeout = settings.smtp_timeout_seconds,
			)
		
		if settings.smtp_username or settings.smtp_password:
			assert settings.smtp_username and settings.smtp_password
			smtp.login( settings.smtp_username, settings.smtp_password )
		
		await self.car_activity( f'sending email to={ec.to!r}, cc={ec.cc!r}, bcc={bcc!r}' )
		try:
			resp: str
			senderrs: Dict[str,Tuple[int,str]]
			resp, senderrs = smtp.sendmail2( ec.from_, list( chain( ec.to, ec.cc, bcc )), ec.as_bytes() )
		except Exception as e:
			log.exception( 'email failure:' )
			await self.car_activity( f'ERROR: email failure: {e!r}' )
		else:
			await self.car_activity( f'email success: {resp!r}' )
		
		return CONTINUE
	
	async def _voice_deliver( self, action: ACTION_VOICE_DELIVER, number: str ) -> Tuple[bool,Opt[str]]:
		log = logger.getChild( 'NotifyState._voice_deliver' )
		
		timeout = datetime.timedelta( seconds = await self.toint( action, 'timeout', default = 0 ))
		if timeout.total_seconds() <= 0:
			timeout = datetime.timedelta( seconds = 60 )
		
		settings = await ace_settings.aload()
		
		dest = f'loopback/{number}/default'
		cid_name = str( action.get( 'cid_name' ) or '' ).strip() or f'VMBox {self.box}'
		cid_num = str( action.get( 'cid_num' ) or '' ).strip() or settings.voice_deliver_ani
		context = str( action.get( 'context' ) or '' ).strip() or 'default'
		trusted = expect( bool, action.get( 'trusted' ), default = False )
		
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
		
		await self.car_activity( f'dialing {dest!r}' )
		try:
			# TODO FIXME: may need to create a new ESL object for notifications process...
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
		except Exception as e:
			log.exception( 'Error trying to originate:' )
			await self.car_activity( f'ERROR: could not dial {dest!r}: {e!r}' )
			return False, repr( e )
		log.debug( 'originate -> %r', r )
		
		await asyncio.sleep( 1 )
		
		answered, reason = await self._uuid_wait_for_answer( origination_uuid, timeout )
		
		if not answered:
			await self.car_activity( f'ERROR: dialout never answered: {reason!r}' )
			return False, reason
		
		settings = await ace_settings.aload()
		vm = Voicemail( self.esl, origination_uuid, settings )
		await self.car_activity( f'executing vm box {self.box!r} voice delivery mode' )
		await vm.voice_deliver( self.box, self.msg, trusted, self.boxsettings )
		
		await self.car_activity( f'vm box {self.box!r} voice delivery mode done' )
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
		
		if not number:
			log.error( 'cannot voice deliver - no number' )
			await self.car_activity( f'action_voice_deliver: ERROR - cannot proceed b/c number={number!r}' )
			return CONTINUE
		
		if not Path( self.msg.path ).is_file():
			log.warning( 'cannot voice deliver - wave file no longer exists' )
			await self.car_activity( f'action_voice_deliver: ERROR - cannot proceed b/c no wav file: {str(self.msg.path)!r}' )
			return CONTINUE
		
		await self.car_activity( f'action_voice_deliver: executing voice delivery to number={number!r}' )
		ok, reason = await self._voice_deliver( action, number )
		log.info( 'ok=%r, reason=%r', ok, reason )
		if ok:
			await self.car_activity( 'action_voice_deliver: voice delivery complete' )
		else:
			await self.car_activity( f'action_voice_deliver: ERROR - voice delivery failed with {reason!r}' )
		
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
	state: Opt[CallState] = None
	try:
		headers = await esl.connect_from( reader, writer )
		
		await asyncio.sleep( 0.5 ) # wait for media to establish
		
		#for k, v in headers.items():
		#	print( f'{k!r}: {v!r}' )
		uuid = headers['Unique-ID']
		did = headers['Caller-Destination-Number']
		ani = headers['Caller-ANI']
		cpn = '' # TODO FIXME what field has this?
		log.debug( 'uuid=%r raw did=%r ani=%r', uuid, did, ani )
		
		did = normalize_phone_number( did )
		ani = normalize_phone_number( ani )
		log.debug( 'uuid=%r normalized did=%r ani=%r', uuid, did, ani )
		
		await ace_car.create( State.config.repo_car, uuid, did, ani, cpn )
		
		log.debug( 'calling myevents' )
		await esl.myevents()
		await esl.filter( 'Unique-ID', uuid )
		await esl.event_plain_all()
		
		#await esl.linger() # TODO FIXME: I'm probably going to want this...
		
		state = CallState( esl, uuid, did, ani )
		
		ani_route = await state.try_ani()
		route, didinfo = await state.try_did( ani_route )
		if route:
			await state.car_activity( f'_handler: setting channel variable "route"={route!r}' )
			await esl.uuid_setvar( uuid, 'route', str( route ))
		if didinfo is not None:
			await state.set_preannounce( didinfo )
		
		if not route:
			log.error( 'no route to execute: route=%r', route )
			cause1: Final = 'UNALLOCATED_NUMBER'
			await state.car_activity( f'_handler: hangup call with {cause1!r} b/c no route was found' )
			await util.hangup( esl, uuid, cause1, 'ace_engine._handler#1' )
			return
		
		route_ = str( route or '' )
		if route_.startswith( 'V' ):
			box_ = route_[1:]
			try:
				box = int( box_ )
			except ValueError:
				log.error( 'Could not interpret %r as an integer vm box #', box_ )
				cause2: Final = 'UNALLOCATED_NUMBER'
				await state.car_activity( f'_handler: hangup call with {cause2!r} b/c {box_!r} not an integer vm box #' )
				await util.hangup( esl, uuid, cause2, 'ace_engine._handler#2' )
				return
			await state.car_activity( f'_handler: routing call directly to vm box {box!r}' )
			routedata = {
				#'type': 'root_route',
				'nodes': [{
					'type': 'voicemail',
					'box': box,
				}]
			}
		else:
			try:
				routedata = await state.config.repo_routes.get_by_id( route )
			except repo.ResourceNotFound:
				log.error( 'route does not exist: route=%r', route )
				await state.car_activity( '_handler: hangup call because route {route!r} does not exist' )
				await util.hangup( esl, uuid, 'UNALLOCATED_NUMBER', 'ace_engine._handler#3' )
				return
		
		nodes = cast( ACTIONS, routedata.get( 'nodes' ) or [] )
		r = await state.exec_top_actions( nodes )
		log.info( 'route %r exited with %r', route, r )
		await state.car_activity( f'_handler: route {route!r} exited with {r!r}' )
		
		if state.hangup_on_exit:
			#try:
			#	await esl.uuid_setvar( uuid, ACE_STATE, STATE_KILL )
			#except TimeoutError:
			#	log.warning( 'timeout waiting for uuid_setvar' )
			cause3: Final = 'NORMAL_CLEARING'
			log.debug( 'hangup call with %r', cause3 )
			await state.car_activity( f'hangup call with {cause3!r}' )
			try:
				await util.hangup( esl, uuid, cause3, 'ace_engine._handler' )
			except TimeoutError:
				log.warning( 'timeout waiting for hangup request' )
		else:
			await state.car_activity( f'NOT hangup call because hangup_on_exit={state.hangup_on_exit!r}' )
			#cause = 'NORMAL_CLEARING'
			#log.debug( 'hangup call with %r because route exited with %r and we have no way to signal inband lua yet', cause, r )
			#await esl.uuid_setvar( uuid, ACE_STATE, STATE_CONTINUE )
	
	except AcdConnected as e1:
		log.info( f'call processing finished because {e1!r}' )
		if state is not None:
			await state.car_activity( f'call processing finished because {e1!r}' )
	except ChannelHangup as e2:
		log.warning( repr( e2 ))
		if state is not None:
			await state.car_activity( f'call processing finished because {e2!r}' )
	except Exception as e3:
		log.exception( 'Unexpected error:' )
		if state is not None:
			await state.car_activity( f'call processing aborted with {e3!r}' )
	finally:
		if state is not None:
			await ace_car.finish( State.config.repo_car, uuid )
		log.debug( 'closing down client' )
		await esl.close()

async def _server(
	config: Config,
) -> None:
	util.on_event = _on_event
	
	State.config = config
	
	await Voicemail.init(
		box_path = config.vm_box_path,
		msgs_path = config.vm_msgs_path,
		owner_user = config.owner_user,
		owner_group = config.owner_group,
		on_event = _on_event,
	)
	server = await asyncio.start_server( _handler, '127.0.0.1', 8022 )
	async with server:
		await server.serve_forever()

def _main(
	config: Config
) -> None:
	aiohttp_logging.monkey_patch()
	ace_logging.init( config.engine_logfile, config.loglevels )
	ace_settings.init( config.settings_path, config.settings_mplock )
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
