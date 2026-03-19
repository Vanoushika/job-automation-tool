"""Push jobs_output.json to the data branch via GitHub API."""
import json
import base64
import os
import urllib.request
import urllib.error

TOKEN  = os.environ["GITHUB_TOKEN"]
REPO   = "Vanoushika/job-automation-tool"
FILE   = "jobs_output.json"
BRANCH = "data"

def api(url, method="GET", body=None):
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Authorization": f"token {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)

# Step 1 — ensure the data branch exists
try:
    api(f"https://api.github.com/repos/{REPO}/git/ref/heads/{BRANCH}")
    print(f"Branch '{BRANCH}' exists.")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print(f"Branch '{BRANCH}' not found — creating it...")
        # Get SHA of main branch tip
        main = api(f"https://api.github.com/repos/{REPO}/git/ref/heads/main")
        sha  = main["object"]["sha"]
        api(
            f"https://api.github.com/repos/{REPO}/git/refs",
            method="POST",
            body=json.dumps({"ref": f"refs/heads/{BRANCH}", "sha": sha}).encode(),
        )
        print(f"Branch '{BRANCH}' created.")
    else:
        raise

# Step 2 — get existing file SHA (needed to update)
file_sha = ""
try:
    info = api(f"https://api.github.com/repos/{REPO}/contents/{FILE}?ref={BRANCH}")
    file_sha = info.get("sha", "")
    print(f"Existing file SHA: {file_sha[:8]}...")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("File does not exist yet — will create it.")
    else:
        raise

# Step 3 — push the file
with open(FILE, "rb") as f:
    content = base64.b64encode(f.read()).decode()

payload = {"message": "Jobs update", "content": content, "branch": BRANCH}
if file_sha:
    payload["sha"] = file_sha

api(
    f"https://api.github.com/repos/{REPO}/contents/{FILE}",
    method="PUT",
    body=json.dumps(payload).encode(),
)
print("Jobs pushed to data branch successfully.")
