"""Push jobs_output.json to the data branch via GitHub API."""
import json
import base64
import os
import urllib.request
import urllib.error

TOKEN = os.environ["GITHUB_TOKEN"]
REPO  = "Vanoushika/job-automation-tool"
FILE  = "jobs_output.json"
BRANCH = "data"

# Get current file SHA (required to update an existing file)
sha = ""
try:
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE}?ref={BRANCH}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {TOKEN}"})
    with urllib.request.urlopen(req) as r:
        sha = json.load(r).get("sha", "")
    print(f"Existing file SHA: {sha[:8]}...")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("File does not exist yet — will create it.")
    else:
        raise

# Read and encode jobs file
with open(FILE, "rb") as f:
    content = base64.b64encode(f.read()).decode()

payload = {
    "message": "Jobs update",
    "content": content,
    "branch":  BRANCH,
}
if sha:
    payload["sha"] = sha

data = json.dumps(payload).encode()
req  = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/contents/{FILE}",
    data=data,
    method="PUT",
    headers={
        "Authorization": f"token {TOKEN}",
        "Content-Type":  "application/json",
    },
)
with urllib.request.urlopen(req) as resp:
    print(f"GitHub API response: {resp.status} — jobs pushed to data branch")
