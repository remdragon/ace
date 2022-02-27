import UINode from './UINode.js'

export default class GoTo extends UINode {
	static icon = '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'GoTo'
	static command = 'goto'
	
	help = 'Jumps to a different part of the route'
	get label()
	{
		var self = this
		var target = '(nowhere)'
		if ( this.destination )
		{
			target = '(?missing?)'
			this.walkTree( function( node )
			{
				if( self !== node && self.destination === node.uuid )
					target = node.label
			})
		}
		return 'GoTo ' + target
	}
	
	destination//: string
	
	fields = [{
		key: 'destination',
		input: 'select2',
		label: 'Destination:',
		async options( self ) {
			var targets = [ { label: '(Select One)', value: '' } ]
			self.walkTree( function( node )
			{
				if( node.uuid )
					targets.push( { label: node.label, value: node.uuid } )
			})
			return targets
		},
	}]
}
