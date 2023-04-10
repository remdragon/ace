#region imports


# stdlib imports:
import logging
from typing import Callable, cast, Tuple, Type

# 3rd-party imports:
from tornado.httpserver import HTTPServer # pip install tornado
from tornado.routing import _RuleList
from tornado.web import Application, RequestHandler # pip install tornado


#endregion imports
#region globals


logger = logging.getLogger( __name__ )


#endregion globals
#region router


class Router:
	def __init__( self ) -> None:
		self._rules: list[Tuple[str,Type[RequestHandler]]] = []
	
	def route( self, rule: str ) -> Callable[[Type[RequestHandler]],Type[RequestHandler]]:
		def decorator( cls: Type[RequestHandler] ) -> Type[RequestHandler]:
			self._rules.append(( rule, cls ))
			return cls
		return decorator
	
	def get_rules( self ) -> _RuleList:
		return cast( _RuleList, self._rules )


#endregion router
#region testing


if __name__ == '__main__':
	logging.basicConfig( level = logging.DEBUG )
	import asyncio
	
	router = Router()
	
	@router.route( '/' )
	class RootHandler( RequestHandler ):
		async def get( self ) -> None:
			self.write( 'Hello World' )
	
	@router.route( '/foo' )
	class FooHandler( RequestHandler ):
		async def get( self ) -> None:
			self.write( 'Fooey!' )
	
	app = Application( router.get_rules() )
	async def main() -> None:
		log = logger.getChild( 'main' )
		log.debug( 'creating HTTPServer' )
		httpd = HTTPServer( app )
		
		port = 8888
		httpd.listen( port )
		log.info( 'listening on port %r', port )
		
		await asyncio.Event().wait()
	asyncio.run( main() )


#endregion testing
