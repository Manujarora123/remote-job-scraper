import requests
from bs4 import BeautifulSoup

url = 'https://www.naukri.com/customer-success-manager-jobs-in-india'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html'
}
resp = requests.get(url, headers=headers, timeout=15, allow_redirects=False)
print('Status:', resp.status_code)
print('Redirect:', resp.headers.get('Location', 'None'))
print('Content length:', len(resp.text))
