# Data → Comparison → *Output*
**Spherecast · Agnes AI | Layer Architecture Spec | Hackathon Build**

---

> **⚡ KERN-EINSICHT**
> Das Schlüsselproblem: **Der Output der Data Layer determiniert die Qualität jedes nachfolgenden Schritts.**
> Wenn die Comparison Layer nur noch embedden und similarity-checken soll, muss die Data Layer pro SKU eine `canonical description string` produzieren — einen einzigen, standardisierten Fließtext-String, der alles enthält was für den Vergleich relevant ist. **Nicht strukturiert. Nicht als JSON-Felder. Als natürlichsprachiger String, der fürs Embedding optimiert ist.** Zwei Strings von identischen Materialien sollen hochähnliche Embeddings ergeben — unabhängig davon wie der SKU-Name in der DB aussieht.

---

## 1 | Data Layer
*Collect · Classify · Normalize · Output Canonical Strings*

**Step 1.1 | SKU-Name Parsing**
Jeder Rohstoff-Name aus der DB wird bereinigt: Bindestriche → Leerzeichen, Abkürzungen aufgelöst, Form-Suffix extrahiert (**-hcl, -glycinate, -oxide, -l-form** etc.).
LLM-Prompt: *"What compound or ingredient does this name refer to? Extract: common name, chemical name if applicable, form/salt, branded vs generic."*

**Step 1.2 — Kritisch | Materialkategorie-Klassifikation**
**Muss zuerst passieren.** Bestimmt welche Datenquellen abgefragt werden und was überhaupt ein sinnvoller Vergleich ist.
Fünf Kategorien: Chemikalie / Botanical / Branded Ingredient / Excipient / Flavor+Color. Zero-shot LLM mit wenigen Beispielen reicht.

| Kategorie | Erkennungsmerkmale | Externe Quellen | Was ins Canonical String |
| :--- | :--- | :--- | :--- |
| **Chemikalie** | CAS-Nummer extrahierbar, IUPAC-Name vorhanden | PubChem API, CAS Registry | Molecular formula, CAS, MolWeight, Solubility, Form/Salt |
| **Botanical** | Pflanzengattung erkennbar, "extract", "powder", Standardisierungsprozente | Supplier-Websites, AHPA DB | Genus/Species, Part used, Extraction ratio, Active marker, Standardization % |
| **Branded** | Eigenname (Großbuchstaben), Hersteller-Claim, Patenthinweis | Hersteller-Website, Patentdatenbanken | Brand owner, Proprietary blend claim, Functional claim, Substitution: never |
| **Excipient** | "capsule", "coating", "filler", "flow agent" | USP/EP Pharmacopeia, Supplier-Kataloge | Function class, Pharmacopeia grade, Vegetal/animal origin, Regulatory status |
| **Flavor/Color** | "flavor", "colour", E-Nummer, FEMA GRAS | FEMA DB, EU Regulation | FEMA number, E-number, Natural/Artificial, Regulatory region |

### Output der Data Layer — Canonical Description String (ein String pro SKU)

* **vitamin-d3-cholecalciferol:** Cholecalciferol (Vitamin D3). Chemical. CAS 67-97-0. Molecular formula C27H44O. Fat-soluble secosteroid. Naturally derived from lanolin or lichen. Form: powder. Function: vitamin D source, bone metabolism, immune support. Bioavailability: high. Regulatory: USP grade available. Common supplier names: vitamin D3, cholecalciferol, vitamin-d3-cholecalciferol.
* **cholecalciferol (Prinova):** Cholecalciferol (Vitamin D3). Chemical. CAS 67-97-0. Molecular formula C27H44O. Fat-soluble secosteroid. Lanolin-derived. Form: powder or oil. Function: vitamin D supplementation, calcium absorption support. Bioavailability: high. Regulatory: FCC/USP. Supplier: Prinova USA.
* **magnesium-glycinate:** Magnesium bisglycinate chelate. Chemical. CAS 14783-68-7. Magnesium chelated with glycine amino acid. Form: powder. Function: magnesium source, muscle relaxation, sleep support. Bioavailability: very high (chelate form). Elemental Mg content ~14%. Regulatory: generally recognized as safe. Note: high bioavailability distinguishes from oxide form.
* **magnesium-oxide:** Magnesium oxide. Chemical. CAS 1309-48-4. Inorganic magnesium salt. Form: powder. Function: magnesium source, antacid. Bioavailability: low (15-20%). Elemental Mg content ~60%. Regulatory: USP/FCC. Cost: low. Note: high Mg content by weight but poor absorption compared to chelate forms.

> **Warum ein String und kein JSON?** Embedding-Modelle wurden auf natürlichsprachige Texte trainiert. Ein String wie "Cholecalciferol. Fat-soluble. CAS 67-97-0. Lanolin-derived. Vitamin D source." erzeugt ein semantisch reiches Embedding. Ein JSON-Objekt mit denselben Feldern erzeugt ein wesentlich schwächeres, weil die Beziehungen zwischen Feldern im Latent Space verloren gehen.

---

**↓**
**Output: Ein canonical string pro SKU · gespeichert in DB**
**↓**

---

## 2 | Comparison Layer
*Embed · Similarity · Score · Flag*

Diese Layer tut genau drei Dinge: Strings embedden, Similarity berechnen, Confidence-Level + Compliance-Flags setzen. Sie braucht kein externes Wissen mehr — das wurde vollständig in die Data Layer ausgelagert.

