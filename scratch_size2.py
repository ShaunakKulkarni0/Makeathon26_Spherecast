import sys
import re
from bs4 import BeautifulSoup

with open("page.html", "r") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

variants = []
options = soup.find_all("option")
for opt in options:
    text = opt.text.strip().lower()
    
    price_match = re.search(r'\$\s*([\d\.,]+)', text)
    size_match = re.search(r'([\d\.]+)\s*(g|gram|kg|kilogram)', text)
    
    if price_match and size_match:
        price = float(price_match.group(1).replace(',', ''))
        
        val = float(size_match.group(1))
        unit = size_match.group(2)
        if 'kg' in unit or 'kilogram' in unit:
            val *= 1000
        size_in_grams = val
        
        variants.append({'price': price, 'size': size_in_grams})

print("Parsed Option Variants:", variants)

# What if options don't have prices?
if not variants:
    # fallback to original price logic
    price_match = re.search(r'\$\s*([\d\.,]+)', soup.text)
    if price_match:
        print("Fallback price:", float(price_match.group(1).replace(',', '')))
    
    size_match = re.search(r'([\d\.]+)\s*(g|gram|kg|kilogram)', soup.text.lower())
    if size_match:
        val = float(size_match.group(1))
        unit = size_match.group(2)
        if 'kg' in unit or 'kilogram' in unit:
            val *= 1000
        print("Fallback size:", val)

