import{ UINode, walkChild } from './UINode.js'
import NamedSubtree from './named_subtree.js'
import{ holidays } from '/holidays.js'

const HIT_LABEL = 'Hit'
const MISS_LABEL = 'Miss'

export default class TOD extends UINode {
	static icon = '/media/streamline/time-clock-circle.png'
	static context_menu_name = 'TimeOfDay'
	static command = 'tod'
	
	help =
		`Tests time-of-day conditions and executes different commands depending on the result<br/>
<br/>
Executes the "hit" node if the TOD matches otherwise the "miss" node`
	hit_help = 'This executes if the time-of-day conditions match'
	miss_help = "This executes if the time-of-day conditions don't match"
	
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
		placeholder: `Examples:
Mon,Wed-Fri 08:00-17:00
Sat 08:00-12:00
not 1/5/2022 08:00-1/7 13:00
`,
		tooltip: `Enter specifics for DOW/TOD that should be considered.
One range per line. First pattern matched is used`,
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
		data = {},
	}) {
		super.createElement({ isSubtree, data })
		
		let context = null // use the default
		this.makeFixedBranch( 'hit', HIT_LABEL,
			context,
			this.hit_help,
			data ?? {},
		)
		this.makeFixedBranch( 'miss', MISS_LABEL,
			context,
			this.miss_help,
			data ?? {},
		)
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
		
		walkChild( this.hit, callback )
		walkChild( this.miss, callback )
	}
}
