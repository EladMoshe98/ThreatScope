"""Pydantic request/response models for the NER API."""
from typing import Dict, List

from pydantic import BaseModel, Field


class Entity(BaseModel):
    text: str
    label: str = Field(..., description="Common entity class")
    start: int
    end: int
    score: float


class PredictResponse(BaseModel):
    filename: str
    num_entities: int
    latency_ms: float
    # class name -> list of entity strings (the two-column results table)
    entities_by_class: Dict[str, List[str]]
    # flat list with character offsets (for inline highlighting in the UI)
    entities: List[Entity]


class HealthResponse(BaseModel):
    status: str
    model: str
    model_loaded: bool


class HistoryRow(BaseModel):
    timestamp: str
    filename: str
    latency_ms: float
    num_entities: int
    status: str
    class_counts: Dict[str, int]


class ErrorResponse(BaseModel):
    detail: str
