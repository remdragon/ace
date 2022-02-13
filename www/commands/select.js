import{ UINode, walkChild } from './UINode.js'
import Subtree from './subtree.js'
import CaseSubtree from './caseSubtree.js'

export default class Select extends UINode {
	static icon = '/media/streamline/hierarchy.png'
	static context_menu_name = 'Select'
	static command = 'select'
	
	help = `Select nodes allow you pull in information and test for multiple values<br/>
<br/>
*THIS COMMAND IS NOT IMPLEMENTED YET, PLEASE DO NOT TRY TO USE IT`
	label = 'Select'
	
	expression//: string
	
	fields = [{
		key: 'expression',
		tooltip: 'You can typically want to reference a channel variable like ${zip_code}',
	}]
	
	branches = {
	}
	invalid = []
	
	createElement({
		isSubtree = false,
		data = {},
		NODE_TYPES
	}) {
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
			context: 'contextSelect'
		})
		
		if( data.branches )
		{
			//Object.keys( data.branches )
			//.filter( br => br !== 'invalid' )
			//.forEach((k, i) =>
			for( let k in data.branches ?? {} )
			{
				//if ( !data.branches[k] )
				//	return
				
				this.branches[k] = new CaseSubtree( this, k )
				this.branches[k].createElement(
				{
					isSubtree: true,
					data: data.branches[k],
					NODE_TYPES,
					context: 'contextOptionalSubtree'
				})
			}
		}
		
		this.invalid = new Subtree( this, 'Invalid' )
		this.invalid.createElement(
		{
			isSubtree: true,
			data: data.invalid ?? {},
			NODE_TYPES
		})
	}
	
	getJson()
	{
		const sup = super.getJson()
		
		const branchesData = {}
		for( let k in this.branches )
		{
			if ( this.branches[k] )
				branchesData[k] = this.branches[k].getJson()
			else
				branchesData[k] = []
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
	
	remove(node/*: UINode*/)
	{
		super.remove( node )
		
		Object.keys( this.branches ).some( key =>
			{
			const branch = this.branches[key]
			
			if (branch.element.id === node.element.id)
			{
				delete this.branches[key]
				return true
			}
			
			return false
		})
	}
	
	reorder() {
		const domNodes = this.element.childNodes.sort(( a, b ) => {
			const aText = a.text
			const bText = b.text
			if( aText === 'Invalid' && bText !== 'Invalid' )
				return 1
			if( aText !== 'Invalid' && bText === 'Invalid' )
				return -1
			if( aText < bText )
				return -1
			if( aText > bText )
				return 1
			return 0
		})
		
		const ulNode = this.element.childNodes[0].elementLi.parentNode
		
		domNodes.forEach(el => {
			ulNode.appendChild(el.elementLi)
		})
		
		// TODO: fix dotted lines after reordering
	}
}
