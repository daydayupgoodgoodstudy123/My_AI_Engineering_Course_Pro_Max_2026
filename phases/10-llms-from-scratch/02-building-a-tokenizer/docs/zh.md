<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="building-a-tokenizer-from-scratch"></a>

# 从头开始构建 Tokenizer

> 第 01 课给了你一个玩具。本课程为您提供武器。

**类型：** 构建
**语言：** Python
**先决条件：** 第 10 阶段，第 01 课（Tokenizers：BPE、WordPiece、SentencePiece）
**时间：** ~90 分钟

<a id="learning-objectives"></a>

## 学习目标

- 构建一个生产级 BPE tokenizer，用于处理 Unicode、空白 normalization 和特殊 tokens
- 实现字节级回退，以便 tokenizer 可以对任何输入（包括表情符号、CJK 和代码）进行编码，而无需未知 tokens
- 添加 pre-tokenization 正则表达式模式，在应用 BPE 合并之前在单词边界处分割文本
- 在语料库上训练自定义 tokenizer 并评估其在多语言文本上与 tiktoken 的压缩比

<a id="the-problem"></a>

## 问题

第 01 课中的 BPE tokenizer 适用于英文文本。现在把日语扔进去。或者表情符号。或者混合制表符和空格的 Python 代码。

它坏了。

不是因为 BPE 是错误的——因为实现不完整。生产 tokenizer 处理任何编码中的原始字节，在分割之前规范化 Unicode，管理永远不会合并的特殊 tokens，通过子字分割链接 pre-tokenization，并且所有这些都足够快，不会成为处理 15 万亿的训练管道的瓶颈tokens。

GPT-2的tokenizer有50,257个tokens。 Llama 3 有 128,256。 GPT-4 大约有 100,000 个。这些不是玩具数字。这些 vocabularies 背后的合并表接受了数百 GB 文本的训练，而周围的机制——normalization、预 tokenization、特殊的 token 注入、聊天模板格式化——是区分处理 tokenizer 的原因。来自处理整个互联网的“hello world”。

你将建造那台机器。

<a id="the-concept"></a>

## 概念

<a id="the-full-pipeline"></a>

### 完整的管道

生产 tokenizer 不是一种算法。它是一个由五个阶段组成的管道，每个阶段解决不同的问题。

```mermaid
graph LR
    A[Raw Text] --> B[Normalize]
    B --> C[Pre-Tokenize]
    C --> D[BPE Merge]
    D --> E[Special Tokens]
    E --> F[Token IDs]

    style A fill:#1a1a2e,stroke:#e94560,color:#fff
    style B fill:#1a1a2e,stroke:#e94560,color:#fff
    style C fill:#1a1a2e,stroke:#e94560,color:#fff
    style D fill:#1a1a2e,stroke:#e94560,color:#fff
    style E fill:#1a1a2e,stroke:#e94560,color:#fff
    style F fill:#1a1a2e,stroke:#e94560,color:#fff
```

每个阶段都有特定的工作：

| 舞台 | 它的作用 | 为什么它很重要 |
|-------|-------------|----------------|
| 标准化 | NFKC Unicode，小写可选，条状重音可选 | “fi”连字 (U+FB01) 变为“fi”（两个字符）。如果没有这个，相同的单词会得到不同的 tokens。 |
| 预标记化 | 在 BPE 之前将文本分割成块 | 防止 BPE 跨字边界合并。 “the cat”永远不应该产生 token “e c”。 |
| BPE 合并 | 将学习的合并规则应用于字节序列 | 核心压缩。将原始字节转换为子字 tokens。 |
| 特价Tokens | 注入[BOS]、[EOS]、[PAD]、聊天模板标记 | 这些tokens有固定的ID。他们从不参与 BPE 合并。该模型需要它们来构建结构。 |
| ID映射 | 将 token 字符串转换为整数 ID | 该模型看到的是整数，而不是字符串。 |

<a id="byte-level-bpe"></a>

### 字节级 BPE

第01课的tokenizer对UTF-8字节进行操作。这是正确的决定。但我们跳过了一些重要的事情：当这些字节不是有效的 UTF-8 时会发生什么？

