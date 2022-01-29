import UINode from './UINode.js'

export default class Playback extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play Sound'
	static command = 'playback'
	
	help = `Play an audio file to the caller<br/>
<br/>
Does not collect digits, does not proceed with route instructions until audio is finished playing<br/>
<br/>`
	
	get label()
	{
		if( this.name )
			return `Play ${this.name}`
		else
			return 'Play Sound'
	}
	
	sound = ''//: string
	name = ''
	
	fields = [
		{
			key: 'sound',
			type: 'string',
			input: 'select',
			async options() {
				let params = { headers: { 'Accept': 'application/json' }}
				let json = await fetch( '/sounds', params )
					.then( rsp => rsp.json() )
				//console.log( JSON.stringify( json ) )
				let options = []
				for ( let row of json.rows )
				{
					options.push({ label: row.sound, value: row.sound })
				}
				return options
			}
		},
		{
			key: 'name',
			type: 'string',
			label: 'Name: ',
		}
	]
}
