#! /usr/bin/env python
from __future__ import annotations

'''SMTP/ESMTP client class.

This should follow RFC 821 (SMTP), RFC 1869 (ESMTP), RFC 2554 (SMTP
Authentication) and RFC 2487 (Secure SMTP over TLS).

Notes:

Please remember, when doing ESMTP, that the names of the SMTP service
extensions are NOT the same thing as the option keywords for the RCPT
and MAIL commands!

Example:

  >>> import smtplib2
  >>> s=smtplib2.SMTP("localhost")
  >>> print s.help()
  This is Sendmail version 8.8.4
  Topics:
	  HELO    EHLO    MAIL    RCPT    DATA
	  RSET    NOOP    QUIT    HELP    VRFY
	  EXPN    VERB    ETRN    DSN
  For more info use "HELP <topic>".
  To report bugs in the implementation send email to
	  sendmail-bugs@sendmail.org.
  For local information send email to Postmaster at your site.
  End of HELP info
  >>> s.putcmd("vrfy","someone@here")
  >>> s.getreply()
  (250, "Somebody OverHere <somebody@here.my.org>")
  >>> s.quit()
'''

# Author: The Dragon De Monsyne <dragondm@integral.org>
# ESMTP support, test code and doc fixes added by
#     Eric S. Raymond <esr@thyrsus.com>
# Better RFC 821 compliance (MAIL and RCPT, and CRLF in data)
#     by Carey Evans <c.evans@clear.net.nz>, for picky mail servers.
# RFC 2554 (authentication) support by Gerhard Haering <gerhard@bigfoot.de>.
#
# This was modified from the Python 1.5 library HTTP lib.
#
# This was further modified to remove set_debuglevel and replace it with the logging module

import base64
import email.utils
import hmac
import logging
import re
import socket
import sys
from typing import (
	BinaryIO, Callable, Dict, List, Optional as Opt, Sequence as Seq, Tuple,
	Union,
)

__all__ = [
	'SMTPException', 'SMTPServerDisconnected', 'SMTPResponseException',
	'SMTPSenderRefused', 'SMTPRecipientsRefused', 'SMTPDataError',
	'SMTPConnectError', 'SMTPHeloError', 'SMTPAuthenticationError',
	'quoteaddr', 'quotedata', 'SMTP',
]

logger = logging.getLogger ( __name__ )

AUTH_PLAIN = 'PLAIN'
AUTH_CRAM_MD5 = 'CRAM-MD5'
AUTH_LOGIN = 'LOGIN'

SMTP_PORT = 25
SMTP_SSL_PORT = 465
LMTP_PORT = 2003
CRLF = b'\r\n'
_MAXLINE = 8192 # more than 8 times larger than RFC 821, 4.5.3

OLDSTYLE_AUTH = re.compile ( r'auth=(.*)', re.I )


# Exception classes used by this module.
class SMTPException ( Exception ):
	"""Base class for all exceptions raised by this module."""

class SMTPServerDisconnected ( SMTPException ):
	"""Not connected to any SMTP server.

	This exception is raised when the server unexpectedly disconnects,
	or when an attempt is made to use the SMTP instance before
	connecting it to a server.
	"""

class SMTPResponseException ( SMTPException ):
	"""Base class for all exceptions that include an SMTP error code.

	These exceptions are generated in some instances when the SMTP
	server returns an error code.  The error code is stored in the
	`smtp_code' attribute of the error, and the `smtp_error' attribute
	is set to the error message.
	"""

	def __init__( self, code: int, msg: str ) -> None:
		self.smtp_code = code
		self.smtp_error = msg
		self.args = code, msg

class SMTPSenderRefused ( SMTPResponseException ):
	"""Sender address refused.

	In addition to the attributes set by on all SMTPResponseException
	exceptions, this sets `sender' to the string that the SMTP refused.
	"""

	def __init__ ( self, code: int, msg: str, sender: str ) -> None:
		self.smtp_code = code
		self.smtp_error = msg
		self.sender = sender
		self.args = code, msg, sender

class SMTPRecipientsRefused ( SMTPException ):
	"""All recipient addresses refused.

	The errors for each recipient are accessible through the attribute
	'recipients', which is a dictionary of exactly the same sort as
	SMTP.sendmail() returns.
	"""

	def __init__ ( self, recipients: Dict[str,Tuple[int,str]] ) -> None:
		self.recipients = recipients
		self.args = ( recipients, )


class SMTPDataError ( SMTPResponseException ):
	"""The SMTP server didn't accept the data."""

class SMTPConnectError ( SMTPResponseException ):
	"""Error during connection establishment."""

