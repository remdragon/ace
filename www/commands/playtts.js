import UINode from './UINode.js'
//import sounds_options from '/util/sounds_options.js'

export default class PlayTTS extends UINode {
	static icon = '/media/streamline/megaphone-tts.png'
	static context_menu_name = 'Play Text to Speech'
	static command = 'playtts'
	
	help = `Play text to speech to the caller<br/>
<br/>
Does not collect digits, does not proceed with route instructions until audio is finished playing<br/>
<br/>`
	
	get label()
	{
		if( this.name )
			return `Say ${this.name}`
		else
			return 'Say Text'
	}
	
	voice = 'Joanna'
	text = ''
	name = ''
	
	fields = [{
		key: 'name',
		label: 'Name: ',
		type: 'string',
	},{
		key: 'voice',
		label: 'Speech Voice',
		input: 'select2', // 'select2_or_text'
		async options( self ) { return [
			{ label: 'en-US Joanna', value: 'Joanna' },
			{ label: 'en-US Ivy', value: 'Ivy' },
			{ label: 'en-US Kendra' , value: 'Kendra' },
			{ label: 'en-US Kimberly', value: 'Kimberly' },
			{ label: 'en-US Salli', value: 'Salli' },
			{ label: 'en-US Joey', value: 'Joey' },
			{ label: 'en-US Justin', value: 'Justin' },
			{ label: 'en-US Kevin', value: 'Kevin' },
			{ label: 'en-US Matthew', value: 'Matthew' }
		]}
	},{
		key: 'text',
		label: 'Text to Say',
		input: 'textarea',
		rows: 10,
		cols: 40
	}]
}
