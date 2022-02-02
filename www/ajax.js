'use strict'

// here is the "itas solutions" ajax method. Put it in ajax.js

// The important difference is that when the server is sending data to
// the ajax request, it *must* be json encoded. If this function fails
// to decode the response as ajax, it will call the fail_callback function
// this is important because if there's a 500 error or other failure condition,
// we want that information to be visible instead of quietly putting it's error
// information in the browser's console log.

// preferrably fail_callback should call alert() with the error information,
// at least during development

class AjaxRequestLog
{
	url // string
	start_timestamp // Date;
	end_timestamp = null // Date | null = null;
	
	constructor(url /*string*/ ) {
		this.url = url
		this.start_timestamp = new Date()
	}
	
	begin() {
		this.start_timestamp = new Date()
		console.log('request made for: %s', this.url)
	}
	
	end(status /*number*/ ) {
		this.end_timestamp = new Date()
		var time_between =
			(this.end_timestamp.getTime() - this.start_timestamp.getTime()) / 1000
		console.log(
			'request completed: %s. ( %s sec ) status=%d',
			this.url,
			time_between,
			status,
		)
	}
}

export default function ajax(
	method, //: string,
	url, //: string,
	headers, //: any,
	body, //: any,
	success_callback, // : (data: any) => void,
	fail_callback, // ?: (body: any) => void,
)
{
	if( !fail_callback )
	{
		//if there is no fail callback, create one
		fail_callback = function( body )
		{
			alert( body )
		}
	}

	if ( typeof success_callback != 'function' )
	{
		alert( 'ajax success_callback must be a function callback' )
		return
	}
	
	if ( typeof fail_callback != 'function' )
	{
		alert( 'ajax fail_callback must be NULL or a function callback' )
		return
	}
	
	var xhr = ajax_new_XmlHttpRequest()
	var log = new AjaxRequestLog( url )
	
	xhr.onreadystatechange = function()
	{
		if ( this.readyState != 4 )
			return
		log.end( this.status )
		try
		{
			if ( this.status >= 200 && this.status < 300 )
			{
				var data = null;
				var redirect = xhr.getResponseHeader( 'redirect' )
				if ( redirect ) {
					location.href = redirect
					return
				}
				if ( this.status != 204 )
					data = JSON.parse( this.responseText ) // all ajax responses must be json-encoded
				//console.log ( "data" + JSON.stringify ( data ) )
				success_callback(data);
			}
			else if ( this.status == 0 )
			{
				fail_callback( 'timeout waiting for response from server' )
			}
			else
			{
				var e =
					'server error: ' +
					this.status +
					' - ' +
					this.statusText +
					' - ' +
					this.responseURL
				if( this.responseText )
				{
					var response = this.responseText
					var jsonObj = JSON.parse( response )
					if ( jsonObj && jsonObj.error )
						response = jsonObj.error
					e += ':\n\n' + response
				}
				console.error( e )
				fail_callback( e )
			}
		} catch (e) {
			var errorStr =
				'ajax caught exception:\n\n' +
				e +
				'\n\nresponse body:\n\n' +
				this.responseText +
				'\n\n' +
				e.stack;
			console.error( errorStr )
			fail_callback( errorStr )
		}
	}
	// TODO FIXME: do we set another xmlhttp event function to point to fail_callback?
	if ( ajax.cache_bust && method == 'GET' )
	{
		if ( url.indexOf('?') != -1 )
			url += '&_=' + new Date().getTime()
		else
		url += '?_=' + new Date().getTime()
	}
	
	log.begin()
	xhr.open( method, url, true )
	
	if ( headers != null )
		for ( var name in headers )
			xhr.setRequestHeader( name, headers[name] )
	
	if( body )
		xhr.send( body )
	else
		xhr.send()
}
// IE cache-busting ( set to false to disable this behavior ):
ajax.cache_bust =
	navigator.userAgent.indexOf('MSIE ') > 0 ||
	navigator.appVersion.indexOf('Trident/') > -1;
//console.log ( 'navigator.userAgent=' + window.navigator.userAgent + ', ajax.cache_bust=' + ajax.cache_bust )

function ajax_new_XmlHttpRequest()
{
	if( window.XMLHttpRequest )
		// IE7+, Firefox, Chrome, Opera, Safari
		return new XMLHttpRequest()
	else
		// code for IE6, IE5
		return new ActiveXObject( 'Microsoft.XMLHTTP' )
}
