import UINode from './UINode.js'
import NamedSubtree from './named_subtree.js'

export default class IfNum extends UINode {
	static icon = '/media/streamline/road-sign-look-both-ways-1.png'
	static context_menu_name = 'IfNum'
	static command = 'ifnum'
	
	help =
		`Converts both operands to numeric values and tests the condition.<br/>
<br/>
If the condition is true, execute the "true" branch, otherwise the "false" branch`
	get label()
	{
		return 'IfNum ' + ( this.lhs || '?' ) + ' ' + ( this.op || '?' ) + ' ' + ( this.rhs || '?' )
	}
	
	lhs//: string
	op//: string
	rhs//: string
	trueBranch//: NamedSubtree
	falseBranch//: NamedSubtree
	
	fields = [{
		key: 'lhs',
		label: 'Left Operand:',
		tooltip: 'You can type a literal string here or reference a channel variable like ${destination_number} or a global variable like $${hold_music}',
	},{
		key: 'op',
		label: 'Comparison:',
		input: 'select',
		async options(){
			return [
				{ label: '(choose one)', value: '' },
				{ label: '<=', value: '<=' },
				{ label: '<', value: '<' },
				{ label: '=', value: '=' },
				{ label: '!=', value: '!=' },
				{ label: '>', value: '>' },
				{ label: '>=', value: '>=' },
			]
		}
	},{
		key: 'rhs',
		label: 'Right Operand:',
		tooltip: 'You can type a literal string here or reference a channel variable like ${destination_number} or a global variable like $${hold_music}',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
		NODE_TYPES
	}) {
		super.createElement({ isSubtree, data, NODE_TYPES })
		
		this.trueBranch = new NamedSubtree( this, 'true' )
		this.trueBranch.createElement({
			isSubtree: true,
			data: data.trueBranch ?? {},
			NODE_TYPES
		})
		
		this.falseBranch = new NamedSubtree( this, 'false' )
		this.falseBranch.createElement({
			isSubtree: true,
			data: data.falseBranch ?? {},
			NODE_TYPES
		})
	}
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			trueBranch: this.trueBranch.getJson(),
			falseBranch: this.falseBranch.getJson()
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		this.trueBranch.walkChildren( callback )
		this.falseBranch.walkChildren( callback )
	}
}
