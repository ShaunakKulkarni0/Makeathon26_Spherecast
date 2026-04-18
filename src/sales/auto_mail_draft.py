import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent

def _load_api_key() -> str:
    env_path = _ROOT / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Die .env Datei wurde nicht gefunden unter: {env_path}")

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "OpenAIAPI":
            return value.strip().strip('"').strip("'")

    raise ValueError("OPENAI_API_KEY wurde in der .env Datei nicht gefunden.")


@dataclass
class EmailInput:
    """
    Speichert alle Variablen, die das LLM für den E-Mail-Entwurf benötigt.
    """
    input_dict: Dict[str, str] = field(default_factory=dict)
    language: str = "German"
    # NEU: Liste für fehlende/unbekannte Felder
    unknown_fields: List[str] = field(default_factory=list) 


class AutoEmailDrafter:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def generate_draft(self, email_input: EmailInput) -> Optional[str]:
        system_prompt = (
            "You are an expert B2B purchasing and sourcing manager. "
            "Your task is to write highly professional, concise, and polite "
            "outreach emails to potential suppliers."
        )

        user_prompt = (
            f"Please draft a B2B sourcing email in {email_input.language}.\n\n"
            "Use the following known information to personalize the email:\n"
        )
        
        # 1. Bekannte Daten einfügen
        for key, value in email_input.input_dict.items():
            user_prompt += f"- {key.replace('_', ' ').title()}: {value}\n"

        # 2. NEU: Unbekannte Daten als Fragen an den Lieferanten formulieren
        if email_input.unknown_fields:
            user_prompt += (
                "\nWe are missing some information. Please politely ask the supplier "
                "to provide details on the following points:\n"
            )
            for field_name in email_input.unknown_fields:
                user_prompt += f"- {field_name.replace('_', ' ').title()}\n"

        user_prompt += (
            "\nRequirements:\n"
            "- Keep it professional, clear, and direct (B2B standard).\n"
            "- Integrate the questions about the missing information smoothly into the text.\n"
            "- Do not include placeholders like [Your Name] if the information is missing, "
            "just adapt the text smoothly.\n"
            "- Output ONLY the email subject and the email body. Nothing else."
        )

        try:
            response = httpx.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.4,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            
            response_data = response.json()
            draft = response_data["choices"][0]["message"]["content"].strip()
            return draft

        except Exception as exc:
            logger.error(f"Fehler bei der E-Mail-Generierung: {exc}")
            return None


if __name__ == "__main__":
    try:
        API_KEY = _load_api_key()
        drafter = AutoEmailDrafter(api_key=API_KEY)
        
        # Test-Daten inkl. unknown_fields
        daten = EmailInput(
            language="English",
            input_dict={
                "supplier_name": "Acme Ingredients GmbH",
                "product_of_interest": "Organic Vanilla Extract",
                "estimated_volume": "500 liters per month",
                "my_company_name": "SweetBakes Bakery",
                "my_name": "Max Mustermann",
            },
            unknown_fields=[
                "minimum_order_quantity", 
                "lead_time_to_germany", 
                "organic_certification_documents"
            ]
        )
        
        print("Generiere Entwurf...\n")
        print("-" * 50)
        entwurf = drafter.generate_draft(daten)
        print(entwurf)
        print("-" * 50)
        
    except Exception as e:
        print(f"Abbruch: {e}")