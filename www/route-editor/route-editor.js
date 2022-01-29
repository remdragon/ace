// main editor module
import context_menu from './context-menu.js'
import ajax from '../ajax.js'

import UINode from '../commands/UINode.js'
import Root from '../commands/root.js'
import NODE_TYPES from '../commands/index.js'

import { debounce } from './util.js'

const route_id = parseInt( location.pathname.split( /\// ).pop() )
let route_data // route data
let tree
let root

let divHelp

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
		initTree( data )
	}
)

function initTree( data ) {
	route_data = data
	document.title = route_data.name
	
	tree = createTree( 'div_tree', 'white', context_menu )
	
	//console.log( 'route_id=', route_id, 'route_data=', route_data )
	root = new Root( tree, route_id, route_data, NODE_TYPES )
	
	divHelp = document.getElementById( 'div_help' )
	
	tree.nodeSelectedEvent = onNodeSelected
	
	tree.drawTree()
	
	UINode.onChange = () => {
		treeDidChange()
	}
}

function onNodeSelected(aimaraNode)
{
	let node = aimaraNode.node
	
	if (node) {
		divHelp.innerHTML = node.help
		node.onSelected( divHelp )
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
