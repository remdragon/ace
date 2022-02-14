import UINode from './UINode.js'

export default class Email extends UINode {
	static icon = '/media/streamline/mail-send-envelope@22.png'
	static context_menu_name = 'Email'
	static command = 'email'
	
	help = `Sends voicemail message as an email<br/>
<br/>
This command only works for voicemail notify, it does nothing if invoked in a route`
	
	get label()
	{
		return 'Email ' + ( this.name || '' )
	}
	
	name = '' // string
	mailto = '' // string
	subject = '' // string
	body = '' // string
	format = 'mp3' // string
	
	fields = [{
		key: 'name',
		label: 'Name:',
	},{
		key: 'mailto',
		label: 'Email To:',
	},{
		key: 'subject',
		label: 'Subject:',
	},{
		key: 'body',
		label: 'Body:',
		input: 'textarea',
		cols: 60,
		rows: 10,
	},{
		key: 'format',
		label: 'Attached Greeting File Format:',
		input: 'select',
		async options( self )
		{
			return [
				{ label: 'No attachment', value: '' },
				{ label: 'MP3', value: 'mp3' },
				{ label: 'WAV', value: 'wav' },
			]
		},
	}]
}
