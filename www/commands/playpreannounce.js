import UINode from './UINode.js'

export default class PlayPreAnnounce extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play Pre-Announce'
	static command = 'preannounce'
	
	help = `Plays the current preannounce greeting based on the current flags,<br/>
holiday, and time of day.
`
	
	label = 'PreAnnounce'
}
