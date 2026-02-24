import requests
from bs4 import BeautifulSoup

url = 'https://www.naukri.com/customer-success-manager-jobs-in-india'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}
resp = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(resp.text, "lxml")

# Just print the raw text length
text = soup.get_text()
print(f"Text length: {len(text)}")
print(f"Text preview: {text[:500]}")
