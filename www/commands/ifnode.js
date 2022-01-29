import UINode from "./UINode.js";
import Subtree from "./subtree.js";

export default class IfNode extends UINode {
	static icon = "/media/streamline/road-sign-look-both-ways-1.png";
	static context_menu_name = 'If'
	static command = "if";

	help =
		"Test the condition. If the condition is true, executable all nodes in the 'true' branch, otherwise the 'false' branch";
	label = "If";

	condition//: string;
	trueBranch//: Subtree;
	falseBranch//: Subtree;

	fields = [{ key: "condition" }];

	createElement({
		isSubtree = false,
		data = { true: [], false: [] },
		NODE_TYPES
	}) {
		super.createElement({ isSubtree, data, NODE_TYPES });

		this.trueBranch = new Subtree(this, "true");
		this.trueBranch.createElement({
			isSubtree: true,
			data: data.true,
			NODE_TYPES
		});

		this.falseBranch = new Subtree(this, "false");
		this.falseBranch.createElement({
			isSubtree: true,
			data: data.false,
			NODE_TYPES
		});
	}

	getJson() {
		let sup = super.getJson();

		return {
			...sup,
			true: this.trueBranch.getJson(),
			false: this.falseBranch.getJson()
		};
	}
}
