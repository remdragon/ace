# stdlib imports:
from typing import Any, Optional as Opt, Sequence as Seq, Tuple

# 3rd-party imports:
from typing_extensions import Literal, Self # pip install typing_extensions

P249_NAME = str
P249_TYPE = Any
P249_DISPLAY_SIZE = Opt[int]
P249_INTERNAL_SIZE = Opt[int]
P249_PRECISION = Opt[int]
P249_SCALE = Opt[int]
P249_NULL_OK = Opt[bool]
P249_DESCRIPTOR = Tuple[
	P249_NAME,
	P249_TYPE,
	P249_DISPLAY_SIZE,
	P249_INTERNAL_SIZE,
	P249_PRECISION,
	P249_SCALE,
	P249_NULL_OK
]
P249_DESCRIPTION = Seq[P249_DESCRIPTOR]

class cursor:
	description: Opt[P249_DESCRIPTION]
	
	def __enter__( self: Self ) -> Self:
		...
	
	def __exit__( self, *exc_info: Any ) -> Literal[False]:
		...
	
	def close( self ) -> None:
		...
	
	def execute( self, query: str, vars: Seq[Any]|None = ... ) -> None:
		...
	
	def fetchone( self ) -> tuple[Any]: # TODO FIXME: can return Map based on row_factory
		...

'''
class cursor(builtins.object)
 |  A database cursor.
 |
 |  Methods defined here:
 |
 |  __enter__(...)
 |      __enter__ -> self
 |
 |  __exit__(...)
 |      __exit__ -- close the cursor
 |
 |  __init__(self, /, *args, **kwargs)
 |      Initialize self.  See help(type(self)) for accurate signature.
 |
 |  __iter__(self, /)
 |      Implement iter(self).
 |
 |  __next__(self, /)
 |      Implement next(self).
 |
 |  __repr__(self, /)
 |      Return repr(self).
 |
 |  __str__(self, /)
 |      Return str(self).
 |
 |  callproc(...)
 |      callproc(procname, parameters=None) -- Execute stored procedure.
 |
 |  cast(...)
 |      cast(oid, s) -> value
 |
 |      Convert the string s to a Python object according to its oid.
 |
 |      Look for a typecaster first in the cursor, then in its connection,then in the global register. If no suitable typecaster is found,leave the value as a string.
 |
 |  close(...)
 |      close() -- Close the cursor.
 |
 |  copy_expert(...)
 |      copy_expert(sql, file, size=8192) -- Submit a user-composed COPY statement.
 |      `file` must be an open, readable file for COPY FROM or an open, writable
 |      file for COPY TO. The optional `size` argument, when specified for a COPY
 |      FROM statement, will be passed to file's read method to control the read
 |      buffer size.
 |
 |  copy_from(...)
 |      copy_from(file, table, sep='\t', null='\\N', size=8192, columns=None) -- Copy table from file.
 |
 |  copy_to(...)
 |      copy_to(file, table, sep='\t', null='\\N', columns=None) -- Copy table to file.
 |
 |  execute(...)
 |      execute(query, vars=None) -- Execute query with bound vars.
 |
 |  executemany(...)
 |      executemany(query, vars_list) -- Execute many queries with bound vars.
 |
 |  fetchall(...)
 |      fetchall() -> list of tuple
 |
 |      Return all the remaining rows of a query result set.
 |
 |      Rows are returned in the form of a list of tuples (by default) or using
 |      the sequence factory previously set in the `row_factory` attribute.
 |      Return `!None` when no more data is available.
 |
 |  fetchmany(...)
 |      fetchmany(size=self.arraysize) -> list of tuple
 |
 |      Return the next `size` rows of a query result set in the form of a list
 |      of tuples (by default) or using the sequence factory previously set in
 |      the `row_factory` attribute.
 |
 |      Return an empty list when no more data is available.
 |
 |  fetchone(...)
 |      fetchone() -> tuple or None
 |
 |      Return the next row of a query result set in the form of a tuple (by
 |      default) or using the sequence factory previously set in the
 |      `row_factory` attribute. Return `!None` when no more data is available.
 |
 |  mogrify(...)
 |      mogrify(query, vars=None) -> str -- Return query after vars binding.
 |
 |  nextset(...)
 |      nextset() -- Skip to next set of data.
 |
 |      This method is not supported (PostgreSQL does not have multiple data
 |      sets) and will raise a NotSupportedError exception.
 |
 |  scroll(...)
 |      scroll(value, mode='relative') -- Scroll to new position according to mode.
 |
 |  setinputsizes(...)
 |      setinputsizes(sizes) -- Set memory areas before execute.
 |
 |      This method currently does nothing but it is safe to call it.
 |
 |  setoutputsize(...)
 |      setoutputsize(size, column=None) -- Set column buffer size.
 |
 |      This method currently does nothing but it is safe to call it.
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
 |  arraysize
 |      Number of records `fetchmany()` must fetch if not explicitly specified.
 |
 |  binary_types
 |
 |  closed
 |      True if cursor is closed, False if cursor is open
 |
 |  connection
 |      The connection where the cursor comes from.
 |
 |  description
 |      Cursor description as defined in DBAPI-2.0.
 |
 |  itersize
 |      Number of records ``iter(cur)`` must fetch per network roundtrip.
 |
 |  lastrowid
 |      The ``oid`` of the last row inserted by the cursor.
 |
 |  name
 |
 |  pgresult_ptr
 |      pgresult_ptr -- Get the PGresult structure pointer.
 |
 |  query
 |      The last query text sent to the backend.
 |
 |  row_factory
 |
 |  rowcount
 |      Number of rows read from the backend in the last command.
 |
 |  rownumber
 |      The current row position.
 |
 |  scrollable
 |      Set or return cursor use of SCROLL
 |
 |  statusmessage
 |      The return message of the last command.
 |
 |  string_types
 |
 |  typecaster
 |
 |  tzinfo_factory
 |
 |  withhold
 |      Set or return cursor use of WITH HOLD
'''
