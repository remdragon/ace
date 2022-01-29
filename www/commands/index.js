import Hangup from './hangup.js'; export { Hangup }
import AcdCallAdd from './acd_call_add.js'; export { AcdCallAdd }
import AcdCallGate from './acd_call_gate.js'; export { AcdCallGate }
import AcdCallUnGate from './acd_call_ungate.js'; export { AcdCallUnGate }
import Answer from './answer.js'; export { Answer }
import IfNode from './ifnode.js'; export { IfNode }
import PlayEmerg from './playemerg.js'; export { PlayEmerg }
import PlayEstHold from './playesthold.js'; export { PlayEstHold }
import PlayMOH from './playmoh.js'; export { PlayMOH }
import PlayPreAnnounce from './playpreannounce.js'; export { PlayPreAnnounce }
import Ring from './ring.js'; export { Ring }
import Preanswer from './preanswer.js'; export { Preanswer }
import Repeat from './repeat.js'; export { Repeat }
import SetNode from './set.js'; export { SetNode }
import Setmoh from './setmoh.js'; export { Setmoh }
import Translate from './translate.js'; export { Translate }
import IVR from './ivr.js'; export { IVR }
import Select from './select.js'; export { Select }

const NODE_TYPES = {
	acd_call_add: AcdCallAdd,
	acd_call_gate: AcdCallGate,
	acd_call_ungate: AcdCallUnGate,
	answer: Answer,
	hangup: Hangup,
	if: IfNode,
	playemerg: PlayEmerg,
	playesthold: PlayEstHold,
	playmoh: PlayMOH,
	playpreannounce: PlayPreAnnounce,
	preanswer: Preanswer,
	repeat: Repeat,
	ring: Ring,
	setNode: SetNode,
	setmoh: Setmoh,
	translate: Translate,
	ivr: IVR,
	select: Select
}

export default NODE_TYPES
