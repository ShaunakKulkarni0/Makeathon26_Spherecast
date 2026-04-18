import os
import re
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup

from src.crawling.crawling_entry import search_purebulk

logger = logging.getLogger(__name__)

def _scrape_detail_page(url: str, session: requests.Session) -> Dict[str, Any]:
    """Scrapes individual metadata from a PureBulk product page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Product Name
    h1 = soup.find("h1")
    name = h1.text.strip() if h1 else ""
    if not name:
        title_tag = soup.title.text if soup.title else ""
        name = title_tag.split("–")[0].strip() if "–" in title_tag else title_tag.strip()

    # 2. Starting Price
    price = None
    # Look closely near price elements or the full text
    price_match = re.search(r'\$\s*([\d\.,]+)', soup.text)
    if price_match:
        try:
            # We take the first matched price because PureBulk often lists the lowest/starting price first
            price = float(price_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # 3. Items Left
    items_left = None
    # We look for explicit remaining quantity indicators
    inventory_match = re.search(r'(?:Only\s+)?(\d+)\s+items?\s+left', soup.text, re.IGNORECASE)
    if inventory_match:
        try:
            items_left = int(inventory_match.group(1))
        except ValueError:
            pass

    # 4. Loose Tagging (Certification Tags)
    tags = set()
    text = soup.text.lower()
    
    # Direct mention: "Free of", "Free", or "Non-"
    if re.search(r'\b(free of|free|non-)\b', text, re.IGNORECASE):
        # Extract the actual phrases
        matches = re.finditer(r'\b(non-[a-z]+|[a-z]+-free|free of [a-z]+)\b', text, re.IGNORECASE)
        for m in matches:
            matched_phrase = m.group(1).upper()
            formatted_tag = matched_phrase.replace("FREE OF ", "") + ("-FREE" if "FREE OF" in matched_phrase else "")
            tags.add(formatted_tag)

    # Implicit Purity
    if re.search(r'\b(pure|100%|no additives)\b', text, re.IGNORECASE):
        tags.update(["NO-FILLERS", "PURE"])

    # Dietary Inference
    if re.search(r'\b(plant-based|vegetable|vegan|vegetarian)\b', text, re.IGNORECASE):
        tags.update(["VEGAN", "VEGETARIAN"])

    # Safety Inference
    if re.search(r'\b(synthetic|plant-derived without animal components|no animal)\b', text, re.IGNORECASE):
        tags.add("BSE-TSE-FREE")
    elif "plant-based" in text or "vegetable" in text or "vegan" in text or "vegetarian" in text:
        # If it's plant derived / vegan, it lacks animal components by definition
        tags.add("BSE-TSE-FREE")

    # 5. Size in Grams and Price Per Gram
    valid_variants = []
    options = soup.find_all("option")
    for opt in options:
        opt_text = opt.text.strip().lower()
        opt_price_match = re.search(r'\$\s*([\d\.,]+)', opt_text)
        size_match = re.search(r'([\d\.]+)\s*(g|gram|grams|kg|kilogram|kilograms)\b', opt_text)
        
        if opt_price_match and size_match:
            try:
                opt_price = float(opt_price_match.group(1).replace(',', ''))
                val = float(size_match.group(1))
                unit = size_match.group(2)
                if 'kg' in unit or 'kilogram' in unit:
                    val *= 1000
                valid_variants.append({'price': opt_price, 'size': val})
            except ValueError:
                pass
                
    size_in_grams = None
    price_per_gram = None
    
    if valid_variants:
        best_variant = None
        if price:
            for v in valid_variants:
                if abs(v['price'] - price) < 0.01:
                    best_variant = v
                    break
        if not best_variant:
            best_variant = valid_variants[0]
            
        size_in_grams = best_variant['size']
        if size_in_grams > 0:
            price_per_gram = round(best_variant['price'] / size_in_grams, 4)
    else:
        # Fallback to general text
        size_match = re.search(r'(?<!\d)([\d\.]+)\s*(g|gram|grams|kg|kilogram|kilograms)\b', soup.text.lower())
        if size_match:
            try:
                val = float(size_match.group(1))
                unit = size_match.group(2)
                if 'kg' in unit or 'kilogram' in unit:
                    val *= 1000
                size_in_grams = val
                if price and size_in_grams > 0:
                    price_per_gram = round(price / size_in_grams, 4)
            except ValueError:
                pass

    product_id = url.split("?")[0].split("/")[-1]

    return {
        "product_id": product_id,
        "name": name,
        "starting_price": price,
        "size_in_grams": size_in_grams,
        "price": price_per_gram,
        "currency": "USD",
        "items_left": items_left,
        "url": url.split("?")[0],  # Clean URL
        "certification_tags": sorted(list(tags))
    }


def run_purebulk_deep_crawl(search_queries: List[str], output_json_path: str, product_urls: List[str] = None):
    """Entry point for sweeping search terms, fetching detail pages, and saving to JSON."""
    os.makedirs(os.path.dirname(output_json_path) or ".", exist_ok=True)
    
    unique_urls = set()
    if product_urls:
        unique_urls.update(product_urls)
        
    logger.info("Executing searches...")
    for query in search_queries:
        try:
            results = search_purebulk(query)
            for res in results:
                url = res.get("product_url")
                if url:
                    clean_url = url.split("?")[0]
                    unique_urls.add(clean_url)
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            
    logger.info(f"Identified {len(unique_urls)} unique products to deeply crawl.")

    session = requests.Session()
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    final_products = []

    for idx, product_url in enumerate(list(unique_urls)):
        logger.info(f"[{idx+1}/{len(unique_urls)}] Fetching details for {product_url}")
        
        # Concurrency: 1-2 second delay
        time.sleep(2)
        
        detail_data = _scrape_detail_page(product_url, session)
        if not detail_data or not detail_data.get("name"):
            continue

        final_products.append(detail_data)
        
    output_object = {
        "timestamp": timestamp,
        "supplier": "PureBulk",
        "products": final_products
    }
    
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_object, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Crawl complete. Output written to {output_json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_purebulk_deep_crawl(["vitamin c"], "data/purebulk_crawler_output.json")
