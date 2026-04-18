from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

def check_search(url_template, name):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url_template.format(query="vitamin"))
        time.sleep(3)
        print(f"{name}: URL={driver.current_url}")
        print(f"{name}: Title={driver.title}")
    except Exception as e:
        print(f"{name}: Error={e}")
    finally:
        driver.quit()

sites = [
    ("Capsuline", "https://www.capsuline.com/search?q={query}"),
    ("Colorcon", "https://www.colorcon.com/search?query={query}"),
    ("Custom Probiotics", "https://www.customprobiotics.com/search.php?search_query={query}"),
    ("Darling Ingredients / Rousselot", "https://www.rousselot.com/search?q={query}"),
    ("Icelandirect", "https://www.icelandirect.com/?s={query}"),
    ("Ingredion", "https://www.ingredion.com/na/en-us/search.html?q={query}"),
    ("Jost Chemical", "https://www.jostchemical.com/?s={query}"),
    ("Koster Keunen", "https://www.kosterkeunen.com/?s={query}"),
    ("Nutra Food Ingredients", "https://www.nutrafoodingredients.com/?s={query}"),
    ("PureBulk", "https://purebulk.com/search?q={query}"),
    ("Sensient", "https://sensientfoodcolors.com/?s={query}"),
    ("Source-Omega LLC", "https://www.source-omega.com/search?q={query}"),
    ("Strahl & Pitsch", "https://strahlpitsch.com/?s={query}"),
    ("Trace Minerals", "https://www.traceminerals.com/search?q={query}")
]

for name, url in sites:
    check_search(url, name)

