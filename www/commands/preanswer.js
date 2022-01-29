import UINode from './UINode.js'

export default class PreAnswer extends UINode {
	static icon = '/media/streamline/robot-1.png'
	static context_menu_name = 'Pre-Answer'
	static command = 'preanswer'
	
	help = `pre-answer transitions a call from the "routing" to the "ringing" state<br>
<br>
This is necessary if you want to play ringing or other audio to the caller<br/>
<br>
This should be done soon after the call arrives because carriers will give up`
	label = 'Pre-Answer'
}
