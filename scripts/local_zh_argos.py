"""Offline, placeholder-safe translation using public OPUS-MT and CTranslate2.

The historical filename describes the initially planned Argos backend. Model
downloads from Argos were unavailable; the installed backend is the official
Helsinki-NLP/opus-mt-en-zh model, revision recorded in the model directory.
No network calls are performed by this module. Use the isolated interpreter:
~/.local/share/ai-engineering-from-scratch/translation-env/bin/python

``translate_batch(items: list[str]) -> list[str]`` accepts prepared Markdown
segments. Placeholders never enter the neural model: natural fragments are
collected across all rows, deduplicated, translated in batches, then restored
to their original row positions. Long fragments are split without truncation.
"""

from __future__ import annotations

from collections import Counter
import argparse
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import warnings


BASE = Path.home() / ".local/share/ai-engineering-from-scratch"
DEFAULT_MODEL = BASE / "translation-models/helsinki-opus-mt-en-zh-ct2-int8"
KEEP_RE = re.compile(r"ZXKEEP\d+QXZ")
_ENGINE = None
_ENGINE_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_FRAGMENT_CACHE: dict[str, str] = {}
METRICS: Counter = Counter()
REJECTED_FRAGMENTS: list[dict[str, object]] = []
_REJECTED_KEYS: set[tuple[str, str, str]] = set()
_REJECTED_LOCK = threading.Lock()
_SHORT_PHRASES = {
    "and": "和", "or": "或", "to": "以", "from": "来自", "of": "的",
    "with": "与", "without": "不使用", "is": "是", "are": "是",
    "was": "是", "were": "是", "be": "为", "being": "作为",
    "the": "该", "a": "一个", "an": "一个", "by": "通过", "as": "作为",
    "in": "在", "on": "在", "for": "用于", "at": "在", "into": "进入",
    "between": "之间", "after": "之后", "before": "之前", "than": "比",
    "then": "然后", "if": "如果", "when": "当", "while": "而", "but": "但",
    "not": "不", "no": "无", "yes": "是", "only": "仅", "also": "也",
    "it": "它", "its": "它的", "this": "此", "that": "该",
    "these": "这些", "those": "那些", "you": "你", "your": "你的",
    "we": "我们", "our": "我们的", "they": "它们", "their": "它们的",
    "each": "每个", "every": "每个", "all": "所有", "any": "任意",
    "both": "两者", "either": "任一", "such as": "例如", "instead of": "而非",
    "and the": "以及该", "or the": "或该", "of the": "的", "in the": "在",
    "on the": "在", "for the": "用于", "with the": "与", "to the": "至",
    "from the": "来自", "is a": "是一个", "is an": "是一个", "is the": "是该",
    "are the": "是这些", "and a": "和一个", "and an": "和一个", "or a": "或一个",
    "using": "使用", "use": "使用", "used": "使用", "uses": "使用",
    "via": "通过", "per": "每", "vs": "与", "versus": "与",
    "e.g.": "例如", "i.e.": "即", "etc.": "等", "'s": "的", "’s": "的",
    "model": "模型", "models": "模型", "weight": "权重", "weights": "权重",
    "learning objectives": "学习目标", "the problem": "问题", "the concept": "概念",
    "build it": "动手实现", "use it": "使用现有工具", "verify it": "验证",
    "practice lab": "练习实验", "interactive lab": "交互式实验",
    "shipped artifact": "交付成果", "key terms": "关键术语",
    "common mistakes": "常见错误", "code walkthrough": "代码讲解",
    "run it": "运行示例", "capstone connection": "与综合项目的联系",
    "is not": "不是", "are not": "不是", "was not": "不是", "were not": "不是",
    "does not": "不", "do not": "不", "did not": "没有", "never": "绝不",
    "must": "必须", "must not": "不得", "should": "应当", "should not": "不应",
    "can": "可以", "cannot": "无法", "can not": "无法", "can't": "无法",
    "may": "可能", "may not": "可能不会", "will": "将", "will not": "不会",
    "won't": "不会", "don't": "不要", "doesn't": "不会", "isn't": "不是",
    "aren't": "不是", "has": "具有", "have": "具有", "has no": "没有",
    "have no": "没有", "no longer": "不再", "at least": "至少", "at most": "最多",
    "rather than": "而非", "instead": "改为", "otherwise": "否则", "unless": "除非",
    "whether": "是否", "returns": "返回", "return": "返回", "requires": "需要",
    "require": "需要", "predicts": "预测", "predict": "预测", "trains": "训练",
    "train": "训练", "learns": "学习", "learn": "学习", "generates": "生成",
    "generate": "生成", "true": "真", "false": "假", "valid": "有效", "invalid": "无效",
    "type": "类型", "languages": "语言", "prerequisites": "先修要求", "time": "时间",
    "related": "相关内容", "none": "无", "input": "输入", "output": "输出",
    "inputs": "输入", "outputs": "输出", "example": "示例", "examples": "示例",
    "name": "名称", "description": "描述", "method": "方法", "methods": "方法",
    "feature": "特征", "features": "特征", "value": "值", "values": "值",
    "error": "错误", "errors": "错误", "cost": "成本", "speed": "速度",
    "quality": "质量", "reason": "原因", "result": "结果", "results": "结果",
    "positive": "正", "negative": "负", "small": "小", "large": "大",
    "low": "低", "high": "高", "better": "更好", "worse": "更差",
    "yes": "是", "no": "否", "default": "默认", "optional": "可选",
    "required": "必需", "recommended": "推荐", "supported": "支持",
    "unsupported": "不支持", "enabled": "启用", "disabled": "禁用",
    "model weights": "模型权重", "training data": "训练数据", "training pipeline": "训练流程",
    "training loop": "训练循环", "loss function": "损失函数", "learning rate": "学习率",
    "batch size": "批次大小", "weight decay": "权重衰减", "hidden state": "隐藏状态",
    "terminal output": "终端输出", "source code": "源代码", "test data": "测试数据",
    "validation data": "验证数据", "test set": "测试集", "training set": "训练集",
    "validation set": "验证集", "best practice": "最佳实践", "best practices": "最佳实践",
    "next steps": "后续步骤", "use case": "使用场景", "use cases": "使用场景",
}


