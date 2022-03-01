import{ UINode, walkChild } from './UINode.js'

const TRUE_LABEL = 'True'
const FALSE_LABEL = 'False'

export default class IfNum extends UINode {
	static icon = '/media/streamline/road-sign-look-both-ways-1.png'
	static context_menu_name = 'IfNum'
	static command = 'ifnum'
	
	help = `Convert both values to a number and test for a condition i.e. 1000 > 11.<br/>
<br/>
If an alphabetical comparison where "1000" < "11", use the IfStr node instead<br/>
<br/>
If the condition is true, execute the "${TRUE_LABEL}" branch, otherwise the "${FALSE_LABEL}" branch`
	true_subtree_help = 'commands to execute if the condition result is "true"'
	false_subtree_help = 'commands to execute if the condition result is "true"'
	
	get label()
	{
		return 'IfNum ' + ( this.lhs || '?' ) + ' ' + ( this.op || '?' ) + ' ' + ( this.rhs || '?' )
	}
	
	lhs//: string
	op//: string
	rhs//: string
	trueBranch = null//: NamedSubtree
	falseBranch = null//: NamedSubtree
	
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
		context = this.contextOptionalSubtree(),
	}) {
		super.createElement({ isSubtree, data })
		
		this.makeFixedBranch( 'trueBranch', TRUE_LABEL,
			context,
			this.true_subtree_help,
			data ?? {},
		)
		this.makeFixedBranch( 'falseBranch', FALSE_LABEL,
			context,
			this.false_subtree_help,
			data ?? {},
		)
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
