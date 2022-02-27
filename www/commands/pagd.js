import{ UINode, walkChild } from './UINode.js'

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
	invalidBranch//: invalid branch...
	timeoutBranch//: timeout branch...
	failureBranch//: failure branch
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'min_digits',
		type: 'int',
		maxlength: 2,
		size: 3,
		label: 'Min Digits:',
		tooltip: 'minimum # of digits a caller must enter for the input to be valid, must be >= 0',
	},{
		key: 'max_digits',
		type: 'int',
		maxlength: 2,
		size: 3,
		label: 'Max Digits:',
		tooltip: 'maximum # of digits a caller must enter for the input to be valid, must be <= 128',
	},{
		key: 'max_attempts',
		type: 'int',
		maxlength: 2,
		size: 3,
		label: 'Max Attempts:',
		tooltip: 'the number of times the greeting will play while attempting to get a valid response',
	},{
		key: 'digit_regex',
		type: 'string',
		size: 30,
		label: 'Digit Pattern:',
		tooltip: 'Optional pattern that defines valid input (does not override min/max digits)',
	},{
		key: 'timeout',
		type: 'float',
		maxlength: 2,
		size: 3,
		label: 'Timeout (seconds):',
		tooltip: 'the number of seconds it will wait for a valid response after finishing a greeting before starting next attempt (see max_attempts)',
	},{
		key: 'terminators',
		type: 'string',
		maxlength: 12,
		size: 13,
		label: 'Terminators:',
		tooltip: 'allows you define a dtmf that the caller can use to terminate digit input (default is #)',
	},{
		key: 'variable_name',
		type: 'string',
		label: 'Variable Name:',
		tooltip: 'Channel variable name where the collected digits can be stored',
	},{
		key: 'digit_timeout',
		type: 'float',
		maxlength: 2,
		size: 3,
		label: 'Digit Timeout (seconds):',
		tooltip: 'the number of seconds to wait in between each digit before considering the caller finished.',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
	}){
		this.uuid = data.uuid || crypto.randomUUID()
		
		super.createElement({
			isSubtree,
			data,
			context: 'contextPAGD',
		})
		
		this.makeFixedBranch( 'greetingBranch', GREETING_LABEL,
			'context_GreetingInvalidTimeout',
			this.greeting_subtree_help,
			data,
		)
		this.makeFixedBranch( 'invalidBranch', INVALID_LABEL,
			'context_GreetingInvalidTimeout',
			this.invalid_subtree_help,
			data,
		)
		this.makeFixedBranch( 'timeoutBranch', TIMEOUT_LABEL,
			'context_GreetingInvalidTimeout',
			this.timeout_subtree_help,
			data,
		)
		this.makeFixedBranch( 'successBranch', SUCCESS_LABEL,
			'contextIVR_PAGD_SuccessFailure',
			this.success_subtree_help,
			data,
		)
		this.makeFixedBranch( 'failureBranch', FAILURE_LABEL,
			'contextIVR_PAGD_SuccessFailure',
			this.failure_subtree_help,
			data,
		)
	}
	
	reorder()
	{
		const domNodes = this.treenode.childNodes.sort(( a, b ) =>
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
		
		const ulNode = this.treenode.childNodes[0].elementLi.parentNode
		
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
}
