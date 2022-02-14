import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

const TRUE_LABEL = 'True'
const FALSE_LABEL = 'False'

export default class IfStr extends UINode {
	static icon = '/media/streamline/road-sign-look-both-ways-1.png'
	static context_menu_name = 'IfStr'
	static command = 'ifstr'
	
	help = `Test for a condition using an alphabetical comparison, i.e. "1000" < "11".<br/>
<br/>
If a numerical comparison where 1000 > 11, use the IfNum node instead<br/>
<br/>
If the condition is true, execute the "${TRUE_LABEL}" branch, otherwise the "${FALSE_LABEL}" branch`
	get label()
	{
		return 'IfStr ' + ( this.lhs || '?' ) + ' ' + ( this.op || '?' ) + ' ' + ( this.rhs || '?' )
	}
	
	lhs//: string
	op//: string
	rhs//: string
	case//: boolean
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
				{ label: 'begins-with', value: 'begins-with' },
				{ label: 'contains', value: 'contains' },
				{ label: 'ends-with', value: 'ends-with' },
			]
		}
	},{
		key: 'rhs',
		label: 'Right Operand:',
		tooltip: 'You can type a literal string here or reference a channel variable like ${destination_number} or a global variable like $${hold_music}',
	},{
		key: 'case',
		label: 'Case Sensitive',
		input: 'checkbox',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
	}) {
		super.createElement({ isSubtree, data })
		
		let context = null // use the default
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
