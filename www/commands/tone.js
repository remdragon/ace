import UINode from './UINode.js'

const TONE_UK_RING = '%(400,200,400,450);%(400,2200,400,450)'
const TONE_US_RING = '%(2000,4000,440,480)'
const TONE_US_BUSY = '%(500,500,480,620)'
const TONE_US_REORDER = '%(300,200,480,620)'
const TONE_US_SIT_OOSVC = '%(274,0,913.8);%(274,0,1370.6);%(380,1000,1776.7)'

export default class Tone extends UINode {
	static icon = '/media/streamline/music-note-2@20.png'
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
	tone = TONE_US_BUSY//: string
	loops = 1
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'tone',
		label: 'Tone:',
		input: 'select',
		or_text: true,
		async options( self ) {
			return [
				{ label: 'UK Ring', value: TONE_UK_RING },
				{ label: 'US Ring', value: TONE_US_RING },
				{ label: 'US Busy', value: TONE_US_BUSY },
				{ label: 'US Reorder', value: TONE_US_REORDER },
				{ label: 'US SIT Tone (out of service)', value: TONE_US_SIT_OOSVC },
			]
		},
	},{
		key: 'loops',
		type: 'int',
		label: 'Loops',
		tooltip: 'How many times should it play the tone. To loop forever, use the value -1'
	}]
}
