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
import MOH from './moh.js'; export{ MOH }
import Playback from './playback.js'; export{ Playback }
import PlayDTMF from './play_dtmf.js'; export{ PlayDTMF }
import PlayEmerg from './playemerg.js'; export{ PlayEmerg }
import PlayEstHold from './playesthold.js'; export{ PlayEstHold }
import PlayPreAnnounce from './playpreannounce.js'; export{ PlayPreAnnounce }
import PlayTTS from './playtts.js'; export{ PlayTTS }
import PreAnswer from './preanswer.js'; export{ PreAnswer }
import Repeat from './repeat.js'; export{ Repeat }
import Ring from './ring.js'; export{ Ring }
import Route from './route.js'; export{ Route }
import Select from './select.js'; export{ Select }
import SetMOH from './setmoh.js'; export{ SetMOH }
import SetNode from './set.js'; export{ SetNode }
import Silence from './silence.js'; export{ Silence }
import TOD from './tod.js'; export{ TOD }
import Tone from './tone.js'; export{ Tone }
import Transfer from './transfer.js'; export{ Transfer }
import Translate from './translate.js'; export{ Translate }
import Voicemail from './voicemail.js'; export{ Voicemail }
import Wait from './wait.js'; export{ Wait }

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
	moh: MOH,
	playpreannounce: PlayPreAnnounce,
	playtts: PlayTTS,
	preanswer: PreAnswer,
	repeat: Repeat,
	ring: Ring,
	route: Route,
	select: Select,
	setNode: SetNode,
	setmoh: SetMOH,
	silence: Silence,
	tod: TOD,
	tone: Tone,
	transfer: Transfer,
	translate: Translate,
	voicemail: Voicemail,
	wait: Wait,
}

export default NODE_TYPES
