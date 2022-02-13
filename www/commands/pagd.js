import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

const GREETING_LABEL = 'Greeting'
const INVALID_LABEL = 'Invalid'
const TIMEOUT_LABEL = 'Timeout'
const SUCCESS_LABEL = 'Success'
const FAILURE_LABEL = 'Failure'

export default class PAGD extends UINode {
	static icon = '/media/streamline/login-dial-pad-finger-password.png'
	static context_menu_name = 'PAGD'
	static command = 'pagd'
	
	help = `This lets you play a greeting to your caller and collect digits from them.<br/>
<br/>
Add branches to the node by right-clicking on it.<br/>
<br/>
<a href='https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+play_and_get_digits'>FreeSWITCH documentation on "Play And Get Digits"</a><br/>
<br/>
<a href='https://freeswitch.org/confluence/display/FREESWITCH/Regular+Expression'>FreeSWITCH documentation on Digit Patterns</a>
`
	greeting_subtree_help = 'Add nodes here to define what the caller hears while waiting for them to input digits'
	invalid_subtree_help = `If the caller enters digits but they fail to match the input criteria, these commands will be executed<br/>
<br/>
Note that this branch does not execute after the last attempt. Instead the failure branch executes`
	timeout_subtree_help = `If the caller does not enter any digits at all before the greeting finishes, these commands will be executed<br/>
<br/>
Note that this branch does not execute after the last attempt. Instead the failure branch executes`
	success_subtree_help = `This branch executes if the caller enters digits that match all the criteria`
	failure_subtree_help = `This branch executes if the caller exhausts all their attempts and never enters digits that match the input criteria`
	
	get label()
	{
		return `PAGD ${this.name ?? ''}`
	}
	
	name = ''
	min_digits = 1 //: int
	max_digits = 1 //: int
	max_attempts = 3 //: int
	timeout = 3.0 //: float
	terminators = '' //: string
	digit_regex = '' //: string
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
		key: 'digit_regex',
		type: 'string',
		size: 30,
		label: 'Digit Pattern: ',
		tooltip: 'Optional pattern that defines valid input (does not override min/max digits)',
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
		tooltip: 'Channel variable name where the collected digits can be stored',
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
		this.uuid = data.uuid || crypto.randomUUID()
		
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
			context: 'contextPAGD',
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
		
		this.successBranch = new NamedSubtree( this, SUCCESS_LABEL,
			this.success_subtree_help,
		)
		this.successBranch.createElement(
		{
			isSubtree: true,
			data: data.successBranch ?? {},
			NODE_TYPES,
			context: 'contextIVR_PAGD_SuccessFailure',
		})
		
		this.failureBranch = new NamedSubtree( this, FAILURE_LABEL,
			this.failure_subtree_help,
		)
		this.failureBranch.createElement(
		{
			isSubtree: true,
			data: data.failureBranch ?? {},
			NODE_TYPES,
			context: 'contextIVR_PAGD_SuccessFailure',
		})
	}
	
	reorder()
	{
		const domNodes = this.element.childNodes.sort(( a, b ) =>
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
			
			// success sits where IVR digits go
			if( a.text === SUCCESS_LABEL )
				return 1
			if( b.text === SUCCESS_LABEL )
				return -1
			
			// shouldn't be possible to get here...
			const aValue = parseInt( a.text )
			const bValue = parseInt( b.text )
			
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
		
		let greetingBranch = null
		if( this.greetingBranch )
			greetingBranch = this.greetingBranch.getJson()//.nodes
		let invalidBranch = null
		if( this.invalidBranch )
			invalidBranch = this.invalidBranch.getJson()//.nodes
		let timeoutBranch = null
		if( this.timeoutBranch )
			timeoutBranch = this.timeoutBranch.getJson()//.nodes
		let successBranch = null
		if( this.successBranch )
			successBranch = this.successBranch.getJson()//.nodes
		let failureBranch = null
		if( this.failureBranch )
			failureBranch = this.failureBranch.getJson()//.nodes
		
		return {
			...sup,
			uuid: this.uuid,
			greetingBranch: greetingBranch,
			invalidBranch: invalidBranch,
			timeoutBranch: timeoutBranch,
			successBranch: successBranch,
			failureBranch: failureBranch,
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		walkChild( this.greetingBranch, callback )
		walkChild( this.invalidBranch, callback )
		walkChild( this.timeoutBranch, callback )
		walkChild( this.successBranch, callback )
		walkChild( this.failureBranch, callback )
	}
	
	remove( node/*: UINode*/ )
	{
		super.remove( node )
		
		// TODO FIXME: this code is wrong, need to figure out how to fix it
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
