import UINode from './UINode.js'

export default class Answer extends UINode {
	static icon = '/media/streamline/phone-actions-receive.png'
	static context_menu_name = 'Answer'
	static command = 'answer'
	
	help = `Transitions the call to an ANSWERED state which sends back answer supervision and begins billing with your carrier.

This command does nothing if the call is already in an answered state.
`
	label = 'Answer'
}
