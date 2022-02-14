import UINode from './UINode.js'

export default class Wait extends UINode {
	static icon = '/media/wait.png'
	static context_menu_name = 'Wait'
	static command = 'wait'
	
	help = `Pauses execution for the specified number of mintes &amp; seconds`
	
	get label()
	{
		let s = 'Wait'
		let total_seconds = ( this.minutes || 0 ) * 60 + ( this.seconds || 0 )
		let seconds = total_seconds % 60
		let minutes = parseInt( ( total_seconds - seconds ) / 60 )
		if( minutes )
			s += ` ${minutes}m`
		if( seconds || !minutes )
			s += ` ${seconds}s`
		return s
	}
	
	minutes//: number
	seconds//: number
	
	fields = [{
		key: 'minutes',
		type: 'float',
		label: 'Minutes:',
	},{
		key: 'seconds',
		type: 'float',
		label: 'Seconds:',
	}]
}
