import ajax from './ajax.js'
import context_menu from '/editor/context-menu.js'

(function() {
	//var pilot_id = window.location.pathname.split ( '/' ).slice ( -1 )[0]
	//console.log ( pilot_id )
	
	var pilot_data = null
	var tree = null
	let div_help = null
	
	function on_pilot_data(data) {
		pilot_data = data
		if (tree !== null) {
			console.log('on_pilot_data calling main()')
			main()
		}
		else
		{
			console.log('on_pilot_data not calling main() - tree not set yet')
		}
	}
	
	var url = location.href
	var headers = {Accept: 'application/json', 'cache-control': 'no-cache'}
	var body = null
	console.log(url)
	ajax('GET', url, headers, body, on_pilot_data)
	
	function newElement(tag, attributes) {
		var el = document.createElement(tag)
		for (var key in attributes) {
			if (attributes.hasOwnProperty(key)) el.setAttribute(key, attributes[key])
		}
		return el
	}
	
	//Tree Context Menu Structure
	/*var context_menu = {
		context1: {
			elements: [
				{
					text: 'Node Actions',
					icon: '/aimara/images/blue_key.png',
					action: function(node) {},
					submenu: {
						elements: [
							{
								text: 'Toggle Node',
								icon: '/aimara/images/leaf.png',
								action: function(node) {
									node.toggleNode()
								},
							},
							{
								text: 'Expand Node',
								icon: '/aimara/images/leaf.png',
								action: function(node) {
									node.expandNode()
								},
							},
							{
								text: 'Collapse Node',
								icon: '/aimara/images/leaf.png',
								action: function(node) {
									node.collapseNode()
								},
							},
							{
								text: 'Expand Subtree',
								icon: '/aimara/images/tree.png',
								action: function(node) {
									node.expandSubtree()
								},
							},
							{
								text: 'Collapse Subtree',
								icon: '/aimara/images/tree.png',
								action: function(node) {
									node.collapseSubtree()
								},
							},
							{
								text: 'Delete Node',
								icon: '/aimara/images/delete.png',
								action: function(node) {
									node.removeNode()
								},
							},
						],
					},
				},
				{
					text: 'Child Actions',
					icon: '/aimara/images/blue_key.png',
					action: function(node) {},
					submenu: {
						elements: [
							{
								text: 'Create Child Node',
								icon: '/aimara/images/add1.png',
								action: function(node) {
									node.createChildNode(
										'Created',
										false,
										'/aimara/images/folder.png',
										null,
										'context1',
									)
								},
							},
							{
								text: 'Delete Child Nodes',
								icon: '/aimara/images/delete.png',
								action: function(node) {
									node.removeChildNodes()
								},
							},
						],
					},
				},
			],
		},
	}*/
	
	function nbsp() {
		var el = document.createElement('span')
		el.innerHTML = '&nbsp;'
		return el
	}
	
	function node_base(parent, label, icon) {
		//console.log ( [ label, parent ] )
		/*if ( parent == tree )
			return parent.createNode ( label, true, icon, null, null, 'context1' )
		else*/
		return parent.createChildNode(label, true, icon, null, 'context1')
	}
	
	function node_pre_answer(parent) {
		var node = node_base(
			parent,
			'pre_answer',
			'/media/streamline/phone-actions-ring.png',
		)
		node.selected = function(node) {
			div_help.innerHTML =
				"`pre-answer` is a condition where the call isn't answered yet,<br/>but you can play audio to the caller instead of ring tone<br/>"
		}
		return node
	}
	
	function node_set(parent, name, value) {
		var node = node_base(parent, 'set', '/media/streamline/type-cursor-1.png')
		var input_name = newElement('input', {
			type: 'text',
			value: name,
		})
		node.elementSpan.appendChild(document.createTextNode(' '))
		node.elementSpan.appendChild(input_name)
		node.elementSpan.appendChild(document.createTextNode(' value '))
		var input_value = newElement('input', {
			type: 'text',
			value: value,
		})
		node.elementSpan.appendChild(input_value)
		node.tag = {
			name: input_name,
			value: input_value,
		}
		node.selected = function(node) {
			div_help.innerHTML = 'Saves information in a channel variable<br/>'
		}
		return node
	}
	
	function node_answer(parent) {
		var node = node_base(
			parent,
			'answer',
			'/media/streamline/phone-actions-receive.png',
		)
		node.selected = function(node) {
			div_help.innerHTML =
				'Transitions the call to an ANSWERED state, if not already answered.'
		}
		return node
	}
	
	function node_moh(parent, moh) {
		return node_base(parent, moh, '/media/streamline/music-note-2.png')
	}
	
	function node_if(parent, condition, true_data, false_data) {
		var ifnode = node_base(
			parent,
			'if: ' + condition,
			'/media/streamline/road-sign-look-both-ways-1.png',
		)
		var true_node = node_base(ifnode, 'true', null)
		node_array(true_node, true_data)
		var false_node = node_base(ifnode, 'false', null)
		node_array(false_node, false_data)
		return ifnode
	}
	
	function node_hangup(parent) {
		return node_base(
			parent,
			'hangup',
			'/media/streamline/phone-actions-remove.png',
		)
	}
	
	function node_acd(parent, gate, priority, offset) {
		return node_base(
			parent,
			'acd gate=`' +
				gate +
				'`, priority=`' +
				priority +
				'`, offset=`' +
				offset +
				'`',
			'media/streamline/headphones-customer-support-human-1.png',
		)
	}
	
	function node_repeat(parent, body) {
		var node = node_base(parent, 'repeat', '/media/streamline/robot-1.png')
		node_array(node, body)
		return node
	}
	
	function node_translate(parent, table, variable, hit_data, miss_data) {
		var tran_node = node_base(
			parent,
			'translate table ',
			'/media/streamline/database-2.png',
		)
		
		var el_table = newElement('input', {
			type: 'text',
			value: table,
		})
		tran_node.elementSpan.appendChild(el_table)
		tran_node.elementSpan.appendChild(document.createTextNode(' variable '))
		var el_variable = newElement('input', {
			type: 'text',
			value: variable,
		})
		tran_node.elementSpan.appendChild(el_variable)
		tran_node.tag = {
			table: el_table,
			variable: el_variable,
		}
		tran_node.selected = function(node) {
			div_help.innerHTML =
				'Lookup info in a translation table and set any specified channel variables'
		}
		
		var hit_node = node_base(tran_node, 'hit', null)
		node_array(hit_node, hit_data)
		var miss_node = node_base(tran_node, 'miss', null)
		node_array(miss_node, miss_data)
		
		return tran_node
	}
	
	function node_placeholder(parent, text) {
		return node_base(
			parent,
			text,
			'/media/streamline/professions-man-construction-1.png',
		)
	}
	
	//var div_log = document.getElementById ( 'div_log' )
	
	function node_array(base, data)
	{
		if (data !== null && typeof data != 'undefined')
		{
			for (var i = 0; i < data.length; i++)
			{
				var item = data[i]
				//console.log ( i, item )
				var command = item.command
				if (command == 'preanswer') node_pre_answer(base)
				else if (command == 'set') node_set(base, item.name, item.value)
				else if (command == 'answer') node_answer(base)
				else if (command == 'setmoh') node_moh(base, item.value)
				else if (command == 'if')
					node_if(base, item.condition, item.true, item.false)
				else if (command == 'hangup') node_hangup(base)
				else if (command == 'repeat') node_repeat(base, item.body)
				else if (command == 'translate')
					node_translate(base, item.table, item.variable, item.hit, item.miss)
				else {
					node_placeholder(base, command)
					console.log('invalid command `' + command + '`')
				}
			}
		}
	}
	
	/*function expand_all() {
		tree.expandTree()
	}
	
	function clear_log() {
		document.getElementById('div_log').innerHTML = ''
	}
	
	function collapse_all() {
		tree.collapseTree()
	}*/
	
	function DOMContentLoaded() {
		//Creating the tree
		if (pilot_data !== null) {
			console.log('DOMContentLoaded calling main()')
			main()
		} else
			console.log(
				'DOMContentLoaded not calling main() - pilot_data not set yet',
			)
	}
	document.addEventListener('DOMContentLoaded', DOMContentLoaded)
	
	function main() {
		console.log('main starting')
		tree = createTree('div_tree', 'white', context_menu)
		
		let pilot_name = pilot_data['name']
		let pilot_nodes = pilot_data['nodes']
		
		document.title = pilot_name
		var root = tree.createNode(
			pilot_name,
			true,
			'/media/streamline/kindle.png',
			null,
			null,
			'context1',
		)
			
		//Setting custom events
		tree.nodeBeforeOpenEvent = function(node) {
			console.log(node.text + ': Before expand event')
		}
		
		tree.nodeAfterOpenEvent = function(node) {
			console.log(node.text + ': After expand event')
		}
		
		tree.nodeBeforeCloseEvent = function(node) {
			console.log(node.text + ': Before collapse event')
		}
		
		div_help = document.getElementById('div_help')
		tree.nodeSelectedEvent = function(node) {
			console.log(node.text + ': Selected event')
			if (typeof node.selected != 'undefined' && node.selected !== null)
				node.selected(node)
			else div_help.innerHTML = 'No help is available for this node type, yet'
		}
		
		//Rendering the tree
		tree.drawTree()
		
		node_array(root, pilot_nodes)
	}
})()
