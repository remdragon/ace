import UINode from './UINode.js'

export default class AcdCallAdd extends UINode {
	static icon = '/media/streamline/headphones-customer-support-human-1.png'
	static context_menu_name = 'ACD Call Add'
	static command = 'acd_call_add'
	
	help = `Queue the call into the ACD to be answered by an agent<br>
<br>
Gates is a comma-separated list of gates to add the call to<br>
<br>
Priority is a value from 1 - 99, higher values get answered first<br>
<font color=red>WARNING</font> Priority completely overrides queue time, use it sparingly<br>
<br>
Offset is the number of seconds to artificially add to a caller's queue time. This is a much
softer way to prioritize a call instead of the Priority value.
`
	
	get label() {
		return `ACD Call Add: gates=${this.gates || ''}, priority=${this.priority || ''}, offset=${this.offset || ''}`
	}
	
	gates//: string
	priority//: number
	offset//: number
	
	fields = [
		{ key: 'gates', type: 'string' },
		{ key: 'priority', type: 'int' },
		{ key: 'offset', type: 'int' }
	]
}
