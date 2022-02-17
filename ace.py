#!/usr/bin/env python3
#region copyright


# This file is Copyright (C) 2022 ITAS Solutions LP, All Rights Reserved
# Contact ITAS Solutions LP at royce3@itas-solutions.com for licensing inquiries


#endregion copyright
#region imports


from abc import ABCMeta, abstractmethod
import accept_types # type: ignore # pip install accept-types
from contextlib import closing
import datetime
from flask import( # pip install flask
	Flask, jsonify, render_template, request, Response,
	send_from_directory, session, url_for,
)
from flask_login import( # type: ignore # pip install flask-login
	LoginManager, UserMixin, AnonymousUserMixin,
	login_required, current_user, confirm_login, login_user, logout_user,
)
from flask_session import Session # type: ignore # pip install flask-session
import html
import json
import logging
import mimetypes
import os
from pathlib import Path
#import platform
import random
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
from tornado.wsgi import WSGIContainer # pip install tornado
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from typing import(
	Any, Callable, cast, Dict, Iterator, List, Optional as Opt, Sequence as Seq,
	Tuple, Type, TypeVar, TYPE_CHECKING, Union,
)
import tzlocal # pip install tzlocal
from urllib.parse import urlencode, urlparse
import uuid
from werkzeug.serving import make_ssl_devcert

if TYPE_CHECKING:
	def redirect( url: str ) -> Response: ...
else:
	from flask import redirect # flask.wrappers.Response vs werkzeug.wrappers.Response

# OS specific:
if os.name == 'posix': # Linux or cygwin
	import grp
	import pam # type: ignore # pip install python-pam
	import pwd
	from systemd.journal import JournaldLogHandler # type: ignore # pip install systemd


#endregion imports
#region globals


SESSION_USERDATA = 'userdata'
etc_path = Path( '/etc/itas/ace/' )
default_data_path = Path( '/usr/share/itas/ace/' )

logger = logging.getLogger( __name__ )

if os.name == 'posix':
	auth = pam.pam()
else:
	logger.critical(
		'NON-POSIX IMPLEMENTATION ONLY SUPPORTS A SINGLE HARD-CODED USER FOR NOW'
	)


#endregion globals
#region utilities


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
	log.debug( f'url={url!r} -> unsafe={unsafe!r}' )
	return not unsafe

def is_root() -> bool:
	assert os.name == 'posix' # this function doesn't make sense outside of posix for now
	uid: int = os.getuid() # type: ignore
	return uid == 0

def drop_root( uid_name: str = 'nobody', gid_name: str = 'nogroup' ) -> None:
	if os.name != 'posix' or not is_root():
		return # we're already not root, nothing to do
	
	# Get the uid/gid from the name
	running_uid = pwd.getpwnam( uid_name ).pw_uid
	running_gid = grp.getgrnam( gid_name ).gr_gid
	
	# Remove group privileges
	os.setgroups( [] ) # type: ignore
	
	# Try setting the new uid/gid
	os.setgid( running_gid ) # type: ignore
	os.setuid( running_uid ) # type: ignore
	
	# Ensure a very conservative umask
	_ = os.umask( 0o077 ) # returns old_umask

def chown( path: str, uid_name: str, gid_name: str ) -> None:
	if os.name == 'nt':
		return
	uid = pwd.getpwnam( uid_name ).pw_uid
	gid = grp.getgrnam( gid_name ).gr_gid
	os.chown( path, uid, gid ) # type: ignore

def os_execute( cmd: str ) -> None:
	log = logger.getChild( 'os_execute' )
	log.debug( cmd )
	os.system( cmd )

def json_dumps( data: Any ) -> str:
	return json.dumps( data, indent = '\t', separators = ( ',', ': ' ))

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


def html_text( text: str ) -> str:
	return html.escape( text, quote = False )

def html_att( text: str ) -> str:
	return html.escape( text, quote = True )

def html_page( *lines: str, stylesheets: Opt[List[str]] = None, status_code: Opt[int] = None ) -> Response:
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
			f'	<li><a href="{url_for("http_audit_list")}">Audit</a></li>',
			f'	<li><a href="{url_for("http_logout")}">Log Out</a></li>',
			'</ul>',
		] )
	header.append( '<div id="content">' )
	footer = [ f'<br/><br/>{ITAS_MOTD}</div></body></html>' ]
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
	return cast( Response, jsonify( success = True, rows = rows or [] ))

def rest_failure( error: str, status_code: Opt[int] = None ) -> Response:
	r = cast( Response, jsonify( success = False, error = error ))
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
def authenticate( usernm: str, secret: str ) -> bool:
	log = logger.getChild( 'authenticate' )
	if os.name == 'posix':
		return bool( auth.authenticate( usernm, secret ))
	else:
		log.critical(
			'NON-POSIX IMPLEMENTATION ONLY SUPPORTS A SINGLE HARD-CODED USER FOR NOW'
		)
		return usernm == 'setup' and secret == 'deleteme'


#endregion authentication
#region custom DID fields


class ValidationError( Exception ):
	pass

class Field:
	def __init__( self, field: str, label: str, *,
		tooltip: str = '',
		required: bool = False,
		min_length: Opt[int] = None,
		max_length: Opt[int] = None,
	) -> None:
		self.field = field
		self.label = label
		self.tooltip = tooltip
		self.required = required
		self.min_length = min_length
		self.max_length = max_length
	
	def validate( self, rawvalue: Opt[str] ) -> Union[None,int,str]:
		if rawvalue is None:
			if self.required:
				raise ValidationError( f'{self.label} is required' )
			return None
		if self.min_length is not None and len( rawvalue ) < self.min_length:
			raise ValidationError( f'{self.label} is too short, min length is {self.min_length!r}' )
		if self.max_length is not None and len( rawvalue ) > self.max_length:
			raise ValidationError( f'{self.label} is too long, max length is {self.max_length!r}' )
		return rawvalue

