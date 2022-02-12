import UINode from './UINode.js'
import NamedSubtree from './named_subtree.js'

const GREETING_LABEL = 'Greeting'
const INVALID_LABEL = 'Invalid'
const TIMEOUT_LABEL = 'Timeout'
const FAILURE_LABEL = 'Failure'

export default class IVR extends UINode {
	static icon = '/media/streamline/login-dial-pad-finger-password.png'
	static context_menu_name = 'IVR'
	static command = 'ivr'
	
	help = `This lets you play a greeting to your caller and collect digits from them.<br/>
<br/>
Add branches to the node by right-clicking on it.<br/>
<br/>
<a href='https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+play_and_get_digits'>See FreeSWITCH documentation</a>`
	
	digits_subtree_help = 'If the caller enters the digits indicated here, the commands under this node will be executed<br/>'
	greeting_subtree_help = 'Add nodes here to define what the caller hears while waiting for them to input digits'
	invalid_subtree_help = `If the caller enters digits but they fail to match any defined digits branches, these commands will be executed<br/>
<br/>
Note that this branch does not execute after the last attempt. Instead the failure branch executes`
	timeout_subtree_help = `If the caller does not enter any digits at all before the greeting finishes, these commands will be executed<br/>
<br/>
Note that this branch does not execute after the last attempt. Instead the failure branch executes`
	failure_subtree_help = `This branch executes if the caller exhausts all their attempts and never enters digits that match any of the defined digits branches`
	
	get label()
	{
		return `IVR ${this.name ?? ''}`
	}
	
	name = ''
	min_digits = 1 //: int
	max_digits = 1 //: int
	max_attempts = 3 //: int
	timeout = 3.0 //: float
	terminators = '' //: string
	variable_name = '' //: string
	digit_timeout = 3.0 //: float
	
	greetingBranch//: greeting branch...
	branches = {}
	invalidBranch//: invalid branch...
	timeoutBranch//: timeout branch...
	failureBranch//: failure branch
	
