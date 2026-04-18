import sys
from bs4 import BeautifulSoup
import re

with open("page.html", "r") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

sizes = set()
for s in soup.find_all(string=re.compile(r'\d+\s*(?:g|grams?|kg|kilograms?|mg|milligrams?)\b', re.IGNORECASE)):
    if len(s.strip()) < 30:
        sizes.add(s.strip())

print("Possible size strings found:", sizes)

# Also check if there's any dropdown or radio button for weight/sizes
variants = soup.find_all("option")
for v in variants:
    print("Option:", v.text.strip(), "value:", v.get("value"))

radio_labels = soup.find_all("label", class_=lambda c: c and "variant" in c.lower() or "option" in c.lower())
if not radio_labels:
    radio_labels = soup.find_all("label")
for l in radio_labels:
    text = l.text.strip()
    if re.search(r'\d+\s*(?:g|kg|mg|oz|lb)\b', text, re.IGNORECASE):
        print("Label:", text)
