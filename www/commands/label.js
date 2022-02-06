import UINode from './UINode.js'

export default class Label extends UINode {
	static icon = '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'Label'
	static command = 'label'
	
	help = 'A possible destination for GoTo command'
	get label()
	{
		return 'Label ' + ( this.name || '(unnamed)' )
	}
	
	uuid//: string
	
	fields = [
		{
			key: 'name',
			label: 'Name: ',
		}
	]
	
	createElement({
		isSubtree = false,
		data = { branches: {} },
		NODE_TYPES,
	}) {
		this.uuid = data.uuid || crypto.randomUUID()
		
		super.createElement({
			isSubtree,
			data,
			NODE_TYPES,
		})
	}
	
	getJson()
	{
		const sup = super.getJson()
		
		return {
			...sup,
			uuid: this.uuid,
		}
	}
}
