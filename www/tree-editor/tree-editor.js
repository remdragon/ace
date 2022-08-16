import context_menu from './context-menu.js'
import ajax from '../ajax.js'

import UINode from '../commands/UINode.js'
import RootRoute from '../commands/root_route.js'
import RootVoiceMail from '../commands/root_voicemail.js'

import { debounce } from './util.js'

const id = parseInt( location.pathname.split( /\// ).pop() )
let route_data // route data
let tree
let root

let divHelp

export function routeEditorMain()
{
	ajax(
		'get',
		location.href,
		{
			accept: 'application/json',
			'cache-control': 'no-cache'
		},
		null,
		(data) => {
			console.assert( !tree )
			if ( data.success )
				initTree( data.rows[0], RootRoute )
			else
				alert( data.error )
		}
	)
}

export function voiceMailEditorMain()
{
	ajax(
		'get',
		location.href,
		{
			accept: 'application/json',
			'cache-control': 'no-cache'
		},
		null,
		(data) => {
			console.assert( !tree )
			if ( data.success )
				initTree( data.rows[0], RootVoiceMail )
			else
				alert( data.error )
		}
	)
}

function initTree( data, Root )
{
	route_data = data
	document.title = route_data.name
	
	tree = createTree( 'div_tree', 'white', context_menu )
	
	//console.log( 'id=', id, 'route_data=', route_data )
	root = new Root( tree, id, route_data )
	
	divHelp = document.getElementById( 'div_details' )
	
	tree.nodeSelectedEvent = onNodeSelected
	
	tree.drawTree()
	
	root.makeClickable()
	
	UINode.onChange = () => {
		treeDidChange()
	}
}

async function onNodeSelected( aimaraNode )
{
	let uinode = aimaraNode.uinode
	
	if( uinode )
	{
		divHelp.innerHTML = ( uinode.help || '(This node is missing its help text)' ) + '<br/><br/>'
		await uinode.onSelected( divHelp )
	}
}

function updateTree() {
	console.log( 'update' )
	
	ajax(
		"patch",
		location.href,
		{
			accept: "application/json",
			"Content-Type": "application/json",
			"cache-control": "no-cache"
		},
		JSON.stringify( root.getJson() ),
		(data) => {
			console.log( 'patch callback' )
		}
	)
}

// Send to server changed after some time user has stopped editing
export const treeDidChange = debounce( updateTree, 1000 )
