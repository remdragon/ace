var deleteButton = document.getElementById( 'delete' )

deleteButton.addEventListener( 'click', function( event ) {
	event.preventDefault()
	let id = deleteButton.getAttribute( 'ani' )
	let id_confirm = prompt( `Type "${id}" to delete ANI ${id}:` )
	if( id_confirm == id )
	{
		let url = window.location.href
		fetch(
			url,
			{
				method: 'DELETE',
				headers: { Accept: 'application/json' }
			},
		).then( data => {
			if ( !data.ok )
			{
				data.json().then( jdata => {
					alert( jdata.error )
				}).catch( error => alert( error ))
			}
			else
				window.location.href = '/anis/'
		}).catch( error => alert( error ))
	}
})
