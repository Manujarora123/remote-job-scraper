import requests
from bs4 import BeautifulSoup

url = 'https://remoteok.com/remote-sales-jobs'
headers = {'User-Agent': 'Mozilla/5.0'}
resp = requests.get(url, headers=headers, timeout=15)
print('Status:', resp.status_code)
soup = BeautifulSoup(resp.text, 'lxml')
print('Title:', soup.title.string if soup.title else 'None')
jobs = soup.select('tr.job')
print('Jobs found:', len(jobs))
if jobs:
    j = jobs[0]
    print('First job classes:', j.get('class'))
    print('Title elem:', j.select_one('h2'))
    print('Company elem:', j.select_one('h3'))
    # Try alternate selectors
    print('Alt title:', j.select_one('.title'))
    print('Full HTML snippet:', str(j)[:500])
