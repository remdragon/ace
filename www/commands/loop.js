import{ UINode, walkChild } from './UINode.js'

export default class Loop extends UINode {
	static icon = '/media/streamline/repeat.png'
	static context_menu_name = 'Loop'
	static command = 'repeat'
	
	canPaste = true
	help =
		`This node runs all its commands in a loop<br/>
<br/>
Loops forever if count is 0, otherwise stops after count is met`
	
	get label()
	{
		return 'Loop ' + ( this.name || this.count || 'forever' )
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
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'count',
		type: 'int',
		tooltip: 'How many times in total to execute the nodes inside here (use 0 for unlimited)',
		default: 0,
	}]
	
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
