import UINode from './UINode.js'

export default class Log extends UINode {
	static icon = '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'Log'
	static command = 'log'
	
	help = 'Log diagnostic information to FreeSWITCH console/log file'
	get label()
	{
		return `Log ${this.name || this.text || ''}`
	}
	
	name//: string
	level//: string
	text//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'level',
		input: 'select',
		label: 'Level:',
		async options( self ) { return [
			{ label: 'Console', value: 'CONSOLE' },
			{ label: 'Alert', value: 'ALERT' },
			{ label: 'Critical', value: 'CRIT' },
			{ label: 'Error', value: 'ERR' },
			{ label: 'Warning', value: 'WARNING' },
			{ label: 'Notice', value: 'NOTICE' },
			{ label: 'Info', value: 'INFO' },
			{ label: 'Debug', value: 'DEBUG' },
		]}
	},{
		key: 'text',
		label: 'Text:',
	}]
}
