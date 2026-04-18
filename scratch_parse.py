import sys
from bs4 import BeautifulSoup

with open("page.html", "r") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

print("Title:", soup.title.text if soup.title else None)
h1 = soup.find("h1")
print("H1:", h1.text.strip() if h1 else None)

price_elements = soup.find_all(class_=lambda c: c and "price" in c.lower())
for p in price_elements[:5]:
    print("Price Element:", p.text.strip()[:100])
    
desc = soup.find(id=lambda i: i and "description" in i.lower()) or soup.find(class_=lambda c: c and "description" in c.lower())
print("Description length:", len(desc.text) if desc else 0)

inventory = soup.find_all(lambda tag: tag.name and "left" in tag.text.lower())
for tag in inventory:
    if len(tag.text.strip()) < 50:
        print("Inventory text:", tag.text.strip())
