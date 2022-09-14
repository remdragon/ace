#!/usr/bin/env python3
#region copyright


# This file is Copyright (C) 2022 ITAS Solutions LP, All Rights Reserved
# Contact ITAS Solutions LP at royce3@itas-solutions.com for licensing inquiries


#endregion copyright
#region imports

# stdlib imports:
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from dataclasses import asdict, fields
import datetime
from enum import Enum
import html
import itertools
import json
import logging
import mimetypes
from multiprocessing import RLock as MPLockFactory
from multiprocessing.synchronize import RLock as MPLock
import os
from pathlib import Path, PurePosixPath
import queue
import random
import re
import shutil
import socket
import sys
import tempfile
from threading import RLock, Thread
from time import sleep
from typing import(
	Any, Callable, cast, Dict, Iterator, List, Optional as Opt,
	Sequence as Seq, Tuple, Type, TypeVar, TYPE_CHECKING, Union,
)
from typing_extensions import Literal # Python 3.7
from urllib.parse import urlencode, urlparse
import uuid

def _requirements() -> int:
	cmd = f'{sys.executable} -m pip install accept-types aiofiles aiohttp aioshutil boto3 flask Flask-Login Flask-Session mypy-extensions pydub PyOpenSSL service_identity tornado tzlocal'
	print ( cmd )
	os.system ( cmd )
	return -1

if __name__ == '__main__' and sys.argv[1:] == [ 'requirements' ]:
	sys.exit( _requirements() )

# 3rd-party imports:
import accept_types # type: ignore # pip install accept-types
from flask import( # pip install flask
	Flask, jsonify, render_template, request, Response,
	send_from_directory, session, url_for,
)
from flask_login import( # type: ignore # pip install flask-login
	LoginManager, UserMixin, AnonymousUserMixin,
	login_required, current_user, confirm_login, login_user, logout_user,
)
from flask_session import Session # type: ignore # pip install flask-session
from tornado.wsgi import WSGIContainer # pip install tornado
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from werkzeug.serving import make_ssl_devcert

if TYPE_CHECKING:
	def redirect( url: str ) -> Response: ...
else:
	from flask import redirect # flask.wrappers.Response vs werkzeug.wrappers.Response

# OS specific:
if sys.platform != 'win32':
	import grp
	import pam # pip install python-pam
	import pwd

if __name__ == '__main__':
	sys.path.append( 'incpy' )

# local imports:
import ace_engine
from ace_fields import Field, ValidationError
import ace_logging
import ace_settings
import auditing
from coalesce import coalesce
from dhms import dhms
import repo
from tts import TTS_VOICES, tts_voices

#endregion imports
#region globals


DEBUG9 = 9

DID_MAX_LENGTH = 10
ANI_MAX_LENGTH = 20
CPN_MAX_LENGTH = 30
ACCT_NUM_MAX_LENGTH = 4
ACCT_NAME_MAX_LENGTH = 30

SESSION_USERDATA = 'userdata'
etc_path = Path( '/etc/itas/ace/' )
default_data_path = Path( '/usr/share/itas/ace/' )

logger = logging.getLogger( __name__ )

if sys.platform != 'win32':
	auth = pam.pam()
else:
	logger.critical(
		'NON-POSIX IMPLEMENTATION ONLY SUPPORTS A SINGLE HARD-CODED USER FOR NOW'
	)

g_settings_mplock = MPLockFactory()
g_car_mplock = MPLockFactory()


#endregion globals
#region utilities


def new_audit() -> auditing.Audit:
	assert request.remote_addr is not None
	return auditing.Audit(
		user = current_user.name,
		remote_addr = request.remote_addr,
	)

def logging_formatTime( self: Any, record: Any, datefmt: Opt[str] = None ) -> str:
	dt = datetime.datetime.fromtimestamp( record.created )
	datefmt = datefmt or '%b%d %H:%M:%S.%F'
	if '%F' in datefmt:
		datefmt = datefmt.replace( '%F', dt.strftime('%f')[:-3] )
	return dt.strftime( datefmt )
setattr( logging.Formatter, 'formatTime', logging_formatTime )

AnyNumeric = TypeVar( 'AnyNumeric', int, float )
def clamp( val: AnyNumeric, minval: AnyNumeric, maxval: AnyNumeric ) -> AnyNumeric:
	return sorted( [ val, minval, maxval ] )[1]

def to_optional_int( s: Opt[str] ) -> Opt[int]:
	if s is None:
		return None
	return int( s )

def is_safe_url( url: str ) -> bool:
	log = logger.getChild( 'is_safe_url' )
	unsafe = bool( urlparse( url ).netloc )
	log.debug( 'url=%r -> unsafe=%r', url, unsafe )
	return not unsafe

def is_root() -> bool:
	assert os.name == 'posix' # this function doesn't make sense outside of posix for now
	uid: int = os.getuid() # type: ignore
	return uid == 0

if sys.platform != 'win32':
	def drop_root( uid_name: str = 'nobody', gid_name: str = 'nogroup' ) -> None:
		if not is_root():
			return # we're already not root, nothing to do
		
		# Get the uid/gid from the name
		running_uid = pwd.getpwnam( uid_name ).pw_uid
		running_gid = grp.getgrnam( gid_name ).gr_gid
		
		# Remove group privileges
		os.setgroups( [] )
		
		# Try setting the new uid/gid
		os.setgid( running_gid )
		os.setuid( running_uid )
		
		# Ensure a very conservative umask
		_ = os.umask( 0o077 ) # returns old_umask
else:
	def drop_root( uid_name: str = 'nobody', gid_name: str = 'nogroup' ) -> None:
		pass

if sys.platform != 'win32':
	def chown( path: str, uid_name: str, gid_name: str ) -> None:
		uid = pwd.getpwnam( uid_name ).pw_uid
		gid = grp.getgrnam( gid_name ).gr_gid
		os.chown( path, uid, gid )
else:
	def chown( path: str, uid_name: str, gid_name: str ) -> None:
		pass

def os_execute( cmd: str ) -> None:
	log = logger.getChild( 'os_execute' )
	log.debug( cmd )
	os.system( cmd )

def walk_json_dicts( json_data: Any, callback: Callable[[Any],Opt[Any]] ) -> Opt[Any]:
	if isinstance( json_data, dict ):
		r = callback( json_data )
		if r is not None:
			return r
		for k, v in json_data.items():
			r = walk_json_dicts( v, callback )
			if r is not None:
				return r
	elif isinstance( json_data, list ):
		for v in json_data:
			r = walk_json_dicts( v, callback )
			if r is not None:
				return r
	return None

#endregion utilities
#region html helpers


def qry_int( name: str, default: int, *,
	min: Opt[int] = None,
	max: Opt[int] = None,
) -> int:
	try:
		q = int( request.args.get( name, '' ))
	except ValueError:
		q = default
	if min is not None and q < min:
		return min
	if max is not None and q > max:
		return max
	return q

def html_text( text: str ) -> str:
	return html.escape( text, quote = False )

def html_att( text: str ) -> str:
	return html.escape( text, quote = True )

def html_page( *lines: str, stylesheets: Opt[List[str]] = None, status_code: Opt[int] = None ) -> Response:
	
	settings = ace_settings.load()
	
	header = [
		'<!doctype html>',
		'<html>',
		'<head>',
		'<link rel="stylesheet" href="/ace.css">',
	]
	for stylesheet in stylesheets or ():
		header.append( f'<link rel="stylesheet" href="{stylesheet}">' )
	header.append( '</head><body>' )
	if current_user.is_authenticated:
		header.extend( [
			'<ul class="nav">',
			f'	<li><a href="{url_for("http_index")}">ACE</a></li>',
			f'	<li><a href="{url_for("http_dids")}">DIDs</a></li>',
			f'	<li><a href="{url_for("http_anis")}">ANIs</a></li>',
			f'	<li><a href="{url_for("http_flags")}">Flags</a></li>',
			f'	<li><a href="{url_for("http_routes")}">Routes</a></li>',
			f'	<li><a href="{url_for("http_voicemails")}">Voicemail</a></li>',
			f'	<li><a href="{url_for("http_settings")}">Settings</a></li>',
			f'	<li><a href="{url_for("http_cars")}">CAR</a></li>',
			f'	<li><a href="{url_for("http_audits")}">Audit</a></li>',
			f'	<li><a href="{url_for("http_logout")}">Log Out</a></li>',
			'</ul>',
		] )
	header.append( '<div id="content">' )
	footer = [ f'<br/><br/>{settings.motd}</div></body></html>' ]
	return Response(
		'\n'.join( header + list( lines ) + footer ),
		status_code or 200,
	)

def accept_type(
	accepted_types: List[str] = [ 'text/html', 'application/json' ],
) -> str:
	#log = logger.getChild( 'accept_type' )
	accept_header = request.headers.get( 'Accept' )
	return_type: str = accept_types.get_best_match( accept_header, accepted_types )
	assert isinstance( return_type, str ), f'invalid return_type={return_type!r}'
	#log.debug( 'accept_header=%r, accepted_types=%r, return_type=%r', accept_header, accepted_types, return_type )
	return return_type

class HttpFailure( Exception ):
	def __init__( self, error: str, status_code: int = 400 ) -> None:
		self.error = error
		self.status_code = status_code
	def __repr__( self ) -> str:
		cls = type( self )
		return f'{cls.__module__}.{cls.__name__}(error={self.error!r}, status_code={self.status_code!r})'

def rest_success( rows: Opt[List[Dict[str,Any]]] = None ) -> Response:
	return jsonify( success = True, rows = rows or [] )

def rest_failure( error: str, status_code: Opt[int] = None ) -> Response:
	r = jsonify( success = False, error = error )
	r.status_code = status_code or 400
	return r

def _http_failure( return_type: str, error: str, status_code: int = 400 ) -> Response:
	if return_type == 'application/json':
		return rest_failure( error, status_code )
	else:
		return html_page( html_text( error ), status_code = status_code )

def inputs() -> Dict[str,Any]:
	if request.content_type == 'application/json':
		return cast( Dict[str,Any], request.json )
	else:
		return request.form


#endregion html helpers
#region authentication


# NOTE: you can override this function in flask.cfg if you want to implement alternative auth method
if sys.platform != 'win32':
	def authenticate( usernm: str, secret: str ) -> bool:
		return bool( auth.authenticate( usernm, secret ))
else:
	def authenticate( usernm: str, secret: str ) -> bool:
		log = logger.getChild( 'authenticate' )
		log.critical(
			'NON-POSIX IMPLEMENTATION ONLY SUPPORTS A SINGLE HARD-CODED USER FOR NOW'
		)
		return usernm == 'setup' and secret == 'deleteme'


#endregion authentication
#region custom DID fields


class IntField( Field ):
	def __init__( self, field: str, label: str, *,
		tooltip: str = '',
		required: bool = False,
		min_length: Opt[int] = None,
		max_length: Opt[int] = None,
		min_value: Opt[int] = None,
		max_value: Opt[int] = None,
		placeholder: Opt[str] = None,
	) -> None:
		super().__init__( field, label,
			tooltip = tooltip,
			required = required,
			min_length = min_length,
			max_length = max_length,
			placeholder = placeholder,
		)
		self.min_value = min_value
		self.max_value = max_value
	
	def validate( self, rawvalue: Opt[str] ) -> Union[None,int,str]:
		rawvalue_ = super().validate( rawvalue )
		if rawvalue_ is None:
			return None
		try:
			value = int( rawvalue_ )
		except ValueError as e1:
			raise ValidationError( f'invalid {self.label}: {e1.args[0]!r}' ) from None
		if self.min_value is not None and value < self.min_value:
			raise ValidationError( f'{self.label} is too small, min value is {self.min_value!r}' )
		if self.max_value is not None and value > self.max_value:
			raise ValidationError( f'{self.label} is too large, max value is {self.max_value!r}' )
		return value

class StrField( Field ):
	pass


#endregion custom DID fields
#region flask config

etc_path.mkdir( mode = 0o770, parents = True, exist_ok = True )