class IntField( Field ):
	def __init__( self, field: str, label: str, *,
		tooltip: str = '',
		required: bool = False,
		min_length: Opt[int] = None,
		max_length: Opt[int] = None,
		min_value: Opt[int] = None,
		max_value: Opt[int] = None,
	) -> None:
		super().__init__( field, label,
			tooltip = tooltip,
			required = required,
			min_length = min_length,
			max_length = max_length,
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
		f'ITAS_AUDIT_DIR = {"/var/log/itas/ace/"!r}',
		f'ITAS_AUDIT_FILE = {"%Y-%m-%d.log"!r}',
		f'ITAS_AUDIT_TIME = {"%Y-%m-%d %H:%M:%S.%f %Z%z"!r}',
		f'ITAS_FREESWITCH_SOUNDS = {["/usr/share/freeswitch/sounds/en/us/callie"]!r}',
		f'ITAS_REPOSITORY_TYPE = {"fs"!r}',
		f'ITAS_REPOSITORY_FS_PATH = {"/usr/share/itas/ace/"!r}',
		f'ITAS_REPOSITORY_SQLITE_PATH = {"/usr/share/itas/ace/database.db"!r}',
		f'ITAS_FLAGS_PATH = {str(default_data_path)!r}',
		f'ITAS_DIDS_PATH = {str(default_data_path/"did")!r}',
		f'ITAS_ANIS_PATH = {str(default_data_path/"ani")!r}',
		'ITAS_DID_CATEGORIES = {!r}'.format( [
			'general',
			'medical',
			'shoes',
		] ),
		f'ITAS_DID_FIELDS = {[]!r}',
		f'ITAS_DID_VARIABLES_EXAMPLES = {[]!r}',
		'ITAS_ANI_OVERRIDES_EXAMPLES = {!r}'.format( [
			'# <<< anything after a # is a "comment" and is ignored',
			'8005551212 6999 # always send calls with this ANI and DID 8005551212 to route 6999',
			'8005551213 6999 1999-12-31 # send calls with this ANI and DID 8005551213 to route 6999 until Dec 31, 1999 12:00:00 AM',
			'8005551214 6999 1999-12-31 08:00:00 # send calls with this ANI and DID 8005551214 to route 6999 until Dec 31, 1999 8:00 AM (local time)',
		] ),
		f'ITAS_VOICEMAIL_META_PATH = {"/usr/share/itas/ace/voicemail/meta/"!r}',
		f'ITAS_VOICEMAIL_MSGS_PATH = {"/usr/share/itas/ace/voicemail/msgs/"!r}',
		'ITAS_MOTD = {!r}'.format( "Don't Panic!" ),
	] )
	with cfg_path.open( 'w' ) as f:
		print( cfg_raw, file = f )
else:
	with cfg_path.open( 'r' ) as f:
		cfg_raw = f.read()

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
ITAS_AUDIT_DIR: str = ''
ITAS_AUDIT_FILE: str = ''
ITAS_AUDIT_TIME: str = ''
ITAS_FREESWITCH_SOUNDS: List[str] = []
ITAS_REPOSITORY_TYPE: str = ''
ITAS_REPOSITORY_FS_PATH: str = ''
ITAS_REPOSITORY_SQLITE_PATH: str = ''
ITAS_FLAGS_PATH: str = ''
ITAS_DIDS_PATH: str = ''
ITAS_ANIS_PATH: str = ''
ITAS_DID_CATEGORIES: List[str] = []
ITAS_DID_FIELDS: List[Field] = []
ITAS_DID_VARIABLES_EXAMPLES: List[str] = []
ITAS_ANI_OVERRIDES_EXAMPLES: List[str] = []
ITAS_VOICEMAIL_META_PATH: str
ITAS_VOICEMAIL_MSGS_PATH: str
ITAS_MOTD: str = ''
exec( cfg_raw + '\n' ) # begin flask.cfg variables created by this exec:
# end of flask.cfg variables

app.config.from_object( __name__ )
app.config['APP_NAME'] = 'Automated Call Experience (ACE)'


#endregion flask config
#region paths and auditing


audit_path = Path( ITAS_AUDIT_DIR )
audit_path.mkdir( mode = 0o770, parents = True, exist_ok = True )

if __name__ == '__main__' and SESSION_TYPE == 'filesystem':
	session_path = Path( SESSION_FILE_DIR )
	session_path.mkdir( mode = 0o770, parents = True, exist_ok = True )
	if os.name == 'posix':
		chown( str( session_path ), 'www-data', 'www-data' )
		os.chmod( SESSION_FILE_DIR, 0o770 )

r_valid_audit_filename = re.compile( r'^[a-zA-Z0-9_\.-]+$', re.I )
def valid_audit_filename( filename: str ) -> bool:
	return bool( r_valid_audit_filename.match( filename ))

def audit( msg: str ) -> None:
	tzinfo = tzlocal.get_localzone()
	now = datetime.datetime.now( tz = tzinfo )
	line = ' '.join( [
		now.strftime( ITAS_AUDIT_TIME ),
		current_user.name,
		request.remote_addr,
		msg,
	] )
	path = audit_path / now.strftime( ITAS_AUDIT_FILE )
	with path.open( 'a', encoding = 'utf-8', errors = 'backslashreplace' ) as f:
		print( line, file = f )

flags_path = Path( ITAS_FLAGS_PATH )
flags_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( flags_path ), 'www-data', 'www-data' )
os.chmod( str( flags_path ), 0o775 )
def flag_file_path( flag: str ) -> Path:
	return flags_path / f'{flag}.flag'

dids_path = Path( ITAS_DIDS_PATH )
dids_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( dids_path ), 'www-data', 'www-data' )
os.chmod( str( dids_path ), 0o775 )
def did_file_path( did: int ) -> Path:
	return dids_path / f'{did}.did'

anis_path = Path( ITAS_ANIS_PATH )
anis_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( anis_path ), 'www-data', 'www-data' )
os.chmod( str( anis_path ), 0o775 )
def ani_file_path( ani: int ) -> Path:
	return anis_path / f'{ani}.ani'

voicemail_meta_path = Path( ITAS_VOICEMAIL_META_PATH )
voicemail_meta_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( voicemail_meta_path ), 'www-data', 'www-data' )
os.chmod( str( anis_path ), 0o775 )
def voicemail_settings_path( box: Union[int,str] ) -> Path:
	return voicemail_meta_path / f'{box}.box'
def voicemail_greeting_path( box: int, greeting: int ) -> Path:
	return voicemail_meta_path / f'{box}' / f'greeting{greeting}.wav'

voicemail_msgs_path = Path( ITAS_VOICEMAIL_MSGS_PATH )
voicemail_msgs_path.mkdir( mode = 0o775, parents = True, exist_ok = True )
chown( str( voicemail_msgs_path ), 'www-data', 'www-data' )
os.chmod( str( anis_path ), 0o775 )
def voicemail_box_msgs_path( box: int ) -> Path:
	return voicemail_msgs_path / str( box )


