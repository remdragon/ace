import os
from typing import IO, Optional as Opt, Union

class AudioSegment:
	@classmethod
	def from_wav( cls, path: Union[str,os.PathLike[str],IO[bytes]] ) -> AudioSegment: ...
	
	def export( self,
		path: Opt[Union[str,os.PathLike[str]]] = ...,
		format: str = 'mp3',
	) -> IO[bytes]: ...
