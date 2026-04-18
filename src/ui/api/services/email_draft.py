from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


@dataclass
class DraftContext:
    supplier_name: str
    seller_email: str
    seller_website: str
    material_name: str
    material_id: str
    issue_summary: str
    missing_information: list[str]
    prohibited_allergens: list[str]
    destination_country: str


def _as_clean_str(value: Any) -> str:
    return str(value or "").strip()


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_context(payload: dict[str, Any]) -> DraftContext:
    return DraftContext(
        supplier_name=_as_clean_str(payload.get("supplier_name")),
        seller_email=_as_clean_str(payload.get("seller_email")),
        seller_website=_as_clean_str(payload.get("seller_website")),
        material_name=_as_clean_str(payload.get("material_name")),
        material_id=_as_clean_str(payload.get("material_id")),
        issue_summary=_as_clean_str(payload.get("issue_summary")) or "Missing allergen details",
        missing_information=_as_str_list(payload.get("missing_information")),
        prohibited_allergens=_as_str_list(payload.get("prohibited_allergens")),
        destination_country=_as_clean_str(payload.get("destination_country")) or "Germany",
    )


def _fallback_draft(context: DraftContext) -> dict[str, str]:
    subject = f"Request for Allergen Information - {context.material_name or 'Material'}"
    lines = [
        "Dear Sales Team,",
        "",
        (
            f"I am reaching out regarding your material {context.material_name or 'from your catalog'}"
            + (f" ({context.material_id})" if context.material_id else "")
            + "."
        ),
        f"We need additional clarification before finalizing sourcing for delivery to {context.destination_country}.",
        "",
        "Could you please share the following details:",
    ]

    requested = context.missing_information or [
        "Complete allergen declaration",
        "Cross-contamination / may-contain statement",
        "Latest specification sheet or certificate",
    ]
    for item in requested:
        lines.append(f"- {item}")

    if context.prohibited_allergens:
        lines.extend(
            [
                "",
                "Our prohibited allergens are:",
                f"- {', '.join(context.prohibited_allergens)}",
            ]
        )

    lines.extend(
        [
            "",
            "If available, please also share the relevant specification or compliance documents.",
            "",
            "Thank you in advance for your support.",
            "Best regards,",
        ]
    )

    body = "\n".join(lines)
    return {"subject": subject, "body": body}


def _extract_subject_and_body(content: str, fallback_subject: str) -> dict[str, str]:
    text = content.strip()
    subject = fallback_subject
    body = text

    for line in text.splitlines():
        lower = line.lower().strip()
        if lower.startswith("subject:"):
            subject = line.split(":", 1)[1].strip() or fallback_subject
            body = "\n".join(text.splitlines()[1:]).strip() or text
            break

    return {"subject": subject, "body": body}


def generate_email_draft(payload: dict[str, Any]) -> dict[str, Any]:
    context = _build_context(payload)
    fallback = _fallback_draft(context)

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OpenAIAPI")
    model = os.getenv("EMAIL_DRAFT_MODEL", "gpt-4o-mini")

    if not api_key:
        return {
            **fallback,
            "full_draft": f"Subject: {fallback['subject']}\n\n{fallback['body']}",
            "provider": "template",
        }

    missing_points = context.missing_information or [
        "Complete allergen declaration",
        "Cross-contamination / may-contain statement",
        "Latest specification sheet or certificate",
    ]
    prohibited = ", ".join(context.prohibited_allergens) if context.prohibited_allergens else "none specified"

    user_prompt = (
        "Create a concise, professional English supplier email draft.\n"
        "Output format:\n"
        "Subject: ...\n"
        "<blank line>\n"
        "<email body>\n\n"
        f"Supplier: {context.supplier_name or 'Unknown supplier'}\n"
        f"Seller email (if known): {context.seller_email or 'not available'}\n"
        f"Seller website (if known): {context.seller_website or 'not available'}\n"
        f"Material: {context.material_name or 'N/A'} ({context.material_id or 'N/A'})\n"
        f"Issue summary: {context.issue_summary}\n"
        f"Destination country: {context.destination_country}\n"
        f"Prohibited allergens: {prohibited}\n"
        "Information still missing:\n"
        + "\n".join(f"- {item}" for item in missing_points)
        + "\n\n"
        "Tone: polite, practical, B2B procurement style. "
        "Ask clearly for the missing information and relevant documents."
    )

    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a sourcing manager assistant for B2B ingredient procurement. "
                            "Write clear supplier outreach emails."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_subject_and_body(content, fallback["subject"])
        return {
            **parsed,
            "full_draft": f"Subject: {parsed['subject']}\n\n{parsed['body']}",
            "provider": "openai",
            "model": model,
        }
    except Exception:
        return {
            **fallback,
            "full_draft": f"Subject: {fallback['subject']}\n\n{fallback['body']}",
            "provider": "template",
        }

