# stdlib imports:
from abc import ABCMeta, abstractmethod
import asyncio
from dataclasses import dataclass
import datetime
from enum import Enum
import logging
from multiprocessing import Process
from pathlib import Path
import re
from typing import (
	Any, Awaitable, Callable, Dict, List, Optional as Opt,
	Tuple, Type, TypeVar, Union,
)
from typing_extensions import Final, Literal # Python 3.7

# local imports:
from esl import ESL
import repo

logger = logging.getLogger( __name__ )

PARAMS = Dict[str,Any]

GOTO: Final = 'goto'
EXEC: Final = 'exec'
HUNT: Final = 'hunt'
EXECSTATE = Literal['goto','exec','hunt']

class State( metaclass = ABCMeta ):
	def __init__( self, esl: ESL, state: EXECSTATE ) -> None:
		self.esl = esl
		self.state = state
	
	@abstractmethod
	async def can_continue( self ) -> bool:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.can_continue()' )

class CallState( State ):
	uuid: str
	
	def __init__( self, esl: ESL, state: EXECSTATE, uuid: str ) -> None:
		super().__init__( esl, state )
		self.uuid = uuid
	
	@abstractmethod
	async def can_continue( self ) -> bool:
		log = logger.getChild( 'CallState.can_continue' )
		if not await self.esl.uuid_exists( self.uuid ):
			log.debug( 'uuid_exists -> false' )
			return False
		if await self.esl.uuid_getvar( self.uuid, 'bridge_uuid' ):
			log.debug( 'bridge_uuid ~= nil' )
			return False
		return True

class NotifyState( State ):
	msg: Dict[str,Any]

CONTINUE: Final = 'continue'
STOP: Final = 'stop'
RESULT = Literal['continue','stop']

RESULT1 = RESULT
RESULT3 = Tuple[RESULT,Opt[str],Opt[bool]]

@dataclass
class PAGD:
	min_digits: int
	max_digits: int
	timeout: datetime.timedelta
	terminators: str
	digit_regex: str
	variable_name: str
	digit_timeout: datetime.timedelta

def to_callstate( state: State ) -> CallState:
	assert isinstance( state, CallState ), f'invalid state={state!r}'
	return state

T = TypeVar( 'T' )
def expect( type: Type[T], data: Dict[str,Any], name: str, *, required: bool = False, default: Opt[T] = None ) -> T:
	value = data.get( name )
	if value is None:
		return default if default is not None else type()
	if isinstance( value, type ):
		return value
	raise ValueError( f'expecting {name!r} of type {str(type)!r} but got {value!r}' )

def numeric( data: Dict[str,Any], name: str, *, default: Opt[Union[int,float]] = None ) -> Union[int,float]:
	value = data.get( name )
	if value is None:
		if default is not None:
			return default
	else:
		try:
			return int( value )
		except ValueError:
			pass
		try:
			return float( value )
		except ValueError:
			pass
	raise ValueError( f'Expecting {name!r} of type convertable to int/float but got {value!r}' )

async def expand( state: State, s: str ) -> str:
	log = logger.getChild( 'expand' )
	log.debug( 'input=%r', s )
	if s:
		ar: list[str] = re.split( r'\$\${([^}]+)}', s )
		for i in range( 1, len( ar ), 2 ):
			r = await state.esl.global_getvar( ar[i] )
			ar[i] = r.value
		s = ''.join( ar )
		ar = re.split( r'\${([^}]+)}', s )
		if isinstance( state, CallState ):
			# calls
			for i in range( 1, len( ar ), 2 ):
				r = await state.esl.uuid_getvar( state.uuid, ar[i] )
				ar[i] = r.value
		elif isinstance( state, NotifyState ):
			# voicemail notify context
			for i in range( 1, len( ar ), 2 ):
				ar[i] = state.msg.get( ar[i] ) or ''
		else:
			assert False, f'invalid state={state!r}'
		s = ''.join( ar )
	log.debug( 'output=%r', s )
	return s

