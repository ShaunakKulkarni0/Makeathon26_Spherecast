from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1920,1080')
driver = webdriver.Chrome(options=options)
driver.get("https://eu.capsuline.com/search?q=vitamin")
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')
links = soup.find_all('a', href=True)
for item in links[:20]:
    print(item.get('href'), item.text.strip()[:100])
