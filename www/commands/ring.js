import UINode from "./UINode.js"

export default class Ring extends UINode {
	static icon = '/media/streamline/phone-actions-ring.png'
	static context_menu_name = 'Play RingTone'
	static command = 'ring'
	
	help = 'This is used to initiate ringing to the caller.'
	label = 'Ring'
	
	fields = []
}
