import{ UINode, walkChild } from './UINode.js'

export default class RootRoute extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'N/A'
	static command = ''
	
	canPaste = true
	help = `This is the root node for your route<br/>
<br/>
Right-click on it to start adding instructions to your route.
`
	
	get label()
	{
		return `Route ${this.route} ${this.name || '(Unnamed)'}`
	}
	
	route//: integer
	name//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	}]
	
	constructor( tree, route, data )
	{
		super( null )
		this.tree = tree
		
		this.route = route
		this.name = data.name
		
		this.treenode = tree.createNode(
			this.label,
			true,
			RootRoute.icon,
			null,
			null,
			'contextRouteRoot'
		)
		
		this.treenode.uinode = this
		
		this.createChildren( data.nodes ?? [] )
	}
	
	getJson()
	{
		return {
			type: 'root_route',
			name: this.name,
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
