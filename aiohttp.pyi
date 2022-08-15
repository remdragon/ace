from typing import Any, AsyncIterator, Dict, Optional as Opt

class ClientSession:
	async def __aenter__( self ) -> ClientSession:
		...
	async def __aexit__( self, *args: Any, **kwds: Any ) -> bool:
		...
	def post( self,
		url: str,
		headers: Opt[Dict[str,str]] = ...,
		data: Opt[Dict[str,str]] = ...,
		json: Opt[Dict[str,str]] = ...,
	) -> Response:
		...

class Response:
	async def __aenter__( self ) -> Response:
		...
	async def __aexit__( self, *args: Any, **kwds: Any ) -> bool:
		...
	async def text( self ) -> str:
		...
