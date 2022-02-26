// TODO FIXME: need a Set Voice command

import '/nice-select2/nice-select2.js'
import{ parseBoolean, moveNodeUp, moveNodeDown } from '/tree-editor/util.js'

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

export default class UINode
{
	static icon//: string
	static context_menu_name//: string
	static command//: string
	static onChange = () => {}//: function
	static contextLeaf = 'contextLeaf'
	static contextSubtree = 'contextSubtree'
	static NODE_TYPES = null // chicken vs egg - gives access to this here - set from index.js
	static NamedSubtree = null // chicken vs egg - gives access to a specific subclass - set from named_subtree.js
	canDelete = true // most nodes can be deleted
	canPaste = false // most nodes can't be pasted to
	
	help//: string
	fields = []//: Field[];
	
	parent//: UINode | null
	treenode//: any
	children = null//: UINode[]
	
	constructor( parent /*: UINode*/ )
	{
		this.children = []
		if ( !parent )
			return
		this.tree = parent.tree
		this.parent = parent
		if( parent.children == null )
			alert( `programming error, ${parent.constructor.name} did not call it's super constructor` )
		parent.children.push( this )
	}
	
	get label()
	{
		return `oops, command ${this.constructor.name} is missing a label!`
	}
	
	createElement({
		isSubtree = false,
		data,
		context
	}/*: {
		isSubtree: boolean
		data: any
		context: string
	}*/)
	{
		this.isSubtree = isSubtree
		if( data )
		{
			for( let field of this.fields )
			{
				if( data.hasOwnProperty( field.key ))
					this[field.key] = data[field.key]
			}
		}
		
		this.treenode = this.parent.treenode.createChildNode(
			this.label,
			true,
			( this.constructor /*as any*/ ).icon,
			null,
			context ? context : isSubtree ? 'contextSubtree' : 'contextLeaf'
		)
		this.makeClickable()
		
		this.treenode.uinode = this
	}
	
	createChildren( children )
	{
		let changed = false
		for( let nodeData of children )
		{
			let NodeType = UINode.NODE_TYPES[nodeData.type]
			if( NodeType )
			{
				let node = new NodeType( this )
				node.createElement({ data: nodeData })
				changed = true
			}
			else
			{
				alert( 'invalid nodeData.type=' + nodeData.type )
			}
		}
		return changed
	}
	
	makeFixedBranch( key, label, context, help, data )
	{
		this[key] = new UINode.NamedSubtree( this, label, help )
		this[key].canDelete = false
		this[key].createElement({
			isSubtree: true,
			data: data[key] ?? {},
			context: context,
		})
	}
	
	contextOptionalSubtree()
	{
		if( this.parent )
			return this.parent.contextOptionalSubtree()
		else
			return 'contextOptionalSubtree'
	}
	
	makeClickable()
	{
		this.walkChildren( function( uinode ){
			let elementLi = uinode.treenode.elementLi
			if( elementLi )
			{
				//console.log( 'elementLi=', elementLi )
				elementLi.setAttribute( 'tabindex', 0 )
				
				// don't draw border around treenode when keyboard focus:
				elementLi.style.outline = 'none'
				
				elementLi.onkeydown = function( event )
				{
					if( event.key == 'Control' ) // ignore keydowns of the meta keys themselves (to reduce logging noise)
						return true // allow event to propagate
					let fname = 'onkeydown_'
					if( event.altKey )
						fname += 'alt_'
					if( event.ctrlKey )
						fname += 'ctrl_'
					if( event.shiftKey )
						fname += 'shift_'
					fname += event.key
					//console.log( 'fname=', fname )
					let f = uinode[fname]
					if( false && !f )
						console.log( `no handler for ${fname} in`, uinode )
					if( f )
					{
						f.apply( uinode )
						// don't allow event to propagate:
						console.log( 'cancelling propagation' )
						event.preventDefault()
						event.stopImmediatePropagation()
						return false
					}
					return true // allow event to propagate
				}
			}
		})
	}
	
	async onkeydown_ctrl_c()
	{
		let json = JSON.stringify( this.getJson(), null, 4 )
		navigator.clipboard.writeText( json )
	}
	
	async onkeydown_ctrl_x()
	{
		if ( !confirm( `Cut "${this.label}" and all its children?` ))
			return
		this.treenode.elementLi.focus()
		let json = JSON.stringify( this.getJson(), null, 4 )
		navigator.clipboard.writeText( json )
		this.parent.remove( this )
		this.treenode.removeNode()
		UINode.onChange()
	}
	
	async onkeydown_ctrl_v()
	{
		if( !this.canPaste )
			return alert( "Sorry, you can't paste here - try it from a parent node?" )
			
		let json = await navigator.clipboard.readText()
		let nodeData = JSON.parse( json )
		let nodes = [ nodeData ]
		let is_multi = {
			'': true,
			'root_route': true,
			'root_voicemail': true,
		}
		if( is_multi[nodeData.type] && nodeData.hasOwnProperty( 'nodes' ))
			nodes = nodeData.nodes
		let changed = this.createChildren( nodes ?? [] )
		if( changed )
			UINode.onChange()
	}
	
	async onkeydown_Delete()
	{
		if ( !confirm( `Delete "${this.label}" and all its children?` ))
			return
		
		let uiparent = this.parent
		uiparent.remove( this )
		this.treenode.removeNode()
		UINode.onChange()
		uiparent.tree.selectNode( uiparent.treenode )
	}
	
	async onkeydown_shift_ArrowDown()
	{
		this.moveNode( 'down' )
	}
	
	async onkeydown_shift_ArrowUp()
	{
		this.moveNode( 'up' )
	}
	