cfg_path = etc_path / 'flask.cfg'
if not cfg_path.is_file():
	cfg_raw = '\n'.join( [
		f'ENV = {"production"!r}',
		f'DEBUG = {False!r}',
		f'TESTING = {False!r}',
		f'SECRET_KEY = {os.urandom(24)!r}',
		f'SESSION_TYPE = {"filesystem"!r}',
		f'SESSION_FILE_DIR = {"/var/cache/itas/ace/sessions"!r}',
		f'PERMANENT_SESSION_LIFETIME = {datetime.timedelta(minutes=5)!r}',
		f'ITAS_LISTEN_PORT = {443!r}',
		f'ITAS_CERTIFICATE_PEM = {str(etc_path/"certificate.pem")!r}',
		f'ITAS_AUTOBAN_BAD_EXPIRE_MINUTES = {0.5!r}',
		f'ITAS_AUTOBAN_BAD_COUNT_LOCKOUT = {10!r}',
		f'ITAS_AUTOBAN_DURATION_MINUTES = {10!r}',
		f'ITAS_AUDIT_DIR = {"/var/log/itas/ace/audit/"!r}',
		f'ITAS_AUDIT_FILE = {"%Y-%m-%d.log"!r}',
		f'ITAS_AUDIT_TIME = {"%Y-%m-%d %H:%M:%S.%f %Z%z"!r}',
		f'ITAS_OWNER_USER = {"www-data"!r}',
		f'ITAS_OWNER_GROUP = {"www-data"!r}',
		f'ITAS_FREESWITCH_JSON_CDR_PATH = {"/var/log/freeswitch/json_cdr"!r}',
		f'ITAS_REPOSITORY_TYPE = {"fs"!r}',
		f'ITAS_REPOSITORY_FS_PATH = {"/usr/share/itas/ace/"!r}',
		f'ITAS_REPOSITORY_SQLITE_PATH = {"/usr/share/itas/ace/ace.sqlite"!r}',
		f'ITAS_FLAGS_PATH = {str(default_data_path)!r}',
		f'ITAS_DID_FIELDS = {[]!r}',
		f'ITAS_DID_VARIABLES_EXAMPLES = {[]!r}',
		'ITAS_ANI_OVERRIDES_EXAMPLES = {!r}'.format([
			'# <<< anything after a # is a "comment" and is ignored',
			'8005551212 6999 # always send calls with this ANI and DID 8005551212 to route 6999',
			'8005551213 6999 1999-12-31 # send calls with this ANI and DID 8005551213 to route 6999 until Dec 31, 1999 12:00:00 AM',
			'8005551214 6999 1999-12-31 08:00:00 # send calls with this ANI and DID 8005551214 to route 6999 until Dec 31, 1999 8:00 AM (local time)',
		]),
		f'ITAS_VOICEMAIL_BOXES_PATH = {"/usr/share/itas/ace/boxes/"!r}',
		f'ITAS_VOICEMAIL_MSGS_PATH = {"/usr/share/itas/ace/msgs/"!r}',
		f'ITAS_SETTINGS_PATH = {"/etc/itas/ace/settings.json"!r}',
		f'ITAS_UI_LOGFILE = {"/var/log/itas/ace/logs/ui.log"!r}',
		f'ITAS_ENGINE_LOGFILE = {"/var/log/itas/ace/logs/engine.log"!r}',
		'ITAS_LOGLEVELS = {!r}'.format( {} ),
	] )
	with cfg_path.open( 'w' ) as f:
		print( cfg_raw, file = f )
else:
	with cfg_path.open( 'r' ) as f:
		cfg_raw = f.read()

# begin flask.cfg variables:
app = Flask( __name__ )
ENV: str = ''
DEBUG: bool = False
TESTING: bool = False
SECRET_KEY: bytes = b''
SESSION_TYPE: str = ''
SESSION_FILE_DIR: str = ''
PERMANENT_SESSION_LIFETIME: datetime.timedelta = datetime.timedelta( minutes = 5 )
ITAS_LISTEN_PORT: int = 443
ITAS_CERTIFICATE_PEM: str = ''
ITAS_AUTOBAN_BAD_EXPIRE_MINUTES: float = 0.5
ITAS_AUTOBAN_BAD_COUNT_LOCKOUT: int = 10
ITAS_AUTOBAN_DURATION_MINUTES: float = 10
ITAS_AUDIT_DIR: str = ''
ITAS_AUDIT_FILE: str = ''
ITAS_AUDIT_TIME: str = ''
ITAS_OWNER_USER: str = ''
ITAS_OWNER_GROUP: str = ''
ITAS_FREESWITCH_JSON_CDR_PATH: str = ''
ITAS_REPOSITORY_TYPE: str = ''
ITAS_REPOSITORY_FS_PATH: str = ''
ITAS_REPOSITORY_SQLITE_PATH: str = ''
ITAS_FLAGS_PATH: str = ''
ITAS_DID_FIELDS: List[Field] = []
ITAS_DID_VARIABLES_EXAMPLES: List[str] = []
ITAS_ANI_OVERRIDES_EXAMPLES: List[str] = []
ITAS_VOICEMAIL_BOXES_PATH: str
ITAS_VOICEMAIL_MSGS_PATH: str
ITAS_SETTINGS_PATH: str
ITAS_UI_LOGFILE: str = ''
ITAS_ENGINE_LOGFILE: str = ''
ITAS_LOGLEVELS: Dict[str,str] = {}
exec( cfg_raw + '\n' ) # this exec overrides the variables from flask.cfg
assert ITAS_AUDIT_DIR, f'flask.cfg missing ITAS_AUDIT_DIR'
assert ITAS_UI_LOGFILE, f'flask.cfg missing ITAS_UI_LOGFILE'
assert ITAS_ENGINE_LOGFILE, f'flask.cfg missing ITAS_ENGINE_LOGFILE'
# end of flask.cfg variables

app.config.from_object( __name__ )
app.config['APP_NAME'] = 'Automated Call Experience (ACE)'


#endregion flask config
#region autoban


class AutoBan:
	def __init__( self ) -> None:
		self._lock = RLock()
		self._fails: Dict[str,List[datetime.datetime]] = {}
		self._bans: Dict[str,datetime.datetime] = {}
	
	def try_auth( self, usernm: str, secret: str ) -> bool:
		log = logger.getChild( 'AutoBan.try_auth' )
		auth = authenticate( usernm, secret )
		with self._lock:
			ip = request.remote_addr
			now = datetime.datetime.now()
			
			if ip is None:
				log.debug( 'user %r has ip=%r', usernm, ip )
				return False
			
			# check if user is already locked out:
			try:
				until = self._bans[ip]
			except KeyError:
				pass
			else:
				if until <= now:
					del self._bans[ip]
				else:
					log.debug( 'user %r is locked out until %r', usernm, str( until ))
					return False
			
			# check for auth success:
			if auth:
				self._fails.pop( ip, None ) # successful login - reset failure count
				return True
			
			# update fail count and check if user needs to be locked out:
			ar = self._fails.get( ip, [] )
			while ar and ar[0] <= now:
				ar = ar[1:] # remove expired bad pw attempts
			ar.append( now + datetime.timedelta( minutes = ITAS_AUTOBAN_BAD_EXPIRE_MINUTES ))
			if len( ar ) >= ITAS_AUTOBAN_BAD_COUNT_LOCKOUT:
				until = now + datetime.timedelta( minutes = ITAS_AUTOBAN_DURATION_MINUTES )
				self._bans[ip] = until
				self._fails.pop( ip, None )
				log.debug( 'user %r banned until %r', usernm, str( until ))
			else:
				self._fails[ip] = ar
				log.debug( 'user %r fail count=%r', usernm, len( ar ))
			return False
autoban = AutoBan()


#endregion autoban
#region paths and auditing


auditing.init(
	path = Path( ITAS_AUDIT_DIR ),
	file = ITAS_AUDIT_FILE,
	time_format = ITAS_AUDIT_TIME,
)

