import UINode from './UINode.js'

export default class Python extends UINode {
	static icon = '/media/streamline/robot-1.png'
	static context_menu_name = 'Python'
	static command = 'python'
	
	help = `Runs python code.<br/>
<br/>
If you wish to pass the uuid to the python script, put ${uuid} in the arguments field<br/>
<br/>
See <a href='https://freeswitch.org/confluence/display/FREESWITCH/mod_python'>the documentation</a> for more info.
`
	get label()
	{
		return 'Python ' + ( this.name ?? this.module )
	}
	
	name = ''
	module = ''
	args = ''
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'module',
		label: 'Module Name:',
	},{
		key: 'args',
		label: 'Arguments:',
		tooltip: 'Additional arguments to pass to the python module',
	}]
}
