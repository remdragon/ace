import UINode from "./UINode.js"

export default class Ring extends UINode {
	static icon = '/media/streamline/music-note-2.png' // TODO FIXME: need a better icon
	static context_menu_name = 'Play RingTone'
	static command = 'ring'
	
	help = 'This is used to initiate ringing to the caller.'
	label = 'Ring'
	
	fields = []
}