if __name__ == '__main__' and SESSION_TYPE == 'filesystem':
	session_path = Path( SESSION_FILE_DIR )
	session_path.mkdir( mode = 0o770, parents = True, exist_ok = True )
	if os.name == 'posix':
		chown( str( session_path ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
		os.chmod( SESSION_FILE_DIR, 0o770 )

r_valid_audit_filename = re.compile( r'^[a-zA-Z0-9_\.-]+$', re.I )
def valid_audit_filename( filename: str ) -> bool:
	return bool( r_valid_audit_filename.match( filename ))

flags_path = Path( ITAS_FLAGS_PATH )
flags_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( flags_path ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
os.chmod( str( flags_path ), 0o775 )
def flag_file_path( flag: str ) -> Path:
	return flags_path / f'{flag}.flag'

# TODO FIXME: replace this with REPO_DIDS...
DIDS = 'dids'
dids_path = Path( ITAS_REPOSITORY_FS_PATH ) / DIDS
dids_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( dids_path ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
os.chmod( str( dids_path ), 0o775 )
def did_file_path( did: int ) -> Path:
	return dids_path / f'{did}.did'

# TODO FIXME: replace this with REPO_ANIS...
ANIS = 'anis'
anis_path = Path( ITAS_REPOSITORY_FS_PATH ) / ANIS
anis_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( anis_path ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
os.chmod( str( anis_path ), 0o775 )
def ani_file_path( ani: int ) -> Path:
	return anis_path / f'{ani}.ani'

voicemail_meta_path = PurePosixPath( ITAS_VOICEMAIL_BOXES_PATH )
Path( voicemail_meta_path ).mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( voicemail_meta_path ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
os.chmod( str( anis_path ), 0o775 )
def voicemail_settings_path( box: Union[int,str] ) -> PurePosixPath:
	return voicemail_meta_path / f'{box}.box'
def voicemail_greeting_path( box: int, greeting: int ) -> PurePosixPath:
	return voicemail_meta_path / f'{box}' / f'greeting{greeting}.wav'

voicemail_msgs_path = PurePosixPath( ITAS_VOICEMAIL_MSGS_PATH )
Path( voicemail_msgs_path ).mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( voicemail_msgs_path ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
os.chmod( str( anis_path ), 0o775 )
def voicemail_box_msgs_path( box: int ) -> PurePosixPath:
	return voicemail_msgs_path / str( box )


#endregion paths and auditing
#region repo config

repo_config = repo.Config(
	fs_path = Path( ITAS_REPOSITORY_FS_PATH ),
	sqlite_path = Path( ITAS_REPOSITORY_SQLITE_PATH ),
)

REPO_FACTORY: Type[repo.Repository]

# Setup repositories based on config
if ITAS_REPOSITORY_TYPE == 'sqlite':
	REPO_FACTORY = repo.RepoSqlite
elif ITAS_REPOSITORY_TYPE == 'fs':
	REPO_FACTORY = repo.RepoFs
else:
	raise Exception( f'invalid ITAS_REPOSITORY_TYPE={ITAS_REPOSITORY_TYPE!r}' )

REPO_FACTORY_NOFS: Type[repo.Repository] = REPO_FACTORY
if REPO_FACTORY == repo.RepoFs:
	REPO_FACTORY_NOFS = repo.RepoSqlite

REPO_DIDS = REPO_FACTORY( repo_config, DIDS, '.did', [
	#repo.SqlInteger( 'id', null = False, size = 10, auto = True, primary = True ),
	#repo.SqlText( 'name', null = True ),
])

REPO_ANIS = REPO_FACTORY( repo_config, ANIS, '.ani', [] )

REPO_ROUTES = REPO_FACTORY( repo_config, 'routes', '.route', [
	repo.SqlInteger( 'id', null = False, size = 10, auto = True, primary = True ),
	repo.SqlText( 'name', null = True ),
	repo.SqlJson( 'json', null = False ),
])

REPO_BOXES = REPO_FACTORY( repo_config, 'boxes', '.box', [] )

REPO_JSON_CDR = REPO_FACTORY_NOFS( repo_config, 'cdr', '.cdr', [
	repo.SqlInteger( 'id', null = False, size = 16, auto = True, primary = True ),
	repo.SqlVarChar( 'call_uuid', size = 36, null = False ),
	repo.SqlDateTime( 'start_stamp', null = False ),
	repo.SqlDateTime( 'answered_stamp', null = True ),
	repo.SqlDateTime( 'end_stamp', null = False ),
	repo.SqlJson( 'json', null = False ),
], auditing = False )

# CAR = Caller Activity Report
REPO_CAR = REPO_FACTORY_NOFS( repo_config, 'car', '.car', [
	# NOTE: keep this in sync with ace_car.CAR
	repo.SqlVarChar( 'id', size = 36, null = False, primary = True ), # call's uuid
	repo.SqlVarChar( 'did', size = DID_MAX_LENGTH, null = False ),
	repo.SqlVarChar( 'ani', size = ANI_MAX_LENGTH, null = False ),
	repo.SqlVarChar( 'cpn', size = CPN_MAX_LENGTH, null = False ),
	repo.SqlVarChar( 'acct_num', size = ACCT_NUM_MAX_LENGTH, null = True ),
	repo.SqlVarChar( 'acct_name', size = ACCT_NAME_MAX_LENGTH, null = True ),
	repo.SqlFloat( 'start', null = False ),
	repo.SqlFloat( 'end', null = True ),
	repo.SqlJson( 'activity',  null = False ),
], auditing = False )

#endregion repo config
#region session management


Session( app )


class User( UserMixin ): # type: ignore
	def __init__( self, name: str ) -> None:
		self.name = name
		self.id = str( uuid.uuid4() )
		self.active = True
	
	def __repr__( self ) -> str:
		cls = type( self )
		return f'{cls.__module__}.{cls.__qualname__}(name={self.name!r}, id={self.id!r})' # TODO FIXME: id is not a parameter to __init__
	
	def __str__( self ) -> str:
		return repr( self )


class Anonymous( AnonymousUserMixin ): # type: ignore
	name = 'Anonymous'


login_manager = LoginManager()
login_manager.login_view = 'http_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.refresh_view = 'http_reauth'

@login_manager.user_loader # type: ignore
def load_user( user_id: str ) -> UserMixin:
	#log = logger.getChild( 'load_user' )
	user = session.get( SESSION_USERDATA, None )
	#log.debug( 'user_id %r -> %r', user_id, user )
	return user

login_manager.setup_app( app )

def try_login( usernm: str, secret: str, remember: bool = False ) -> bool:
	log = logger.getChild( 'try_login' )
	log.debug( 'trying usernm=%r', usernm )
	if usernm and secret and autoban.try_auth( usernm, secret ):
		log.debug( 'usernm %r auth success', usernm )
		user = User( usernm )
		session[SESSION_USERDATA] = user
		if login_user( user, remember = remember ):
			log.debug( 'usernm %r logged in', usernm )
			session.permanent = True
			return True
	return False

def try_logout() -> None:
	try:
		del session[SESSION_USERDATA]
	except KeyError:
		pass
	logout_user()


#endregion session management
#region http - login


@app.route( '/login', methods = [ 'GET', 'POST' ] )
def http_login() -> Response:
	log = logger.getChild( 'http_login' )
	return_type = accept_type()
	usernm: str = ''
	errmsg = ''
	
	if request.method == 'POST':
		inp = inputs()
		usernm = inp.get( 'usernm', '' )
		secret = inp.get( 'secret', '' )
		remember_ = inp.get( 'remember', 'no' )
		if remember_ not in ( 'yes', 'no' ):
			return _http_failure(
				return_type,
				'"remember" must be "yes" or "no"',
				400,
			)
		remember =( remember_ == 'yes' )
		if try_login( usernm, secret, remember ):
			if return_type == 'application/json':
				return rest_success( [] )
			next_url = request.args.get( 'next' )
			if next_url and is_safe_url( next_url ):
				return redirect( next_url )
			return redirect( url_for( 'http_index' ))
		else:
			log.warning( 'username %r auth failure', usernm )
			errmsg = 'Invalid credentials'
			if return_type == 'application/json':
				logout_user()
				return rest_failure( errmsg )
	
	logout_user()
	
	return html_page(
		'<center>',
		f'<p>{app.config["APP_NAME"]} Portal Login</p>',
		'<p>',
		'	<form method="POST">',
		'		User Name:<br/>',
		f'		<input type="text" name="usernm" value="{html_att(usernm)}" autofocus/><br/>',
		'		<br/>',
		'		Secret:<br/>',
		'		<input type="password" name="secret"/><br/>',
		'		<br/>',
		'		<input type="submit" value="Login"/>',
		'	</form>',
		'</p>',
		f'<font color=red>{errmsg}</font>',
		'</center>',
	)

@app.route( '/reauth', methods = [ 'GET', 'POST' ] )
@login_required # type: ignore
def http_reauth() -> Response:
	log = logger.getChild( 'http_reauth' )
	if request.method == 'POST':
		confirm_login()
		return redirect( url_for( 'http_index' ))
	log.warning( 'ToDO FiXME: need to generate reauth html content' )
	return html_page(
		'ToDO FiXME: reauth html content goes here',
	)

@app.route( '/logout' )
def http_logout() -> Response:
	log = logger.getChild( 'http_logout' )
	log.debug( 'logging out current user' )
	return_type = accept_type()
	try_logout()
	if return_type == 'application/json':
		return rest_success( [] )
	return redirect( url_for( 'http_index' ))


#endregion http - login
#region http - misc

@app.route( '/<path:filepath>' )
def http_send_from_directory( filepath: str ) -> Response:
	mimetype = mimetypes.guess_type( filepath )[0]
	if not mimetype:
		mimetype = 'text/plain'
	return send_from_directory(
		'www',
		filepath,
		mimetype = mimetype,
		max_age = 30 * 60,
	)

@app.route( '/' )
@login_required # type: ignore
def http_index() -> Response:
	#log = logger.getChild( 'http_index' )
	#return_type = accept_type()
	
	settings = ace_settings.load()
	
	return html_page(
		'TODO FIXME',
	)


r_callie = re.compile( r'[/\\]callie[/\\]([^/\\]+)[/\\]8000[/\\](.*)$' )
def _iter_sounds( sounds: Path ) -> Iterator[str]:
	for path2 in sounds.iterdir():
		if path2.stem == 'music':
			continue
		for folder, _, files in os.walk( str( path2 )):
			path3 = Path( folder )
			if path3.stem not in ( '16000', '32000', '48000' ):
				for file in files:
					path = str( Path( folder ) / file )
					# callie sounds can be specifically simplified for freeswitch:
					m = r_callie.search( path )
					if m:
						yield f'{m.group(1)}/{m.group(2)}' # <<< FS can handle forward slashes on windows
					else:
						yield path

@app.route( '/sounds/' )
@login_required # type: ignore
def http_sounds() -> Response:
	return_type = accept_type()
	sounds: List[Dict[str,str]] = []
	settings = ace_settings.load()
	for path in map( Path, settings.freeswitch_sounds ):
		sounds.extend( [
			{ 'sound': sound }
			for sound in _iter_sounds( path )
		] )
	sounds.sort( key = lambda d: d['sound'] )
	rsp = rest_success( sounds )
	rsp.cache_control.public = True
	rsp.cache_control.max_age = 30
	return rsp

#endregion http - misc
#region http - DID

def valid_destination( dest: str ) -> bool:
	if dest.startswith( 'V' ):
		dest = dest[1:]
	return dest.isnumeric()

@app.route( '/dids/', methods = [ 'GET' ] )
@login_required # type: ignore
def http_dids() -> Response:
	log = logger.getChild( 'http_dids' )
	return_type = accept_type()
	
	q_limit = qry_int( 'limit', 20, min = 1, max = 1000 )
	q_offset = qry_int( 'offset', 0, min = 0 )
	
	q_did = request.args.get( 'did', '' ).strip()
	q_tf = request.args.get( 'tf', '' ).strip()
	q_acct = request.args.get( 'acct', '' ).strip()
	q_name = request.args.get( 'name', '' ).strip()
	q_route = request.args.get( 'route', '' ).strip()
	q_notes = request.args.get( 'notes', '' ).strip()
	
	dids: List[Dict[str,Any]] = []
	pattern = f'*{q_did}*.did' if q_did else '*.did'
	files = list( dids_path.glob( pattern ))
	files.sort ( key = lambda file: file.stem )
	skipped = 0
	datadefs: Dict[str,Any] = {
		'acct': '',
		'name': '',
	}
	for file in files:
		data: Dict[str,Any] = {}
		if q_tf or q_acct or q_name or q_route or q_notes:
			with file.open( 'r' ) as f:
				try:
					data = cast( Dict[str,Any], json.loads( f.read() ))
				except Exception as e:
					log.error( f'error parsing json of {str(file)!r}: {e!r}' )
					continue
			if q_tf and q_tf not in data.get( 'tollfree', '' ):
				#log.debug( f'rejecting {str(file)!r} b/c {q_tf!r} not in {data.get("tollfree","")!r}' )
				continue
			if q_acct and q_acct not in str( data.get( 'acct', '' )):
				#log.debug( f'rejecting {str(file)!r} b/c {q_acct!r} not in {data.get("acct","")!r}' )
				continue
			if q_name and q_name not in data.get( 'name', '' ):
				#log.debug( f'rejecting {str(file)!r} b/c {q_name!r} not in {data.get("name","")!r}' )
				continue
			if q_route and q_route not in str( data.get( 'route', '' )):
				#log.debug( f'rejecting {str(file)!r} b/c {q_route!r} not in {data.get("route","")!r}' )
				continue
			if q_notes and q_notes not in data.get( 'notes', '' ):
				#log.debug( f'rejecting {str(file)!r} b/c {q_notes!r} not in {data.get("notes","")!r}' )
				continue
		if skipped < q_offset:
			skipped += 1
			continue
		did2 = int( file.stem )
		if not data:
			with file.open( 'r' ) as f:
				try:
					data = cast( Dict[str,Any], json.loads( f.read() ))
				except Exception as e:
					log.error( f'error parsing json of {str(file)!r}: {e!r}' )
					continue
		data['did'] = did2
		dids.append({ **datadefs, **data })
		if len( dids ) >= q_limit:
			break
	if return_type == 'application/json':
		return rest_success( dids )
	row_html = (
		'<tr>'
		'<td><a href="/dids/{did}">{did}</a></td>'
		'<td><a href="/dids/{did}">{acct}</a></td>'
		'<td><a href="/dids/{did}">{name}</a></td>'
		'</tr>'
	)
	body = '\n'.join( [
		row_html.format( **d ) for d in dids
	] )
	
	did_tip = 'Performs substring search of all DIDs'
	tf_tip = 'Performs substring search of all TF #s'
	acct_tip = 'Performs substring search of all Account #s'
	name_tip = 'Performs substring search of all Account Names'
	route_tip = 'Performs substring search of all Routes'
	notes_tip = 'Performs substring search of all Notes'
	
	prevpage = urlencode( { 'did': q_did, 'tf': q_tf, 'acct': q_acct, 'name': q_name, 'route': q_route, 'notes': q_notes, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit ) } )
	nextpage = urlencode( { 'did': q_did, 'tf': q_tf, 'acct': q_acct, 'name': q_name, 'route': q_route, 'notes': q_notes, 'limit': q_limit, 'offset': q_offset + q_limit } )
	return html_page(
		'<table width="100%"><tr>',
		'<td align="center">',
		'<a href="/dids/0">(Create new DID)</a>',
		'</td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span tooltip="{html_att(did_tip)}"><input type="text" name="did" placeholder="DID" value="{html_att(q_did)}" maxlength="10" size="10" /></span>',
		f'<span tooltip="{html_att(tf_tip)}"><input type="text" name="tf" placeholder="TF#" value="{html_att(q_tf)}" maxlength="10" size="10" /></span>',
		f'<span tooltip="{html_att(acct_tip)}"><input type="text" name="acct" placeholder="Acct#" value="{html_att(q_acct)}" maxlength="4" size="4" /></span>',
		f'<span tooltip="{html_att(name_tip)}"><input type="text" name="name" placeholder="Name" value="{html_att(q_name)}" size="10" /></span>',
		f'<span tooltip="{html_att(route_tip)}"><input type="text" name="route" placeholder="Route" value="{html_att(q_route)}" size="4" /></span>',
		f'<span tooltip="{html_att(notes_tip)}"><input type="text" name="notes" placeholder="Notes" value="{html_att(q_notes)}" size="10" /></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{prevpage}">&lt;&lt;</a>&nbsp;&nbsp;<a href="?{nextpage}">&gt;&gt;</a></td>',
		'</tr></table>',
		
		'<table class="fancy dids_list">',
		'	<tr><th>DID</th><th>Acct#</th><th>Acct Name</th></tr>',
			body,
		'</table>',
	)

def try_post_did( did: int, data: Dict[str,str] ) -> int:
	try:
		did2 = did or int( data.get( 'did' ) or '' )
	except Exception as e1:
		raise ValidationError( f'invalid DID: {e1!r}' ) from None
	if len( str( did2 )) != 10:
		raise ValidationError( 'invalid DID: must be 10 digits exactly' )
	
	data2: Dict[str,Union[int,str]] = {}
	
	try:
		tollfree = data.get( 'tollfree', '' )
	except Exception as e0:
		raise ValidationError( f'invalid Toll Free #: {e0!r}' ) from None
	if tollfree:
		data2['tollfree'] = tollfree
	
	try:
		category = data.get( 'category', '' )
	except Exception as e4:
		raise ValidationError( f'invalid Category: {e4!r}' ) from None
	if category:
		data2['category'] = category
	
	try:
		did_flag = data.get( 'did_flag', '' )
	except Exception as e6:
		raise ValidationError( f'invalid DID Flag: {e6!r}' ) from None
	if did_flag:
		data2['did_flag'] = did_flag
	
	try:
		acct_ = data.get( 'acct', '' )
		acct: Opt[int] = int( acct_ ) if acct_ else None
	except Exception as e2:
		raise ValidationError( f'invalid Account #: {e2!r}' ) from None
	if acct is not None and not ( 1 <= acct <= 9999 ):
		raise ValidationError( 'Account # must be between 1-9999' )
	if acct is not None:
		data2['acct'] = acct
	
	try:
		name = data.get( 'name', '' )
	except Exception as e3:
		raise ValidationError( f'invalid Client Name: {e3!r}' ) from None
	if name:
		data2['name'] = name
	
	try:
		acct_flag = data.get( 'acct_flag', '' )
	except Exception as e6:
		raise ValidationError( f'invalid Acct Flag: {e6!r}' ) from None
	if acct_flag:
		data2['acct_flag'] = acct_flag
	
	route = data.get( 'route' ) or ''
	if not valid_destination( route ):
		raise ValidationError( f'invalid Destination: {route!r}' )
	data2['route'] = route
	
	for field in ITAS_DID_FIELDS:
		rawvalue: Opt[str] = data.get( field.field, '' ) or None
		value = field.validate( rawvalue )
		if value is not None and value != '':
			data2[field.field] = value

	try:
		variables = data.get( 'variables', '' )
	except Exception as e7:
		raise ValidationError( f'invalid Variables: {e7!r}' ) from None
	if variables:
		data2['variables'] = variables
	
	try:
		notes = data.get( 'notes', '' )
	except Exception as e8:
		raise ValidationError( f'invalid Notes: {e8!r}' ) from None
	if notes:
		data2['notes'] = notes
	
	path = did_file_path( did2 )
	with path.open( 'r' ) as f:
		olddata = json.loads( f.read() )
	keys = set( olddata.keys() ) | set( data2.keys() )
	auditdata_: List[str] = []
	for key in sorted( keys ):
		oldval = coalesce( olddata.get( key ), '' )
		newval = coalesce( data2.get( key ), '' )
		if oldval != newval:
			auditdata_.append( f'\t{key}: {oldval!r} -> {newval!r}' )
		else:
			auditdata_.append( f'\t{key}: {oldval!r} (unchanged)' )
	auditdata = '\n'.join( auditdata_ )
	
	audit = new_audit()
	
	glue = ':\n' if auditdata else ''
	if did:
		audit.audit( f'Changed DID {did} at {str(path)!r}{glue}{auditdata}' )
	else:
		if path.exists():
			raise ValidationError( f'DID already exists: {did2}' )
		audit.audit( f'Created DID {did2} at {str(path)!r}{glue}{auditdata}' )
	with path.open( 'w' ) as f:
		print( repo.json_dumps( data2 ), file = f )
	
	return did2

@app.route( '/dids/<int:did>', methods = [ 'GET', 'POST', 'DELETE' ] )
@login_required # type: ignore
def http_did( did: int ) -> Response:
	log = logger.getChild( 'http_did' )
	return_type = accept_type()
	path = did_file_path( did )
	audit = new_audit()
	
	if request.method == 'DELETE':
		if not path.is_file():
			return _http_failure( return_type, 'DID not found', 404 )
		try:
			path.unlink()
		except Exception as e1:
			return _http_failure( return_type, repr( e1 ), 500 )
		else:
			audit.audit( f'Deleted DID {did} at {str(path)!r}' )
			if return_type == 'application/json':
				return rest_success( [] )
			return redirect( '/dids/' )
	
	err: str = ''
	if request.method == 'POST':
		data = inputs()
		try:
			did2 = try_post_did( did, data )
		except ValidationError as e2:
			err = e2.args[0]
		except Exception as e3:
			log.exception( 'Unexpected error posting DID:' )
			err = repr ( e3 )
		else:
			if return_type == 'application/json':
				return rest_success( [] )
			return redirect ( f'/dids/{did2}' )
		if return_type == 'application/json':
			return rest_failure( err )
	else:
		if did:
			try:
				with path.open() as f:
					data = json.loads( f.read() )
			except Exception as e4:
				return _http_failure( return_type, repr( e4 ), 500 )
			if return_type == 'application/json':
				return rest_success( [ data ] )
		else:
			data = request.args
	
	tollfree: str = data.get( 'tollfree' ) or ''
	category: str = data.get( 'category' ) or ''
	acct: str = data.get( 'acct' ) or ''
	name: str = data.get( 'name' ) or ''
	acct_flag = data.get( 'acct_flag', '' )
	route_: str = str( data.get( 'route' ) or '' ).strip()
	if route_:
		if route_.startswith( 'V' ):
			try:
				_ = int( route_[1:] )
			except ValueError as e:
				return _http_failure(
					return_type,
					f'Bad route: {e!r}',
					400,
				)
		else:
			try:
				route = to_optional_int( route_ )
			except ValueError as e:
				return _http_failure(
					return_type,
					f'Bad route: {e!r}',
					400,
				)
	variables = data.get( 'variables', '' )
	did_flag = data.get( 'did_flag', '' )
	notes = data.get( 'notes', '' )
	
	html_rows = [
		'<form method="POST" enctype="application/x-www-form-urlencoded">',
	]
	if not did:
		did_html = f'<input type="text" name="did" value="{html_att(data.get("did",""))}" size="{DID_MAX_LENGTH+1!r}" maxlength="{DID_MAX_LENGTH!r}"/>'
	else:
		did_html = html_text( str( did ))
	
	settings = ace_settings.load()
	
	category_options: List[str] = [ '<option value="">(None)</option>' ]
	for cat in settings.did_categories:
		att = ' selected' if category == cat else ''
		category_options.append( f'<option{att}>{cat}</option>' )
	
	try:
		routes = REPO_ROUTES.list()
	except Exception as e:
		#raise e
		return _http_failure(
			return_type,
			f'Error querying routes list: {e!r}',
			500,
		)
	
	try:
		boxes = REPO_BOXES.list()
	except Exception as e:
		return _http_failure(
			return_type,
			f'Error querying voicemail box list: {e!r}',
			500,
		)
	
	route_options: List[str] = []
	found = False
	for r, routedata in routes:
		att = ''
		if route_ == str( r ):
			att = ' selected'
			found = True
		lbl = routedata.get( 'name' ) or '(Unnamed)'
		route_options.append( f'<option value="{r}"{att}>Route {r} {lbl}</option>' )
	for box, boxdata in boxes:
		att = ''
		key = f'V{box}'
		if route_ == key:
			att = ' selected'
			found = True
		lbl = boxdata.get( 'name' ) or '(Unnamed)'
		route_options.append( f'<option value="{key}"{att}>VM {box} {lbl}</option>' )
	if not found and route_:
		if route_.startswith( 'V' ):
			route_options.insert( 0, f'<option value="{route_}" selected>Voicemail {route_} DOES NOT EXIST</option>' )
		else:
			route_options.insert( 0, f'<option value="{route_}" selected>Route {route_} DOES NOT EXIST</option>' )
	
	category_tip = 'All DIDs assigned to the same category will look for a preannounce of "category_{category_name}_{category_flag}.wav"'
	acct_flag_tip = 'Causes preannounce calculation to look for "{Acct}_{acct_flag}.wav"'
	did_flag_tip = 'Causes preannounce calculation to look for "{DID}_{did_flag}.wav"'
	
	html_rows.extend( [
		
		'<table class="unpadded"><tr><td valign="top">',
		f'<b>DID:</b><br/>{did_html}',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Toll Free #:</b><br/><input type="text" name="tollfree" value="{html_att(str(tollfree))}" size="15" maxlength="15"/><br/><br/>',
		'</td><td>&nbsp;</td><td valign="top">',
		'<b>Category:</b><br/>',
		f'<span tooltip="{html_att(category_tip)}"><select name="category">{"".join(category_options)}</select></span>',
		'</td></tr></table>',
		
		'<table class="unpadded"><tr><td valign="top">',
		f'<b>Account #:</b><br/><input type="text" name="acct" value="{html_att(str(acct))}" size="{ACCT_NUM_MAX_LENGTH+1!r}" maxlength="{ACCT_NUM_MAX_LENGTH!r}"/><br/><br/>',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Client Name:</b><br/><input type="text" name="name" value="{html_att(name)}" size="{ACCT_NAME_MAX_LENGTH+1!r}" maxlength="{ACCT_NAME_MAX_LENGTH!r}"/><br/><br/>',
		'</td><td>&nbsp;</td><td valign="top">',
		'<b>Acct Flag:</b><br/>',
		f'<span tooltip="{html_att(acct_flag_tip)}"><input type="text" name="acct_flag" value="{html_att(str(acct_flag))}" size="31" maxlength="30"/></span>',
		'</td></tr></table>',
		
		'<table class="unpadded"><tr><td valign="top">',
		f'<b>Destination:</b><br/><select name="route">{"".join(route_options)}</select>',
		'</td><td>&nbsp;</td><td valign="top">',
		'<b>DID Flag:</b><br/>',
		f'<span tooltip="{html_att(did_flag_tip)}"><input type="text" name="did_flag" value="{html_att(str(did_flag))}" size="31" maxlength="30"/></span>',
		'</td></tr></table>',
		'<br/>',
	])
	
	for field in ITAS_DID_FIELDS:
		x = f'<b>{field.label}</b><br/>'
		if field.tooltip:
			x += f'<span tooltip="{html_att(field.tooltip)}">'
		atts = ''
		if field.max_length:
			atts += f' size="{field.max_length+1!r}" maxlength="{field.max_length!r}"'
		if field.placeholder:
			atts += f' placeholder="{html_att(field.placeholder)}"'
		value: Union[None,int,str] = data.get( field.field, None )
		value = str( value ) if value is not None else ''
		x += f'<input type="text" name="{field.field}" value="{html_att(value)}"{atts}/>'
		if field.tooltip:
			x += '</span>'
		x += '<br/><br/>'
		html_rows.append( x )
	
	variables_examples = '\n'.join( ITAS_DID_VARIABLES_EXAMPLES )
	
	html_rows.extend([
		'<table class="unpadded"><tr><td valign="top">',
		'<b>Variables:</b><br/>',
		f'<textarea name="variables" cols="40" rows="4">{html_text(variables)}</textarea><br/><br/>',
		'</td><td>&nbsp;&nbsp;&nbsp;</td><td valign="top">',
		f'<b>Examples:</b><pre class="no_top_margin">{html_text(variables_examples)}</pre>',
		'</td></tr></table>',
		
		f'<b>Notes:</b><br/><textarea name="notes" cols="80" rows="4">{html_text(str(notes))}</textarea><br/><br/>',
	])
	if did:
		mtime = datetime.datetime.fromtimestamp( path.stat().st_mtime ).strftime( '%Y-%m-%d %I:%M:%S %p' )
		html_rows.append( f'Last Modified: {html_text(mtime)}<br/><br/>' )
	submit = 'Save' if did else 'Create'
	cloneparams = urlencode( data )
	cloneaction = f"window.location='/dids/0?{cloneparams}'"
	html_rows.extend([
		f'<input type="submit" value="{html_att(submit)}"/>',
		'&nbsp;&nbsp;&nbsp;',
		f'<button onclick="{cloneaction}" type="button" class="clone">Clone</button>' if did else '',
		'&nbsp;&nbsp;&nbsp;',
		'<button id="delete" class="delete">Delete</button>' if did else '',
		'<br/><br/>',
		f'<font color="red">{err}</font>',
		'<script src="/did.js"></script>',
		'</form>',
	])
	return html_page( *html_rows )


#endregion http - DID
#region http - ANI


@app.route( '/anis/', methods = [ 'GET', 'POST' ] )
@login_required # type: ignore
def http_anis() -> Response:
	#log = logger.getChild( 'http_anis' )
	return_type = accept_type()
	
	q_limit = qry_int( 'limit', 20, min = 1, max = 1000 )
	q_offset = qry_int( 'offset', 0, min = 0 )
	
	search = request.args.get( 'search', '' )
	anis: List[Dict[str,int]] = []
	pattern = f'*{search}*.ani' if search else '*.ani'
	for f in anis_path.glob( pattern ):
		anis.append( { 'ani': int( f.stem ) } )
	anis.sort ( key = lambda d: d['ani'] )
	anis = anis[q_offset:q_offset + q_limit]
	if return_type == 'application/json':
		return rest_success( anis )
	row_html = (
		'<tr>'
		'<td><a href="/anis/{ani}">{ani}</a></td>'
		'</tr>'
	)
	body = '\n'.join( [
		row_html.format( **d ) for d in anis
	] )
	
	search_tip = 'Performs substring search of all ANIs'
	
	prevpage = urlencode( { 'search': search, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit ) } )
	nextpage = urlencode( { 'search': search, 'limit': q_limit, 'offset': q_offset + q_limit } )
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Prev Page</a></td>',
		'<td align="center">',
		'<a href="/anis/0">(Create new ANI)</a>',
		'</td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span tooltip="{html_att(search_tip)}"><input type="text" name="search" placeholder="ANI" value="{html_att(search)}"/></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{nextpage}">Next Page</a></td>',
		'</tr></table>',
		
		'<table class="fancy anis_list">',
			body,
		'</table>',
	)

def try_post_ani( ani: int, data: Dict[str,str] ) -> int:
	try:
		ani2 = ani or int( data.get( 'ani' ) or '' )
	except Exception as e1:
		raise ValidationError( f'invalid ANI: {e1!r}' ) from None
	if len( str( ani2 )) != 10:
		raise ValidationError( 'invalid ANI: must be 10 digits exactly' )
	
	data2: Dict[str,Union[int,str]] = {}
	
	try:
		route_ = data.get( 'route', '' )
		route: Opt[int] = int( route_ ) if route_ else None
	except Exception as e4:
		raise ValidationError( f'invalid Route: {e4!r}' ) from None
	if route is not None and route <= 0:
		raise ValidationError( 'route must be an integer > 0' )
	if route is not None:
		data2['route'] = route
	
	found_override = False
	try:
		overrides = data.get( 'overrides', '' )
	except Exception as e5:
		raise ValidationError( f'invalid DID Overrides: {e5!r}' ) from None
	for lineno, line in enumerate( overrides.split ( '\n' ), start = 1 ):
		line, _, comment = line.partition( '#' )
		line = line.strip()
		if not line:
			continue
		args = re.split( r'\s+', line )
		
		found_override = True
		
		try:
			did_ = args.pop( 0 )
		except IndexError: # this shouldn't be possible because we skip blank lines above
			raise ValidationError( f'DID Overrides line {lineno} invalid: missing DID' ) from None
		if len( did_ ) != 10:
			raise ValidationError( f'DID Overrides line {lineno} invalid: DID must be 10 digits exactly' )
		try:
			_ = int( did_ )
		except ValueError:
			raise ValidationError( f'DID Overrides line {lineno} invalid: DID must be numeric' ) from None
		
		try:
			route = int( args.pop( 0 ))
		except IndexError:
			raise ValidationError( f'DID Overrides line {lineno} invalid: Route is required' ) from None
		except ValueError:
			raise ValidationError( f'DID Overrides line {lineno} invalid: Route must be numeric' ) from None
		
		if not REPO_ROUTES.exists( route ):
			raise ValidationError( f'DID Overrides line {lineno} invalid: Route {route!r} does not exist' )
		
		try:
			exp_date = args.pop( 0 )
		except IndexError:
			pass # exp_date is optional
		else:
			if not re.match( '^\d{4}-\d{2}-\d{2}$', exp_date ):
				raise ValidationError( f'DID Overrides line {lineno} invalid: Expiration date must be formatted as YYYY-MM-DD' )
		
		try:
			exp_time = args.pop( 0 )
		except IndexError:
			pass # exp_time is optional
		else:
			if not re.match( '^\d{2}:\d{2}:\d{2}$', exp_time ):
				raise ValidationError( f'DID Overrides line {lineno} invalid: Expiration time must be formatted as HH:MM:SS' )
		
		if args:
			raise ValidationError( f'DID Overrides line {lineno} invalid: only comments allowed after Expiration' )
	if overrides:
		data2['overrides'] = overrides
	
	if route is None and not found_override:
		raise ValidationError( 'Must set a Route or at least one DID Override' )
	
	try:
		notes = data.get( 'notes', '' )
	except Exception as e7:
		raise ValidationError( f'invalid Notes: {e7!r}' ) from None
	if notes:
		data2['notes'] = notes
	
	path = ani_file_path( ani2 )
	with path.open( 'r' ) as f:
		olddata = json.loads( f.read() )
	keys = set( olddata.keys() ) | set( data2.keys() )
	auditdata_: List[str] = []
	for key in sorted( keys ):
		oldval = coalesce( olddata.get( key ), '' )
		newval = coalesce( data2.get( key ), '' )
		if oldval != newval:
			auditdata_.append( f'\t{key}: {oldval!r} -> {newval!r}' )
		else:
			auditdata_.append( f'\t{key}: {oldval!r} (unchanged)' )
	auditdata = '\n'.join ( auditdata_ )
	
	audit = new_audit()
	
	glue = ':\n' if auditdata else ''
	if ani:
		audit.audit( f'Changed ANI {ani} at {str(path)!r}{glue}{auditdata}' )
	else:
		if path.exists():
			raise ValidationError( f'ANI already exists: {ani2}' )
		audit.audit( f'Created ANI {ani2} at {str(path)!r}{glue}{auditdata}' )
	with path.open( 'w' ) as f:
		print( repo.json_dumps( data2 ), file = f )
	
	return ani2

@app.route( '/anis/<int:ani>', methods = [ 'GET', 'POST', 'DELETE' ] )
@login_required # type: ignore
def http_ani( ani: int ) -> Response:
	#log = logger.getChild( 'http_ani' )
	return_type = accept_type()
	path = ani_file_path( ani )
	
	if request.method == 'DELETE':
		if not path.is_file():
			return _http_failure( return_type, 'ANI not found', 404 )
		try:
			path.unlink()
		except Exception as e1:
			return _http_failure( return_type, repr( e1 ), 500 )
		else:
			new_audit().audit( f'Deleted ANI {ani} at {str(path)!r}' )
			if return_type == 'application/json':
				return rest_success( [] )
			return redirect( '/anis/' )
	
	err: str = ''
	if request.method == 'POST':
		data = inputs()
		try:
			ani2 = try_post_ani( ani, data )
		except ValidationError as e2:
			err = e2.args[0]
		except Exception as e3:
			err = repr( e3 )
		else:
			if return_type == 'application/json':
				return rest_success( [] )
			return redirect( f'/anis/{ani2}' )
		if return_type == 'application/json':
			return rest_failure( err )
	else:
		if ani:
			try:
				with path.open() as f:
					data = json.loads( f.read() )
			except Exception as e4:
				return _http_failure( return_type, repr( e4 ), 500 )
			if return_type == 'application/json':
				return rest_success( [ data ] )
		else:
			data = request.args
	
	route = to_optional_int( data.get( 'route', '' ) or None )
	overrides = data.get( 'overrides', '' )
	notes = data.get( 'notes', '' )
	
	html_rows = [
		'<form method="POST" enctype="application/x-www-form-urlencoded">',
	]
	if not ani:
		ani_html = f'<input type="text" name="ani" value="{html_att(data.get("ani",""))}" size="11" maxlength="10"/>'
	else:
		ani_html = html_text( str( ani ))
	
	try:
		routes = REPO_ROUTES.list()
	except Exception as e:
		#raise e
		return _http_failure(
			return_type,
			f'Error querying routes list: {e!r}',
			500,
		)
	
	route_options: List[str] = [ '<option value="">(Do Nothing)</option>' ]
	for r, data in routes:
		att = ' selected' if route == r else ''
		lbl = data.get( 'name', '(Unnamed)' )
		route_options.append( f'<option value="{r}"{att}>{r} {lbl}</option>' )
	
	route_tip = 'Selecting a Route here will reroute this ANI no matter what DID is called'
	
	html_rows.extend( [
		f'<b>ANI:</b><br/>{ani_html}<br/><br/>',
		
		f'<b>Route:</b><br/><span tooltip="{html_att(route_tip)}"><select name="route">{"".join(route_options)}</select></span><br/><br/>',
	])
	
	overrides_tip = 'Use this section to block/redirect this ANI for specific DIDs'
	overrides_examples = '\n'.join ( ITAS_ANI_OVERRIDES_EXAMPLES )
	
	html_rows.extend( [
		'<table class="unpadded"><tr><td valign="top">',
		'<b>DID Overrides:</b><br/>',
		f'<span tooltip="{html_att(overrides_tip)}"><textarea name="overrides" cols="80" rows="4">{html_text(overrides)}</textarea></span><br/><br/>',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Examples:</b><pre class="no_top_margin">{html_text(overrides_examples)}</pre>',
		'</td></tr></table>',
		
		f'<b>Notes:</b><br/><textarea name="notes" cols="80" rows="4">{html_text(str(notes))}</textarea><br/><br/>',
	])
	if ani:
		mtime = datetime.datetime.fromtimestamp( path.stat().st_mtime ).strftime( '%Y-%m-%d %I:%M:%S %p' )
		html_rows.append( f'Last Modified: {html_text(mtime)}<br/><br/>' )
	submit = 'Save' if ani else 'Create'
	cloneparams = urlencode( data )
	cloneaction = f"window.location='/anis/0?{cloneparams}'"
	html_rows.extend( [
		f'<input type="submit" value="{html_att(submit)}"/>',
		'&nbsp;&nbsp;&nbsp;',
		f'<button onclick="{cloneaction}" type="button" class="clone">Clone</button>' if ani else '',
		'&nbsp;&nbsp;&nbsp;',
		'<button id="delete" class="delete">Delete</button>' if ani else '',
		'<br/><br/>',
		f'<font color="red">{err}</font>',
		'</form>',
		'''
<script>
var deleteButton = document.getElementById( 'delete' )

deleteButton.addEventListener( 'click', function( event ) {
	event.preventDefault()
	if ( confirm( 'Delete this ANI? ' ) )
	{
		let url = window.location.href
		fetch(
			url,
			{
				method: 'DELETE',
				headers: { Accept: 'application/json' }
			},
		).then( data => {
			if ( !data.ok )
			{
				data.json().then( jdata => {
					alert( jdata.error )
				}).catch( error => alert( error ))
			}
			else
				window.location.href = '/anis/'
		}).catch( error => alert( error ))
	}
})
</script>
'''
	] )
	return html_page( *html_rows )


#endregion http - ANI
#region http - flags


@app.route( '/flags', methods = [ 'GET', 'POST' ])
@login_required # type: ignore
def http_flags() -> Response:
	#log = logger.getChild( 'http_flags' )
	return_type = accept_type()
	
	if request.method == 'POST':
		data = inputs()
		name = data['name']
		value = data['value']
		
		path = flag_file_path( name )
		with path.open( 'w' ) as f:
			new_audit().audit( f'Set flag {name}={value!r} at {str(path)!r}' )
			print( value, file = f )
		
		if return_type == 'application/json':
			return rest_success( [] )
	
	h: List[str] = []
	def flag_form( name: str, label: str ) -> None:
		last_modified: str = '(never)'
		value = ''
		path = flag_file_path( name )
		if path.exists():
			try:
				last_modified = datetime.datetime.fromtimestamp( path.stat().st_mtime ).strftime( '%Y-%m-%d %I:%M:%S %p' )
			except Exception as e1:
				last_modified = repr( e1 )
			try:
				with path.open( 'r' ) as f:
					value = f.read()
			except Exception:
				pass
		
		h.append(
			'<form method="POST" enctype="application/x-www-form-urlencoded">'
			f'<input type="hidden" name="name" value="{html_att(name)}"/>'
			f'<b>{html_text(label)}</b><br/><input type="text" name="value" value="{html_att(value)}"/>'
			'<input type="submit" value="Set"/>'
			f'&nbsp;&nbsp;Last Modified: {html_text(last_modified)}'
			'</form><br/>'
		)
	
	settings = ace_settings.load()
	
	flag_form( 'global_flag', 'Global Flag:' )
	for cat in settings.did_categories:
		flag_form( f'category_{cat}', f'Category: {cat}' )
	
	return html_page(
		*h
	)


#endregion http - flags
#region http - routes

@app.route( '/routes', methods = [ 'GET', 'POST' ])
@login_required # type: ignore
def http_routes() -> Response:
	log = logger.getChild( 'http_routes' )
	return_type = accept_type()
	
	if request.method == 'POST':
		# BEGIN route creation
		inp = inputs()
		try:
			route = int( inp.get( 'route', '' ).strip() )
		except ValueError as e:
			return _http_failure(
				return_type,
				f'invalid route number: {e!r}',
				400,
			)
		
		try:
			REPO_ROUTES.create( route, { 'name': '', 'nodes': [] }, audit = new_audit() )
		except repo.ResourceAlreadyExists:
			return _http_failure(
				return_type,
				'resource already exists',
				400,
			)
		except HttpFailure as e:
			return _http_failure(
				return_type,
				e.error,
				e.status_code,
			)
		if return_type == 'application/json':
			return rest_success( [ { 'route': route } ] )
		url = url_for( 'http_route', route = id )
		return redirect( url )
		# END route creation
	
	q_limit = qry_int( 'limit', 20, min = 1, max = 1000 )
	q_offset = qry_int( 'offset', 0, min = 0 )
	
	q_route = request.args.get( 'route', '' ).strip()
	q_name = request.args.get( 'name', '' ).strip()
	
	filters: Dict[str,str] = {}
	if q_route:
		filters['id'] = q_route
	if q_name:
		filters['name'] = q_name
	
	# BEGIN route list
	try:
		routes = list( REPO_ROUTES.list( 
			filters,
			limit = q_limit,
			offset = q_offset,
		))
	except Exception as e:
		log.exception( 'Error querying routes list:' )
		return _http_failure(
			return_type,
			f'Error querying routes list: {e!r}',
			500,
		)
	if return_type == 'application/json':
		return rest_success([{
			'route': id,
			'name': route.get( 'name' )
		} for id, route in routes ] )
	
	row_html = '\n'.join([
		'<tr>',
			'<td><a href="{url}">{route}</a></td>',
			'<td><a href="{url}">{name}</a></td>',
			'<td><button class="delete" route="{route}">Delete {route} {name}</button></td>',
		'</tr>',
	])
	body = '\n'.join([
		row_html.format(
			route = route,
			name = data.get( 'name' ) or '(Unnamed)',
			url = url_for( 'http_route', route = route ),
		)
		for route, data in routes
	])
	
	route_tip = 'Performs substring search of all Route numbers'
	name_tip = 'Performs substring search of all Route Names'
	
	prevpage = urlencode({ 'route': q_route, 'name': q_name, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit )})
	nextpage = urlencode({ 'route': q_route, 'name': q_name, 'limit': q_limit, 'offset': q_offset + q_limit })
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Prev Page</a></td>',
		'<td align="center">',
		'<a id="route_new" href="#">(New Route)</a>',
		'</td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span tooltip="{html_att(route_tip)}"><input type="text" name="route" placeholder="Route" value="{html_att(q_route)}" size="10"/></span>',
		f'<span tooltip="{html_att(name_tip)}"><input type="text" name="name" placeholder="Name" value="{html_att(q_name)}" size="10"/></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{nextpage}">Next Page</a></td>',
		'</tr></table>',
		
		'<table border=1>',
		'<tr><th>Route</th><th>Name</th><th>Delete</th></tr>',
		body,
		'</table>',
		#'<script src="/aimara/lib/Aimara.js"></script>',
		'<script type="module" src="routes.js"></script>',
	)
	# END route list

route_id_html = '''
<div class="tree-editor">
	<div class="tree">
		<div id="div_tree"></div>
	</div>
	<div class="details">
		<div id="div_details">
			This is the Route Editor.<br/>
			<br/>
			Please click on a node to select it and see more details about
			it.<br/>
			<br/>
			Or try right-clicking on a node for more options.
		</div>
	</div>
</div>

<br/>
<br/>
<font size="-2">
	<a href="https://www.streamlineicons.com/"
		>Free Icons from Streamline Icons Pack</a
	>
</font>

<script src="/aimara/lib/Aimara.js"></script>
<script type="module" src="/tree-editor/route-editor.js"></script>
'''

@app.route( '/routes/<int:route>', methods = [ 'GET', 'PATCH', 'DELETE' ] )
@login_required # type: ignore
def http_route( route: int ) -> Response:
	log = logger.getChild( 'http_route' )
	return_type = accept_type()
	try:
		if return_type != 'application/json':
			if request.method == 'GET':
				return html_page(
					route_id_html,
					stylesheets = [
						'/aimara/css/Aimara.css',
						'/tree-editor/tree-editor.css',
						'/nice-select2/nice-select2.css',
					],
				)
			else:
				return _http_failure(
					return_type,
					'Invalid Request Method'
					'( did you forget to set header Accept=application/json? )',
					405,
				)
		
		try:
			id_ = REPO_ROUTES.valid_id( route )
		except ValueError as e1:
			raise HttpFailure( f'invalid route={route!r}: {e1!r}' ).with_traceback( e1.__traceback__ ) from None
		
		if request.method == 'GET':
			data = REPO_ROUTES.get_by_id( id_ )
			return rest_success( [ data ] )
		elif request.method == 'PATCH':
			data = inputs()
			log.debug( data )
			REPO_ROUTES.update( route, data, audit = new_audit() )
			return rest_success( [ data ] )
		elif request.method == 'DELETE':
			return route_delete( route )
		else:
			return rest_failure( f'request method {request.method} not implemented yet', 405 )
	except HttpFailure as e2:
		return _http_failure(
			return_type,
			e2.error,
			e2.status_code,
		)

def route_delete( route: int ) -> Response:
	assert isinstance( route, int ) and route > 0, f'invalid route={route!r}'
	# check if route even exists:
	if not REPO_ROUTES.exists( route ):
		raise HttpFailure( f'Route {route!r} does not exist', 404 )
	
	# check if route is referenced by any DID
	for did, did_data in REPO_DIDS.list():
		try:
			did_route_ = cast( Opt[Union[int,str]], did_data.get( 'route' ))
			did_route: Opt[int] = int( did_route_ ) if did_route_ is not None else None
		except ValueError:
			pass # could also be a 'V...' but we don't care here
		else:
			if route == did_route:
				raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by DID {did}' )
	
	# check if route is referenced by an ANI
	for ani, ani_data in REPO_ANIS.list():
		try:
			route_ = cast( Opt[Union[int,str]], ani_data.get( 'route' ))
			ani_route = int( route_ ) if route_ is not None else None
		except ValueError:
			pass
		else:
			if route == ani_route:
				raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by ANI {ani}' )
		overrides = ani_data.get( 'overrides' ) or ''
		for line in overrides.split( '\n' ):
			parts = re.split( r'\s+', line )
			if len( parts ) >= 2:
				try:
					override_route = int( parts[1] )
				except ValueError:
					pass
				else:
					if route == override_route:
						raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by ANI {ani}' )
	
	# check if route is referenced by another route:
	def json_dict_route_check( jdata: Any ) -> Opt[Any]:
		nodetype = jdata.get( 'type' )
		if nodetype == 'route':
			try:
				route2 = int( jdata.get( 'route' ) or '' )
			except ValueError:
				pass
			if route2 == route:
				return True
		return None
	
	for route2, route_settings in REPO_ROUTES.list():
		if route == route2:
			continue
		if walk_json_dicts( route_settings, json_dict_route_check ):
			raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by route {route2!r}' )
	
	# check if route is referenced by a voicemail box
	for file in Path( voicemail_settings_path( 1 )).parent.glob( '*.box' ):
		with file.open( 'r' ) as f:
			raw = f.read()
		box_settings = json.loads( raw ) if raw else {}
		if walk_json_dicts( box_settings, json_dict_route_check ):
			raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by voicemail box {file.stem}' )
	
	REPO_ROUTES.delete( route, audit = new_audit() )
	return rest_success( [] )

#endregion http - routes
#region http - voicemail

def validate_voicemail_settings( settings: Any ) -> None:
	if not isinstance( settings, dict ):
		raise ValidationError(
			f'invalid type: settings={settings!r}',
		)
	pin = settings.get( 'pin', None )
	if not isinstance( pin, str ) or not pin.isnumeric():
		raise ValidationError(
			f'missing/invalid pin: settings={settings!r}',
		)
	if not isinstance( settings.get( 'max_greeting_seconds', None ), int ):
		raise ValidationError(
			f'missing/invalid max_greeting_seconds: settings={settings!r}',
		)
	if not isinstance( settings.get( 'max_message_seconds', None ), int ):
		raise ValidationError(
			f'missing/invalid max_message_seconds: settings={settings!r}',
		)
	if not isinstance( settings.get( 'allow_guest_urgent', None ), bool ):
		raise ValidationError(
			f'missing/invalid allow_guest_urgent: settings={settings!r}',
		)

@app.route( '/voicemails', methods = [ 'GET', 'POST' ] )
@login_required # type: ignore
def http_voicemails() -> Response:
	log = logger.getChild( 'http_voicemails' )
	return_type = accept_type()
	
	if request.method == 'POST':
		# BEGIN voicemail box creation
		inp = inputs()
		try:
			box = int( inp.get( 'box', '' ).strip() )
		except ValueError as e:
			return _http_failure(
				return_type,
				f'invalid box number: {e!r}',
				400,
			)
		
		path: PurePosixPath = voicemail_settings_path( box )
		path_ = Path( path )
		if path_.is_file():
			return _http_failure(
				return_type,
				f'voicemail box number {box!r} already exists',
			)
		
		settings = inp.get( 'settings', None )
		if settings:
			try:
				validate_voicemail_settings( settings )
			except ValidationError as e:
				return _http_failure( return_type, e.args[0] )
		else:
			digits = list( '1234567890' )
			random.shuffle( digits )
			settings = {
				'pin': ''.join( digits[:8] ),
				'max_greeting_seconds': 120, # TODO FIXME: system default?
				'max_message_seconds': 120, # TODO FIXME: system default?
				'allow_guest_urgent': True,
				'format': 'mp3',
			}
		
		with path_.open( 'w' ) as f:
			f.write( repo.json_dumps( settings ))
		chown( str( path_ ), ITAS_OWNER_USER, ITAS_OWNER_GROUP )
		os.chmod( str( path_ ), 0o770 )
		
		auditdata = ''.join (
			f'\n\t{k}={v!r}' for k, v in settings.items()
			if k != 'pin' and v not in ( None, '' )
		)
		new_audit().audit( f'Created voicemail {box!r} at {str(path)!r}:{auditdata}' )
		
		if return_type == 'application/json':
			return rest_success( [ { 'box': box } ] )
		
		url = url_for( 'http_voicemail', box = box )
		log.warning( 'url=%r', url )
		return redirect( url )
		# END voicemail box creation
	
	# BEGIN voicemail boxes list
	
	q_limit = qry_int( 'limit', 20, min = 1, max = 1000 )
	q_offset = qry_int( 'offset', 0, min = 0 )
	
	q_box = request.args.get( 'box', '' ).strip()
	q_name = request.args.get( 'name', '' ).strip()
	
	try:
		path = voicemail_settings_path( '*' )
		boxes: List[Dict[str,Any]] = []
		for box_path in Path( path.parent ).glob( path.name ):
			with box_path.open( 'r' ) as f:
				settings = json.loads( f.read() )
			boxid = int( box_path.stem )
			if q_box and q_box not in str( boxid ):
				continue
			boxdata: Dict[str,Any] = { 'box': boxid, 'name': '(Unnamed)', **settings }
			if q_name and q_name.lower() not in str( boxdata['name'] ).lower():
				continue
			boxes.append( boxdata )
	except Exception as e:
		return _http_failure(
			return_type,
			f'Error querying voicemail boxes list: {e!r}',
			500,
		)
	
	boxes.sort( key = lambda box: cast( int, box['box'] ))
	if q_offset:
		boxes = boxes[q_offset:]
	if q_limit:
		boxes = boxes[:q_limit]
	
	if return_type == 'application/json':
		return rest_success( boxes )
	
	# TODO FIXME: pagination anyone?
	
	row_html = '\n'.join( [
		'<tr>',
			'<td><a href="{url}">{box}</a></td>',
			'<td><a href="{url}">{name}</a></td>',
			'<td><button class="clone" box="{box}">Clone {box} {name}</button></td>',
			'<td><button class="delete" box="{box}">Delete {box} {name}</button></td>',
		'</tr>',
	] )
	body = '\n'.join( [
		row_html.format(
			box = box['box'],
			name = box.get( 'name' ) or '(Unnamed)',
			url = url_for( 'http_voicemail', box = box['box'] ),
		) for box in boxes
	] )
	
	box_tip = 'Performs substring search of all Box numbers'
	name_tip = 'Performs substring search of all Box Names'
	
	prevpage = urlencode( { 'box': q_box, 'name': q_name, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit ) } )
	nextpage = urlencode( { 'box': q_box, 'name': q_name, 'limit': q_limit, 'offset': q_offset + q_limit } )
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Prev Page</a></td>',
		'<td align="center">',
		'<a id="box_new" href="#">(New Voicemail Box)</a>',
		'</td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span tooltip="{html_att(box_tip)}"><input type="text" name="box" placeholder="Box" value="{html_att(q_box)}" size="10"/></span>',
		f'<span tooltip="{html_att(name_tip)}"><input type="text" name="name" placeholder="Name" value="{html_att(q_name)}" size="10"/></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{nextpage}">Next Page</a></td>',
		'</tr></table>',
		
		'<table border=1>',
		'<tr>',
			'<th>Box</th>',
			'<th>Name</th>',
			'<th>Clone</th>',
			'<th>Delete</th>',
		'</tr>',
		body,
		'</table>',
		'<script type="module" src="voicemails.js"></script>',
	)
	# END voicemail boxes list

