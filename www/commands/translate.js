import UINode from './UINode.js'
import Subtree from './subtree.js'

export default class Translate extends UINode {
	static icon = '/media/streamline/database-2.png'
	static context_menu_name = 'Translate'
	static command = 'translate'

	help = `Lookup info in a translation table and set any specified channel variables.<br/>
<br/>
If a match is found, the "hit" node will be executed.<br/>
<br/>
Otherwise the "miss" node will be executed<br/>
<br/>
*THIS COMMAND IS NOT IMPLEMENTED YET, PLEASE DO NOT TRY TO USE IT*`
	
	label = 'Translate'
	
	table//: string
	variable//: string
	
	hitBranch//: Subtree
	missBranch//: Subtree
	
	fields = [{ key: 'table' }, { key: 'variable' }]
	
	createElement({
		isSubtree = false,
		data = { hit: [], miss: [] },
		NODE_TYPES
	}) {
		super.createElement({ isSubtree, data, NODE_TYPES })

		this.hitBranch = new Subtree(this, 'hit')
		this.hitBranch.createElement({
			isSubtree: true,
			data: data.hit,
			NODE_TYPES
		})
		this.missBranch = new Subtree(this, 'miss')
		this.missBranch.createElement({
			isSubtree: true,
			data: data.miss,
			NODE_TYPES
		})
	}
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			hit: this.hitBranch.getJson(),
			miss: this.missBranch.getJson()
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		this.hitBranch.walkChildren( callback )
		this.missBranch.walkChildren( callback )
	}
}
