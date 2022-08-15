# stdlib imports:
import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncIterator, Callable, Optional as Opt
from typing_extensions import Literal

# 3rd-party imports:
import aiofiles.os # pip install aiofiles
import aioshutil # pip install aioshutil

# local imports:
from esl import ESL

logger = logging.getLogger( __name__ )

CAUSE = Literal['ORIGINATOR_CANCEL','NORMAL_CLEARING','UNALLOCATED_NUMBER','USER_BUSY']
causes =       ('ORIGINATOR_CANCEL','NORMAL_CLEARING','UNALLOCATED_NUMBER','USER_BUSY')

on_event: Opt[Callable[[ESL.Message],None]] = None

async def answer( esl: ESL, uuid: str, source: str ) -> bool:
	log = logger.getChild( 'answer' )
	log.info( 'answering from %s', source )
	
	# TODO FIXME: there's 2 ways available to us to answer the call.
	if True:
		r = await esl.uuid_answer( uuid )
		# TODO FIXME: check for -ERR condition? (ESL might throw an error so may not be necessary)
		log.debug( 'result: %r', r )
	else:
		async for event in await esl.answer():
			if on_event:
				on_event( event )
	
	return True # TODO FIXME: return False if call no longer exists...

async def chmod( path: Path, mode: int ) -> None:
	if os.name == 'posix':
		loop = asyncio.get_running_loop()
		await loop.run_in_executor( None, os.chmod, path, mode )

async def chown( path: Path, user: str, group: str ) -> None:
	if os.name == 'posix':
		await aioshutil.chown( str( path ), user, group )

async def glob( path: Path, mask: str ) -> AsyncIterator[Path]:
	it = iter( path.glob( mask ))
	loop = asyncio.get_running_loop()
	SENTINEL = object()
	while True:
		file = await loop.run_in_executor( None, next, it, SENTINEL )
		if file is SENTINEL:
			break
		assert isinstance( file, Path ), f'invalid file={file!r}'
		yield file

async def hangup( esl: ESL, uuid: str, cause: CAUSE, source: str ) -> None:
	log = logger.getChild( 'hangup' )
	log.info( 'hangup with cause=%r from %r', cause, source )
	
	# TODO FIXME: there's 2 way available to use to hangup a call
	if True:
		r = await esl.uuid_kill( uuid, cause )
		log.debug( 'result: %r', r )
	else:
		async for event in await esl.hangup( cause ):
			if on_event:
				on_event( event )

async def mkdir( path: Path, *, mode: int = 0o775, parents: bool = False, exist_ok: bool = False ) -> None:
	if parents and not path.parent.is_dir():
		await mkdir( path.parent, mode = mode, parents = parents, exist_ok = exist_ok )
	try:
		await aiofiles.os.mkdir( str( path ), mode = mode )
	except FileExistsError:
		if exist_ok:
			return
		raise

async def mkdirp( path: Path, *, mode: int = 0o775, exist_ok: bool = True ) -> None:
	await mkdir( path, mode = mode, parents = True, exist_ok = exist_ok )

async def pre_answer( esl: ESL, uuid: str, source: str ) -> bool:
	log = logger.getChild( 'pre_answer' )
	log.info( 'ppre-answering from %s', source )
	
	# TODO FIXME: there's 2 ways available to us to pre-answer the call.
	if True:
		r = await esl.uuid_pre_answer( uuid )
		# TODO FIXME: check for -ERR condition? (ESL might throw an error so may not be necessary)
		log.debug( 'result: %r', r )
	else:
		async for event in await esl.pre_answer():
			if on_event:
				on_event( event )
	
	return True # TODO FIXME: return False if call no longer exists...
