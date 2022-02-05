import UINode from './UINode.js'
import NamedSubtree from './named_subtree.js'
import { holidays } from '/holidays.js'

export default class TOD extends UINode {
	static icon = '/media/streamline/road-sign-look-both-ways-1.png'
	static context_menu_name = 'TimeOfDay'
	static command = 'tod'
	hit_help = 'These instructions will execute if the time-of-day conditions match<br/>'
	miss_help = "These instructions will execute if the time-of-day conditions don't match<br/>"
	
	help =
		'Tests time-of-day conditions and executes different commands depending on the result'
	get label()
	{
		return 'TOD ' + ( this.name || '(Unnamed)' )
	}
	
	name//: string
	times//: string
	hit//: NamedSubtree
	miss//: NamedSubtree
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'For documentation purposes only',
	},{
		key: 'times',
		input: 'textarea',
		cols: 40,
		rows: 10,
		tooltip: `Enter specifics for DOW/TOD that should be considered.
One range per line, for example:

Mon,Wed-Fri 08:00-17:00
Sat 08:00-12:00
1/5/2022 08:00-1/7 13:00
`,
		// TODO FIXME: move examples to an examples key (requires adding support for examples to textarea impl)
	}]
	
	constructor( parent )
	{
		super( parent )
		let new_fields = []
		for( let field of this.fields )
			new_fields.push( field )
		for( let holiday_id in holidays )
		{
			new_fields.push({
				key: holiday_id,
				label: holidays[holiday_id],
				input: 'select',
				async options( self ) { return [
					{ label: 'N/A', value: '' },
					{ label: 'Required', value: 'required' },
					{ label: 'Excluded', value: 'excluded' },
				]}
			})
		}
		this.fields = new_fields
	}
	
	createElement({
		isSubtree = false,
		data = { hit: [], miss: [] },
		NODE_TYPES
	}) {
		super.createElement({ isSubtree, data, NODE_TYPES })
		
		this.hit = new NamedSubtree( this, 'hit', this.hit_help )
		this.hit.createElement({
			isSubtree: true,
			data: data.hit,
			NODE_TYPES
		})
		
		this.miss = new NamedSubtree( this, 'miss', this.miss_help )
		this.miss.createElement({
			isSubtree: true,
			data: data.miss,
			NODE_TYPES
		})
	}
	
	getJson()
	{
		let sup = super.getJson()
		
		return {
			...sup,
			hit: this.hit.getJson(),
			miss: this.miss.getJson()
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		this.hit.walkChildren( callback )
		this.miss.walkChildren( callback )
	}
}
