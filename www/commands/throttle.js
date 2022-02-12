import UINode from './UINode.js'
import NamedSubtree from './named_subtree.js'

export default class Throttle extends UINode {
	static icon = '/media/streamline/volcano@22.png'
	static context_menu_name = 'Throttle'
	static command = 'throttle'
	
	help =
		`Limit the number of calls based on the throttling parameters in DID setup`
	get label()
	{
		return `Throttle ${this.name || ''}`
	}
	
	name//: string
	allowedBranch//: NamedSubtree
	throttledBranch//: NamedSubtree
	
	fields = [{
		key: 'name',
		label: 'Name:',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
		NODE_TYPES
	}) {
		super.createElement({ isSubtree, data, NODE_TYPES })
		
		this.allowedBranch = new NamedSubtree( this, 'allowed' )
		this.allowedBranch.createElement({
			isSubtree: true,
			data: data.allowedBranch ?? {},
			NODE_TYPES
		})
		
		this.throttledBranch = new NamedSubtree( this, 'throttled' )
		this.throttledBranch.createElement({
			isSubtree: true,
			data: data.throttledBranch ?? {},
			NODE_TYPES
		})
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
		
		if( this.allowedBranch )
			this.allowedBranch.walkChildren( callback )
		if( this.throttledBranch )
			this.throttledBranch.walkChildren( callback )
	}
}
