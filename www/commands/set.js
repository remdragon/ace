import UINode from './UINode.js'

export default class Set extends UINode {
	static icon = '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'Set Variable'
	static command = 'set'
	
	help = 'Saves information in a channel variable<br/>'
	label = 'Set'
	
	name//: string
	value//: string
	
	fields = [{ key: 'name' }, { key: 'value' }]
}