voicemail_id_html = '''
<div class="tree-editor">
	<div class="tree">
		<div id="div_tree"></div>
		<!--br/><br/>
		<div>Statistics (TODO FIXME will go here):</div-->
	</div>
	<div class="details">
		<div id="div_details">
			This is the Voicemail Box Editor.<br/>
			<br/>
			Please click on a node to select it and see more details about
			it.<br/>
			<br/>
			Or try right-clicking on a node for more options.
		</div>
	</div>
</div>

<br/>
<br/>
<font size="-2">
	<a href="https://www.streamlineicons.com/"
		>Free Icons from Streamline Icons Pack</a
	>
</font>

<script src="/aimara/lib/Aimara.js"></script>
<script type="module" src="/tree-editor/voicemail-editor.js"></script>
'''

@app.route( '/voicemails/<int:box>', methods = [ 'GET', 'PATCH', 'DELETE' ] )
@login_required # type: ignore
def http_voicemail( box: int ) -> Response:
	log = logger.getChild( 'http_voicemail' )
	return_type = accept_type()
	try:
		if return_type != 'application/json':
			if request.method == 'GET':
				return html_page(
					voicemail_id_html,
					stylesheets = [
						'/aimara/css/Aimara.css',
						'/tree-editor/tree-editor.css',
						'/nice-select2/nice-select2.css',
					],
				)
			else:
				return _http_failure(
					return_type,
					'Invalid Request Method'
					'( did you forget to set header Accept=application/json? )',
					405,
				)
		
		path = Path( voicemail_settings_path( box ))
		if not path.is_file():
			raise HttpFailure( 'Voicemail box not found', 404 )
		if request.method == 'GET':
			with path.open( 'r' ) as f:
				settings = json.loads( f.read() )
			return rest_success( [ settings ] )
		elif request.method == 'PATCH':
			data = inputs()
			log.debug( data )
			with path.open( 'r' ) as f:
				settings = json.loads( f.read() )
			for k, v in data.items():
				settings[k] = v
			try:
				validate_voicemail_settings( settings )
			except ValidationError as e:
				raise HttpFailure( e.args[0] ) from None
			with path.open( 'w' ) as f:
				f.write( repo.json_dumps( settings ))
			
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in settings.items()
				if k != 'pin' and v not in ( None, '' )
			)
			new_audit().audit( f'Updated voicemail {box!r} at {str(path)!r}:{auditdata}' )
			
			return rest_success( [ settings ] )
		elif request.method == 'DELETE':
			msgs_path = Path( voicemail_box_msgs_path( box ))
			log.warning( f'msgs_path={msgs_path!r}' )
			if msgs_path.is_dir():
				try:
					shutil.rmtree( str( msgs_path ))
				except OSError as e1:
					log.exception( 'Could not delete box %r messages:', box )
					return rest_failure( f'Could not delete box {box!r} messages: {e1!r}' )
			
			greetings_path = Path( voicemail_greeting_path( box, 1 )).parent
			log.warning( f'greetings_path={greetings_path!r}' )
			if greetings_path.is_dir():
				try:
					shutil.rmtree( str( greetings_path ))
				except OSError as e2:
					log.exception( 'Could not delete box %r greetings:', box )
					return rest_failure( f'Could not delete box {box!r} greetings: {e2!r}' )
			
			try:
				path.unlink()
			except OSError as e3:
				log.exception( 'Could not delete box %r settings file:', box )
				return rest_failure( f'Could not delete box {box!r} settings file: {e3!r}' )
			
			new_audit().audit( f'Deleted voicemail {box!r} at {str(path)!r}' )
			
			return rest_success( [] )
		else:
			return rest_failure( f'invalid request method={request.method!r}' )
	except HttpFailure as e:
		return _http_failure(
			return_type,
			e.error,
			e.status_code,
		)


