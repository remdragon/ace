import UINode from './UINode.js'

export default class Voicemail extends UINode {
	static icon = '/media/streamline/folder-code.png'
	static context_menu_name = 'Voicemail'
	static command = 'voicemail'
	
	help = `Invoke the voicemail subsystem<br/>
<br/>
If "box" is blank or 0, invokes the voicemail checkin<br/>
<br/>
You can use channel variables in the greeting override, but if that doesn't evaluate to a number from 0-9, the current greeting will be played instead.<br/>
<br/>
When that finishes, execution will resume here
`
	
	get label()
	{
		return 'Voicemail ' + this.box
	}
	
	box = ''//: string
	greeting_override//: string
	
	fields = [{
		key: 'box',
		type: 'string',
		input: 'select2',
		or_text: true,
		label: 'Voicemail: ',
		async options( self )
		{
			let params = { headers: { 'Accept': 'application/json' }}
			let json = await fetch( '/voicemails', params )
				.then( rsp => rsp.json() )
			//console.log( JSON.stringify( json ) )
			let options = [ { label: '(Choose One)', value: '' } ]
			for ( let row of json.rows )
			{
				options.push({ label: `${row.box} ${row.name || "(Unnamed)"}`, value: row.box })
			}
			return options
		}
	},{
		key: 'greeting_override',
		type: 'string',
		input: 'text',
		label: 'Play a different greeting other than the current (0 to play no greeting)',
	}]
}
