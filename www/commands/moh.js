import UINode from './UINode.js'

export default class MOH extends UINode {
	static icon = '/media/streamline/music-note-2.png'
	static context_menu_name = 'Stream MoH'
	static command = 'moh'
	
	help = `Streams Hold Music for the caller<br/>
<br/>
Execution moves to the next node immediately. Use the "Wait" command if a delay is needed
`
	
	label = 'Play MOH'
	
	fields = []
}
