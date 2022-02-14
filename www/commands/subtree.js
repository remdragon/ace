import{ UINode, walkChild } from './UINode.js'

export default class Subtree extends UINode {
	static icon = ''
	static context_menu_name = 'N/A'
	static command = ''
	
	canPaste = true
	
	//help: string = ...
	label = ''
	
	constructor( parent /*: UINode*/, label /*: string*/, help )
	{
		super( parent )
		
		this.label = label
		this.help = help || 'This is a subtree node, click on the parent node for more information'
	}
	
	createElement({
		isSubtree,
		data = [],
		context,
	})
	{
		super.createElement({
			isSubtree,
			data,
			context,
		})
		
		this.createChildren( data.nodes ?? [] )
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
			walkChild( node, callback )
	}
}
