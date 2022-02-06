import UINode from './UINode.js'

export default class Wait extends UINode {
	static icon = '/media/wait.png'
	static context_menu_name = 'Wait'
	static command = 'wait'
	
	help = `Pauses execution for the specified number of seconds`
	
	get label()
	{
		return 'Wait ' + ( this.seconds || 0 ) + ' second(s)'
	}
	
	seconds//: number
	
	fields = [{
		key: 'seconds',
		type: 'float',
		label: 'Seconds:',
	}]
}
