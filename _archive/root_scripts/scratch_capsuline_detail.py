from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1920,1080')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=options)

url = "https://eu.capsuline.com/products/clear-gelatin-capsules-size-00-box-of-70-000"
driver.get(url)
time.sleep(3)

html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

print(f"Title: {soup.title.text if soup.title else 'None'}")
price = soup.find(class_='price')
print(f"Price: {price.text.strip() if price else 'Not found'}")

print("\n--- PDF Links ---")
links = soup.find_all('a', href=True)
for item in links:
    href = item['href']
    if '.pdf' in href.lower() or 'sheet' in item.text.lower() or 'cert' in item.text.lower():
        print(f"Found: {item.text.strip()} -> {href}")

driver.quit()