	fields = [{
		key: 'name',
		type: 'string',
		label: 'Name: ',
		tooltip: "What's in a name? This is for documentation purposes only",
	},{
		key: 'min_digits',
		type: 'int',
		maxlength: 2,
		size: 3,
		label: 'Min Digits: ',
		tooltip: 'minimum # of digits a caller must enter for the input to be valid, must be >= 0',
	},{
		key: 'max_digits',
		type: 'int',
		maxlength: 2,
		size: 3,
		label: 'Max Digits: ',
		tooltip: 'maximum # of digits a caller must enter for the input to be valid, must be <= 128',
	},{
		key: 'max_attempts',
		type: 'int',
		maxlength: 2,
		size: 3,
		label: 'Max Attempts: ',
		tooltip: 'the number of times the greeting will play while attempting to get a valid response',
	},{
		key: 'timeout',
		type: 'float',
		maxlength: 2,
		size: 3,
		label: 'Timeout (seconds): ',
		tooltip: 'the number of seconds it will wait for a valid response after finishing a greeting before starting next attempt (see max_attempts)',
	},{
		key: 'terminators',
		type: 'string',
		maxlength: 12,
		size: 13,
		label: 'Terminators: ',
		tooltip: 'allows you define a dtmf that the caller can use to terminate digit input (default is #)',
	},{
		key: 'variable_name',
		type: 'string',
		label: 'Variable Name: ',
		tooltip: 'Optional channel variable name where the collected digits can be stored',
	},{
		key: 'digit_timeout',
		type: 'float',
		maxlength: 2,
		size: 3,
		label: 'Digit Timeout (seconds): ',
		tooltip: 'the number of seconds to wait in between each digit before considering the caller finished.',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
		NODE_TYPES,
	}){
		this.uuid = data.uuid ?? crypto.randomUUID()
		
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
			context: 'contextIVR',
		})
		
		this.greetingBranch = new NamedSubtree( this, GREETING_LABEL,
			this.greeting_subtree_help,
		)
		this.greetingBranch.createElement({
			isSubtree: true,
			data: data.greetingBranch ?? {},
			NODE_TYPES,
			context: 'contextIVR_PAGD_GreetingInvalidTimeout',
		})
		
		if ( data.branches )
		{
			this.branches = {}
			let all_digits = []
			for( const digits in data.branches )
				all_digits.push( digits )
			all_digits.sort()
			for( const digits of all_digits )
			{
				//console.log( `ivr.createElement: digits=${digits}` )
				this.branches[digits] = new NamedSubtree(
					this, digits, this.digits_subtree_help,
				)
				this.branches[digits].createElement({
					isSubtree: true,
					data: data.branches[digits] ?? {},
					NODE_TYPES,
					context: 'contextIVRBranch',
				})
			}
		}
		
		this.invalidBranch = new NamedSubtree( this, INVALID_LABEL,
			this.invalid_subtree_help,
		)
		this.invalidBranch.createElement({
			isSubtree: true,
			data: data.invalidBranch ?? {},
			NODE_TYPES,
			context: 'contextIVR_PAGD_GreetingInvalidTimeout',
		})
		
		this.timeoutBranch = new NamedSubtree( this, TIMEOUT_LABEL,
			this.timeout_subtree_help,
		)
		this.timeoutBranch.createElement({
			isSubtree: true,
			data: data.timeoutBranch ?? {},
			NODE_TYPES,
			context: 'contextIVR_PAGD_GreetingInvalidTimeout',
		})
		
		this.failureBranch = new NamedSubtree( this, FAILURE_LABEL,
			this.failure_subtree_help,
		)
		this.failureBranch.createElement({
			isSubtree: true,
			data: data.failureBranch ?? {},
			NODE_TYPES,
			context: 'contextIVR_PAGD_SuccessFailure',
		})
	}
	
	reorder()
	{
		let treenode = this.element
		const domNodes = treenode.childNodes.sort(( a, b ) =>
		{
			// greeting is always at the top:
			if( a.text === GREETING_LABEL )
				return -1
			if( b.text === GREETING_LABEL )
				return 1
			
			// invalid is always right below greeting
			if( a.text === INVALID_LABEL )
				return -1
			if( b.text === INVALID_LABEL )
				return 1
			
			// timeout is always right below invalid
			if( a.text === TIMEOUT_LABEL )
				return -1
			if( b.text === TIMEOUT_LABEL )
				return 1
			
			// failure is always the very bottom
			if( a.text === FAILURE_LABEL )
				return 1
			if( b.text === FAILURE_LABEL )
				return -1
			
			// what's left is the digits branches:
			const aValue = parseInt( a.text )
			const bValue = parseInt( b.text )
			
			return aValue - bValue
		})
		
		const ulNode = treenode.childNodes[0].elementLi.parentNode
		
		domNodes.forEach( el =>
		{
			ulNode.appendChild( el.elementLi )
		})
		
		// fix dotted lines after reordering:
		/*let id = treenode.parent.id
		let ulElement = document.getElementById( `ul_${id}` )
		console.log( 'id=', id, 'ulElement=', ulElement )
		this.tree.adjustLines( ulElement, false ) // <<< this doesn't work sadly*/
	}
	
	getJson()
	{
		const sup = super.getJson()
		
		let greetingBranch = null
		if( this.greetingBranch )
			greetingBranch = this.greetingBranch.getJson()//.nodes
		let invalidBranch = null
		if( this.invalidBranch )
			invalidBranch = this.invalidBranch.getJson()//.nodes
		let timeoutBranch = null
		if( this.timeoutBranch )
			timeoutBranch = this.timeoutBranch.getJson()//.nodes
		
		const branchesData = {}
		for( const digits in this.branches )
		{
			let branch = this.branches[digits]
			branchesData[digits] = branch ? branch.getJson() : {}
		}
		
		let failureBranch = null
		if( this.failureBranch )
			failureBranch = this.failureBranch.getJson()//.nodes
		
		return {
			...sup,
			uuid: this.uuid,
			greetingBranch: greetingBranch,
			invalidBranch: invalidBranch,
			timeoutBranch: timeoutBranch,
			branches: branchesData,
			failureBranch: failureBranch,
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		if( this.greetingBranch )
			this.greetingBranch.walkChildren( callback )
		if( this.invalidBranch )
			this.invalidBranch.walkChildren( callback )
		if( this.timeoutBranch )
			this.timeoutBranch.walkChildren( callback )
		for( let digits in this.branches )
		{
			let node = this.branches[digits]
			if ( node )
				node.walkChildren( callback )
		}
		if( this.failureBranch )
			this.failureBranch.walkChildren( callback )
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