#endregion http - voicemail
#region http - settings


@app.route( '/settings' )
@login_required # type: ignore
def http_settings() -> Response:
	return_type = accept_type()
	
	settings = ace_settings.load()
	
	if return_type == 'application/json':
		return rest_success([ asdict( settings )])
	
	h: List[str] = [
		'<table class="fancy" style="width:auto">',
		'<tr><th>Field</th><th>Value</th>',
	]
	for fld in fields( ace_settings.Settings ):
		editor: ace_settings.Editor = fld.metadata['editor']
		value = getattr( settings, fld.name )
		url = url_for( 'http_settings_id', fld_name = fld.name )
		h.extend([
			'<tr><th style="text-align:left">',
			f'<a href="{url}">{fld.metadata["description"]}</a>',
			'</th><td style="text-align:left">',
			f'<a href="{url}">{editor.display( value )}</a>',
			'</td></tr>',
		])
	h.append( '</table>' )
	
	return html_page( *h )


@app.route( '/settings/<string:fld_name>', methods = [ 'GET', 'POST' ])
@login_required # type: ignore
def http_settings_id( fld_name: str ) -> Response:
	return_type = accept_type()
	
	flds = { fld.name: fld for fld in fields( ace_settings.Settings )}
	fld = flds[fld_name]
	editor: ace_settings.Editor = fld.metadata['editor']
	
	settings = ace_settings.load()
	
	if request.method == 'POST':
		data = inputs()
		oldvalue = getattr( settings, fld.name )
		newvalue = editor.post( settings, fld, data )
		audit = new_audit()
		audit.audit( f'Changed Setting {fld.name} from {oldvalue!r} to {newvalue!r}' )
		setattr( settings, fld.name, newvalue )
		ace_settings.save( settings )
		if return_type == 'application/json':
			rest_success([{ fld.name: newvalue }])
	
	return html_page(
		'<form method="POST">',
		f'<label for="{fld.name}">{html.escape(fld.metadata["description"])}:<br/>',
		editor.edit( settings, fld ),
		'</label>',
		'<br/><br/>',
		'<input type="submit" value="Save"/>',
		'</form>',
	)


