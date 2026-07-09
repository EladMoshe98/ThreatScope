# models/

Holds the chosen model's weights (SecureBERT-NER). Populate this folder **once,
before building the Docker image**:

```
python scripts/download_model.py     # -> models/securebert-ner/
```

```
models/
└── securebert-ner/     # config.json, model.safetensors, tokenizer files (~480 MB)
```

### Why the weights aren't in Git
The weight files are ~480 MB — far too big to commit to a Git repository (Git is for
source code, not large binaries). So they are **excluded from Git** (via `.gitignore`);
only this README is committed. Anyone cloning the repo runs the download script above
to fetch the weights locally.

### How the container gets the weights
When you build the API image, the Dockerfile **copies this `models/` folder into the
image** (`COPY models/ ...`). That means the finished image carries its own copy of the
model, so the running container needs **no internet** — it works fully offline / on-prem.
