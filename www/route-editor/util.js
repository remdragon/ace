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

