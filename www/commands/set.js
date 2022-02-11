import UINode from './UINode.js'

export default class Set extends UINode {
	static icon = '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'Set Variable'
	static command = 'set'
	
	help = 'Saves information in a channel variable'
	
	get label()
	{
		if( this.name )
			return `Set ${this.name}`
		else
			return `Set ${this.variable || '?'}=${this.value || ''}`
	}
	
	name//: string
	variable//: string
	value//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'Name the node on the tree, can be left blank',
	},{
		key: 'variable',
		label: 'Variable:',
		tooltip: 'The variable to receive the new value',
	},{
		key: 'value',
		label: 'Value:',
		tooltip: 'The value to set the variable to',
	}]
}