#endregion http - settings
#region http - CAR


@app.route( '/cars', methods = [ 'GET' ])
@login_required # type: ignore
def http_cars() -> Response:
	log = logger.getChild( 'http_cars' )
	return_type = accept_type()
	
	q_limit = qry_int( 'limit', 20, min = 1, max = 1000 )
	q_offset = qry_int( 'offset', 0, min = 0 )
	
	q_did = request.args.get( 'did', '' ).strip()
	q_ani = request.args.get( 'ani', '' ).strip()
	
	filters: Dict[str,str] = {}
	if q_did:
		filters['did'] = q_did
	if q_ani:
		filters['ani'] = q_ani
	
	try:
		cars = list( REPO_CAR.list(
			filters,
			limit = q_limit,
			offset = q_offset,
			orderby = 'start',
			reverse = True,
		))
	except Exception as e:
		log.exception( 'Error querying car list:' )
		return _http_failure(
			return_type,
			f'Error querying car list: {e!r}',
			500,
		)
	
	if return_type == 'application/json':
		return rest_success([
			data for _, data in cars
		])
	
	row_html = '\n'.join([
		'<tr>',
			'<td><a href="{url}">{uuid}</a></td>',
			'<td><a href="{url}">{did}</a></td>',
			'<td><a href="{url}">{ani}</a></td>',
			'<td><a href="{url}">{cpn}</a></td>',
			'<td><a href="{url}">{acct_num}</a></td>',
			'<td><a href="{url}">{acct_name}</a></td>',
			'<td><a href="{url}">{start}</a></td>',
			'<td><a href="{url}">{end}</a></td>',
		'</tr>',
	])
	body_: List[str] = []
	for _, data in cars:
		try:
			start = (
				datetime.datetime.utcfromtimestamp( data['start'] )
				.replace( tzinfo = datetime.timezone.utc ) # assign correct tz
				.astimezone() # convert to local time
				.strftime( '%Y-%m-%d %H:%M:%S.%f%z' )
			)
		except Exception as e:
			start = repr( e )
		try:
			end = (
				datetime.datetime.utcfromtimestamp( data['end'] )
				.replace( tzinfo = datetime.timezone.utc ) # assign correct tz
				.astimezone() # convert to local time
				.strftime( '%Y-%m-%d %H:%M:%S.%f%z' )
			)
		except Exception as e:
			end = repr( e )
		uuid = data['id']
		data2: Dict[str,Any] = dict( **data )
		data2['uuid'] = uuid
		data2['start'] = start
		data2['end'] = end
		data2['url'] = url_for( 'http_car', uuid = uuid ) # TODO FIXME: This can throw a number of exceptions...
		body_.append( row_html.format( **data2 ))
	
	body = '\n'.join( body_ )
	
	did_tip = 'search for full or partial DID'
	ani_tip = 'search for full or partial ANI'
	
	prevpage = urlencode({ 'did': q_did, 'ani': q_ani, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit )})
	nextpage = urlencode({ 'did': q_did, 'ani': q_ani, 'limit': q_limit, 'offset': q_offset + q_limit })
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Prev Page</a></td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span tooltip="{html_att(did_tip)}"><input type="text" name="did" placeholder="DID" value="{html_att(q_did)}" maxlength="10" size="11"/></span>',
		f'<span tooltip="{html_att(ani_tip)}"><input type="text" name="ani" placeholder="ANI" value="{html_att(q_ani)}" maxlength="10" size="11"/></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{nextpage}">Next Page</a></td>',
		'</tr></table>',
		
		'<table border=1>',
		'<tr>',
		'	<th>UUID</th>',
		'	<th>DID</th>',
		'	<th>ANI</th>',
		'	<th>CPN</th>',
		'	<th>Acct#</th>',
		'	<th>Acct Name</th>',
		'	<th>Start</th>',
		'	<th>End</th>',
		'</tr>',
		body,
		'</table>',
	)

