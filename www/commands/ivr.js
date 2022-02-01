import UINode from './UINode.js'
import Subtree from './subtree.js'
import NamedSubtree from './named_subtree.js'
import sounds_options from '/util/sounds_options.js'

/*
TODO FIXME: ability to "name" branch nodes themselves for documentation purposes
*/

export default class Ivr extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'IVR'
	static command = 'ivr'
	
	help = `This lets you play a greeting to your caller and collect digits from them.<br/>
<br/>
Add branches to the node by right-clicking on it.<br/>
<br/>
`
	subtree_help = 'If the caller enters the digits indicated here, the commands under this node will be executed<br/>'
	invalid_subtree_help = 'If the caller fails to enter valid input, the commands under this node will be executed'
	
	get label()
	{
		return `IVR ${this.name || "(Unnamed)"}`
	}
	
	name = ''
	min_digits = 1 //: int
	max_digits = 1 //: int
	max_attempts = 3 //: int
	timeout = 3.0 //: float
	terminators = '' //: string
	greeting = '' //: string
	error = 'ivr/ivr-that_was_an_invalid_entry.wav' //: string
	digit_regex = '' //: string
	variable_name = '' //: string
	digit_timeout = 3.0 //: float
	
	branches = {}
	invalid//: invalid path...
	
	fields = [
		{
			key: 'name',
			type: 'string',
			label: 'Name: ',
			tooltip: "What's in a name? This is for documentation purposes only",
		},
		{
			key: 'min_digits',
			type: 'int',
			maxlength: 2,
			size: 3,
			label: 'Min Digits: ',
			tooltip: 'minimum # of digits a caller must enter for the input to be valid',
		},
		{
			key: 'max_digits',
			type: 'int',
			maxlength: 2,
			size: 3,
			label: 'Max Digits: ',
			tooltip: 'maximum # of digits a caller must enter for the input to be valid',
		},
		{
			key: 'max_attempts',
			type: 'int',
			maxlength: 2,
			size: 3,
			label: 'Max Attempts: ',
			tooltip: 'the number of times the greeting will play while attempting to get a valid response',
		},
		{
			key: 'timeout',
			type: 'number',
			maxlength: 2,
			size: 3,
			label: 'Timeout (seconds): ',
			tooltip: 'the number of seconds it will wait for a valid response after finishing a greeting before starting next attempt (see max_attempts)',
		},
		{
			key: 'terminators',
			type: 'string',
			maxlength: 12,
			size: 13,
			label: 'Terminators: ',
			tooltip: 'allows you define a dtmf such as # that the caller can use to terminate digit input',
		},
		{
			key: 'greeting',
			input: 'select2',
			label: 'Greeting Prompt: ',
			tooltip: 'the recording to play instructing the caller what digits are expected',
			async options() {
				return await sounds_options()
			}
		},
		{
			key: 'error',
			input: 'select2',
			label: 'Error Prompt: ',
			tooltip: "the recording to play if caller's input is not valid",
			async options() {
				return await sounds_options()
			}
		},
		{
			key: 'digit_regex',
			type: 'string',
			label: 'Digit Regex: ',
			tooltip: 'an advanced feature that defines what a valid input is, in addition to min_digits and max_digits. Note that the system will generate one for you based on the branches you add to this node.',
		},
		{
			key: 'variable_name',
			type: 'string',
			label: 'Variable Name: ',
			tooltip: 'an optional channel variable name where the collected digits can be stored',
		},
		{
			key: 'digit_timeout',
			type: 'number',
			maxlength: 2,
			size: 3,
			label: 'Digit Timeout (seconds): ',
			tooltip: 'the number of seconds to wait in between each digit before considering the caller finished.',
		},
	]
	
	createElement({
		isSubtree = false,
		data = { branches: {} },
		NODE_TYPES,
	}) {
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
				all_digits.push( digits )
			all_digits.sort()
			for ( const digits of all_digits )
			{
				//console.log( `ivr.createElement: digits=${digits}` )
				this.branches[digits] = new NamedSubtree(
					this, digits, this.subtree_help
				)
				this.branches[digits].createElement({
					isSubtree: true,
					data: data.branches[digits],
					NODE_TYPES,
					context: 'contextIVRBranch',
				})
			}
		}
		
		this.invalid = new Subtree( this, 'Invalid',
			this.invalid_subtree_help,
		)
		this.invalid.createElement(
		{
			isSubtree: true,
			data: { type: '', nodes: data.invalid },
			NODE_TYPES,
			context: 'contextIVRInvalid',
		})
	}
	
	reorder()
	{
		const domNodes = this.element.childNodes.sort(( a, b ) =>
		{
			if( a.text === 'Invalid' && b.text !== 'Invalid' )
				return 1
			
			if( a.text !== 'Invalid' && b.text === 'Invalid' )
				return -1
			
			const aValue = parseInt( a.text )
			const bValue = parseInt( b.text )
			
			/*if (aValue === 0 && bValue !== 0) {
				return 1
			}
			
			if (aValue !== 0 && bValue === 0) {
				return -1
			}*/
			
			return aValue - bValue
		})
		
		const ulNode = this.element.childNodes[0].elementLi.parentNode
		
		domNodes.forEach(el =>
		{
			ulNode.appendChild( el.elementLi )
		})
		
		// TODO: fix dotted lines after reordering
	}

	getJson()
	{
		const sup = super.getJson()
		
		const branchesData = {}
		for( const digits in this.branches )
		{
			let branch = this.branches[digits]
			branchesData[digits] = branch ? branch.getJson() : {}
		}
		
		let invalid = null
		if( this.invalid )
			invalid = this.invalid.getJson().nodes
		
		return {
			...sup,
			branches: branchesData,
			invalid: invalid,
		}
	}
	
	remove( node/*: UINode*/ )
	{
		super.remove( node )
		
		Object.keys( this.branches ).some( key =>
		{
			const branch = this.branches[key]
			
			if( branch.element.id === node.element.id )
			{
				delete this.branches[key]
				return true
			}
			
			return false
		})
	}
}
