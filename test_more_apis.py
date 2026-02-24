import requests

# Test more job board APIs
apis = [
    ('Remote OK (all)', 'https://remoteok.com/api'),
    ('Remotive', 'https://remotive.com/api/remote-jobs?limit=50'),
    ('Remote Python', 'https://remote-python.com/joblist/'),
]

for name, url in apis:
    try:
        r = requests.get(url, timeout=10)
        print(f'{name}: {r.status_code} ({len(r.text)} bytes)')
    except Exception as e:
        print(f'{name}: Error')
