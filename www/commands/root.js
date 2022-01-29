import UINode from "./UINode.js";

export default class Root extends UINode {
	static icon = "/media/streamline/kindle.png";
	static context_menu_name = 'N/A'
	static command = "";
	
	help = `This is the root node for your route<br/>
<br/>
Right-click on it to start adding instructions to your route.<br/>
<br/>`
	
	get label()
	{
		return `${this.route} ${this.name || '(Unnamed)'}`
	}
	
	route//: integer
	name//: string
	
	fields = [
		{ key: 'name', type: 'string', label: 'Name: ' }
	]
	
	constructor( tree, route, data, NODE_TYPES )
	{
		super( null )
		
		this.route = route
		this.name = data.name
		
		this.element = tree.createNode(
			this.label,
			true,
			Root.icon,
			null,
			null,
			"contextSubtree"
		)
		
		this.element.node = this
		
		data.nodes.forEach(nodeData => {
			let NodeType = NODE_TYPES[nodeData.type]
			
			if (NodeType) {
				let node = new NodeType( this )
				node.createElement( { data: nodeData, NODE_TYPES } )
			}
		})
	}
	
	getJson() {
		return {
			name: this.name,
			nodes: this.children.map( node => node.getJson() )
		}
	}
}
