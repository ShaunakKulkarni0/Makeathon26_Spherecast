import json
import csv
import sys
import os

def extract_to_csv(input_json_path, output_csv_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    supplier = data.get("supplier", "NONE")
    products = data.get("products", [])
    
    # Target exact columns from data/extracted_capsuline_products.csv
    columns = [
        "product_name", "price", "supplier", "properties", 
        "certifications", "lead_days", "lead_type", 
        "years_in_business", "source_url"
    ]
    
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        
        for p in products:
            product_name = p.get("name", "NONE")
            if not product_name:
                product_name = "NONE"
                
            # Prefer price per gram ("price"), fallback to starting price
            price = p.get("price")
            if price is None:
                price = p.get("starting_price", "NONE")
                
            certs = p.get("certification_tags", [])
            if not certs:
                certs_str = "NONE"
            else:
                certs_str = json.dumps(certs)
                
            source_url = p.get("url", "NONE")
            if not source_url:
                source_url = "NONE"
            
            row = {
                "product_name": product_name,
                "price": price,
                "supplier": supplier,
                "properties": "NONE",
                "certifications": certs_str,
                "lead_days": "NONE",
                "lead_type": "NONE",
                "years_in_business": "NONE",
                "source_url": source_url
            }
            writer.writerow(row)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_data_structured.py <input_json> <output_csv>")
        sys.exit(1)
        
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    extract_to_csv(in_path, out_path)
    print(f"Extracted structured data from {in_path} to {out_path}")
