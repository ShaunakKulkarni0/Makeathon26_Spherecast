from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1920,1080')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(options=options)

def dump_links(url, name):
    print(f"\n=== {name} ===")
    driver.get(url)
    time.sleep(5)
    links = driver.find_elements('tag name', 'a')
    for l in links[:50]:
        href = l.get_attribute('href')
        text = l.text.strip().replace('\n', ' ')
        if href and text and len(text) > 3:
            print(f"{text} -> {href}")

dump_links("https://www.colorcon.com/search?query=Opadry%C2%AE%20Film%20Coating%20Systems", "Colorcon")
dump_links("https://www.customprobiotics.com/search.php?search_query=High%20Potency%20Probiotic%20Powders", "Custom Probiotics")
dump_links("https://strahlpitsch.com/?s=Beeswax", "Strahl & Pitsch")
dump_links("https://www.traceminerals.com/search?q=ConcenTrace%20Trace%20Mineral%20Drops", "Trace Minerals")

driver.quit()