字节级 BPE 通过将每个可能的字节值 (0-255) 视为有效的 token 来解决此问题。您的基础 vocabulary 正好有 256 个条目。任何文件——文本文件、二进制文件、损坏的文件——都可以被标记化，而不会产生未知的 token。

GPT-2 添加了一个技巧：将每个字节映射到可打印的 Unicode 字符，以便 vocabulary 保持人类可读。字节 0x20（空格）在其映射中成为字符“G”。这纯粹是装饰性的。算法并不关心。

真正的力量：字节级 BPE 可以处理地球上的每种语言。中文字符每个为 3 个 UTF-8 字节。日语可以是 3-4 个字节。阿拉伯语、梵文、表情符号——都只是字节序列。 BPE 算法在这些字节序列中查找模式的方式与在英语 ASCII 字节中查找模式的方式完全相同。

<a id="pre-tokenization"></a>

### 预售 Tokenization

在 BPE 接触您的文本之前，您需要将其分割成块。这可以防止合并算法创建跨越字边界的 tokens。

GPT-2 使用正则表达式模式来分割文本：

```
'(?:[sdmt]|ll|ve|re)| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+
```

此模式根据缩写（“don't”变为“don”+“'t”）、带有可选前导空格、数字、标点符号和空格的单词进行拆分。前导空格保留在单词上 - 所以“the cat”变成了 [" the", " cat"]，而不是 ["the", " ", "cat"]。

Llama 使用 SentencePiece，它完全跳过正则表达式。它将原始字节流视为一个长序列，并让 BPE 算法找出边界。这更简单，但为 BPE 提供了更多自由来创建跨字 tokens。

选择很重要。 GPT-2 的正则表达式会阻止 tokenizer 了解一个单词末尾的“the”和下一个单词开头的“the”应该合并。 SentencePiece 允许这样做，有时会产生更有效的压缩，但可解释性较差 tokens。

<a id="special-tokens"></a>

### 特价Tokens

每个生产 tokenizer 都保留 token ID 用于结构标记：

| Token | 目的 | 使用者 |
|-------|---------|---------|
| `[BOS]` / `<s>` | 序列的开始 | Llama 3, GPT |
| `[EOS]` / `</s>` | 序列结束 | 所有型号 |
| `[PAD]` | 批次填充 alignment | BERT，T5 |
| `[UNK]` | 未知token（字节级BPE消除了这个） | BERT, WordPiece |
| `<\|im_start\|>` | 聊天消息边界开始 | ChatGPT, Qwen |
| `<\|im_end\|>` | 聊天消息边界结束 | ChatGPT, Qwen |
| `<\|user\|>` | 用户转弯标记 | Llama 3 |
| `<\|assistant\|>` | 助理转弯标记 | Llama 3 |

特殊的tokens永远不会被BPE分割。它们在合并算法运行之前完全匹配，用它们的固定 ID 替换，并且周围的文本正常标记化。

<a id="chat-templates"></a>

### 聊天模板

这是大多数人感到困惑和大多数实现失败的地方。

当您向聊天模型发送消息时，API 接受消息列表：

```
[
  {"role": "system", "content": "You are helpful."},
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi there!"}
]
```

该型号没有看到 JSON。它看到一个平坦的 token 序列。聊天模板使用特殊的 tokens 将消息转换为平面序列。每个模型的做法都不同：

```
Llama 3:
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are helpful.<|eot_id|><|start_header_id|>user<|end_header_id|>

Hello<|eot_id|><|start_header_id|>assistant<|end_header_id|>

Hi there!<|eot_id|>

ChatGPT:
<|im_start|>system
You are helpful.<|im_end|>
<|im_start|>user
Hello<|im_end|>
<|im_start|>assistant
Hi there!<|im_end|>
```

如果模板错误，模型就会产生垃圾。它是按照一种精确的格式进行训练的。任何偏差——缺少换行符、交换的 token、额外的空格——都会将输入置于训练分布之外。

<a id="speed"></a>

### 速度

Python 对于生产 tokenization 来说太慢。

