# stdlib imports:
import logging
import sys
from typing import Dict

if sys.platform != 'win32':
	try:
		from systemd.journal import JournaldLogHandler # pip install systemd
	except ImportError:
		print( 'WARNING: JournaldLogHandler not found', file = sys.stderr )
		JournaldLogHandler = None

def init( loglevels: Dict[str,str] ) -> None:
	logging.basicConfig(
		level = logging.DEBUG,
		#level = DEBUG9,
		format = '%(asctime)s:%(levelname)s:%(name)s:%(message)s',
	)
	
	if sys.platform != 'win32' and JournaldLogHandler:
		journald_handler = JournaldLogHandler()
		journald_handler.setFormatter(
			logging.Formatter( '[%(levelname)s] %(message)s' )
		)
		logging.getLogger( '' ).addHandler( journald_handler )
	
	for name, level in loglevels.items():
		assert level.isnumeric() or level in ( 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' ), f'invalid level={level!r}'
		logger = logging.getLogger( name )
		if level.isnumeric():
			logger.setLevel( int( level ))
		else:
			logger.setLevel( getattr( logging, level ))
