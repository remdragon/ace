import{ UINode, walkChild } from './UINode.js'

export default class NamedSubtree extends UINode {
	static icon = ''
	static context_menu_name = 'N/A'
	static command = ''
	
	canPaste = true
	
	get label()
	{
		let label = this._label
		if( this.name )
			label += ' ' + this.name
		return label
	}
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	}]
	
	constructor(parent /*: UINode*/, label /*: string*/, help)
	{
		super(parent)
		
		this._label = label
		this.help = help || 'This is a named subtree node, click on the parent node for more information'
	}
	
	createElement({
		isSubtree,
		data = {},
		context,
	}) {
		super.createElement({
			isSubtree,
			data,
			context,
		})
		
		this.createChildren( data.nodes ?? [] )
	}

	getJson()/*: object*/ {
		const sup = super.getJson()
		delete sup.type
		return {
			...sup,
			nodes: this.children.map(node => node.getJson())
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		for( let node of this.children )
			walkChild( node, callback )
	}
}

UINode.NamedSubtree = NamedSubtree // chicken vs egg: gives UINode.makeFixedBranch access to this class
