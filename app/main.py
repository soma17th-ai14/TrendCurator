"""TrendCurator FastAPI 앱 진입점."""

from fastapi import FastAPI

from app.api.documents import router as documents_router

app = FastAPI(title="TrendCurator API")
app.include_router(documents_router)
