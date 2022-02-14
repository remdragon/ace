import UINode from './UINode.js'

export default class PreAnnounce extends UINode {
	static icon = '/media/streamline/music-note-2@20.png'
	static context_menu_name = 'Play Pre-Announce'
	static command = 'preannounce'
	
	help = `Plays the current preannounce greeting based on the current flags,<br/>
holiday, and time of day.
`
	
	label = 'PreAnnounce'
}
