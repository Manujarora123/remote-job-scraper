import requests
import json

headers = {'User-Agent': 'Mozilla/5.0'}

# Get sales jobs via API
resp = requests.get('https://remoteok.com/api?tag=sales', headers=headers, timeout=10)
data = resp.json()

# Skip first item (legal notice), show next 3
for job in data[1:4]:
    print(json.dumps(job, indent=2))
    print("---")
