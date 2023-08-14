# stdlib imports:
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from multiprocessing.synchronize import RLock as MPLock
from typing import Any, Dict, List, Optional as Opt

# local imports:
import auditing
import repo

@dataclass
class CAR:
	id: str # call uuid
	did: str
	ani: str
	cpn: str
	acct_num: Opt[int]
	acct_name: Opt[str]
	start: float
	end: Opt[float]
	activity: Any

async def create(
	ctr: repo.Connector,
	repo: repo.AsyncRepository,
	uuid: str,
	did: str,
	ani: str,
	cpn: str,
	start: Opt[datetime] = None,
) -> None:
	if start is None:
		start = datetime.now().astimezone()
	await repo.create( ctr, uuid,
		{
			'id': uuid,
			'did': did,
			'ani': ani,
			'cpn': cpn,
			'start': start.astimezone( timezone.utc ).timestamp(),
			'activity': json.dumps([]),
		},
		audit = auditing.NoAudit(),
	)

async def activity(
	ctr: repo.Connector,
	repo: repo.AsyncRepository,
	lock: MPLock,
	uuid: str,
	description: str,
) -> None:
	with lock:
		record = await repo.get_by_id( ctr, uuid )
		activity: List[Dict[str,str]] = json.loads( record['activity'] )
		activity.append({
			'time': datetime.now().astimezone().strftime( '%H:%M:%S.%f' ),
			'description': description
		})
		record['activity'] = json.dumps( activity )
		await repo.update( ctr, uuid, record, audit = auditing.NoAudit() )

async def finish(
	ctr: repo.Connector,
	repo: repo.AsyncRepository,
	uuid: str,
	end: Opt[datetime] = None,
) -> None:
	if end is None:
		end = datetime.now().astimezone()
	await repo.update( ctr, uuid,
		{
			'end': end.astimezone( timezone.utc ).timestamp(),
		},
		audit = auditing.NoAudit(),
	)
