import requests

url = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
response = requests.get(url)
content = response.text

# Print first 50 lines to see the structure
lines = content.split('\n')
for i, line in enumerate(lines[:100], 1):
    if '|' in line:
        print(f"{i}: {line[:150]}")
