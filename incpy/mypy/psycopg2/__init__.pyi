from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Type

__all__ = [
	'BINARY',
	'Binary',
	'DATETIME',
	'DateError',
	'DatabaseError',
	'Date',
	'DateFromTicks',
	'Error',
	'IntegrityError',
	'InterfaceError',
	'InternalError',
	'NUMBER',
	'NotSupportedError',
	'OperationalError',
	'ProgrammingError',
	'ROWID',
	'STRING',
	'Time',
	'TimeFromTicks',
	'Timestamp',
	'TimestampFromTicks',
	'Warning'
	'__libpq_version__',
	'_ext',
	#'_json',
	'_psycopg',
	'_range',
	'apilevel',
	'connect',
	'errors',
	'extensions',
	'paramstyle',
	'threadsafety',
]

from psycopg2 import _psycopg
from psycopg2 import errors
from psycopg2 import extensions as _ext

__libpq_version__: int

SSLMODE = Literal[
	'disable',
	'allow',
	'prefer', # default
	'require',
	'verify-ca',
	'verify-full',
]

class connection:
	def close( self ) -> None:
		...
	def commit( self ) -> None:
		...
	def cursor( self,
		name: str|None = ...,
		cursor_factory: Type[_psycopg.cursor] = ...,
		withhold: bool = ...,
	) -> _psycopg.cursor:
		...
	def rollback( self ) -> None:
		...
	def set_session( self, *,
		autocommit: bool|None = ...,
		#isolation_level: Any = ...,
		#readonly: Any = ...,
		#deferrable: Any = ...,
	) -> None:
		...
