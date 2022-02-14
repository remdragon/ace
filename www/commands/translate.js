import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

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
	
	hitBranch//: NamedSubtree
	missBranch//: NamedSubtree
	
	fields = [{ key: 'table' }, { key: 'variable' }]
	
	createElement({
		isSubtree = false,
		data = {},
	}) {
		super.createElement({ isSubtree, data })
		
		// TODO FIXME: makeFixedBranch
		this.hitBranch = new NamedSubtree(this, 'hit')
		this.hitBranch.createElement({
			isSubtree: true,
			data: data.hit ?? {},
		})
		this.missBranch = new NamedSubtree(this, 'miss')
		this.missBranch.createElement({
			isSubtree: true,
			data: data.miss ?? {},
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
		walkChild( this.hitBranch, callback )
		walkChild( this.missBranch, callback )
	}
}
