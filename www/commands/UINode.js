// TODO FIXME: need a Set Voice command
// TODO FIXME: play a different prompt based on a schedule

import '/nice-select2/nice-select2.js'

/*interface Field {
	key: string
	name?: string
	type?: string
	options?: { label: string; value: string }[]
}*/

const PATTERNS = {
	int: "[0-9]*",
	float: "[0-9]*(.[0-9]*)?"
}

export default class UINode {
	static icon//: string
	static context_menu_name//: string
	static command//: string
	static onChange = () => {}//: function
	
	help//: string
	fields = []//: Field[];
	
	parent//: UINode | null
	element//: any
	children = []//: UINode[]
	
	constructor( parent /*: UINode*/ )
	{
		if (!parent)
			return
		this.parent = parent
		parent.children.push( this )
	}
	
	get label() {
		return `oops, command ${this.constructor.name} is missing a label!`
	}
	
	createElement({
		isSubtree = false,
		data,
		NODE_TYPES,
		context
	}/*: {
		isSubtree: boolean
		data: any
		NODE_TYPES: object
		context: string
	}*/) {
		if( data )
		{
			this.fields.forEach(field =>
			{
				if( data.hasOwnProperty( field.key ))
					this[field.key] = data[field.key]
			})
		}
		
		this.element = this.parent.element.createChildNode(
			this.label,
			true,
			( this.constructor /*as any*/ ).icon,
			null,
			context ? context : isSubtree ? 'contextSubtree' : 'contextLeaf'
		)
		
		this.element.node = this
	}
	
	async onSelected( divHelp )/*: void*/
	{
		var has_select2 = false
		for( let field of this.fields )
		{
			//console.log( `processing ${field.key}` )
			divHelp.appendChild( document.createElement( 'br' ))
			var self = this
			const _onChange = function( newValue )
			{
				if( field.type === 'float' )
					self[field.key] = parseFloat( newValue )
				else if( field.type === 'int' )
					self[field.key] = parseInt( newValue )
				else
					self[field.key] = newValue
				
				UINode.onChange()
				
				self.element.elementSpan.children[1].innerText = self.label
			}
			const onChangeEvent = evt =>
			{
				_onChange( evt.target.value )
			}
			
			let inputGroup = document.createElement( 'div' )
			inputGroup.classList.add( 'input-group' )
			
			let label = document.createElement( 'label' )
			let tooltipped, input, tooltip
			let changeevent = 'input'
			
			if( field.input === 'select' || field.input === 'select2' )
			{
				input = document.createElement( 'select' )
				if( field.input === 'select2' )
				{
					has_select2 = true
					input.setAttribute( 'class', 'ace_select2' )
					input.style.display = 'none'
					changeevent = 'change'
					
					setTimeout( function()
					{
						let options = { searchable: true }
						let x = NiceSelect.bind( input, options )
					}, 100 )
				}
				
				let selectedValue = this[field.key] || ''
				let options = await field.options()
				options.forEach( option => {
					let optionEl = document.createElement('option')
					optionEl.setAttribute( 'value', option.value )
					optionEl.innerText = option.label || option.value
					if ( selectedValue == ( option.value || option.label ))
						optionEl.setAttribute( 'selected', 'selected' )
					input.appendChild( optionEl )
				})
			}
			else
			{
				input = document.createElement( 'input' )
				input.setAttribute( 'type', field.input || 'text' )
				
				let pattern = PATTERNS[field.type]
				if( field.hasOwnProperty( 'maxlength' ))
					input.setAttribute( 'maxlength', field.maxlength )
				if( field.hasOwnProperty( 'size' ))
					input.setAttribute( 'size', field.size )
				if( pattern )
				{
					let reg = new RegExp( `^${pattern}$` )
					input.setAttribute( 'pattern', pattern )
					input.onkeypress = evt => {
						let text = input.value
						
						return reg.test( text + evt.key )
					}
				}
				input.value = this[field.key] || ''
			}
			
			input.addEventListener( changeevent, onChangeEvent )
			
			label.innerText = field.label || field.key
			
			label.appendChild( document.createElement( 'br' ))
			
			if( field.tooltip )
			{
				tooltipped = document.createElement( 'span' )
				tooltipped.setAttribute( 'class', 'tooltipped' )
				tooltipped.appendChild( input )
				
				tooltip = document.createElement( 'span' )
				tooltip.setAttribute( 'class', 'tooltip' )
				tooltip.innerText = field.tooltip
				tooltipped.appendChild( tooltip )
				
				label.appendChild( tooltipped )
			}
			else
				label.appendChild( input )
			
			inputGroup.appendChild( label )
			if( field.input == 'select2' ) // grr select2
			{
				inputGroup.appendChild( document.createElement( 'br' ))
				inputGroup.appendChild( document.createElement( 'br' ))
			}
			
			divHelp.appendChild( inputGroup )
		}
	}
	
	getJson() {
		let fields = {}
		this.fields.forEach(field => {
			fields[field.key] = this[field.key] || ''
		})
		
		return {
			type: ( this.constructor /*as any*/ ).command,
			...fields
		}
	}

	moveNodeUp( node/*: UINode*/ )
	{
		let i = this.children.findIndex(
			n => JSON.stringify( n.getJson() ) === JSON.stringify( node.getJson() )
		)
		
		// if < 0 does not exist
		// if 0 already at top of array
		if ( i < 1 )
			return
		
		let aux = this.children[i - 1]
		this.children[i - 1] = this.children[i]
		this.children[i] = aux
	}
	
	moveNodeDown( node/*: UINode*/ )
	{
		let i = this.children.findIndex(
			n => JSON.stringify( n.getJson() ) === JSON.stringify( node.getJson() )
		)
		
		// if < 0 does not exist
		// if === length already at bottom of array
		if ( i < 0 || i === this.children.length - 1 )
			return
		
		let aux = this.children[i + 1]
		this.children[i + 1] = this.children[i]
		this.children[i] = aux
	}
	
	remove( node/*: UINode*/ )
	{
		this.children = this.children.filter(n =>
		{
			return n.element.id !== node.element.id
		})
	}
}
