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

let delete_links = document.getElementsByClassName( 'route_delete' )
for ( let i = 0; i < delete_links.length; i++ ) {
	let el = delete_links[i]
	let id = el.getAttribute( 'route' )
	el.addEventListener(
		'click',
		function() {
			alert(id)
		},
		false,
	)
}
