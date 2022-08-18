# aiohttp_logging.py

from __future__ import annotations

import aiohttp.client_reqrep
import logging
from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
	from aiohttp.connector import Connection
	from aiohttp.client_proto import ResponseHandler

logger = logging.getLogger( __name__ )

OriginalClientRequest_send = aiohttp.client_reqrep.ClientRequest.send
OriginalStreamWriter = aiohttp.client_reqrep.StreamWriter
OriginalClientResponse_start = aiohttp.client_reqrep.ClientResponse.start
OriginalClientResponse_read = aiohttp.client_reqrep.ClientResponse.read

async def LoggingClientRequest_send(self: aiohttp.client_reqrep.ClientRequest, conn: Connection) -> aiohttp.client_reqrep.ClientResponse:
	logger.debug( f'requesting {self.method} {self.original_url}' )
	return await OriginalClientRequest_send( self, conn )

class LoggingStreamWriter( OriginalStreamWriter ):
	def _write( self, chunk: bytes ) -> None:
		#log = logger.getChild( 'LoggingStreamWriter._write' )
		super()._write( chunk )
		for line in chunk.decode( 'cp437' ).split( '\n' )[:-1]: # -1 because an extra blank lines gets shown otherwise...
			logger.debug( f'C>{line}' )

class LoggingProtocol:
	def __init__( self, protocol: ResponseHandler ) -> None:
		self.protocol = protocol
	
	async def read( self ) -> Tuple[Any,Any]:
		#log = logger.getChild( 'LoggingProtocol.read' )
		msg, payload = await self.protocol.read()
		logger.debug( f'S>HTTP/{msg.version.major}.{msg.version.minor} {msg.code} {msg.reason}' )
		for name, value in msg.raw_headers:
			logger.debug( f'S>{name.decode("cp437")}: {value.decode("cp437")}' )
		logger.debug( 'S>' ) # show blank line between headers and body
		return msg, payload

async def LoggingClientResponse_start( self: aiohttp.client_reqrep.ClientResponse, connection: Connection ) -> aiohttp.client_reqrep.ClientResponse:
	#log = logger.getChild( 'LoggingClientResponse_start' )
	orig_protocol = connection.protocol
	try:
		connection._protocol = LoggingProtocol( orig_protocol ) # type: ignore
		return await OriginalClientResponse_start( self, connection )
	finally:
		connection._protocol = orig_protocol

async def LoggingClientResponse_read( self: aiohttp.client_reqrep.ClientResponse ) -> bytes:
	#log = logger.getChild( 'LoggingClientResponse_read' )
	data = await OriginalClientResponse_read( self )
	for line in data.split( b'\n' ):
		logger.debug( f'S>{line.decode("cp437").rstrip()}' )
	return data

def monkey_patch() -> None:
	assert aiohttp.client_reqrep.StreamWriter == OriginalStreamWriter, 'already monkey-patched'
	aiohttp.client_reqrep.ClientRequest.send = LoggingClientRequest_send # type: ignore
	aiohttp.client_reqrep.StreamWriter = LoggingStreamWriter # type: ignore
	aiohttp.client_reqrep.ClientResponse.start = LoggingClientResponse_start # type: ignore
	aiohttp.client_reqrep.ClientResponse.read = LoggingClientResponse_read # type: ignore