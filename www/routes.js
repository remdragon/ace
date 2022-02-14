'use strict'
import ajax from './ajax.js'

function success_callback(data) {
	let success = data['success']
	if (!success) alert( JSON.stringify( data ))
	else {
		let route = data['rows'][0]['route']
		window.location.href = `/routes/${route}`
	}
}

let new_link = document.getElementById( 'route_new' )
new_link.addEventListener(
	'click',
	function() {
		let route = prompt( 'New Route Number:' )
		
		if( route == null )
		{
			console.log( 'New Route request cancelled' )
		}
		else
		{
			let headers = {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			}
			
			let body = JSON.stringify( { route: route } )
			ajax( 'POST', '/routes', headers, body, success_callback )
		}
	},
	false,
)

let delete_links = document.getElementsByClassName( 'delete' )
for( let el of delete_links )
{
	let id = el.getAttribute( 'route' )
	el.addEventListener(
		'click',
		async function( event )
		{
			let id_confirm = prompt( `Type "${id}" to delete route ${id}` )
			if( id_confirm == id )
			{
				fetch(
					`/routes/${id}`,
					{
						method: 'DELETE',
						headers: { Accept: 'application/json' },
					}
				).then( data => {
					if( !data.ok )
					{
						data.json().then( jdata => {
							alert( jdata.error )
						}).catch( error => alert( error ))
					}
					window.location.href = '/routes'
				}).catch( error => alert( error ))
			}
		},
		false,
	)
}
