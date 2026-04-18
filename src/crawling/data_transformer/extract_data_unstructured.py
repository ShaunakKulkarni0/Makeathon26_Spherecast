import os
import json
import csv
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import pypdf

# Load env variables
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY_Dibbo")

if not API_KEY:
    raise ValueError("OPENAI_API_KEY_Dibbo is not set in .env. Please set it to run the script.")

client = OpenAI(api_key=API_KEY)

# Define schemas for Structured Outputs

class ProductCoreSchema(BaseModel):
    product_name: str
    price: Optional[float]
    supplier: str
    lead_days: Optional[int]
    lead_type: Optional[str] # "stock" or "out of stock"
    years_in_business: Optional[int]
    source_url: str

class ProductPropertiesSchema(BaseModel):
    properties: str

class CertificationSchema(BaseModel):
    dietary: List[str]
    compliance: List[str]
    safety: List[str]
    quality: List[str]

def extract_text_from_pdf(local_path: str) -> str:
    """Extract text robustly from a PDF up to a reasonable number of pages."""
    if not os.path.exists(local_path):
        return ""
    text = ""
    try:
        with open(local_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for i in range(min(5, len(reader.pages))):
                page = reader.pages[i]
                found_text = page.extract_text()
                if found_text:
                    text += found_text + "\n"
    except Exception as e:
        print(f"Failed to extract {local_path}: {e}")
    return text

def extract_core_info(product_data: dict, supplier: str) -> dict:
    original_name = product_data.get("name", "")
    original_price = product_data.get("price", "")
    url = product_data.get("url", "")
    
    context_text = f"Product Name: {original_name}\nPrice: {original_price}\nSupplier: {supplier}\nURL: {url}\n"
    
    prompt = (
        "You are a data extraction pipeline. You are given basic metadata for a product.\n"
        "Extract the following into the precise forced JSON schema structure:\n"
        "1. product_name: Clean the original product name (e.g., 'oeghwht-html5-vitamin-c' -> 'Vitamin C'). Do NOT include quantities or box sizes.\n"
        "2. price: Parse to a float number from the string representation (ignore currency symbols).\n"
        "3. supplier: The name of the company supplying the product.\n"
        "4. lead_days: Provide as integer if lead time or shipping time is mentioned. Otherwise null.\n"
        "5. lead_type: Use exactly 'stock' or 'out of stock' if mentioned. Otherwise null.\n"
        "6. years_in_business: Find the integer number of years in business if mentioned. Otherwise null.\n"
        "7. source_url: Use the provided URL.\n\n"
        "DATA TO EXTRACT:\n\n"
        f"{context_text}"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a highly precise data parsing assistant."},
                {"role": "user", "content": prompt}
            ],
            response_format=ProductCoreSchema,
            temperature=0.1
        )
        parsed = completion.choices[0].message.parsed
        if parsed is not None:
            return parsed.model_dump()
    except Exception as e:
        print(f"Error extracting core info for {original_name}: {e}")
    return {}

def extract_properties(tech_sheet_path: str) -> str:
    text = extract_text_from_pdf(tech_sheet_path)
    if not text.strip():
        return "{}"
        
    # Cap token length roughly
    max_len = 50000 
    if len(text) > max_len:
        text = text[:max_len] + "\n...[TRUNCATED]"

    prompt = (
        "Extract technical properties from the following sheet. "
        "Extract properties (like density, pH, dimensions, limits, ingredients, etc) "
        "as a valid JSON format string (e.g., '{\"density\": \"1.0\"}'). Return '{}' if there are none.\n\n"
        "TEXT:\n"
        f"{text}"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract technical document properties efficiently."},
                {"role": "user", "content": prompt}
            ],
            response_format=ProductPropertiesSchema,
            temperature=0.1
        )
        parsed = completion.choices[0].message.parsed
        if parsed is not None:
            return parsed.properties
    except Exception as e:
        print(f"Error extracting properties: {e}")
    return "{}"

