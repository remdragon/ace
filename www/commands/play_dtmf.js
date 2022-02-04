import UINode from './UINode.js'
import sounds_options from '/util/sounds_options.js'

export default class PlayDTMF extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play DTMF'
	static command = 'playdtmf'
	
	help = `Play DTMF tone(s) to the caller<br/>
<br/>
Useful for auto-accepting calls from Google for example<br/>
<br/>`
	
	get label()
	{
		return `Play DTMF ${this.name || ""}`
	}
	
	dtmf = ''//: string
	name = ''
	
	fields = [
		{
			key: 'dtmf',
			type: 'string',
			label: 'DTMF: ',
			tooltip: 'Example: 123*#',
		},
		{
			key: 'name',
			type: 'string',
			label: 'Name: ',
		}
	]
}
