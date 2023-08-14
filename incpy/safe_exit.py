# stdlib imports:
import functools
from types import TracebackType
from typing import Any, Callable, Coroutine, Optional as Opt, Type, TypeVar

# 3rd-party imports:
from typing_extensions import Literal # pip install typing-extensions

T = TypeVar ( 'T' )

EXITFUNC = Callable[
	[
		T,
		Opt[Type[BaseException]],
		Opt[BaseException],
		Opt[TracebackType],
	],
	Literal[False]
]

AEXITFUNC = Callable[
	[
		T,
		Opt[Type[BaseException]],
		Opt[BaseException],
		Opt[TracebackType],
	],
	Coroutine[Any,Any,Literal[False]]
]

def safe_exit ( exitfunc: EXITFUNC[T] ) -> EXITFUNC[T]:
	@functools.wraps ( exitfunc )
	def safe_exit_wrapper ( self: T,
		exc_type: Opt[Type[BaseException]],
		exc_val: Opt[BaseException],
		exc_tb: Opt[TracebackType],
	) -> Literal[False]:
		try:
			return exitfunc ( self, exc_type, exc_val, exc_tb )
		except Exception:
			if not isinstance ( exc_val, Exception ):
				raise
			return False
	return safe_exit_wrapper

def safe_aexit ( aexitfunc: AEXITFUNC[T] ) -> AEXITFUNC[T]:
	@functools.wraps ( aexitfunc )
	async def safe_aexit_wrapper ( self: T,
		exc_type: Opt[Type[BaseException]],
		exc_val: Opt[BaseException],
		exc_tb: Opt[TracebackType],
	) -> Literal[False]:
		try:
			return await aexitfunc ( self, exc_type, exc_val, exc_tb )
		except Exception:
			if not isinstance ( exc_val, Exception ):
				raise
			return False
	return safe_aexit_wrapper