### Flow
1.  **2.1 Batch Embed:** Alle canonical strings → text-embedding-3-large (3072-dim). Einmalig, gecacht.
2.  **2.2 ANN Search:** FAISS / pgvector: für jede SKU top-k Kandidaten (k=10–20). Schnell, kein paarweises O(n²).
3.  **2.3 Similarity Score:** Cosine similarity pro Paar. Grob-Filter: score < 0.65 → kein Match.
4.  **2.4 LLM Verification:** Nur für score ≥ 0.65: LLM-as-Judge mit beiden Strings → confidence + flags.
5.  **2.5 Store Result:** Match-Tabelle: (sku_a, sku_b, confidence, flags, reasoning) → DB.

### Score Matrix

| Confidence Level | Schwellenwert & Kriterien | Agnes-Empfehlung |
| :--- | :--- | :--- |
| ● **Exact** | cos ≥ 0.92 + gleiche CAS / gleiche Funktion + LLM bestätigt identisch | Sofortige Konsolidierung. Gemeinsamer RFQ. Keine Compliance-Prüfung nötig. |
| ● **Functional** | cos 0.78–0.92 + gleiche Funktion + unterschiedliche Form/Salt + LLM: "austauschbar mit Einschränkungen" | Substitution möglich. Compliance-Flags prüfen: Bioavailability-Delta, Labeling-Impact, Vegan-Status. |
| ● **Category** | cos 0.65–0.78 + gleiche Produktfunktion aber verschiedene Chemie + LLM: "nur mit Reformulierung" | Nicht direkt austauschbar. Flag für Produktmanager. Langfristige Sourcing-Konsolidierung möglich. |

### Compliance Flags — Was der LLM-Judge zusätzlich prüft
*(aus den Canonical Strings extrahiert)*

* **VEGAN_CONFLICT:** Eines der Materialien ist animal-derived (gelatin, lanolin-D3), das andere nicht. Substitution erfordert Label-Änderung.
* **BIOAVAILABILITY_DELTA:** Signifikanter Unterschied in Absorption (z.B. Mg-oxide 15% vs. Mg-glycinate 80%). Dosierungsanpassung nötig.
* **LABELING_CLAIM_IMPACT:** Austausch würde bestehende On-Label Claims (z.B. "highly bioavailable magnesium") ungültig machen.
* **BRANDED_NO_SUB:** Eines der Materialien ist ein Branded Ingredient (EpiCor, Albion Chelate). Keine Substitution ohne Lizenz.

---

**↓**
**Output: Match-Tabelle mit Confidence + Flags · pro Paar**
**↓**

---

## 3 | Output Layer
*Cluster · Rank · Recommend · Explain*

* **3.1 — Consolidation Groups (Clustering):** Alle "Exact"-Matches → ein Cluster. Graph-Komponenten-Analyse auf der Match-Tabelle. Ergebnis: "Diese 3 SKUs von 4 Unternehmen sind dasselbe Material."
* **3.2 — Best Supplier per Cluster (Supplier Ranking):** Pro Cluster: welcher Supplier beliefert bereits die meisten Unternehmen? Welches Preisband? Volumen-Schätzung. Ranking: Coverage × Price × Compliance-Score.
* **3.3 — Erwartete Einsparung (Savings Estimate):** Δ zwischen Einzelpreis-Schätzung und Volumenpreis-Schätzung. Konservativ modelliert: 8–15% für Exact-Matches typisch bei Supplement-Rohstoffen.

### Output Schema pro Recommendation

```json
// Agnes Sourcing Recommendation Object
{
  "cluster_id": "VIT-D3-001",
  "confidence_level": "exact",
  "canonical_material": "Cholecalciferol (Vitamin D3) · CAS 67-97-0",

  "affected_companies": [
    { "company": "A", "sku": "vitamin-d3-cholecalciferol", "supplier": "PureBulk" },
    { "company": "B", "sku": "cholecalciferol",            "supplier": "Prinova USA" },
    { "company": "C", "sku": "vitamin-d3",                 "supplier": "Prinova USA" }
  ],

  "recommended_supplier": "Prinova USA",
  "recommendation_rationale": "Already supplies 2 of 3 companies. Volume consolidation achievable immediately.",

  "compliance_flags": ["VEGAN_CONFLICT: lanolin-derived — verify against vegan product lines"],
  "compliance_safe": true,  // true for exact matches unless flag triggered

  "estimated_savings_pct": 12,
  "combined_volume_units": "~4,200 kg/year (estimated)",

  "similarity_score": 0.97,
  "reasoning": "All three SKUs resolve to the same compound (CAS 67-97-0). Naming variation is purely cosmetic. Safe to consolidate purchasing immediately."
}
```

---

## Implementierungshinweise

**FÜR DEN HACKATHON — WAS ZUERST BAUEN**
1. **Data Layer:** Prompt-Template für Canonical String schreiben. Alle 143 Problem-Ingredienzien durchlaufen lassen.
2. **Comparison Layer:** Alle Strings embedden (OpenAI batch API), paarweise Similarity für bekannte Polypropylene-Demo berechnen.
3. **Output Layer:** Für Top-5 Cluster eine Agnes-Recommendation generieren.
**Das reicht für eine überzeugende Demo.**

**DIE EINE SACHE DIE ALLES ENTSCHEIDET**
Die Qualität des **Canonical String Prompts** in der Data Layer. Wenn dieser Prompt konsequent dieselben semantischen Informationen für dasselbe Material produziert — unabhängig vom Input-SKU-Namen — dann ist der Rest fast trivial.
Testet diesen Prompt an den bekannten Vitamin-D3 / Vitamin-C Dubletten und verifiziert dass die generierten Strings hochähnliche Embeddings erzeugen.

---
*Spherecast × Agnes AI — 3-Layer Architecture Spec | Data Layer → Comparison Layer → Output Layer*