async def _pagd( state: CallState, params: PARAMS, success: Callable[[str],Opt[RESULT]] ) -> RESULT1:
	log = logger.getChild( '_pagd' )
	timeout = datetime.timedelta( seconds = numeric( params, 'timeout', default = 3 ))
	pagd = PAGD(
		min_digits = expect( int, params, 'min_digits', default = 1 ),
		max_digits = expect( int, params, 'max_digits', default = 1 ),
		timeout = datetime.timedelta( milliseconds = 50 ), # don't want to apply8 pagd.timeout to every node under greeting branch
		terminators = expect( str, params, 'terminators', default = '' ),
		digit_regex = expect( str, params, 'digit_regex', default = '' ),
		variable_name = expect( str, params, 'variable_name', default = '' ),
		digit_timeout = datetime.timedelta( seconds = numeric( params, 'digit_timeout', default = timeout.total_seconds() ))
	)
	max_attempts = expect( int, params, 'max_attempts', default = 3 )
	attempt: int = 1
	digits: Opt[str] = None
	r: RESULT
	valid: Opt[bool] = None
	while attempt <= max_attempts:
		branch: dict[str,Any] = expect( dict, params, 'greetingBranch', default = {} )
		branch_name = branch.get( 'name' )
		if digits:
			log.info( 'executing greeting branch %r', branch_name )
			nodes = expect( list, branch, 'nodes', default = [] )
			r, digits, valid = await exec_actions( state, nodes, pagd )
			if r == STOP: return STOP
			if digits:
				r, digits, valid = await action_silence( state, { 'seconds': 3 }, pagd )
				log.info( 'back from post-greeting auto-silence with r=%r, digits=%r, valid=%r',
					r, digits, valid
				)
				if r == STOP: return STOP
		else:
			log.info( 'skipped greeting branch %r because digits=%r, valid=%r',
				branch_name, digits, valid,
			)
		
		if digits and valid:
			result = success( digits )
			if result is not None:
				return result
		if attempt < max_attempts:
			if digits:
				branch = expect( dict, params, 'invalidBranch', default = {} )
				log.info( 'executing invalid branch %r', branch.get( 'name' ))
				nodes = expect( list, branch, 'nodes', default = [] )
				r, digits, valid = await exec_actions( state, nodes, pagd )
				if r == STOP: return STOP
			else:
				branch = expect( dict, params, 'timeoutBranch', default = {} )
				log.info( 'executing timeout branch %r', branch.get( 'name' ))
				nodes = expect( list, branch, 'nodes', default = [] )
				r, digits, valid = await exec_actions( state, nodes, pagd )
				if r == STOP: return STOP
		else:
			branch = expect( dict, params, 'failureBranch', default = {} )
			log.info( 'executing failure branch %r', branch.get( 'name' ))
			nodes = expect( list, branch, 'nodes', default = [] )
			r, _, _ = await exec_actions( state, nodes )
			return r
		attempt += 1
	return CONTINUE

async def _playback( state: CallState, sound: str, pagd: Opt[PAGD] ) -> RESULT3:
	log = logger.getChild( '_playback' )
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
		async for event in state.esl.play_and_get_digits(
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
		):
			event_name = event.event_name
			if event_name == 'DTMF':
				dtmf_digit = expect( str, event.headers, 'DTMF-Digit' )
				digits_.append( dtmf_digit )
		digits = ''.join( digits_ )
		log.info( 'got digits=%r', digits )
		
		valid: bool = True
		if pagd.digit_regex:
			log.debug( 'call regex( %r, %r )', digits, pagd.digit_regex )
			valid = await state.esl.regex( digits, pagd.digit_regex )
		
		log.info( 'got digits=%r valid=%r', digits, valid )
		return CONTINUE, digits, valid
	else:
		log.debug( 'executing break all' )
		await state.esl.uuid_break( state.uuid, 'all' )
		
		log.info( 'executing playback %r', sound )
		async for event in state.esl.playback( sound ):
			log.debug( f'event name={event.event_name!r}' )
		
		return CONTINUE, None, None

