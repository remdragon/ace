import datetime
import logging
import sys
from typing import List

logger = logging.getLogger ( __name__ )

def dhms ( dt: datetime.timedelta, limit: int = 2 ) -> str:
	'''
	>>> dhms ( datetime.timedelta() )
	'0s'
	>>> dhms ( datetime.timedelta ( days = 1, hours = 3, minutes = 5, seconds = 7 ) )
	'1d 3h'
	>>> dhms ( -datetime.timedelta ( days = 1, hours = 3, minutes = 5, seconds = 7 ) )
	'-(1d 3h)'
	>>> dhms ( datetime.timedelta ( seconds = 4.5 ) )
	'4.5s'
	'''
	limit = max ( limit, 1 ) # you must allow at least one visible component
	ar: List[str] = []
	suffix = ''
	if dt.days < 0:
		dt = -dt
		ar.append ( '-(' )
		limit += 1
		suffix = ')'
	seconds = dt.seconds % 60
	minutes = ( dt.seconds // 60 ) % 60
	hours = dt.seconds // 3600
	
	if dt.days:
		ar.append ( f'{dt.days}d ' )
	if hours:
		ar.append ( f'{hours}h ' )
	if minutes:
		ar.append ( f'{minutes}m ' )
	if not ar:
		ar.append ( f'{seconds+dt.microseconds*0.000001:.3f}'.rstrip ( '0' ).rstrip ( '.' ) + 's' )
	elif seconds:
		ar.append ( f'{seconds}s ' )
	
	return ''.join ( ar[:limit] ).rstrip() + suffix

if True: # for now, run doctest on every import to make sure I don't break something
	if __name__ == '__main__':
		logging.basicConfig ( level = logging.DEBUG )
	import doctest
	fail_count, test_count = doctest.testmod ( sys.modules[__name__] ) # TODO FIXME: does this cause pyinstaller executable bloat?
	assert not fail_count, f'{fail_count=}'
	if __name__ == '__main__':
		print ( f'{test_count=} test(s) passed' )

if __name__ == '__main__':
	now = datetime.datetime.now()
	earlier = now - datetime.timedelta ( hours = 4, minutes = 5, seconds = 6 )
	positive_delta = now - earlier
	print ( f'{positive_delta=} -> {dhms(positive_delta)=}' )
	negative_delta = earlier - now
	print ( f'{negative_delta=} -> {dhms(negative_delta)=}' )
