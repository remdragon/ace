# https://github.com/kennethreitz
#from __future__ import annotations

# python imports:
from collections import OrderedDict
import logging
from typing import Any, Iterator, Mapping, MutableMapping, Tuple, TypeVar

# incpy imports:
import caseless

logger = logging.getLogger ( __name__ )

T = TypeVar ( 'T' )
class CaseFoldedDict ( MutableMapping ): # type: ignore
	"""A case-folded ``dict``-like object.
	Implements all methods and operations of
	``MutableMapping`` as well as dict's ``copy``. Also
	provides ``folded_items``.
	All keys are required to be unicode strings. The structure remembers the
	case of the key from the last time it was set, and ``iter(instance)``,
	``keys()``, ``items()``, ``iterkeys()``
	will contain case-sensitive keys. However, querying and contains
	testing is case insensitive::
		cid = CaseFoldedDict()
		cid['Accept'] = 'application/json'
		cid['aCCEPT'] == 'application/json'  # True
		list(cid) == ['Accept']  # True
	For example, ``headers['content-encoding']`` will return the
	value of a ``'Content-Encoding'`` response header, regardless
	of how the header name was originally stored.
	If the constructor, ``.update``, or equality comparison
	operations are given keys that have equal case-folded keys, the
	behavior is undefined.
	"""
	
	_store: MutableMapping[str,Tuple[str,T]] = None
	
	def __init__ ( self, data: Any = None, **kwargs: T ) -> None:
		# 1st arg? Union[Mapping[str,Any],Seq[Tuple[str,Any]],ValuesView[Tuple[str,Any]]]
		self._store = OrderedDict()
		self.update ( data or {}, **kwargs )
	
	def __setitem__ ( self, key: str, value: T ) -> None:
		# Use the casefolded key for lookups, but store the actual
		# key alongside the value.
		assert isinstance ( key, str ), 'expecting str key not {!r}'.format ( key )
		self._store[caseless.normalize ( key )] = ( key, value ) # type: ignore
	
	def __getitem__ ( self, key: str ) -> T:
		assert isinstance ( key, str ), 'expecting str key not {!r}'.format ( key )
		kv = self._store.get ( caseless.normalize ( key ) ) # type: ignore
		if kv is None:
			raise KeyError ( key )
		return kv[1] # type: ignore
	
	def __delitem__ ( self, key: str ) -> None:
		del self._store[caseless.normalize ( key )] # type: ignore
	
	def __iter__ ( self ) -> Iterator[str]:
		for casedkey, _ in self._store.values(): # type: ignore
			yield casedkey
	
	def _to_dict ( self ):
		return dict ( self.items() )
	
	def items ( self ) -> Iterator[Tuple[str,T]]:
		for casedkey, mappedvalue in self._store.values(): # type: ignore
			yield casedkey, mappedvalue
	
	def __len__ ( self ) -> int:
		return len ( self._store ) # type: ignore
	
	def lower_items ( self ) -> Iterator[Tuple[str,T]]:
		"""Like items(), but with all lowercase keys."""
		for keyval in self._store.values(): # type: ignore
			yield keyval[0].lower(), keyval[1]
	
	def folded_items ( self ) -> Iterator[Tuple[str,T]]:
		for folded_key, keyval in self._store.items(): # type: ignore
			yield folded_key, keyval[1]
	
	def __eq__ ( self, other: Any ) -> bool:
		if isinstance ( other, Mapping ):
			other = CaseFoldedDict ( other )
		else:
			return NotImplemented
		# Compare insensitively
		return dict ( self.folded_items() ) == dict ( other.folded_items() )
	
	# Copy is required
	def copy ( self ) -> MutableMapping[str,T]:
		return CaseFoldedDict ( self._store.values() ) # type: ignore
	
	def __repr__ ( self ) -> str:
		return 'CaseFoldedDict({{{}}})'.format ( ', '.join ( (
			'{!r}: {!r}'.format ( k, v )
			for k, v in self._store.values() # type: ignore
		) ) )


if __name__ == '__main__': # pragma: no cover
	d = { 'foo': 'bar' }
	d2 = CaseFoldedDict ( d, foo2='bar2' )
	print ( repr ( d2 ) )