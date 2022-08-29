import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'

const GREETING_LABEL = 'Greeting'
const DELIVERY_LABEL = 'Delivery'

export default class RootVoiceMail extends UINode {
	static icon = '/media/streamline/kindle.png'
	static context_menu_name = 'N/A'
	static command = ''
	
	help = `This is the configuration node for your Voicemail Box<br/>
<br/>
Configuration settings here or right-click on the delivery node to configuration automation on delivery.<br/>
<br/>
If user doesn't press any digits, timeout plays a beep and records a message<br/>
<br/>
Email Subject/Body and SMS Message support placeholders like \${box} \${ani} \${did} \${checkin}`
	
	greeting_subtree_help = 'Add nodes here to define what the caller hears when entering the voicemail box'
	digit_subtree_help = 'If this digit is pressed during the greeting, do this instead'
	delivery_subtree_help = 'Use this to send emails and SMS msgs when a message has been created.'
	
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
	default_email_subject = ''
	default_email_body = ''
	default_sms_message = ''
	
	greetingBranch = null//: greeting branch...
	branches = null
	delivery = null
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'pin',
		type: 'string',
		pattern: '\\d+',
		input: 'password',
		label: 'PIN:',
		tooltip: 'numeric password to admin the box',
	},{
		key: 'greeting',
		type: 'int',
		label: 'Greeting:',
		size: 2,
		tooltip: 'greeting # to play (1-9) - can be changed from the voicemail admin menu',
	},{
		key: 'allow_guest_urgent',
		type: 'boolean',
		input: 'checkbox',
		label: 'Allow guests to make URGENT',
		tooltip: 'enables extra prompt after guest records message giving them option to make message urgent',
	},{
		key: 'max_greeting_seconds',
		type: 'int',
		label: 'Max greeting seconds:',
		size: 4,
	},{
		key: 'max_message_seconds',
		type: 'int',
		label: 'Max message seconds:',
		size: 4,
	},{
		key: 'default_email_subject',
		size: 60,
		label: 'Default Email Subject:',
	},{
		key: 'default_email_body',
		label: 'Default Email Body:',
		input: 'textarea',
		cols: 60,
		rows: 10,
	},{
		key: 'format',
		label: 'Default Attached Greeting File Format:',
		input: 'select',
		async options( self )
		{
			return [
				{ label: 'No attachment', value: '-' },
				{ label: 'MP3', value: 'mp3' },
				{ label: 'WAV', value: 'wav' },
			]
		},
	},{
		key: 'default_sms_message',
		size: 40,
		label: 'Default SMS Message:',
	}]
	
	constructor( tree, box, data )
	{
		super( null )
		this.tree = tree
		
		this.box = box
		for( let field of this.fields )
			this[field.key] = data[field.key]
		
		this.treenode = tree.createNode(
			this.label,
			true,
			RootVoiceMail.icon,
			null,
			null,
			'contextVoiceMailRoot',
		)
		
		this.treenode.uinode = this
		
		this.makeFixedBranch( 'greetingBranch', GREETING_LABEL,
			'context_VoicemailGreeting',
			this.greeting_subtree_help,
			data,
			'context_VoicemailGreetingChildren',
		)
		
		this.branches = {}
		if( data.branches )
		{
			let all_digits = []
			for( const digit in data.branches )
				all_digits.push( digit )
			all_digits.sort()
			for( const digit of all_digits )
				this.makeDigitBranch( digit, data )
		}
		
		this.makeFixedBranch( 'delivery', DELIVERY_LABEL,
			'contextRootVoicemailDelivery',
			this.delivery_subtree_help,
			data ?? {},
		)
		this.delivery.contextOptionalSubtree = function()
		{
			return 'contextOptionalSubtreeVoicemailDelivery'
		}
	}
	
	makeDigitBranch( digit, data )
	{
		let uinode = new NamedSubtree(
			this, digit, this.digit_subtree_help,
		)
		uinode.contextOptionalSubtree = function()
		{
			return 'contextOptionalSubtreeVoicemail'
		}
		this.branches[digit] = uinode
		uinode.createElement({
			isSubtree: true,
			data: ( data.branches ?? {} )[digit] ?? {},
			context: 'contextRootVoicemailDigitSubtree',
		})
		return uinode
	}
	
	reorder()
	{
		const domNodes = this.treenode.childNodes.sort(( a, b ) =>
		{
			// greeting is always at the top
			if( a.text === GREETING_LABEL )
				return -1
			if( b.text === GREETING_LABEL )
				return 1
			
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
		
		const ulNode = this.treenode.childNodes[0].elementLi.parentNode
		
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
		
		let greetingBranch = null
		if( this.greetingBranch )
			greetingBranch = this.greetingBranch.getJson()
		
		const branchesData = {}
		for( const digit in this.branches )
		{
			let branch = this.branches[digit]
			branchesData[digit] = branch ? branch.getJson() : {}
		}
		
		let delivery = null
		if( this.delivery )
			delivery = this.delivery.getJson()
		
		return {
			...sup,
			type: 'root_voicemail',
			name: this.name,
			greetingBranch: greetingBranch,
			branches: branchesData,
			delivery: delivery,
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		for( let digit in this.branches )
			walkChild( this.branches[digit], callback )
		walkChild( this.delivery, callback )
	}
	
	remove( uinode/*: UINode*/ )
	{
		super.remove( uinode )
		
		for( let digit in this.branches )
		{
			let branch = this.branches[digit]
			if( branch.treenode.id === uinode.treenode.id )
				delete this.branches[digit]
		}
	}
}
