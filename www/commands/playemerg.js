import UINode from './UINode.js';

export default class PlayEmerg extends UINode {
  static icon = '/media/streamline/music-note-2.png';
	static context_menu_name = 'Play ER Greeting?'
  static command = 'playemerg';

  help = 'No help is available for this node type, yet';
  label = 'PlayEmerg';
}
