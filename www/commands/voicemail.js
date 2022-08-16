import UINode from './UINode.js'

var greeting_options = [
	{ 'label': '(Use Default Behavior)', 'value': '' },
	{ 'label': '(Play Active Greeting)', 'value': 'A' },
	{ 'label': 'Greeting 1', 'value': '1' },
	{ 'label': 'Greeting 2', 'value': '2' },
	{ 'label': 'Greeting 3', 'value': '3' },
	{ 'label': 'Greeting 4', 'value': '4' },
	{ 'label': 'Greeting 5', 'value': '5' },
	{ 'label': 'Greeting 6', 'value': '6' },
	{ 'label': 'Greeting 7', 'value': '7' },
	{ 'label': 'Greeting 8', 'value': '8' },
	{ 'label': 'Greeting 9', 'value': '9' },
	{ 'label': '(Play NO Greeting At All)', 'value': 'X' },
]

export default class Voicemail extends UINode {
	static icon = '/media/streamline/folder-code.png'
	static context_menu_name = 'Voicemail'
	static command = 'voicemail'
	
	help = `Invoke the voicemail subsystem<br/>
<br/>
If "box" is blank or 0, invokes the voicemail checkin<br/>
<br/>
You can use channel variables in the greeting override, but if that doesn't evaluate to a number from 1-9, the current greeting will be played instead.<br/>
<br/>
When that finishes, execution will resume here
`
	
	get label()
	{
		return 'Voicemail ' + ( this.name || this.box )
	}
	
	name = ''
	box = ''//: string
	greeting_override//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'box',
		type: 'string',
		input: 'select2',
		or_text: true,
		label: 'Voicemail:',
		async options( self )
		{
			let params = { headers: { 'Accept': 'application/json' }}
			let json = await fetch( '/voicemails?limit=1000', params )
				.then( rsp => rsp.json() )
			//console.log( JSON.stringify( json ) )
			let options = [{ label: '(Checkin)', value: '0' }]
			for ( let row of json.rows )
			{
				options.push({ label: `${row.box} ${row.name || "(Unnamed)"}`, value: row.box })
			}
			return options
		}
	},{
		key: 'greeting_override',
		type: 'string',
		input: 'select',
		async options( self )
		{
			return greeting_options
		},
		label: 'Play the following greeting instead of allowing the default greeting behavior:',
	}]
}
