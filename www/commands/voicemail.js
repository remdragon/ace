import UINode from './UINode.js'

export default class Voicemail extends UINode {
	static icon = '/media/streamline/folder-code.png'
	static context_menu_name = 'Voicemail'
	static command = 'voicemail'
	
	help = `Choose another route to execute from here.<br/>
<br/>
When that route finishes, execution will resume here in this route<br/>`
	
	get label()
	{
		return 'Voicemail ' + this.box
	}
	
	box = ''//: string
	
	fields = [
		{
			key: 'box',
			type: 'int',
			input: 'select',
			label: 'Voicemail: ',
			async options( self ) {
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
		}
	]
}
