from bs4 import BeautifulSoup
import requests
import json

url = "https://eu.capsuline.com/products/separated-empty-gelatin-capsules-size-0-box-of-100-000"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
soup = BeautifulSoup(resp.text, 'html.parser')

prices = soup.find_all(class_="price")
for idx, p in enumerate(prices):
    print(f"--- .price block {idx} ---")
    print(p.text.strip().replace('\n', ' '))

print("\n--- Any element containing 761 ---")
for el in soup.find_all(string=lambda text: "761" in text if text else False):
    parent = el.parent
    print(f"<{parent.name} class='{parent.get('class', [])}'> {el.strip()}")

