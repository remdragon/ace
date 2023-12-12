#region imports

from __future__ import annotations

# stdlib imports:
from abc import ABCMeta, abstractmethod
import asyncio
from contextlib import closing, contextmanager
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
from types import TracebackType
from typing import (
	Any, Callable, cast, Iterator, Optional as Opt, Sequence as Seq, Tuple,
	Type, Union,
)
import uuid

# 3rd-party imports:
import psycopg2 # pip install psycopg2
from typing_extensions import Literal, TypeAlias # pip install typing_extensions

if __name__ == '__main__':
	sys.path.append( 'incpy' )

# incpy imports
from safe_exit import safe_exit

# local imports:
import auditing
from chown import chown

#endregion imports
#region globals/exceptions

logger = logging.getLogger( __name__ )

class ResourceAlreadyExists( Exception ):
	pass

class ResourceNotFound( Exception ):
	pass

def json_dumps( data: Any ) -> str:
	return json.dumps( data, indent = '\t', separators = ( ',', ': ' ))

#endregion globals/exceptions
#region connector


class Connector:
	pg_conns: dict[str,psycopg2.connection]
	sqlite_conns: dict[str,sqlite3.Connection]
	
	def __enter__( self ) -> Connector:
		self.pg_conns = {}
		self.sqlite_conns = {}
		return self
	
	@safe_exit
	def __exit__( self,
		exc_type: Opt[Type[BaseException]],
		exc_val: Opt[BaseException],
		exc_tb: Opt[TracebackType],
	) -> Literal[False]:
		log = logger.getChild( 'Connector.__exit__' )
		
		for pgcon in self.pg_conns.values():
			try:
				pgcon.close()
			except Exception:
				log.exception( 'Error closing postgres connection:' )
		del self.pg_conns
		
		for sql3con in self.sqlite_conns.values():
			try:
				sql3con.close()
			except Exception:
				log.exception( 'Error closing sqlite3 connection:' )
		del self.sqlite_conns
		
		return False
	
	def postgres( self,
		host: str,
		database: str,
		user: str,
		password: str,
		port: int,
		sslmode: Opt[Literal['disable','allow','prefer','require','verify-ca','verify-full']],
		sslrootcert: Opt[Path],
	) -> psycopg2.connection:
		assert hasattr( self, 'pg_conns' ), 'Attempt to use Connector outside of with context'
		key = f'{host}:{port}:{database}'
		conn = self.pg_conns.get( key )
		if conn is None:
			conn = psycopg2.connect(
				host = host,
				database = database,
				user = user,
				password = password,
				port = port,
				sslmode = sslmode,
				sslrootcert = sslrootcert,
			)
			self.pg_conns[key] = conn
		return conn
	
	def sqlite( self, path: str ) -> sqlite3.Connection:
		assert hasattr( self, 'sqlite_conns' ), 'Attempt to use Connector outside of with context'
		conn = self.sqlite_conns.get( path )
		if conn is None:
			conn = sqlite3.connect( path )
			setattr( conn, 'row_factory', dict_factory )
			self.sqlite_conns[path] = conn
		return conn


#endregion connector
#region repo base


REPOID: TypeAlias = Union[int,str]
PGSQL_SSLMODE: TypeAlias = Opt[Literal['disable','allow','prefer','require','verify-ca','verify-full']]


@dataclass
class Config:
	fs_path: Opt[Path] = None
	sqlite_path: Opt[Path] = None
	pgsql_host: Opt[str] = None
	pgsql_db: Opt[str] = None
	pgsql_uid: Opt[str] = None
	pgsql_pwd: Opt[str] = None
	pgsql_port: Opt[int] = None
	pgsql_sslmode: Opt[PGSQL_SSLMODE] = None
	pgsql_sslrootcert: Opt[Path] = None


