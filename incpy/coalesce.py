from typing import Any

def coalesce ( *args: Any ) -> Any:
	for arg in args:
		if arg is not None:
			return arg
	return None
