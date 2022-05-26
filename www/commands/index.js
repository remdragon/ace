import UINode from './UINode.js'
import AcdCallAdd from './acd_call_add.js'; export{ AcdCallAdd }
import AcdCallGate from './acd_call_gate.js'; export{ AcdCallGate }
import AcdCallUnGate from './acd_call_ungate.js'; export{ AcdCallUnGate }
import Answer from './answer.js'; export{ Answer }
import Bridge from './bridge.js'; export{ Bridge }
import Email from './email.js'; export{ Email }
import GoTo from './goto.js'; export{ GoTo }
import Greeting from './greeting.js'; export{ Greeting }
import Hangup from './hangup.js'; export{ Hangup }
import IfNum from './ifnum.js'; export{ IfNum }
import IfStr from './ifstr.js'; export{ IfStr }
import IVR from './ivr.js'; export{ IVR }
import Label from './label.js'; export{ Label }
import Log from './log.js'; export{ Log }
import Lua from './lua.js'; export{ Lua }
import MOH from './moh.js'; export{ MOH }
import PAGD from './pagd.js'; export{ PAGD }
import Playback from './playback.js'; export{ Playback }
import PlayDTMF from './play_dtmf.js'; export{ PlayDTMF }
import PlayEmerg from './playemerg.js'; export{ PlayEmerg }
import PlayEstHold from './playesthold.js'; export{ PlayEstHold }
import PreAnnounce from './preannounce.js'; export{ PreAnnounce }
import PlayTTS from './playtts.js'; export{ PlayTTS }
import PreAnswer from './preanswer.js'; export{ PreAnswer }
import Repeat from './repeat.js'; export{ Repeat }
import Ring from './ring.js'; export{ Ring }
import Route from './route.js'; export{ Route }
import RxFax from './rxfax.js'; export{ RxFax }
import Select from './select.js'; export{ Select }
import SetMOH from './setmoh.js'; export{ SetMOH }
import SetNode from './set.js'; export{ SetNode }
import Silence from './silence.js'; export{ Silence }
import SMS from './sms.js'; export{ SMS }
import Throttle from './throttle.js'; export{ Throttle }
import TOD from './tod.js'; export{ TOD }
import Tone from './tone.js'; export{ Tone }
import Transfer from './transfer.js'; export{ Transfer }
import Translate from './translate.js'; export{ Translate }
import VoiceDeliver from './voice_deliver.js'; export{ VoiceDeliver }
import Voicemail from './voicemail.js'; export{ Voicemail }
import Wait from './wait.js'; export{ Wait }

let all_commands =
	[ AcdCallAdd
	, AcdCallGate
	, AcdCallUnGate
	, Answer
	, Bridge
	, Email
	, GoTo
	, Greeting
	, Hangup
	, IfNum
	, IfStr
	, IVR
	, Label
	, Log
	, Lua
	, MOH
	, PAGD
	, Playback
	, PlayDTMF
	, PlayEmerg
	, PlayEstHold
	, PreAnnounce
	, PlayTTS
	, PreAnswer
	, Repeat
	, Ring
	, Route
	, RxFax
	, Select
	, SetNode
	, SetMOH
	, Silence
	, SMS
	, Throttle
	, TOD
	, Tone
	, Transfer
	, Translate
	, VoiceDeliver
	, Voicemail
	, Wait
	]

const NODE_TYPES = {}
all_commands.map( NodeType => {
	NODE_TYPES[NodeType.command] = NodeType
})
UINode.NODE_TYPES = NODE_TYPES

export default NODE_TYPES
