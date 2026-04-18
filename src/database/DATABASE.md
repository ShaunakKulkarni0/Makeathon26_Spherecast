***

# SYSTEM ARCHITECTURE SPECIFICATION: Spherecast Layer 1 & 2
**Context:** We are building an AI-driven material consolidation pipeline for supply chain and procurement. We process raw, messy SKU names from different companies, normalize them, embed them, and match them based on chemical and functional semantic similarity.
**Tech Stack Core:** OpenAI API (used for both LLM reasoning and Embeddings), Relational DB (e.g., PostgreSQL), Vector DB (e.g., pgvector).

---

## LAYER 1: DATA LAYER (Normalization & Canonical String Generation)
**Goal:** Transform a messy raw SKU string into a standardized, semantic "Canonical String" that explicitly resolves implicit domain knowledge (CAS numbers, bioavailability, dosage, chiral forms) to prepare it for high-quality embedding.

### 1.1 API Configuration
* **Provider:** OpenAI
* **Endpoint:** `https://api.openai.com/v1/chat/completions`
* **Model:** `gpt-4o` (or `gpt-4o-mini` for speed/cost optimization)
* **Authentication:** Bearer token (OpenAI API Key)
* **Response Format:** `{"type": "json_object"}`

### 1.2 The LLM System Prompt (Data Layer)
Use the following strict system prompt to instruct the LLM on how to parse the SKU:

```text
You are an expert chemical and supply chain data normalizer. 
Your task is to analyze a raw material/SKU name, classify it into one of 7 categories, and generate a "Canonical Description String".

Categories:
1. Chemical (has CAS/IUPAC)
2. Botanical (plant-derived, extracts)
3. Bioactive (probiotics, enzymes - metric is CFU or activity units like GDU)
4. Branded (proprietary ingredients, e.g., "Albion TRAACS")
5. Excipient (fillers, capsules, coatings)
6. Flavor/Color (E-numbers, FEMA)
7. Blend/Premix (mixture of multiple ingredients)

RULES FOR THE CANONICAL STRING:
- It must be a continuous natural language paragraph. DO NOT output a JSON stringified object inside this field.
- HARD EXTRACTION: You MUST explicitly state any numbers, dosages (mg, %), and chiral forms (L- vs. D-) in the string.
- If Chemical: Include CAS number, molecular formula, form (salt/chelate/oxide), and general bioavailability.
- If Branded: Explicitly state "Substitution: never without license".
- If Bioactive: Explicitly state the strain or activity unit.

Output STRICTLY in the following JSON schema:
{
  "category": "Chemical | Botanical | Bioactive | Branded | Excipient | Flavor/Color | Blend/Premix | Unknown",
  "extracted_entities": {
    "cas_number": "string or null",
    "dosage_or_concentration": "string or null",
    "chiral_form": "string or null"
  },
  "canonical_string": "The generated continuous text paragraph."
}
```

### 1.3 Data Flow & Storage
1. Retrieve raw `sku_name` and `sku_id` from the relational DB.
2. Send to OpenAI Chat API using the prompt above.
3. Save the resulting `canonical_string` to the relational DB, linked to `sku_id`.

---

## LAYER 2: COMPARISON LAYER (Embedding, Vector Search & LLM Judge)
**Goal:** Embed the Canonical Strings, perform an Approximate Nearest Neighbor (ANN) search to find candidates, and use an LLM to definitively score and flag the matches.

### Step 2.1: Batch Embedding
* **Endpoint:** `https://api.openai.com/v1/embeddings`
* **Model:** `text-embedding-3-large`
* **Dimensions:** 3072
* **Payload Example:**
    ```json
    {
      "input": "<canonical_string_from_layer_1>",
      "model": "text-embedding-3-large"
    }
    ```
* **Action:** Store the returned 3072-dimensional vector array in the Vector DB (e.g., pgvector column) alongside the `sku_id`.

### Step 2.2: Vector Search & Thresholding
* **Action:** For a given target `sku_id` vector, perform a Cosine Similarity search against all other vectors in the database.
* **Limit:** Retrieve Top-K candidates (e.g., K=15).
* **Hard Filter:** Drop any candidate where `cosine_similarity < 0.65`.

### Step 2.3: LLM Judge (Verification & Flagging)
For every candidate pair that passed the `0.65` threshold, make an LLM call to act as the final judge.

* **Endpoint:** `https://api.openai.com/v1/chat/completions`
* **Model:** `gpt-4o`
* **Response Format:** `{"type": "json_object"}`

**LLM Judge System Prompt:**
```text
You are an expert procurement verification AI. 
I will provide you with TWO canonical description strings representing raw materials.
Your job is to determine if they are the exact same material, functionally substitutable, or just in the same category.

Evaluate based on:
1. Chemistry/CAS (must match for Exact)
2. Dosage/Concentration (if one is 1mg and the other 10mg, they are NOT exact)
3. Chiral forms (L- vs D- are completely different)
4. Branded vs. Generic (cannot substitute branded without flag)

Define the Confidence Level:
- "Exact": Identical chemical and function. Safe to consolidate.
- "Functional": Same function, different form (e.g., Magnesium Citrate vs Magnesium Oxide).
- "Category": Same product family, but requires formulation change.
- "No Match": Different materials.

Check for Compliance Flags (return as array of strings, or empty array):
- "VEGAN_CONFLICT" (animal vs plant derived)
- "BIOAVAILABILITY_DELTA" (different absorption rates)
- "LABELING_CLAIM_IMPACT" (changes label claims)
- "BRANDED_NO_SUB" (one is a protected brand)

Output STRICTLY in the following JSON schema:
{
  "confidence_level": "Exact | Functional | Category | No Match",
  "reasoning": "1-2 sentences explaining why.",
  "compliance_flags": ["FLAG_1", "FLAG_2"]
}
```

### 2.4 Final Output Storage
Store the result of Step 2.3 in a `matches` table in the relational DB:
* `sku_id_a` (Foreign Key)
* `sku_id_b` (Foreign Key)
* `cosine_similarity` (Float, from Step 2.2)
* `confidence_level` (String, from Step 2.3)
* `compliance_flags` (JSON Array, from Step 2.3)
* `reasoning` (Text, from Step 2.3)