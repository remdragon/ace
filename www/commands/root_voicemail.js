import UINode from './UINode.js'
import Subtree from './subtree.js'

export default class RootVoiceMail extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'N/A'
	static command = ''
	
	help = `This is the configuration node for your Voicemail Box<br/>
<br/>
Configuration settings here or right-click on the delivery node to configuration automation on delivery.
`
	
	get label()
	{
		return `VoiceMail ${this.box} ${this.name || '(Unnamed)'}`
	}
	
	box//: integer
	name//: string
	greeting//: integer
	allow_guest_urgent//: boolean
	max_greeting_seconds//: integer
	max_message_seconds//: integer
	
	fields = [
		{
			key: 'name',
			type: 'string',
			label: 'Name: ',
		},{
			key: 'greeting',
			type: 'int',
			label: 'Greeting: ',
		},{
			key: 'allow_guest_urgent',
			type: 'boolean',
			input: 'checkbox',
			label: 'Allow guests to make URGENT',
		},{
			key: 'max_greeting_seconds',
			type: 'int',
			label: 'Max greeting seconds: ',
		},{
			key: 'max_message_seconds',
			type: 'int',
			label: 'Max message seconds: ',
		}
	]
	
	constructor( tree, box, data, NODE_TYPES )
	{
		super( null )
		
		this.box = box
		for( let field of this.fields )
		{
			this[field.key] = data[field.key]
		}
		
		this.element = tree.createNode(
			this.label,
			true,
			RootVoiceMail.icon,
			null,
			null,
			'contextVoiceMailRoot'
		)
		
		this.element.node = this
		
		this.delivery = new Subtree( this, 'delivery',
			'Add commands to this node to automate delivery of messages taken in this box'
		)
		this.delivery.createElement({
			isSubtree: true,
			data: { nodes: data.delivery },
			NODE_TYPES,
		})
	}
	
	getJson()
	{
		const sup = super.getJson()
		delete sup['type']
		
		return {
			...sup,
			type: 'root_voicemail',
			name: this.name,
			delivery: this.delivery.getJson().nodes
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		for( let node of this.children )
		{
			node.walkChildren( callback )
		}
	}
}
