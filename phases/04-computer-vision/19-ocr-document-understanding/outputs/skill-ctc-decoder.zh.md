---
name: skill-ctc-decoder
description: Write greedy and beam-search CTC decoders from scratch, including length normalisation
version: 1.0.0
phase: 4
lesson: 19
tags: [ocr, ctc, decoding, sequence-models]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="ctc-decoder"></a>

# CTC Decoder

为 CTC 输出生成两个解码例程：贪婪（快速）和光束（在噪声输入上效果更好）。

<a id="when-to-use"></a>

## 何时使用

- 在自定义 CRNN 输出上运行 OCR inference。
- 针对不同的 decoders 对预训练的 OCR 模型进行基准测试。
- 实现简单的波束搜索，无需引入 ctcdecode。

<a id="inputs"></a>

## 输入

- `log_probs`：（T、N、C）对词汇 softmax 进行记录（按照惯例，索引 0 = 空白）。
- `vocab`：C 字符列表。
- `beam_width`（仅限梁）：通常为 5-10。

<a id="greedy-decoder"></a>

## 贪婪 decoder

```python
def greedy_ctc_decode(log_probs, vocab, blank=0):
    preds = log_probs.argmax(dim=-1).transpose(0, 1).cpu().tolist()
    out = []
    for seq in preds:
        decoded = []
        prev = None
        for idx in seq:
            if idx != prev and idx != blank:
                decoded.append(vocab[idx])
            prev = idx
        out.append("".join(decoded))
    return out
```

<a id="beam-search-decoder"></a>

## 光束搜索decoder

```python
import heapq
import math

def beam_ctc_decode(log_probs, vocab, beam_width=5, blank=0):
    T, N, C = log_probs.shape
    lp = log_probs.cpu()
    results = []
    for n in range(N):
        beams = {("",): (0.0, -math.inf)}  # (prefix_tuple) -> (p_blank, p_nonblank)
        for t in range(T):
            logits_t = lp[t, n]
            new_beams = {}
            for prefix, (p_b, p_nb) in beams.items():
                for c in range(C):
                    p = logits_t[c].item()
                    if c == blank:
                        nb = p_b + p
                        nnb = p_nb + p
                        upd = new_beams.get(prefix, (-math.inf, -math.inf))
                        new_beams[prefix] = (
                            _logsumexp(upd[0], _logsumexp(nb, nnb)),
                            upd[1],
                        )
                    else:
                        last = prefix[-1] if prefix else ""
                        char = vocab[c]
                        if char == last:
                            # Case 1: stay on same prefix (collapse from p_nb)
                            upd = new_beams.get(prefix, (-math.inf, -math.inf))
                            new_beams[prefix] = (upd[0], _logsumexp(upd[1], p_nb + p))
                            # Case 2: extend prefix via blank-separated repeat ("a_a" -> "aa")
                            new_prefix = prefix + (char,)
                            upd = new_beams.get(new_prefix, (-math.inf, -math.inf))
                            new_beams[new_prefix] = (upd[0], _logsumexp(upd[1], p_b + p))
                        else:
                            new_prefix = prefix + (char,)
                            upd = new_beams.get(new_prefix, (-math.inf, -math.inf))
                            nb = _logsumexp(p_b, p_nb) + p
                            new_beams[new_prefix] = (upd[0], _logsumexp(upd[1], nb))
            beams = dict(heapq.nlargest(
                beam_width,
                new_beams.items(),
                key=lambda kv: _logsumexp(kv[1][0], kv[1][1]),
            ))
        best = max(beams.items(), key=lambda kv: _logsumexp(kv[1][0], kv[1][1]))[0]
        results.append("".join(best))
    return results


def _logsumexp(a, b):
    if a == -math.inf: return b
    if b == -math.inf: return a
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))
```

<a id="rules"></a>

## 规则

- 在PyTorch的`nn.CTCLoss`中，CTC中的空白索引按照惯例为0。
- 集束搜索提高了低置信度输入的准确性；对于清洁投入，改进<1% CER。
- 切勿修剪5以下的梁；准确率与延迟之间的关系在该值以下趋于平缓。
- 当在紧张的延迟预算内运行波束搜索时，请降至贪婪；大多数 OCR 生产数据的质量影响很小。
- 对于大型vocabularies（3000+字符的CJK），切换到`ctcdecode`（C++）而不是上面的纯Python版本； Python 梁很快成为瓶颈。
