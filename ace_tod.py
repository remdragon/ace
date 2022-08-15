# stdlib imports:
import datetime
import logging
import os
import re
from typing import Any, Dict, List, Optional as Opt, Union

logger = logging.getLogger( __name__ )

def epoch_from_dateobj( d: datetime.datetime ) -> float:
	return d.timestamp()

def dateobj_from_epoch( epoch_seconds: float ) -> datetime.datetime:
	return datetime.datetime.fromtimestamp( epoch_seconds )

def format_dateobj( fmt: str, d: datetime.datetime ) -> str:
	return d.strftime( fmt )

def epoch_add_days( e: float, days: Union[int,float] ) -> float:
	return e + days * 24 * 60 * 60

def dateobj_add_days( d: datetime.datetime, days: Union[int,float] ) -> datetime.datetime:
	e = epoch_from_dateobj( d )
	e = epoch_add_days( e, days )
	return dateobj_from_epoch( e )

DOW: Dict[str,int] = {
	'mon': 0, 'mo': 0, 'm': 0,
	'tue': 1, 'tu': 1,
	'wed': 2, 'we': 2, 'w': 2,
	'thu': 3, 'th': 3,
	'fri': 4, 'fr': 4, 'f': 4,
	'sat': 5, 'sa': 5,
	'sun': 6, 'su': 6,
}

def minutes_from_hhmm( hhmm: str ) -> int:
	#log = logger.getChild( 'minutes_from_hhmm' )
	#log.debug( 'hhmm=%s', repr( hhmm ))
	hh, _, mm = hhmm.partition( ':' )
	return int( hh ) * 60 + int( mm )

def minutes_from_dow_hhmm( dow: str, hhmm: str ) -> int:
	dow_ = DOW[dow] # convert 'tue' into 1
	minutes = minutes_from_hhmm( hhmm ) # convert '01:00' into 60
	return dow_ * 24 * 60 + minutes

def dateobj_from_datetimestr( s: str, year: Union[int,str] ) -> datetime.datetime:
	#log = logger.getChild( 'dateobj_from_datetimestr' )
	month, _, s = s.partition( '/' )
	day, _, t = s.partition( ' ' )
	#log.info( 'day=' .. repr( day ))
	if '/' in day:
		day, _, year = day.partition( '/' )
		#log.info( 'day=%s, year=%s', repr( day ), repr( year ))
	hour, _, minute = t.partition( ':' )
	second = '0'
	if ':' in minute:
		minute, _, second = minute.partition( ':' )
	#log.info( 'hour=%s, minute=%s, second=%s', repr( hour ), repr( minute ), repr( second ))
	return datetime.datetime(
		year = int( year ), month = int( month ), day = int( day ),
		hour = int( hour ), minute = int( minute ), second = int( second ),
	)

def epoch_from_datetimestr( d: str, year: int ) -> float:
	return epoch_from_dateobj( dateobj_from_datetimestr( d, year ))

