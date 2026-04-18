import sys
import logging
from src.crawling.crawling_entry import SEARCH_ROUTING_MAP

logging.basicConfig(level=logging.ERROR)

test_data = {
    "Capsuline": ["Empty Gelatin Capsules (Size 00)"],
    "Colorcon": ["Opadry® Film Coating Systems"],
    "Custom Probiotics": ["High Potency Probiotic Powders"],
    "Darling Ingredients / Rousselot": ["Peptan® Collagen Peptides"],
    "Icelandirect": ["Norwegian Salmon Oil"],
    "Ingredion": ["PureCircle™ Stevia Solutions"],
    "Jost Chemical": ["Ultra Pure Magnesium Citrate"],
    "Koster Keunen": ["Natural Yellow Beeswax"],
    "Nutra Food Ingredients": ["Bovine Collagen Peptides"],
    "PureBulk": ["N-Acetyl L-Cysteine (NAC) Powder"],
    "Sensient": ["Natural Red/Yellow Food Colors"],
    "Source-Omega LLC": ["Algal DHA Oil"],
    "Strahl & Pitsch": ["Beeswax (USP/NF/EP Monograph)"],
    "Trace Minerals": ["ConcenTrace Trace Mineral Drops"]
}

for supplier, queries in test_data.items():
    print(f"\n--- Testing {supplier} ---")
    func = SEARCH_ROUTING_MAP.get(supplier)
    if func:
        try:
            for query in queries:
                print(f"Searching for: '{query}'")
                results = func(query)
                if results is None:
                    print(f"Returned None")
                elif len(results) == 0:
                    print("Returned 0 results (or no functional endpoint).")
                else:
                    print(f"Found {len(results)} results:")
                    for idx, res in enumerate(results[:3]):
                        print(f"  {idx+1}. {res.get('product_name')} -> {res.get('product_url')}")
                    if len(results) > 3:
                        print(f"  ...and {len(results)-3} more.")
        except Exception as e:
            print(f"Exception during testing {supplier}: {e}")
    else:
        print(f"No entry found in SEARCH_ROUTING_MAP for {supplier}")

