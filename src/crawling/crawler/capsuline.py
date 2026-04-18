import os
import json
import time
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

from src.crawling.crawling_entry import search_capsuline

logger = logging.getLogger(__name__)

PDF_STORAGE_DIR = "assets/documents/capsuline"

def _download_pdf(url: str, output_dir: str, title: str) -> Optional[str]:
    """Downloads a PDF from a URL securely and saves it offline."""
    if not url:
        return None
        
    try:
        # Standardize URL if it's relative
        if url.startswith("//"):
            url = f"https:{url}"
        elif url.startswith("/"):
            url = f"https://eu.capsuline.com{url}"

        # Clean title for filesystem
        safe_title = "".join([c if c.isalnum() else "_" for c in title]).strip("_")
        if not safe_title:
            safe_title = "document"
            
        unique_suffix = str(uuid.uuid4())[:8]
        file_name = f"{safe_title}_{unique_suffix}.pdf"
        local_path = os.path.join(output_dir, file_name)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return local_path
    except Exception as e:
        logger.error(f"Failed to download PDF {url}: {e}")
        return None

def _scrape_detail_page(url: str, driver_or_session) -> Dict[str, Any]:
    """Scrapes individual metadata blocks and PDF links from a Capsuline product page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    html = ""
    try:
        if hasattr(driver_or_session, 'get') and not hasattr(driver_or_session, 'request'): 
            driver_or_session.get(url)
            html = driver_or_session.page_source
        else: 
            resp = driver_or_session.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Product Name
    title_tag = soup.title.text if soup.title else ""
    name = title_tag.split("–")[0].strip() if "–" in title_tag else title_tag.strip()
    if not name:
        h1 = soup.find("h1")
        name = h1.text.strip() if h1 else ""

    # 2. Price
    price = ""
    # The true computed price (with VAT/local taxes) is rendered by JS inside the "Add to cart" button
    add_to_cart_btn = soup.find("button", {"name": "add"}) or soup.find("button", class_="product-form__submit")
    if add_to_cart_btn:
        btn_text = add_to_cart_btn.text.strip()
        # "Add to cart - €761,95" -> "€761,95"
        if "-" in btn_text:
            price = btn_text.split("-")[-1].strip()
        else:
            price = btn_text
            
    # Fallback to OG tags if button is somehow missing
    if not price:
        og_price = soup.find("meta", property="og:price:amount")
        og_currency = soup.find("meta", property="og:price:currency")
        if og_price and og_price.get("content"):
            currency_sym = "€" if (og_currency and "EUR" in og_currency.get("content", "")) else (og_currency.get("content", "") if og_currency else "")
            price = f"{currency_sym}{og_price.get('content')}"

    # 3. Documents
    certifications = []
    technical_sheet = None

    links = soup.find_all("a", href=True)
    for link in links:
        href = link.get("href")
        text = link.text.strip()
        text_lower = text.lower()

        # Identify PDFs - shopify serves pdfs from cdn typically without .pdf extension sometimes but with standard path
        is_pdf = ".pdf" in href.lower() or "cdn.shopify.com/s/files" in href.lower() or href.startswith("//cdn.shopify.com/")

        if is_pdf:
            if "technical" in text_lower or "sheet" in text_lower or "download" in text_lower:
                if not technical_sheet:
                    technical_sheet = {"url": href, "local_path": ""}
            elif "coa" in text_lower or "kosher" in text_lower or "halal" in text_lower or "allergen" in text_lower or "cert" in text_lower or len(text) > 2:
                if not any(c.get("url") == href for c in certifications):
                    certifications.append({"title": text, "url": href, "local_path": ""})

    product_id = url.split("/")[-1].split("?")[0]

    return {
        "product_id": product_id,
        "name": name,
        "price": price,
        "url": url,
        "docs_to_download": {
            "certifications": certifications,
            "technical_sheet": technical_sheet
        }
    }


def run_capsuline_deep_crawl(search_queries: List[str], output_json_path: str, product_urls: List[str] = None):
    """Entry point for sweeping search terms, fetching detail pages, expanding to PDFs, and saving to JSON."""
    os.makedirs(PDF_STORAGE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(output_json_path) or ".", exist_ok=True)
    
    unique_urls = set()
    if product_urls:
        unique_urls.update(product_urls)
        
    logger.info("Executing searches...")
    for query in search_queries:
        try:
            results = search_capsuline(query)
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

    for idx, product_url in enumerate(unique_urls):
        logger.info(f"[{idx+1}/{len(unique_urls)}] Fetching details for {product_url}")
        
        time.sleep(2)
        
        detail_data = _scrape_detail_page(product_url, session)
        if not detail_data.get("name"):
            continue

        raw_docs = detail_data.pop("docs_to_download", {})
        
        # Download Certifications
        final_certs = []
        for cert in raw_docs.get("certifications", []):
            local_path = _download_pdf(cert["url"], PDF_STORAGE_DIR, cert["title"] or "cert")
            if local_path:
                final_certs.append({
                    "title": cert["title"],
                    "url": cert["url"],
                    "local_path": local_path
                })
        
        # Download Technical Sheet
        final_technical_sheet = None
        ts = raw_docs.get("technical_sheet")
        if ts:
            local_path = _download_pdf(ts["url"], PDF_STORAGE_DIR, "Technical_Sheet")
            if local_path:
                final_technical_sheet = {
                    "url": ts["url"],
                    "local_path": local_path
                }
        
        detail_data["documents"] = {
            "certifications": final_certs,
            "technical_sheet": final_technical_sheet
        }
        
        final_products.append(detail_data)
        
    output_object = {
        "timestamp": timestamp,
        "supplier": "Capsuline",
        "products": final_products
    }
    
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_object, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Crawl complete. Output written to {output_json_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_capsuline_deep_crawl(["Clear Gelatin Capsules Size 00"], "data/capsuline_crawler_output.json")
