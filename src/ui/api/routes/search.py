from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.orchestrator import (
    list_csv_materials,
    load_requirements_defaults,
    run_csv_scoring,
)


router = APIRouter()


class CSVScoreRequest(BaseModel):
    selected_material_id: str
    weights: dict[str, float] | None = None
    top_n: int = Field(default=3, ge=1, le=25)
    requirements_override: dict | None = None


@router.get("/csv/materials")
def get_csv_materials() -> dict:
    return {
        "materials": list_csv_materials(),
        "requirements_defaults": load_requirements_defaults(),
    }


@router.post("/csv/score")
def score_from_csv(payload: CSVScoreRequest) -> dict:
    return run_csv_scoring(
        selected_material_id=payload.selected_material_id,
        weights=payload.weights,
        top_n=payload.top_n,
        requirements_override=payload.requirements_override,
    )