tiktoken（OpenAI）是用 Rust 编写的，并具有 Python 绑定。 HuggingFace tokenizers 也是 Rust。 SentencePiece 是 C++。与纯 Python 相比，它们实现了 10-100 倍的加速。

从长远来看：将 15 万亿个 tokens 代币化为 100 万个 tokens per second（快速 Python）的 Llama 3 预训练需要 174 天。 1亿个tokens per second（Rust），需要1.7天。

您正在构建 Python 来理解该算法。在生产中，您将使用已编译的实现，并且仅触及 Python 包装器。

```figure
weight-tying
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-byte-level-encoding"></a>

### 第 1 步：字节级编码

基础。将任何字符串转换为字节序列，将每个字节映射到可打印字符以进行显示，然后反转该过程。

```python
def bytes_to_tokens(text):
    return list(text.encode("utf-8"))

def tokens_to_text(token_bytes):
    return bytes(token_bytes).decode("utf-8", errors="replace")
```

对多语言文本进行测试以查看字节数：

```python
texts = [
    ("English", "hello"),
    ("Chinese", "你好"),
    ("Emoji", "🔥"),
    ("Mixed", "hello你好🔥"),
]

for label, text in texts:
    b = bytes_to_tokens(text)
    print(f"{label}: {len(text)} chars -> {len(b)} bytes -> {b}")
```

“你好”是 5 个字节。 “你好”是 6 个字节（每个字符 3 个字节）。火表情符号有 4 个字节。字节级tokenizer并不关心它是什么语言。字节就是字节。

<a id="step-2-pre-tokenizer-with-regex"></a>

### 第2步：使用正则表达式预Tokenizer

使用 GPT-2 正则表达式模式将文本拆分为块。每个块都由 BPE 独立标记。

```python
import re

try:
    import regex
    GPT2_PATTERN = regex.compile(
        r"""'(?:[sdmt]|ll|ve|re)| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""
    )
except ImportError:
    GPT2_PATTERN = re.compile(
        r"""'(?:[sdmt]|ll|ve|re)| ?[a-zA-Z]+| ?[0-9]+| ?[^\s\w]+|\s+(?!\S)|\s+"""
    )

def pre_tokenize(text):
    return [match.group() for match in GPT2_PATTERN.finditer(text)]
```

`regex` 模块支持 Unicode 属性转义（字母为 `\p{L}`，数字为 `\p{N}`）。标准库 `re` 模块没有，因此我们回退到 ASCII 字符类。对于生产多语言 tokenizers，请安装 `regex`。

尝试一下：

```python
print(pre_tokenize("Hello, world! Don't stop."))
# [' Hello', ',', ' world', '!', " Don", "'t", ' stop', '.']
```

前导空格仍然附着在单词上。缩写在撇号处分开。标点符号成为它自己的块。 BPE 永远不会跨越这些边界合并 tokens。

<a id="step-3-bpe-on-byte-sequences"></a>

### 步骤 3：字节序列上的 BPE

第 01 课中的核心算法，但现在独立地在预标记化块上运行。

```python
from collections import Counter

def get_byte_pairs(chunks):
    pairs = Counter()
    for chunk in chunks:
        byte_seq = list(chunk.encode("utf-8"))
        for i in range(len(byte_seq) - 1):
            pairs[(byte_seq[i], byte_seq[i + 1])] += 1
    return pairs

def apply_merge(byte_seq, pair, new_id):
    merged = []
    i = 0
    while i < len(byte_seq):
        if i < len(byte_seq) - 1 and byte_seq[i] == pair[0] and byte_seq[i + 1] == pair[1]:
            merged.append(new_id)
            i += 2
        else:
            merged.append(byte_seq[i])
            i += 1
    return merged
```

<a id="step-4-special-token-handling"></a>

### 第4步：特殊Token处理

特殊tokens需要精确匹配且固定的ID。他们完全绕过 BPE。

```python
class SpecialTokenHandler:
    def __init__(self):
        self.special_tokens = {}
        self.pattern = None

    def add_token(self, token_str, token_id):
        self.special_tokens[token_str] = token_id
        escaped = [re.escape(t) for t in sorted(self.special_tokens.keys(), key=len, reverse=True)]
        self.pattern = re.compile("|".join(escaped))

    def split_with_specials(self, text):
        if not self.pattern:
            return [(text, False)]
        parts = []
        last_end = 0
        for match in self.pattern.finditer(text):
            if match.start() > last_end:
                parts.append((text[last_end:match.start()], False))
            parts.append((match.group(), True))
            last_end = match.end()
        if last_end < len(text):
            parts.append((text[last_end:], False))
        return parts