class SqlBase( metaclass = ABCMeta ):
	def __init__( self, name: str, *,
		null: bool,
		primary: bool = False,
		unique: bool = False,
		index: bool = False,
	) -> None:
		for invalid in ( '"', "'", '`', '[', ']' ):
			assert invalid not in name, f'invalid character {invalid!r} in name {name!r}'
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
	
	def to_sqlite_extra( self ) -> list[str]:
		# this is used to create extra entries inside the create table statement
		return []
	
	def to_sqlite_after( self, table: str ) -> list[str]:
		# this is used to create supplemental entries after the create table statement
		sql: list[str] = []
		if self.index:
			sql.append( 'CREATE INDEX "idx_{table}_{self.name}" ON "{table}" ({self.name})' )
		return sql
	
	@abstractmethod
	def to_postgres( self ) -> str:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__qualname__}.to_sqlite()' )
	
	def to_postgres_extra( self ) -> list[str]:
		# this is used to create extra entries inside the create table statement
		return []
	
	def to_postgres_after( self, table: str ) -> list[str]:
		# this is used to create supplemental entries after the create table statement
		sql: list[str] = []
		if self.index:
			sql.append( 'CREATE INDEX "idx_{table}_{self.name}" ON "{table}" ({self.name})' )
		return sql
	
	def encode_postgres( self, val: Any ) -> Any:
		return val
	def decode_postgres( self, val: Any ) -> Any:
		return val


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
		sql: list[str] = [
			self.name,
			f'VARCHAR({self.size})',
			'NULL' if self.null else 'NOT NULL',
			'PRIMARY KEY' if self.primary else '',
			'UNIQUE' if self.unique else '',
			'COLLATE NOCASE',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		sql: list[str] = [
			f'"{self.name}"',
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
		sql: list[str] = [
			self.name,
			'TEXT', # sqlite doesn't have a DATETIME type
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		sql: list[str] = [
			f'"{self.name}"',
			'timestamptz',
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
		sql: list[str] = [
			self.name,
			'INTEGER' if self.auto else f'INTEGER({self.size})', # sqlite doesn't like (size) for autoinc fields,
			'NULL' if self.null else 'NOT NULL',
			'PRIMARY KEY' if self.primary else '',
			'UNIQUE' if self.unique else '',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		if self.size <= 4:
			typename: str = 'SMALLSERIAL' if self.auto else 'SMALLINT'
		elif self.size <= 9:
			typename = 'SERIAL' if self.auto else 'INTEGER'
		elif self.size <= 18:
			typename = 'BIGSERIAL' if self.auto else 'BIGINT'
		else:
			assert not self.auto, f'size {self.size!r} too big for auto={self.auto!r}'
			typename = f'NUMERIC({self.size})'
		sql: list[str] = [
			f'"{self.name}"',
			typename,
			'NULL' if self.null else 'NOT NULL',
			'PRIMARY KEY' if self.primary else '',
			'UNIQUE' if self.unique else '',
		]
		return ' '.join( filter( None, sql ))


class SqlFloat( SqlBase ):
	def __init__( self, name: str, *,
		null: bool,
		index: bool = False,
	) -> None:
		super().__init__( name,
			null = null,
			index = index,
		)
	
	def validate( self ) -> None:
		pass
	
	def to_sqlite( self ) -> str:
		sql: list[str] = [
			self.name,
			'FLOAT',
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		sql: list[str] = [
			f'"{self.name}"',
			'FLOAT',
			'NULL' if self.null else 'NOT NULL',
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
		sql: list[str] = [
			self.name,
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
			'COLLATE NOCASE',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		sql: list[str] = [
			f'"{self.name}"',
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
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
		sql: list[str] = [
			self.name,
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		sql: list[str] = [
			f'"{self.name}"',
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))
	
	def encode_postgres( self, val: Any ) -> Any:
		return json.dumps( val )
	def decode_postgres( self, val: Any ) -> Any:
		return json.loads( val ) if val is not None else None


class SqlBool( SqlBase ):
	def __init__( self, name: str, *,
		null: bool,
	) -> None:
		super().__init__( name, null = null )
	
	def validate( self ) -> None:
		pass
	
	def to_sqlite( self ) -> str:
		sql: list[str] = [
			self.name,
			'BOOL',
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))
	
	def to_postgres( self ) -> str:
		sql: list[str] = [
			f'"{self.name}"',
			'BOOL',
			'NULL' if self.null else 'NOT NULL',
		]
		return ' '.join( filter( None, sql ))


class Repository( metaclass = ABCMeta ):
	type = 'Abstract repository'
	schemas: dict[str,list[SqlBase]] = {}
	
	def __init__( self,
		config: Config,
		tablename: str,
		ending: str,
		fields: list[SqlBase],
		owner_user: str,
		owner_group: str,
		*,
		auditing: bool = True,
		keyname: str = 'id',
	) -> None:
		assert tablename not in Repository.schemas, f'duplicate schema definition for table {tablename!r}'
		Repository.schemas[tablename] = fields
		self.tablename = tablename
		self.ending = ending
		self.auditing = auditing
		self.keyname = keyname
		self.fields: dict[str,SqlBase] = {
			field.name: field for field in fields
		}
	
	@abstractmethod
	def valid_id( self, id: REPOID ) -> REPOID:
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.valid_id' )
	
	@abstractmethod
	def exists( self, ctr: Connector, id: REPOID ) -> bool:
		# does the indicated id exist?
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.exists' )
	
	@abstractmethod
	def get_by_id( self, ctr: Connector, id: REPOID ) -> dict[str, Any]:
		# Return single dictionary by id
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.get_by_id' )
	
	@abstractmethod
	def list( self,
		ctr: Connector,
		filters: dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, dict[str, Any]]]:
		# Return all dictionaries of type
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.list' )
	
	@abstractmethod
	def create( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> None:
		# Persist new dictionary and return it
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.create' )
	
	@abstractmethod
	def update( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> dict[str,Any]:
		# Update by id and return updated dict
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.update' )
	
	@abstractmethod
	def delete( self, ctr: Connector, id: REPOID, *, audit: auditing.Audit ) -> dict[str,Any]:
		# delete by id and return deleted dict
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.delete' )

repo_types: dict[str,Type[Repository]] = {}

def repo_type( name: str ) -> Callable[[Type[Repository]],Type[Repository]]:
	def _decorator( cls: Type[Repository] ) -> Type[Repository]:
		global repo_types
		assert name not in repo_types, f'duplicate repo type name={name!r}'
		repo_types[name] = cls
		return cls
	return _decorator

def from_type( name: str ) -> Type[Repository]:
	global repo_types
	cls: Type[Repository] = repo_types[name]
	return cls

def auditdata_from_update( olddata: dict[str,Any], newdata: dict[str,Any] ) -> str:
	keys = set( olddata.keys() ) | set( newdata.keys() )
	auditlines: list[str] = []
	for key in sorted( keys ):
		oldval = olddata.get( key, '' )
		newval = newdata.get( key, '' )
		if oldval != newval:
			auditlines.append( f'\t{key}: {oldval!r} -> {newval!r}' )
		else:
			auditlines.append( f'\t{key}: {oldval!r} (unchanged)' )
	return '\n'.join( auditlines )

#endregion repo base
#region repo sqlite


def dict_factory( cursor: Any, row: Seq[Any] ) -> dict[str,Any]:
	d: dict[str,Any] = {}
	for idx, col in enumerate( cursor.description ):
		d[col[0]] = row[idx]
	return d

@repo_type( 'sqlite' )
class RepoSqlite( Repository ):
	type = 'sqlite'
	sqlite_path: Path
	tls = threading.local()
	
	@classmethod
	def setup( cls, config: Config ) -> None:
		assert config.sqlite_path is not None, 'repo.Config.sqlite_path not set'
		sqlite_path = Path( config.sqlite_path )
		if not sqlite_path.exists():
			sqlite_path.touch()
		cls.sqlite_path = sqlite_path
	
	def __init__( self,
		config: Config,
		tablename: str,
		ending: str,
		fields: list[SqlBase],
		owner_user: str,
		owner_group: str,
		*,
		auditing: bool = True,
		keyname: str = 'id',
	) -> None:
		assert re.match( r'^[a-z][a-z_0-9]+$', tablename )
		
		assert fields, f'no fields defined for table {tablename!r}'
		
		if not hasattr( RepoSqlite, 'sqlite_path' ):
			RepoSqlite.setup( config )
		
		super().__init__(
			config, tablename, ending, fields, owner_user, owner_group,
			auditing = auditing,
			keyname = keyname,
		)
		#if not RepoSqlite.schemas:
		#	RepoSqlite.setup( config )
		
		fldsql: list[str] = []
		fldxtra: list[str] = []
		fldsupp: list[str] = []
		for fld in fields:
			fldsql.append( fld.to_sqlite() )
			fldxtra.extend( fld.to_sqlite_extra() )
			fldsupp.extend( fld.to_sqlite_after( tablename ))
		
		_flds_ = ',\n'.join( fldsql + fldxtra )
		sql: list[str] = [ f'CREATE TABLE IF NOT EXISTS "{tablename}" ({_flds_});' ]
		sql.extend( fldsupp )
		
		with Connector() as ctr:
			conn = self.connect( ctr )
			with closing( conn.cursor() ) as cur:
				for sql_ in sql:
					cur.execute( sql_ )
		conn.commit()
	
	def connect( self, ctr: Connector ) -> sqlite3.Connection:
		return ctr.sqlite( str( self.sqlite_path ))
	
	def valid_id( self, id: REPOID ) -> REPOID:
		log = logger.getChild( 'RepoSqlite.valid_id' )
		
		if not isinstance( id, int ):
			if isinstance( id, str ) and id.isnumeric():
				return int( id )
			try:
				_ = uuid.UUID( id )  # TODO FIXME: invalid uuid?
			except ValueError as e:
				raise ValueError( f'Invalid uuid {id!r}: {e!r}' ).with_traceback( e.__traceback__ ) from None
		return id
	
	def exists( self, ctr: Connector, id: REPOID ) -> bool:
		assert isinstance( id, ( int, str )), f'invalid id={id!r}'
		conn: sqlite3.Connection = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			cur.execute( f'select count(*) as "qty" from "{self.tablename}" WHERE "{self.keyname}" = ?', ( id, ) )
			row: dict[str,int] = cur.fetchone()
		return row['qty'] > 0
	
	def get_by_id( self, ctr: Connector, id: REPOID ) -> dict[str,Any]:
		assert isinstance( id, ( int, str )), f'invalid id={id!r}'
		conn = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			cur.execute( f'select * from "{self.tablename}" WHERE "{self.keyname}" = ?', [ id ])
			item: Opt[dict[str,Any]] = cur.fetchone() # TODO FIXME: EOF?
		if item is None:
			raise ResourceNotFound( id )
		return item
	
	def list( self,
		ctr: Connector,
		filters: dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, dict[str, Any]]]:
		params: list[str] = []
		if filters:
			wheres: list[str] = []
			for k, v in filters.items():
				wheres.append( f'"{k}" like ?' )
				params.append( f'%{str(v).replace("%","%%")}%' )
			_where_ = f'where {" and ".join(wheres)}'
		else:
			_where_ = ''
		
		paging: list[str] = []
		if limit or offset:
			paging.append( f'limit {int(limit or -1)!r}' )
			if offset:
				paging.append( f'offset {int(offset or 0)!r}' )
		_paging_ = ' '.join( paging )
		
		orderby = orderby.strip() or self.keyname
		assert '"' not in orderby, f'invalid orderby={orderby!r}'
		direction = 'desc' if reverse else 'asc'
		sql = f'select * from "{self.tablename}" {_where_} order by "{orderby}" {direction} {_paging_}'
		items: list[Tuple[REPOID,dict[str,Any]]] = []
		conn: sqlite3.Connection = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			cur.execute( sql, params )
			for row in cur.fetchall():
				id = row.pop( self.keyname )
				items.append(( id, row ))
		
		return items
	
	def create( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> None:
		sql1 = f'SELECT COUNT(*) AS "qty" FROM "{self.tablename}" WHERE "{self.keyname}"=?'
		conn: sqlite3.Connection = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			cur.execute( sql1, [ id ] )
			row = cur.fetchone()
			qty = cast( int, row['qty'] )
			if qty > 0:
				raise ResourceAlreadyExists()
		
		keys: list[str] = []
		values: list[str] = []
		params: list[Any] = []
		for key, val in resource.items():
			assert '"' not in key, f'invalid key={key!r}'
			keys.append( f'"{key}"' )
			values.append( '?' )
			params.append( val )
		
		_keys_ = ','.join( keys )
		_values_ = ','.join( values )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'INSERT INTO "{self.tablename}" ({_keys_}) VALUES ({_values_});'
		
		with closing( conn.cursor() ) as cur:
			cur.execute( sql, params )
		
		conn.commit()
		
		if self.auditing:
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in resource.items()
				if v not in ( None, '' )
			)
			audit.audit( f'Created {self.tablename} {id!r}:{auditdata}' )
	
	def update( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> dict[str,Any]:
		values: list[str] = []
		params: list[Any] = []
		for k, v in resource.items():
			values.append( f'{k}=?' )
			params.append( v )
		_values_ = ','.join( values )
		
		olddata = self.get_by_id( ctr, id )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'UPDATE "{self.tablename}" SET {_values_} WHERE "{self.keyname}"=?'
		params.append( id )
		
		conn: sqlite3.Connection = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			cur.execute( sql, params )
		conn.commit()
		
		if self.auditing:
			auditdata = auditdata_from_update( olddata, resource )
			audit.audit( f'Updated {self.tablename} {id!r}:{auditdata}' )
		
		return resource
	
	def delete( self, ctr: Connector, id: REPOID, *, audit: auditing.Audit ) -> dict[str,Any]:
		# delete by id and return deleted dict
		data = self.get_by_id( ctr, id )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'DELETE FROM "{self.tablename}" WHERE "{self.keyname}"=?;'
		
		conn: sqlite3.Connection = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			cur.execute( sql, [ id ])
		conn.commit()
		
		if self.auditing:
			audit.audit( f'Deleted {self.tablename} {id!r}' )
		
		return data


#endregion repo sqlite
#region repo postgres

@repo_type( 'postgres' )
class RepoPostgres( Repository ):
	type = 'postgres'
	tls = threading.local()
	pgsql_host: str
	pgsql_db: str
	pgsql_uid: str
	pgsql_pwd: str
	pgsql_port: int = 5432
	pgsql_sslmode: Opt[Literal['disable','allow','prefer','require','verify-ca','verify-full']] = None
	pgsql_sslrootcert: Opt[Path] = None
	
	@classmethod
	def setup( cls, config: Config ) -> None:
		assert config.pgsql_host is not None, 'repo.Config.pgsql_host not set'
		cls.pgsql_host = config.pgsql_host
		assert config.pgsql_db is not None, 'repo.Config.pgsql_db not set'
		cls.pgsql_db = config.pgsql_db
		assert config.pgsql_uid is not None, 'repo.Config.pgsql_uid not set'
		cls.pgsql_uid = config.pgsql_uid
		assert config.pgsql_pwd is not None, 'repo.Config.pgsql_pwd not set'
		cls.pgsql_pwd = config.pgsql_pwd
		if config.pgsql_port:
			cls.pgsql_port = config.pgsql_port
		cls.pgsql_sslmode = config.pgsql_sslmode
		cls.pgsql_sslrootcert = config.pgsql_sslrootcert
	
	def __init__( self,
		config: Config,
		tablename: str,
		ending: str,
		fields: list[SqlBase],
		owner_user: str,
		owner_group: str,
		*,
		auditing: bool = True,
		keyname: str = 'id',
	) -> None:
		assert re.match( r'^[a-z][a-z_0-9]+$', tablename )
		
		assert fields, f'no fields defined for table {tablename!r}'
		
		if not hasattr( RepoPostgres, 'pgsql_host' ):
			RepoPostgres.setup( config )
		
		super().__init__(
			config, tablename, ending, fields, owner_user, owner_group,
			auditing = auditing,
			keyname = keyname,
		)
		#if not RepoPostgres.schemas:
		#	RepoPostgres.setup( config )
		
		fldsql: list[str] = []
		fldxtra: list[str] = []
		fldsupp: list[str] = []
		for fld in fields:
			fldsql.append( fld.to_postgres() )
			fldxtra.extend( fld.to_postgres_extra() )
			fldsupp.extend( fld.to_postgres_after( tablename ))
		
		_flds_ = ',\n'.join( fldsql + fldxtra )
		sql: list[str] = [ f'CREATE TABLE IF NOT EXISTS "{tablename}" ({_flds_});' ]
		sql.extend( fldsupp )
		
		with Connector() as ctr:
			with self._cursor( ctr ) as cur:
				for sql_ in sql:
					#print( f'>>>>>> executing sql:\n{sql_}\n<<<<<<<<<<<<<<<<<<' )
					cur.execute( sql_ )
	
	def connect( self, ctr: Connector ) -> psycopg2.connection:
		return ctr.postgres(
			host = self.pgsql_host,
			database = self.pgsql_db,
			user = self.pgsql_uid,
			password = self.pgsql_pwd,
			port = self.pgsql_port,
			sslmode = self.pgsql_sslmode,
			sslrootcert = self.pgsql_sslrootcert,
		)
	
	@contextmanager
	def _cursor( self, ctr: Connector ) -> Iterator[psycopg2._psycopg.cursor]:
		log = logger.getChild( 'RepoPostgres._cursor' )
		conn = self.connect( ctr )
		with closing( conn.cursor() ) as cur:
			try:
				yield cur
			except Exception:
				conn.rollback()
				raise
			else:
				conn.commit()
	
	def valid_id( self, id: REPOID ) -> REPOID:
		log = logger.getChild( 'RepoSqlite.valid_id' )
		
		if not isinstance( id, int ):
			if isinstance( id, str ) and id.isnumeric():
				return int( id )
			try:
				_ = uuid.UUID( id )  # TODO FIXME: invalid uuid?
			except ValueError as e:
				raise ValueError( f'Invalid uuid {id!r}: {e!r}' ).with_traceback( e.__traceback__ ) from None
		return id
	
	def exists( self, ctr: Connector, id: REPOID ) -> bool:
		assert isinstance( id, ( int, str )), f'invalid id={id!r}'
		with self._cursor( ctr ) as cur:
			cur.execute( f'select count(*) as "qty" from "{self.tablename}" WHERE "{self.keyname}" = %s', ( id, ) )
			assert cur.description is not None
			hdrs: list[str] = [ desc[0] for desc in cur.description ]
			vals: Opt[Tuple[Any,...]] = cur.fetchone()
			row: dict[str,Any] = dict( zip( hdrs, vals )) if vals else {}
		try:
			return int( row['qty'] ) > 0
		except ( KeyError, ValueError ):
			return False
	
	def _row_from_hdrs_vals( self, hdrs: list[str], vals: Tuple[Any,...] ) -> dict[str,Any]:
		return {
			hdr: self.fields[hdr].decode_postgres( val )
			for hdr, val
			in zip( hdrs, vals )
		}
	
	def get_by_id( self, ctr: Connector, id: REPOID ) -> dict[str,Any]:
		assert isinstance( id, ( int, str )), f'invalid id={id!r}'
		with self._cursor( ctr ) as cur:
			cur.execute( f'select * from "{self.tablename}" WHERE "{self.keyname}" = %s', [ id ])
			hdrs: list[str] = [ desc[0] for desc in cur.description ]
			vals: Opt[Tuple[Any,...]] = cur.fetchone()
			if vals is None:
				raise ResourceNotFound( id )
			row = self._row_from_hdrs_vals( hdrs, vals )
			return row
	
	def list( self,
		ctr: Connector,
		filters: dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, dict[str, Any]]]:
		params: list[str] = []
		if filters:
			wheres: list[str] = []
			for k, v in filters.items():
				wheres.append( f'lower(cast("{k}" as varchar)) like %s' )
				params.append( f'%{str(v).lower().replace("%","%%")}%' )
			_where_ = f'where {" and ".join(wheres)}'
		else:
			_where_ = ''
		
		paging: list[str] = []
		if limit or offset:
			paging.append( f'limit {int(limit or -1)!r}' )
			if offset:
				paging.append( f'offset {int(offset or 0)!r}' )
		_paging_ = ' '.join( paging )
		
		orderby = orderby.strip() or self.keyname
		assert '"' not in orderby, f'invalid orderby={orderby!r}'
		direction = 'desc' if reverse else 'asc'
		sql = f'select * from "{self.tablename}" {_where_} order by "{orderby}" {direction} {_paging_}'
		items: list[Tuple[REPOID,dict[str,Any]]] = []
		with self._cursor( ctr ) as cur:
			cur.execute( sql, params )
			hdrs: list[str] = [ desc[0] for desc in cur.description ]
			for row in map( lambda vals: self._row_from_hdrs_vals( hdrs, vals ), cur.fetchall() ):
				id = row.pop( self.keyname )
				items.append(( id, row ))
		
		return items
	
	def create( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> None:
		sql1 = f'SELECT COUNT(*) AS "qty" FROM "{self.tablename}" WHERE "{self.keyname}"=%s'
		with self._cursor( ctr ) as cur:
			cur.execute( sql1, [ id ])
			hdrs: list[str] = [ desc[0] for desc in cur.description ]
			vals: Opt[Tuple[Any,...]] = cur.fetchone()
			row: Opt[dict[str,Any]] = dict( zip( hdrs, vals )) if vals is not None else None
		assert row is not None
		qty = cast( int, row['qty'])
		if qty > 0:
			raise ResourceAlreadyExists()
		
		keys: list[str] = []
		values: list[str] = []
		params: list[Any] = []
		for key, val in resource.items():
			assert '"' not in key, f'invalid key={key!r}'
			keys.append( f'"{key}"' )
			values.append( '%s' )
			params.append( self.fields[key].encode_postgres( val ))
		
		_keys_ = ','.join( keys )
		_values_ = ','.join( values )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql2 = f'INSERT INTO "{self.tablename}" ({_keys_}) VALUES ({_values_});'
		
		with self._cursor( ctr ) as cur:
			cur.execute( sql2, params )
		
		if self.auditing:
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in resource.items()
				if v not in ( None, '' )
			)
			audit.audit( f'Created {self.tablename} {id!r}:{auditdata}' )
	
	def update( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> dict[str,Any]:
		values: list[str] = []
		params: list[Any] = []
		for k, v in resource.items():
			values.append( f'"{k}"=%s' )
			params.append( self.fields[k].encode_postgres( v ))
		_values_ = ','.join( values )
		
		olddata = self.get_by_id( ctr, id )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'UPDATE "{self.tablename}" SET {_values_} WHERE "{self.keyname}"=%s'
		params.append( id )
		
		with self._cursor( ctr ) as cur:
			cur.execute( sql, params )
		
		if self.auditing:
			auditdata = auditdata_from_update( olddata, resource )
			audit.audit( f'Updated {self.tablename} {id!r}:{auditdata}' )
		
		return resource
	
	def delete( self, ctr: Connector, id: REPOID, *, audit: auditing.Audit ) -> dict[str,Any]:
		# delete by id and return deleted dict
		data = self.get_by_id( ctr, id )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'DELETE FROM "{self.tablename}" WHERE "{self.keyname}"=%s;'
		
		with self._cursor( ctr ) as cur:
			cur.execute( sql, [ id ])
		
		if self.auditing:
			audit.audit( f'Deleted {self.tablename} {id!r}' )
		
		return data


#endregion repo postgres
#region repo filesystem


@repo_type( 'fs' )
class RepoFs( Repository ):
	type = 'fs'
	base_path: Path
	
	@classmethod
	def setup( cls, config: Config ) -> None:
		assert config.fs_path is not None, 'repo.Config.fs_path not set'
		cls.base_path = Path( config.fs_path )
	
	def __init__( self,
		config: Config,
		tablename: str,
		ending: str,
		fields: list[SqlBase],
		owner_user: str,
		owner_group: str,
		*,
		auditing: bool = True,
		keyname: str = 'id',
	) -> None:
		if not hasattr( RepoFs, 'base_path' ):
			RepoFs.setup( config )
		super().__init__(
			config, tablename, ending, fields, owner_user, owner_group,
			auditing = auditing,
			keyname = keyname,
		)
		self.path = self.base_path / tablename
		self.path.mkdir( mode = 0o775, parents = True, exist_ok = True )
		chown( str( self.path ), owner_user, owner_group )
		os.chmod( str( self.path ), 0o775 )
		self.owner_user = owner_user
		self.owner_group = owner_group
	
	def valid_id( self, id: REPOID ) -> REPOID:
		log = logger.getChild( 'RepoFs.valid_id' )
		log.debug( f'id={id!r}' )
		#try:
		#	_ = uuid.UUID( id )  # TODO FIXME: invalid uuid?
		#except ValueError as e:
		#	raise HttpFailure( f'Invalid uuid {id!r}: {e!r}', 400 )
		return id
	
	def exists( self, ctr: Connector, id: REPOID ) -> bool:
		itemFile = self._path_from_id( id )
		return itemFile.is_file()
	
	def get_by_id( self, ctr: Connector, id: REPOID ) -> dict[str,Any]:
		itemFile = self._path_from_id( id )
		try:
			with itemFile.open( 'r' ) as fileContent: # TODO FIXME: this can raise FileNotFoundError
				item: dict[str,Any] = json.loads( fileContent.read() )
		except FileNotFoundError as e:
			raise ResourceNotFound( id ).with_traceback( e.__traceback__ ) from None
		return item
	
	def list( self,
		ctr: Connector,
		filters: dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, dict[str, Any]]]:
		log = logger.getChild( 'RepoFs.list' )
		items: list[Tuple[REPOID, dict[str, Any]]] = []
		
		def _filter( id: int, data: dict[str,Any] ) -> bool:
			id2: str = str( id )
			for k, v in filters.items():
				if k == self.keyname:
					if v not in id2:
						return True
				else:
					if v.lower() not in str( data.get( k, '' )).lower():
						return True
			return False
		
		for itemFile in self.path.iterdir():
			name = itemFile.name.lower()
			if name.endswith( self.ending ):
				with itemFile.open( 'r' ) as f:
					id = int( itemFile.stem )
					try:
						data = json.loads( f.read() )
					except json.JSONDecodeError:
						log.exception( 'Error trying to load %r:', str( itemFile ))
						data = {}
					if not _filter( id, data ):
						items.append(( id, data ))
		
		if not orderby.strip():
			orderby = self.keyname
		if orderby == self.keyname:
			sorter = lambda kv: kv[0]
		else:
			sorter = lambda kv: kv[1].get( orderby ) or ''
		items = sorted( items, key = sorter )
		if reverse:
			items = items[::-1]
		if offset:
			items = items[offset:]
		if limit:
			items = items[:limit]
		return items
	
	def create( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> None:
		path = self._path_from_id( id )
		if path.is_file():
			raise ResourceAlreadyExists()
		with path.open( 'w' ) as fileContent:
			fileContent.write( json_dumps( resource ))
		chown( str( path ), self.owner_user, self.owner_group )
		os.chmod( str( path ), 0o770 )
		
		if self.auditing:
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in resource.items()
				if v not in ( None, '' )
			)
			audit.audit( f'Created {self.tablename} {id!r} at {str(path)!r}:{auditdata}' )
	
	def update( self, ctr: Connector, id: REPOID, resource: dict[str,Any] = {}, *, audit: auditing.Audit ) -> dict[str,Any]:
		path = self._path_from_id( id )
		with path.open( 'r' ) as f:
			olddata = json.loads( f.read() )
		with path.open( 'w' ) as f:
			f.write( json_dumps( resource ))
		
		if self.auditing:
			auditdata = auditdata_from_update( olddata, resource )
			audit.audit( f'Changed {self.tablename} {id!r} at {str(path)!r}:{auditdata}' )
		
		return resource
	
	def delete( self, ctr: Connector, id: REPOID, *, audit: auditing.Audit ) -> dict[str,Any]:
		path = self._path_from_id( id )
		with path.open( 'r' ) as fileContent:
			resource: dict[str,Any] = json.loads( fileContent.read() )
		
		path.unlink()
		
		if self.auditing:
			audit.audit( f'Deleted {self.tablename} {id!r} at {str(path)!r}' )
		
		return resource
	
	def _path_from_id( self, id: REPOID ) -> Path:
		return self.path / f'{id}{self.ending}'


#endregion repo filesystem
#region async support

class AsyncRepository:
	def __init__( self, repo: Repository ) -> None:
		self.repo = repo
	
	async def exists( self, ctr: Connector, id: REPOID ) -> bool:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.exists( ctr, id )
		)
	
	async def get_by_id( self, ctr: Connector, id: REPOID ) -> dict[str, Any]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.get_by_id( ctr, id )
		)
	
	async def list( self,
		ctr: Connector,
		filters: dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, dict[str, Any]]]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.list( ctr, filters, limit = limit, offset = offset, orderby = orderby )
		)
	
	async def create( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> None:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.create( ctr, id, resource, audit = audit )
		)
	
	async def update( self, ctr: Connector, id: REPOID, resource: dict[str,Any], *, audit: auditing.Audit ) -> dict[str,Any]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.update( ctr, id, resource, audit = audit )
		)
	
	async def delete( self, ctr: Connector, id: REPOID, *, audit: auditing.Audit ) -> dict[str,Any]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.delete( ctr, id, audit = audit )
		)


#endregion async support
