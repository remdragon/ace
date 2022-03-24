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

let clone_links = document.getElementsByClassName( 'clone' )
for( let el of clone_links )
{
	let id = el.getAttribute( 'box' )
	el.addEventListener(
		'click',
		async function( event )
		{
			let new_box = prompt( `Type box # to clone ${id} to:` )
			if( !new_box )
				return
			
			let url = `/voicemails/${id}`
			let params = {
				method: 'GET',
				headers: { Accept: 'application/json' },
			}
			try
			{
				let rsp = await fetch( url, params )
				if( !rsp.ok )
				{
					var body = await rsp.text()
					alert( `Error fetching box ${id} settings: ${rsp.status} ${rsp.statusText} - ${body}` )
					return
				}
				let jdata = await rsp.json()
				if( !jdata.success )
				{
					alert( `Error fetching box ${id} settings: ${jdata.error}` )
					return
				}
				var settings = jdata.rows[0]
			}
			catch( e )
			{
				alert( `Error fetching box ${id} settings: ${e}` )
				return
			}
			
			settings.name = ( settings.name ?? '(Unnamed)' ) + ' (Clone)'
			
			console.log( 'settings=', settings )
			url = '/voicemails'
			params.method = 'POST'
			params.headers['Content-Type'] = 'application/json'
			params.body = JSON.stringify({
				box: new_box,
				settings: settings,
			})
			console.log( 'params=', params )
			try
			{
				let rsp = await fetch( url, params )
				if( !rsp.ok )
				{
					var body = await rsp.text()
					alert( `Error creating new box ${new_box} settings: ${rsp.status} ${rsp.statusText} - ${body}` )
					return
				}
				let jdata = await rsp.json()
				if( !jdata.success )
				{
					alert( `Error creating new box ${new_box}: ${jdata.error}` )
					return
				}
			}
			catch( e )
			{
				alert( `Error creating new box ${new_box}: ${e}` )
				return
			}
			
			window.location.href = `/voicemails/${new_box}`
		},
		false,
	)
}

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
