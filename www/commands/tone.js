import UINode from './UINode.js'

export default class Tone extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play Tone'
	static command = 'tone'
	
	help = `Play a tone to the caller<br/>
<br/>
Does not collect digits, does not proceed with route instructions until audio is finished playing<br/>
<br/>
See <a href='https://freeswitch.org/confluence/display/FREESWITCH/Tone_stream'>FreeSWITCH docs about the tone_stream app</a>
`
	
	get label()
	{
		if( this.name )
			return `Play ${this.name}`
		else
			return 'Play Tone'
	}
	
	name = ''
	tone = '%(500,500,480,620)'//: string
	loops = 1
	
	fields = [{
		key: 'name',
		label: 'Name: ',
		type: 'string',
	},{
		key: 'tone',
		label: 'Tone:',
		input: 'select',
		or_text: true,
		async options( self ) {
			return [
				{ label: 'UK Ring', value: '%(400,200,400,450);%(400,2200,400,450)' },
				{ label: 'US Ring', value: '%(2000,4000,440,480)' },
				{ label: 'US Busy', value: '%(500,500,480,620)' },
				{ label: 'US Reorder', value: '%(300,200,480,620)' },
			]
		},
	},{
		key: 'loops',
		type: 'int',
		label: 'Loops',
		tooltip: 'How many times should it play the tone. To loop forever, use the value -1'
	}]
}
