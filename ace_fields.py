# stdlib imports:
from typing import Optional as Opt, Union


class ValidationError( Exception ):
	pass


class Field:
	def __init__( self, field: str, label: str, *,
		tooltip: str = '',
		required: bool = False,
		min_length: Opt[int] = None,
		max_length: Opt[int] = None,
		placeholder: Opt[str] = None,
	) -> None:
		self.field = field
		self.label = label
		self.tooltip = tooltip
		self.required = required
		self.min_length = min_length
		self.max_length = max_length
		self.placeholder = placeholder
	
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
