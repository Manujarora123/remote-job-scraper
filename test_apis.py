import requests
import json

# Check for job board APIs
apis_to_check = [
    ("Wellfound (AngelList)", "https://api.wellfound.com/api/v1/jobs?limit=10"),
    ("Remotive", "https://remotive.com/api/remote-jobs"),
    ("JSRemotely", "https://jsremotely.com/api/v1/jobs"),
    ("EuroJobs", "https://eurojobs.com/api/jobs"),
]

headers = {"User-Agent": "Mozilla/5.0"}

for name, url in apis_to_check:
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"{name}: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:5]}")
                if 'jobs' in data:
                    print(f"  Jobs count: {len(data['jobs'])}")
                    if data['jobs']:
                        print(f"  Sample: {data['jobs'][0].get('title', 'N/A')}")
            elif isinstance(data, list):
                print(f"  Items: {len(data)}")
    except Exception as e:
        print(f"{name}: Error - {str(e)[:50]}")
