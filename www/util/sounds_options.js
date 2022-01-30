export default async function sounds_options()
{
	let params = { headers: { 'Accept': 'application/json' }}
	let json = await fetch( '/sounds/', params )
		.then( rsp => rsp.json() )
	//console.log( JSON.stringify( json ) )
	let options = []
	for ( let row of json.rows )
	{
		options.push({ label: row.sound, value: row.sound })
	}
	return options
}
