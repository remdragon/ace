import UINode from './UINode.js'

export default class Label extends UINode {
	static icon = '/media/streamline/type-cursor-1.png'
	static context_menu_name = 'Label'
	static command = 'label'
	
	help = 'A possible destination for GoTo command'
	get label()
	{
		return 'Label ' + ( this.name ?? '' )
	}
	
	uuid//: string
	
	fields = [{
		key: 'name',
		label: 'Name:',
		tooltip: 'This is for documentation purposes only',
	}]
	
	createElement({
		isSubtree = false,
		data = {},
	}) {
		this.uuid = data.uuid || crypto.randomUUID()
		
		super.createElement({
			isSubtree,
			data,
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