#endregion paths and auditing
#region repo base


REPOID = int


class SqlBase( metaclass = ABCMeta ):
	def __init__( self, name: str, *,
		null: bool,
		primary: bool = False,
		unique: bool = False,
		index: bool = False,
	) -> None:
		assert not name.lower().startswith( 'idx_' ), '"idx_" prefix is not allowed for field names, it is reserved for indexes'
		self.name = name
		self.null = null
		
		# only one of the following 3 should be set to true
		self.primary = primary
		self.unique = unique and not self.primary
		self.index = index and not self.unique
	
	@abstractmethod
	def validate( self ) -> None:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.validate()' )
	
	@abstractmethod
	def to_sqlite( self ) -> str:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.to_sqlite()' )
	
	def to_sqlite_extra( self ) -> List[str]:
		# this is used to create extra entries inside the create table statement
		return []
	
	def to_sqlite_after( self, table: str ) -> List[str]:
		# this is used to create supplemental entries after the create table statement
		sql: List[str] = []
		if self.index:
			sql.append( 'CREATE INDEX "idx_{table}_{self.name}" ON "{table}" ({self.name})' )
		return sql


class SqlVarChar( SqlBase ):
	def __init__( self, name: str, *,
		size: int,
		null: bool,
		primary: bool = False,
		unique: bool = False,
		index: bool = False,
	) -> None:
		super().__init__( name,
			null = null,
			primary = primary,
			unique = unique,
			index = index,
		)
		assert isinstance( size, int ) and 1 <= size <= 255, f'invalid size={size!r}'
		self.size = size
	
	def validate( self ) -> None:
		assert self.size > 0
	
	def to_sqlite( self ) -> str:
		sql: List[str] = [
			self.name,
			f'VARCHAR({self.size})',
			'NULL' if self.null else 'NOT NULL',
			'PRIMARY KEY' if self.primary else '',
			'UNIQUE' if self.unique else '',
		]
		return ' '.join( filter( None, sql ))


class SqlDateTime( SqlBase ):
	def __init__( self, name: str, *,
		null: bool,
		index: bool = False,
	) -> None:
		super().__init__( name,
			null = null,
			primary = False,
			unique = False,
			index = index,
		)
	
	def validate( self ) -> None:
		pass
	
	def to_sqlite( self ) -> str:
		sql: List[str] = [
			self.name,
			'TEXT', # sqlite doesn't have a DATETIME type
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))


class SqlInteger( SqlBase ):
	def __init__( self, name: str, *,
		size: int,
		null: bool,
		auto: bool = False,
		primary: bool = False,
		unique: bool = False,
		index: bool = False,
	) -> None:
		super().__init__( name,
			null = null,
			primary = primary,
			unique = unique,
			index = index,
		)
		assert isinstance( size, int ) and 1 <= size <= 20, f'invalid size={size!r}'
		self.size = size
		self.auto = auto
	
	def validate( self ) -> None:
		assert self.size > 0
	
	def to_sqlite( self ) -> str:
		sql: List[str] = [
			self.name,
			f'INTEGER({self.size})',
			'NULL' if self.null else 'NOT NULL',
			'PRIMARY KEY' if self.primary else '',
			'UNIQUE' if self.unique else '',
			'AUTOINCREMENT' if self.auto else '',
		]
		return ' '.join( filter( None, sql ))


class SqlText( SqlBase ):
	def __init__( self, name: str, *,
		null: bool,
		primary: bool = False,
		unique: bool = False,
		index: bool = False,
	) -> None:
		assert not unique, 'text fields cannot be unique'
		assert not primary, 'text fields cannot be primary keys'
		super().__init__( name,
			null = null,
			primary = primary,
			unique = unique,
			index = index,
		)
	
	def validate( self ) -> None:
		pass
	
	def to_sqlite( self ) -> str:
		sql: List[str] = [
			self.name,
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
			#'PRIMARY KEY' if self.primary else '',
			#'UNIQUE' if self.unique else '',
		]
		return ' '.join( filter( None, sql ))


class SqlJson( SqlBase ):
	def __init__( self, name: str, *,
		null: bool,
		primary: bool = False,
		unique: bool = False,
		index: bool = False,
	) -> None:
		assert not unique, 'json fields cannot be unique'
		assert not primary, 'json fields cannot be primary keys'
		super().__init__( name,
			null = null,
			primary = primary,
			unique = unique,
			index = index,
		)
	
	def validate( self ) -> None:
		pass
	
	def to_sqlite( self ) -> str:
		sql: List[str] = [
			self.name,
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
			#'PRIMARY KEY' if self.primary else '',
			#'UNIQUE' if self.unique else '',
		]
		return ' '.join( filter( None, sql ))


class Repository( metaclass = ABCMeta ):
	type = 'Abstract repository'
	schemas: Dict[str,List[SqlBase]]
	
	def __init__( self, tablename: str, ending: str, fields: List[SqlBase] ) -> None:
		assert tablename not in RepoSqlite.schemas, f'duplicate schema definition for table {tablename!r}'
		self.schemas[tablename] = fields
	
	@abstractmethod
	def valid_id( self, id: REPOID ) -> REPOID:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.valid_id' )
	
	@abstractmethod
	def exists( self, id: REPOID ) -> bool:
		# does the indicated id exist?
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.exists' )
	
	@abstractmethod
	def get_by_id( self, id: REPOID ) -> Dict[str, Any]:
		# Return single dictionary by id
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.get_by_id' )
	
	@abstractmethod
	def list( self ) -> Seq[Tuple[int, Dict[str, Any]]]:
		# Return all dictionaries of type
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.list' )
	
	@abstractmethod
	def create( self, id: REPOID, resource: Dict[str,Any] ) -> None:
		# Persist new dictionary and return it
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.create' )
	
	@abstractmethod
	def update( self, id: REPOID, resource: Dict[str,Any] ) -> Dict[str,Any]:
		# Update by id and return updated dict
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.update' )
	
	@abstractmethod
	def delete( self, id: REPOID ) -> Dict[str,Any]:
		# delete by id and return deleted dict
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.delete' )


#endregion repo base
#region repo sqlite


def dict_factory( cursor: Any, row: Seq[Any] ) -> Dict[str,Any]:
	d: Dict[str,Any] = {}
	for idx, col in enumerate( cursor.description ):
		d[col[0]] = row[idx]
	return d

