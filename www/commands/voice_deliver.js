import UINode from './UINode.js'

export default class VoiceDeliver extends UINode {
	static icon = '/media/streamline/phone-actions-ring.png'
	static context_menu_name = 'Voice Deliver'
	static command = 'voice_deliver'
	
	help = `Place an outbound call to deliver a voicemail message.<br/>
<br/>
Does not proceed with delivery instructions until call attempt has completed
`
	
	get label()
	{
		if( this.name )
			return `${this.name}`
		else
			return `Voice Deliver ${this.number}`
	}
	
	name = ''
	number = ''//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'number',
		label: 'Number:',
		tooltip: 'The number to call, you may need to put a 9 in front of it, depending on your switch configuration',
	}]
}