```

<a id="step-5-full-tokenizer-class"></a>

### 第5步：完整的Tokenizer类

将所有内容链接在一起：规范化、在特殊 tokens 上拆分、预标记、BPE 合并、映射到 ID。

```python
import unicodedata

class ProductionTokenizer:
    def __init__(self):
        self.merges = {}
        self.vocab = {i: bytes([i]) for i in range(256)}
        self.special_handler = SpecialTokenHandler()
        self.next_id = 256

    def normalize(self, text):
        return unicodedata.normalize("NFKC", text)

    def train(self, text, num_merges):
        text = self.normalize(text)
        chunks = pre_tokenize(text)
        chunk_bytes = [list(chunk.encode("utf-8")) for chunk in chunks]

        for i in range(num_merges):
            pairs = Counter()
            for seq in chunk_bytes:
                for j in range(len(seq) - 1):
                    pairs[(seq[j], seq[j + 1])] += 1
            if not pairs:
                break
            best = max(pairs, key=pairs.get)
            new_id = self.next_id
            self.next_id += 1
            self.merges[best] = new_id
            self.vocab[new_id] = self.vocab[best[0]] + self.vocab[best[1]]
            chunk_bytes = [apply_merge(seq, best, new_id) for seq in chunk_bytes]

    def add_special_token(self, token_str):
        token_id = self.next_id
        self.next_id += 1
        self.special_handler.add_token(token_str, token_id)
        self.vocab[token_id] = token_str.encode("utf-8")
        return token_id

    def encode(self, text):
        text = self.normalize(text)
        parts = self.special_handler.split_with_specials(text)
        all_ids = []
        for part_text, is_special in parts:
            if is_special:
                all_ids.append(self.special_handler.special_tokens[part_text])
            else:
                for chunk in pre_tokenize(part_text):
                    byte_seq = list(chunk.encode("utf-8"))
                    for pair, new_id in self.merges.items():
                        byte_seq = apply_merge(byte_seq, pair, new_id)
                    all_ids.extend(byte_seq)
        return all_ids

    def decode(self, ids):
        byte_parts = []
        for token_id in ids:
            if token_id in self.vocab:
                byte_parts.append(self.vocab[token_id])
        return b"".join(byte_parts).decode("utf-8", errors="replace")

    def vocab_size(self):
        return len(self.vocab)
```

<a id="step-6-multilingual-test"></a>

### 第6步：多语言测试

真正的考验。向它扔英文、中文、表情符号和代码。

```python
corpus = (
    "The quick brown fox jumps over the lazy dog. "
    "The quick brown fox runs through the forest. "
    "Machine learning models process natural language. "
    "Deep learning transforms how we build software. "
    "def train(model, data): return model.fit(data) "
    "def predict(model, x): return model(x) "
)

tok = ProductionTokenizer()
tok.train(corpus, num_merges=50)

bos = tok.add_special_token("<|begin|>")
eos = tok.add_special_token("<|end|>")

test_texts = [
    "The quick brown fox.",
    "你好世界",
    "Hello 🌍 World",
    "def foo(x): return x + 1",
    f"<|begin|>Hello<|end|>",
]

for text in test_texts:
    ids = tok.encode(text)
    decoded = tok.decode(ids)
    print(f"Input:   {text}")
    print(f"Tokens:  {len(ids)} ids")
    print(f"Decoded: {decoded}")
    print()
```

每个汉字产生 3 个字节。表情符号产生 4 个字节。这些都不会导致 tokenizer 崩溃。没有一个产生未知的 tokens。这就是字节级BPE的威力。

<a id="use-it"></a>

## 实际应用

<a id="comparing-real-tokenizers"></a>

### 比较真实的Tokenizers

从 Llama 3、GPT-4 和 Mistral 加载实际的 tokenizers。了解每个人如何处理相同的多语言段落。

```python
import tiktoken

