import os
import json
import csv
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict
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
class ProductSchema(BaseModel):
    product_name: str
    price: Optional[float]
    supplier: str
    properties: str
    certifications: List[str]
    lead_days: Optional[int]
    lead_type: Optional[str] # "stock" or "out of stock"
    years_in_business: Optional[int]
    source_url: str

def extract_text_from_pdf(local_path: str) -> str:
    """Extract text robustly from a PDF up to a reasonable number of pages."""
    if not os.path.exists(local_path):
        return ""
    text = ""
    try:
        with open(local_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            # Limit page processing to avoid breaking context window max limits unnecessarily
            for i in range(min(5, len(reader.pages))):
                page = reader.pages[i]
                found_text = page.extract_text()
                if found_text:
                    text += found_text + "\n"
    except Exception as e:
        print(f"Failed to extract {local_path}: {e}")
    return text

def process_product(product_data: dict, supplier: str) -> dict:
    original_name = product_data.get("name", "")
    original_price = product_data.get("price", "")
    url = product_data.get("url", "")
    
    docs = product_data.get("documents", {})
    certs = docs.get("certifications", [])
    tech_sheet = docs.get("technical_sheet")
    
    # Base text block
    context_text = f"Product Name: {original_name}\nPrice: {original_price}\nSupplier: {supplier}\nURL: {url}\n\n"
    
    context_text += "--- TECHNICAL SHEET ---\n"
    if tech_sheet and isinstance(tech_sheet, dict):
        tech_path = tech_sheet.get("local_path")
        if tech_path:
            context_text += extract_text_from_pdf(tech_path)
            
    context_text += "\n--- CERTIFICATIONS ---\n"
    if certs:
        for cert in certs:
            if isinstance(cert, dict):
                c_title = cert.get("title", "")
                c_path = cert.get("local_path")
                context_text += f"Cert Title: {c_title}\n"
                if c_path:
                    context_text += extract_text_from_pdf(c_path)
                    
    # Cap token length roughly
    max_len = 50000 
    if len(context_text) > max_len:
        context_text = context_text[:max_len] + "\n...[TRUNCATED]"

    prompt = (
        "You are a data extraction pipeline. You are given text and metadata for a product, "
        "including text extracted from its technical sheet and certifications PDFs.\n\n"
        "Extract the following into the precise forced JSON schema structure:\n"
        "1. product_name: Clean the original product name (e.g., 'oeghwht-html5-vitamin-c' -> 'Vitamin C').\n"
        "2. price: Parse to a float number from the string representation (ignore currency symbols).\n"
        "3. supplier: The name of the company supplying the product.\n"
        "4. properties: Look strictly in the TECHNICAL SHEET text (if provided) and extract properties (like density, pH, dimensions, limits, ingredients, etc) as a valid JSON string (e.g., '{\"density\": \"1.0\"}'). Return '{}' if there are none.\n"
        "5. certifications: Extract the names/ids of all mentioned certifications from the CERTIFICATIONS text, or technical sheet.\n"
        "6. lead_days: Provide as integer if lead time or shipping time is mentioned.\n"
        "7. lead_type: Use exactly 'stock' or 'out of stock' if mentioned.\n"
        "8. years_in_business: Find the integer number of years in business if mentioned.\n"
        "9. source_url: Use the provided URL.\n\n"
        "If you cannot find one of the fields in the provided text, leave Optional fields null, or return empty lists/dicts.\n\n"
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
            response_format=ProductSchema,
            temperature=0.1
        )
        parsed = completion.choices[0].message.parsed
        if parsed is not None:
            return parsed.model_dump()
    except Exception as e:
        print(f"Error extracting product {original_name}: {e}")
        
    return {}

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
        parsed_dict = process_product(p, supplier)
        if not parsed_dict:
            continue
            
        row = {}
        row["product_name"] = parsed_dict.get("product_name", "NONE")
        
        price = parsed_dict.get("price")
        row["price"] = price if price is not None else "NONE"
        
        row["supplier"] = parsed_dict.get("supplier", "NONE")
        
        props = parsed_dict.get("properties", "")
        row["properties"] = props if props and props != "{}" else "NONE"
        
        certs = parsed_dict.get("certifications", [])
        row["certifications"] = json.dumps(certs) if certs else "NONE"
        
        ld = parsed_dict.get("lead_days")
        row["lead_days"] = ld if ld is not None else "NONE"
        
        lt = parsed_dict.get("lead_type")
        row["lead_type"] = lt if lt else "NONE"
        
        yib = parsed_dict.get("years_in_business")
        row["years_in_business"] = yib if yib is not None else "NONE"
        
        url = parsed_dict.get("source_url")
        row["source_url"] = url if url else "NONE"
        
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
