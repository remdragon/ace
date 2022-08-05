from __future__ import annotations

# stdlib imports:
import asyncio
import certifi
import datetime
from enum import Enum
import itertools
import logging
from pathlib import Path
import ssl
from typing import (
	Dict, Iterator, List, Literal, Optional as Opt, overload, Tuple, TypeVar, Union,
)
from typing_extensions import AsyncIterator
from urllib.parse import unquote as urllib_unquote

logger = logging.getLogger( __name__ )

DEBUG9 = 9

idgen = itertools.count()
g_last_id: int = 0

UUID_BROADCAST_LEG = Literal['aleg','bleg','holdb','both']

class ESL:
	_reader: asyncio.StreamReader
	_writer: Opt[asyncio.StreamWriter] = None
	_event_queue: asyncio.Queue[ESL.Message]
	_requests: asyncio.Queue[ESL.Request]
	request_timeout = datetime.timedelta( seconds = 10 )
	
	class Disconnect( Exception ):
		pass
	
	class Error( Exception ):
		pass
	
	class SoftError( Error ):
		" any error that doesn't require closing the connection "
	
	class HardError( Error ):
		" Errors that probably require you to close and reconnect "
	
	class AuthFailure( HardError ):
		pass
	
	class Message:
		esl_headers: Opt[Dict[str,str]] = None
		content_type: str
		when_event: datetime.datetime
		when_rcvd: datetime.datetime
		
		def __init__( self, *,
			headers: Dict[str,str],
			raw: Opt[bytes] = None
		) -> None:
			self.raw: Opt[bytes] = None
			self.headers = headers
			self.body: str = ''
		
		@overload
		def header( self, key: str, default: str ) -> str: ...
		
		@overload
		def header( self, key: str, default: Opt[str] = None ) -> Opt[str]: ...
		
		def header( self,
			key: str,
			default: Opt[str] = None,
		) -> Opt[str]:
			return self.headers.get( key, default )
		
		@property
		def event_name( self ) -> Opt[str]:
			return self.header( 'Event-Name' )
		
		def content_length( self ) -> Opt[int]:
			content_length = self.header( 'Content-Length' )
			if content_length is None:
				return None
			try:
				return int( content_length )
			except ValueError as e:
				raise ESL.HardError(
					f'Error parsing Content-Length {content_length!r}: {e!r}'
				).with_traceback( e.__traceback__ ) from None
		
		def on_yield( self ) -> None:
			pass
		
		@classmethod
		def parse( cls, buf: bytes ) -> Tuple[Opt[ESL.Message],bytes]:
			#log = logger.getChild( 'Message.parse' )
			hdr_len = buf.find( b'\n\n' )
			#log.debug( f'hdr_len={hdr_len!r}, buf={buf!r}' )
			if -1 == hdr_len:
				#log.debug( 'early exit - no double-lf' )
				return None, buf
			raw_hdrs = buf[:hdr_len]
			body_off = hdr_len + 2
			msg = ESL.Message(
				headers = ESL.Message._parse_headers( raw_hdrs.decode( 'utf-8', 'replace' )),
				raw = raw_hdrs, # will replace later if we discover a body
			)
			body_len = msg.content_length() or 0
			msg_len = body_off + body_len
			if len( buf ) < msg_len:
				#log.debug( 'early exit - incomplete packet' )
				return None, buf
			msg.raw = buf[:msg_len]
			msg.body = msg.raw[body_off:].decode()
			return msg, buf[msg_len:]
		
		@staticmethod
		def _parse_headers(
			hdrs: str,
		) -> Dict[str,str]:
			headers: Dict[str,str] = {}
			for line in hdrs.split( '\n' ):
				ar = line.split( ':', 1 )
				if len( ar ) == 2:
					key = urllib_unquote( ar[0].strip() )
					val = urllib_unquote( ar[1].strip() )
					headers[key] = val
			return headers
		
		def __repr__( self ) -> str:
			cls = type( self )
			ar = [ f'{cls.__module__}.{cls.__qualname__}(' ]
			ar.append( f'headers={self.headers!r}, raw={self.raw!r}, body={self.body!r})' )
			return ''.join( ar )
	
	class DisconnectEvent( Message ):
		def __init__( self ) -> None:
			pass
		def on_yield( self ) -> None:
			raise ESL.Disconnect()
	
	class ErrorEvent( Message ):
		def __init__( self, exc: Exception ) -> None:
			self.exc = exc
		
		def on_yield( self ) -> None:
			raise self.exc from None
	
	RequestType = TypeVar( 'RequestType', bound = 'Request' )
	class Request:
		raw: Opt[bytes] = None
		err: Opt[Exception] = None
		command_required = True
		
		def __init__( self,
			cli: ESL,
			command: Opt[str] = None,
			headers: Opt[Dict[str,str]] = None,
			body: Opt[str] = None,
			*,
			event_lock: bool = False,
		) -> None:
			self.reply: Opt[ESL.Message] = None
			if command:
				_body_ = body.encode() if body else b''
				if _body_:
					if headers is None:
						headers = {}
					headers['Content-Length'] = str( len( _body_ ))
				lines: List[str] = [ command ]
				if headers:
					lines.extend([
						f'{k}: {v}' for k, v in headers.items()
					])
				if event_lock:
					lines.append( 'event-lock: true' )
				_lines_ = '\n'.join( lines ).encode()
				self.raw = b''.join([
					_lines_,
					b'\n\n',
					_body_,
				])
				cli._assert_alive()
			else:
				assert not self.command_required, f'{type(self).__name__} created with invalid command={command!r}'
			self.trigger = asyncio.Event()
		
		async def wait( self: ESL.RequestType, timeout: Opt[Union[int,float]] = None ) -> ESL.RequestType:
			log = logger.getChild( 'Request.wait' )
			#log.debug( 'waiting for trigger' )
			if not await asyncio.wait_for( self.trigger.wait(), timeout = timeout or ESL.request_timeout.total_seconds() ):
				raise TimeoutError()
			#log.debug( 'got trigger' )
			if self.err is not None:
				raise self.err
			return self
		
		def on_reply( self, reply: ESL.Message ) -> None:
			log = logger.getChild( 'Request.on_reply' )
			reply_text = reply.header( 'Reply-Text' ) or ''
			#log.log( logging.DEBUG, 'reply_text=%r, reply.body=%r', reply_text, reply.body )
			if reply_text.startswith( '-ERR' ):
				#log.warning( f'reply_text={reply_text!r} reply.headers={reply.headers!r}' )
				raise ESL.SoftError( reply_text )
			elif reply.body.startswith( '-ERR' ):
				raise ESL.SoftError( reply.body )
		
		def __repr__( self ) -> str:
			cls = type( self )
			return f'{cls.__module__}.{cls.__qualname__}(reply={self.reply!r})'
	
	class HelloRequest( Request ):
		command_required = False
		
		def on_reply( self, reply: ESL.Message ) -> None:
			assert reply is not None
			content_type = reply.header( 'Content-Type' )
			assert content_type == 'auth/request', f'invalid content_type={content_type!r}'
	
	class AuthRequest( Request ):
		def on_reply( self, reply: ESL.Message ) -> None:
			reply_text = reply.header( 'Reply-Text' ) or ''
			if not reply_text.startswith( '+OK' ):
				raise ESL.AuthFailure( reply_text )
	
	class ValueRequest( Request ):
		_value: Opt[str] = None
		
		@property
		def value( self ) -> str:
			assert self._value is not None, 'call request.wait() first'
			return self._value
		
		def on_reply( self, reply: ESL.Message ) -> None:
			super().on_reply( reply )
			assert reply.body is not None
			self._value = reply.body
		
		def __repr__( self ) -> str:
			cls = type( self )
			return f'{cls.__module__}.{cls.__qualname__}(value={self.value!r}, reply={self.reply!r})'
	
	class BoolRequest( Request ):
		_value: Opt[bool] = None
		
		@property
		def value( self ) -> bool:
			assert self._value is not None, 'call request.wait() first'
			return self._value
		
		def on_reply( self, reply: ESL.Message ) -> None:
			super().on_reply( reply )
			if reply.body == 'true':
				self._value = True
			else:
				assert reply.body == 'false', f'unexpected response: {reply.body!r}'
				self._value = False
		
		def __repr__( self ) -> str:
			cls = type( self )
			return f'{cls.__module__}.{cls.__qualname__}(value={self.value!r}, reply={self.reply!r})'
	
	def __init__( self ) -> None:
		global g_last_id
		self.id = g_last_id = next( idgen )
		self.lock = asyncio.Lock()
		self._reader_alive = asyncio.Event()
	
	async def connect_to( self,
		host: Opt[str] = None,
		port: Opt[int] = None,
		pwd: Opt[str] = None,
		tls: bool = False,
		timeout_seconds: Union[int,float] = 3,
		tls_check_hostname: bool = True,
		tls_cafile: Opt[str] = None,
	) -> None:
		log = logger.getChild( 'ESL.connect' )
		
		host = host or '127.0.0.1'
		port = port or 8021
		pwd = pwd or 'ClueCon'
		
		self._event_queue = asyncio.Queue()
		self._requests = asyncio.Queue()
		
		ctx: Opt[ssl.SSLContext] = None
		if tls:
			ctx = ssl.SSLContext( ssl.PROTOCOL_TLS )
			ctx.verify_mode = ssl.CERT_REQUIRED
			ctx.check_hostname = tls_check_hostname
			ctx.load_verify_locations( cafile = tls_cafile or certifi.where() )
		
		try:
			hello = ESL.HelloRequest( self, None )
			await self._requests.put( hello )
			log.debug( 'connecting to host=%r port=%r', host, port )
			self._reader, self._writer = await asyncio.open_connection( host, port, ssl = ctx )
		except Exception:
			# connection wasn't entirely successful, so kill the socket
			await self._close()
			raise
		
		asyncio.create_task( self._reader_task() )
		assert await asyncio.wait_for( self._reader_alive.wait(), timeout = timeout_seconds ), 'reader never started'
		
		log.debug( 'waiting for hello' )
		await hello.wait( timeout = timeout_seconds )
		log.debug( 'sending auth' )
		auth = await self.auth( pwd )
		log.debug( 'waiting for auth' )
		await auth.wait( timeout = timeout_seconds )
		log.debug( 'authenticated' )
	
	async def connect_from( self,
		reader: asyncio.StreamReader,
		writer: asyncio.StreamWriter,
		timeout_seconds: Union[int,float] = 3,
	) -> dict[str,str]:
		log = logger.getChild ( 'ESL.connect_from' )
		
		# NOTE: this does not conform to the normal API and must only be called as the
		# first api call on receiving a connection from and outbound ESL...
		self._event_queue = asyncio.Queue()
		self._requests = asyncio.Queue()
		
		log.debug( 'sending connect command' )
		self._reader = reader
		self._writer = writer
		writer.write( b'connect\n\n' )
		await writer.drain()
		
		log.debug( 'waiting for channel variables' )
		hdrs = await reader.readuntil( b'\n\n' )
		
		log.debug( 'creating reader task' )
		asyncio.create_task( self._reader_task() )
		assert await asyncio.wait_for( self._reader_alive.wait(), timeout = timeout_seconds ), 'reader never started'
		
		return ESL.Message._parse_headers( hdrs.decode( 'utf-8', 'replace' ))
	
	def escape( self, s: Union[int,str] ) -> str:
		_s_ = str( s ).replace( '\\', '\\\\' ).replace( "'", "\\'" )
		return f"'{_s_}'"
	
	# BEGIN requests:
	
	async def answer( self ) -> ESL.Request:
		return await self._send( ESL.Request( self, 'sendmsg', {
			'call-command': 'execute',
			'execute-app-name': 'answer',
		}))
	
	async def auth( self, pwd: str ) -> ESL.Request:
		r = ESL.AuthRequest( self, f'auth {pwd}' )
		return await r.wait()
	
	#async def linger( self ) -> None:
	#	log = logger.getChild( 'ESO.linger' )
	#	await self._write( b'linger\n\n' )
	#	packet = await self._waitfor( b'\n\n' )
	#	log.warn( f'packet={packet!r}' )
	
	async def event( self,
		event_name: str,
		headers: Opt[Dict[str,str]] = None,
		body: Opt[str] = None,
	) -> ESL.Request:
		#log = logger.getChild( 'ESL.event' )
		cmd = f'sendevent {event_name}'
		r = ESL.Request( self, cmd, headers, body )
		return await r.wait()
	
	async def event_plain_all( self ) -> ESL.Request:
		return await self._send( ESL.Request( self, 'event plain all' ))
	
	async def execute( self, app: str, *args: str ) -> AsyncIterator[ESL.Message]:
		log = logger.getChild( 'ESL.execute' )
		assert isinstance( app, str ) and len( app ), f'invalid app={app!r}'
		args_ = ' '.join( map( self.escape, args ))
		r = await self._send( ESL.Request( self, 'sendmsg', {
			'call-command': 'execute',
			'execute-app-name': app,
			'execute-app-arg': args_,
		}))
		log.debug( 'r=%r', r )
		while True:
			async for event in self.events():
				event_name = event.event_name
				if event_name == 'CHANNEL_EXECUTE_COMPLETE':
					app2 = event.header( 'Application' )
					appdata = event.header( 'Application-Data' )
					if app == app2 and appdata == args_:
						return
				yield event
	
	async def filter( self,
		key: str,
		val: str,
	) -> ESL.Request:
		assert key.strip().lower() != 'delete'
		assert ' ' not in key
		assert ' ' not in val
		return await self._send( ESL.Request( self, f'filter {key} {val}' ))
	
	async def filter_delete( self,
		key: str,
		val: str,
	) -> ESL.Request:
		assert key.strip().lower() != 'delete'
		assert ' ' not in key
		assert ' ' not in val
		return await self._send( ESL.Request( self, f'filter delete {key} {val}' ))
	
	async def global_getvar( self, key: str ) -> ESL.ValueRequest:
		assert isinstance( key, str ) and ' ' not in key, f'invalid key={key!r}'
		return await self._send( ESL.ValueRequest( self, f'api global_getvar {key}' ))
	
	async def global_setvar( self,
		key: str,
		val: str = '',
	) -> ESL.Request:
		assert isinstance( key, str ) and ' ' not in key, f'invalid key={key!r}'
		assert isinstance( val, str ) and ' ' not in val, f'invalid val={val!r}'
		return await self._send( ESL.Request( self,
			f'api global_setvar {key} {val}'
		))
	
	async def hangup( self, reason: str = 'USER_BUSY' ) -> ESL.Request:
		# TODO FIXME: this seems like it will only work on an Event Socket Outbound
		return await self._send( ESL.Request( self, 'sendmsg', {
			'call-command': 'execute',
			'execute-app-name': 'hangup',
			'execute-app-arg': reason,
		}))
	
	async def hostname( self ) -> ESL.ValueRequest:
		return await self._send( ESL.ValueRequest( self, 'api hostname' ))
	
	async def lua( self,
		script: str, # freeswitch lua interface can't handle this being quoted...
		*args: str,
	) -> ESL.ValueRequest: # TODO FIXME: is ESL.ValueRequest correct for lua command ( using .reply.body in code below )
		_args_ = ' '.join( map( self.escape, args ))
		return await self._send( ESL.ValueRequest( self, f'api lua {script} {_args_}' ))
	
	async def luarun( self,
		*args: str,
	) -> ESL.Request:
		_args_ = ' '.join( args )
		return await self._send( ESL.Request( self, f'api luarun {_args_}' ))
	
	async def myevents( self ) -> ESL.Request:
		#log = logger.getChild( 'ESL.myevents' )
		return await self._send( ESL.Request( self, 'myevents' ))
	
	async def play_and_get_digits( self,
		min_digits: int,
		max_digits: int,
		tries: int,
		timeout: datetime.timedelta,
		terminators: str,
		file: str,
		invalid_file: Opt[str] = None,
		var_name: Opt[str] = None,
		regexp: Opt[str] = None,
		digit_timeout: Opt[datetime.timedelta] = None,
		transfer_on_failure: Opt[str] = None,
	) -> AsyncIterator[ESL.Message]:
		log = logger.getChild( 'ESL.play_and_get_digits' )
		assert min_digits >= 0, f'invalid min_digits={min_digits!r}'
		assert max_digits <= 128, f'invalid max_digits={max_digits!r}'
		assert min_digits <= max_digits, f'invalid min_digits={min_digits!r} vs max_digits={max_digits!r}'
		assert tries > 0, f'invalid tries={tries!r}'
		timeout_milliseconds = timeout.total_seconds() * 1000
		assert timeout_milliseconds >= 0, f'invalid timeout={timeout!r}'
		assert isinstance( terminators, str ), f'invalid terminators={terminators!r}'
		assert isinstance( file, str ) and len( file ), f'invalid file={file!r}'
		digit_timeout_ms = digit_timeout.total_seconds() * 1000 if digit_timeout else timeout_milliseconds
		
		async for event in self.execute( 'play_and_get_digits',
			str( min_digits ),
			str( max_digits ),
			str( tries ),
			str( timeout_milliseconds ),
			terminators,
			file,
			invalid_file or '',
			var_name or '',
			regexp or '',
			str( digit_timeout_ms ),
			transfer_on_failure or '',
		):
			yield event
	
	async def playback( self, stream: str, *,
		event_lock: bool = False,
	) -> AsyncIterator[ESL.Message]:
		#log = logger.getChild( 'ESL.playback' )
		# TODO FIXME: this seems like it will only work on an Event Socket Outbound
		assert isinstance( stream, str ) and len( stream ), f'invalid stream={stream!r}'
		async for event in self.execute( 'playback', stream ):
			yield event
	
	async def record( self,
		path: Path,
		time_limit: Opt[datetime.timedelta] = None,
		silence_threshold: int = 30,
		silence_hits: int = 5,
	) -> AsyncIterator[ESL.Message]:
		log = logger.getChild( 'ESL.record' )
		assert isinstance( path, Path ), f'invalid path={path!r}'
		assert path.parent.is_dir(), f'path.parent={path.parent!r} does not exist'
		assert time_limit is None or ( isinstance( time_limit, datetime.timedelta ) and time_limit.total_seconds() > 0 ), f'invalid time_limit={time_limit!r}'
		assert isinstance( silence_threshold, int ) and silence_threshold > 0, f'invalid silence_threshold={silence_threshold!r}'
		assert isinstance( silence_hits, int ) and silence_hits > 0, f'invalid silence_hits={silence_hits!r}'
		path_ = str( path ).replace( '\\', '/' )
		async for event in self.execute( 'record',
			path_,
			str( int( time_limit.total_seconds() )) if time_limit else '',
			str( silence_threshold ),
			str( silence_hits ),
		):
			yield event
	
	async def regex( self, needle: str, haystack: str ) -> bool:
		assert ' ' not in needle, f'invalid needle={needle!r}'
		assert ' ' not in haystack, f'invalid haystack={haystack!r}'
		args: str = '|'.join( map( lambda s: s.replace( '|', r'\|' ), [
			needle,
			haystack,
		]))
		r = await self._send( ESL.BoolRequest( self,
			f'api regex {args}'
		))
		return r.value
	
	async def strftime( self ) -> ESL.ValueRequest:
		return await self._send( ESL.ValueRequest( self, 'api strftime' ))
	
	async def uuid_break( self,
		uuid: str,
		all: Literal['','all'],
	) -> ESL.Request:
		assert isinstance( uuid, str ) and len( uuid ) == 36, f'invalid uuid={uuid!r}'
		assert all in ( '', 'all' ), f'invalid all={all!r}'
		return await self._send( ESL.Request( self,
			f'api uuid_break {uuid} {all}'
		))
	
	async def uuid_broadcast( self,
		uuid: str,
		path: str,
		leg: UUID_BROADCAST_LEG,
	) -> ESL.Request:
		assert isinstance( uuid, str ) and len( uuid ) == 36, f'invalid uuid={uuid!r}'
		assert isinstance( path, str ) and len( path ) > 0, f'invalid path={path!r}'
		return await self._send( ESL.Request( self,
			f'api uuid_broadcast {uuid} {self.escape(path)} {leg}'
		))
	
	async def uuid_exists( self,
		uuid: str,
	) -> ESL.BoolRequest:
		assert isinstance( uuid, str ) and len( uuid ) == 36, f'invalid uuid={uuid!r}'
		return await self._send( ESL.BoolRequest( self, f'api uuid_exists {uuid}' ))
	
	async def uuid_getvar( self,
		uuid: str,
		key: str,
	) -> ESL.ValueRequest:
		assert isinstance( uuid, str ) and len( uuid ) == 36, f'invalid uuid={uuid!r}'
		assert isinstance( key, str ) and ' ' not in key, f'invalid key={key!r}'
		return await self._send( ESL.ValueRequest( self, f'api uuid_getvar {uuid} {key}' ))
	
	async def uuid_kill( self,
		uuid: str,
	) -> ESL.Request:
		assert isinstance( uuid, str ) and len( uuid ) == 36, f'invalid uuid={uuid!r}'
		return await self._send( ESL.Request( self, f'api uuid_kill {uuid}' ))
	
	async def uuid_setvar( self,
		uuid: str,
		key: str,
		val: str,
	) -> ESL.Request:
		assert isinstance( uuid, str ) and len( uuid ) == 36, f'invalid uuid={uuid!r}'
		assert isinstance( key, str ) and ' ' not in key, f'invalid key={key!r}'
		assert isinstance( val, str ) and ' ' not in val, f'invalid val={val!r}'
		return await self._send( ESL.Request( self,
			f'api uuid_setvar {uuid} {key} {val}'
		))
	
	# END requests ^^^^
	
	def _assert_alive( self ) -> None:
		# TODO FIXME: check timestamp of last heartbeat event...
		if not self._reader_alive.is_set():
			if self.closed:
				raise ESL.Disconnect()
			else:
				raise ESL.HardError( 'reader is not alive' )
	
	async def events( self, timeout: Union[int,float] = 0.25 ) -> AsyncIterator[ESL.Message]:
		while True:
			self._assert_alive()
			try:
				event = await asyncio.wait_for( self._event_queue.get(), timeout = timeout )
			except asyncio.exceptions.TimeoutError: # queue.Empty:
				return
			else:
				event.on_yield()
				yield event
	
	async def _send( self, req: ESL.RequestType ) -> ESL.RequestType:
		log = logger.getChild( 'ESL._send' )
		if req.raw:
			async with self.lock:
				log.log( DEBUG9, 'XMIT %r', req.raw )
				writer = self._writer
				if writer is None:
					raise EOFError( 'socket closed' )
				await self._requests.put( req )
				writer.write( req.raw )
				await writer.drain()
				await req.wait()
		elif not isinstance( req, ESL.HelloRequest ):
			log.error( 'ignoring %s.raw=%s b/c falsy', type( req ).__name__, req.raw )
		return req
	
	async def _reader_task( self ) -> None:
		log = logger.getChild( 'ESL._reader_task' )
		log.log( DEBUG9, 'starting up' )
		self._reader_alive.set()
		buf: bytes = b''
		reader = self._reader # make a copy of internal reader object, so if ESL object gets closed and reopened we can know it
		try:
			while reader is not None and reader == self._reader: # if reader has changed, this reader is done ( new call to connect() will spawn a new reader )
				try:
					#try:
					data = await reader.read( 16384 )
					#except socket.timeout:
					#	log.debug( 'socket.timeout' )
					#	continue
					#except OSError as e:
					#	if e.errno == socket.EBADF:
					#		# socket is no (no longer) valid
					#		return
					#	raise
					if not data:
						log.debug( 'got EOF' )
						await self._event_queue.put( ESL.ErrorEvent( ESL.HardError( 'EOF' )))
						return
					else:
						log.log( DEBUG9, 'data=%r', data )
						buf = await self._reader_parse_bytes( buf + data )
				except Exception as e:
					log.exception( 'Unexpected error:' )
					await self._event_queue.put( ESL.ErrorEvent( ESL.HardError( repr( e )).with_traceback( e.__traceback__ )))
					await asyncio.sleep( 1.0 )
		finally:
			self._reader_alive.clear()
	
	async def _reader_parse_bytes( self, buf: bytes ) -> bytes:
		log = logger.getChild( 'ESL._reader_parse_bytes' )
		while True:
			msg, buf = ESL.Message.parse( buf )
			if msg is None:
				#log.debug( f'not a complete packet: buf={buf!r}' )
				return buf
			log.log( DEBUG9, 'msg=%r', msg )
			content_type = msg.header( 'Content-Type' )
			log.log( DEBUG9, 'content_type=%r', content_type )
			
			if content_type in (
				'auth/request',
				'command/reply',
				'api/response',
				'text/rude-rejection',
			):
				try:
					request = self._requests.get_nowait()
				except asyncio.queues.QueueEmpty:
					raise ESL.HardError( f'{content_type} when not expecting one' ) from None
				assert request is not None
				#log.debug( f'request={request!r} getting msg={msg!r}' )
				request.reply = msg
				try:
					request.on_reply( msg )
				except ESL.Error as e:
					request.err = e # NOTE: will be rethrown from Request.wait()
				request.trigger.set()
			elif content_type == 'text/event-plain':
				evt = msg
				evt.content_type = content_type
				evt.esl_headers = evt.headers
				evt_hdrs, evt_body = evt.body.split( '\n\n', 1 )
				evt.headers = ESL.Message._parse_headers( evt_hdrs )
				try:
					evt.when_event = datetime.datetime.fromtimestamp( float( evt.headers['Event-Date-Timestamp'] ) * 0.000001 )
				except Exception:
					log.exception( 'Error parsing event timestamp:' )
					evt.when_event = datetime.datetime.now() # fake it 'til you make it
				evt.when_rcvd = datetime.datetime.now()
				evt.body = evt_body
				#log.debug( 'queueing evt id %r %r', id( evt ), evt.event_name )
				await self._event_queue.put( evt )
			else:
				if content_type == 'text/disconnect-notice':
					await self._event_queue.put( ESL.DisconnectEvent() )
					continue
				elif content_type is None:
					errmsg = 'event missing content-type'
				else:
					errmsg = f'Unknown content-type: {content_type!r}'
				log.warning( errmsg )
				await self._event_queue.put( ESL.ErrorEvent( ESL.HardError( errmsg )))
	
	@property
	def closed( self ) -> bool:
		return self._writer is None
	
	async def close( self ) -> None:
		''' this method attempts to tell FreeSWITCH we're going away '''
		log = logger.getChild( 'ESL.close' )
		if self._writer is not None:
			try:
				r = await self._send( ESL.Request( self, 'exit' ))
			except ESL.Disconnect:
				pass
			except Exception as e1:
				log.warning( 'Error trying to shut down connection: %r', e1 )
			finally:
				await self._close()
	
	async def _close( self ) -> None:
		''' this method actually does the process of closing down and cleaning up the socket connection '''
		log = logger.getChild( 'ESL._close' )
		writer = self._writer
		self._writer = None
		if writer is not None:
			try:
				#if writer.can_write_eof():
				#	await writer.write_eof()
				writer.close()
				await writer.wait_closed()
			except Exception as e:
				log.warning( 'Error trying to close writer: %r', e )
	
	def __del__( self ) -> None:
		log = logger.getChild( 'ESL.__del__' )
		if self._writer is not None:
			log.warning( 'ESL id=%r deleted without being closed first', self.id )
