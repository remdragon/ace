import AcdCallAdd from './acd_call_add.js'; export{ AcdCallAdd }
import AcdCallGate from './acd_call_gate.js'; export{ AcdCallGate }
import AcdCallUnGate from './acd_call_ungate.js'; export{ AcdCallUnGate }
import Answer from './answer.js'; export{ Answer }
import Bridge from './bridge.js'; export{ Bridge }
import GoTo from './goto.js'; export{ GoTo }
import Hangup from './hangup.js'; export{ Hangup }
import IfNum from './ifnum.js'; export{ IfNum }
import IfStr from './ifstr.js'; export{ IfStr }
import IVR from './ivr.js'; export{ IVR }
import Label from './label.js'; export{ Label }
import Playback from './playback.js'; export{ Playback }
import PlayDTMF from './play_dtmf.js'; export{ PlayDTMF }
import PlayEmerg from './playemerg.js'; export{ PlayEmerg }
import PlayEstHold from './playesthold.js'; export{ PlayEstHold }
import PlayMOH from './playmoh.js'; export{ PlayMOH }
import PlayPreAnnounce from './playpreannounce.js'; export{ PlayPreAnnounce }
import PreAnswer from './preanswer.js'; export{ PreAnswer }
import Repeat from './repeat.js'; export{ Repeat }
import Ring from './ring.js'; export{ Ring }
import Route from './route.js'; export{ Route }
import Select from './select.js'; export{ Select }
import SetMOH from './setmoh.js'; export{ SetMOH }
import SetNode from './set.js'; export{ SetNode }
import TOD from './tod.js'; export{ TOD }
import Transfer from './transfer.js'; export{ Transfer }
import Translate from './translate.js'; export{ Translate }
import Voicemail from './voicemail.js'; export{ Voicemail }

const NODE_TYPES = {
	acd_call_add: AcdCallAdd,
	acd_call_gate: AcdCallGate,
	acd_call_ungate: AcdCallUnGate,
	answer: Answer,
	bridge: Bridge,
	goto: GoTo,
	hangup: Hangup,
	ifnum: IfNum,
	ifstr: IfStr,
	ivr: IVR,
	label: Label,
	playback: Playback,
	play_dtmf: PlayDTMF,
	playemerg: PlayEmerg,
	playesthold: PlayEstHold,
	playmoh: PlayMOH,
	playpreannounce: PlayPreAnnounce,
	preanswer: PreAnswer,
	repeat: Repeat,
	ring: Ring,
	route: Route,
	select: Select,
	setNode: SetNode,
	setmoh: SetMOH,
	tod: TOD,
	transfer: Transfer,
	translate: Translate,
	voicemail: Voicemail,
}

export default NODE_TYPES