	moveNode( direction )
	{
		// the following check *must* be here for event propagation reasons
		if( !this.isSubtree && this.parent )
		{
			let uiparent = this.parent
			let treenode = this.treenode
			let treeparent = treenode.parent
			if( direction == 'down' )
			{
				moveNodeDown( treeparent, treenode )
				uiparent.moveNodeDown( this )
			}
			else
			{
				moveNodeUp( treeparent, treenode )
				uiparent.moveNodeUp( this )
			}
			UINode.onChange()
			treenode.elementLi.focus()
		}
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
					console.assert( ( field.type ?? 'string' ) === 'string' )
					self[field.key] = newValue
				}
				
				UINode.onChange()
				
				self.treenode.elementSpan.children[1].innerText = self.label
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
				tooltipped = newChild( label, 'span', { class: 'tooltipped' })
				inputParent = tooltipped
				
				tooltip = newChild( tooltipped, 'span', { class: 'tooltip' })
				tooltip.innerText = field.tooltip
			}
			else if ( field.input == 'checkbox' )
				inputParent = inputGroup
			
			if( field.input === 'select' || field.input === 'select2' )
			{
				let textable_span = null, toggle = null, text = null
				if( field.or_text )
				{
					textable_span = newChild( inputParent, 'span' )
					text = newChild( inputParent, 'input', { type: 'text', style: 'display:none' })
					if( field.maxlength )
						text.setAttribute( 'maxlength', field.maxlength )
					if( field.size )
						text.setAttribute( 'size', field.size )
					if( field.placeholder )
						text.setAttribute( 'placeholder', field.placeholder )
					let ttd = newChild( label, 'span', { class: 'tooltipped' })
					toggle = newChild( ttd, 'button' )
					toggle.innerText = '...'
					let tt = newChild( ttd, 'span', { class: 'tooltip' })
					tt.innerText = 'Toggles between the select box and a text box'
					
					inputParent = textable_span
				}
				
				input = newChild( inputParent, 'select', { id: id } )
				
				let selectedValue = this[field.key] ?? ''
				let options = await field.options( this )
				let nice_select = null
				let found = false
				for( let option of options )
				{
					let optionEl = newChild( input, 'option')
					optionEl.setAttribute( 'value', option.value )
					optionEl.innerText = option.label ?? option.value
					if ( selectedValue == ( option.value ?? option.label ))
					{
						optionEl.setAttribute( 'selected', 'selected' )
						found = true
					}
				}
				if( !found )
				{
					let optionEl = document.createElement( 'option' )
					optionEl.setAttribute( 'value', selectedValue )
					optionEl.setAttribute( 'selected', 'selected' )
					optionEl.innerText = selectedValue
					input.insertBefore( optionEl, input.firstChild )
				}
				
				if( field.input === 'select2' )
				{
					input.setAttribute( 'class', 'ace_select2' )
					input.style.display = 'none'
					changeevent = 'change'
					
					nice_select = NiceSelect.bind( input, { searchable: true } )
				}
				
				if( field.or_text )
				{
					toggle.onclick = function( evt )
					{
						let opts = input.getElementsByTagName( 'option' )
						if( text.style.display == 'none' )
						{
							// switching from select -> text
							if( nice_select == null )
							{
								// select (not select2) -> text
								for( let i = 0; i < opts.length; i++ )
								{
									let option = opts[i]
									if( option.getAttribute( 'selected' ))
									{
										text.value = option.value
										break
									}
								}
							}
							else
							{
								// select2 -> text
								// this may be fragile as it relies on the inner workings of select2
								let current = nice_select.dropdown.getElementsByClassName( 'current' )[0]
								text.value = current.innerText
							}
							textable_span.style.display = 'none'
							text.style.display = ''
						}
						else
						{
							// switching from text -> select
							let found = false
							if( nice_select == null )
							{
								// text -> select (not select2)
								for( let i = 0; i < opts.length; i++ )
								{
									let option = opts[i]
									if( text.value == option.value )
									{
										option.setAttribute( 'selected', 'selected' )
										found = true
									}
									else
										option.removeAttribute( 'select' )
								}
								if( !found )
								{
									let optionEl = document.createElement( 'option' )
									optionEl.setAttribute( 'value', text.value )
									optionEl.setAttribute( 'selected', 'selected' )
									optionEl.innerText = text.value
									input.insertBefore( optionEl, input.firstChild )
								}
							}
							else
							{
								// text -> select2
								// this may be fragile as it relies *extensively* on the inner workings of select2
								let current = nice_select.dropdown.getElementsByClassName( 'current' )[0]
								current.innerText = text.value
								
								let opts = nice_select.dropdown.getElementsByTagName( 'li' )
								for( let i = 0; i < opts.length; i++ )
								{
									let opt = opts[i]
									if( opt.innerText == text.value )
										opt.className = 'option selected null'
									else
										opt.className = 'option null'
								}
								if( !found )
								{
									let ul = nice_select.dropdown.getElementsByClassName( 'list' )[0]
									let li = document.createElement( 'li' )
									li.setAttribute( 'data-value', text.value )
									li.setAttribute( 'class', 'option selected null' )
									li.innerText = text.value
									ul.insertBefore( li, ul.firstChild )
								}
							}
							text.style.display = 'none'
							textable_span.style.display = ''
						}
					}
					text.addEventListener( 'input', onChangeEvent )
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
				input.innerText = this[field.key] ?? ''
			}
			else
			{
				input = newChild( inputParent, 'input', { id: id, type: field.input ?? 'text' } )
				
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
				input.value = this[field.key] ?? ''
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
	
	remove( uinode/*: UINode*/ )
	{
		this.children = this.children.filter( n =>
		{
			return n.treenode.id !== uinode.treenode.id
		})
	}
}
export{ UINode }

export function walkChild( uinode, callback )
{
	if( uinode )
		uinode.walkChildren( callback )
}
