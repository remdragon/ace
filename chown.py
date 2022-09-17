# stdlib imports:
import os
import sys

if sys.platform != 'win32':
	import grp
	import pwd
	def chown( path: str, uid_name: str, gid_name: str ) -> None:
		uid = pwd.getpwnam( uid_name ).pw_uid
		gid = grp.getgrnam( gid_name ).gr_gid
		os.chown( path, uid, gid )
else:
	def chown( path: str, uid_name: str, gid_name: str ) -> None:
		pass
