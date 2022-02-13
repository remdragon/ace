import{ UINode, walkChild } from './UINode.js'

export default class RootRoute extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'N/A'
	static command = ''
	
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
	
	fields = [
		{ key: 'name', type: 'string', label: 'Name: ' }
	]
	
	constructor( tree, route, data, NODE_TYPES )
	{
		super( null )
		this.tree = tree
		
		this.route = route
		this.name = data.name
		
		this.element = tree.createNode(
			this.label,
			true,
			RootRoute.icon,
			null,
			null,
			'contextRouteRoot'
		)
		
		this.element.node = this
		
		this.createChildren( data.nodes ?? [], NODE_TYPES )
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
