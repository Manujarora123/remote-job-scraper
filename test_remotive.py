import requests
import json

headers = {"User-Agent": "Mozilla/5.0"}

# Check Remotive categories
categories = ["sales", "customer-service", "business"]

for cat in categories:
    url = f"https://remotive.com/api/remote-jobs?category={cat}"
    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()
    print(f"\n=== {cat} ({data.get('job-count')} jobs) ===")
    for job in data.get('jobs', [])[:2]:
        print(f"  {job.get('title')} @ {job.get('company_name')}")
