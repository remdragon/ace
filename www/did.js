var deleteButton = document.getElementById( 'delete' )

deleteButton.addEventListener( 'click', function( event ) {
	event.preventDefault()
	if ( confirm( 'Delete this DID? ' ) )
	{
		let url = window.location.href
		fetch(
			url,
			{
				method: 'DELETE',
				headers: {
					'Accept': 'application/json',
				}
			},
		).then( data => {
			if ( !data.ok )
			{
				data.json().then( jdata => {
					alert( jdata.error )
				}).catch( error => alert( error ))
			}
			else
				window.location.href = '/dids/'
		}).catch( error => alert( error ))
	}
})
