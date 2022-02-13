import CaseSubtree from '/commands/caseSubtree.js'
import NamedSubtree from '/commands/named_subtree.js'

import * as commands from '/commands/index.js'
import NODE_TYPES from '/commands/index.js'
import { treeDidChange } from './tree-editor.js'
import{ moveNodeUp, moveNodeDown } from './util.js'

const copyNode = {
	text: 'Copy',
	icon: '/media/streamline/edit-copy.png',
	action: function( element )
	{
		let json = JSON.stringify( element.node.getJson(), null, 4 )
		navigator.clipboard.writeText( json )
	}
}

const cutNode = {
	text: 'Cut',
	icon: '/media/streamline/edit-scissors.png',
	action: function(element)
	{
		let uinode = element.node
		if ( !confirm( `Cut "${uinode.label}" and all its children?` ))
			return
		element.elementLi.focus()
		let json = JSON.stringify( uinode.getJson(), null, 4 )
		navigator.clipboard.writeText( json )
		uinode.parent.remove( uinode )
		element.removeNode()
		treeDidChange()
	}
}

const pasteNode = {
	text: 'Paste',
	icon: '/media/streamline/edit-glue.png',
	action: async function( element )
	{
		let json = await navigator.clipboard.readText()
		let nodeData = JSON.parse( json )
		let nodes = [ nodeData ]
		let is_multi = {
			'': true,
			'root_route': true,
			'root_voicemail': true,
		}
		if( is_multi[nodeData.type] && nodeData.hasOwnProperty( 'nodes' ))
			nodes = nodeData.nodes
		let changed = element.node.createChildren( nodes ?? [], NODE_TYPES )
		if( changed )
			treeDidChange()
	}
}

const deleteNode = {
	text: 'Delete Node',
	icon: '/aimara/images/delete.png',
	action: function( treenode )
	{
		let uinode = treenode.node
		if ( !confirm( `Delete "${uinode.label}" and all its children?` ))
			return
		let uiparent = uinode.parent
		uiparent.remove( uinode )
		treenode.removeNode()
		treeDidChange()
		uiparent.tree.selectNode( uiparent.element )
	}
}

/*const getJson = {
	text: 'Get Json',
	icon: '/aimara/images/tree.png',
	action: function(element)
	{
		let json = JSON.stringify( element.node.getJson(), null, 4 )
		console.log( json )
	}
}*/

