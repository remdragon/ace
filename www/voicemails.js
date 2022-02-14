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

let delete_links = document.getElementsByClassName( 'delete' )
for( let el of delete_links )
{
	let id = el.getAttribute( 'box' )
	el.addEventListener(
		'click',
		function( event )
		{
			let id_confirm = prompt( `Type "${id}" to delete voicemail box ${id} and all it's greetings and messages?` )
			if( id_confirm == id )
			{
				fetch(
					`/voicemails/${id}`,
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
					window.location.href = '/voicemails'
				}).catch( error => alert( error ))
			}
		},
		false,
	)
}
