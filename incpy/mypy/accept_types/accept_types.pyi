from decimal import Decimal
import re
from typing import Any

class AcceptableType:
	mime_type: str
	weight: Decimal
	pattern: re.Pattern[str]
	
	def __init__( self, raw_mime_type: str ) -> None:
		...
	
	def matches( self, mime_type: str ) -> re.Match[str]|None:
		...
	
	def __str__( self ) -> str:
		...
	
	def __repr__( self ) -> str:
		...
	
	def __eq__( self, other: Any ) -> bool:
		...
	
	def __lt__( self, other: Any ) -> bool:
		...

def get_best_match( header: str, available_types: list[str] ) -> str|None:
	...

def parse_header( header: str ) -> list[AcceptableType]:
	...
