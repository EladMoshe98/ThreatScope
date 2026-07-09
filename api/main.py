"""
NERF API — FastAPI service hosting SecureBERT-NER.

Endpoints: GET /health, POST /predict, GET /history, GET /docs (Swagger).
Run locally:  uvicorn api.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import ner_model, routers
from api.logger import get_logger

log = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the model at startup so the first /predict isn't slow (and /health flips
    # to model_loaded=true only once weights are in memory).
    log.info("Loading model: %s", ner_model.MODEL_PATH)
    try:
        ner_model.warmup()
        log.info("Model ready.")
    except Exception:  # noqa: BLE001
        log.exception("Model warmup failed at startup; /predict will retry on first call.")
    yield


app = FastAPI(
    title="NERF — SecureBERT-NER API",
    description="On-prem named-entity recognition for cyber-threat-intel text.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(routers.router)


@app.get("/", tags=["health"])
def root():
    return {"service": "NERF NER API", "model": ner_model.MODEL_PATH, "docs": "/docs"}
