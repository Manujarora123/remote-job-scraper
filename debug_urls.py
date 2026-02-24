import requests
import re
import json

# Get the email
resp = requests.get('http://localhost:3001/read-email?id=19c8deff2362d9d6')
data = resp.json()
body = data['email']['body']

# Find all URLs
urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', body)
print(f"Found {len(urls)} URLs:")
for u in urls[:10]:
    print(f"  {u[:100]}")
