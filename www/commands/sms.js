import UINode from './UINode.js'

export default class SMS extends UINode {
	static icon = '/media/streamline/mail-chat-bubble-typing-oval@22.png'
	static context_menu_name = 'SMS'
	static command = 'sms'
	
	help = `Sends sms notification about a voicemail message<br/>
<br/>
This command only works for voicemail notify, it does nothing if invoked in a route`
	
	get label()
	{
		return 'SMS ' + ( this.name || this.smsto || '' )
	}
	
	name = '' // string
	smsto = '' // string
	message = '' // string
	
	fields = [{
		key: 'name',
		label: 'Name:',
	},{
		key: 'smsto',
		label: 'SMS To:',
	},{
		key: 'message',
		label: 'Message:',
		size: 60,
	}]
}
