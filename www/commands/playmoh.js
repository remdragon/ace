import UINode from "./UINode.js";

export default class PlayMOH extends UINode {
	static icon = '/media/streamline/music-note-2.png';
	static context_menu_name = 'Play Music on Hold'
	static command = "moh";
	
	help = "No help is available for this node type, yet";
	label = "Play MOH";
	
	seconds//: number;
	
	fields = [{ key: "seconds", type: "float" }];
}
