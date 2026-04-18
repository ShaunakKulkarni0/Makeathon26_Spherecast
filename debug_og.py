from bs4 import BeautifulSoup
import requests

urls = [
    "https://eu.capsuline.com/products/separated-empty-gelatin-capsules-size-0-box-of-100-000",
    "https://eu.capsuline.com/products/colored-empty-gelatin-capsules-size-3-box-of-200-000"
]
for url in urls:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, 'html.parser')
    price_amt = soup.find('meta', property='og:price:amount')
    price_cur = soup.find('meta', property='og:price:currency')
    
    print(f"\n{url}")
    if price_amt and price_cur:
        print(f"Price: {price_amt['content']} {price_cur['content']}")
    else:
        print("og:price not found")