class SMTPHeloError ( SMTPResponseException ):
	"""The server refused our HELO reply."""

class SMTPAuthenticationError ( SMTPResponseException ):
	"""Authentication error.
	
	Most probably the server didn't accept the username/password
	combination provided.
	"""

def encode_base64 ( b: bytes ) -> bytes:
	encoded = base64.b64encode ( b )
	assert not b'\r' in encoded, f'invalid encoded (CR): {encoded!r}'
	assert not b'\n' in encoded, f'invalid encoded (LF): {encoded!r}'
	return encoded

def quoteaddr ( addr: str ) -> bytes:
	"""Quote a subset of the email addresses defined by RFC 821.
	
	Should be able to handle anything rfc822.parseaddr can handle.
	"""
	m: Opt[str] = None
	try:
		m = email.utils.parseaddr ( addr )[1]
	except AttributeError:
		pass
	if m is None:  # Indicates parse failure or AttributeError
		# something weird here.. punt -ddm
		return f'<{addr}>'.encode ( 'ascii', 'strict' )
	elif not m:
		# the sender wants an empty return address
		return b'<>'
	else:
		return f'<{m}>'.encode ( 'utf-8', 'strict' ) # TODO FIXME: I think utf-8 might be wrong here...

def _addr_only ( addrstring: str ) -> bytes:
	displayname, addr = email.utils.parseaddr ( addrstring )
	if ( displayname, addr ) == ( '', '' ):
		# parseaddr couldn't parse it, so use it as is.
		return addrstring.encode ( 'ascii', 'strict' )
	return addr.encode ( 'ascii', 'strict' )

_r_leading_dot = re.compile ( b'(?m)^\\.' )
_r_eol = re.compile ( b'(?:\\r\\n|\\n|\\r(?!\\n))' )
def quotedata ( data: bytes ) -> bytes:
	"""Quote data for email.
	
	Double leading '.', and change Unix newline '\\n', or Mac '\\r' into
	Internet CRLF end-of-line.
	"""
	assert isinstance ( data, bytes ), f'expected type(data)=bytes but got {data!r}'
	return _r_leading_dot.sub ( b'..', _r_eol.sub ( CRLF, data ) )


try:
	import ssl
except ImportError:
	_have_ssl = False
else:
	class SSLFakeFile:
		"""A fake file like object that really wraps a SSLObject.
		
		It only supports what is needed in smtplib2.
		"""
		def __init__ ( self, sslobj: ssl.SSLSocket ) -> None:
			self.sslobj = sslobj
		
		def readline ( self, size: Opt[int] = -1 ) -> bytes:
			if size is not None and size < 0:
				size = None
			buf = b''
			chr = None
			while chr != b'\n':
				if size is not None and len ( buf ) >= size:
					break
				chr = self.sslobj.read ( 1 )
				if not chr:
					break
				buf += chr
			return buf
		
		def close ( self ) -> None:
			pass
	
	_have_ssl = True

def encode_cram_md5 ( challenge: str, user: str, password: str ) -> bytes:
	passbytes: bytes = password.encode( 'utf-8' )
	challenge2: bytes = base64.decodebytes ( challenge.encode ( 'ascii', 'strict' ) )
	digest: bytes = hmac.HMAC ( passbytes, challenge2 ).hexdigest().encode ( 'ascii', 'strict' )
	response = b' '.join ( [ user.encode ( 'ascii', 'strict' ), digest ] )
	return encode_base64 ( response )

def encode_plain ( user: str, password: str ) -> bytes:
	return encode_base64 ( b'\0'.join ( [
		b'',
		user.encode ( 'ascii', 'strict' ),
		password.encode ( 'ascii', 'strict' ),
	] ) )

