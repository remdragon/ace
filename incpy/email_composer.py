import base64
import email
from email.mime.text import MIMEText
#from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
#from email.mime.nonmultipart import MIMENonMultipart
from io import BytesIO
import quopri
from typing import Any, IO, List, Optional as Opt, Sequence as Seq, Tuple, Union


class Email_composer:
	_from: Opt[str] = None
	text: Opt[str] = None
	html: Opt[str] = None
	subject: Opt[str] = None
	
	def __init__( self ) -> None:
		self._to: List[str] = []
		self._cc: List[str] = []
		#self._bcc: List[str] = []
		self._atts: List[Tuple[bytes, str, Opt[str]]] = []
	
	@property
	def from_( self ) -> Opt[str]:
		return self._from
	
	@from_.setter
	def from_( self, eml: str ) -> None:
		self._from = eml
	
	@property
	def to( self ) -> Seq[str]:
		return self._to
	
	@to.setter
	def to( self, emls: Union[str,Seq[str]] ) -> None:
		self._to = self._eml_list( emls )
	
	def add_to( self, emls: Union[str,Seq[str]] ) -> None:
		self._to += self._eml_list( emls )
	
	@property
	def cc( self ) -> Seq[str]:
		return self._cc
	
	@cc.setter
	def cc( self, emls: Union[str,Seq[str]] ) -> None:
		self._cc = self._eml_list( emls )
	
	def add_cc( self, emls: Union[str,Seq[str]] ) -> None:
		self._cc += self._eml_list( emls )
	
	#@property
	#def bcc( self ):
	#	return self._bcc
	#@bcc.setter
	#def bcc( self, emls ):
	#	self._bcc = self._eml_list(emls)
	#def add_bcc( self, emls ):
	#	self._bcc += self._eml_list(emls)
	
	def _eml_list( self, *args: Union[str,Seq[str]] ) -> List[str]:
		ar: List[str] = []
		for arg in args:
			if isinstance( arg, str ):
				ar += [ e for e in arg.replace( ',', ';' ).split( ';' ) if e ]
			elif isinstance( arg, Seq ):
				ar += self._eml_list( *arg )
			else:
				assert arg is not None, f'unsupported arg {arg!r}'
		return ar
	
	def attach( self, fp: IO[bytes], filename: str = '', content_type: Opt[str] = None ) -> None:
		# TODO FIXME: support `<img src="cid:some-image-cid" alt="img" />` (https://mailtrap.io/blog/embedding-images-in-html-email-have-the-rules-changed/)
		self._atts.append(( fp.read(), filename, content_type ))
	
	def as_bytes( self ) -> bytes:
		# text and html bodies are mime/text. If you have both, they must both
		# be in a mime/multipart/alternative.
		# if there are attachments, those must be stored in mime/multipart/mixed
		# of which the mime/text or mime/multipart/alternative must be another attachment
		# whoever ends up being the top mime envelope is where the from/to/subject/etc gets set
		msg: Union[None,MIMEText,MIMEMultipart] = None
		msg_txt = None
		msg_htm = None
		if self.text:
			if isinstance( self.text, bytes ):
				self.text = self.text.decode( 'us-ascii' )
			msg_txt = MIMEText( self.text, 'plain' )
			msg = msg_txt
		if self.html:
			if isinstance( self.html, bytes ):
				self.html = self.html.decode( 'us-ascii' )
			msg_htm = MIMEText( self.html, 'html' )
			if msg_txt is not None:
				msg = MIMEMultipart( 'alternative' )
				msg.attach( msg_txt )
				msg.attach( msg_htm )
			else:
				msg = msg_htm
		if msg is None:
			raise Exception( 'email must have a text and/or html body' )
		
		if len( self._atts ):
			mixed = MIMEMultipart( 'mixed' )
			mixed.attach( msg )
			msg = mixed
		for content, filename, content_type in self._atts:
			att = email.message.Message()
			if not content_type:
				content_type = 'application/octet-stream'
			if filename:
				att['Content-Type'] = f'{content_type}; name="{filename}"'
				att['Content-Disposition'] = f'attachment; filename="{filename}"'
			else:
				att['Content-Type'] = content_type
				att['Content-Disposition'] = 'attachment'
			# choose encoding based on which one will generate a smaller email
			b = base64.encodebytes( content )
			q = quopri.encodestring( content )
			if len(b) < len(q):
				att['Content-Transfer-Encoding'] = 'base64'
				att.set_payload(b)
			else:
				att['Content-Transfer-Encoding'] = 'quoted-printable'
				att.set_payload(q)
			msg.attach(att)
		
		# now that we've finished constructing all the mime wrappers, it's safe
		# to set the top-level headers:
		assert self._from is not None
		msg['From'] = self._from
		rcpts = False
		if self._to:
			msg['To'] = ', '.join( self._to )
			rcpts = True
		if self._cc:
			msg['Cc'] = ', '.join( self._cc )
			rcpts = True
		if not rcpts:
			raise Exception( 'email must have TO or CC' )
		#if self._bcc:
		#	msg['Bcc'] = ', '.join( self._bcc ) # DON'T DO THIS!!!
		msg['Date'] = email.utils.formatdate( localtime = True )
		if self.subject is None:
			raise Exception( 'email must have a subject' )
		msg['Subject'] = self.subject
		return msg.as_bytes()

if __name__=='__main__':
	x = Email_composer()
	x.from_ = 'from@from.com'
	x.to = 'to@to.com'
	x.subject = 'subjective'
	x.text = 'text body'
	x.html = 'html body'
	x.attach( BytesIO( b'Hello World' ), 'text-plain.txt', 'text/plain' )
	x.attach( BytesIO( b'Hello World' ), 'default.bin' )
	print( x.as_bytes().decode( 'us-ascii' ))
	