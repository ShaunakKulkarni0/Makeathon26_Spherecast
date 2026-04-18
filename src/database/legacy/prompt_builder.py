# Data Layer/prompt_builder.py

"""
Baut den Normalisierungs-Prompt dynamisch aus dem entdeckten Schema.
"""
from __future__ import annotations
import json

# Dieser Teil ist generisch und bleibt immer gleich
_STATIC_BASE = """\
You are a raw material data normalizer for supply chain deduplication.

IGNORE internal codes: prefixes like "RM-C1-", "MAT-", "ING-" and hex suffixes like "-67efce0f".
Focus ONLY on the actual material name.

Your output is a CANONICAL STRING used to detect duplicate/substitutable SKUs.
The canonical string must be pipe-separated key attributes: "attr1 | attr2 | attr3"
Omit unknown attributes. No sentences, no filler words.

UNIVERSAL RULES (apply to any dataset):
- Always be MORE specific than the input, never less
- If a form/variant is ambiguous, mark it as "(unspecified)" rather than omitting
- Preserve every number, unit, and qualifier present in the original name
- Never merge semantically different concepts even if names are similar

You MUST respond with ONLY valid JSON — no markdown, no prose:
{
  "category": "<category>",
  "extracted_entities": {
    "cas_number": "<string or null>",
    "dosage_or_concentration": "<string or null>",
    "chiral_form": "<string or null>"
  },
  "canonical_string": "<pipe-separated string>"
}
"""

def build_normalization_prompt(schema: dict | None) -> str:
    """
    Kombiniert den statischen Base-Prompt mit dynamisch
    abgeleiteten Regeln aus dem Schema-Discovery.
    """
    if schema is None:
        # Fallback: nur generische Regeln
        return _STATIC_BASE + "\nCategories: Chemical | Botanical | Bioactive | Branded | Excipient | Flavor/Color | Blend/Premix | Unknown"
    
    sections = [_STATIC_BASE]
    
    # Dataset-spezifischer Kontext
    sections.append(f"""
DATASET CONTEXT:
This database contains: {schema.get('dataset_domain', 'unknown domain')}
Regulatory context: {schema.get('regulatory_context', 'not determined')}
""")
    
    # Kritische Dimensionen die das LLM selbst entdeckt hat
    if schema.get("critical_dimensions"):
        sections.append("CRITICAL DIMENSIONS TO EXTRACT (discovered from this dataset):")
        for dim in schema["critical_dimensions"]:
            sections.append(
                f"- {dim['dimension']}: {dim['extraction_instruction']}"
                f"\n  Why critical: {dim['why_critical']}"
            )
    
    # Bekannte Ambiguitäten aus dieser Datenbank
    if schema.get("common_ambiguities"):
        sections.append("\nKNOWN AMBIGUITIES IN THIS DATASET — resolve as follows:")
        for amb in schema["common_ambiguities"]:
            sections.append(
                f"- Pattern '{amb['ambiguous_pattern']}': {amb['resolution_rule']}"
            )
    
    # Allergen-Hinweis wenn relevant
    if schema.get("allergen_relevant"):
        sections.append(
            "\nALLERGEN SOURCES: This dataset is allergen-relevant. "
            "Always extract and include the biological source "
            "(e.g. soy, sunflower, dairy, fish) as a canonical string attribute."
        )
    
    # Kategorien aus dem Schema selbst ableiten
    if schema.get("critical_dimensions"):
        sections.append("\nCategories: Chemical | Botanical | Bioactive | Branded | Excipient | Flavor/Color | Blend/Premix | Unknown")
    
    return "\n".join(sections)