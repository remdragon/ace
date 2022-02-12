import NamedSubtree from './named_subtree.js'

export default class CaseSubtree extends NamedSubtree {
	static context_menu_name = 'N/A'
	get label() {
		let s = `Case "${this.value || ''}"`
		if( this.name )
			s += ' ' + this.name
		return s
	}
	
	//set label(value){}
	
	name = '' // : string
	value /*: string*/ = ''
	
	fields = [{
		key: 'name',
		label: 'Name:'
	},{
		key: 'value',
		label: 'Value:',
	}]
}
