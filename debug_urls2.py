import requests
import re
import json

# Get the email
resp = requests.get('http://localhost:3001/read-email?id=19c8deff2362d9d6')
data = resp.json()
body = data['email']['body']

# Find URLs with better regex - handle truncated URLs
# Look for linkedin.com/jobs patterns
patterns = [
    r'linkedin\.com/comm/jobs/view/[0-9]+',
    r'linkedin\.com/jobs/view/[0-9]+',
    r'View job: (https?://[^\s]+)',
]

for pattern in patterns:
    matches = re.findall(pattern, body)
    print(f"Pattern '{pattern}': {len(matches)} matches")
    for m in matches[:3]:
        print(f"  {m[:100]}")