class SMTP:
	"""This class manages a connection to an SMTP or ESMTP server.
	SMTP Objects:
		SMTP objects have the following attributes:
			helo_resp
				This is the message given by the server in response to the
				most recent HELO command.
			
			ehlo_resp
				This is the message given by the server in response to the
				most recent EHLO command. This is usually multiline.
			
			does_esmtp
				This is a True value _after you do an EHLO command_, if the
				server supports ESMTP.
			
			esmtp_features
				This is a dictionary, which, if the server supports ESMTP,
				will _after you do an EHLO command_, contain the names of the
				SMTP service extensions this server supports, and their
				parameters (if any).
				
				Note, all extension names are mapped to lower case in the
				dictionary.
		
		See each method's docstrings for details.  In general, there is a
		method of the same name to perform each SMTP command.  There is also a
		method called 'sendmail' that will do an entire mail transaction.
		"""
	file: Opt[Union[BinaryIO,SSLFakeFile]] = None
	helo_resp = None
	ehlo_msg = b'ehlo'
	ehlo_resp = None
	does_esmtp = 0
	default_port = SMTP_PORT
	
	def __init__ ( self,
		host: str = '',
		port: int = 0,
		local_hostname: Opt[str] = None,
		timeout: Opt[Union[int,float]] = None,
	) -> None:
		"""Initialize a new instance.

		If specified, `host' is the name of the remote host to which to
		connect.  If specified, `port' specifies the port to which to connect.
		By default, smtplib2.SMTP_PORT is used.  If a host is specified the
		connect method is called, and if it returns anything other than a
		success code an SMTPConnectError is raised.  If specified,
		`local_hostname` is used as the FQDN of the local host for the
		HELO/EHLO command.  Otherwise, the local hostname is found using
		socket.getfqdn().
		
		"""
		self.timeout = timeout
		self.esmtp_features: Dict[str,str] = {}
		if host:
			code, msg = self.connect ( host, port )
			if code != 220:
				self.close()
				raise SMTPConnectError ( code, msg )
		if local_hostname is not None:
			self.local_hostname = local_hostname
		else:
			# RFC 2821 says we should use the fqdn in the EHLO/HELO verb, and
			# if that can't be calculated, that we should use a domain literal
			# instead (essentially an encoded IP address like [A.B.C.D]).
			fqdn: str = socket.getfqdn()
			if '.' in fqdn:
				self.local_hostname = fqdn
			else:
				# We can't find an fqdn hostname, so use a domain literal
				addr: str = '127.0.0.1'
				try:
					addr = socket.gethostbyname ( socket.gethostname() )
				except socket.gaierror:
					pass
				self.local_hostname = f'[{addr}]'
	
	def _get_socket ( self,
		host: str,
		port: int,
		timeout: Opt[Union[int,float]],
	) -> socket.socket:
		# This makes it simpler for SMTP_SSL to use the SMTP connect code
		# and just alter the socket connection bit.
		log = logger.getChild ( 'SMTP._get_socket' )
		log.info ( 'connecting to host %r port %r', host, port )
		return socket.create_connection ( ( host, port ),
			timeout or getattr ( socket, '_GLOBAL_DEFAULT_TIMEOUT' )
		)
	
	def connect ( self, host: str = 'localhost', port: int = 0 ) -> Tuple[int,str]:
		"""Connect to a host on a given port.
		
		If the hostname ends with a colon (`:') followed by a number, and
		there is no port specified, that suffix will be stripped off and the
		number interpreted as the port number to use.
		
		Note: This method is automatically invoked by __init__, if a host is
		specified during instantiation.
		
		"""
		#log = logger.getChild ( 'SMTP.connect' )
		if not port and ( host.find ( ':' ) == host.rfind ( ':' ) ):
			i = host.rfind ( ':' )
			if i >= 0:
				host, port_ = host[:i], host[i + 1:]
				try:
					port = int ( port_ )
				except ValueError as e:
					raise socket.error( 'non-numeric port' ).with_traceback( e.__traceback__ ) from None
		if not port:
			port = self.default_port
		self.sock = self._get_socket ( host, port, self.timeout )
		code, msg = self.getreply()
		return code, msg
	
	def send ( self, content: bytes, *, sensitive: bool = False ) -> None:
		"""Send `content' to the server."""
		log = logger.getChild ( 'SMTP.send' )
		loglevel = logging.DEBUG if sensitive else logging.INFO
		log.log ( loglevel, 'C>%r', content )
		if getattr ( self, 'sock', None ):
			try:
				self.sock.sendall ( content )
			except socket.error as e:
				self.close()
				raise SMTPServerDisconnected( repr( e )).with_traceback( e.__traceback__ ) from None
		else:
			raise SMTPServerDisconnected ( 'please run connect() first' )
	
	def putcmd ( self, cmd: bytes, args: bytes = b'', sensitive: bool = False ) -> None:
		"""Send a command to the server."""
		assert isinstance ( cmd, bytes ), f'expected type(cmd)=bytes but got {cmd!r}'
		if args == b"":
			content = b''.join ( [ cmd, CRLF ] )
		else:
			content = b''.join ( [ cmd, b' ', args, CRLF ] )
		self.send ( content, sensitive = sensitive )
	
	def getreply ( self ) -> Tuple[int,str]:
		"""Get a reply from the server.
		
		Returns a tuple consisting of:
		
		  - server response code (e.g. '250', or such, if all goes well)
			Note: returns -1 if it can't read response code.
		
		  - server response string corresponding to response code (multiline
			responses are converted to a single, multiline string).
		
		Raises SMTPServerDisconnected if end-of-file is reached.
		"""
		log = logger.getChild ( 'SMTP.getreply' )
		resp: List[str] = []
		if self.file is None:
			self.file = self.sock.makefile ( 'rb' )
		while 1:
			try:
				line: str = self.file.readline ( _MAXLINE + 1 ).decode ( 'ascii' )
			except socket.error as e:
				self.close()
				raise SMTPServerDisconnected ( f'Connection unexpectedly failed: {e!r}' )
			if not line:
				self.close()
				raise SMTPServerDisconnected ( 'Connection unexpectedly closed' )
			log.info ( 'S>%s', line.rstrip( '\r\n' ))
			if len ( line ) > _MAXLINE:
				raise SMTPResponseException ( 500, 'Line too long.' )
			resp.append ( line[4:].strip() )
			code_ = line[:3]
			# Check that the error code is syntactically correct.
			# Don't attempt to read a continuation line if it is broken.
			try:
				code = int ( code_ )
			except ValueError:
				log.warning ( 'server sent invalid code=%r', code_ )
				code = -1
				break
			# Check if multiline response.
			if line[3:4] != '-':
				break
		
		msg = '\n'.join ( resp )
		log.debug ( 'reply code=%r msg=%r', code, msg ) # this is debug because it's redundant to logging above
		return code, msg
	
	def docmd ( self, cmd: bytes, args: bytes = b'', *, sensitive: bool = False ) -> Tuple[int,str]:
		"""Send a command, and return its response code."""
		self.putcmd ( cmd, args, sensitive = sensitive )
		return self.getreply()
	
	# std smtp commands
	def helo ( self, name: str = '' ) -> Tuple[int,str]:
		"""SMTP 'helo' command.
		Hostname to send for this command defaults to the FQDN of the local
		host.
		"""
		self.putcmd ( b'helo', ( name or self.local_hostname ).encode ( 'ascii', 'strict' ) )
		code, msg = self.getreply()
		self.helo_resp = msg
		return code, msg
	
	def ehlo ( self, name: str = '' ) -> Tuple[int,str]:
		""" SMTP 'ehlo' command.
		Hostname to send for this command defaults to the FQDN of the local
		host.
		"""
		self.esmtp_features = {}
		self.putcmd ( self.ehlo_msg, ( name or self.local_hostname ).encode ( 'ascii', 'strict' ) )
		code, msg = self.getreply()
		# According to RFC1869 some (badly written)
		# MTA's will disconnect on an ehlo. Toss an exception if
		# that happens -ddm
		if code == -1 and len ( msg ) == 0:
			self.close()
			raise SMTPServerDisconnected ( 'Server not connected' )
		self.ehlo_resp = msg
		if code != 250:
			return code, msg
		self.does_esmtp = 1
		#parse the ehlo response -ddm
		resp = self.ehlo_resp.split ( '\n' )
		del resp[0]
		for each in resp:
			# To be able to communicate with as many SMTP servers as possible,
			# we have to take the old-style auth advertisement into account,
			# because:
			# 1) Else our SMTP feature parser gets confused.
			# 2) There are some servers that only advertise the auth methods we
			#    support using the old style.
			auth_match = OLDSTYLE_AUTH.match ( each )
			if auth_match:
				# This doesn't remove duplicates, but that's no problem
				auth = self.esmtp_features.get ( 'auth', '' )
				grp = auth_match.group(0)[0]
				self.esmtp_features['auth'] = f'{auth} {grp}'
				continue
			
			# RFC 1869 requires a space between ehlo keyword and parameters.
			# It's actually stricter, in that only spaces are allowed between
			# parameters, but were not going to check for that here.  Note
			# that the space isn't present if there are no parameters.
			m = re.match ( r'(?P<feature>[A-Za-z0-9][A-Za-z0-9\-]*) ?', each )
			if m:
				feature = m.group ( 'feature' ).lower()
				params = m.string[m.end ( 'feature' ):].strip()
				if feature == 'auth':
					esmtp_feature = self.esmtp_features.get ( feature, '' )
					self.esmtp_features[feature] = f'{esmtp_feature} {params}'
				else:
					self.esmtp_features[feature] = params
		return code, msg
	
	def has_extn ( self, opt: str ) -> bool:
		"""Does the server support a given SMTP service extension?"""
		return opt.lower() in self.esmtp_features
	
	def help ( self, args: str = '' ) -> str:
		"""SMTP 'HELP' command.
		Returns help text from server."""
		self.putcmd ( b'HELP', args.encode ( 'ascii', 'strict' ) )
		return self.getreply()[1]
	
	def rset ( self ) -> Tuple[int,str]:
		"""SMTP 'RSET' command -- resets session."""
		return self.docmd ( b'RSET' )
	
	def noop ( self ) -> Tuple[int,str]:
		"""SMTP 'NOOP' command -- doesn't do anything :>"""
		return self.docmd ( b'NOOP' )
	
	def mail ( self, sender: str, options: List[bytes] = [] ) -> Tuple[int,str]:
		"""SMTP 'MAIL' command -- begins mail xfer session."""
		optionlist = b''
		if options and self.does_esmtp:
			optionlist = b' ' + b' '.join ( options )
		self.putcmd ( b'MAIL', b''.join ( [ b'FROM:', quoteaddr ( sender ), optionlist ] ) )
		return self.getreply()
	
	def rcpt ( self, recip: str, options: List[bytes] = [] ) -> Tuple[int,str]:
		"""SMTP 'RCPT' command -- indicates 1 recipient for this mail."""
		optionlist = b''
		if options and self.does_esmtp:
			optionlist = b' ' + b' '.join ( options )
		self.putcmd ( b'RCPT', b''.join ( [ b'TO:', quoteaddr ( recip ), optionlist ] ) )
		return self.getreply()
	
	def data ( self, msg: bytes ) -> Tuple[int,str]:
		"""SMTP 'DATA' command -- sends message data to server.
		
		Automatically quotes lines beginning with a period per rfc821.
		Raises SMTPDataError if there is an unexpected reply to the
		DATA command; the return value from this method is the final
		response code received when the all data is sent.
		"""
		log = logger.getChild ( 'SMTP.data' )
		self.putcmd ( b'DATA' )
		code, repl = self.getreply()
		if code != 354:
			log.warning ( 'initial response: %r %s', code, repl )
			raise SMTPDataError ( code, repl )
		else:
			log.info ( 'initial response: %r %s', code, repl )
			q = quotedata ( msg )
			if q[-2:] != CRLF:
				q = q + CRLF
			q = q + b'.' + CRLF
			self.send ( q, sensitive = True )
			code, resp = self.getreply()
			loglevel = logging.WARNING if code >= 400 else logging.INFO
			log.log ( loglevel, 'final response: %r %s', code, resp )
			return code, resp
	
	def verify ( self, address: str ) -> Tuple[int,str]:
		"""SMTP 'verify' command -- checks for address validity."""
		self.putcmd ( b'VRFY', _addr_only ( address ) )
		return self.getreply()
	# a.k.a.
	vrfy = verify
	
	def expn ( self, address: str ) -> Tuple[int,str]:
		"""SMTP 'EXPN' command -- expands a mailing list."""
		self.putcmd ( b'EXPN', _addr_only ( address ) )
		return self.getreply()
	
	# some useful methods
	
	def ehlo_or_helo_if_needed ( self ) -> None:
		"""Call self.ehlo() and/or self.helo() if needed.
		
		If there has been no previous EHLO or HELO command this session, this
		method tries ESMTP EHLO first.
		
		This method may raise the following exceptions:
		
		 SMTPHeloError            The server didn't reply properly to
								  the helo greeting.
		"""
		if self.helo_resp is None and self.ehlo_resp is None:
			if not ( 200 <= self.ehlo()[0] <= 299 ):
				code, resp = self.helo()
				if not ( 200 <= code <= 299 ):
					raise SMTPHeloError ( code, resp )
	
	def _auth_cram_md5 ( self, user: str, password: str ) -> Tuple[int,str]:
		code, resp = self.docmd ( b'AUTH', b'CRAM-MD5', sensitive = True )
		if code != 503: # 503 == 'Error: already authenticated'
			code, resp = self.docmd ( encode_cram_md5 ( resp, user, password ) )
		return code, resp
	
	def _auth_plain ( self, user: str, password: str ) -> Tuple[int,str]:
		code, resp = self.docmd ( b'AUTH',
			b'PLAIN ' + encode_plain ( user, password ),
			sensitive = True,
		)
		return code, resp
	
	def _auth_login ( self, user: str, password: str ) -> Tuple[int,str]:
		code, resp = self.docmd ( b'AUTH',
			b'LOGIN ' + encode_base64 ( user.encode ( 'ascii', 'strict' ) ),
			sensitive = True,
		)
		if code != 334:
			raise SMTPAuthenticationError ( code, resp )
		code, resp = self.docmd (
			encode_base64 ( password.encode ( 'utf-8', 'strict' ) ),
			sensitive = True,
		)
		return code, resp
	
	_preferred_auths: List[Tuple[str,Callable[[SMTP,str,str],Tuple[int,str]]]] = [
		( AUTH_CRAM_MD5, _auth_cram_md5 ),
		( AUTH_PLAIN, _auth_plain ),
		( AUTH_LOGIN, _auth_login ),
	]
	
	def login ( self, user: str, password: str ) -> Tuple[int,str]:
		"""Log in on an SMTP server that requires authentication.
		
		The arguments are:
			- user:     The user name to authenticate with.
			- password: The password for the authentication.
		
		If there has been no previous EHLO or HELO command this session, this
		method tries ESMTP EHLO first.
		
		This method will return normally if the authentication was successful.
		
		This method may raise the following exceptions:
		
		 SMTPHeloError            The server didn't reply properly to
								  the helo greeting.
		 SMTPAuthenticationError  The server didn't accept the username/
								  password combination.
		 SMTPException            No suitable authentication method was
								  found.
		"""
		log = logger.getChild ( 'SMTP.login' )
		
		self.ehlo_or_helo_if_needed()
		
		if not self.has_extn ( 'auth' ):
			raise SMTPException ( 'SMTP AUTH extension not supported by server.' )
		
		# Authentication methods the server supports:
		authlist = self.esmtp_features['auth'].split()
		log.info ( 'authlist=%r', authlist )
		
		# List of authentication methods we support: from preferred to
		# less preferred methods. Except for the purpose of testing the weaker
		# ones, we prefer stronger methods like CRAM-MD5:
		
		# Determine the authentication method we'll use
		authmethod: Opt[Callable[[SMTP,str,str],Tuple[int,str]]] = None
		for method, impl in self._preferred_auths:
			if method in authlist:
				authmethod = impl
				break
		
		if authmethod is None:
			raise SMTPException ( '"No suitable authentication method found.' )
		else:
			code, resp = authmethod ( self, user, password )
		
		if code != 503: # already authenticated
			if code >= 400:
				raise SMTPAuthenticationError ( code, resp )
			if code != 235: # authentication successful
				log.warning ( 'unexpected success code=%r resp=%r', code, resp )
		return code, resp
	
	def starttls ( self, keyfile: Opt[str] = None, certfile: Opt[str] = None ) -> Tuple[int,str]:
		"""Puts the connection to the SMTP server into TLS mode.
		
		If there has been no previous EHLO or HELO command this session, this
		method tries ESMTP EHLO first.
		
		If the server supports TLS, this will encrypt the rest of the SMTP
		session. If you provide the keyfile and certfile parameters,
		the identity of the SMTP server and client can be checked. This,
		however, depends on whether the socket module really checks the
		certificates.
		
		This method may raise the following exceptions:
		
		 SMTPHeloError            The server didn't reply properly to
								  the helo greeting.
		"""
		#log = logger.getChild ( 'SMTP.starttls' )
		
		self.ehlo_or_helo_if_needed()
		if not self.has_extn ( 'starttls' ):
			raise SMTPException ( 'STARTTLS extension not supported by server.' )
		resp, reply = self.docmd ( b'STARTTLS' )
		if resp == 220:
			if not _have_ssl:
				raise RuntimeError ( 'No SSL support included in this Python' )
			sock = ssl.wrap_socket ( self.sock, keyfile, certfile )
			self.sock = sock
			self.file = SSLFakeFile ( sock )
			# RFC 3207:
			# The client MUST discard any knowledge obtained from
			# the server, such as the list of SMTP service extensions,
			# which was not obtained from the TLS negotiation itself.
			self.helo_resp = None
			self.ehlo_resp = None
			self.esmtp_features = {}
			self.does_esmtp = 0
		else:
			# RFC 3207:
			# 501 Syntax error (no parameters allowed)
			# 454 TLS not available due to temporary reason
			raise SMTPResponseException ( resp, reply )
		return resp, reply
	
	def sendmail ( self,
		from_addr: str,
		to_addrs: Union[str,Seq[str]],
		msg: bytes,
		mail_options: List[str] = [],
		rcpt_options: List[bytes] = [],
	) -> Dict[str,Tuple[int,str]]:
		resp, senderrs = self.sendmail2(
			from_addr,
			to_addrs,
			msg,
			mail_options,
			rcpt_options,
		)
		return senderrs
	
	def sendmail2 ( self,
		from_addr: str,
		to_addrs: Union[str,Seq[str]],
		msg: bytes,
		mail_options: List[str] = [],
		rcpt_options: List[bytes] = [],
	) -> Tuple[str,Dict[str,Tuple[int,str]]]:
		"""This command performs an entire mail transaction.
		
		The arguments are:
			- from_addr    : The address sending this mail.
			- to_addrs     : A list of addresses to send this mail to.  A bare
							 string will be treated as a list with 1 address.
			- msg          : The message to send.
			- mail_options : List of ESMTP options (such as 8bitmime) for the
							 mail command.
			- rcpt_options : List of ESMTP options (such as DSN commands) for
							 all the rcpt commands.
		
		If there has been no previous EHLO or HELO command this session, this
		method tries ESMTP EHLO first.  If the server does ESMTP, message size
		and each of the specified options will be passed to it.  If EHLO
		fails, HELO will be tried and ESMTP options suppressed.
		
		This method will return normally if theg mail is accepted for at least
		one recipient.  It returns a dictionary, with one entry for each
		recipient that was refused.  Each entry contains a tuple of the SMTP
		error code and the accompanying error message sent by the server.
		
		This method may raise the following exceptions:
		
		 SMTPHeloError          The server didn't reply properly to
								the helo greeting.
		 SMTPRecipientsRefused  The server rejected ALL recipients
								(no mail was sent).
		 SMTPSenderRefused      The server didn't accept the from_addr.
		 SMTPDataError          The server replied with an unexpected
								error code (other than a refusal of
								a recipient).
		
		Note: the connection will be open even after an exception is raised.
		
		Example:
		
		 >>> import smtplib2
		 >>> s=smtplib2.SMTP("localhost")
		 >>> tolist=["one@one.org","two@two.org","three@three.org","four@four.org"]
		 >>> msg = '''\\
		 ... From: Me@my.org
		 ... Subject: testin'...
		 ...
		 ... This is a test '''
		 >>> s.sendmail("me@my.org",tolist,msg)
		 { "three@three.org" : ( 550 ,"User unknown" ) }
		 >>> s.quit()
		
		In the above example, the message was accepted for delivery to three
		of the four addresses, and one was rejected, with the error code
		550.  If all addresses are accepted, then the method will return an
		empty dictionary.
		
		"""
		assert isinstance ( msg, bytes ), f'expected type(msg)=bytes but got {msg!r}'
		self.ehlo_or_helo_if_needed()
		esmtp_opts: List[bytes] = []
		if self.does_esmtp:
			# Hmmm? what's this? -ddm
			# self.esmtp_features['7bit']=""
			if self.has_extn ( 'size' ):
				esmtp_opts.append ( f'size={len(msg)}'.encode ( 'ascii', 'strict' ) )
			for option in mail_options:
				esmtp_opts.append ( option.encode ( 'ascii', 'strict' ) )
		
		code, resp = self.mail ( from_addr, esmtp_opts )
		if code != 250:
			self.rset()
			raise SMTPSenderRefused ( code, resp, from_addr )
		senderrs: Dict[str,Tuple[int,str]] = {}
		if isinstance ( to_addrs, ( str, bytes ) ):
			to_addrs = [ to_addrs ]
		for each in to_addrs:
			code, resp = self.rcpt ( each, rcpt_options )
			if code not in ( 250, 251 ):
				senderrs[each] = code, resp
		if len ( senderrs ) == len ( to_addrs ):
			# the server refused all our recipients
			self.rset()
			raise SMTPRecipientsRefused ( senderrs )
		code, resp = self.data ( msg )
		if code != 250:
			self.rset()
			raise SMTPDataError ( code, resp )
		#if we got here then somebody got our mail
		return resp, senderrs
	
	def close ( self ) -> None:
		"""Close the connection to the SMTP server."""
		try:
			file = self.file
			self.file = None
			if file:
				file.close()
		finally:
			sock = getattr ( self, 'sock', None )
			if sock is not None:
				del self.sock
				sock.close()
	
	def quit ( self ) -> Tuple[int,str]:
		"""Terminate the SMTP session."""
		res = self.docmd ( b'QUIT' )
		# A new EHLO is required after reconnecting with connect()
		self.ehlo_resp = self.helo_resp = None
		self.esmtp_features = {}
		self.does_esmtp = False
		self.close()
		return res

