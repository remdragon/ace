from mypy_extensions import TypedDict
from typing import Any, Dict, IO, List, Optional as Opt, Union
from typing_extensions import Literal

botocore_client_Config = Any

class SynthesizedSpeech( TypedDict ):
	AudioStream: IO[bytes]
	ContentType: str
	RequestCharacters: int

class Client:
	def synthesize_speech( self, *,
		OutputFormat: Literal['json','mp3','ogg_vorbis','pcm'],
		Text: str,
		VoiceId: Literal['Aditi','Amy','Astrid','Bianca','Brian','Camila','Carla','Carmen','Celine','Chantal','Conchita','Cristiano','Dora','Emma','Enrique','Ewa','Filiz','Gabrielle','Geraint','Giorgio','Gwyneth','Hans','Ines','Ivy','Jacek','Jan','Joanna','Joey','Justin','Karl','Kendra','Kevin','Kimberly','Lea','Liv','Lotte','Lucia','Lupe','Mads','Maja','Marlene','Mathieu','Matthew','Maxim','Mia','Miguel','Mizuki','Naja','Nicole','Olivia','Penelope','Raveena','Ricardo','Ruben','Russell','Salli','Seoyeon','Takumi','Tatyana','Vicki','Vitoria','Zeina','Zhiyu','Aria','Ayanda','Arlet','Hannah','Arthur','Daniel','Liam','Pedro','Kajal'],
		Engine: Literal['standard','neural'] = 'standard',
		LanguageCode: Literal['arb','cmn-CN','cy-GB','da-DK','de-DE','en-AU','en-GB','en-GB-WLS','en-IN','en-US','es-ES','es-MX','es-US','fr-CA','fr-FR','is-IS','it-IT','ja-JP','hi-IN','ko-KR','nb-NO','nl-NL','pl-PL','pt-BR','pt-PT','ro-RO','ru-RU','sv-SE','tr-TR','en-NZ','en-ZA','ca-ES','de-AT'] = ...,
		LexiconNames: List[str] = ...,
		SampleRate: Literal['8000','16000','22050','24000'] = ...,
		SpeechMarkTypes: List[str] = ...,
		TextType: Literal['ssml','text'] = 'text',
	) -> SynthesizedSpeech:
		...

def client(
	service_name: str,
	region_name: Opt[str] = ...,
	api_version: Opt[str] = ...,
	use_ssl: bool = ...,
	verify: Opt[Union[bool,str]] = ...,
	endpoint_url: Opt[str] = ...,
	aws_access_key_id: Opt[str] = ...,
	aws_secret_access_key: Opt[str] = ...,
	aws_session_token: Opt[str] = ...,
	config: Opt[botocore_client_Config] = ...,
) -> Client:
	...
