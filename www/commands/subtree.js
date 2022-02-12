import UINode from './UINode.js'

export default class Subtree extends UINode {
	static icon = ''
	static context_menu_name = 'N/A'
	static command = ''
	
	//help = 'This is a subtree node'
	label = ''
	
	constructor( parent /*: UINode*/, label /*: string*/, help )
	{
		super( parent )
		
		this.label = label
		this.help = help || 'This is a subtree node, click on the parent node for more information'
	}
	
	createElement({
		isSubtree,
		data = {nodes:[]},
		NODE_TYPES,
		context,
	})
	{
		super.createElement({ isSubtree, data, NODE_TYPES, context })
		
		this.createChildren( data.nodes ?? [], NODE_TYPES )
	}
	
	getJson()//: object
	{
		const sup = super.getJson()
		//delete sup['type']
		return {
			...sup,
			nodes: this.children.map( node => node.getJson() )
		}
	}
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		for( let node of this.children )
			node.walkChildren( callback )
	}
}
