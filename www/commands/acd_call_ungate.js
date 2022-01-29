import UINode from './UINode.js'

export default class AcdCallUnGate extends UINode {
	static icon = '/media/streamline/headphones-customer-support-human-1.png' // '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'ACD Call UnGate'
	static command = 'acd_call_ungate'
	
	help = 'Removes the call from an ACD gate/skill'
	get label() {
		return `ACD Call UnGate: gate=${this.gates || ''}`
	}
	
	gate//: number
	
	fields = [
		{key: 'gate', type: 'int'},
	]
}