def match_tod( times: Opt[str], dnow: Opt[datetime.datetime] = None, *, verbose: bool = False ) -> bool:
	log = logger.getChild( 'match_tod' )
	
	times = ( times or '' ).lower()
	
	if dnow is None: dnow = datetime.datetime.now()
	now_dow = str( dnow.weekday() )
	
	for line in times.split( '\n' ):
		line = line.strip()
		
		line, subs = re.subn( r'^not\s+', '', line, count = 1 )
		result = ( subs == 0 )
		
		m = re.match( '^\s*([adefhimnorstuw,-]+)\s+(\d+:\d+)\s*-\s*(\d+:\d+)\s*$', line )
		if m:
			# Ex: Mon-Wed,Fri-Sat 08:00-17:00
			
			dowspec = m.group( 1 )
			tod1 = m.group( 2 )
			tod2 = m.group( 3 )
			
			dowspec = dowspec.replace( ' ', '' ) # get rid of spaces
			if verbose: log.debug( 'dowspec=%s', repr( dowspec ))
			dowlist: List[str] = []
			for rangespec in dowspec.split( ',' ):
				ranges = rangespec.split( '-' )
				if len( ranges ) == 1:
					ranges.append( ranges[0] )
				if verbose: log.debug( 'ranges=%s', repr( ranges ))
				for dow1, dow2 in zip( ranges[:-1], ranges[1:] ):
					j = DOW.get( dow1 )
					k = DOW.get( dow2 )
					if verbose: log.debug( 'j=%s, k=%s', repr( j ), repr( k ))
					if j is None:
						log.warning( 'invalid dow=%r', dow1 )
					elif k is None:
						log.warning( 'invalid dow=%r', dow2 )
					else:
						while True:
							if verbose: log.debug( 'j=%s', repr( j ))
							dowlist.append( str( j ))
							if j == k: break
							j = ( j + 1 ) % 7
			dow = ''.join( dowlist )
			if verbose: log.debug( 'dow=%s, now_dow=%s', repr( dow ), repr( now_dow ))
			
			if verbose: log.debug( 'tod1=%s, tod2=%s', repr( tod1 ), repr( tod2 ))
			min1 = minutes_from_hhmm( tod1 )
			min2 = minutes_from_hhmm( tod2 )
			mnow = minutes_from_hhmm( f'{dnow.hour}:{dnow.minute}' )
			if verbose: log.debug( 'min1=%s, min2=%s, mnow=%s', repr( min1 ), repr( min2 ), repr( mnow ))
			if min1 <= min2:
				if min1 <= mnow and mnow <= min2:
					if now_dow in dow:
						return result
			else:
				if mnow >= min1:
					if now_dow in dow:
						return result
					return result
				if mnow <= min2:
					# our time matched but after midnight, we need to check if dow matched the previous day, not this day...
					yesterday = dateobj_add_days( dnow, -1 )
					yesterday_dow = str( yesterday.weekday() )
					if yesterday_dow in dow:
						return result
			if verbose: log.debug( '!match' )
			continue
		
		m = re.match( r'^\s*([adefhimnorstuw]+)\s+(\d{1,2}:\d{2})\s*-\s*([adefhimnorstuw]+)\s+(\d{1,2}:\d{2})\s*$', line )
		if m:
			# Ex: Fri 17:00 - Mon 08:00
			parts: List[str] = line.split( '-' )
			if verbose: log.debug( 'parts=%s', repr( parts ))
			if len( parts ) <= 1:
				log.warning( 'not enough parts in time spec: %s', line )
			else:
				parts2: List[int] = []
				mnow = dnow.weekday() * 24 * 60 + minutes_from_hhmm( f'{dnow.hour}:{dnow.minute}' )
				for i, part in enumerate( parts ):
					dow, hhmm = re.split( '\s+', part.strip(), maxsplit = 1 )
					if verbose: log.debug( 'dow=%s, hhmm=%s', repr( dow ), repr( hhmm ))
					parts2.append( minutes_from_dow_hhmm( dow, hhmm ))
				for m1, m2 in zip( parts2[:-1], parts2[1:] ):
					if m1 <= m2:
						if m1 <= mnow and mnow <= m2:
							return result
					else:
						if mnow <= m1 or mnow >= m2:
							return result
			continue
		
		if re.match( r'^\s*\d+/\d+/\d\d\d\d\s+\d+:\d+\s*-\s*\d+/\d+/\d\d\d\d\s+\d+:\d+\s*$', line ):
			# Ex: 1/1/2000 17:00 - 1/2/2000 08:00
			s1, _, s2 = line.partition( '-' )
			e1 = epoch_from_datetimestr( s1, dnow.year )
			e2 = epoch_from_datetimestr( s2, dnow.year )
			enow = epoch_from_dateobj( dnow )
			if e2 < e1:
				# user specified them backwards but gave absolute years so just swap them
				e2, e1 = e1, e2
			if e1 <= enow and enow <= e2:
				return result
			continue
		
		if re.match( r'^\s*\d+/\d+/\d\d\d\d\s+\d+:\d+\s*-\s*\d+/\d+\s+\d+:\d+\s*$', line ):
			# Ex: 1/1/2000 17:00 - 1/2 08:00
			dtspec1, _, dtspec2 = line.partition( '-' )
			t1 = dateobj_from_datetimestr( dtspec1, dnow.year )
			e2 = epoch_from_datetimestr( dtspec2, t1.year )
			e1 = epoch_from_dateobj( t1 )
			if e2 < e1:
				# year is inferred in 2nd entry, but month/day is < than 1st entry, so bump 2nd entry to next year
				e2 = epoch_from_datetimestr( dtspec2, t1.year + 1 )
			enow = epoch_from_dateobj( dnow )
			if e1 <= enow and enow <= e2:
				return result
			continue
		
		if re.match( r'^\s*\d+/\d+\s+\d+:\d+\s*-\s*\d+/\d+\s+\d+:\d+\s*$', line ):
			# Ex: 1/1 17:00 - 1/2 08:00
			s1, _, s2 = line.partition( '-' )
			s1 = s1.strip()
			s2 = s2.strip()
			d1 = dateobj_from_datetimestr( s1, dnow.year )
			e1 = epoch_from_dateobj( d1 )
			enow = epoch_from_dateobj( dnow )
			if e1 > enow:
				d1 = dateobj_from_datetimestr( s1, dnow.year - 1 )
				e1 = epoch_from_dateobj( d1 )
			d2 = dateobj_from_datetimestr( s2, d1.year )
			e2 = epoch_from_dateobj( d2 )
			if e2 < e1:
				# bump e2 to next year
				e2 = epoch_from_datetimestr( s2, d1.year + 1 )
			if e1 <= enow and enow <= e2:
				return result
			continue
		
		if re.match( r'^\s*\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*$', line ) or re.match( r'^\s*\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*$', line ):
			# Ex: 1/1 17:00 - 08:00
			s1, _, s2 = line.partition( '-' )
			if verbose: log.debug( 's1=%s, s2=%s', repr( s1 ), repr( s2 ))
			d1 = dateobj_from_datetimestr( s1.strip(), dnow.year )
			if verbose: log.debug( 'd1=%s', repr( d1 ))
			e1 = epoch_from_dateobj( d1 )
			s2 = d1.strftime( '%m/%d/%Y ' ) + s2.strip()
			if verbose: log.debug( 's2=%s', repr( s2 ))
			e2 = epoch_from_datetimestr( s2, dnow.year )
			if e2 < e1:
				e2 = epoch_add_days( e2, 1 )
			enow = epoch_from_dateobj( dnow )
			if e1 <= enow and enow <= e2:
				return result
			continue
		
		log.warning( 'invalid match_tod line=%s', repr( line ))
	return False

