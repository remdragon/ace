import UINode from './UINode.js'

export default class NamedSubtree extends UINode {
	static icon = ''
	static context_menu_name = 'N/A'
	static command = ''
	
	get label()
	{
		let label = this._label
		if( this.name )
			label += ' ' + this.name
		return label
	}
	
	fields = [
		{
			key: 'name',
			label: 'Name: ',
		},
	]
	
	constructor(parent /*: UINode*/, label /*: string*/, help)
	{
		super(parent)
		
		this._label = label
		this.help = help || 'This is a named subtree node, click on the parent node for more information'
	}
	
	createElement({
		isSubtree,
		data = {},
		NODE_TYPES,
		context,
	}) {
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
			context,
		})
		
		this.createChildren( data.nodes ?? [], NODE_TYPES )
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
			node.walkChildren( callback )
	}
}
