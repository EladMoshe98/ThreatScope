"""
Download the chosen NER model (SecureBERT-NER) into ./models/securebert-ner/.

Run this once before building the Docker image — the API image COPIES these
weights in, so the container is fully self-contained and runs offline.

    python scripts/download_model.py
"""
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ID = "CyberPeace-Institute/SecureBERT-NER"
TARGET = Path(__file__).resolve().parent.parent / "models" / "securebert-ner"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_ID} -> {TARGET} …")
    snapshot_download(
        MODEL_ID,
        local_dir=str(TARGET),
        # inference needs only: config + safetensors weights + tokenizer.
        # (skip pytorch_model.bin duplicate, optimizer & training state)
        allow_patterns=[
            "config.json", "model.safetensors",
            "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
            "vocab.json", "merges.txt",
        ],
    )
    print("Done. Contents:")
    for p in sorted(TARGET.iterdir()):
        print("  ", p.name)


if __name__ == "__main__":
    main()
