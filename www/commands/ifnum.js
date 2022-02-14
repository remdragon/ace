import{ UINode, walkChild } from './UINode.js'
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
	}) {
		super.createElement({ isSubtree, data })
		
		// TODO FIXME: makeFixedBranch
		this.trueBranch = new NamedSubtree( this, 'true' )
		this.trueBranch.createElement({
			isSubtree: true,
			data: data.trueBranch ?? {},
		})
		
		this.falseBranch = new NamedSubtree( this, 'false' )
		this.falseBranch.createElement({
			isSubtree: true,
			data: data.falseBranch ?? {},
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
		
		walkChild( this.trueBranch, callback )
		walkChild( this.falseBranch, callback )
	}
}
