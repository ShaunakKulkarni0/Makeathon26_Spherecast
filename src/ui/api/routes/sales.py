from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.email_draft import generate_email_draft


router = APIRouter()


class EmailDraftRequest(BaseModel):
    supplier_name: str | None = None
    seller_email: str | None = None
    seller_website: str | None = None
    material_name: str = Field(default="")
    material_id: str = Field(default="")
    issue_summary: str = Field(default="Missing allergen information")
    missing_information: list[str] = Field(default_factory=list)
    prohibited_allergens: list[str] = Field(default_factory=list)
    destination_country: str = Field(default="Germany")


@router.post("/sales/email-draft")
def create_email_draft(payload: EmailDraftRequest) -> dict[str, Any]:
    try:
        return generate_email_draft(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate email draft: {exc}") from exc

