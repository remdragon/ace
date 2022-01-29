import UINode from './UINode.js'
import Subtree from './subtree.js'

// TODO FIXME: the ability to "name" an IVR node and have that hsow up in the tree

export default class Ivr extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'IVR'
	static command = 'ivr'
	
	help = `This is the ivr node. This lets you play a greeting to your caller and collect digits from them.<br>
<br>
min_digits and max_digits are the minimum/maximum # of digits a caller must enter for the input to be valid<br>
<br>
max_attempts is the number of times the greeting will play while attempting to get a valid response<br>
<br>
timeout is the number of seconds it will wait for a valid response after finishing a greeting before starting next attempt (see max_attempts)<br>
<br>
terminators allows you define a dtmf such as # that the caller can use to terminate digit input<br>
<br>
greeting is the recording to play<br>
<br>
error is the recording to play if caller's input is not valid<br>
<br>
digit_regex is an advanced feature that defines what a valid input is, in addition to min_digits and max_digits. Note that the system will generate one for you based on the branches you add to this node.<br>
<br>
variable_name is an optional channel variable name where the collected digits can be stored<br>
<br>
digit_timeout is the numbers of seconds to wait in between each digit before considering the caller finished.<br>
<br>
`
	subtree_help = 'If the caller enters the digits indicated here, the commands under this node will be executed'
	invalid_subtree_help = 'If the caller fails to enter valid input, the commands under this node will be executed'
	label = 'IVR'
	
	min_digits//: int
	max_digits//: int
	max_attempts//: int
	timeout//: float
	terminators//: string
	greeting//: string
	error//: string
	digit_regex//: string
	variable_name//: string
	digit_timeout//: float
	
	branches = {}
	invalid//: invalid path...
	
	fields = [
		{ key: 'min_digits', type: 'int' },
		{ key: 'max_digits', type: 'int' },
		{ key: 'max_attempts', type: 'int' },
		{ key: 'timeout', type: 'number' },
		{ key: 'terminators', type: 'string' },
		{ key: 'greeting', type: 'string' },
		{ key: 'error', type: 'string' },
		{ key: 'digit_regex', type: 'string' },
		{ key: 'variable_name', type: 'string' },
		{ key: 'digit_timeout', type: 'number' },
	]
	
	createElement({
		isSubtree = false,
		data = { branches: {} },
		NODE_TYPES
	}) {
		this.min_digits = 1
		this.max_digits = 1
		this.max_attempts = 3
		this.timeout = 3
		this.terminators = ''
		this.greeting = ''
		this.error = 'ivr/ivr-that_was_an_invalid_entry.wav'
		this.digit_regex = ''
		this.variable_name = ''
		this.digit_timeout = 3
		
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
			context: 'contextIVR',
		})
		
		if ( data.branches )
		{
			let all_digits = []
			for( const digits in data.branches )
			{
				if ( data.branches[digits] )
					all_digits.push( digits )
			}
			all_digits.sort()
			for ( const digits of all_digits )
			{
				this.branches[digits] = new Subtree(
					this, digits, this.subtree_help
				)
				this.branches[digits].createElement({
					isSubtree: true,
					data: data.branches[digits],
					NODE_TYPES,
					context: 'contextIVRSubtree'
				})
			}
		}
		
		this.invalid = new Subtree( this, 'Invalid', this.invalid_subtree_help )
		this.invalid.createElement({
			isSubtree: true,
			data: data.invalid,
			NODE_TYPES
		})
	}
	
	reorder() {
		const domNodes = this.element.childNodes.sort((a, b) => {
			
			if( a.text === "Invalid" && b.text !== "Invalid" )
				return 1
			
			if( a.text !== "Invalid" && b.text === "Invalid" )
				return -1
			
			const aValue = parseInt( a.text )
			const bValue = parseInt( b.text )
			
			/*if (aValue === 0 && bValue !== 0) {
				return 1
			}
			
			if (aValue !== 0 && bValue === 0) {
				return -1
			}*/
			
			return aValue > bValue
		})
		
		const ulNode = this.element.childNodes[0].elementLi.parentNode
		
		domNodes.forEach(el => {
			ulNode.appendChild(el.elementLi)
		})
		
		// TODO: fix dotted lines after reordering
	}

	getJson() {
		const sup = super.getJson()
		
		const branchesData = {}
		for( const digits in this.branches )
		{
			let branch = this.branches[digits]
			if ( branch )
				branchesData[digits] = branch.getJson()
		}
		
		let invalid = null
		if ( this.invalid )
			invalid = this.invalid.getJson()
		
		return {
			...sup,
			branches: branchesData,
			invalid: invalid,
		}
	}
	
	remove(node/*: UINode*/) {
		super.remove(node)
		
		Object.keys(this.branches).some(key => {
			const branch = this.branches[key]
			
			if (branch.element.id === node.element.id) {
				delete this.branches[key]
				return true
			}
			
			return false
		})
	}
}
