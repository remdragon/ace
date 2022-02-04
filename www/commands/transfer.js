import UINode from './UINode.js'

export default class Transfer extends UINode {
	static icon = '/media/streamline/phone-actions-receive.png'
	static context_menu_name = 'Transfer'
	static command = 'transfer'
	
	help = `Transfers the call out of ACE to the FreeSWITCH dialplan.<br/>
<br/>
Route exection stops here<br/>`
	get label()
	{
		return 'Transfer ' + ( this.dest || '' )
	}
	
	leg//: string
	dest//: string
	dialplan = 'default' //: dialplan
	context = 'xml'//: context
	
	fields = [
		{
			key: 'leg',
			input: 'select',
			label: 'Leg: ',
			async options( self ) {
				return [
					{ label: 'A Leg (default)', value: '' },
					{ label: 'B Leg', value: '-bleg' },
					{ label: 'Both Legs', value: '-both' },
				]
			},
			tooltip: 'In the confines of the ACE system, the "A Leg" option may be the only relevant choice',
		},{
			key: 'dest',
			label: 'Destination:',
			tooltip: 'Enter the destination to transfer the call to',
		},{
			key: 'dialplan',
			label: 'Dialplan:',
			input: 'select',
			async options( self ) {
				return [
					{ label: '(choose one)', value: '' },
					{ label: 'default', value: 'default' },
					{ label: 'public', value: 'public' },
				]
			},
			tooltip: 'default is for internal and outbound dialing, public would be to simulate an inbound call'
		},{
			key: 'context',
			label: 'Context:',
			tooltip: 'This is an advanced feature and will probably always be left as xml',
		}
	]
}
