/*interface Field {
	key: string;
	name?: string;
	type?: string;
	options?: { label: string; value: string }[];
}*/

const PATTERNS = {
	int: "[0-9]*",
	float: "[0-9]*(.[0-9]*)?"
};

export default class UINode {
	static icon//: string
	static context_menu_name//: string
	static command//: string
	static onChange = () => {}//: function

	help//: string
	fields = []//: Field[];

	parent//: UINode | null;
	element//: any
	children = []//: UINode[]

	constructor(parent /*: UINode*/) {
		if (!parent)
			return
		this.parent = parent
		parent.children.push( this )
	}
	
	get label() {
		return `oops, command ${this.constructor.name} is missing a label!`
	}
	
	createElement({
		isSubtree = false,
		data,
		NODE_TYPES,
		context
	}/*: {
		isSubtree: boolean;
		data: any;
		NODE_TYPES: object;
		context: string;
	}*/) {
		if (data) {
			this.fields.forEach(field => {
				this[field.key] = data[field.key];
			});
		}
		
		this.element = this.parent.element.createChildNode(
			this.label,
			true,
			(this.constructor /*as any*/).icon,
			null,
			context ? context : isSubtree ? 'contextSubtree' : 'contextLeaf'
		)
		
		
		this.element.node = this
	}

	onSelect()/*: void*/ {
		let divHelp = document.getElementById('div_help')

		this.fields.forEach(field => {
			const onChange = evt => {
				if (field.type === 'float') {
					this[field.key] = parseFloat(evt.target.value);
				} else if (field.type === 'int') {
					this[field.key] = parseInt(evt.target.value);
				} else {
					this[field.key] = evt.target.value;
				}

				UINode.onChange()

				this.element.elementSpan.children[1].innerText = this.label
			}

			let inputGroup = document.createElement('div')
			inputGroup.classList.add('input-group')

			let label = document.createElement('label')
			let input

			if (field.type !== 'select') {
				input = document.createElement('input')
				input.setAttribute('type', 'text')

				let pattern = PATTERNS[field.type]
				if (pattern) {
					let reg = new RegExp(`^${pattern}$`)
					input.setAttribute('pattern', pattern)
					input.onkeypress = evt => {
						let text = input.value

						return reg.test(text + evt.key)
					}
				}
			} else {
				input = document.createElement('select')
				input.setAttribute('type', 'select')

				field.options.forEach(option => {
					let optionEl = document.createElement('option')
					optionEl.setAttribute('value', option.value)
					optionEl.innerText = option.label || option.value

					input.appendChild(optionEl)
				})
			}

			input.addEventListener('input', onChange)
			input.value = this[field.key] || ''

			label.innerText = field.name || field.key
			label.appendChild(input)

			inputGroup.appendChild(label)

			divHelp.appendChild(inputGroup)
		})
	}

	getJson() {
		let fields = {}
		this.fields.forEach(field => {
			fields[field.key] = this[field.key] || ''
		})

		return {
			command: (this.constructor /*as any*/).command,
			...fields
		}
	}

	moveNodeUp(node/*: UINode*/) {
		let i = this.children.findIndex(
			n => JSON.stringify(n.getJson()) === JSON.stringify(node.getJson())
		)

		// if < 0 does not exist
		// if 0 already at top of array
		if (i < 1) {
			return
		}

		let aux = this.children[i - 1]
		this.children[i - 1] = this.children[i]
		this.children[i] = aux
	}

	moveNodeDown(node/*: UINode*/) {
		let i = this.children.findIndex(
			n => JSON.stringify(n.getJson()) === JSON.stringify(node.getJson())
		)

		// if < 0 does not exist
		// if === length already at bottom of array
		if (i < 0 || i === this.children.length - 1) {
			return
		}

		let aux = this.children[i + 1]
		this.children[i + 1] = this.children[i]
		this.children[i] = aux
	}

	remove(node/*: UINode*/) {
		this.children = this.children.filter(n => {
			return n.element.id !== node.element.id
		})
	}
}
