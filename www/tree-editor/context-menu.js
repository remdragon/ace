import CaseSubtree from '/commands/caseSubtree.js'
import Subtree from '/commands/subtree.js'

import * as commands from '/commands/index.js'
import NODE_TYPES from '/commands/index.js'
import { treeDidChange } from './tree-editor.js'

const deleteNode = {
	text: 'Delete Node',
	icon: '/aimara/images/delete.png',
	action: function(element) {
		element.node.parent.remove(element.node)
		element.removeNode()
		treeDidChange()
	}
}

const nodeActions = {
	text: 'Node Actions',
	icon: '/aimara/images/star.png',
	action: function(element) {},
	submenu: {
		elements: [
			{
				text: 'Get Json',
				icon: '/aimara/images/tree.png',
				action: function(element)
				{
					let json = JSON.stringify( element.node.getJson(), null, 4 )
					console.log( json )
				}
			},
			{
				text: 'Move node up',
				icon: '/aimara/images/tree.png',
				action: function( element )
				{
					let parentNode = element.node.parent
					let parent = element.parent
					
					if ( parent && parentNode )
					{
						moveNodeUp( parent, element )
						parentNode.moveNodeUp( element.node )
						treeDidChange()
					}
				}
			},
			{
				text: 'Move node down',
				icon: '/aimara/images/tree.png',
				action: function( element )
				{
					let parentNode = element.node.parent
					let parent = element.parent
					
					if ( parent && parentNode )
					{
						moveNodeDown( parent, element )
						parentNode.moveNodeDown( element.node )
						treeDidChange()
					}
				}
			}
		]
	}
}

const newTelephonyNode = {
	text: 'New Telephony',
	icon: '/aimara/images/add1.png',
	action: function( element ) {},
	submenu: {
		elements: [
			...[
				commands.AcdCallAdd,
				commands.AcdCallGate,
				commands.AcdCallUnGate,
				commands.Answer,
				commands.Hangup,
				commands.IVR,
				commands.PreAnswer,
				//commands.SetMOH,
				commands.Voicemail,
			].map(NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType )
			}))
		]
	}
}

const newLogicNode = {
	text: 'New Logic',
	icon: '/aimara/images/add1.png',
	action: function(element) {},
	submenu: {
		elements: [
			...[
				commands.GoTo,
				//commands.IfNode,
				commands.Label,
				commands.Repeat,
				commands.Route,
				//commands.Select,
				//commands.SetNode,
				commands.TOD,
				//commands.Translate,
			].map( NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType )
			}))
		]
	}
}

const createPlayNode = {
	text: 'New Play Node',
	icon: '/aimara/images/add1.png',
	action: function(element) {},
	submenu: {
		elements: [
			...[
				commands.Ring,
				commands.Playback,
				commands.PlayMOH,
				commands.PlayPreAnnounce,
				//commands.PlayEmerg,
				//commands.PlayEstHold,
			].map(
				NodeType => ({
					text: NodeType.context_menu_name,
					icon: NodeType.icon,
					action: createNodeFromNodeType( NodeType )
				})
			)
		]
	}
}

