import UINode from './UINode.js'

export default class PlayMOH extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play Music on Hold'
	static command = 'moh'
	
	help = 'Play Hold Music for the caller'
	label = 'Play MOH'
	
	seconds//: number
	
	fields = [{ key: 'seconds', type: 'float' }]
}
