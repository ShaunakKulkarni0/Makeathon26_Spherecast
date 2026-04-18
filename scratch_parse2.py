import sys
import re
from bs4 import BeautifulSoup

with open("page.html", "r") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

h1 = soup.find("h1")
name = h1.text.strip() if h1 else ""

# Price
price = None
price_match = re.search(r'\$\s*([\d\.,]+)', soup.text)
if price_match:
    price = float(price_match.group(1).replace(',', ''))

# Items Left
items_left = None
inventory_match = re.search(r'(?:Only )?(\d+)\s+(?:items? )?left', soup.text, re.IGNORECASE)
if inventory_match:
    items_left = int(inventory_match.group(1))

# Tags
text = soup.text.lower()
tags = set()

if re.search(r'\b(free of|free|non-)\b', text, re.IGNORECASE):
    # This is rough, let's extract the actual word if possible
    matches = re.finditer(r'\b(non-[a-z]+|[a-z]+-free|free of [a-z]+)\b', text, re.IGNORECASE)
    for m in matches:
        tags.add(m.group(1).upper().replace("FREE OF ", "") + ("-FREE" if "FREE OF" in m.group(1).upper() else ""))

if re.search(r'\b(pure|100%|no additives)\b', text, re.IGNORECASE):
    tags.update(["NO-FILLERS", "PURE"])

if re.search(r'\b(plant-based|vegetable|vegan|vegetarian)\b', text, re.IGNORECASE):
    tags.update(["VEGAN", "VEGETARIAN"])

if re.search(r'\b(synthetic|plant-derived without animal components|no animal)\b', text, re.IGNORECASE):
    tags.add("BSE-TSE-FREE") # Loose safety inference
elif "plant-based" in text or "vegetable" in text or "vegan" in text or "vegetarian" in text:
    # If it's vegan, it has no animal components, therefore BSE-TSE-free
    # "described as synthetic or plant-derived without animal components"
    tags.add("BSE-TSE-FREE")

print("Name:", name)
print("Price:", price)
print("Items left:", items_left)
print("Tags:", tags)
