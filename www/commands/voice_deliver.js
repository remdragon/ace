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
	},{
		key: 'dialplan',
		label: 'Dial Plan:',
		tooltip: 'An advanced setting, leave blank for default of "xml"',
	},{
		key: 'context',
		label: 'Context:',
		tooltip: 'An advanced setting, leave blank for default of "default"',
	},{
		key: 'cid_name',
		label: 'Caller Name:',
		tooltip: 'leave blank for default',
	},{
		key: 'cid_num',
		label: 'Caller ID Number:',
		tooltip: 'leave blank for default',
	},{
		key: 'timeout',
		label: 'Call Timeout (seconds):',
		size: 4,
		tooltip: 'Time to wait for bridge to be answered before timing out (blank or 0 = wait forever)',
	},{
		key: 'trusted',
		type: 'boolean',
		input: 'checkbox',
		label: 'Trusted:',
		tooltip: "Don't require entering pin to login before being able to listen to message",
	}]
}