@app.route( '/cars/<string:uuid>', methods = [ 'GET' ])
@login_required # type: ignore
def http_car( uuid: str ) -> Response:
	log = logger.getChild( 'http_car' )
	return_type = accept_type()
	try:
		try:
			id_ = REPO_CAR.valid_id( uuid )
		except ValueError as e1:
			raise HttpFailure( f'invalid uuid={uuid!r}: {e1!r}' ).with_traceback( e1.__traceback__ ) from None
		
		data = REPO_CAR.get_by_id( id_ )
		
		if return_type == 'application/json':
			return rest_success([ data ])
		
		did = data.get( 'did' ) or '(none)'
		ani = data.get( 'ani' ) or '(none)'
		cpn = data.get( 'cpn' ) or '(none)'
		acct_num = data.get( 'acct_num' ) or '(none)'
		acct_name = data.get( 'acct_name' ) or '(none)'
		
		try:
			start_: Opt[datetime.datetime] = (
				datetime.datetime.utcfromtimestamp( data['start'] )
				.replace( tzinfo = datetime.timezone.utc ) # assign correct tz
				.astimezone() # convert to local time
			)
			assert start_ is not None
			start: str = start_.strftime( '%Y-%m-%d %H:%M:%S.%f%z' )
		except Exception as e:
			start_ = None
			start = repr( e )
		
		try:
			end_: Opt[datetime.datetime] = (
				datetime.datetime.utcfromtimestamp( data['end'] )
				.replace( tzinfo = datetime.timezone.utc ) # assign correct tz
				.astimezone() # convert to local time
			)
			assert end_ is not None
			end: str = end_.strftime( '%Y-%m-%d %H:%M:%S.%f%z' )
		except Exception as e:
			end_ = None
			end = repr( e )
		
		if start_ and end_:
			duration: str = dhms( end_ - start_ )
		else:
			duration = '(unknown)'
		
		html_lines: List[str] = [
			'<h2>Call Activity Record:</h2>',
			f'<b>UUID:</b> {html_text(uuid)}<br/>',
			f'<b>DID:</b> {html_text(did)}<br/>',
			f'<b>ANI:</b> {html_text(ani)}<br/>',
			f'<b>CPN:</b> {html_text(cpn)}<br/>',
			f'<b>Acct#:</b> {html_text(acct_num)}<br/>',
			f'<b>Acct Name:</b> {html_text(acct_name)}<br/>',
			f'<b>Start:</b> {html_text(start)}<br/>',
			f'<b>End:</b> {html_text(end)}<br/>',
			f'<b>Duration:</b> {html_text(duration)}<br/>',
		]
		
		try:
			activity: List[Dict[str,str]] = json.loads( cast( str, data.get( 'activity' )))
			assert isinstance( activity, list )
		except Exception as e:
			log.exception( 'Error loading car activity:' )
			html_lines.append(
				f'ERROR loading activity: {e!r}'
			)
		else:
			html_lines.append( f'<table border="1" style="border-collapse:collapse"><tr><th>Time</th><th>Activity</th></tr>' )
			for row in activity:
				try:
					time: str = row['time']
				except Exception as e:
					time = repr( e )
				try:
					description: str = row['description']
				except Exception as e:
					description = repr( e )
				html_lines.append(
					'<tr>'
						f'<td>{html_text(time)}</td>'
						f'<td>{html_text(description)}</td>'
					'</tr>'
				)
			html_lines.append( '</table>' )
		
		return html_page( *html_lines )
		
	except HttpFailure as e2:
		return _http_failure(
			return_type,
			e2.error,
			e2.status_code,
		)

