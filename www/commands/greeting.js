import UINode from './UINode.js'

var greeting_options = [
	{ 'label': '(Active)', 'value': '' },
	{ 'label': 'Greeting 1', 'value': '1' },
	{ 'label': 'Greeting 2', 'value': '2' },
	{ 'label': 'Greeting 3', 'value': '3' },
	{ 'label': 'Greeting 4', 'value': '4' },
	{ 'label': 'Greeting 5', 'value': '5' },
	{ 'label': 'Greeting 6', 'value': '6' },
	{ 'label': 'Greeting 7', 'value': '7' },
	{ 'label': 'Greeting 8', 'value': '8' },
	{ 'label': 'Greeting 9', 'value': '9' },
]

export default class Greeting extends UINode {
	static icon = '/media/streamline/megaphone-greeting.png'
	static context_menu_name = 'Greeting'
	static command = 'greeting'
	
	help = `Plays a selected greeting from this voicemail box or another`
	
	get label()
	{
		return 'Greeting ' + ( this.name ?? greeting_options[this.greeting]?.value ?? '(Unset)' )
	}
	
	name//: string
	box//: integer
	greeting//: integer
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'box',
		type: 'string',
		input: 'select2',
		or_text: true,
		label: 'Box:',
		async options( self )
		{
			let params = { headers: { 'Accept': 'application/json' }}
			let json = await fetch( '/voicemails?limit=1000', params )
				.then( rsp => rsp.json() )
			let options = [{ label: '(Current Box)', value: '0' }]
			for ( let row of json.rows )
			{
				options.push({ label: `${row.box} ${row.name || "(Unnamed)"}`, value: row.box })
			}
			return options
		}
	},{
		key: 'greeting',
		type: 'int',
		input: 'select',
		label: 'Greeting:',
		async options( self )
		{
			return greeting_options
		},
		tooltip: 'greeting # to play (1-9) - can be changed from the voicemail admin menu',
	}]
}