gpt4_enc = tiktoken.get_encoding("cl100k_base")

test_paragraph = "Machine learning is powerful. 机器学习很强大。 L'apprentissage automatique est puissant. 🤖💪"

tokens = gpt4_enc.encode(test_paragraph)
pieces = [gpt4_enc.decode([t]) for t in tokens]
print(f"GPT-4 ({len(tokens)} tokens): {pieces}")
```

```python
from transformers import AutoTokenizer

llama_tok = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B")
mistral_tok = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-v0.1")

for name, tok in [("Llama 3", llama_tok), ("Mistral", mistral_tok)]:
    tokens = tok.encode(test_paragraph)
    pieces = tok.convert_ids_to_tokens(tokens)
    print(f"{name} ({len(tokens)} tokens): {pieces[:20]}...")
```

您将看到相同文本的不同 token 计数。 Llama 3 与 128K vocabulary 在合并常见模式方面更加积极。 GPT-4 100K 位于中间。 32K 的 Mistral 产生更多的 tokens，但具有更小的 embedding 层。

权衡总是相同的：更大的 vocabulary 意味着更短的序列，但更多的 parameters。

<a id="ship-it"></a>

## 交付成果

本课程生成一个 prompt，用于构建和调试生产 tokenizers。参见 `outputs/prompt-tokenizer-builder.md`。

<a id="exercises"></a>

## 练习

1. **Easy:** 添加 `get_token_bytes(id)` 方法，该方法显示任何 token ID 的原始字节。用它来检查最常见的合并 tokens 实际代表的内容。
2. **Medium:** 实现 Llama 样式的 pre-tokenizer，它在空格和数字上分割，但保留前导空格。在同一语料库上将其 vocabulary 与 GPT-2 正则表达式方法进行比较。
3. **难的：**添加一个聊天模板方法，该方法接受列表`{"role": ..., "content": ...}`消息并产生正确的token的序列为Llama3.聊天格式。 针对 HuggingFace 实现对其进行测试。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| 字节级 BPE | “Tokenizer 适用于字节” | BPE，具有 256 字节值的基础 vocabulary——处理没有未知 tokens 的任何输入 |
| 预售tokenization | “在BPE之前分裂” | 正则表达式或基于规则的分割，防止 BPE 跨字边界合并 |
| NFKC normalization | “Unicode 清理” | 规范分解后进行兼容性组合 - “fi”连字变为“fi”，全角“A”变为“A” |
| 聊天模板 | 《消息如何变成tokens》 | 将角色/内容消息列表转换为平面 token 序列的确切格式 - 特定于模型且必须匹配训练格式 |
| 特别tokens | “控制tokens” | 绕过 BPE 的保留 token ID -- [BOS]、[EOS]、 [PAD]，聊天标记——合并前完全匹配 |
| 生育能力 | “每个字 Tokens” | 输出 tokens 与输入单词的比率 -- GPT-4 中英语为 1.3，韩语为 2-3，较高意味着浪费上下文 |
| 抖音 | "OpenAI tokenizer" | Rust BPE 与 Python 绑定的实现——比纯 Python 快 10-100 倍 |
| 合并表 | “vocabulary” | 训练期间学到的字节对合并的有序列表——这是 tokenizer 学到的知识 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI tiktoken源码](https://github.com/openai/tiktoken) -- Rust BPE使用的实现GPT-3.5/4
- [HuggingFace tokenizers](https://github.com/huggingface/tokenizers) -- Rust tokenizer 支持 BPE 的库， WordPiece，一元语法
- [Llama 3篇论文（Meta，2024）](https://arxiv.org/abs/2407.21783) -- 128K vocabulary 和 tokenizer 训练的详细信息
- [SentencePiece (Kudo & Richardson, 2018)](https://arxiv.org/abs/1808.06226) -- 与语言无关的 tokenization
- [GPT-2 tokenizer source](https://github.com/openai/gpt-2/blob/master/src/encoder.py) -- 原始字节到Unicode的映射
