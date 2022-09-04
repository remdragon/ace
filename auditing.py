# stdlib imports:
import datetime
import logging
from pathlib import Path

# 3rd-party imports:
import tzlocal # pip install tzlocal


logger = logging.getLogger( __name__ )

_path: Path
_file: str
_time_format: str

def init(
	path: Path,
	file: str,
	time_format: str,
) -> None:
	global _path, _file, _time_format
	_path = path
	_file = file
	_time_format = time_format
	
	_path.mkdir( mode = 0o770, parents = True, exist_ok = True )

class Audit:
	def __init__( self, *, user: str, remote_addr: str ) -> None:
		self.user = user
		self.remote_addr = remote_addr
	
	def audit( self, msg: str ) -> None:
		tzinfo = tzlocal.get_localzone()
		now = datetime.datetime.now( tz = tzinfo )
		line = ' '.join( [
			now.strftime( _time_format ),
			self.user,
			self.remote_addr,
			msg,
		] )
		path = _path / now.strftime( _file )
		with path.open( 'a', encoding = 'utf-8', errors = 'backslashreplace' ) as f:
			print( line, file = f )

class NoAudit( Audit ):
	def __init__( self ) -> None:
		pass
	def audit( self, msg: str ) -> None:
		pass