const ivrNodeActions = {
	text: 'IVR node',
	icon: '/aimara/images/add1.png',
	action: function(element) {},
	submenu: {
		elements: [
			/*...[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map( branchName => (
			{
				text: `Create branch ${branchName}`,
				icon: commands.IVR.icon,
				action: element =>
				{
					if (!element.node.branches[branchName])
					{
						element.node.branches[branchName] = new Subtree(
							element.node,
							branchName
						)
						element.node.branches[branchName].createElement(
							{ NODE_TYPES, context: "contextOptionalSubtree" }
						)
						element.node.reorder()
						treeDidChange()
					}
				}
			}))*/
			{
				text: 'Add Digits',
				icon: commands.IVR.icon,
				action: element =>
				{
					let digits = ''
					let min_digits = parseInt( element.node.min_digits )
					if( isNaN( min_digits ))
					{
						alert( 'invalid min digits for this IVR, please fix it first' )
						return
					}
					let max_digits = parseInt( element.node.max_digits )
					if( isNaN( max_digits ))
					{
						alert( 'invalid max digits for this IVR, please fix it first' )
						return
					}
					let regex = null
					if( element.node.digit_regex )
					{
						regex = new RegExp( element.node.digit_regex )
					}
					while( true )
					{
						digits = prompt( 'Enter Digits:', digits )
						if( digits == null ) // the user hit cancel
							return
						if( digits.length < min_digits )
						{
							alert( 'min_digits for this IVR is ' + min_digits )
							continue
						}
						if( digits.length > max_digits )
						{
							alert( 'max_digits for this IVR is ' + max_digits )
							continue
						}
						if( regex != null && !regex.test( digits ))
						{
							alert( 'digits do not match digit_regex "' + digit_regex + '"' )
							continue
						}
						if( element.node.branches[digits] )
						{
							alert( 'a branch for those digits has already been created' )
							continue
						}
						element.node.branches[digits] = new Subtree(
							element.node,
							digits,
							commands.IVR.subtree_help,
						)
						element.node.branches[digits].createElement(
							{ NODE_TYPES, context: 'contextOptionalSubtree' }
						)
						element.node.reorder()
						treeDidChange()
						return
					}
				}
			}
		]
	}
}

const selectNodeActions = {
	text: 'Select node',
	icon: '/aimara/images/add1.png',
	action: function(element) {},
	submenu: {
		elements: [
			{
				text: 'New case branch',
				icon: CaseSubtree.icon,
				action: element => {
					let i = 0
					while(element.node.branches[`branch${i}`]) {
						i++
					}
					let branchName = `branch${i}`
					if (!element.node.branches[branchName]) {
						element.node.branches[branchName] = new CaseSubtree(
							element.node,
							branchName
						)
						element.node.branches[branchName].createElement(
							{ NODE_TYPES, context: 'contextOptionalSubtree' }
						)
						element.node.reorder()
						treeDidChange()
					}
				}
			}
		]
	}
};

const context_menu = {
	contextLeaf: { elements: [deleteNode, nodeActions] },
	contextSubtree: {
		elements: [nodeActions, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextOptionalSubtree: {
		elements: [deleteNode, nodeActions, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextIVR: {
		elements: [deleteNode, nodeActions, ivrNodeActions]
	},
	contextIVRBranch: {
		elements: [deleteNode, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextIVRInvalid: {
		elements: [newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextSelect: {
		elements: [deleteNode, nodeActions, selectNodeActions]
	},
	contextVoiceMailRoot: {
		elements: []
	},
};

function createNodeFromNodeType(NodeType) {
	return element => {
		let node = new NodeType(element.node);
		node.createElement({ NODE_TYPES });
		treeDidChange()
	}
}

function moveNodeUp(parent, node) {
	let i = parent.childNodes.findIndex(n => n.id === node.id)

	// if < 0 does not exist
	// if 0 already at top of array
	if (i < 1) {
		return
	}

	let aux = parent.childNodes[i - 1]
	parent.childNodes[i - 1] = parent.childNodes[i]
	parent.childNodes[i] = aux

	node.elementLi.parentNode.insertBefore(
		parent.childNodes[i - 1].elementLi,
		parent.childNodes[i].elementLi
	)
}

function moveNodeDown(parent, node) {
	let i = parent.childNodes.findIndex(n => n.id === node.id)

	// if < 0 does not exist
	// if === length already at bottom of array
	if (i < 0 || i === parent.childNodes.length - 1) {
		return
	}

	let aux = parent.childNodes[i + 1]
	parent.childNodes[i + 1] = parent.childNodes[i]
	parent.childNodes[i] = aux

	node.elementLi.parentNode.insertBefore(
		parent.childNodes[i].elementLi,
		parent.childNodes[i + 1].elementLi
	)
}

export default context_menu
