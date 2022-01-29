import UINode from "./UINode.js";

export default class SetMOH extends UINode {
	static icon = "/media/streamline/type-cursor-1.png";
	static context_menu_name = 'Set MOH'
	static command = "setmoh";
	
	help = "Sets the music-on-hold source for this call.";
	label = "SetMoh";
	
	value//: string;
	
	fields = [{ key: "value" }]
}
