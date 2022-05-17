import UINode from './UINode.js'

export default class PlayTTS extends UINode {
	static icon = '/media/streamline/megaphone-tts.png'
	static context_menu_name = 'Play Text to Speech'
	static command = 'playtts'
	
	help = `Play text to speech to the caller<br/>
<br/>
Does not proceed with route instructions until audio is finished playing<br/>
<br/>
For a list of all voices available, <a href='https://docs.aws.amazon.com/polly/latest/dg/voicelist.html'>see AWS documentation</a>`
	
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
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'voice',
		label: 'Speech Voice',
		input: 'select2',
		or_text: true,
		async options( self ) { return [
			{ label: '(System Default)', value: '' },
			{ label: 'en-AU Nicole (English Australian Female Adult)', value: 'Nicole' },
			{ label: 'en-AU Russell (English Australian Male Adult)', value: 'Russell' },
			{ label: 'es-ES Conchita (Spanish European Female Adult)', value: 'Conchita' },
			{ label: 'es-ES Enrique (Spanish European Male Adult)', value: 'Enrique' },
			{ label: 'es-MX Mia (Spanish Mexican Female Adult)', value: 'Mia' },
			{ label: 'es-US Lupe (Spanish American Female Adult)', value: 'Lupe' },
			{ label: 'es-US Miguel (Spanish American Male Adult)', value: 'Miguel' },
			{ label: 'es-US Penelope (Spanish American Female Adult)', value: 'Penelope' },
			{ label: 'en-GB Amy (English British Female Adult)', value: 'Amy' },
			{ label: 'en-GB Brian (English British Male Adult)', value: 'Brian' },
			{ label: 'en-GB Emma (English British Female Adult)', value: 'Emma' },
			{ label: 'en-US Ivy (English American Female Child)', value: 'Ivy' },
			{ label: 'en-US Joanna (English American Female Adult)', value: 'Joanna' },
			{ label: 'en-US Joey (English American Male Adult)', value: 'Joey' },
			{ label: 'en-US Justin (English American Male Child)', value: 'Justin' },
			{ label: 'en-US Kendra (English American Female Adult)' , value: 'Kendra' },
			{ label: 'en-US Kimberly (English American Female Adult)', value: 'Kimberly' },
			{ label: 'en-US Matthew (English American Male Adult)', value: 'Matthew' },
			{ label: 'en-US Salli (English American Female Adult)', value: 'Salli' },
		]}
	},{
		key: 'text',
		label: 'Text to Say',
		input: 'textarea',
		rows: 10,
		cols: 40
	}]
}
// The number you called from is <say-as interpret-as="telephone" format="1">${caller_id_number}</say-as>.
