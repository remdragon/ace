import UINode from "./UINode.js";
import Subtree from "./subtree.js";
import CaseSubtree from "./caseSubtree.js";

export default class Select extends UINode {
	static icon = "/media/streamline/kindle.png";
	static context_menu_name = 'Select'
	static command = "select";

	help = "This is a select node";
	label = "Select";

	variable//: string;

	fields = [{ key: "variable" }];

	branches = {
		invalid: {}
	};

	createElement({
		isSubtree = false,
		data = { branches: { invalid: [] } },
		NODE_TYPES
	}) {
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
			context: "contextSelect"
		});

		if (data.branches) {
			Object.keys(data.branches)
				.filter(br => br !== "invalid")
				.forEach((k, i) => {
					if (!data.branches[k]) {
						return;
					}

					this.branches[k] = new CaseSubtree(this, k);
					this.branches[k].createElement({
						isSubtree: true,
						data: data.branches[k],
						NODE_TYPES,
						context: "contextOptionalSubtree"
					});
				});
		}

		this.branches.invalid = new Subtree(this, "Invalid");
		this.branches.invalid.createElement({
			isSubtree: true,
			data: data.branches.invalid,
			NODE_TYPES
		});
	}

	getJson() {
		const sup = super.getJson();

		const branchesData = {};
		Object.keys(this.branches).forEach((k, i) => {
			if (!this.branches[k]) {
				return;
			}

			branchesData[k] = this.branches[k].getJson();
		});

		return {
			...sup,
			branches: branchesData
		};
	}

	remove(node/*: UINode*/) {
		super.remove(node)

		Object.keys(this.branches).some(key => {
			const branch = this.branches[key];

			if (branch.element.id === node.element.id) {
				delete this.branches[key];
				return true;
			}

			return false;
		});
	}

	reorder() {
		const domNodes = this.element.childNodes.sort((a, b) => {
			const aText = a.text;
			const bText = b.text;

			if (aText === "Invalid" && bText !== "Invalid") {
				return 1;
			}

			if (aText !== "Invalid" && bText === "Invalid") {
				return -1;
			}

			return aText > bText;
		});

		const ulNode = this.element.childNodes[0].elementLi.parentNode;

		domNodes.forEach(el => {
			ulNode.appendChild(el.elementLi);
		});

		// TODO: fix dotted lines after reordering
	}
}