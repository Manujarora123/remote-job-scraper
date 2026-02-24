import requests
import json

headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

# Try the API endpoint
urls = [
    'https://remoteok.com/api',
    'https://remoteok.com/api?tag=sales',
]

for url in urls:
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f'{url}: {resp.status_code}')
        if resp.status_code == 200:
            data = resp.json()
            print(f'  Items: {len(data)}')
            if data:
                print(f'  First: {data[0]}')
    except Exception as e:
        print(f'{url}: Error - {e}')
