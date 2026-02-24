import requests
import json

# Try Naukri API endpoints
headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# Try different Naukri endpoints
endpoints = [
    "https://www.naukri.com/job-search?variablesJson={}",
    "https://www.naukri.com/nlogin/login",
    "https://www.naukri.com/api/jobs/search"
]

for url in endpoints:
    try:
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        print(f"{url[:50]}...: {resp.status_code}")
    except Exception as e:
        print(f"Error: {str(e)[:50]}")