const nodeActions = {
	text: 'Node Actions',
	icon: '/aimara/images/star.png',
	action: function(element) {},
	submenu: {
		elements: [
			//getJson,
			{
				text: 'Move node up',
				icon: '/aimara/images/tree.png',
				action: function( treenode )
				{
					let uiparent = treenode.node.parent
					let treeparent = treenode.parent
					
					if ( treeparent && uiparent )
					{
						moveNodeUp( treeparent, treenode )
						uiparent.moveNodeUp( treenode.node )
						treeDidChange()
					}
					treenode.elementLi.focus()
				}
			},
			{
				text: 'Move node down',
				icon: '/aimara/images/tree.png',
				action: function( treenode )
				{
					let uiparent = treenode.node.parent
					let treeparent = treenode.parent
					
					if ( treeparent && uiparent )
					{
						//console.log( 'treeparent=', treeparent, ', treenode=', treenode )
						moveNodeDown( treeparent, treenode )
						//console.log( 'uiparent=', uiparent, ', treenode.node=', treenode.node )
						uiparent.moveNodeDown( treenode.node )
						treeDidChange()
					}
					treenode.elementLi.focus()
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
				commands.Bridge,
				commands.Hangup,
				commands.IVR,
				commands.PAGD,
				commands.PreAnswer,
				//commands.SetMOH,
				commands.Transfer,
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
				commands.IfNum,
				commands.IfStr,
				commands.Label,
				commands.Log,
				commands.Repeat,
				commands.Route,
				//commands.Select,
				commands.SetNode,
				commands.Throttle,
				commands.TOD,
				//commands.Translate,
				commands.Wait,
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
	action: function( element ) {},
	submenu: {
		elements: [
			...[
				commands.PlayDTMF,
				commands.MOH,
				commands.Playback,
				commands.PlayPreAnnounce,
				commands.Ring,
				commands.Silence,
				commands.Tone,
				commands.PlayTTS
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
						digits = prompt( 'Enter digit(s):', digits )
						if( digits == null ) // the user hit cancel
							return
						if( digits.length < min_digits )
						{
							alert( `min_digits for this IVR is ${min_digits}` )
							continue
						}
						if( digits.length > max_digits )
						{
							alert( `max_digits for this IVR is ${max_digits}` )
							continue
						}
						if( regex != null && !regex.test( digits ))
						{
							alert( `digits do not match digit_regex "${digit_regex}"` )
							continue
						}
						if( element.node.branches[digits] )
						{
							alert( 'a branch for those digits has already been created' )
							continue
						}
						element.node.branches[digits] = new NamedSubtree(
							element.node,
							digits,
							commands.IVR.digits_subtree_help,
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


const ivrRootVoicemailActions = {
	text: 'Add Digit',
	icon: '/aimara/images/add1.png',
	action: function( element ) {},
	submenu: {
		elements: [
			...[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map( digit => (
			{
				text: digit,
				icon: commands.IVR.icon, // this is confusing but I don't have a better icon right now
				action: function( treenode )
				{
					let uinode = treenode.node
					if( uinode.branches[digit] )
					{
						alert( 'a branch for that digit has already been created' )
						return
					}
					uinode.branches[digit] = new NamedSubtree(
						uinode,
						digit
					)
					uinode.branches[digit].createElement({
						NODE_TYPES,
						context: 'contextRootVoicemailDigitSubtree'
					})
					uinode.reorder()
					uinode.tree.selectNode( uinode.branches[digit].element )
					treeDidChange()
				}
			}))
		]
	}
}


const ivrVoicemailDeliveryActions = {
}

const selectNodeActions = {
	text: 'Select node',
	icon: '/aimara/images/add1.png',
	action: function( element ) {},
	submenu: {
		elements: [
			{
				text: 'New case branch',
				icon: CaseSubtree.icon,
				action: element => {
					let i = 0
					while( element.node.branches[`branch${i}`] )
						i++
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
}

const context_menu = {
	contextRouteRoot: {
		elements: [copyNode, pasteNode, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextLeaf: {
		elements: [copyNode, cutNode, pasteNode, deleteNode, nodeActions]
	},
	contextSubtree: {
		elements: [copyNode, pasteNode, nodeActions, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextOptionalSubtree: {
		elements: [copyNode, pasteNode, deleteNode, nodeActions, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextIVR: {
		elements: [copyNode, deleteNode, nodeActions, ivrNodeActions]
	},
	contextPAGD: {
		elements: [copyNode, deleteNode, nodeActions]
	},
	contextIVR_PAGD_GreetingInvalidTimeout: {
		elements: [copyNode, pasteNode, createPlayNode]
	},
	contextIVRBranch: {
		elements: [copyNode, pasteNode, deleteNode, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextIVR_PAGD_SuccessFailure: {
		elements: [copyNode, pasteNode, newTelephonyNode, newLogicNode, createPlayNode]
	},
	contextSelect: {
		elements: [deleteNode, nodeActions, selectNodeActions]
	},
	contextVoiceMailRoot: {
		elements: [ ivrRootVoicemailActions ]
	},
	contextRootVoicemailDigitSubtree: {
		elements: [ copyNode, pasteNode, deleteNode, newTelephonyNode, newLogicNode, createPlayNode ]
	},
	contextRootVoicemailDelivery: {
		elements: [ ivrVoicemailDeliveryActions ]
	},
}

function createNodeFromNodeType(NodeType) {
	return element => {
		let node = new NodeType( element.node )
		node.createElement({ NODE_TYPES })
		treeDidChange()
	}
}

export default context_menu
