import Subtree from "./subtree.js";

export default class CaseSubtree extends Subtree {
	static context_menu_name = 'N/A'
	get label() {
		return `Case "${this.value || ""}":`;
	}
	
	//set label(value){}
	
	value /*: string*/ = "";
	
	fields = [{ key: "value" }];
}
