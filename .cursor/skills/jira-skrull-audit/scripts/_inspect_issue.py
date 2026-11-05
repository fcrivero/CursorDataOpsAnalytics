import json
import os
import base64
import urllib.request
from pathlib import Path

env = Path(r"C:\Users\rivef104\Documents\AI\MCP-Cursor\jira-mcp-server-main\.env")
for line in env.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

email = os.environ["JIRA_USERNAME"]
pw = os.environ["JIRA_PASSWORD"]
auth = base64.b64encode(f"{email}:{pw}".encode()).decode()

key = os.environ.get("ISSUE", "SKRULL-9698")
url = (
    f"https://deept.atlassian.net/rest/api/3/issue/{key}"
    "?fields=summary,parent,customfield_10014,issuetype,status,assignee"
)
req = urllib.request.Request(
    url,
    headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
f = d["fields"]
print(json.dumps({"key": d["key"], "summary": f.get("summary"), "parent": f.get("parent"), "epic_link_cf10014": f.get("customfield_10014")}, indent=2))

jql = f'key = {key} AND "Epic Link" is EMPTY AND parent is EMPTY'
from urllib.parse import quote

search_url = f"https://deept.atlassian.net/rest/api/3/search/jql?jql={quote(jql)}&maxResults=1&fields=key"
req2 = urllib.request.Request(
    search_url,
    headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
)
with urllib.request.urlopen(req2) as r:
    s = json.loads(r.read())
print("matches missing-epic JQL:", len(s.get("issues") or []))
