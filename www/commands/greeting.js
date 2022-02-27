import UINode from './UINode.js'

export default class Greeting extends UINode {
	static icon = '/media/streamline/megaphone-greeting.png'
	static context_menu_name = 'Greeting'
	static command = 'greeting'
	
	help = `Plays a selected greeting from this voicemail box`
	
	get label()
	{
		return 'Greeting ' + ( this.name ?? this.greeting ?? '(Unset)' )
	}
	
	name//: string
	greeting//: integer
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'greeting',
		type: 'int',
		label: 'Greeting:',
		tooltip: 'greeting # to play (1-9) - can be changed from the voicemail admin menu',
	}]
}