def _deterministic_fragment(text: str) -> str | None:
    """Keep tiny connector fragments out of a sentence-trained neural model."""
    direct = _SHORT_PHRASES.get(text.casefold())
    if direct is not None:
        return direct
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", text):
        # A sentence-trained MT model can hallucinate a full unrelated sentence
        # from one unfamiliar word. Retain that possible technical term.
        return text
    # A connector with ordinary boundary punctuation is still the same
    # connector. Punctuation is copied, not regenerated by the model.
    match = re.fullmatch(r"([\s\"'()\[\]{},:;.!?—–-]*)([A-Za-z]+(?:\s+[A-Za-z]+){0,2})([\s\"'()\[\]{},:;.!?—–-]*)", text)
    if match:
        value = _SHORT_PHRASES.get(match.group(2).casefold())
        if value is not None:
            return match.group(1) + value + match.group(3)
    if not re.search(r"\s", text) and re.search(r"[A-Za-z]", text):
        # Punctuation-bearing names and one extremely long identifier also
        # remain atomic. Splitting their SentencePiece tokens would corrupt
        # spelling, while asking the model to translate them can loop.
        return text
    return None


def _record_rejected(text: str, result: str, reason: str, strategy: str) -> None:
    """Expose complete decoder rejects for a final manual review/export."""
    source_words = Counter(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", KEEP_RE.sub("", text)))
    target_words = Counter(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", KEEP_RE.sub("", result)))
    retained = sum((source_words & target_words).values())
    key = (text, reason, strategy)
    with _REJECTED_LOCK:
        METRICS["decoder_rejected_fragments"] += 1
        if key in _REJECTED_KEYS:
            return
        _REJECTED_KEYS.add(key)
        REJECTED_FRAGMENTS.append({
            "source": text,
            "result": result,
            "reason": reason,
            "strategy": strategy,
            "retained_source_words": retained,
        })
    if strategy == "wordwise_fallback" or retained:
        warnings.warn(
            f"Local translation needs review ({reason}; {strategy}; "
            f"retained {retained} source words): {text[:160]!r}. "
            "Full fragment is available in local_zh_argos.REJECTED_FRAGMENTS.",
            RuntimeWarning,
            stacklevel=2,
        )


def _limit_fallback(text: str, reason: str = "decoder reached its length limit") -> str:
    """Bounded, explicit final recovery; preserve every unknown source word.

    This helper is shared with the MPS provider. It translates only known
    function words/phrases, copies whitespace/punctuation/placeholders, and
    records the complete original for manual translation. It never presents an
    untouched prose paragraph as a successful neural translation silently.
    """
    pieces = re.split(r"(\s+|ZXKEEP\d+QXZ)", text)
    output = []
    for piece in pieces:
        if not piece or piece.isspace() or KEEP_RE.fullmatch(piece):
            output.append(piece)
            continue
        deterministic = _deterministic_fragment(piece)
        output.append(piece if deterministic is None else deterministic)
    result = "".join(output)
    METRICS["terminal_wordwise_fallbacks"] += 1
    _record_rejected(text, result, reason, "wordwise_fallback")
    return result


def _load_dependencies():
    # This adds only the isolated translation packages; the course venv is not
    # activated, modified, or used for inference. ABI versions must match.
    site = BASE / "translation-env/lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if site.is_dir() and str(site) not in sys.path:
        sys.path.insert(0, str(site))
    try:
        import ctranslate2
        import sentencepiece
    except ImportError as exc:
        raise RuntimeError(
            "Run the local translation provider with "
            f"{BASE / 'translation-env/bin/python'} (isolated Python 3.12)"
        ) from exc
    return ctranslate2, sentencepiece


class LocalTranslator:
    def __init__(self):
        ctranslate2, sentencepiece = _load_dependencies()
        self.model_path = Path(os.environ.get("LOCAL_ZH_CT2_MODEL", str(DEFAULT_MODEL)))
        if not (self.model_path / "model.bin").is_file():
            raise FileNotFoundError(f"Local CTranslate2 model not installed: {self.model_path}")
        self.batch_size = int(os.environ.get("LOCAL_ZH_CT2_BATCH_SIZE", "64"))
        self.beam_size = int(os.environ.get("LOCAL_ZH_CT2_BEAM", "2"))
        self.max_source_tokens = int(os.environ.get("LOCAL_ZH_CT2_SOURCE_TOKENS", "150"))
        self.max_decoding_length = int(os.environ.get("LOCAL_ZH_CT2_MAX_DECODE", "256"))
        self.source = sentencepiece.SentencePieceProcessor(model_file=str(self.model_path / "source.spm"))
        self.target = sentencepiece.SentencePieceProcessor(model_file=str(self.model_path / "target.spm"))
        self.translator = ctranslate2.Translator(
            str(self.model_path),
            device="cpu",
            compute_type="int8",
            intra_threads=int(os.environ.get("LOCAL_ZH_CT2_INTRA_THREADS", "4")),
            inter_threads=int(os.environ.get("LOCAL_ZH_CT2_INTER_THREADS", "2")),
        )

    def chunk(self, text: str, max_tokens: int | None = None) -> list[str]:
        """Sentence-first, word-boundary chunks; nothing is silently truncated."""
        limit = max_tokens or self.max_source_tokens
        if len(text) <= 600 and len(self.source.encode(text, out_type=str)) <= limit:
            return [text]
        sentences = re.split(r"(?<=[.!?;])\s+(?=[A-Z\"'])", text)
        chunks: list[str] = []
        buffer = ""
        for sentence in sentences:
            for word in re.findall(r"\S+", sentence):
                candidate = (buffer + " " + word).lstrip()
                if buffer and (len(candidate) > 600 or len(self.source.encode(candidate, out_type=str)) > limit):
                    chunks.append(buffer)
                    buffer = ""
                if len(self.source.encode(word, out_type=str)) > limit:
                    if buffer:
                        chunks.append(buffer)
                        buffer = ""
                    # Keep an oversized atomic word intact. raw_batch's
                    # deterministic path preserves it without model inference.
                    chunks.append(word)
                else:
                    buffer = (buffer + " " + word).lstrip()
            # Prefer a complete sentence boundary once the buffer is substantial.
            if len(buffer) >= 350:
                chunks.append(buffer)
                buffer = ""
        if buffer:
            chunks.append(buffer)
        if not chunks:
            raise ValueError("Nonempty fragment produced no local translation chunks")
        return chunks

    def raw_batch(self, fragments: list[str], split_limit: int | None = None) -> list[str]:
        if not fragments:
            return []
        rows = [self.chunk(text, split_limit) for text in fragments]
        flattened = [chunk for row in rows for chunk in row]
        translations: list[str | None] = [_deterministic_fragment(chunk) for chunk in flattened]
        pending = [index for index, value in enumerate(translations) if value is None]
        sources = [[">>cmn_Hans<<"] + self.source.encode(flattened[index], out_type=str) + ["</s>"] for index in pending]
        results = self.translator.translate_batch(
            sources,
            beam_size=self.beam_size,
            max_batch_size=self.batch_size,
            batch_type="examples",
            max_input_length=0,
            max_decoding_length=self.max_decoding_length,
            replace_unknowns=True,
            repetition_penalty=1.05,
        ) if sources else []
        if len(results) != len(pending):
            raise RuntimeError("Local model returned fewer results than source fragments")
        for index, result in zip(pending, results):
            chunk = flattened[index]
            tokens = result.hypotheses[0]
            if len(tokens) >= self.max_decoding_length:
                old_limit = split_limit or self.max_source_tokens
                actual_tokens = len(self.source.encode(chunk, out_type=str))
                next_limit = max(1, min(old_limit // 2, actual_tokens // 2))
                smaller = self.chunk(chunk, next_limit)
                if next_limit < old_limit and len(smaller) > 1 and all(len(part) < len(chunk) for part in smaller):
                    recovered = self.raw_batch([chunk], split_limit=next_limit)[0]
                    translations[index] = recovered
                    _record_rejected(chunk, recovered, "decoder reached its length limit", "split_retry")
                    METRICS["decode_limit_retries"] += 1
                else:
                    translations[index] = _limit_fallback(chunk)
                continue
            clean = [token for token in tokens if token not in {"</s>", "<s>", "<pad>", ">>cmn_Hans<<"}]
            text = self.target.decode(clean).strip()
            text = re.sub(r"[\r\n]+", " ", text).replace("|", "｜")
            letters = re.sub(r"[^A-Za-z]", "", chunk)
            if len(letters) <= 12 and len(re.findall(r"[\u3400-\u9fff]", text)) > max(12, 3 * len(letters)):
                text = _limit_fallback(chunk, "short source produced excessive decoder output")
                METRICS["short_expansion_rejected"] += 1
            if not text:
                text = _limit_fallback(chunk, "decoder returned an empty translation")
            translations[index] = text
        cursor = 0
        outputs = []
        for row in rows:
            row_translations = translations[cursor:cursor + len(row)]
            if any(value is None for value in row_translations):
                raise RuntimeError("Local model left an unresolved fragment slot")
            outputs.append(" ".join(row_translations))
            cursor += len(row)
        METRICS["neural_fragments"] += len(pending)
        METRICS["neural_batches"] += bool(pending)
        return outputs


def _engine() -> LocalTranslator:
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                _ENGINE = LocalTranslator()
    return _ENGINE


def translate_batch(items: list[str]) -> list[str]:
    """Translate prepared rows offline; copy every placeholder byte-for-byte."""
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise TypeError("translate_batch expects list[str]")
    if not items:
        return []
    rows: list[list[str | tuple[str, str, str]]] = []
    unique: dict[str, None] = {}
    for item in items:
        row: list[str | tuple[str, str, str]] = []
        cursor = 0
        for match in list(KEEP_RE.finditer(item)) + [None]:
            stop = match.start() if match else len(item)
            fragment = item[cursor:stop]
            if re.search(r"[A-Za-z]", fragment):
                leading = re.match(r"\s*", fragment).group()
                trailing = re.search(r"\s*$", fragment).group()
                core = fragment[len(leading):len(fragment) - len(trailing) if trailing else len(fragment)]
                if core:
                    row.append((leading, core, trailing))
                    unique[core] = None
                else:
                    row.append(fragment)
            else:
                row.append(fragment)
            if match:
                row.append(match.group())
                cursor = match.end()
        rows.append(row)
    with _CACHE_LOCK:
        available = {fragment: _FRAGMENT_CACHE[fragment] for fragment in unique if fragment in _FRAGMENT_CACHE}
    for fragment in unique:
        if fragment not in available:
            deterministic = _deterministic_fragment(fragment)
            if deterministic is not None:
                available[fragment] = deterministic
                METRICS["deterministic_fragments"] += 1
    pending = [fragment for fragment in unique if fragment not in available]
    if pending:
        engine = _engine()
        values = engine.raw_batch(pending)
        available.update(zip(pending, values))
        with _CACHE_LOCK:
            _FRAGMENT_CACHE.update(zip(pending, values))
    outputs: list[str] = []
    for original, row in zip(items, rows):
        output = "".join(piece[0] + available[piece[1]] + piece[2] if isinstance(piece, tuple) else piece for piece in row)
        if KEEP_RE.findall(output) != KEEP_RE.findall(original):
            raise ValueError("Local translator changed protected placeholders")
        outputs.append(output)
    METRICS["segments"] += len(items)
    METRICS["cache_hits"] += len(unique) - len(pending)
    return outputs


def self_test() -> None:
    """Run an actual local model smoke test, including protected syntax."""
    examples = [
        "Learning Objectives",
        "A model learns a policy to maximize total reward.",
        "Use ZXKEEP00000001QXZ to inspect the terminal output.",
        "ZXKEEP00000002QXZModel weightsZXKEEP00000003QXZ are stored in memory.",
        "Only ZXKEEP00000004QXZ and ZXKEEP00000005QXZ remain protected.",
        "ZXKEEP00000006QXZ",
    ]
    start = time.monotonic()
    values = translate_batch(examples)
    for source, target in zip(examples, values):
        assert KEEP_RE.findall(source) == KEEP_RE.findall(target)
        assert "\n" not in target and "|" not in target
        print(source, "=>", target)
    assert values[4] == "仅 ZXKEEP00000004QXZ 和 ZXKEEP00000005QXZ 保持保护。"
    assert translate_batch(["and", "or", "the", "(and)", "model", "weight"]) == ["和", "或", "该", "(和)", "模型", "权重"]
    print({"seconds": round(time.monotonic() - start, 3), "metrics": dict(METRICS)})


def benchmark(count: int = 100) -> None:
    """Benchmark real prepared course segments, without modifying any files."""
    from local_zh_markdown import prepare, validate_segment
    root = Path(__file__).resolve().parents[1]
    terms = re.findall(r"^### (.+)$", (root / "glossary/terms.md").read_text(), re.M)
    extra = root.parent / "learning-artifacts/chinese-translation/glossary-extra.json"
    if extra.exists():
        terms += json.loads(extra.read_text())
    samples: list[str] = []
    files = sorted((root / "phases/11-llm-engineering").glob("*/docs/en.md"))
    for path in files:
        _, segments = prepare(path.read_text(), terms)
        samples.extend(segments)
        if len(samples) >= count:
            break
    samples = samples[:count]
    # Load and warm up separately so throughput is not conflated with startup.
    warm_start = time.monotonic()
    translate_batch(["This is a local translation benchmark."])
    startup = time.monotonic() - warm_start
    start = time.monotonic()
    values = translate_batch(samples)
    elapsed = time.monotonic() - start
    assert all(validate_segment(source, target) for source, target in zip(samples, values))
    for source, target in zip(samples[:12], values[:12]):
        print(json.dumps({"source": source, "translated": target}, ensure_ascii=False))
    print(json.dumps({"segments": len(samples), "seconds": round(elapsed, 3), "segments_per_second": round(len(samples) / elapsed, 3), "startup_seconds": round(startup, 3), "metrics": dict(METRICS)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=int, nargs="?", const=100, default=0)
    args = parser.parse_args()
    if args.benchmark:
        benchmark(args.benchmark)
    else:
        self_test()
