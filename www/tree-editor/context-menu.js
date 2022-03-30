import PatternSubtree from '/commands/patternSubtree.js'

import * as commands from '/commands/index.js'
//import UINode from '/commands/UINode.js'
import { treeDidChange } from './tree-editor.js'
import{ moveNodeUp, moveNodeDown } from './util.js'

const copyNode = {
	text: 'Copy (Ctrl+C)',
	icon: '/media/streamline/edit-copy.png',
	action: function( treenode )
	{
		treenode.uinode.onkeydown_ctrl_c()
	}
}

const cutNode = {
	text: 'Cut (Ctrl+X)',
	icon: '/media/streamline/edit-scissors.png',
	action: function( treenode )
	{
		treenode.uinode.onkeydown_ctrl_x()
	}
}

const pasteNode = {
	text: 'Paste (Ctrl+V)',
	icon: '/media/streamline/edit-glue.png',
	action: async function( treenode )
	{
		treenode.uinode.onkeydown_ctrl_v()
	}
}

const deleteNode = {
	text: 'Delete (Delete)',
	icon: '/aimara/images/delete.png',
	action: function( treenode )
	{
		let uinode = treenode.uinode
		uinode.onkeydown_Delete()
	}
}

/*const getJson = {
	text: 'Get Json',
	icon: '/aimara/images/tree.png',
	action: function( treenode )
	{
		let json = JSON.stringify( treenode.uinode.getJson(), null, 4 )
		console.log( json )
	}
}*/

const nodeActions = {
	text: 'Node Actions',
	icon: '/aimara/images/star.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			//getJson,
			{
				text: 'Move up (Shift+Up)',
				icon: '/aimara/images/tree.png',
				action: function( treenode )
				{
					let uiparent = treenode.uinode.parent
					let treeparent = treenode.parent
					
					if ( treeparent && uiparent )
					{
						moveNodeUp( treeparent, treenode )
						uiparent.moveNodeUp( treenode.uinode )
						treeDidChange()
					}
					treenode.elementLi.focus()
				}
			},
			{
				text: 'Move down (Shift+Down)',
				icon: '/aimara/images/tree.png',
				action: function( treenode )
				{
					let uiparent = treenode.uinode.parent
					let treeparent = treenode.parent
					
					if ( treeparent && uiparent )
					{
						//console.log( 'treeparent=', treeparent, ', treenode=', treenode )
						moveNodeDown( treeparent, treenode )
						//console.log( 'uiparent=', uiparent, ', treenode.uinode=', treenode.uinode )
						uiparent.moveNodeDown( treenode.uinode )
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
	action: function( treenode ) {},
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
				commands.RxFax,
				//commands.SetMOH,
				commands.Transfer,
				commands.Voicemail,
			].map( NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType ),
			}))
		]
	}
}

const newRouteLogicNode = {
	text: 'New Logic',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
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
				action: createNodeFromNodeType( NodeType ),
			}))
		]
	}
}

const newNotifyLogicNode = {
	text: 'New Logic',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			...[
				commands.GoTo,
				//commands.IfNum,
				//commands.IfStr,
				commands.Label,
				commands.Log,
				commands.Repeat,
				//commands.Route,
				//commands.Select,
				//commands.SetNode,
				//commands.Throttle,
				commands.TOD,
				//commands.Translate,
				commands.Wait,
			].map( NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType ),
			}))
		]
	}
}

const newNotifyActionNode = {
	text: 'New Notification',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			...[
				commands.Email,
				commands.SMS,
			].map( NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType ),
			}))
		]
	}
}

const createRoutePlayNode = {
	text: 'New Play Node',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			...[
				commands.PlayDTMF,
				commands.MOH,
				commands.Playback,
				commands.PreAnnounce,
				commands.Ring,
				commands.Silence,
				commands.Tone,
				commands.PlayTTS
				//commands.PlayEmerg,
				//commands.PlayEstHold,
			].map( NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType )
			}))
		]
	}
}

const createVoicemailPlayNode = {
	text: 'New Play Node',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			...[
				commands.Greeting,
				commands.PlayDTMF,
				commands.MOH,
				commands.Playback,
				commands.PreAnnounce,
				commands.Ring,
				commands.Silence,
				commands.Tone,
				commands.PlayTTS
				//commands.PlayEmerg,
				//commands.PlayEstHold,
			].map( NodeType => ({
				text: NodeType.context_menu_name,
				icon: NodeType.icon,
				action: createNodeFromNodeType( NodeType )
			}))
		]
	}
}

