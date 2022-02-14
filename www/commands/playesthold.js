import UINode from './UINode.js'

export default class PlayEstHold extends UINode {
	static icon = '/media/streamline/music-note-2@20.png'
	static context_menu_name = 'Play Est HoldTime'
	static command = 'playesthold'
	
	help = `Play estimated hold time in queue<br/>
<br/>
This command is not implemented in ACE yet, so it does nothing<br/>
<br/>
(Estimated hold time calculation is supported in ACD,
we just haven't decided how to implement that here)
`
	label = 'Play EstHold'
	
	value//: string
	
	fields = [
		{ key: 'value' },
	]
}