if __name__ == '__main__':
	logging.basicConfig( level = logging.DEBUG )
	
	logger.debug( 'testing minutes_from_hhmm()' )
	test: Any = minutes_from_hhmm( '00:00' )
	assert test == 0, test
	test = minutes_from_hhmm( '00:01' )
	assert test == 1, test
	test = minutes_from_hhmm( '01:00' )
	assert test == 60, test
	test = minutes_from_hhmm( '23:59' )
	assert test == 1439, test
	
	logger.debug( 'testing minutes_from_dow_hhmm()' )
	test = minutes_from_dow_hhmm( 'tue', '00:00' )
	assert test == 1440, test
	test = minutes_from_dow_hhmm( 'sun', '00:00' )
	assert test == 8640, test
	
	logger.debug( 'testing format_dateobj()' )
	test = format_dateobj( '%Y-%m-%d %H:%M:%S', dateobj_from_datetimestr( '12/31/1999 23:59:58', 1999 ))
	assert '1999-12-31 23:59:58' == test, test
	test = format_dateobj( '%Y-%m-%d %H:%M:%S', dateobj_from_datetimestr( '12/31 23:59:58', 1999 ))
	assert '1999-12-31 23:59:58' == test, test
	
	logger.debug( 'testing 1st match_tod() pattern' )
	fri_10am = dateobj_from_datetimestr( '02/04/2022 10:00', 1999 )
	wed_3pm = dateobj_from_datetimestr( '02/02/2022 15:00', 1999 )
	thu_12am = dateobj_from_datetimestr( '02/03/2022 00:00', 1999 )
	test = match_tod( 'Mon-Fri 08:00-17:00', fri_10am )
	assert test == True, test
	test = match_tod( 'not Mon-Fri 08:00-17:00', fri_10am )
	assert test == False, test
	test = match_tod( 'Wed 15:00-15:00', wed_3pm )
	assert test == True, test
	test = match_tod( 'Wed 15:01-15:01', wed_3pm )
	assert test == False, test
	test = match_tod( 'Su-Sa 00:00-14:59', wed_3pm )
	assert test == False, test
	test = match_tod( 'Su-Sa 15:01-23:59', wed_3pm )
	assert test == False, test
	test = match_tod( 'Su-Sa 15:01-14:59', wed_3pm )
	assert test == False, test
	test = match_tod( 'Thu 23:59-10:00', fri_10am )
	assert test == True, test
	
	logger.debug( 'testing 2nd match_tod() pattern' )
	test = match_tod( 'Wed 15:00 - Fri 10:00', wed_3pm, verbose = True )
	assert test == True, test
	test = match_tod( 'Wed 15:00 - Fri 10:00', thu_12am )
	assert test == True, test
	test = match_tod( 'Wed 15:00 - Fri 10:00', fri_10am )
	assert test == True, test
	test = match_tod( 'Wed 15:01 - Fri 10:00', wed_3pm )
	assert test == False, test
	test = match_tod( 'Wed 15:00 - Fri 09:59', fri_10am )
	assert test == False, test
	
	logger.debug( 'testing 3rd match_tod() pattern' )
	test = match_tod( '2/4/2022 00:00 - 2/4/2022 09:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/4/2022 10:01 - 2/4/2022 23:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/4/2022 10:00 - 2/4/2022 10:00', fri_10am )
	assert test == True, test
	
	logger.debug( 'testing 4th match_tod() pattern' )
	test = match_tod( '2/4/2022 00:00 - 2/4 09:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/4/2022 10:01 - 2/4 23:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/4/2022 10:00 - 2/4 10:00', fri_10am )
	assert test == True, test
	test = match_tod( '12/31/2021 10:00 - 2/4 10:00', fri_10am )
	assert test == True, test
	
	logger.debug( 'testing 5th match_tod() pattern' )
	test = match_tod( '2/4 00:00 - 2/4 09:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/4 10:01 - 2/4 23:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/4 10:00 - 2/4 10:00', fri_10am )
	assert test == True, test
	test = match_tod( '12/31 10:00 - 2/4 10:00', fri_10am )
	assert test == True, test
	
	logger.debug( 'testing 6th match_tod() pattern' )
	test = match_tod( '2/3 23:59 - 09:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/3 23:59 - 10:00', fri_10am )
	assert test == True, test
	test = match_tod( '2/4 10:00 - 10:00', fri_10am )
	assert test == True, test
	test = match_tod( '2/3/2022 23:59 - 09:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/3/2022 23:59 - 10:00', fri_10am )
	assert test == True, test
	test = match_tod( '2/4/2022 10:00 - 10:00', fri_10am )
	assert test == True, test
	test = match_tod( '2/3/2021 23:59 - 09:59', fri_10am )
	assert test == False, test
	test = match_tod( '2/3/2021 23:59 - 10:00', fri_10am )
	assert test == False, test
	test = match_tod( '2/4/2021 10:00 - 10:00', fri_10am )
	assert test == False, test
	
	logger.info( '**** ALL DATE/TIME TESTS PASSED ****' )