const ivrNodeActions = {
	text: 'IVR node',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [{
			text: 'Add Digits',
			icon: commands.IVR.icon,
			action: function( treenode )
			{
				let uinode = treenode.uinode
				let digits = ''
				let min_digits = parseInt( uinode.min_digits )
				if( isNaN( min_digits ))
				{
					alert( 'invalid min digits for this IVR, please fix it first' )
					return
				}
				let max_digits = parseInt( uinode.max_digits )
				if( isNaN( max_digits ))
				{
					alert( 'invalid max digits for this IVR, please fix it first' )
					return
				}
				let regex = null
				if( uinode.digit_regex )
				{
					regex = new RegExp( uinode.digit_regex )
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
					if( uinode.branches[digits] )
					{
						alert( 'a branch for those digits has already been created' )
						continue
					}
					let new_uinode = uinode.makeDigitsBranch( digits, {} )
					uinode.reorder()
					uinode.tree.selectNode( new_uinode.treenode )
					treeDidChange()
					return
				}
			}
		}]
	}
}


const ivrRootVoicemailActions = {
	text: 'Add Digit',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			...[1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map( digit => (
			{
				text: digit,
				icon: commands.IVR.icon, // this is confusing but I don't have a better icon right now
				action: function( treenode )
				{
					let uinode = treenode.uinode
					if( uinode.branches[digit] )
					{
						alert( 'a branch for that digit has already been created' )
						return
					}
					let new_uinode = uinode.makeDigitBranch( digit, {} )
					uinode.reorder()
					uinode.tree.selectNode( new_uinode.treenode )
					treeDidChange()
				}
			}))
		]
	}
}


const selectNodeActions = {
	text: 'Select node',
	icon: '/aimara/images/add1.png',
	action: function( treenode ) {},
	submenu: {
		elements: [
			{
				text: 'New pattern branch',
				icon: PatternSubtree.icon,
				action: function( treenode )
				{
					let uinode = treenode.uinode
					let i = 0
					let pattern = prompt( 'Pattern:' )
					let new_uinode = uinode.makePatternBranch( pattern, {} )
					uinode.reorder()
					treeDidChange()
				}
			}
		]
	}
}

const context_menu = {
	contextRouteRoot: {
		elements: [ copyNode, pasteNode, newTelephonyNode, newRouteLogicNode, createRoutePlayNode ]
	},
	contextLeaf: {
		elements: [ copyNode, cutNode, pasteNode, deleteNode, nodeActions ]
	},
	contextSubtree: {
		elements: [ copyNode, pasteNode, nodeActions, newTelephonyNode, newRouteLogicNode, createRoutePlayNode ]
	},
	contextOptionalSubtree: {
		elements: [ copyNode, pasteNode, deleteNode, nodeActions, newTelephonyNode, newRouteLogicNode, createRoutePlayNode ]
	},
	contextOptionalSubtreeVoicemail: {
		elements: [ copyNode, pasteNode, deleteNode, nodeActions, newTelephonyNode, newRouteLogicNode, createVoicemailPlayNode ]
	},
	contextOptionalSubtreeVoicemailDelivery: {
		elements: [ copyNode, pasteNode, deleteNode, nodeActions, newNotifyLogicNode, newNotifyActionNode ]
	},
	contextIVR: {
		elements: [ copyNode, deleteNode, nodeActions, ivrNodeActions ]
	},
	contextPAGD: {
		elements: [ copyNode, deleteNode, nodeActions ]
	},
	context_GreetingInvalidTimeout: {
		elements: [ copyNode, pasteNode, createRoutePlayNode ]
	},
	contextIVRBranch: {
		elements: [ copyNode, pasteNode, deleteNode, newTelephonyNode, newRouteLogicNode, createRoutePlayNode ]
	},
	contextIVR_PAGD_SuccessFailure: {
		elements: [ copyNode, pasteNode, newTelephonyNode, newRouteLogicNode, createRoutePlayNode ]
	},
	contextSelect: {
		elements: [ deleteNode, nodeActions, selectNodeActions ]
	},
	contextVoiceMailRoot: {
		elements: [ ivrRootVoicemailActions ]
	},
	contextRootVoicemailDigitSubtree: {
		elements: [ copyNode, pasteNode, deleteNode, newTelephonyNode, newRouteLogicNode, createVoicemailPlayNode ]
	},
	contextRootVoicemailDelivery: {
		elements: [ copyNode, pasteNode, newNotifyLogicNode, newNotifyActionNode ]
	},
}

function createNodeFromNodeType( NodeType )
{
	return function( treenode )
	{
		let parent = treenode.uinode
		let uinode = new NodeType( parent )
		uinode.createElement({})
		treeDidChange()
		
		// TODO FIXME: figure out why the following isn't working:
		//console.log( 'attempting focus to ', uinode.treenode.elementLi )
		//uinode.treenode.elementLi.focus()
	}
}

export default context_menu
