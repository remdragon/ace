import UINode from './UINode.js'

export default class Subtree extends UINode {
	static icon = ''
	static context_menu_name = 'N/A'
	static command = ''
	
	//help = 'This is a subtree node'
	label = ''
	
	constructor(parent /*: UINode*/, label /*: string*/, help)
	{
		super(parent)
		
		this.label = label
		this.help = help || 'This is a subtree node, click on the parent node for more information'
	}
	
	createElement({ isSubtree, data = {nodes:[]}, NODE_TYPES, context }) {
		super.createElement({ isSubtree, data, NODE_TYPES, context });
		
		if (data.nodes) {
			data.nodes.forEach((nodeData /*: any*/) => {
				//console.log( nodeData )
				let NodeType = NODE_TYPES[nodeData.type]
				if (NodeType) {
					let node = new NodeType(this);
					node.createElement({ data: nodeData, NODE_TYPES });
				}
			});
		}
	}

	getJson()/*: object*/ {
		const sup = super.getJson()
		return {
			...sup,
			nodes: this.children.map(node => node.getJson())
		}
	}
}
