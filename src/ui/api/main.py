from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.search import router as csv_router
from .routes.sales import router as sales_router


app = FastAPI(
    title="Spherecast UI API",
    version="0.1.0",
    description="CSV-driven scoring endpoints for the UI demo",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(csv_router, prefix="/api", tags=["csv-scoring"])
app.include_router(sales_router, prefix="/api", tags=["sales"])
