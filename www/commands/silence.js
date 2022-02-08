import UINode from './UINode.js'

export default class Silence extends UINode {
	static icon = '/media/streamline/volume-remove.png'
	static context_menu_name = 'Silence'
	static command = 'silence'
	
	help = `Plays silence for the specified number of seconds`
	
	get label()
	{
		if( this.seconds < 0 )
			return 'Silence forever'
		else
			return 'Silence ' + ( this.seconds || 0 ) + ' second(s)'
	}
	
	seconds = 1//: number
	divisor = 0//: int
	
	fields = [{
		key: 'seconds',
		type: 'float',
		label: 'Seconds:',
		tooltip: 'Number of seconds of silence. -1 = infinite',
	},{
		key: 'divisor',
		type: 'int',
		label: 'Comfort Noise:',
		tooltip: '0 for complete silence, >0 for comfort noise (try a value of 1400)',
	}]
}
