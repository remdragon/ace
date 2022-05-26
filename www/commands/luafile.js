import UINode from './UINode.js'

export default class LuaFile extends UINode {
	static icon = '/media/streamline/robot-1.png'
	static context_menu_name = 'LuaFile'
	static command = 'luafile'
	
	help = `Runs a lua file from the scripts folder.<br/>
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
		return 'LuaFile ' + ( this.file ?? this.name )
	}
	
	name = ''
	file = ''
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'file',
		label: 'File Name:',
		tooltip: 'The name of the lua file to run, the question is: do we need to include the .lua extension or not?',
	}]
}
