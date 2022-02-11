'use strict'
import ajax from './ajax.js'

function success_callback(data) {
	let success = data['success']
	if (!success) alert( JSON.stringify( data ))
	else {
		let box = data['rows'][0]['box']
		window.location.href = `/voicemails/${box}`
	}
}

let new_link = document.getElementById( 'box_new' )
new_link.addEventListener(
	'click',
	function() {
		let box = prompt( 'New Voicemail box number:' )
		
		if( box == null )
		{
			console.log( 'New Voicemail box request cancelled' )
		}
		else
		{
			let headers = {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			}
			
			let body = JSON.stringify( { box: box } )
			ajax( 'POST', '/voicemails', headers, body, success_callback )
		}
	},
	false,
)

let delete_links = document.getElementsByClassName( 'box_delete' )
for ( let i = 0; i < delete_links.length; i++ ) {
	let el = delete_links[i]
	let id = el.getAttribute( 'box' )
	el.addEventListener(
		'click',
		function() {
			alert(id)
		},
		false,
	)
}
