import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

const HIT_LABEL = 'Hit'
const MISS_LABEL = 'Miss'

export default class Translate extends UINode {
	static icon = '/media/streamline/database-2.png'
	static context_menu_name = 'Translate'
	static command = 'translate'
	
	help = `Lookup info in a translation table and set any specified channel variables.<br/>
<br/>
If a match is found, the "${HIT_LABEL}" node will be executed.<br/>
<br/>
Otherwise the "${MISS_LABEL}" node will be executed<br/>
<br/>
*THIS COMMAND IS NOT IMPLEMENTED YET, PLEASE DO NOT TRY TO USE IT*`
	hit_help = 'These instructions will execute if a match is found in the table'
	miss_help = 'These instructions will execute if no match was found in the table'
	
	label = 'Translate'
	
	name = '' // string
	table = '' // string
	expression = '' // string
	
	hitBranch = null // NamedSubtree
	missBranch = null // NamedSubtree
	
	fields = [{
		key: 'name',
		label: 'Name:',
	},{
		key: 'table',
		label: 'Table:',
	},{
		key: 'expression',
		label: 'Expression:',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
	}) {
		super.createElement({ isSubtree, data })
		
		let context = null // use the default
		this.makeFixedBranch( 'hitBranch', HIT_LABEL,
			context,
			this.hit_help,
			data ?? {},
		)
		this.makeFixedBranch( 'missBranch', MISS_LABEL,
			context,
			this.miss_help,
			data ?? {},
		)
	}
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			hitBranch: this.hitBranch.getJson(),
			missBranch: this.missBranch.getJson()
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		walkChild( this.hitBranch, callback )
		walkChild( this.missBranch, callback )
	}
}
