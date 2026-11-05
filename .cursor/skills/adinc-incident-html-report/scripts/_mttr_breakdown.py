import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adinc_credentials import basic_auth, load_credentials
from adinc_fetch import jira_search

jql = (
    'project = ADINC AND resolutiondate >= "2026-10-01" '
    'AND resolutiondate < "2026-11-01" ORDER BY resolutiondate DESC'
)
user, tok = load_credentials()
issues = jira_search(jql, basic_auth(user, tok))
rows = [(i["key"], i.get("start_date_pick"), i.get("end_date"), i.get("mttr_days")) for i in issues]
rows.sort(key=lambda x: x[3] or -1, reverse=True)
vals = [r[3] for r in rows if r[3] is not None]
print("MTTR = End Date - Start DatePick (calendar days)\n")
for k, s, e, m in rows:
    print(f"  {k}: {s} -> {e} = {m}d")
mean = sum(vals) / len(vals)
med = sorted(vals)[len(vals) // 2]
print(f"\nn={len(vals)}  mean={mean:.2f}d  median={med}d  KPI tile={int(round(mean))}d")
