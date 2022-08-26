# https://www.mybluelinux.com/pyhon-lru-cache-with-time-expiration/

from datetime import datetime, timedelta
from functools import lru_cache, wraps
import logging
from typing import Any, Callable, Optional as Opt, TypeVar, Union

logger = logging.getLogger( __name__ )

T = TypeVar( 'T' )

WRAPPED = Callable[...,T]

def timed_lru_cache( seconds: Union[int,float], maxsize: Opt[int] = None ) -> Callable[[WRAPPED[T]],WRAPPED[T]]:
	
	def wrapper_cache( func: WRAPPED[T] ) -> WRAPPED[T]:
		#print( "I will use lru_cache" )
		func2 = lru_cache( maxsize = maxsize )( func )
		#print( "I'm setting func.lifetime" )
		lifetime = timedelta( seconds = seconds )
		#print( "I'm setting func.expiration" )
		expiration = datetime.utcnow() + lifetime
		
		@wraps( func2 )
		def wrapped_func( *args: Any, **kwargs: Any ) -> Any:
			nonlocal lifetime, expiration
			#print( "Check func expiration" )
			#print( f'datetime.utcnow(): {datetime.utcnow()}, expiration: {expiration}' )
			if datetime.utcnow() >= expiration:
				#print( 'func.expiration lru_cache lifetime expired' )
				func2.cache_clear()
				expiration = datetime.utcnow() + lifetime
			
			return func2( *args, **kwargs )
		
		return wrapped_func
	
	return wrapper_cache
