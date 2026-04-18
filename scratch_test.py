import sys
import os

# Add to Python path
sys.path.append("/Users/dibbo/IdeaProjects/agnes/Makeathon26_Spherecast")

from src.crawling.crawling_entry import search_purebulk, _get_driver

print("Searching purebulk...")
res = search_purebulk("vitamin c")
print(res[:2])

if res:
    driver = _get_driver()
    url = res[0]["product_url"]
    print(f"Fetching {url}")
    driver.get(url)
    import time
    time.sleep(3)
    html = driver.page_source
    with open("page.html", "w") as f:
        f.write(html)
    driver.quit()
    print("Done fetching, saved to page.html")
