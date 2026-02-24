import requests
from bs4 import BeautifulSoup

url = 'https://www.naukri.com/customer-success-manager-jobs-in-india'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive'
}
resp = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(resp.text, "lxml")

# Check for job cards
job_cards = soup.select("article.jobTuple, .job-card, .tuple")
print(f"Job cards: {len(job_cards)}")

# Check for any notices/blocks
notices = soup.select(".notice, .block-message, .recaptcha")
print(f"Notices/blocks: {len(notices)}")

# Print title
print(f"Page title: {soup.title.string if soup.title else 'No title'}")

# Look for any element with 'job' in class
job_elements = soup.find_all(class_=lambda x: x and 'job' in x.lower())
print(f"Elements with 'job' in class: {len(job_elements)}")

# Try to find main content
main = soup.select_one("#root, .main, .container")
if main:
    print(f"Main container found: {main.get('class')}")
else:
    print("No main container found")

# Print first 500 chars of body
body = soup.body
if body:
    print(f"\nBody classes: {body.get('class')}")
    print(f"Body text preview: {body.get_text()[:300]}")
