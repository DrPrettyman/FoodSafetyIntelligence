"""
Download all-MiniLM-L6-v2 ONNX model and tokenizer for lightweight runtime inference.

Requires: pip install huggingface-hub sentence-transformers

Run once from the project root:
    python scripts/export_onnx_model.py

Produces:
    models/all-MiniLM-L6-v2-onnx/model.onnx
    models/all-MiniLM-L6-v2-onnx/tokenizer.json
    models/all-MiniLM-L6-v2-onnx/tokenizer_config.json
"""

import json
import shutil
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download

MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
OUTPUT_DIR = Path("models/all-MiniLM-L6-v2-onnx")
MAX_LENGTH = 256


def download_model() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Download ONNX model from HuggingFace Hub (pre-exported by sentence-transformers)
    files = {
        "onnx/model.onnx": "model.onnx",
        "tokenizer.json": "tokenizer.json",
        "tokenizer_config.json": "tokenizer_config.json",
    }

    for hub_path, local_name in files.items():
        print(f"Downloading {hub_path}...")
        downloaded = hf_hub_download(repo_id=MODEL_REPO, filename=hub_path)
        shutil.copy2(downloaded, OUTPUT_DIR / local_name)

    # Override max_length to match sentence-transformers config (256, not 512)
    config_path = OUTPUT_DIR / "tokenizer_config.json"
    config = json.loads(config_path.read_text())
    config["model_max_length"] = MAX_LENGTH
    config_path.write_text(json.dumps(config, indent=2))

    model_size = (OUTPUT_DIR / "model.onnx").stat().st_size / 1024 / 1024
    print(f"model.onnx: {model_size:.1f} MB")

    # Parity check
    print("Running parity check...")
    verify_parity()
    print("Done.")


def verify_parity() -> None:
    """Verify ONNX output matches sentence-transformers within fp32 tolerance."""
    import onnxruntime as ort
    from sentence_transformers import SentenceTransformer
    from tokenizers import Tokenizer

    test_sentences = [
        "novel food insect protein regulation",
        "food additive labelling requirements",
        "EU regulation 2015/2283 on novel foods",
        "allergen declaration on food packaging",
        "health claims on food products",
    ]

    # sentence-transformers embeddings (PyTorch)
    st_model = SentenceTransformer(MODEL_REPO, device="cpu")
    st_embeddings = st_model.encode(test_sentences, normalize_embeddings=True)

    # ONNX embeddings
    session = ort.InferenceSession(
        str(OUTPUT_DIR / "model.onnx"),
        providers=["CPUExecutionProvider"],
    )
    tokenizer = Tokenizer.from_file(str(OUTPUT_DIR / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=MAX_LENGTH)
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

    encodings = tokenizer.encode_batch(test_sentences)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    token_type_ids = np.array([e.type_ids for e in encodings], dtype=np.int64)

    outputs = session.run(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )
    hidden_state = outputs[0]

    # Mean pooling
    mask = attention_mask[:, :, None].astype(np.float32)
    sum_hidden = (hidden_state * mask).sum(axis=1)
    token_counts = mask.sum(axis=1).clip(min=1e-9)
    mean_pooled = sum_hidden / token_counts

    # L2 normalize
    norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
    onnx_embeddings = mean_pooled / np.clip(norms, 1e-12, None)

    # Check parity
    cosine_sims = np.sum(st_embeddings * onnx_embeddings, axis=1)
    max_diff = float(np.max(1.0 - cosine_sims))
    print(f"  Cosine similarities: {cosine_sims}")
    print(f"  Max cosine diff from 1.0: {max_diff:.2e}")

    assert max_diff < 1e-4, f"Parity check failed: max cosine diff {max_diff:.2e}"
    print("  Parity check passed.")


if __name__ == "__main__":
    download_model()
