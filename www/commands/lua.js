import UINode from './UINode.js'

export default class Lua extends UINode {
	static icon = '/media/streamline/robot-1.png'
	static context_menu_name = 'Lua'
	static command = 'lua'
	
	help = `Runs inline lua code.<br/>
<br/>
A "state" object is passed as the 1st argument to the script, to access it and see what's inside it, try this:<br/>
</br>
<pre>
args = { ... }
state = args[1]
log_console( 'state=%s', repr( state ))
</pre>
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
