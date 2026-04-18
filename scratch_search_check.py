import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

urls = {
    "Capsuline": "https://www.capsuline.com",
    "Colorcon": "https://www.colorcon.com",
    "Custom Probiotics": "https://www.customprobiotics.com",
    "Darling Ingredients / Rousselot": "https://www.rousselot.com",
    "Icelandirect": "https://www.icelandirect.com",
    "Ingredion": "https://www.ingredion.com",
    "Jost Chemical": "https://www.jostchemical.com",
    "Koster Keunen": "https://www.kosterkeunen.com",
    "Nutra Food Ingredients": "https://www.nutrafoodingredients.com",
    "PureBulk": "https://www.purebulk.com",
    "Sensient": "https://www.sensientfoodcolors.com",
    "Source-Omega LLC": "https://www.source-omega.com",
    "Strahl & Pitsch": "https://www.strahlpitsch.com",
    "Trace Minerals": "https://www.traceminerals.com"
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

for name, url in urls.items():
    try:
        r = requests.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(r.text, 'html.parser')
        search_inputs = soup.find_all('input', {'type': ['search', 'text'], 'name': lambda x: x and 'search' in x.lower() or 'q' in x.lower()})
        search_forms = soup.find_all('form', action=lambda x: x and 'search' in x.lower())
        has_search = len(search_inputs) > 0 or len(search_forms) > 0
        print(f"{name}: Search Input/Form found? {has_search}")
    except Exception as e:
        print(f"{name}: Error {e}")
