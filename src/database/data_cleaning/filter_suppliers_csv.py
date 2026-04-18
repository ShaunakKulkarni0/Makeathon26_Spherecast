import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import openai
import os
import time
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY_Dibbo")

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_csv = os.path.join(base_dir, 'suppliers.csv')
output_csv = os.path.join(base_dir, 'suppliers_filtered_evaluated.csv')

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def check_bot_protection(response_code, html):
    if response_code in [401, 403]:
        return True
    html_lower = html.lower()
    if 'cloudflare' in html_lower or 'imperva' in html_lower or 'captcha' in html_lower or 'are you a human?' in html_lower:
        return True
    return False

def check_login_wall(text):
    login_phrases = ["b2b login", "customer portal", "login to view pricing", "request quote"]
    text_lower = text.lower()
    for phrase in login_phrases:
        if phrase in text_lower:
            return True
    return False

def find_catalog_links(soup, base_url):
    catalog_keywords = ['/products', '/catalog', '/shop', '/ingredients']
    found_links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(kw in href.lower() for kw in catalog_keywords):
            found_links.add(href)
    return list(found_links)

def evaluate_with_llm(text):
    prompt = f"Analyze this webpage text. Does it contain public-facing product information for raw materials? Look for specific product names, ingredient specifications, certifications, and pricing. Reply with ONLY 'VIABLE', 'REQUIRES_LOGIN', or 'NO_DATA'.\n\nText:\n{text[:15000]}"
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip()
        # Clean up any extra text
        if 'VIABLE' in result: return 'VIABLE'
        if 'REQUIRES_LOGIN' in result: return 'REQUIRES_LOGIN'
        return 'NO_DATA'
    except Exception as e:
        print(f"LLM Error: {e}")
        return "NO_DATA"

def main():
    print(f"Reading CSV from {input_csv}...")
    df = pd.read_csv(input_csv)
    
    # Step 1: Semantic Pre-Filtering
    print(f"Original shape: {df.shape}")
    
    def is_contract_manufacturer(row):
        cat = str(row.get('category', '')).lower()
        notes = str(row.get('notes', '')).lower()
        return 'contract manufacturer' in cat or 'contract manufacturer' in notes
        
    df = df[~df.apply(is_contract_manufacturer, axis=1)]
    print(f"Shape after filtering contract manufacturers: {df.shape}")
    
    def tag_priority(row):
        cat = str(row.get('category', ''))
        if cat in ["B2B Bulk Ingredient Supplier", "Direct Bulk Ingredient Supplier"]:
            return "High"
        return "Normal"
        
    df['priority_level'] = df.apply(tag_priority, axis=1)
    
    results = []
    
    driver = None
    
    # Limit processing for test/debug if needed, but we'll do all here
    for idx, row in df.iterrows():
        url = row['website']
        print(f"---\nProcessing {url}...")
        
        entry = row.to_dict()
        entry['primary_scraping_method'] = 'Static/Requests'
        entry['llm_evaluation'] = 'NO_DATA'
        entry['catalog_paths'] = ''
        entry['bot_protected'] = False
        entry['login_wall_detected'] = False
        
        try:
            # Step 2: Lightweight Diagnostic Ping
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            resp = requests.get(url, headers=headers, timeout=15)
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            text_content = soup.get_text(separator=' ', strip=True)
            
            bot_protected = check_bot_protection(resp.status_code, html)
            entry['bot_protected'] = bot_protected
            
            catalog_links = find_catalog_links(soup, url)
            entry['catalog_paths'] = ", ".join(catalog_links[:3])
            
            login_wall = check_login_wall(text_content)
            entry['login_wall_detected'] = login_wall
            
            # Step 3: Deep Verification
            if bot_protected or len(text_content) < 500 or "enable javascript" in text_content.lower() or "please wait" in text_content.lower():
                print(f"  Attempting Selenium for {url}")
                entry['primary_scraping_method'] = 'Dynamic/Selenium'
                if driver is None:
                    driver = setup_driver()
                try:
                    driver.get(url)
                    time.sleep(3) # Wait for DOM
                    text_content = driver.find_element(By.TAG_NAME, 'body').text
                    page_source = driver.page_source
                    soup2 = BeautifulSoup(page_source, 'html.parser')
                    catalog_links = find_catalog_links(soup2, url)
                    entry['catalog_paths'] = ", ".join(catalog_links[:3])
                except Exception as se:
                    print(f"  Selenium failed for {url}: {se}")
                    
            # Step 4: LLM Post-Processing
            if text_content and len(text_content) > 100:
                print(f"  Evaluating with LLM... (text length: {len(text_content)})")
                eval_result = evaluate_with_llm(text_content)
                entry['llm_evaluation'] = eval_result
                if login_wall and eval_result == 'VIABLE':
                    # Heuristic: if we explicitly found login wall text, demote it if LLM missed it
                    pass
            else:
                entry['llm_evaluation'] = 'NO_DATA'
                
        except requests.exceptions.RequestException as re:
            print(f"  Request Exception for {url}: {re}")
            # we can try selenium if requests absolutely fails (e.g. SSL error maybe) but usually timeout means site is dead
            entry['llm_evaluation'] = 'NO_DATA'
            entry['primary_scraping_method'] = 'Failed'
        except Exception as e:
            print(f"  Error processing {url}: {e}")
            entry['llm_evaluation'] = 'NO_DATA'
            entry['primary_scraping_method'] = 'Failed'
            
        print(f"  Result: {entry['llm_evaluation']}, Method: {entry['primary_scraping_method']}")
        results.append(entry)
        
    if driver is not None:
        driver.quit()
        
    out_df = pd.DataFrame(results)
    print(f"\nFinal Distribution of LLM Evaluations:\n{out_df['llm_evaluation'].value_counts()}")
    out_df.to_csv(output_csv, index=False)
    print(f"Done. Saved to {output_csv}")

if __name__ == "__main__":
    main()