class RepoSqlite( Repository ):
	type = 'sqlite'
	database: sqlite3.Connection
	
	@classmethod
	def setup( cls ) -> None:
		sqlite_path = Path( ITAS_REPOSITORY_SQLITE_PATH )
		if not sqlite_path.exists():
			sqlite_path.touch()
		cls.database = sqlite3.connect( str( sqlite_path ))
		setattr( cls.database, 'row_factory', dict_factory )
		#with closing( cls.database.cursor() ) as cur:
		#	#cur.execute(
		#	#	'CREATE TABLE IF NOT EXISTS "audits" (id INTEGER PRIMARY KEY AUTOINCREMENT)' )
		#	#cur.execute( 'CREATE TABLE IF NOT EXISTS "users" (id INTEGER PRIMARY KEY AUTOINCREMENT)' )
	
	def __init__( self, tablename: str, ending: str, fields: List[SqlBase] ) -> None:
		assert re.match( r'^[a-z][a-z_0-9]+$', tablename )
		
		assert fields, f'no fields defined for table {tablename!r}'
		
		if not hasattr( RepoSqlite, 'database' ):
			RepoSqlite.setup()
		
		super().__init__( tablename, ending, fields )
		if not RepoSqlite.schemas:
			RepoSqlite.setup()
		
		
		self.tablename = tablename
		fldsql: List[str] = []
		fldxtra: List[str] = []
		fldsupp: List[str] = []
		for fld in fields:
			fldsql.append( fld.to_sqlite() )
			fldxtra.extend( fld.to_sqlite_extra() )
			fldsupp.extend( fld.to_sqlite_after( tablename ))
		
		_flds_ = ',\n'.join( fldsql + fldxtra )
		_supp_ = ';\n'.join( fldsupp )
		sql: str = f'CREATE TABLE IF NOT EXISTS "{tablename}" (_flds_); _supp_'
		
		with closing( self.database.cursor() ) as cur:
			cur.execute( sql )
	
	def valid_id( self, id: REPOID ) -> REPOID:
		log = logger.getChild( 'RepoFs.valid_id' )
		log.debug( f'id={id!r}' )
		try:
			id_ = int( id )
		except ValueError as e:
			raise HttpFailure( f'Invalid uuid {id!r}: {e!r}', 400 )
		return id_
	
	def exists( self, id: REPOID ) -> bool:
		assert isinstance( id, int )
		with closing( self.database.cursor() ) as cur:
			cur.execute( f'select count(*) as "qty" from "{self.tablename}" WHERE id = ?', ( id, ) )
			row: Dict[str,int] = cur.fetchone()
		return row['qty'] > 0
	
	def get_by_id( self, id: REPOID ) -> Dict[str,Any]:
		assert isinstance( id, int )
		with closing( self.database.cursor() ) as cur:
			cur.execute( f'select * from "{self.tablename}" WHERE id = ?', ( id, ) )
			item: Dict[str,Any] = cur.fetchone() # TODO FIXME: EOF?
		
		return item
	
	def list( self ) -> Seq[Tuple[int,Dict[str,Any]]]:
		items: Seq[Tuple[int, Dict[str, Any]]]
		
		with closing( self.database.cursor() ) as cur:
			cur.execute( f'select * from "{self.tablename}"' )
			items = cur.fetchall()
		
		return items
	
	def create( self, id: REPOID, resource: Dict[str,Any] ) -> None:
		keys = []
		values = []
		for key, val in resource.items():
			keys.append( key )
			values.append( val )
		
		sql1 = f'SELECT COUNT(*) AS "qty" FROM "{self.tablename}" WHERE "id"=?'
		with closing( self.database.cursor() ) as cur:
			cur.execute( sql1 )
			row = cur.fetchone()
			qty = cast( int, row['qty'] )
			if qty > 0:
				raise HttpFailure( 'resource already exists' )
		
		keys_string = '", "'.join( keys )
		values_string = '", "'.join( values )
		
		query_string = 'INSERT INTO "{}" ("{}") VALUES ("{}")'.format(
			self.tablename,
			keys_string,
			values_string, # <<< TODO FIXME: sql injection attack potential here...
		)
		
		with closing( self.database.cursor() ) as cur:
			cur.execute( query_string )
	
	def update( self, id: REPOID, resource: Dict[str,Any] ) -> Dict[str,Any]:
		values = ', '.join( f'{k}={v}' for k, v in resource.items() ) # TODO FIXME: sql injection vulnerability
		
		query_string = 'UPDATE "{}" SET {} WHERE id="{}"'.format(
			self.tablename,
			values, # <<< TODO FIXME: sql injection attack potential here...
			id,
		)
		
		with closing( self.database.cursor() ) as cur:
			cur.execute( query_string )
		
		return resource
	
	def delete( self, id: REPOID ) -> Dict[str,Any]:
		# delete by id and return deleted dict
		data = self.get_by_id( id )
		
		with closing( self.database.cursor() ) as cur:
			cur.execute( 'DELETE FROM "{}" WHERE id="{}"'.format(
				self.tablename, id
			) )
		
		return data


#endregion repo sqlite
#region repo filesystem