if _have_ssl:

	class SMTP_SSL ( SMTP ):
		""" This is a subclass derived from SMTP that connects over an SSL
		encrypted socket (to use this class you need a socket module that was
		compiled with SSL support). If host is not specified, '' (the local
		host) is used. If port is omitted, the standard SMTP-over-SSL port
		(465) is used.  local_hostname has the same meaning as it does in the
		SMTP class.  keyfile and certfile are also optional - they can contain
		a PEM formatted private key and certificate chain file for the SSL
		connection.
		
		"""
		
		default_port = SMTP_SSL_PORT
		
		def __init__ ( self,
			host: str = '',
			port: int = 0,
			local_hostname: Opt[str] = None,
			keyfile: Opt[str] = None,
			certfile: Opt[str] = None,
			timeout: Opt[Union[int,float]] = None,
		) -> None:
			self.keyfile = keyfile
			self.certfile = certfile
			super().__init__ ( host, port, local_hostname,
				timeout or getattr ( socket, '_GLOBAL_DEFAULT_TIMEOUT' )
			)
		
		def _get_socket ( self, host: str, port: int, timeout: Opt[Union[int,float]] ) -> socket.socket:
			log = logger.getChild ( 'SMTP_SSL._get_socket' )
			log.info ( 'host=%r port=%r', host, port )
			new_socket = socket.create_connection ( ( host, port ), timeout )
			new_socket = ssl.wrap_socket ( new_socket, self.keyfile, self.certfile )
			self.file = SSLFakeFile ( new_socket )
			return new_socket
	
	__all__.append ( 'SMTP_SSL' )

