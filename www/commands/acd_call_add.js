import UINode from './UINode.js'

export default class AcdCallAdd extends UINode {
	static icon = '/media/streamline/headphones-customer-support-human-1.png'
	static context_menu_name = 'ACD Call Add'
	static command = 'acd_call_add'
	
	help = `Queue the call into the ACD to be answered by an agent<br>
<br>
<font color=red>WARNING</font> Priority completely overrides queue time<br>
<br>
Offset is a much softer way to prioritize a call instead of the Priority value.`
	
	get label() {
		return `ACD Call Add: gates=${this.gates ?? ''}, priority=${this.priority ?? ''}, offset=${this.offset ?? ''}`
	}
	
	gates//: string
	priority//: number
	offset//: number
	
	fields = [{
		key: 'gates',
		label: 'Gates:',
		type: 'string',
		placeholder: 'Example: 1,2,3',
		tooltip: 'Comma-separted list of gates to put the call in (1-99)',
	},{
		key: 'priority',
		label: 'Priority:',
		type: 'int',
		tooltip: 'A value from 1-99, higher values get answered first. Completely overrides queue time: use sparingly'
	},{
		key: 'offset',
		label: 'Offset (seconds):',
		type: 'int',
		tooltip: "The number of seconds to artificially add to the caller's queue time",
	}]
}
