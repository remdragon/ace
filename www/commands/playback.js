import UINode from './UINode.js'
import sounds_options from '/util/sounds_options.js'

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
			input: 'select2',
			async options() {
				return await sounds_options()
			}
		},
		{
			key: 'name',
			type: 'string',
			label: 'Name: ',
		}
	]
}