class RepoFs( Repository ):
	base_path: Path
	
	@classmethod
	def setup( cls ) -> None:
		cls.base_path = Path( ITAS_REPOSITORY_FS_PATH )
	
	def __init__( self, tablename: str, ending: str, fields: List[Dict[str,Union[int,str]]] ) -> None:
		if not hasattr( RepoFs, 'base_path' ):
			RepoFs.setup()
		self.type = 'fs'
		self.path = self.base_path / tablename
		self.path.mkdir( mode = 0o770, parents = True, exist_ok = True )
		self.ending = ending
	
	def valid_id( self, id: REPOID ) -> REPOID:
		log = logger.getChild( 'RepoFs.valid_id' )
		log.debug( f'id={id!r}' )
		#try:
		#	_ = uuid.UUID( id )  # TODO FIXME: invalid uuid?
		#except ValueError as e:
		#	raise HttpFailure( f'Invalid uuid {id!r}: {e!r}', 400 )
		return id
	
	def exists( self, id: REPOID ) -> bool:
		itemFile = self._path_from_id( id )
		return itemFile.is_file()
	
	def get_by_id( self, id: REPOID ) -> Dict[str,Any]:
		itemFile = self._path_from_id( id )
		with itemFile.open( 'r' ) as fileContent: # TODO FIXME: this can raise FileNotFoundError
			item: Dict[str,Any] = json.loads( fileContent.read() )
		
		return item
	
	def list( self ) -> List[Tuple[int,Dict[str,Any]]]:
		items: List[Tuple[int, Dict[str, Any]]] = []
		
		for itemFile in self.path.iterdir():
			name = itemFile.name.lower()
			if name.endswith( self.ending ):
				with itemFile.open( 'r' ) as fileContent:
					data = json.loads( fileContent.read() )
					items.append( ( int( itemFile.stem ), data ) )
		
		return items
	
	def create( self, id: REPOID, resource: Dict[str,Any] ) -> None:
		path = self._path_from_id( id )
		if path.is_file():
			raise HttpFailure( 'resource already exists' )
		with path.open( 'w' ) as fileContent:
			fileContent.write( json_dumps( resource ))
	
	def update( self, id: Union[int,str], resource: Dict[str,Any] = {} ) -> Dict[str,Any]:
		print( f"updating {resource}" )
		path = self._path_from_id( id )
		with path.open( 'w' ) as fileContent:
			fileContent.write( json_dumps( resource ))
		
		return resource
	
	def delete( self, id: Union[int,str] ) -> Dict[str,Any]:
		path = self._path_from_id( id )
		with path.open( 'r' ) as fileContent:
			resource: Dict[str,Any] = json.loads( fileContent.read() )
		
		path.unlink()
		
		return resource
	
	def _path_from_id( self, id: Union[int,str] ) -> Path:
		return self.path / f'{id}{self.ending}'


#endregion repo filesystem
#region repo config

REPO_FACTORY: Type[Repository]

# Setup repositories based on config
if ITAS_REPOSITORY_TYPE == 'sqlite':
	REPO_FACTORY = RepoSqlite
elif ITAS_REPOSITORY_TYPE == 'fs':
	REPO_FACTORY = RepoFs
else:
	raise Exception( f'invalid ITAS_REPOSITORY_TYPE={ITAS_REPOSITORY_TYPE!r}' )

REPO_FACTORY_NOFS: Type[Repository] = REPO_FACTORY
if REPO_FACTORY == RepoFs:
	REPO_FACTORY_NOFS = RepoSqlite

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
	#log.debug( 'user_id {!r} -> {!r}'.format( user_id, user ))
	return user

login_manager.setup_app( app )

def try_login( usernm: str, secret: str, remember: bool = False ) -> bool:
	log = logger.getChild( 'try_login' )
	log.debug( 'trying usernm=%r', usernm )
	if usernm and secret and authenticate( usernm, secret ):
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
		'		<input type="text" name="usernm" autofocus/><br/>',
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
def http_reauth() -> Any:
	log = logger.getChild( 'http_reauth' )
	if request.method == 'POST':
		confirm_login()
		return redirect( url_for( 'http_index' ))
	log.warning( 'ToDO FiXME: need to generate reauth html content' )
	return html_page(
		'ToDO FiXME: reauth html content goes here',
	)

@app.route( '/logout' )
def http_logout() -> Any:
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
	for path in map( Path, ITAS_FREESWITCH_SOUNDS ):
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


@app.route( '/dids/', methods = [ 'GET', 'POST' ] )
@login_required # type: ignore
def http_dids() -> Response:
	log = logger.getChild( 'http_dids' )
	return_type = accept_type()
	
	try:
		q_limit = int( request.args.get( 'limit', '' ))
	except ValueError:
		q_limit = 20
	q_limit = clamp( q_limit, 1, 1000 )
	
	try:
		q_offset = int( request.args.get( 'offset', '' ))
	except ValueError:
		q_offset = 0
	q_offset = max( 0, q_offset )
	
	q_did = request.args.get( 'did', '' ).strip()
	q_tf = request.args.get( 'tf', '' ).strip()
	q_acct = request.args.get( 'acct', '' ).strip()
	q_name = request.args.get( 'name', '' ).strip()
	q_notes = request.args.get( 'notes', '' ).strip()
	
	path = Path( ITAS_DIDS_PATH )
	dids: List[Dict[str,Any]] = []
	pattern = f'*{q_did}*.did' if q_did else '*.did'
	files = list( path.glob( pattern ))
	files.sort ( key = lambda file: file.stem )
	skipped = 0
	datadefs: Dict[str,Any] = {
		'acct': '',
		'name': '',
	}
	for file in files:
		data: Dict[str,Any] = {}
		if q_tf or q_acct or q_name or q_notes:
			with file.open( 'r' ) as f:
				try:
					data = cast( Dict[str,Any], json.loads( f.read() ))
				except Exception as e:
					log.error( f'error parsing json of {str(file)!r}: {e!r}' )
					continue
			if q_tf and q_tf not in data.get( 'tollfree', '' ):
				log.debug( f'rejecting {str(file)!r} b/c {q_tf!r} not in {data.get("tollfree","")!r}' )
				continue
			if q_acct and q_acct not in str( data.get( 'acct', '' )):
				log.debug( f'rejecting {str(file)!r} b/c {q_acct!r} not in {data.get("acct","")!r}' )
				continue
			if q_name and q_name not in data.get( 'name', '' ):
				log.debug( f'rejecting {str(file)!r} b/c {q_name!r} not in {data.get("name","")!r}' )
				continue
			if q_notes and q_notes not in data.get( 'notes', '' ):
				log.debug( f'rejecting {str(file)!r} b/c {q_notes!r} not in {data.get("notes","")!r}' )
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
		dids.append( { **datadefs, **data } )
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
	prevpage = urlencode( { 'did': q_did, 'tf': q_tf, 'acct': q_acct, 'name': q_name, 'limit': q_limit, 'offset': max( 0, q_offset - q_limit ) } )
	nextpage = urlencode( { 'did': q_did, 'tf': q_tf, 'acct': q_acct, 'name': q_name, 'limit': q_limit, 'offset': q_offset + q_limit } )
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Prev Page</a></td>',
		'<td align="center">',
		'<a href="/dids/0">(Create new DID)</a>',
		'</td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span class="tooltipped"><input type="text" name="did" placeholder="DID" value="{html_att(q_did)}" maxlength="10" size="10"/><span class="tooltip">Performs substring search of all DIDs</span></span>',
		f'<span class="tooltipped"><input type="text" name="tf" placeholder="TF#" value="{html_att(q_tf)}" maxlength="10" size="10"/><span class="tooltip">Performs substring search of all TF #s</span></span>',
		f'<span class="tooltipped"><input type="text" name="acct" placeholder="Acct#" value="{html_att(q_acct)}" maxlength="4" size="4"/><span class="tooltip">Performs substring search of all Account #s</span></span>',
		f'<span class="tooltipped"><input type="text" name="name" placeholder="Name" value="{html_att(q_name)}" size="10"/><span class="tooltip">Performs substring search of all Account Names</span></span>',
		f'<span class="tooltipped"><input type="text" name="notes" placeholder="Notes" value="{html_att(q_notes)}" size="10"/><span class="tooltip">Performs substring search of all Account Names</span></span>',
		'<input type="submit" value="Search"/>',
		'<button id="clear" type="button" onclick="window.location=\'?\'">Clear</button>'
		'</form>',
		'</td>',
		f'<td align="right"><a href="?{nextpage}">Next Page</a></td>',
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
		category = data.get( 'category', '' )
	except Exception as e4:
		raise ValidationError( f'invalid Category: {e4!r}' ) from None
	if category:
		data2['category'] = category
	
	try:
		route = int( data.get( 'route', '0' ))
	except Exception as e5:
		raise ValidationError( f'invalid Route: {e5!r}' ) from None
	if route <= 0:
		raise ValidationError( 'route must be an integer > 0' )
	data2['route'] = route
	
	try:
		flag = data.get( 'flag', '' )
	except Exception as e6:
		raise ValidationError( f'invalid Flag: {e6!r}' ) from None
	if flag:
		data2['flag'] = flag
	
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
	auditdata = ''.join (
		f'\n\t{k}={v!r}' for k, v in data2.items() if v != ''
	)
	if did:
		audit( f'Changed DID {did}:{auditdata}' )
	else:
		if path.exists():
			raise ValidationError( f'DID already exists: {did2}' )
		audit( f'Created DID {did2}:{auditdata}' )
	with path.open( 'w' ) as f:
		print( json_dumps( data2 ), file = f )
	
	return did2

