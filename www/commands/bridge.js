import UINode from './UINode.js'

export default class Bridge extends UINode {
	static icon = '/media/streamline/phone-actions-receive.png'
	static context_menu_name = 'Bridge'
	static command = 'bridge'
	
	help = `Executes the FreeSWITCH bridge command<br/>
<br/>
This is an advanced feature that uses the FreeSWITCH's <a href="https://freeswitch.org/confluence/display/FREESWITCH/mod_dptools%3A+bridge">"bridge" dialplan application</a><br/>`
	get label()
	{
		if( this.name )
			return 'Bridge ' + this.name
		else
			return 'Bridge ' + ( this.dial_string || '' )
	}
	
	name//: string
	dial_string//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'dial_string',
		size: 50,
		label: 'Dial String:',
		tooltip: 'See the link above for FreeSWITCH documentation about this command',
	}]
}
