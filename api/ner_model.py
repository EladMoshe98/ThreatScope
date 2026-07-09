"""
SecureBERT-NER inference wrapper.

The raw HuggingFace token-classification pipeline fragments entities (an IP comes
back as `185`, `.`, `220`, …; `ShadowPad` as `Shadow` + `Pad`). This module loads
the model once and turns that into clean, whole entities grouped by SecureBERT's
native class — which is what the API and the Streamlit two-column table need.

Offline / on-prem: set NER_MODEL_PATH to a local directory holding the baked-in
model weights. It defaults to the HuggingFace id for local development.
"""
import os
from functools import lru_cache
from typing import Dict, List, Tuple

from transformers import pipeline

# SecureBERT-NER's native entity classes (the model's real output), display order.
SECUREBERT_CLASSES = [
    "APT", "SECTEAM", "IDTY", "ACT", "OS", "TOOL",
    "VULID", "VULNAME", "MAL",
    "FILE", "DOM", "ENCR", "IP", "URL", "MD5", "PROT", "EMAIL", "SHA1", "SHA2",
    "TIME", "LOC",
]


def strip_bio(tag: str) -> str:
    """'B-APT' -> 'APT'; 'I-IP' -> 'IP'; 'O' / bare tags -> as-is."""
    return tag.split("-", 1)[1] if "-" in tag else tag


# Local dir (weights baked into the image) or HF id for dev.
MODEL_PATH = os.getenv("NER_MODEL_PATH", "CyberPeace-Institute/SecureBERT-NER")

# Keep each pipeline call comfortably under the model's 512-token limit. Long
# uploads are split into character windows at whitespace so nothing is truncated.
MAX_CHARS_PER_CHUNK = int(os.getenv("NER_MAX_CHARS_PER_CHUNK", "1000"))


@lru_cache(maxsize=1)
def get_pipeline():
    """Load the model once (CPU). Cached for the process lifetime."""
    return pipeline("token-classification", model=MODEL_PATH, aggregation_strategy="none")


def warmup() -> None:
    """Force model load + a tiny inference so the first real request is fast."""
    get_pipeline()("warmup")


def _chunks(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> List[Tuple[str, int]]:
    """Split text into <=max_chars windows, breaking at whitespace to avoid
    slicing through a word/entity. Returns (chunk_text, base_offset) pairs."""
    chunks, i, n = [], 0, len(text)
    while i < n:
        end = min(i + max_chars, n)
        if end < n:
            brk = max(text.rfind(" ", i, end), text.rfind("\n", i, end))
            if brk > i:
                end = brk
        chunks.append((text[i:end], i))
        i = end
    return chunks


def _merge(preds: List[dict], text: str, base: int) -> List[dict]:
    """Merge consecutive same-class tokens into whole entities, using character
    offsets on the ORIGINAL text (so surface strings are clean, no `Ġ`/`##`)."""
    entities: List[dict] = []
    cur = None
    for p in preds:
        tag = strip_bio(p["entity"])  # native SecureBERT class, e.g. 'APT', 'IP', 'MAL'
        gs, ge = base + p["start"], base + p["end"]
        if not tag or tag == "O":
            cur = None
            continue
        # extend if same class and contiguous (allow a single separating space)
        if cur and cur["class"] == tag and gs - cur["end"] <= 1:
            cur["end"] = ge
            cur["score"] = min(cur["score"], float(p["score"]))
        else:
            cur = {"class": tag, "start": gs, "end": ge, "score": float(p["score"])}
            entities.append(cur)
    for e in entities:
        e["text"] = text[e["start"]:e["end"]].strip()
        e["score"] = round(e["score"], 4)
    return [e for e in entities if e["text"]]


def extract_entities(text: str) -> List[dict]:
    """Return a flat list of entities: {text, class, start, end, score}, with
    offsets into `text` (usable for inline highlighting)."""
    pipe = get_pipeline()
    entities: List[dict] = []
    for chunk_text, base in _chunks(text):
        if chunk_text.strip():
            entities.extend(_merge(pipe(chunk_text), text, base))
    return entities


def group_by_class(entities: List[dict]) -> Dict[str, List[str]]:
    """SecureBERT class -> de-duplicated list of entity strings (display order),
    ready for the two-column results table."""
    grouped: Dict[str, List[str]] = {c: [] for c in SECUREBERT_CLASSES}
    for e in entities:
        bucket = grouped.setdefault(e["class"], [])
        if e["text"] not in bucket:
            bucket.append(e["text"])
    return {c: v for c, v in grouped.items() if v}
