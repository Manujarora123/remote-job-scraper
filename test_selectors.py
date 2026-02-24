import requests
from bs4 import BeautifulSoup

# Try different URL paths
urls = [
    'https://remoteok.com/remote-sales-jobs',
    'https://remoteok.com/remote-customer-success-jobs',
    'https://remoteok.com/'
]

headers = {'User-Agent': 'Mozilla/5.0'}

for url in urls:
    print(f"\n=== {url} ===")
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'lxml')
    
    # Look for various job selectors
    selectors = ['tr.job', 'div.job', 'a.job', '.job-item', 'article']
    for sel in selectors:
        items = soup.select(sel)
        if items:
            print(f"  Selector '{sel}': {len(items)} items")
            # Print structure of first item
            first = items[0]
            print(f"    First item classes: {first.get('class')}")
            print(f"    HTML: {str(first)[:300]}")
            break
