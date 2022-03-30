import UINode from './UINode.js'

export default class RxFax extends UINode {
	static icon = '/media/streamline/recording-tape-2@20x20.png'
	static context_menu_name = 'Rcv Fax'
	static command = 'rxfax'
	
	help = `Receive a fax and email it to a recipient.<br/>
<br/>
If no email is specified, call will hangup instead of receiving a fax.<br/>
<br/>
Subject/Body support placeholders like \${ani} \${did}`
	
	get label()
	{
		return 'RcvFax ' + ( this.name || this.mailto || '' )
	}
	
	name = '' // string
	mailto = '' // string
	subject = '' // string
	body = '' // string
	
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
		placeholder: '(Using default email subject)',
		tooltip: 'If left blank, the system default is used',
	},{
		key: 'body',
		label: 'Body:',
		input: 'textarea',
		cols: 60,
		rows: 10,
		placeholder: '(using default email body)',
		tooltip: 'If left blank, the system default is used',
	}]
}
