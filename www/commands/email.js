import UINode from './UINode.js'

export default class Email extends UINode {
	static icon = '/media/streamline/mail-send-envelope@22.png'
	static context_menu_name = 'Email'
	static command = 'email'
	
	help = `Sends voicemail message as an email<br/>
<br/>
This command only works for voicemail notify, it does nothing if invoked in a route<br/>
<br/>
Subject/Body support placeholders like \${box} \${ani} \${did} \${checkin}`
	
	get label()
	{
		return 'Email ' + ( this.name || this.mailto || '' )
	}
	
	name = '' // string
	mailto = '' // string
	subject = '' // string
	body = '' // string
	format = 'mp3' // string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'mailto',
		label: 'Email To:',
		placeholder: '(recipient email address)',
		tooltip: 'Enter the recipient email address here, multiple recipients not supported',
	},{
		key: 'subject',
		label: 'Subject:',
		size: 60,
		placeholder: '(Using default email subject)',
		tooltip: 'If left blank, the box default is used',
	},{
		key: 'body',
		label: 'Body:',
		input: 'textarea',
		cols: 60,
		rows: 10,
		placeholder: '(using default email body)',
		tooltip: 'If left blank, the box default is used',
	},{
		key: 'format',
		label: 'Attached Greeting File Format:',
		input: 'select',
		async options( self )
		{
			return [
				{ label: '(Use Voicemail box default)', value: '' },
				{ label: 'No attachment', value: '-' },
				{ label: 'MP3', value: 'mp3' },
				{ label: 'WAV', value: 'wav' },
			]
		},
	}]
}
