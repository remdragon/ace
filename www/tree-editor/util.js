export function newElement(tag/*: string*/, attributes/*: object*/)
{
	var el = document.createElement( tag )
	for( var key in attributes )
	{
		if( attributes.hasOwnProperty(key) )
			el.setAttribute( key, attributes[key] )
	}
	return el
}

export function debounce( func, timer = 1000 )
{
	let inDebounce
	
	return function()
	{
		const context = this || {}
		const args = arguments
		clearTimeout( inDebounce )
		inDebounce = setTimeout(() => func.apply( context, args ), timer)
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

export function moveNodeUp( treeparent, treenode )
{
	let i = treeparent.childNodes.findIndex( n => n.id === treenode.id )
	
	// < 0 does not exist
	// 0 already at top of array
	if( i < 1 )
		return
	
	let aux = treeparent.childNodes[i - 1]
	treeparent.childNodes[i - 1] = treeparent.childNodes[i]
	treeparent.childNodes[i] = aux
	
	treenode.elementLi.parentNode.insertBefore(
		treeparent.childNodes[i - 1].elementLi,
		treeparent.childNodes[i].elementLi
	)
}

export function moveNodeDown( treeparent, treenode )
{
	let i = treeparent.childNodes.findIndex( n => n.id === treenode.id )
	
	// < 0 does not exist
	// >= length already at bottom of array
	if( i < 0 || i >= treeparent.childNodes.length - 1)
		return
	
	let aux = treeparent.childNodes[i + 1]
	treeparent.childNodes[i + 1] = treeparent.childNodes[i]
	treeparent.childNodes[i] = aux
	
	treenode.elementLi.parentNode.insertBefore(
		treeparent.childNodes[i].elementLi,
		treeparent.childNodes[i + 1].elementLi
	)
}