def extract_certifications(coa_pdf_path: str) -> list:
    text = extract_text_from_pdf(coa_pdf_path)
    if not text.strip():
        return []
        
    max_len = 50000 
    if len(text) > max_len:
        text = text[:max_len] + "\n...[TRUNCATED]"

    prompt = (
        "Task: Act as a Quality Assurance Auditor. Analyze the provided Certificate of Analysis (COA) for a dietary supplement ingredient and extract all applicable product certifications and safety tags.\n\n"
        "Instructions:\n"
        "Search for Regulatory Standards: Identify mentions of USP, EP, JP, or FDA GRAS status.\n"
        "Extract Dietary Certifications: Look for explicit mentions of Kosher, Halal, Vegan, or Vegetarian status.\n"
        "Identify \"Free-From\" Claims: Check for statements regarding preservatives, allergens (Soy, Dairy, Gluten), GMOs, or BSE/TSE.\n"
        "Verify Microbiological Safety: Tag as \"Microbiologically Tested\" if E. coli, Salmonella, or other pathogens are listed as \"Absence\".\n\n"
        "Output Format (Official Tags Only):\n"
        "Dietary: [List tags like: VEGAN, VEGETARIAN, KOSHER, HALAL]\n"
        "Compliance: [List tags like: USP-GRADE, EP-COMPLIANT, FDA-GRAS]\n"
        "Safety: [List tags like: PRESERVATIVE-FREE, BSE/TSE-FREE, NON-GMO, ALLERGEN-FREE]\n"
        "Quality: [List tags like: MICROBIOLOGICALLY-TESTED, PASSES-DISINTEGRATION]\n\n"
        "TEXT:\n"
        f"{text}"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract compliance and certification tags into strict lists."},
                {"role": "user", "content": prompt}
            ],
            response_format=CertificationSchema,
            temperature=0.1
        )
        parsed = completion.choices[0].message.parsed
        if parsed is not None:
            # Combine all tags into one flat list
            all_tags = []
            all_tags.extend(parsed.dietary)
            all_tags.extend(parsed.compliance)
            all_tags.extend(parsed.safety)
            all_tags.extend(parsed.quality)
            return all_tags
    except Exception as e:
        print(f"Error extracting certifications: {e}")
    return []

def main(input_json: str, output_csv: str):
    if not os.path.exists(input_json):
        print(f"File not found: {input_json}")
        return

    with open(input_json, "r") as f:
        data = json.load(f)
        
    supplier = data.get("supplier", "Unknown")
    products = data.get("products", [])
    
    extracted_rows = []
    
    for i, p in enumerate(products):
        print(f"Processing product {i+1}/{len(products)}: {p.get('name')}")
        
        # 1. Extract core data
        core_dict = extract_core_info(p, supplier)
        if not core_dict:
            continue
            
        row = {}
        row["product_name"] = core_dict.get("product_name", "NONE")
        price = core_dict.get("price")
        row["price"] = price if price is not None else "NONE"
        row["supplier"] = core_dict.get("supplier", "NONE")
        ld = core_dict.get("lead_days")
        row["lead_days"] = ld if ld is not None else "NONE"
        lt = core_dict.get("lead_type")
        row["lead_type"] = lt if lt else "NONE"
        yib = core_dict.get("years_in_business")
        row["years_in_business"] = yib if yib is not None else "NONE"
        url = core_dict.get("source_url")
        row["source_url"] = url if url else "NONE"
        
        # 2. Extract properties
        props_str = ""
        docs = p.get("documents", {})
        tech_sheet = docs.get("technical_sheet")
        if tech_sheet and isinstance(tech_sheet, dict):
            tech_path = tech_sheet.get("local_path")
            if tech_path:
                props_str = extract_properties(tech_path)
                
        row["properties"] = props_str if props_str and props_str != "{}" else "NONE"
        
        # 3. Extract certifications from COA
        certs_list = []
        certs = docs.get("certifications", [])
        for c in certs:
            if isinstance(c, dict):
                title = c.get("title", "").lower()
                c_path = c.get("local_path")
                # Look for COA in title
                if "coa" in title and c_path:
                    certs_found = extract_certifications(c_path)
                    certs_list.extend(certs_found)
                    
        # Remove duplicates if multiple COAs processed
        certs_list = list(set(certs_list))
        row["certifications"] = json.dumps(certs_list) if certs_list else "NONE"
        
        extracted_rows.append(row)
        
    if not extracted_rows:
        print("No valid rows were extracted.")
        return
        
    columns = ["product_name", "price", "supplier", "properties", "certifications", 
               "lead_days", "lead_type", "years_in_business", "source_url"]
               
    print(f"Writing to {output_csv}")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(extracted_rows)
        
    print("Extraction complete.")

if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data/capsuline_crawler_output.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data/extracted_capsuline_products.csv"
    main(input_file, output_file)
