#!/usr/bin/env bash
# End-to-end synthetic alert test. Creates a clearly labelled test record.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

BASE='http://127.0.0.1:5174'
AM='http://127.0.0.1:9093/api/v2/alerts'
name='AIOpsFinalSmokeTest'
instance=f'local-final-{int(time.time())}'
labels={'alertname':name,'instance':instance,'severity':'warning'}
annotations={'summary':'Synthetic end-to-end smoke test','description':'Not a real outage; automatically sent by test script'}
starts_at=datetime.now(timezone.utc).isoformat()

def post_alert(ends):
    alert=[{'labels':labels,'annotations':annotations,
            'startsAt':starts_at,
            'endsAt':ends.isoformat()}]
    request=Request(AM,data=json.dumps(alert).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=10) as response:
        print('Alertmanager accepted:',response.status)

def find_incident():
    with urlopen(f'{BASE}/api/incidents',timeout=10) as response:
        records=json.load(response)['incidents']
    candidates=[x for x in records if x.get('alertname')==name]
    # Database may contain earlier smoke tests; correlate with the current time.
    return next((x for x in candidates if x.get('summary')=='Synthetic end-to-end smoke test' and
                 datetime.fromisoformat(x['created_at']).timestamp() > started-10),None)

started=time.time()
post_alert(datetime.now(timezone.utc)+timedelta(minutes=5))
print('Checking Alertmanager -> backend -> PostgreSQL (up to 90s)...')
incident=None
for attempt in range(30):
    time.sleep(3)
    incident=find_incident()
    if incident:
        print('FIRING delivery VERIFIED; incident:',incident['id'],'status:',incident['status'])
        break
if not incident:
    raise SystemExit('FAIL: synthetic firing alert was not persisted. Check Alertmanager/backend logs.')

# Test resolved notification on same label set. Server may coalesce groups.
post_alert(datetime.now(timezone.utc)-timedelta(seconds=2))
print('Checking resolved notification (up to 120s)...')
for attempt in range(40):
    time.sleep(3)
    incident=find_incident()
    if incident and incident['status']=='resolved':
        print('RESOLVED lifecycle VERIFIED; incident:',incident['id'])
        break
else:
    print('NOT VERIFIED: resolved status not received in test window. Inspect Alertmanager grouping/logs.')
    raise SystemExit(2)
PY
