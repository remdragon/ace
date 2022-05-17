import{ UINode, walkChild } from './UINode.js'

const FAIL_LABEL = 'Fail'
const TIMEOUT_LABEL = 'Timeout'

export default class Bridge extends UINode {
	static icon = '/media/streamline/phone-actions-receive.png'
	static context_menu_name = 'Bridge'
	static command = 'bridge'
	
	help = `Executes the FreeSWITCH bridge command<br/>
<br/>
This is an advanced feature that uses the FreeSWITCH's <a href="https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+bridge">"bridge" dialplan application</a><br/>
<br/>
Timeouts execute the timeout branch before continuing on past the bridge.<br/>
Failures will execute the fail branch before continuing<br/>
<br/>
IMPORTANT: If the bridge succeeds and gets answered, execution stops here and does not continue`
	
	fail_subtree_help = 'Commands to execute if the bridge command fails'
	timeout_subtree_help = 'Commands to execute if the bridge command times out before being answered'
	
	get label()
	{
		if( this.name )
			return 'Bridge ' + this.name
		else
			return 'Bridge ' + ( this.dial_string || '' )
	}
	
	name = ''//: string
	dial_string = ''//: string
	dialplan = ''
	context = ''
	cid_name = ''
	cid_num = ''
	timeout//: int
	failBranch = null
	timeoutBranch = null
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'dial_string',
		label: 'Dial String:',
		size: 50,
		tooltip: 'See the link above for FreeSWITCH documentation about this command',
	},{
		key: 'dialplan',
		label: 'Dial Plan:',
		tooltip: 'An advanced setting, leave blank for default of "xml"',
	},{
		key: 'context',
		label: 'Context:',
		tooltip: 'An advanced setting, leave blank for default of "default"',
	},{
		key: 'cid_name',
		label: 'Caller Name:',
		tooltip: 'leave blank to inherit',
	},{
		key: 'cid_num',
		label: 'Caller ID Number:',
		tooltip: 'leave blank to inherit',
	},{
		key: 'timeout',
		label: 'Call Timeout (seconds):',
		size: 4,
		tooltip: 'Time to wait for bridge to be answered before timing out (blank or 0 = wait forever)',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
		context = this.contextOptionalSubtree(),
	}) {
		super.createElement({ isSubtree, data })
		
		this.makeFixedBranch( 'failBranch', FAIL_LABEL,
			context,
			this.fail_subtree_help,
			data ?? {},
		)
		this.makeFixedBranch( 'timeoutBranch', TIMEOUT_LABEL,
			context,
			this.timeout_subtree_help,
			data ?? {},
		)
	}
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			failBranch: this.failBranch.getJson(),
			timeoutBranch: this.timeoutBranch.getJson()
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		walkChild( this.failBranch, callback )
		walkChild( this.timeoutBranch, callback )
	}
}
