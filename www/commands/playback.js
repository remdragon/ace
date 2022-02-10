import UINode from './UINode.js'
import sounds_options from '/util/sounds_options.js'

export default class Playback extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play Sound'
	static command = 'playback'
	
	help = `Play an audio file to the caller<br/>
<br/>
Does not proceed with route instructions until audio is finished playing
`
	
	get label()
	{
		if( this.name )
			return `Play ${this.name}`
		else
			return 'Play Sound'
	}
	
	sound = ''//: string
	name = ''
	
	fields = [{
		key: 'name',
		label: 'Name: ',
		type: 'string',
	},{
		key: 'sound',
		label: 'Sound:',
		type: 'string',
		input: 'select2',
		or_text: true,
		async options( self ) {
			return await sounds_options()
		}
	}]
}
