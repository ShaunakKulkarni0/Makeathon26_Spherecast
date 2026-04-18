import os
import json
import logging
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from src.crawling.crawling_entry import search_purebulk
from src.crawling.crawler.purebulk import run_purebulk_deep_crawl

logger = logging.getLogger(__name__)

CACHE_FILE = "data/purebulk_query_cache.json"

def get_synonyms_from_gpt(group_name: str, api_key: str) -> list:
    """Uses GPT-4o-mini to generate synonyms for purebulk catalog."""
    if not api_key:
        logger.warning(f"No OpenAI API Key found, skipping synonyms for {group_name}")
        return []
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a specialized search dictionary. The user gives you a compound or product group. Provide EXACTLY 3 highly relevant synonyms, specific versions, or alternative names that would successfully match an item on a website selling wholesale vitamins, dietary supplements, and bulk powders (like PureBulk). Only output those 3 strings separated strictly by commas. Nothing else."
                },
                {
                    "role": "user",
                    "content": group_name
                }
            ],
            temperature=0.3
        )
        msg = response.choices[0].message.content.strip()
        synonyms = [s.strip() for s in msg.split(",") if s.strip()]
        return synonyms[:3]
    except Exception as e:
        logger.error(f"Failed GPT inference for {group_name}: {e}")
        return []


def process_targets(csv_path: str):
    df = pd.read_csv(csv_path)
    
    # Filter for PureBulk
    targets_df = df[df['supplier_names'].str.contains('purebulk', case=False, na=False)]
    unique_groups = targets_df['group_name'].str.lower().str.strip().unique().tolist()
    
    logger.info(f"Identified {len(unique_groups)} unique product groups related to PureBulk.")
    
    # Init Cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

    # Load Env
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    for i, group in enumerate(unique_groups):
        logger.info(f"[{i+1}/{len(unique_groups)}] Processing '{group}'...")

        if group in cache:
            logger.info(f"'{group}' is already cached. Skipping search execution.")
            continue
            
        results = search_purebulk(group)
        used_synonym = None
        
        # Fallback Logic
        if not results:
            logger.info(f"0 results for '{group}'. Fetching synonyms...")
            synonyms = get_synonyms_from_gpt(group, api_key)
            for syn in synonyms:
                logger.info(f"Trying synonym: '{syn}'")
                res = search_purebulk(syn)
                if res:
                    results = res
                    used_synonym = syn
                    logger.info(f"Synonym '{syn}' yielded {len(results)} matches!")
                    break

        cache[group] = {
            "query": group,
            "results": results,
            "synonym_used": used_synonym
        }
        
        # Save cache dynamically
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    logger.info("Search phase complete. Compiling unique URLs for deep crawl...")
    
    unique_urls = set()
    for grp, data in cache.items():
        for res in data.get("results", []):
            url = res.get("product_url")
            if url:
                unique_urls.add(url.split("?")[0])

    if unique_urls:
        logger.info(f"Dispatching deep crawl for {len(unique_urls)} total unique distinct urls.")
        # We pass search_queries=[] because we're relying entirely on product_urls
        run_purebulk_deep_crawl(
            search_queries=[],
            output_json_path="data/purebulk_crawler_output.json",
            product_urls=list(unique_urls)
        )
    else:
        logger.info("No unique URLs found to crawl.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process_targets("compound_groups.csv")
