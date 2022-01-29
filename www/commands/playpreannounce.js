import UINode from './UINode.js';

export default class PlayPreAnnounce extends UINode {
	// TODO FIXME: maybe get rid of this since it can be dealt with via Playback
	static icon = '/media/streamline/music-note-2.png';
	static context_menu_name = 'Play Pre-Announce'
	static command = 'preannounce';
	
	help = 'No help is available for this node type, yet';
	label = 'PreAnnounce';
}