@app.route( '/dids/<int:did>', methods = [ 'GET', 'POST', 'DELETE' ] )
@login_required # type: ignore
def http_did( did: int ) -> Response:
	log = logger.getChild( 'http_did' )
	return_type = accept_type()
	path = did_file_path( did )
	
	if request.method == 'DELETE':
		if not path.is_file():
			return _http_failure( return_type, 'DID not found', 404 )
		try:
			path.unlink()
		except Exception as e1:
			return _http_failure( return_type, repr( e1 ), 500 )
		else:
			audit( f'Deleted DID {did}' )
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
	
	tollfree = data.get( 'tollfree', '' )
	acct = data.get( 'acct', '' ) or ''
	name = data.get( 'name', '' )
	category = data.get( 'category', '' )
	route = to_optional_int( data.get( 'route', '' ) or None )
	variables = data.get( 'variables', '' )
	flag = data.get( 'flag', '' )
	notes = data.get( 'notes', '' )
	
	html_rows = [
		'<form method="POST" enctype="application/x-www-form-urlencoded">',
	]
	if not did:
		did_html = f'<input type="text" name="did" value="{html_att(data.get("did",""))}" size="11" maxlength="10"/>'
	else:
		did_html = html_text( str( did ))
	
	category_options: List[str] = [ '<option value="">(None)</option>' ]
	for cat in ITAS_DID_CATEGORIES:
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
	
	route_options: List[str] = []
	for r, routedata in routes:
		att = ' selected' if route == r else ''
		lbl = routedata.get( 'name' ) or '(Unnamed)'
		route_options.append( f'<option value="{r}"{att}>{r} {lbl}</option>' )
	
	html_rows.extend( [
		
		'<table class="unpadded"><tr><td valign="top">',
		f'<b>DID:</b><br/>{did_html}',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Toll Free #:</b><br/><input type="text" name="tollfree" value="{html_att(str(tollfree))}" size="15" maxlength="15"/><br/><br/>',
		'</td></tr></table>',
		
		'<table class="unpadded"><tr><td valign="top">',
		f'<b>Account #:</b><br/><input type="text" name="acct" value="{html_att(str(acct))}" size="5" maxlength="4"/><br/><br/>',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Client Name:</b><br/><input type="text" name="name" value="{html_att(name)}" size="31" maxlength="30"/><br/><br/>',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Category:</b><br/><select name="category">{"".join(category_options)}</select>',
		'</td></tr></table>',
		
		'<table class="unpadded"><tr><td valign="top">',
		f'<b>Route:</b><br/><select name="route">{"".join(route_options)}</select>',
		'</td><td>&nbsp;</td><td valign="top">',
		f'<b>Flag:</b><br/><span class="tooltipped"><input type="text" name="flag" value="{html_att(str(flag))}" size="31" maxlength="30"/><span class="tooltip">Overrides preannounce calculations</span></span>',
		'</td></tr></table>',
		'<br/>',
	])
	
	for field in ITAS_DID_FIELDS:
		x = f'<b>{field.label}</b><br/>'
		if field.tooltip:
			x += '<span class="tooltipped">'
		atts = ''
		if field.max_length:
			atts += f' size="{field.max_length+1!r}" maxlength="{field.max_length!r}"'
		value: Union[None,int,str] = data.get( field.field, None )
		value = str( value ) if value is not None else ''
		x += f'<input type="text" name="{field.field}" value="{html_att(value)}"{atts}/>'
		if field.tooltip:
			x += f'<span class="tooltip">{field.tooltip}</span></span>'
		x += '<br/><br/>'
		html_rows.append( x )
	
	variables_examples = '\n'.join ( ITAS_DID_VARIABLES_EXAMPLES )
	
	html_rows.extend( [
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
	html_rows.extend( [
		f'<input type="submit" value="{html_att(submit)}"/>',
		'&nbsp;&nbsp;&nbsp;',
		f'<button onclick="{cloneaction}" type="button" class="clone">Clone</button>' if did else '',
		'&nbsp;&nbsp;&nbsp;',
		'<button id="delete" class="delete">Delete</button>' if did else '',
		'<br/><br/>',
		f'<font color="red">{err}</font>',
		'<script src="/did.js"></script>',
		'</form>',
	] )
	return html_page( *html_rows )


#endregion http - DID
#region http - ANI


@app.route( '/anis/', methods = [ 'GET', 'POST' ] )
@login_required # type: ignore
def http_anis() -> Response:
	#log = logger.getChild( 'http_anis' )
	return_type = accept_type()
	
	try:
		limit = int( request.args.get( 'limit', '' ))
	except ValueError:
		limit = 20
	limit = clamp( limit, 1, 1000 )
	
	try:
		offset = int( request.args.get( 'offset', '' ))
	except ValueError:
		offset = 0
	offset = max( 0, offset )
	
	search = request.args.get( 'search', '' )
	path = Path( ITAS_ANIS_PATH )
	anis: List[Dict[str,int]] = []
	pattern = f'*{search}*.ani' if search else '*.ani'
	for f in path.glob( pattern ):
		anis.append( { 'ani': int( f.stem ) } )
	anis.sort ( key = lambda d: d['ani'] )
	anis = anis[offset:offset + limit]
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
	prevpage = urlencode( { 'search': search, 'limit': limit, 'offset': max( 0, offset - limit ) } )
	nextpage = urlencode( { 'search': search, 'limit': limit, 'offset': offset + limit } )
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Prev Page</a></td>',
		'<td align="center">',
		'<a href="/anis/0">(Create new ANI)</a>',
		'</td>',
		'<td align="center">'
		'<form method="GET">'
		f'<span class="tooltipped"><input type="text" name="search" placeholder="ANI" value="{html_att(search)}"/><span class="tooltip">Performs substring search of all ANIs</span></span>',
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
	auditdata = ''.join (
		f'\n\t{k}={v!r}' for k, v in data2.items() if v != ''
	)
	if ani:
		audit( f'Changed ANI {ani}:{auditdata}' )
	else:
		if path.exists():
			raise ValidationError( f'ANI already exists: {ani2}' )
		audit( f'Created ANI {ani2}:{auditdata}' )
	with path.open( 'w' ) as f:
		print( json_dumps( data2 ), file = f )
	
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
			audit( f'Deleted ANI {ani}' )
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
	
	html_rows.extend( [
		f'<b>ANI:</b><br/>{ani_html}<br/><br/>',
		
		f'<b>Route:</b><br/><span class="tooltipped"><select name="route">{"".join(route_options)}</select><span class="tooltip">Selecting a Route here will reroute this ANI no matter what DID is called</span></span><br/><br/>',
	])
	
	overrides_examples = '\n'.join ( ITAS_ANI_OVERRIDES_EXAMPLES )
	
	html_rows.extend( [
		'<table class="unpadded"><tr><td valign="top">',
		'<b>DID Overrides:</b><br/>',
		f'<span class="tooltipped"><textarea name="overrides" cols="80" rows="4">{html_text(overrides)}</textarea><span class="tooltip">Use this section to block/redirect this ANI for specific DIDs</span></span><br/><br/>',
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


@app.route( '/flags', methods = [ 'GET', 'POST' ] )
@login_required # type: ignore
def http_flags() -> Response:
	#log = logger.getChild ( 'http_flags' )
	return_type = accept_type()
	
	if request.method == 'POST':
		data = inputs()
		name = data['name']
		value = data['value']
		
		with flag_file_path( name ).open ( 'w' ) as f:
			audit( f'Set flag {name}={value!r}' )
			print( value, file = f )
		
		if return_type == 'application/json':
			return rest_success( [] )
	
	h: List[str] = []
	def flag_form ( name: str, label: str ) -> None:
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
	
	flag_form( 'global_flag', 'Global Flag:' )
	for cat in ITAS_DID_CATEGORIES:
		flag_form( f'category_{cat}', f'Category: {cat}' )
	
	return html_page(
		*h
	)


#endregion http - flags
#region http - routes

REPO_ROUTES = REPO_FACTORY( 'routes', '.route', [
	SqlInteger( 'id', null = False, size = 10, auto = True, primary = True ),
	SqlText( 'name', null = True ),
	SqlJson( 'json', null = False ),
])

@app.route( '/routes', methods = [ 'GET', 'POST', 'DELETE' ] )
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
			REPO_ROUTES.create( route, { 'name': '', 'nodes': [] } )
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
	
	# BEGIN route list
	try:
		routes = list( REPO_ROUTES.list() )
	except Exception as e:
		#raise e
		return _http_failure(
			return_type,
			f'Error querying routes list: {e!r}',
			500,
		)
	routes.sort( key = lambda kv: kv[0] )
	if return_type == 'application/json':
		return rest_success( [ { 'route': id, 'name': route.get( 'name' ) } for id, route in routes ] )
	
	# TODO FIXME: pagination anyone?
	
	row_html = '\n'.join( [
		'<tr>',
			'<td><a href="{url}">{route}</a></td>',
			'<td><a href="{url}">{name}</a></td>',
			'<td><button class="delete" route="{route}">Delete {route} {name}</button></td>',
		'</tr>',
	] )
	body = '\n'.join( [
		row_html.format( route = route, url = url_for( 'http_route', route = route ), **data )
		for route, data in routes
	] )
	return html_page(
		'<center><a id="route_new" href="#">(New Route)</a></center>',
		'<table border=1>',
		'<tr><th>Route</th><th>Name</th><th>Delete</th></tr>',
		body,
		'</table>',
		#'<script src="/aimara/lib/Aimara.js"></script>',
		'<script type="module" src="routes.js"></script>',
	)
	# END route list

route_id_html = '''
<table border="0">
	<tr>
		<td class="tree"><div id="div_tree"></div></td>
		<td class="help">
			<div id="div_help">
				This is the Route Editor.<br/>
				<br/>
				Please click on a node to select it and see more details about
				it.<br/>
				<br/>
				Or try right-clicking on a node for more options.
			</div>
		</td>
	</tr>
</table>

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
		
		id_ = REPO_ROUTES.valid_id( route )
		
		if request.method == 'GET':
			data = REPO_ROUTES.get_by_id( id_ )
			return rest_success( [ data ] )
		elif request.method == 'PATCH':
			data = inputs()
			log.debug( data )
			REPO_ROUTES.update( route, data )
			return rest_success( [ data ] )
		elif request.method == 'DELETE':
			return route_delete( route )
		else:
			return rest_failure( f'request method {request.method} not implemented yet', 405 )
	except HttpFailure as e:
		return _http_failure(
			return_type,
			e.error,
			e.status_code,
		)

def route_delete( route: int ) -> Response:
	# check if route even exists:
	if not REPO_ROUTES.exists( route ):
		raise HttpFailure( f'Route {route!r} does not exist', 404 )
	
	# check if route is referenced by any DID
	for file in Path( ITAS_DIDS_PATH ).glob( '*.did' ):
		with file.open( 'r' ) as f:
			did = json.load( f )
		if route == did['route']:
			raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by DID {file.stem}' )
	
	# check if route is referenced by ani ANI
	for file in Path( ITAS_ANIS_PATH ).glob( '*.ani' ):
		with file.open( 'r' ) as f:
			ani =json.load( f )
		if route == ani.get( 'route' ):
			raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by ANI {file.stem}' )
		overrides = ani.get( 'overrides' ) or ''
		for line in overrides.split( '\n' ):
			parts = re.split( r'\s+', line )
			if len( parts ) >= 2:
				try:
					override_route = int( parts[1] )
				except ValueError:
					pass
				else:
					if route == override_route:
						raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by ANI {file.stem}' )
	
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
	for file in voicemail_settings_path( 1 ).parent.glob( '*.box' ):
		with file.open( 'r' ) as f:
			box_settings = json.load( f )
		if walk_json_dicts( box_settings, json_dict_route_check ):
			raise HttpFailure( f'Cannot delete route {route!r} - it is referenced by voicemail box {file.stem}' )
	
	REPO_ROUTES.delete( route )
	return rest_success( [] )

#endregion http - routes
#region http - voicemail


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
		
		path = voicemail_settings_path( box )
		if path.is_file():
			return _http_failure(
				return_type,
				f'voicemail box number {box!r} already exists',
				400,
			)
		
		digits = list( '1234567890' )
		random.shuffle( digits )
		settings = {
			'pin': digits[:8],
			'max_greeting_seconds': 120, # TODO FIXME: system default?
			'max_message_seconds': 120, # TODO FIXME: system default?
			'allow_guest_urgent': True,
			'post_save': [],
		}
		with path.open( 'w' ) as f:
			f.write( json_dumps( settings ))
		
		if return_type == 'application/json':
			return rest_success( [ { 'box': box } ] )
		
		url = url_for( 'http_voicemail', box = box )
		log.warning( 'url=%r', url )
		return redirect( url )
		# END voicemail box creation
	
	# BEGIN voicemail boxes list
	try:
		path = voicemail_settings_path( '*' )
		boxes: List[Dict[str,Any]] = []
		for box_path in path.parent.glob( path.name ):
			with box_path.open( 'r' ) as f:
				settings = json.loads( f.read() )
			boxes.append( { 'box': int( box_path.stem ), 'name': '(Unnamed)', **settings } )
	except Exception as e:
		return _http_failure(
			return_type,
			f'Error querying voicemail boxes list: {e!r}',
			500,
		)
	if return_type == 'application/json':
		return rest_success( boxes )
	
	# TODO FIXME: pagination anyone?
	
	row_html = '\n'.join( [
		'<tr>',
			'<td><a href="{url}">{box}</a></td>',
			'<td><a href="{url}">{name}</a></td>',
			'<td><button class="delete" box="{box}">Delete {box} {name}</button></td>',
		'</tr>',
	] )
	body = '\n'.join( [
		row_html.format(
			url = url_for( 'http_voicemail', box = box['box'] ),
			**box
		) for box in boxes
	] )
	return html_page(
		'<center><a id="box_new" href="#">(New Voicemail Box)</a></center>',
		'<table border=1>',
		'<tr>',
			'<th>Box</th>',
			'<th>Name</th>',
			'<th>Delete</th>',
		'</tr>',
		body,
		'</table>',
		'<script type="module" src="voicemails.js"></script>',
	)
	# END voicemail boxes list

voicemail_id_html = '''
<table border="0">
	<tr>
		<td class="tree"><div id="div_tree"></div></td>
		<td class="help">
			<div id="div_help">
				This is the Voicemail Box Editor.<br/>
				<br/>
				Please click on a node to select it and see more details about
				it.<br/>
				<br/>
				Or try right-clicking on a node for more options.
			</div>
		</td>
	</tr>
</table>

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
		
		path = voicemail_settings_path( box )
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
			with path.open( 'w' ) as f:
				f.write( json_dumps( settings ))
			return rest_success( [ settings ] )
		elif request.method == 'DELETE':
			msgs_path = voicemail_box_msgs_path( box )
			log.warning( f'msgs_path={msgs_path!r}' )
			if msgs_path.exists():
				try:
					shutil.rmtree( str( msgs_path ))
				except OSError as e1:
					log.exception( 'Could not delete box %r messages:', box )
					return rest_failure( f'Could not delete box {box!r} messages: {e1!r}' )
			
			greetings_path = voicemail_greeting_path( box, 1 ).parent
			log.warning( f'greetings_path={greetings_path!r}' )
			if greetings_path.exists():
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
#region http - audits


@app.route( '/audit' )
@login_required # type: ignore
def http_audit_list() -> Any:
	return_type = accept_type()
	
	try:
		limit = int( request.args.get( 'limit', '' ))
	except ValueError:
		limit = 20
	limit = clamp( limit, 1, 1000 )
	
	try:
		offset = int( request.args.get( 'offset', '' ))
	except ValueError:
		offset = 0
	offset = max( 0, offset )
	
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
	logfile_list = logfile_list[offset:offset + limit]
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
	
	prevpage = urlencode( { 'limit': limit, 'offset': max( 0, offset - limit ) } )
	nextpage = urlencode( { 'limit': limit, 'offset': offset + limit } )
	return html_page(
		'<table width="100%"><tr>',
		f'<td align="left"><a href="?{prevpage}">Newer Logs</a></td>',
		f'<td align="right"><a href="?{nextpage}">Older Logs</a></td>',
		'</tr></table>',
		'<table class="fancy">',
		'<tr><th>Log File</th></tr>',
		body,
		'</table>',
	)

@app.route( '/audit/<filename>' )
@login_required # type: ignore
def http_audit_item( filename: str ) -> Any:
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
#region bootstrap


if __name__ == '__main__':
	if os.name == 'posix':
		journald_handler = JournaldLogHandler()
		journald_handler.setFormatter(
			logging.Formatter( '[%(levelname)s] %(message)s' )
		)
		logger.addHandler( journald_handler )
	
	logging.basicConfig( level = logging.DEBUG )
	cmd = sys.argv[1] if len( sys.argv ) > 1 else ''
	if cmd:
		sys.exit( service_command( cmd ))
	login_manager.init_app( app )
	
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