async def action_moh( state: State, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT3:
	log = logger.getChild( 'action_moh' )
	if state.state == HUNT: return CONTINUE, None, None
	
	stream: str = await expand( state, expect( str, params, 'stream', default = '$${hold_music}' ))
	
	state_ = to_callstate( state )
	
	log.debug( 'breaking' )
	await state.esl.uuid_break( state_.uuid, 'all' )
	
	log.info( 'playing %r', stream )
	await state.esl.uuid_broadcast( state_.uuid, stream, 'aleg' )
	
	return CONTINUE, None, None

async def action_playback( state: State, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT3:
	log = logger.getChild( 'action_playback' )
	if state.state == HUNT: return CONTINUE, None, None
	
	sound = expect( str, params, 'sound', default = 'ivr/ivr-invalid_sound_prompt.wav' )
	log.info( 'sound=%r', sound )
	return await _playback( to_callstate( state ), sound, pagd )

async def action_silence( state: State, params: PARAMS, pagd: Opt[PAGD] ) -> RESULT3:
	log = logger.getChild( 'action_silence' )
	if state.state == HUNT: return CONTINUE, None, None
	
	seconds = numeric( params, 'seconds', default = 0 )
	divisor = numeric( params, 'divisor', default = 0 )
	duration = -1 if seconds < 0 else seconds * 1000
	stream = f'silence_stream://{duration}!r,{divisor!r}'
	log.info( '%s', stream )
	return await _playback( to_callstate( state ), stream, pagd )

async def exec_actions( state: State, actions: List[PARAMS], pagd: Opt[PAGD] = None ) -> RESULT3:
	for action in actions or []:
		r, digits, valid = await exec_action( state, action, pagd )
		if r != CONTINUE: return r, None, None
		if digits: return CONTINUE, digits, valid
	return CONTINUE, None, None

async def exec_action( state: State, action: PARAMS, pagd: Opt[PAGD] ) -> RESULT3:
	log = logger.getChild( 'exec_action' )
	action_type = expect( str, action, 'type', default = '' )
	if not action_type:
		log.error( 'action.type is missing' ) # TODO FIXME: diagnostic info?
		return CONTINUE, None, None
	fname = f'action_{action_type}'
	f: Opt[Callable[[State,PARAMS,Opt[PAGD]],Awaitable[RESULT3]]] = globals().get( fname )
	if not f or not callable( f ):
		log.error( 'invalid action type: %r', action_type )
		return CONTINUE, None, None
	log.debug( 'executing %r', fname )
	r, digits, valid = await f( state, action, pagd )
	log.debug( '%s -> %r, %r, %r', fname, r, digits, valid )
	if r not in ( CONTINUE, STOP ):
		log.error( '%s returned %r but should have returned %r or %r',
			fname, r, CONTINUE, STOP,
		)
		r = CONTINUE # assume CONTINUE for now..
	if r == CONTINUE:
		if not await state.can_continue():
			return STOP, None, None
	return r, digits, valid

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
		
		#await esl.linger()
		
		log.debug( 'calling myevents' )
		await esl.myevents()
		
		if True:
			await esl.answer()
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
				log.debug( 'draining event %r', event.event_name )
			
			log.debug( 'playback...' )
			async for event in esl.playback( 'ivr/ivr-welcome.wav' ):
				log.debug( 'playback event %r', event.event_name )
		
		if True:
			log.debug( 'draining events...' )
			async for event in esl.events():
				log.debug( 'draining event %r', event.event_name )
			
			log.debug( 'pagd...' )
			async for event in esl.play_and_get_digits(
				min_digits = 1,
				max_digits = 10,
				tries = 1,
				timeout = datetime.timedelta( seconds = 5 ),
				terminators = '#',
				file = 'ivr/ivr-please_enter_pin_followed_by_pound.wav',
			):
				event_name = event.event_name
				if event_name == 'DTMF':
					dtmf_digit = event.header( 'DTMF-Digit' )
					log.debug( 'pagd %s: dtmf_digit=%r', event_name, dtmf_digit )
				else:
					log.debug( 'pagd event_name=%r', event_name )
		
		if True:
			async for event in esl.events():
				log.debug( 'draining event %r', event.event_name )
			
			log.debug( 'record...' )
			async for event in esl.record(
				path = Path( '/tmp/test.wav' ),
				time_limit = datetime.timedelta( seconds = 30 ),
			):
				log.debug( f'record event_name=%r', event.event_name )
		
		# broadcast working...
		# ring-tone working
		# playback working
		# dtmf-collection working...
		# TODO: recordFile...
		
		log.debug( 'issuing hangup' )
		await esl.hangup()
		
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

async def _server() -> None:
	server = await asyncio.start_server( _handler, '127.0.0.1', 8022 )
	async with server:
		await server.serve_forever()

def _main(
	did_path: Path,
	ani_path: Path,
	repo_routes: repo.Repository,
	vm_meta_path: Path,
	vm_msgs_path: Path,
) -> None:
	logging.basicConfig(
		level = logging.DEBUG,
		#level = DEBUG9,
		format = '%(asctime)s:%(levelname)s:%(name)s:%(message)s',
	)
	#print( 'repo_routes=}' )
	asyncio.run( _server() )

def start(
	did_path: Path,
	ani_path: Path,
	repo_routes: repo.Repository,
	vm_meta_path: Path,
	vm_msgs_path: Path,
) -> None:
	eso_process = Process(
		target = _main,
		args = ( did_path, ani_path, repo_routes, vm_meta_path, vm_msgs_path ),
		daemon = True,
	)
	eso_process.start()
