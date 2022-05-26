import UINode from './UINode.js'

export default class Lua extends UINode {
	static icon = '/media/streamline/robot-1.png'
	static context_menu_name = 'Lua'
	static command = 'lua'
	
	help = `Runs inline lua code.
`
	get label()
	{
		return 'Lua ' + this.name
	}
	
	name = ''
	source = ''
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'source',
		input: 'textarea',
		label: 'Source Code:',
		rows: 40,
		cols: 80,
	}]
}
