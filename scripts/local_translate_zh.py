#!/usr/bin/env python3
"""Generate resumable, structurally checked Chinese companions for phases/*.md.

English sources are never rewritten. Translation is a machine draft, not an
independent technical verification of the source. Orchestration uses stdlib;
offline inference providers use separate, locally installed dependencies.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.request

from local_zh_markdown import prepare, rebuild, validate_segment, extract_invariants, _block_spans

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent / 'learning-artifacts' / 'chinese-translation'
NOTICE = '<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->\n\n'
SEP_RE = re.compile(r'\s*ZXQ(\d{6})QXZ\s*')
KEEP_RE = re.compile(r'ZXKEEP\d+QXZ')
LOCK = threading.Lock()
METRICS = Counter()


def digest(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def add_notice(body):
    # YAML must remain the first block, especially in portable skill artifacts.
    spans = _block_spans(body)
    if spans and spans[0][0] == 0 and spans[0][2] == 'frontmatter':
        stop = spans[0][1]
        return body[:stop] + NOTICE + body[stop:]
    return NOTICE + body


def remove_notice(body):
    return body.replace(NOTICE, '', 1)


def destination(p):
    return p.with_name('zh.md' if p.name == 'en.md' else p.stem + '.zh.md')


def glossary():
    terms = re.findall(r'^### (.+)$', (ROOT / 'glossary/terms.md').read_text(), re.M)
    terms = [re.sub(r'\s*\([^)]*\)', '', t).strip() for t in terms]
    terms += ['Prompt Engineering', 'prompt engineering', 'Prompt', 'prompts',
              'Chain-of-Thought', 'Tree-of-Thought', 'few-shot', 'zero-shot',
              'system prompt', 'system prompts', 'context window', 'context windows',
              'reinforcement learning', 'policy gradient', 'policy gradients',
              'reward model', 'reward models', 'value function', 'value functions',
              'state value', 'action value', 'rollout', 'rollouts', 'critic', 'actor',
              'agent harness', 'agent loop', 'agentic', 'tool calling', 'function calling',
              'elicitation', 'sampling', 'grounding', 'fine-tuning', 'pretraining',
              'log-derivative trick', 'off-policy', 'on-policy', 'backpropagation',
              'softmax', 'sigmoid', 'logits', 'embeddings', 'tokens', 'tokenizer',
              'Transformer', 'Transformers', 'Git', 'GitHub', 'Python', 'TypeScript',
              'JavaScript', 'Rust', 'Julia', 'NumPy', 'PyTorch', 'TensorFlow', 'JAX',
              'OpenAI', 'Anthropic', 'Claude', 'ChatGPT', 'Gemini', 'DeepSeek', 'Qwen',
              'Llama', 'Mistral', 'Docker', 'Kubernetes', 'FastAPI', 'LangGraph',
              'LangChain', 'LlamaIndex', 'vLLM', 'SGLang', 'Triton', 'CUDA', 'MLX',
              'ReLU', 'GELU', 'SiLU', 'Adam', 'AdamW', 'SwiGLU', 'RoPE', 'LoRA',
              'QLoRA', 'BERT', 'GPT', 'Word2Vec', 'Skip-gram', 'CBOW', 'DQN', 'PPO',
              'SAC', 'TD3', 'DDPG', 'REINFORCE', 'GRPO', 'RLHF', 'DPO', 'MCP', 'A2A',
              'Model Context Protocol', 'Forward Deployed Engineer', 'harness',
              'LLM', 'LLMs', 'API', 'APIs', 'SDK', 'SDKs', 'CPU', 'GPU', 'GPUs',
              'JSON', 'JSONL', 'YAML', 'XML', 'HTML', 'CSS', 'SQL', 'NoSQL',
              'REST', 'HTTP', 'HTTPS', 'TCP', 'TLS', 'ASCII', 'Unicode', 'Markdown',
              'Jupyter', 'VS Code', 'Visual Studio Code', 'pip', 'npm', 'pnpm',
              'uv', 'pytest', 'unittest', 'RNN', 'RNNs', 'CNN', 'CNNs', 'ViT',
              'VAE', 'GAN', 'GANs', 'RMSNorm', 'LayerNorm', 'BatchNorm', 'BPE',
              'SentencePiece', 'WordPiece', 'NLTK', 'spaCy', 'scikit-learn', 'SciPy',
              'Streamlit', 'system message', 'user message', 'assistant prefill',
              'under-constrained', 'underconstrained', 'prompt failures']
    extra = WORK / 'glossary-extra.json'
    if extra.exists():
        terms += json.loads(extra.read_text())
    return sorted(set(t for t in terms if len(t) > 2), key=lambda x: (-len(x), x))


def request_translation(q):
    url = 'https://translate.googleapis.com/translate_a/single?' + urllib.parse.urlencode(
        {'client': 'gtx', 'sl': 'en', 'tl': 'zh-CN', 'dt': 't', 'q': q})
    last = None
    for attempt in range(7):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                payload = json.load(response)
            translated = ''.join(p[0] for p in payload[0] if p and p[0])
            if q.strip() and not translated.strip():
                raise ValueError('empty translation')
            with LOCK:
                METRICS['requests'] += 1
            return translated
        except Exception as exc:
            last = exc
            with LOCK:
                METRICS['retries'] += 1
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f'translation request failed: {type(last).__name__}: {last}')


def safe_single(source):
    # Long paragraphs and unusual placeholder rewrites are isolated and retried
    # as prose fragments; protected spans never go through this fallback.
    if len(source) <= 3500:
        value = request_translation(source).strip()
        if validate_segment(source, value):
            return value
    chunks = re.split(r'(ZXKEEP\d+QXZ|(?<=[.!?;])\s+)', source)
    result = []
    for part in chunks:
        if not part or not part.strip() or KEEP_RE.fullmatch(part):
            result.append(part)
        elif len(part) <= 3500:
            result.append(request_translation(part).strip())
        else:
            words = re.findall(r'\S+\s*', part)
            buf = ''
            for word in words:
                if len(buf) + len(word) > 3000 and buf:
                    result.append(request_translation(buf).strip() + ' ')
                    buf = ''
                buf += word
            if buf:
                result.append(request_translation(buf).strip())
    value = ''.join(result)
    if not validate_segment(source, value):
        raise ValueError('placeholder mismatch in singleton fallback')
    return value


def translate_batch(items):
    if len(items) == 1 and len(items[0]) > 3500:
        return [safe_single(items[0])]
    source = ''.join((f'\nZXQ{i:06}QXZ\n' if i else '') + s for i, s in enumerate(items))
    raw = request_translation(source)
    pieces = SEP_RE.split(raw)
    if (len(pieces) == 2 * len(items) - 1 and
            pieces[1::2] == [f'{i:06}' for i in range(1, len(items))]):
        values = [s.strip() for s in pieces[::2]]
        if all(validate_segment(s, t) for s, t in zip(items, values)):
            return values
    with LOCK:
        METRICS['split_batches'] += 1
    if len(items) == 1:
        return [safe_single(items[0])]
    middle = len(items) // 2
    return translate_batch(items[:middle]) + translate_batch(items[middle:])


def batches(items, limit=3500):
    batch, size = [], 0
    for s in items:
        cost = len(s) + 20
        if batch and size + cost > limit:
            yield batch
            batch, size = [], 0
        batch.append(s)
        size += cost
    if batch:
        yield batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--provider', choices=['google', 'local', 'local-mps'], default='local')
    parser.add_argument('--phase')
    parser.add_argument('--only')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--cached-only', action='store_true',
                        help='Export only documents whose segments are already cached; never translate')
    args = parser.parse_args()
    provider_metrics = METRICS
    rejected_fragments = []
    WORK.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(WORK / 'translation-cache.sqlite3')
    conn.execute('CREATE TABLE IF NOT EXISTS translations (source TEXT PRIMARY KEY, translated TEXT NOT NULL)')
    sources = sorted(p for p in (ROOT / 'phases').rglob('*.md')
                     if p.name != 'zh.md' and not p.name.endswith('.zh.md')
                     and p.name != '中文教程索引.md')
    if args.phase:
        sources = [p for p in sources if p.relative_to(ROOT / 'phases').parts[0] == args.phase]
    if args.only:
        sources = [p for p in sources if str(p.relative_to(ROOT)) == args.only]
    docs, unique = [], {}
    terms = glossary()
    for p in sources:
        s = p.read_text(encoding='utf-8')
        prepared, segments = prepare(s, glossary=terms)
        docs.append((p, s, prepared, segments))
        for segment in segments:
            unique.setdefault(segment, None)
    print(json.dumps({'files': len(docs), 'segments': sum(len(d[3]) for d in docs),
                      'unique_segments': len(unique), 'characters': sum(map(len, unique)),
                      'glossary_terms': len(terms)}, ensure_ascii=False), flush=True)
    cache = dict(conn.execute('SELECT source, translated FROM translations'))
    pending = [s for s in unique if s not in cache]
    groups = list(batches(pending))
    print(f'Cached {len(unique)-len(pending)}; pending {len(pending)} segments in {len(groups)} batches', flush=True)
    started = time.monotonic()
    if not args.validate_only and not args.cached_only:
        provider_fn = translate_batch
        if args.provider == 'local':
            from local_zh_argos import translate_batch as provider_fn
            from local_zh_argos import METRICS as provider_metrics
            from local_zh_argos import REJECTED_FRAGMENTS as rejected_fragments
        elif args.provider == 'local-mps':
            from local_zh_mps import translate_batch as provider_fn
            from local_zh_mps import METRICS as provider_metrics
            from local_zh_argos import REJECTED_FRAGMENTS as rejected_fragments
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(provider_fn, b): b for b in groups}
            done = 0
            failures = []
            for future in as_completed(futures):
                group = futures[future]
                try:
                    values = future.result()
                    if len(values) != len(group) or not all(validate_segment(s, t) for s, t in zip(group, values)):
                        raise ValueError('provider output violates segment protection')
                except Exception as exc:
                    failures.append((group, str(exc)))
                    print(f'Batch failed: {type(exc).__name__}: {exc}', flush=True)
                    continue
                conn.executemany('INSERT OR REPLACE INTO translations VALUES (?,?)', zip(group, values))
                conn.commit()
                cache.update(zip(group, values))
                done += 1
                if done % 20 == 0 or done == len(groups):
                    print(f'Batches {done}/{len(groups)}; elapsed {time.monotonic()-started:.0f}s; metrics {dict(provider_metrics)}', flush=True)
            if failures:
                (WORK / 'failed-batches.json').write_text(
                    json.dumps([{'segments': group, 'error': error} for group, error in failures],
                               ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                raise RuntimeError(f'{len(failures)} batches failed; all completed batches cached')
        if groups:
            (WORK / 'decoder-rejections.json').write_text(
                json.dumps(rejected_fragments, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = []
    errors = []
    counts = Counter()
    editorial = {}
    if not args.validate_only:
        for overrides_path in sorted(WORK.glob('editorial-overrides*.json')):
            overrides = json.loads(overrides_path.read_text(encoding='utf-8'))
            for entry in overrides:
                if not validate_segment(entry['source'], entry['translated']):
                    raise ValueError('invalid editorial override')
                editorial[entry['source']] = entry['translated']
        print(f'Loaded {len(editorial)} editorial corrections', flush=True)
    try:
        from local_zh_postedit import refine
    except ImportError:
        refine = lambda source, translated, phase='': translated
    navigation = args.validate_only and (ROOT / 'phases' / '中文教程索引.md').exists()
    if navigation:
        from local_zh_navigation import (source_markdown_files, companion_path,
                                         rewrite_relative_links, add_source_heading_anchors)
        mapping = {f: companion_path(f) for f in source_markdown_files(ROOT)
                   if companion_path(f).exists()}
    for p, s, prepared, segments in docs:
        if args.cached_only and not all(segment in cache for segment in segments):
            continue
        dst = destination(p)
        rel = str(p.relative_to(ROOT))
        if args.validate_only:
            if not dst.exists():
                errors.append({'source': rel, 'error': 'missing Chinese companion'})
                continue
            translated = remove_notice(dst.read_text(encoding='utf-8'))
        else:
            phase = p.relative_to(ROOT / 'phases').parts[0]
            values = [editorial[t] if t in editorial else refine(t, cache[t], phase) for t in segments]
            translated = rebuild(prepared, values)
        expected_text = s
        if navigation:
            expected_text = rewrite_relative_links(s, dst, mapping)
            expected_text = add_source_heading_anchors(s, expected_text)
        before, after = extract_invariants(expected_text), extract_invariants(translated)
        problems = []
        for kind, expected in before.items():
            actual = after[kind]
            # Chinese grammar may reorder inline spans within a sentence.
            if kind in {'inline_code', 'math', 'link_targets', 'html', 'reference_ids'}:
                equal = Counter(expected) == Counter(actual)
            else:
                equal = expected == actual
            if not equal:
                problems.append(f'invariant changed: {kind}')
        if p.read_text(encoding='utf-8') != s:
            problems.append('English source changed during generation')
        if segments and not re.search(r'[\u4e00-\u9fff]', translated):
            problems.append('no Chinese prose')
        if problems:
            errors.append({'source': rel, 'errors': problems})
            continue
        if not args.validate_only:
            dst.write_text(add_notice(translated), encoding='utf-8')
        counts[p.relative_to(ROOT / 'phases').parts[0]] += 1
        manifest.append({'source': rel, 'chinese': str(dst.relative_to(ROOT)),
                         'source_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                         'chinese_sha256': hashlib.sha256(dst.read_bytes()).hexdigest(),
                         'segments': len(segments)})
    report = {'provider': 'Google Translate cached segments + offline OPUS-MT (CTranslate2 CPU / Marian MPS) remaining segments',
              'run_provider': args.provider,
              'run_mode': 'validation' if args.validate_only else 'cached_export' if args.cached_only else 'generation',
              'status': 'machine draft; selected lessons language-reviewed; not fully proofread',
              'source_files': len(docs), 'written_and_verified': len(manifest),
              'phases': dict(counts), 'errors': errors, 'metrics': dict(provider_metrics),
              'editorial_corrections': len(editorial),
              'navigation_adjusted': navigation,
              'elapsed_seconds': round(time.monotonic()-started, 1), 'files': manifest}
    complete_export = (len(manifest) == len(docs) and not errors and not args.phase and not args.only)
    report_path = WORK / ('validation-report.json' if args.validate_only else
                          'partial-manifest.json' if args.cached_only and not complete_export
                          else 'translation-manifest.json')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'files'}, ensure_ascii=False), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
