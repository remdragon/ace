# stdlib imports:
from pathlib import Path

# local imports:
import repo

config = repo.Config(
	fs_path = Path( '/usr/share/itas/ace' ),
	sqlite_path = Path( '/usr/share/itas/ace/ace.sqlite' )
)

if False:
	x = repo.RepoFs(
		config,
		tablename = 'boxes',
		ending = '.box',
		fields = [],
		auditing = False,
	)
elif True:
	x = repo.RepoFs(
		config,
		tablename = 'did',
		ending = '.did',
		fields = [],
		auditing = False,
	)
else:
	x = repo.RepoFs(
		config,
		tablename = 'ani',
		ending = '.ani',
		fields = [],
		auditing = False,
	)

for id, box in x.list():
	print( f'{id=} {box=}\n' )
