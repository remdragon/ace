class Error( Exception ):
	...

class DatabaseError( Error ):
	...

class ProgrammingError( DatabaseError ):
	...

class DuplicateTable( ProgrammingError ):
	...
