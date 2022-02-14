import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

export default class IfStr extends UINode {
	static icon = '/media/streamline/road-sign-look-both-ways-1.png'
	static context_menu_name = 'IfStr'
	static command = 'ifstr'
	
	help =
		`Test the condition.<br/>
<br/>
If the condition is true, execute the "true" branch, otherwise the "false" branch`
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
		
		// TODO FIXME: makeFixedBranch
		this.trueBranch = new NamedSubtree(this, 'true')
		this.trueBranch.createElement({
			isSubtree: true,
			data: data.trueBranch ?? {},
		})
		
		this.falseBranch = new NamedSubtree(this, 'false')
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
