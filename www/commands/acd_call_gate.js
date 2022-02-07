import UINode from './UINode.js'

export default class AcdCallGate extends UINode {
	static icon = '/media/streamline/headphones-customer-support-human-1.png' // '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'ACD Call Gate'
	static command = 'acd_call_gate'
	
	help = `Add the call to an additional ACD gate/skill<br/>
<br/>
<font color=red>WARNING</font> Priority completely overrides queue time`
	get label() {
		return `ACD Call Gate: gate=${this.gates ?? ''}, priority=${this.priority ?? ''}`
	}
	
	gate//: number
	priority//: number
	
	fields = [{
		key: 'gate',
		type: 'int',
		tooltip: 'The new gate number (1-99) for this call, does not remove call from any existing gates',
	},{
		key: 'priority',
		type: 'int',
		tooltip: "Priority value (1-99) of the call's membership in this gate.",
	}]
}
