import{ UINode, walkChild } from './UINode.js'
import PatternSubtree from './patternSubtree.js'

export default class Select extends UINode {
	static icon = '/media/streamline/hierarchy.png'
	static context_menu_name = 'Select'
	static command = 'select'
	
	help = `Select nodes allow you pull in information and test for multiple values<br/>
<br/>
*THIS COMMAND IS NOT IMPLEMENTED YET, PLEASE DO NOT TRY TO USE IT`
	invalid_subtree_help = `If the expression does not match any of the provided patterns,<br/>
these commands will be executed`
	
	label = 'Select'
	
	expression//: string
	
	fields = [{
		key: 'expression',
		tooltip: 'You can typically want to reference a channel variable like ${zip_code}',
	}]
	
	branches = null
	invalid = null
	
	createElement({
		isSubtree = false,
		data = {},
	}) {
		super.createElement({
			isSubtree,
			data,
			context: 'contextSelect'
		})
		
		this.branches = []
		//Object.keys( data.branches )
		//.filter( br => br !== 'invalid' )
		//.forEach((k, i) =>
		for( let i in data.branches ?? [] )
			this.makePatternBranch( pattern, data.branches[i] ?? {} )
		
		this.makeFixedBranch( 'invalid', INVALID_LABEL,
			'context_GreetingInvalidTimeout',
			this.invalid_subtree_help,
			data,
		)
	}
	
	makePatternBranch( pattern, data )
	{
		let uinode = new PatternSubtree( this, pattern )
		this.branches.push( uinode )
		uinode.createElement({
			isSubtree: true,
			data: data ?? {},
			context: uinode.contextOptionalSubtree(),
		})
		return uinode
	}
	
	getJson()
	{
		const sup = super.getJson()
		
		const branchesData = {}
		for( let i in this.branches )
		{
			if ( this.branches[i] )
				branchesData[i] = this.branches[i].getJson()
			else
				branchesData[i] = []
		}
		
		let invalidData = this.invalid.getJson()
		
		return {
			...sup,
			branches: branchesData,
			invalid: invalidData,
		}
	}
	
	walkChildren( callback )
	{
		super.walkChildren( callback )
		
		for( let node of branches )
			walkChild( node, callback )
		walkChild( this.invalid, callback )
	}
	
	remove( uinode/*: UINode*/ )
	{
		super.remove( uinode )
		
		for( let i in this.branches )
		{
			let branch = this.patters[i]
			
			if( branch.treenode.id === uinode.treenode.id )
			{
				delete this.branches[i]
				return
			}
		}
	}
	
	reorder() {
		const domNodes = this.treenode.childNodes.sort(( a, b ) => {
			// invalid stays at the bottom
			if( a.text === 'Invalid' && b.text !== 'Invalid' )
				return 1
			if( a.text !== 'Invalid' && b.text === 'Invalid' )
				return -1
			// everything else stays put
			return 0
		})
		
		const ulNode = this.treenode.childNodes[0].elementLi.parentNode
		
		domNodes.forEach(el => {
			ulNode.appendChild( el.elementLi )
		})
		
		// TODO: fix dotted lines after reordering
	}
}
