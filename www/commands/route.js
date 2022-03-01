import UINode from './UINode.js'

export default class Route extends UINode {
	static icon = '/media/streamline/folder-code.png'
	static context_menu_name = 'Route'
	static command = 'route'
	
	help = `Choose another route to execute from here.<br/>
<br/>
When that route finishes, execution will resume here in this route
`
	
	get label()
	{
		return 'Route ' + ( this.name || this.route || '(Undefined)' )
	}
	
	name = ''
	route = ''//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	},{
		key: 'route',
		type: 'int', // TODO FIXME: change to string and call expand() from lua?
		input: 'select',
		label: 'Route:',
		async options( self )
		{
			let params = { headers: { 'Accept': 'application/json' }}
			let json = await fetch( '/routes', params )
				.then( rsp => rsp.json() )
			//console.log( JSON.stringify( json ) )
			let options = [{ label: '(Undefined)', value: '' }]
			for ( let row of json.rows )
			{
				options.push({ label: `${row.route} ${row.name || "(Unnamed)"}`, value: row.route })
			}
			return options
		}
	}]
}
