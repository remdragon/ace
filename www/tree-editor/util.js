export function newElement(tag/*: string*/, attributes/*: object*/) {
	var el = document.createElement(tag)
	for (var key in attributes) {
		if (attributes.hasOwnProperty(key)) el.setAttribute(key, attributes[key])
	}
	return el
}

export function debounce(func, timer = 1000) {
	let inDebounce
	
	return function() {
		const context = this || {}
		const args = arguments
		clearTimeout(inDebounce)
		inDebounce = setTimeout(() => func.apply(context, args), timer)
	}
}

export function parseBoolean( value, nullOnFailure = false )
{
	let value2 = parseFloat( value )
	if( !isNaN( value2 ))
		return !!value2
	if( typeof value !== 'string' )
		return !!value
	switch( value.trim().toLowerCase() )
	{
		case 't':
		case 'true':
		case 'on':
		case 'y':
		case 'yes':
			return true
		case 'f':
		case 'false':
		case 'off':
		case 'n':
		case 'no':
			return false
		default:
			return nullOnFailure ? null : false
	}
}
