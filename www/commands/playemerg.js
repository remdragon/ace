import UINode from './UINode.js'

export default class PlayEmerg extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Play ER Greeting?'
	static command = 'playemerg'
	
	help = `In theory, play an emergency greeting. This command may not get implemented and may be removed from here<br/>
<br/>
Please do not use this command at this time
`
	label = 'PlayEmerg'
}