'''
class connection(builtins.object)
 |  connection(dsn, ...) -> new connection object
 |
 |  :Groups:
 |    * `DBAPI-2.0 errors`: Error, Warning, InterfaceError,
 |      DatabaseError, InternalError, OperationalError,
 |      ProgrammingError, IntegrityError, DataError, NotSupportedError
 |
 |  Methods defined here:
 |
 |  __enter__(...)
 |      __enter__ -> self
 |
 |  __exit__(...)
 |      __exit__ -- commit if no exception, else roll back
 |
 |  __init__(self, /, *args, **kwargs)
 |      Initialize self.  See help(type(self)) for accurate signature.
 |
 |  __repr__(self, /)
 |      Return repr(self).
 |
 |  __str__(self, /)
 |      Return str(self).
 |
 |  cancel(...)
 |      cancel() -- cancel the current operation
 |
 |  close(...)
 |      close() -- Close the connection.
 |
 |  commit(...)
 |      commit() -- Commit all changes to database.
 |
 |  cursor(...)
 |      cursor(name=None, cursor_factory=extensions.cursor, withhold=False) -- new cursor
 |
 |      Return a new cursor.
 |
 |      The ``cursor_factory`` argument can be used to
 |      create non-standard cursors by passing a class different from the
 |      default. Note that the new class *should* be a sub-class of
 |      `extensions.cursor`.
 |
 |      :rtype: `extensions.cursor`
 |
 |  fileno(...)
 |      fileno() -> int -- Return file descriptor associated to database connection.
 |
 |  get_backend_pid(...)
 |      get_backend_pid() -- Get backend process id.
 |
 |  get_dsn_parameters(...)
 |      get_dsn_parameters() -- Get effective connection parameters.
 |
 |  get_native_connection(...)
 |      get_native_connection() -- Return the internal PGconn* as a Python Capsule.
 |
 |  get_parameter_status(...)
 |      get_parameter_status(parameter) -- Get backend parameter status.
 |
 |      Potential values for ``parameter``:
 |        server_version, server_encoding, client_encoding, is_superuser,
 |        session_authorization, DateStyle, TimeZone, integer_datetimes,
 |        and standard_conforming_strings
 |      If server did not report requested parameter, None is returned.
 |
 |      See libpq docs for PQparameterStatus() for further details.
 |
 |  get_transaction_status(...)
 |      get_transaction_status() -- Get backend transaction status.
 |
 |  isexecuting(...)
 |      isexecuting() -> bool -- Return True if the connection is executing an asynchronous operation.
 |
 |  lobject(...)
 |      lobject(oid=0, mode=0, new_oid=0, new_file=None,
 |             lobject_factory=extensions.lobject) -- new lobject
 |
 |      Return a new lobject.
 |
 |      The ``lobject_factory`` argument can be used
 |      to create non-standard lobjects by passing a class different from the
 |      default. Note that the new class *should* be a sub-class of
 |      `extensions.lobject`.
 |
 |      :rtype: `extensions.lobject`
 |
 |  poll(...)
 |      poll() -> int -- Advance the connection or query process without blocking.
 |
 |  reset(...)
 |      reset() -- Reset current connection to defaults.
 |
 |  rollback(...)
 |      rollback() -- Roll back all changes done to database.
 |
 |  set_client_encoding(...)
 |      set_client_encoding(encoding) -- Set client encoding to ``encoding``.
 |
 |  set_isolation_level(...)
 |      set_isolation_level(level) -- Switch isolation level to ``level``.
 |
 |  set_session(...)
 |      set_session(...) -- Set one or more parameters for the next transactions.
 |
 |      Accepted arguments are 'isolation_level', 'readonly', 'deferrable', 'autocommit'.
 |
 |  tpc_begin(...)
 |      tpc_begin(xid) -- begin a TPC transaction with given transaction ID xid.
 |
 |  tpc_commit(...)
 |      tpc_commit([xid]) -- commit a transaction previously prepared.
 |
 |  tpc_prepare(...)
 |      tpc_prepare() -- perform the first phase of a two-phase transaction.
 |
 |  tpc_recover(...)
 |      tpc_recover() -- returns a list of pending transaction IDs.
 |
 |  tpc_rollback(...)
 |      tpc_rollback([xid]) -- abort a transaction previously prepared.
 |
 |  xid(...)
 |      xid(format_id, gtrid, bqual) -- create a transaction identifier.
 |
 |  ----------------------------------------------------------------------
 |  Static methods defined here:
 |
 |  __new__(*args, **kwargs) from builtins.type
 |      Create and return a new object.  See help(type) for accurate signature.
 |
 |  ----------------------------------------------------------------------
 |  Data descriptors defined here:
 |
 |  DataError
 |      Error related to problems with the processed data.
 |
 |  DatabaseError
 |      Error related to the database engine.
 |
 |  Error
 |      Base class for error exceptions.
 |
 |  IntegrityError
 |      Error related to database integrity.
 |
 |  InterfaceError
 |      Error related to the database interface.
 |
 |  InternalError
 |      The database encountered an internal error.
 |
 |  NotSupportedError
 |      A method or database API was used which is not supported by the database.
 |
 |  OperationalError
 |      Error related to database operation (disconnect, memory allocation etc).
 |
 |  ProgrammingError
 |      Error related to database programming (SQL error, table not found etc).
 |
 |  Warning
 |      A database warning.
 |
 |  async
 |      True if the connection is asynchronous.
 |
 |  async_
 |      True if the connection is asynchronous.
 |
 |  autocommit
 |      Set or return the autocommit status.
 |
 |  binary_types
 |      A set of typecasters to convert binary values.
 |
 |  closed
 |      True if the connection is closed.
 |
 |  cursor_factory
 |      Default cursor_factory for cursor().
 |
 |  deferrable
 |      Set or return the connection deferrable status.
 |
 |  dsn
 |      The current connection string.
 |
 |  encoding
 |      The current client encoding.
 |
 |  info
 |      info -- Get connection info.
 |
 |  isolation_level
 |      Set or return the connection transaction isolation level.
 |
 |  notices
 |
 |  notifies
 |
 |  pgconn_ptr
 |      pgconn_ptr -- Get the PGconn structure pointer.
 |
 |  protocol_version
 |      Protocol version used for this connection. Currently always 3.
 |
 |  readonly
 |      Set or return the connection read-only status.
 |
 |  server_version
 |      Server version.
 |
 |  status
 |      The current transaction status.
 |
 |  string_types
 |      A set of typecasters to convert textual values.
'''

def connect (
	dsn: Any = ...,
	connection_factory: Any = ...,
	cursor_factory: Any = ...,
	*,
	host: str|None = ...,
	port: int|None = 5432,
	database: str|None = ...,
	user: str|None = ...,
	password: str|None = ...,
	sslmode: SSLMODE|None = ..., # ( 'disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full' )
	sslcert: Path|str|None = ..., # path to public key
	sslkey: Path|str|None = ..., # path to private key
	sslrootcert: Path|str|None = ..., # path to ca certs
) -> connection: ...

class Error ( Exception ):
	pass

class STRING ( str ):
	pass

class BINARY ( bytes ):
	pass

class NUMBER ( int ):
	pass

class DATETIME ( datetime ):
	pass

class ROWID ( int ):
	pass
