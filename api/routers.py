"""All API routes in one router: /health, /predict, /history."""
import time
from typing import List

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from api import log_store, ner_model
from api.logger import get_logger
from api.schemas import Entity, HealthResponse, HistoryRow, PredictResponse
from api.validation import InputValidationError, validate_and_decode

router = APIRouter()
log = get_logger()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Liveness/readiness probe for Docker and the Streamlit client."""
    loaded = ner_model.get_pipeline.cache_info().currsize > 0
    return HealthResponse(status="ok", model=ner_model.MODEL_PATH, model_loaded=loaded)


@router.post("/predict", response_model=PredictResponse, tags=["predict"])
async def predict(file: UploadFile = File(...)) -> PredictResponse:
    """Process a single text file (one at a time) and return its named entities."""
    raw = await file.read()

    # --- input hardening ---
    try:
        text = validate_and_decode(file.filename or "", raw)
    except InputValidationError as exc:
        log.warning("rejected upload %r: %s", file.filename, exc)
        log_store.log_request(file.filename or "", 0.0, 0, "rejected")
        raise HTTPException(status_code=400, detail=str(exc))

    # --- inference ---
    t0 = time.perf_counter()
    try:
        entities = ner_model.extract_entities(text)
    except Exception:  # noqa: BLE001 - surface a clean error, log the trace
        log.exception("inference failed for %r", file.filename)
        log_store.log_request(file.filename or "", 0.0, 0, "error")
        raise HTTPException(status_code=500, detail="Inference failed while processing the file.")
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    grouped = ner_model.group_by_class(entities)
    class_counts = {cls: len(vals) for cls, vals in grouped.items()}
    log_store.log_request(file.filename or "", latency_ms, len(entities), "success", class_counts)
    log.info("predicted %r: %d entities in %.1f ms", file.filename, len(entities), latency_ms)

    return PredictResponse(
        filename=file.filename or "",
        num_entities=len(entities),
        latency_ms=latency_ms,
        entities_by_class=grouped,
        entities=[
            Entity(text=e["text"], label=e["class"], start=e["start"], end=e["end"], score=e["score"])
            for e in entities
        ],
    )


@router.get("/history", response_model=List[HistoryRow], tags=["history"])
def history(limit: int = Query(20, ge=1, le=200)) -> List[HistoryRow]:
    """Recent request metadata for the History dashboard."""
    return [HistoryRow(**row) for row in log_store.recent(limit)]
