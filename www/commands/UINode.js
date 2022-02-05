// TODO FIXME: need a Set Voice command
// TODO FIXME: play a different prompt based on a schedule

import '/nice-select2/nice-select2.js'
import{ parseBoolean } from '/tree-editor/util.js'

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

function newChild( parent, tag, atts )
{
	let child = document.createElement( tag )
	if( atts )
	{
		for( let k in atts )
			child.setAttribute( k, atts[k] )
	}
	parent.appendChild( child )
	return child
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
		if ( !parent )
			return
		this.parent = parent
		parent.children.push( this )
	}
	
	get label()
	{
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
	}*/)
	{
		if( data )
		{
			for( let field of this.fields )
			{
				if( data.hasOwnProperty( field.key ))
					this[field.key] = data[field.key]
			}
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
		for( let field of this.fields )
		{
			newChild( divHelp, 'br' )
			var self = this
			const _onChange = function( newValue )
			{
				if( field.type === 'float' )
					self[field.key] = parseFloat( newValue )
				else if( field.type === 'int' )
					self[field.key] = parseInt( newValue )
				else if( field.type === 'boolean' )
					self[field.key] = parseBoolean( newValue )
				else
				{
					console.assert( ( field.type || 'string' ) === 'string' )
					self[field.key] = newValue
				}
				
				UINode.onChange()
				
				self.element.elementSpan.children[1].innerText = self.label
			}
			
			let onChangeEvent = function( evt )
			{
				_onChange( evt.target.value )
			}
			
			let inputGroup = newChild( divHelp, 'div' )
			inputGroup.classList.add( 'input-group' )
			
			let label = newChild( inputGroup, 'label' )
			let id = `tree_node_field_${field.key}`
			label.setAttribute( 'for', id )
			label.innerText = field.label || field.key
			newChild( label, 'br' )
			
			let tooltipped, input, tooltip
			let changeevent = 'input'
			
			let inputParent = label
			if( field.tooltip )
			{
				tooltipped = newChild( label, 'span' )
				tooltipped.setAttribute( 'class', 'tooltipped' )
				inputParent = tooltipped
				
				tooltip = newChild( tooltipped, 'span' )
				tooltip.setAttribute( 'class', 'tooltip' )
				tooltip.innerText = field.tooltip
				
			}
			else if ( field.input == 'checkbox' )
				inputParent = inputGroup
			
			if( field.input === 'select' || field.input === 'select2' )
			{
				input = newChild( inputParent, 'select', { id: id } )
				
				let selectedValue = this[field.key] || ''
				let options = await field.options( this )
				for( let option of options )
				{
					let optionEl = newChild( input, 'option')
					optionEl.setAttribute( 'value', option.value )
					optionEl.innerText = option.label || option.value
					if ( selectedValue == ( option.value || option.label ))
						optionEl.setAttribute( 'selected', 'selected' )
				}
				
				if( field.input === 'select2' )
				{
					input.setAttribute( 'class', 'ace_select2' )
					input.style.display = 'none'
					changeevent = 'change'
					
					let options = { searchable: true }
					let x = NiceSelect.bind( input, options )
				}
			}
			else if( field.input == 'checkbox' )
			{
				input = newChild( inputParent, 'input', { id: id } )
				input.setAttribute( 'type', field.input )
				let checked = parseBoolean( this[field.key] )
				if( checked )
					input.setAttribute( 'checked', 'checked' )
				onChangeEvent = function( evt )
				{
					_onChange( evt.target.checked )
				}
			}
			else if( field.input == 'textarea' )
			{
				input = newChild( inputParent, 'textarea', { id: id } )
				if( field.rows )
					input.setAttribute( 'rows', field.rows )
				if( field.cols )
					input.setAttribute( 'cols', field.cols )
				if( field.placeholder )
					input.setAttribute( 'placeholder', field.placeholder )
				input.innerText = this[field.key] || ''
			}
			else
			{
				input = newChild( inputParent, 'input', { id: id, type: field.input || 'text' } )
				
				let pattern = PATTERNS[field.type]
				if( field.maxlength )
					input.setAttribute( 'maxlength', field.maxlength )
				if( field.size )
					input.setAttribute( 'size', field.size )
				if( field.placeholder )
					input.setAttribute( 'placeholder', field.placeholder )
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
			
			if( field.input == 'select2' ) // grr select2
			{
				newChild( inputGroup, 'br' )
				newChild( inputGroup, 'br' )
			}
		}
	}
	
	getJson()
	{
		let fields = {}
		for( let field of this.fields )
		{
			fields[field.key] = this[field.key]
		}
		
		return {
			type: ( this.constructor /*as any*/ ).command,
			...fields
		}
	}
	
	walkTree( callback )
	{
		if( this.parent )
			this.parent.walkTree( callback )
		else
			this.walkChildren( callback )
	}
	
	walkChildren( callback )
	{
		callback( this )
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
		this.children = this.children.filter( n =>
		{
			return n.element.id !== node.element.id
		})
	}
}
