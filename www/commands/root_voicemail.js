import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

const DELIVERY_LABEL = 'delivery'

export default class RootVoiceMail extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'N/A'
	static command = ''
	
	help = `This is the configuration node for your Voicemail Box<br/>
<br/>
Configuration settings here or right-click on the delivery node to configuration automation on delivery.
`
	digit_subtree_help = 'If this digit is pressed during the greeting, do this instead'
	
	get label()
	{
		return `VoiceMail ${this.box} ${this.name || '(Unnamed)'}`
	}
	
	box//: integer
	name//: string
	pin//: integer
	greeting//: integer
	allow_guest_urgent//: boolean
	max_greeting_seconds//: integer
	max_message_seconds//: integer
	
	branches = {} // NamedSubtree
	
	fields = [
		{
			key: 'name',
			type: 'string',
			label: 'Name: ',
		},{
			key: 'pin',
			type: 'int',
			input: 'password',
			label: 'PIN:',
			tooltip: 'numeric password to admin the box',
		},{
			key: 'greeting',
			type: 'int',
			label: 'Greeting: ',
			tooltip: 'greeting # to play (1-9) - can be changed from the voicemail admin menu',
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
		this.tree = tree
		
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
			'contextVoiceMailRoot',
		)
		
		this.element.node = this
		
		if( data.branches )
		{
			this.branches = {}
			let all_digits = []
			for( const digit in data.branches )
				all_digits.push( digit )
			all_digits.sort()
			for( const digit of all_digits )
			{
				this.branches[digit] = new NamedSubtree(
					this, digit, this.digit_subtree_help,
				)
				this.branches[digit].createElement({
					isSubtree: true,
					data: data.branches[digit] ?? {},
					NODE_TYPES,
					context: 'contextRootVoicemailDigitSubtree',
				})
			}
		}
		
		this.delivery = new NamedSubtree( this, DELIVERY_LABEL,
			'Add commands to this node to automate delivery of messages taken in this box'
		)
		this.delivery.createElement({
			isSubtree: true,
			data: data.delivery ?? {},
			NODE_TYPES,
			context: 'contextRootVoicemailDelivery',
		})
	}
	
	reorder()
	{
		const domNodes = this.element.childNodes.sort(( a, b ) =>
		{
			// delivery is always at the bottom
			if( a.text === DELIVERY_LABEL )
				return 1
			if( b.text === DELIVERY_LABEL )
				return -1
			
			// what's left is the digit branches:
			const aValue = parseInt( a.text )
			const bValue = parseInt( b.text )
			
			return aValue - bValue
		})
		
		const ulNode = this.element.childNodes[0].elementLi.parentNode
		
		domNodes.forEach( el =>
		{
			ulNode.appendChild( el.elementLi )
		})
		
		// TODO: fix dotted lines after reordering
	}
	
	getJson()
	{
		const sup = super.getJson()
		delete sup['type']
		
		const branchesData = {}
		for( const digit in this.branches )
		{
			let branch = this.branches[digit]
			branchesData[digit] = branch ? branch.getJson() : {}
		}
		
		return {
			...sup,
			type: 'root_voicemail',
			name: this.name,
			delivery: this.delivery.getJson(),
			branches: branchesData,
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		for( let digit in this.branches )
			walkChild( this.branches[digit], callback )
		walkChild( this.delivery, callback )
	}
	
	remove( node/*: UINode*/ )
	{
		super.remove( node )
		
		for( let digit in this.branches )
		{
			let branch = this.branches[digit]
			if( branch.element.id === node.element.id )
			{
				console.log( `deleting ${digit}` )
				delete this.branches[digit]
			}
		}
	}
}
