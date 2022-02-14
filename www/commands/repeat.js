import{ UINode, walkChild } from './UINode.js'

export default class Repeat extends UINode {
	static icon = '/media/streamline/repeat.png'
	static context_menu_name = 'Repeat'
	static command = 'repeat'
	
	help =
		'This node runs all its commands in a loop until the repeat count is met or forever if count is 0'
	
	get label()
	{
		return 'Repeat ' + ( this.count || 'forever' )
	}
	
	count = 1//: number = 1
	
	createElement({
		isSubtree = true,
		data = [],
		context = this.contextOptionalSubtree(),
	})
	{
		super.createElement({ isSubtree, data, context })
		
		this.createChildren( data.nodes ?? [] )
	}
	
	fields = [
		{
			key: 'count',
			type: 'int'
		}
	]
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			nodes: this.children.map( node => node.getJson() )
		}
	}
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		for( let node of this.children )
		{
			walkChild( node, callback )
		}
	}
}