#endregion http - CAR
#region http - audits


@app.route( '/audit' )
@login_required # type: ignore
def http_audits() -> Response:
	return_type = accept_type()
	
	q_limit = qry_int( 'limit', 20, min = 1, max = 1000 )
	q_offset = qry_int( 'offset', 0, min = 0 )
	
	q_search = request.args.get( 'search', '' ).strip()
	
	try:
		path = Path( ITAS_AUDIT_DIR )
		logfile_list: List[Dict[str,str]] = []
		for item in path.iterdir():
			if item.is_file() and item.exists():
				name = item.name
				lname = name.lower()
				if lname.endswith( '.log' ):
					logfile_list.append( { 'filename': name } )
	except Exception as e:
		return _http_failure(
			return_type,
			f'Error obtaining list of audit logs: {e!r}',
			500,
		)
	logfile_list = sorted( logfile_list, key = lambda d: d['filename'] )[::-1]
	
	if q_search:
		stop = q_offset + q_limit
		search = q_search.lower()
		new_list: List[Dict[str,str]] = []
		for d in logfile_list:
			file = path / d['filename']
			with file.open( 'r' ) as f:
				content = f.read()
			if search in content.lower():
				new_list.append( d )
				if len( new_list ) >= stop: # do we have enough?
					break # we have enough
		logfile_list = new_list
	
	logfile_list = logfile_list[q_offset:q_offset + q_limit]
	if return_type == 'application/json':
		return rest_success( logfile_list )
	row_html = (
		'<tr>'
		'<td><a href="/audit/{filename}">{filename}</a></td>'
		'</tr>'
	)
	body = '\n'.join( [
		row_html.format( **d ) for d in logfile_list
	] )
	
	search_tip = 'Performs substring search of all audit logs'
	
	prevpage = urlencode( { 'search': q_search, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit ) } )
	nextpage = urlencode( { 'search': q_search, 'limit': q_limit, 'offset': q_offset + q_limit } )
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Newer Logs</a></td>',
		'<td align="center">',
		'<form method="GET">'
		f'<span tooltip="{html_att(search_tip)}"><input type="text" name="search" placeholder="Search" value="{html_att(q_search)}"/></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{nextpage}">Older Logs</a></td>',
		'</tr></table>',
		'<table class="fancy">',
		'<tr><th>Log File</th></tr>',
		body,
		'</table>',
	)

@app.route( '/audit/<filename>' )
@login_required # type: ignore
def http_audit_item( filename: str ) -> Response:
	return_type = accept_type()
	if not valid_audit_filename( filename ):
		return _http_failure(
			return_type,
			f'Invalid audit filename {filename!r}',
			400,
		)
	try:
		assert valid_audit_filename( filename )
		path = Path( ITAS_AUDIT_DIR ) / filename
		with path.open( 'r' ) as f:
			content = f.read()
	except Exception as e:
		return _http_failure(
			return_type,
			f'Error retrieving audit file: {e!r}',
			500,
		)
	if return_type == 'application/json':
		return rest_success( [ { 'content': content } ] )
	return html_page(
		f'<pre>{html_text(content)}</pre>',
	)


#endregion http - audits
#region service management


def service_command( cmd: str ) -> int:
	log = logger.getChild( 'service_command' )
	log.debug( 'cmd=%r', cmd )
	service_name = 'ace.service'
	service_path = Path( '/lib/systemd/system/' ) / service_name
	if cmd in ( 'add', 'install' ):
		if service_path.is_file():
			print( f'Service file already exists: {service_path}' )
			return -1
		with service_path.open( 'w', encoding = 'utf-8', errors = 'strict' ) as f:
			this_py = os.path.abspath( __file__ )
			print( '\n'.join( [
				'[Unit]',
				'Description=ITAS Automated Call Engine Portal',
				'After=network.target',
				'',
				'[Service]',
				'Type=simple',
				f'ExecStart=/usr/bin/python3 {this_py}',
				'Restart=on-abort',
				'',
				'[Install]',
				'WantedBy=multi-user.target',
			] ), file = f )
		os_execute( 'systemctl daemon-reload' )
		os_execute( f'systemctl enable {service_name}' )
		os_execute( f'systemctl start {service_name}' )
		return 0
	elif cmd == 'status':
		os_execute( f'systemctl status {service_name}' )
		return 0
	elif cmd == 'start':
		os_execute( f'systemctl start {service_name}' )
		return 0
	elif cmd == 'restart':
		os_execute( f'systemctl restart {service_name}' )
		return 0
	elif cmd == 'stop':
		os_execute( f'systemctl stop {service_name}' )
		return 0
	elif cmd in ( 'remove', 'uninstall' ):
		if not service_path.is_file():
			print( f'Service file does not exist: {service_path}' )
			sys.exit( -1 )
		os_execute( f'systemctl stop {service_name}' )
		os_execute( f'systemctl disable {service_name}' )
		service_path.unlink()
		os_execute( 'systemctl daemon-reload' )
		return 0
	else:
		print( f'command not recognized: {cmd!r}' )
		return -1


#endregion service management
#region CDR Vacuum

def _uepoch_to_timestamp( uepoch: Union[int,str] ) -> str:
	uepoch_float = float( uepoch ) / 1_000_000
	float_datetime = datetime.datetime.fromtimestamp( uepoch_float )
	return float_datetime.strftime( '%Y-%m-%d %H:%M:%S.%f' )


def _cdr_vacuum() -> None:
	log = logger.getChild( 'cdr_processor._vacuum' )
	assert ITAS_FREESWITCH_JSON_CDR_PATH
	path = Path( ITAS_FREESWITCH_JSON_CDR_PATH )
	#removal_list = []
	if not path.is_dir():
		log.warning( 'json_cdr path does not exist: %r', str( path ))
		return
	for item in path.iterdir():
		if item.is_file() and item.exists():
			try:
				with open( item, 'r' ) as cdr_file:
					raw = cdr_file.read()
				data = json.loads( raw ) if raw else {}
				call_uuid = data['variables']['uuid']
				start_stamp = _uepoch_to_timestamp(data['variables']['start_uepoch'])
				answered_stamp = _uepoch_to_timestamp(data['variables']['answered_uepoch'])
				end_stamp = _uepoch_to_timestamp(data['variables']['end_uepoch'])
				try:
					REPO_JSON_CDR.create( call_uuid, {
						'call_uuid': call_uuid,
						'start_stamp': start_stamp,
						'answered_stamp': answered_stamp,
						'end_stamp': end_stamp,
						'json': data
					}, audit = new_audit() )
					os.remove( item )
				except repo.ResourceAlreadyExists:
					raise HttpFailure( 'resource already exists' )
				except Exception:
					log.exception( 'Unable to create CDR database entry for file %r:', str( item ))
			
			except Exception:
				log.exception( 'Unable to import JSON file %r:', str( item ))

def cdr_processor() -> None:
	running = True
	log = logger.getChild( 'cdr_processor' )
	while running:
		try:
			_cdr_vacuum()
		except Exception:
			log.exception( 'CDR processor exception:' )
		sleep( 60 )

def spawn ( target: Callable[...,Any], *args: Any, **kwargs: Any ) -> Thread:
	def _target ( *args: Any, **kwargs: Any ) -> Any:
		log = logger.getChild ( 'spawn._target' )
		try:
			return target ( *args, **kwargs )
		except Exception:
			log.exception ( 'Unhandled exception exit from thread:' )
	thread = Thread (
		target = _target,
		args = args,
		kwargs = kwargs,
		daemon = True,
	)
	thread.start()
	return thread


#endregion CDR Vacuum
#region bootstrap


if __name__ == '__main__':
	ace_logging.init( Path( ITAS_UI_LOGFILE ), ITAS_LOGLEVELS )
	cmd: List[str] = sys.argv[1:2]
	if cmd:
		sys.exit( service_command( cmd[0] ))
	login_manager.init_app( app )
	
	settings_path = Path( ITAS_SETTINGS_PATH )
	ace_settings.init( settings_path, g_settings_mplock )
	
	#assert ITAS_TTS_DEFAULT_VOICE in tts_voices, f'invalid ITAS_TTS_DEFAULT_VOICE={ITAS_TTS_DEFAULT_VOICE!r}'
	ace_engine.start( ace_engine.Config(
		settings_path = settings_path,
		settings_mplock = g_settings_mplock,
		repo_anis = repo.AsyncRepository( REPO_ANIS ),
		repo_dids = repo.AsyncRepository( REPO_DIDS ),
		repo_routes = repo.AsyncRepository( REPO_ROUTES ),
		repo_car = repo.AsyncRepository( REPO_CAR ),
		car_mplock = g_car_mplock,
		did_fields = ITAS_DID_FIELDS,
		flags_path = flags_path,
		vm_box_path = voicemail_meta_path,
		vm_msgs_path = voicemail_msgs_path,
		owner_user = ITAS_OWNER_USER,
		owner_group = ITAS_OWNER_GROUP,
		
		engine_logfile = Path( ITAS_ENGINE_LOGFILE ),
		loglevels = ITAS_LOGLEVELS,
	))
	
	cert_path = Path( ITAS_CERTIFICATE_PEM )
	if cert_path.exists():
		logger.debug( 'loading certificate at %r', cert_path )
		crt_path = key_path = str( cert_path )
	else:
		logger.debug(
			'using adhoc certificate because cert not found at %r', cert_path
		)
		cert_base = str( Path( tempfile.gettempdir() ) / 'ace' )
		crt_path = cert_base + '.crt'
		key_path = cert_base + '.key'
		if not os.path.isfile( key_path ):
			hostname = socket.gethostname()
			host = socket.gethostbyname( hostname )
			logger.debug(
				'generating adhoc cert %r for host %r', crt_path, host,
			)
			x = make_ssl_devcert( cert_base, host = host )
			assert x ==( crt_path, key_path )
		else:
			logger.debug( 'using existing adhoc cert %r', crt_path )
	
	address = '0.0.0.0' # TODO FIXME: load from flask.cfg?
	#Spawn CDR vacuum
	spawn( cdr_processor )
	wsgi = WSGIContainer( app )
	http_server = HTTPServer(
		wsgi,
		ssl_options = { 'certfile': crt_path, 'keyfile': key_path },
	)
	http_server.listen(
		ITAS_LISTEN_PORT,
		address = address,
	)
	IOLoop.instance().start()


#endregion bootstrap
