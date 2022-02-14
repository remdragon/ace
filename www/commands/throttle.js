import{ UINode, walkChild } from './UINode.js'

const ALLOWED_LABEL = 'Allowed'
const THROTTLED_LABEL = 'Throttled'

export default class Throttle extends UINode {
	static icon = '/media/streamline/volcano@22.png'
	static context_menu_name = 'Throttle'
	static command = 'throttle'
	
	allowed_subtree_help = 'Actions to execute if the call does not exceed throttling limits'
	throttled_subtree_help = 'Actions to execute if the call exceeds throttling limits'
	
	help =
		`Limit the number of calls based on the throttling parameters in DID setup`
	get label()
	{
		return `Throttle ${this.name || ''}`
	}
	
	name = '' // string
	allowedBranch = null // NamedSubtree
	throttledBranch = null // NamedSubtree
	
	fields = [{
		key: 'name',
		label: 'Name:',
	}]
	
	createElement({
		isSubtree = false,
		data = {}
	}) {
		super.createElement({ isSubtree, data })
		
		let context = null
		this.makeFixedBranch( 'allowedBranch', ALLOWED_LABEL,
			context,
			this.allowed_subtree_help,
			data,
		)
		this.makeFixedBranch( 'throttledBranch', THROTTLED_LABEL,
			context,
			this.throttled_subtree_help,
			data,
		)
	}
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			allowedBranch: this.allowedBranch.getJson(),
			throttledBranch: this.throttledBranch.getJson()
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		walkChild( this.allowedBranch, callback )
		walkChild( this.throttledBranch, callback )
	}
}
