"""
ONNX Runtime embedder for all-MiniLM-L6-v2.

Produces numerically equivalent output to:
    SentenceTransformer("all-MiniLM-L6-v2").encode(texts, normalize_embeddings=True)

Runtime dependencies: onnxruntime, tokenizers, numpy (no PyTorch).
"""

from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

DEFAULT_MODEL_DIR = Path("models/all-MiniLM-L6-v2-onnx")
MAX_LENGTH = 256


class OnnxEmbedder:
    """Embed text using ONNX Runtime + HuggingFace fast tokenizer."""

    def __init__(self, model_dir: Path | str | None = None):
        self._model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self._session: ort.InferenceSession | None = None
        self._tokenizer: Tokenizer | None = None

    def _get_session(self) -> ort.InferenceSession:
        if self._session is None:
            model_path = self._model_dir / "model.onnx"
            if not model_path.exists():
                raise FileNotFoundError(
                    f"ONNX model not found at {model_path}. "
                    "Run scripts/export_onnx_model.py first."
                )
            self._session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
        return self._session

    def _get_tokenizer(self) -> Tokenizer:
        if self._tokenizer is None:
            tok_path = self._model_dir / "tokenizer.json"
            if not tok_path.exists():
                raise FileNotFoundError(f"Tokenizer not found at {tok_path}")
            self._tokenizer = Tokenizer.from_file(str(tok_path))
            self._tokenizer.enable_truncation(max_length=MAX_LENGTH)
            self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        return self._tokenizer

    def encode(
        self,
        texts: list[str],
        batch_size: int = 64,
        normalize_embeddings: bool = True,
        **kwargs,
    ) -> np.ndarray:
        """Encode texts to 384-dim embeddings.

        Args:
            texts: List of strings to encode.
            batch_size: Batch size for inference.
            normalize_embeddings: L2-normalize output vectors.

        Returns:
            np.ndarray of shape (len(texts), 384).
        """
        tokenizer = self._get_tokenizer()
        session = self._get_session()

        all_embeddings = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]

            encodings = tokenizer.encode_batch(batch)
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
            hidden_state = outputs[0]  # (batch, seq_len, 384)

            # Mean pooling
            mask = attention_mask[:, :, None].astype(np.float32)
            sum_hidden = (hidden_state * mask).sum(axis=1)
            token_counts = mask.sum(axis=1).clip(min=1e-9)
            mean_pooled = sum_hidden / token_counts

            if normalize_embeddings:
                norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
                mean_pooled = mean_pooled / np.clip(norms, 1e-12, None)

            all_embeddings.append(mean_pooled.astype(np.float32))

        return np.vstack(all_embeddings)