#
# LMTP extension
#

if sys.platform != 'win32':
	class LMTP ( SMTP ):
		"""LMTP - Local Mail Transfer Protocol
		
		The LMTP protocol, which is very similar to ESMTP, is heavily based
		on the standard SMTP client. It's common to use Unix sockets for
		LMTP, so our connect() method must support that as well as a regular
		host:port server.  local_hostname has the same meaning as it does in
		the SMTP class.  To specify a Unix socket, you must use an absolute
		path as the host, starting with a '/'.
		
		Authentication is supported, using the regular SMTP mechanism. When
		using a Unix socket, LMTP generally don't support or require any
		authentication, but your mileage might vary."""
		
		default_port = LMTP_PORT
		
		ehlo_msg = b'lhlo'
		
		def __init__ ( self,
			host: str = '',
			port: int = LMTP_PORT,
			local_hostname: Opt[str] = None,
		) -> None:
			"""Initialize a new instance."""
			super().__init__ ( host, port, local_hostname )
		
		def connect ( self, host: str = 'localhost', port: int = 0 ) -> Tuple[int,str]:
			"""Connect to the LMTP daemon, on either a Unix or a TCP socket."""
			log = logger.getChild ( 'LMTP.connect' )
			if host[0] != '/':
				return super().connect ( host, port )
			
			# Handle Unix-domain sockets.
			try:
				self.sock = socket.socket ( socket.AF_UNIX, socket.SOCK_STREAM )
				self.sock.connect ( host )
			except socket.error as e:
				log.warning ( 'connect to host %r failed with %r', host, e )
				if self.sock:
					self.sock.close()
				del self.sock
				raise
			code, msg = self.getreply()
			log.info ( 'connect: %r', msg )
			return code, msg


