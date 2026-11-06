"""Offline OPUS-MT on Apple MPS, reusing the existing protected-row pipeline.

Use the course venv interpreter; sentencepiece is read from translation-env.
The public interface is ``translate_batch(items: list[str]) -> list[str]``.
English fragments, chunking, tiny-phrase handling and placeholder validation
come from local_zh_argos; only neural inference uses Marian on MPS instead of
CTranslate2 on CPU. Model loading is local-only and never downloads files.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import threading

import local_zh_argos as protected_backend


BASE = Path.home() / ".local/share/ai-engineering-from-scratch"
DEFAULT_MODEL = BASE / "translation-models/helsinki-opus-mt-en-zh"
_ENGINE = None
_ENGINE_LOCK = threading.Lock()
_CALL_LOCK = threading.Lock()
METRICS = protected_backend.METRICS
REJECTED_FRAGMENTS = protected_backend.REJECTED_FRAGMENTS


class MPSTranslator:
    # Reuse the exact sentence-first, nontruncating source chunker.
    chunk = protected_backend.LocalTranslator.chunk

    def __init__(self):
        site = BASE / "translation-env/lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
        if site.is_dir() and str(site) not in sys.path:
            sys.path.append(str(site))
        import sentencepiece
        import torch
        from transformers import MarianMTModel, MarianTokenizer

        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS is unavailable; use the existing CPU provider")
        self.torch = torch
        self.model_path = Path(os.environ.get("LOCAL_ZH_MPS_MODEL", str(DEFAULT_MODEL)))
        self.batch_size = int(os.environ.get("LOCAL_ZH_MPS_BATCH_SIZE", "16"))
        self.max_source_tokens = int(os.environ.get("LOCAL_ZH_CT2_SOURCE_TOKENS", "150"))
        self.max_decoding_length = int(os.environ.get("LOCAL_ZH_CT2_MAX_DECODE", "256"))
        if self.batch_size < 1:
            raise ValueError("LOCAL_ZH_MPS_BATCH_SIZE must be positive")
        self.source = sentencepiece.SentencePieceProcessor(model_file=str(self.model_path / "source.spm"))
        self.tokenizer = MarianTokenizer.from_pretrained(str(self.model_path), local_files_only=True)
        self.model = MarianMTModel.from_pretrained(
            str(self.model_path), local_files_only=True, dtype=torch.float16
        ).eval().to("mps")
        # Let max_new_tokens own the bound without a conflicting legacy value.
        self.model.generation_config.max_length = None

    def raw_batch(self, fragments: list[str], split_limit: int | None = None) -> list[str]:
        if not fragments:
            return []
        rows = [self.chunk(text, split_limit) for text in fragments]
        flattened = [chunk for row in rows for chunk in row]
        translations: list[str | None] = [None] * len(flattened)
        pending_indices = []
        for index, chunk in enumerate(flattened):
            deterministic = protected_backend._deterministic_fragment(chunk)
            if deterministic is not None:
                translations[index] = deterministic
                METRICS["deterministic_fragments"] += 1
            else:
                pending_indices.append(index)
        for start in range(0, len(pending_indices), self.batch_size):
            indices = pending_indices[start:start + self.batch_size]
            chunks = [flattened[index] for index in indices]
            inputs = self.tokenizer(
                [">>cmn_Hans<< " + chunk for chunk in chunks],
                return_tensors="pt", padding=True, truncation=False,
            ).to("mps")
            with self.torch.inference_mode():
                generated = self.model.generate(
                    **inputs, num_beams=1, do_sample=False,
                    max_new_tokens=self.max_decoding_length,
                    repetition_penalty=1.05,
                )
            self.torch.mps.synchronize()
            generated_cpu = generated.cpu()
            decoded = self.tokenizer.batch_decode(generated_cpu, skip_special_tokens=True)
            token_rows = generated_cpu.tolist()
            # Keep allocator reserves small between batches on the shared Mac.
            del generated, generated_cpu, inputs
            self.torch.mps.empty_cache()
            for index, chunk, text, token_row in zip(indices, chunks, decoded, token_rows):
                token_row = token_row[1:]  # decoder start is a pad token
                while token_row and token_row[-1] == self.tokenizer.pad_token_id:
                    token_row.pop()
                if len(token_row) >= self.max_decoding_length:
                    old_limit = split_limit or self.max_source_tokens
                    actual_tokens = len(self.source.encode(chunk, out_type=str))
                    next_limit = max(1, min(old_limit // 2, actual_tokens // 2))
                    smaller = self.chunk(chunk, next_limit)
                    if next_limit < old_limit and len(smaller) > 1 and all(len(part) < len(chunk) for part in smaller):
                        translations[index] = self.raw_batch([chunk], split_limit=next_limit)[0]
                        protected_backend._record_rejected(
                            chunk, translations[index], "decoder reached its length limit", "split_retry"
                        )
                        METRICS["decode_limit_retries"] += 1
                    else:
                        translations[index] = protected_backend._limit_fallback(chunk)
                    continue
                text = re.sub(r"[\r\n]+", " ", text.strip()).replace("|", "｜")
                letters = re.sub(r"[^A-Za-z]", "", chunk)
                if len(letters) <= 12 and len(re.findall(r"[\u3400-\u9fff]", text)) > max(12, 3 * len(letters)):
                    text = protected_backend._limit_fallback(chunk, "short source produced excessive decoder output")
                    METRICS["short_expansion_rejected"] += 1
                if not text:
                    text = protected_backend._limit_fallback(chunk, "decoder returned an empty translation")
                translations[index] = text
        cursor = 0
        outputs = []
        for row in rows:
            translated_row = translations[cursor:cursor + len(row)]
            if any(value is None for value in translated_row):
                raise RuntimeError("MPS translation left an unprocessed fragment")
            outputs.append(" ".join(translated_row))
            cursor += len(row)
        METRICS["neural_fragments"] += len(pending_indices)
        METRICS["neural_batches"] += bool(pending_indices)
        return outputs


def _engine() -> MPSTranslator:
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                _ENGINE = MPSTranslator()
    return _ENGINE


def translate_batch(items: list[str]) -> list[str]:
    """Use the existing placeholder-safe wrapper with the MPS neural core.

    A lock serializes model use and isolates the temporary engine substitution.
    The separate CPU translation process is unaffected.
    """
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise TypeError("translate_batch expects list[str]")
    if not items:
        return []
    with _CALL_LOCK:
        previous = protected_backend._ENGINE
        try:
            protected_backend._ENGINE = _engine()
            return protected_backend.translate_batch(items)
        finally:
            protected_backend._ENGINE = previous
