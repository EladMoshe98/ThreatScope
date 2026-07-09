# Theat Scope - Cyber Documents Named Entity Recognition

An on-prem service that extracts **cyber-threat-intelligence entities** from text
using **SecureBERT-NER**. It ships as two Docker containers — a FastAPI service that
hosts the model and a Streamlit UI.

The model was chosen by benchmarking **SecureBERT-NER vs CyNER** (and, as an extra
data point, SecureBERT2.0-NER) on the **DNRTI** dataset — see [Benchmark](#benchmark).

---

## What it does

Upload a `.txt` file → get every named entity, grouped by class, in a two-column
table, plus the text with entities highlighted inline. SecureBERT-NER recognises 21
fine-grained classes (threat actors, malware, CVEs, IPs, domains, hashes, files,
times, locations, …).

---

## Repository structure

```
NERF/
├── api/                 FastAPI service — hosts SecureBERT-NER
│   ├── ner_model.py         load model, chunk long text, merge tokens → clean entities
│   ├── validation.py        input hardening (type / size / decode / control chars)
│   ├── logger.py            structured logging
│   ├── log_store.py         SQLite request log (metadata only)
│   ├── routers/             predict · health · history
│   └── main.py              app + startup model warm-up + Swagger /docs
├── ui/streamlit_app.py  Streamlit client (Analyze · Model Comparison · History)
├── models/              SecureBERT-NER weights (run scripts/download_model.py) — gitignored
├── logs/                runtime request log (bind-mounted, visible) — gitignored
├── scripts/download_model.py   downloads the weights into models/
├── benchmark/           PREP ONLY (never containerized)
│   ├── benchmark.ipynb      SecureBERT-NER vs CyNER vs SecureBERT2.0-NER on DNRTI
│   └── DNRTI.rar            the dataset
├── docker/              Dockerfile.api · Dockerfile.ui · docker-compose.yml
├── .streamlit/config.toml   UI theme
├── requirements-api.txt · requirements-ui.txt
└── .env.example
```

> **The `benchmark/` folder is preparation, not part of the product.** It picks the
> model; it is not built into any container.

---

## Quick start

**Prerequisites:** Docker Desktop, and Python 3.11 (only to fetch the weights once).

```bash
# 1. Download the model weights into models/  (one time, needs internet)
python scripts/download_model.py

# 2. Build and run both containers  (from the repo root)
docker compose -f docker/docker-compose.yml up --build
```

Then open:

| | URL |
|---|---|
| **Streamlit UI** | http://localhost:8501 |
| **API (Swagger docs)** | http://localhost:8000/docs |

Stop with `docker compose -f docker/docker-compose.yml down`.

After the weights are baked into the image, the running stack needs **no internet**.

---

## Using the UI

- **Analyze** — upload one `.txt` file → a two-column table (class → entities),
  inline-highlighted text, per-file latency, and CSV/JSON download. A reference table
  explains what each entity class means.
- **Model Comparison** — the DNRTI benchmark summary and why SecureBERT-NER was chosen.
- **History** — recent requests (metadata only; the uploaded text is never stored).

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/predict` | Upload one `.txt` file → entities grouped by class |
| `GET`  | `/health` | Liveness + whether the model is loaded |
| `GET`  | `/history?limit=N` | Recent request metadata |
| `GET`  | `/docs` | Interactive Swagger UI |

```bash
curl -F "file=@report.txt;type=text/plain" http://localhost:8000/predict
```

```jsonc
{
  "filename": "report.txt",
  "num_entities": 4,
  "latency_ms": 88.8,
  "entities_by_class": { "APT": ["APT32"], "MAL": ["Cobalt Strike"], "IP": ["109.248.148.42"], "TIME": ["April 2018"] },
  "entities": [ { "text": "APT32", "label": "APT", "start": 3, "end": 8, "score": 0.93 }, ... ]
}
```

---

## Benchmark

Open `benchmark/benchmark.ipynb` (best in **Google Colab** — CyNER installs cleanly
there; also runs locally). Upload `DNRTI.rar` via the notebook's upload box, then run
top to bottom. It reports precision / recall / F1 (per-class + overall), latency, and
model footprint, and saves a results JSON + charts.

**Result (662 DNRTI test sentences):**

| Model | F1 (micro) | Precision | Recall | Params |
|---|---|---|---|---|
| **SecureBERT-NER** | **0.70** | 0.70 | 0.70 | 124M |
| CyNER-base | 0.27 | 0.38 | 0.20 | 277M |
| SecureBERT2.0-NER | 0.14 | 0.12 | 0.17 | 150M |

**Decision — SecureBERT-NER:** most accurate (2–5×), fastest, smallest, and the only
model covering Time/Area. It was fine-tuned on APTNER, whose taxonomy closely matches
DNRTI, so it aligns best with this kind of data.
(*CyNER-large was skipped — its trained weights were never publicly released.*)

---

## Configuration

All optional (the app runs with defaults). See `.env.example`. Key variables:

| Variable | Default | Used by |
|---|---|---|
| `NER_MODEL_PATH` | `models/securebert-ner` | API — where the baked weights are |
| `MAX_FILE_SIZE_MB` | `2` | API — upload size limit |
| `LOG_LEVEL` / `LOG_FILE` / `LOG_DB_PATH` | `INFO` / `logs/nerf.log` / `logs/requests.db` | API logging |
| `API_URL` | `http://api:8000` | UI — where to reach the API |

---

## Design notes

- **Offline / on-prem:** the model weights are copied into the API image at build
  time; the container carries its own copy and never calls out at runtime.
- **Input hardening:** `.txt` only, size limit, safe UTF-8 decode, control-char
  stripping; the UI HTML-escapes uploaded text before display (no script injection).
- **Privacy:** the request log stores metadata only (filename, latency, entity
  counts, status) — never the uploaded document text.
- **Two containers:** the model service and the UI are decoupled, so the API is
  independently usable (curl / Swagger / other clients) and the two scale separately.

## Known limitations / future work

- No authentication (single-tenant on-prem assumption).
- Long documents are chunked at whitespace to stay under the model's 512-token limit.
- CyNER-large not benchmarked (weights unavailable); an ensemble of models is a
  possible v2.
