#region imports

# stdlib imports:
from abc import ABCMeta, abstractmethod
import asyncio
from contextlib import closing
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import sqlite3
import threading
from typing import (
	Any, cast, Dict, List, Optional as Opt, Sequence as Seq, Tuple, Union,
)
import uuid

# local imports:
import auditing

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
#region repo base


REPOID = Union[int,str]


@dataclass
class Config:
	fs_path: Opt[Path] = None
	sqlite_path: Opt[Path] = None


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
			'COLLATE NOCASE',
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
			'INTEGER' if self.auto else f'INTEGER({self.size})', # sqlite doesn't like (size) for autoinc fields
			'NULL' if self.null else 'NOT NULL',
			'PRIMARY KEY' if self.primary else '',
			'UNIQUE' if self.unique else '',
			'AUTOINCREMENT' if self.auto else '',
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
		sql: List[str] = [
			self.name,
			f'FLOAT',
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
		sql: List[str] = [
			self.name,
			'TEXT',
			'NULL' if self.null else 'NOT NULL',
			#'PRIMARY KEY' if self.primary else '',
			#'UNIQUE' if self.unique else '',
			'COLLATE NOCASE',
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
	schemas: Dict[str,List[SqlBase]] = {}
	
	def __init__( self,
		config: Config,
		tablename: str,
		ending: str,
		fields: List[SqlBase],
		auditing: bool = True,
	) -> None:
		assert tablename not in Repository.schemas, f'duplicate schema definition for table {tablename!r}'
		Repository.schemas[tablename] = fields
		self.tablename = tablename
		self.ending = ending
		self.auditing = auditing
	
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
	def list( self,
		filters: Dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, Dict[str, Any]]]:
		# Return all dictionaries of type
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.list' )
	
	@abstractmethod
	def create( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> None:
		# Persist new dictionary and return it
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.create' )
	
	@abstractmethod
	def update( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> Dict[str,Any]:
		# Update by id and return updated dict
		cls = type( self )
		raise NotImplementedError( f'{cls.__module__}.{cls.__name__}.update' )
	
	@abstractmethod
	def delete( self, id: REPOID, *, audit: auditing.Audit ) -> Dict[str,Any]:
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
	sqlite_path: Path
	tls = threading.local()
	
	@classmethod
	def setup( cls, config: Config ) -> None:
		assert config.sqlite_path is not None, 'repo.Config.sqlite_path not set'
		sqlite_path = Path( config.sqlite_path )
		if not sqlite_path.exists():
			sqlite_path.touch()
		cls.sqlite_path = sqlite_path
		#with closing( cls.database.cursor() ) as cur:
		#	#cur.execute(
		#	#	'CREATE TABLE IF NOT EXISTS "audits" (id INTEGER PRIMARY KEY AUTOINCREMENT)' )
		#	#cur.execute( 'CREATE TABLE IF NOT EXISTS "users" (id INTEGER PRIMARY KEY AUTOINCREMENT)' )
	
	def __init__( self,
		config: Config,
		tablename: str,
		ending: str,
		fields: List[SqlBase],
		auditing: bool = True,
	) -> None:
		assert re.match( r'^[a-z][a-z_0-9]+$', tablename )
		
		assert fields, f'no fields defined for table {tablename!r}'
		
		if not hasattr( RepoSqlite, 'sqlite_path' ):
			RepoSqlite.setup( config )
		
		super().__init__( config, tablename, ending, fields, auditing )
		if not RepoSqlite.schemas:
			RepoSqlite.setup( config )
		
		fldsql: List[str] = []
		fldxtra: List[str] = []
		fldsupp: List[str] = []
		for fld in fields:
			fldsql.append( fld.to_sqlite() )
			fldxtra.extend( fld.to_sqlite_extra() )
			fldsupp.extend( fld.to_sqlite_after( tablename ))
		
		_flds_ = ',\n'.join( fldsql + fldxtra )
		sql: List[str] = [ f'CREATE TABLE IF NOT EXISTS "{tablename}" ({_flds_});' ]
		sql.extend( fldsupp )
		
		conn = self.database
		with closing( conn.cursor() ) as cur:
			for sql_ in sql:
				cur.execute( sql_ )
		conn.commit()
	
	@property
	def database( self ) -> sqlite3.Connection:
		conn = getattr( self.tls, 'conn', None )
		if conn is None:
			conn = sqlite3.connect( str( self.sqlite_path ))
			setattr( conn, 'row_factory', dict_factory )
			setattr( self.tls, 'conn', conn )
		return conn
	
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
	
	def exists( self, id: REPOID ) -> bool:
		assert isinstance( id, ( int, str )), f'invalid id={id!r}'
		with closing( self.database.cursor() ) as cur:
			cur.execute( f'select count(*) as "qty" from "{self.tablename}" WHERE id = ?', ( id, ) )
			row: Dict[str,int] = cur.fetchone()
		return row['qty'] > 0
	
	def get_by_id( self, id: REPOID ) -> Dict[str,Any]:
		assert isinstance( id, ( int, str )), f'invalid id={id!r}'
		with closing( self.database.cursor() ) as cur:
			cur.execute( f'select * from "{self.tablename}" WHERE id = ?', [ id ])
			item: Opt[Dict[str,Any]] = cur.fetchone() # TODO FIXME: EOF?
		if item is None:
			raise ResourceNotFound( id )
		return item
	
	def list( self,
		filters: Dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, Dict[str, Any]]]:
		items: Seq[Tuple[REPOID, Dict[str, Any]]]
		
		params: List[str] = []
		if filters:
			wheres: List[str] = []
			for k, v in filters.items():
				wheres.append( f'"{k}" like ?' )
				params.append( f'%{v}%' )
			_where_ = f'where {" and ".join(wheres)}'
		else:
			_where_ = ''
		
		paging: List[str] = []
		if limit or offset:
			paging.append( f'limit {int(limit or -1)!r}' )
			if offset:
				paging.append( f'offset {int(offset or 0)!r}' )
		_paging_ = ' '.join( paging )
		
		orderby = orderby.strip() or 'id'
		assert '"' not in orderby, f'invalid orderby={orderby!r}'
		direction = 'desc' if reverse else 'asc'
		sql = f'select * from "{self.tablename}" {_where_} order by "{orderby}" {direction} {_paging_}'
		items: List[Tuple[REPOID,Dict[str,Any]]] = []
		with closing( self.database.cursor() ) as cur:
			cur.execute( sql, params )
			for row in cur.fetchall():
				id = row['id']
				items.append(( id, row ))
		
		return items
	
	def create( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> None:
		sql1 = f'SELECT COUNT(*) AS "qty" FROM "{self.tablename}" WHERE "id"=?'
		conn = self.database
		with closing( conn.cursor() ) as cur:
			cur.execute( sql1, [ id ] )
			row = cur.fetchone()
			qty = cast( int, row['qty'] )
			if qty > 0:
				raise ResourceAlreadyExists()
		
		keys: List[str] = []
		values: List[str] = []
		params: List[Any] = []
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
	
	def update( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> Dict[str,Any]:
		values: List[str] = []
		params: List[Any] = []
		for k, v in resource.items():
			values.append( f'{k}=?' )
			params.append( v )
		_values_ = ','.join( values )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'UPDATE "{self.tablename}" SET {_values_} WHERE id=?'
		params.append( id )
		
		conn = self.database
		with closing( conn.cursor() ) as cur:
			cur.execute( sql, params )
		conn.commit()
		
		if self.auditing:
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in resource.items()
				if v not in ( None, '' )
			)
			audit.audit( f'Updated {self.tablename} {id!r}:{auditdata}' )
		
		return resource
	
	def delete( self, id: REPOID, *, audit: auditing.Audit ) -> Dict[str,Any]:
		# delete by id and return deleted dict
		data = self.get_by_id( id )
		
		assert '"' not in self.tablename, f'invalid tablename={self.tablename!r}'
		sql = f'DELETE FROM "{self.tablename}" WHERE id=?;'
		
		conn = self.database
		with closing( conn.cursor() ) as cur:
			cur.execute( sql, [ id ])
		conn.commit()
		
		if self.auditing:
			audit.audit( f'Deleted {self.tablename} {id!r}' )
		
		return data


#endregion repo sqlite
#region repo filesystem


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
		fields: List[SqlBase],
		auditing: bool = True,
	) -> None:
		if not hasattr( RepoFs, 'base_path' ):
			RepoFs.setup( config )
		super().__init__( config, tablename, ending, fields, auditing )
		self.path = self.base_path / tablename
		self.path.mkdir( mode = 0o770, parents = True, exist_ok = True )
	
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
		try:
			with itemFile.open( 'r' ) as fileContent: # TODO FIXME: this can raise FileNotFoundError
				item: Dict[str,Any] = json.loads( fileContent.read() )
		except FileNotFoundError as e:
			raise ResourceNotFound( id ).with_traceback( e.__traceback__ ) from None
		return item
	
	def list( self,
		filters: Dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, Dict[str, Any]]]:
		items: List[Tuple[REPOID, Dict[str, Any]]] = []
		
		def _filter( id: int, data: Dict[str,Any] ) -> bool:
			for k, v in filters.items():
				if k == 'id':
					if v not in str( id ):
						return True
				else:
					if v.lower() not in data.get( k, '' ).lower():
						return True
			return False
		
		for itemFile in self.path.iterdir():
			name = itemFile.name.lower()
			if name.endswith( self.ending ):
				with itemFile.open( 'r' ) as fileContent:
					id = int( itemFile.stem )
					data = json.loads( fileContent.read() )
					if not _filter( id, data ):
						items.append( ( id, data ) )
		
		if not orderby.strip():
			orderby = 'id'
		items = sorted( items, key = lambda kv: kv[1].get( orderby ))
		if reverse:
			items = items[::-1]
		if offset:
			items = items[offset:]
		if limit:
			items = items[:limit]
		return items
	
	def create( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> None:
		path = self._path_from_id( id )
		if path.is_file():
			raise ResourceAlreadyExists()
		with path.open( 'w' ) as fileContent:
			fileContent.write( json_dumps( resource ))
		
		if self.auditing:
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in resource.items()
				if v not in ( None, '' )
			)
			audit.audit( f'Created {self.tablename} {id!r} at {str(path)!r}:{auditdata}' )
	
	def update( self, id: REPOID, resource: Dict[str,Any] = {}, *, audit: auditing.Audit ) -> Dict[str,Any]:
		print( f'updating {resource}' )
		path = self._path_from_id( id )
		with path.open( 'w' ) as fileContent:
			fileContent.write( json_dumps( resource ))
		
		if self.auditing:
			auditdata = ''.join (
				f'\n\t{k}={v!r}' for k, v in resource.items()
				if v not in ( None, '' )
			)
			audit.audit( f'Changed {self.tablename} {id!r} at {str(path)!r}:{auditdata}' )
		
		return resource
	
	def delete( self, id: REPOID, *, audit: auditing.Audit ) -> Dict[str,Any]:
		path = self._path_from_id( id )
		with path.open( 'r' ) as fileContent:
			resource: Dict[str,Any] = json.loads( fileContent.read() )
		
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
	
	async def exists( self, id: REPOID ) -> bool:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.exists( id )
		)
	
	async def get_by_id( self, id: REPOID ) -> Dict[str, Any]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.get_by_id( id )
		)
	
	async def list( self,
		filters: Dict[str,str] = {},
		*,
		limit: Opt[int] = None,
		offset: int = 0,
		orderby: str = '',
		reverse: bool = False,
	) -> Seq[Tuple[REPOID, Dict[str, Any]]]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.list( filters, limit = limit, offset = offset, orderby = orderby )
		)
	
	async def create( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> None:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.create( id, resource, audit = audit )
		)
	
	async def update( self, id: REPOID, resource: Dict[str,Any], *, audit: auditing.Audit ) -> Dict[str,Any]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.update( id, resource, audit = audit )
		)
	
	async def delete( self, id: REPOID, *, audit: auditing.Audit ) -> Dict[str,Any]:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor( None, lambda:
			self.repo.delete( id, audit = audit )
		)


#endregion async support
