import UINode from './UINode.js';

export default class PlayEstHold extends UINode {
	static icon = '/media/streamline/music-note-2.png';
	static context_menu_name = 'Play Est HoldTime'
	static command = 'playesthold';
	
	help = 'No help is available for this node type, yet';
	label = 'Play EstHold';
	
	value//: string;
	
	fields = [
		{key: 'value'},
	];
}
