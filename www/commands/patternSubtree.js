import NamedSubtree from './named_subtree.js'

export default class PatternSubtree extends NamedSubtree {
	static context_menu_name = 'N/A'
	
	get label() {
		if( this.name )
			return 'Pattern ' + this.name
		else
			return 'Pattern ' + ( this.pattern ?? '' )
	}
	
	name = '' // string
	pattern = '' // string
	
	fields = [{
		key: 'name',
		label: 'Name:'
	},{
		key: 'pattern',
		label: 'Pattern:',
	}]
}