# Test the sendmail method, which tests most of the others.
# Note: This always sends to localhost.
if __name__ == '__main__':
	logging.basicConfig ( level = logging.DEBUG )
	
	if True:
		fromaddr = 'sender@test.local'
		toaddrs = [ 'recipient@test.local' ]
		msg = '\r\n'.join ( [
			f'From: {fromaddr}'
			f'To: {toaddrs[0]}'
			'Subject: subjective'
			''
			'Test message, please disregard'
		] ).encode()
	else:
		fromaddr = input ( 'From: ' )
		toaddrs = input ( 'To: ' ).split ( ',' )
		print ( 'Enter message, end with ^D:' ) # TODO FIXME: ^Z on windows
		msg = b''
		while 1:
			line = sys.stdin.readline()
			if not line:
				break
			msg = msg + line.encode ( 'ascii', 'strict' )
		print ( f'Message length is {len(msg)}' )
	
	
	logger.info ( 'creating SMTP object' )
	port = 587
	secure = ( port == 465 )
	server = ( SMTP_SSL if secure else SMTP ) ( '127.0.0.1', port )
	
	if not secure:
		logger.info ( 'STARTTLS' )
		server.starttls()
	
	if False:
		logger.info ( 'auth' )
		server.login ( 'username', 'password' )
	
	logger.info ( 'sendmail()' )
	server.sendmail ( fromaddr, toaddrs, msg )
	
	logger.info ( 'quit' )
	server.quit()
	
	logger.info ( 'done' )
