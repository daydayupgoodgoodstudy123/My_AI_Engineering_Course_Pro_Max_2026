# 测验 · 从头开始构建 Tokenizer（Building a Tokenizer from Scratch）

> **阶段 10 · 从零构建 LLM · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 生产级 tokenizer 是一条流水线 | Normalize → Pre-Tokenize → BPE Merge → Special Tokens → ID 映射，每一段解决一个不同的问题 |
| 2 | NFKC 规范化 | 把兼容字符统一：连字 "ﬁ"（U+FB01）→ "fi"，全角 "Ａ" → "A"；否则同一个词会得到不同 token。代价是**有损**，解码不一定还原原文 |
| 3 | Byte-level BPE | 256 个字节作为基础词表，任何输入（中文、emoji、代码甚至二进制）都能编码；GPT-2 把字节映射成可打印字符只是为了好看 |
| 4 | 预分词（pre-tokenization） | 先用正则把文本切成词、数字、标点、空白片段，BPE 只在片段内合并，杜绝 "e c" 这种跨词 token |
| 5 | GPT-2 正则的细节 | 缩写单独切（`'t`、`'ll`）、前导空格粘在词前（`" the"`）、`\s+(?!\S)` 把最后一个空格留给下一个词 |
| 6 | SentencePiece 的不同选择 | Llama 2 等不用正则，直接在原始流上做 BPE，压缩可能更好但会产生跨词 token、可解释性差 |
| 7 | 特殊 token | 固定 ID、在 BPE 之前精确匹配、永不参与合并；多个特殊 token 按长度降序构造正则，保证长的优先匹配 |
| 8 | Chat template | 把 `[{"role", "content"}]` 消息列表展平成带特殊 token 的序列，每个模型格式不同；少一个换行都可能让输入落到训练分布之外 |
| 9 | 速度 | 纯 Python 太慢：15T token 以 100 万 token/秒处理要约 174 天，以 1 亿 token/秒（Rust）约 1.7 天 |

### 核心技能（能动手做到）

- [ ] 写出完整的 `ProductionTokenizer`：NFKC 规范化 + 正则预分词 + 片段内 BPE + 特殊 token + 编解码
- [ ] 手动预测 GPT-2 正则对一段含缩写、数字、标点、多空格文本的切分结果
- [ ] 用 `"".join(pre_tokenize(s)) == s` 检查预分词是否**丢字符**，并定位、修复 `re` 回退正则在中文/下划线上的 bug
- [ ] 实现 `SpecialTokenHandler`，正确处理"一个特殊 token 是另一个前缀"的情况
- [ ] 为 Llama 3 格式写出 chat template 函数，并用自己的 tokenizer 编码、往返验证
- [ ] 能解释 NFKC 为什么会让 `decode(encode(x)) != x`，并说出何时应该/不应该做规范化

---

## 二、基础自测（选择题）

**Q1.** 讲义中生产级 tokenizer 流水线的正确顺序是：

- A. Pre-Tokenize → Normalize → BPE Merge → Special Tokens → Token IDs
- B. Normalize → Pre-Tokenize → BPE Merge → Special Tokens → Token IDs
- C. BPE Merge → Normalize → Pre-Tokenize → Special Tokens → Token IDs
- D. Special Tokens → BPE Merge → Normalize → Pre-Tokenize → Token IDs

**Q2.** 使用本节代码中的 GPT-2 预分词正则，`pre_tokenize("a   b")`（a 和 b 之间有 3 个空格）的结果是：

- A. `['a', '   ', 'b']`
- B. `['a', '  ', ' b']`
- C. `['a', ' ', ' ', ' b']`
- D. `['a', '   b']`

**Q3.** 关于 NFKC 规范化，下列说法**错误**的是：

- A. 它会把连字 "ﬁ" 变成两个字符 "fi"
- B. 它会把全角 "Ａ" 变成半角 "A"
- C. 它是无损的，所以 `decode(encode(x)) == x` 对任何输入都成立
- D. 它的目的是让"看起来一样"的文本得到相同的 token

**Q4.** `SpecialTokenHandler.add_token` 在拼接正则前，先把所有特殊 token **按长度降序**排序。这样做的主要目的是：

- A. 让正则匹配更快
- B. 当一个特殊 token 是另一个的前缀时，保证更长的那个优先被匹配
- C. 让特殊 token 的 ID 按长度分配
- D. Python 的 `re` 模块要求备选项必须按长度排序

**Q5.** 讲义估算：用纯 Python 以每秒 100 万 token 的速度处理 Llama 3 的 15 万亿（15T）预训练 token，大约需要：

- A. 1.7 天
- B. 17 天
- C. 174 天
- D. 1,740 天

**Q6.** 关于 chat template，下列说法正确的是：

- A. 所有模型都使用相同的 chat template，因为 API 输入都是 JSON
- B. 模型直接读取 JSON 格式的消息列表
- C. 每个模型的格式不同；缺一个换行、换错一个特殊 token，都可能让输入偏离训练分布，导致输出变差
- D. chat template 只影响 system prompt，不影响 user/assistant 轮次

**Q7.** GPT-2 式正则预分词与 SentencePiece（如 Llama 2）"不做正则、直接在原始流上 BPE"相比，下列说法正确的是：

- A. SentencePiece 的方式完全不可能产生跨词 token
- B. GPT-2 正则禁止跨词合并；SentencePiece 允许，有时压缩更好，但 token 更难解释
- C. 两者学到的词表一定完全相同
- D. GPT-2 正则会把前导空格单独切成一个片段

---

## 三、动手 / 代码题

**Q8.** 在**没有安装 `regex` 包**的环境里运行本节 `main.py`，出现了这样的结果：

```text
Input:   你好世界 Hello World
IDs:     [32, 72, 101, 108, 108, 111, 32, 87, 111, 114, 108, 100]
Tokens:  12 (from 24 bytes, ratio: 0.50)
Decoded:  Hello World
Round-trip: FAIL
```

相关代码：

```python
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

1. 解释"你好世界"为什么凭空消失了。它没有报错，为什么这比报错更危险？
2. 再举出至少两类会被同样"吞掉"的输入（提示：想想代码和欧洲语言）。
3. 只用标准库 `re`，修复回退正则，并写一行能在单元测试里防止此类 bug 的断言。

**Q9.** 不运行代码，写出下面三行的输出（使用 Q8 中 `re` 回退版的正则即可，这几个输入在两版正则下结果相同）：

```python
print(pre_tokenize("I'm here, they'll go"))
print(pre_tokenize("The price is $3.14 per unit."))
print(pre_tokenize("  multiple   spaces   here  "))
```

并说明：为什么讲义 Step 2 的注释写 `pre_tokenize("Hello, world! Don't stop.")` 的第一个片段是 `' Hello'`，实际运行却是 `'Hello'`？

**Q10.** 完成讲义练习 3 的核心部分：写一个函数 `apply_llama3_template(messages, add_generation_prompt=False)`，按讲义给出的 Llama 3 格式把消息列表转成字符串；然后用本节的 `ProductionTokenizer` 注册所需的特殊 token、编码并验证往返一致。

---

## 四、面试高频题

**Q11.**（基础必考）一个生产级 tokenizer 由哪些阶段组成？每个阶段解决什么问题？如果去掉预分词会怎样？

**Q12.**（原理深挖）GPT-2 的预分词正则是怎么设计的？为什么前导空格要粘在单词前面？为什么很多新 tokenizer 会对数字做特殊切分？

**Q13.**（工程实践 / 安全）用户输入里出现了 `<|im_end|>` 或 `<|eot_id|>` 这样的字符串，tokenizer 应该怎么处理？本节代码的做法有什么风险？

**Q14.**（场景设计）你把一个开源 chat 模型做了 SFT，上线后发现它"停不下来"、一直自问自答，或者回答质量明显比基座差。从 tokenizer 和 chat template 的角度，你会怎么排查？

**Q15.**（追问型）Unicode 规范化（如 NFKC）要不要做？做了有什么好处、会引入什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：B

先规范化（统一字符形式），再预分词（切片段），再在片段内做 BPE 合并，然后处理特殊 token，最后映射成 ID。讲义的流程图正是 `Raw Text → Normalize → Pre-Tokenize → BPE Merge → Special Tokens → Token IDs`。注意在本节代码的 `encode` 实现里，"识别特殊 token"其实发生在预分词之前（先 `split_with_specials` 把特殊 token 切出来，剩下的普通文本再预分词和合并），这样特殊 token 才不会被 BPE 拆开；流程图里的"Special Tokens"阶段强调的是"特殊 token 被替换成固定 ID 并注入序列"。

### Q2 — 答案：B

`'a'` 先被 ` ?[a-zA-Z]+` 匹配。剩下 `"   b"`：`\s+(?!\S)` 尝试匹配尽可能多的空白，但要求其后**不是**非空白字符；3 个空格后面紧跟 `b`，于是回退到 2 个空格（其后是第 3 个空格，满足条件）。最后 `" b"` 被 ` ?[a-zA-Z]+` 匹配，前导空格粘在词上。这个设计让"词前空格"始终与词一起出现，保证 `" b"` 与正常句子里的 `" b"` 是同一个 token。（已实际运行验证：`['a', '  ', ' b']`。）

### Q3 — 答案：C

NFKC 会改变文本本身（"ﬁ"→"fi"、"Ａ"→"A"、"²"→"2" 等），所以对这类输入，解码出来的是规范化后的文本而不是原文，往返不成立。A、B、D 都是 NFKC 的正确描述，讲义 Key Terms 也给出了 "ﬁ" 和全角 "A" 两个例子。

### Q4 — 答案：B

正则的 `|` 备选是"从左到右，第一个能匹配的就用"，不是"最长匹配"。如果同时注册了 `<|end|>` 和 `<|end|>!`，而 `<|end|>` 排在前面，文本 `<|end|>!` 永远只会匹配到 `<|end|>`，后面的 `!` 被当成普通文本。按长度降序排序后，长 token 先尝试，问题消失。A、C、D 都不是原因：`re` 对顺序没有要求，ID 由 `next_id` 依次分配，与排序无关。

### Q5 — 答案：C

`15 × 10¹² ÷ 10⁶ = 1.5 × 10⁷ 秒 ≈ 173.6 天`。换成 1 亿 token/秒（Rust 实现）则约 1.7 天（选项 A）。这就是 tiktoken、HF tokenizers、SentencePiece 都用 Rust/C++ 实现的原因。

### Q6 — 答案：C

模型看到的不是 JSON，而是被 chat template 展平后的 token 序列。Llama 3 用 `<|start_header_id|>...<|end_header_id|>` 与 `<|eot_id|>`，ChatGPT/Qwen 用 `<|im_start|>`/`<|im_end|>`。模型只在一种精确格式上训练过，任何偏差都会让输入落到训练分布之外。

### Q7 — 答案：B

讲义原文：GPT-2 的正则阻止 tokenizer 学到跨词合并；SentencePiece 允许跨词，有时压缩更高效，但 token 更难解释。A 恰好相反；C 不成立，预分词改变了 pair 统计；D 错，GPT-2 正则把前导空格**粘在词前**（`" the"`），而不是单独切开。

### Q8 — 参考答案

1. **原因**：标准库 `re` 不支持 `\p{L}`，回退正则用 `[a-zA-Z]` 表示"字母"，用 `[^\s\w]` 表示"标点"。而 Python 3 的 `re` 对 `str` 默认按 Unicode 处理，`\w` 包含汉字。于是汉字既不是 `[a-zA-Z]`、也不是 `[0-9]`、又不属于 `[^\s\w]`（因为它属于 `\w`）、也不是空白——**没有任何一个分支能匹配它**。`finditer` 只返回匹配到的片段，没匹配上的字符被静默跳过。静默丢数据比报错更危险：训练语料里的中文会悄无声息地消失，tokenizer 指标看起来还很好（压缩比 0.50），问题可能在模型训练完才被发现。
2. **同类受害者**（均已实际验证）：
   - 下划线：`"my_var = 1"` → `['my', 'var', ' =', ' 1']`，`_` 丢失——对代码是灾难；
   - 带重音的拉丁字母：`"café naïve"` → `['caf', ' na', 've']`；
   - 日文、韩文等所有非 ASCII 字母，以及 `²`、`①` 这类属于 `\w` 的符号。
3. **修复**：

```python
GPT2_PATTERN = re.compile(
    r"""'(?:[sdmt]|ll|ve|re)| ?[^\W\d_]+| ?\d+| ?(?:[^\s\w]|_)+|\s+(?!\S)|\s+"""
)
```

- `[^\W\d_]` = "属于 `\w`、但不是数字也不是下划线"，即 Unicode 字母，相当于 `\p{L}` 的近似；
- `\d` 在 Unicode 模式下匹配各种十进制数字；
- `(?:[^\s\w]|_)` 把下划线归入"标点"类。

修复后 `"你好世界 Hello World"` → `['你好世界', ' Hello', ' World']`，`"my_var = 1"` → `['my', '_', 'var', ' =', ' 1']`。防回归断言：

```python
assert "".join(pre_tokenize(s)) == s, f"pre_tokenize dropped characters: {s!r}"
```

预分词只是"切分"，拼回去必须等于原文。这条不变量应该对一组多语言、代码、emoji 样本逐一检查。

### Q9 — 参考答案

```text
['I', "'m", ' here', ',', ' they', "'ll", ' go']
['The', ' price', ' is', ' $', '3', '.', '14', ' per', ' unit', '.']
[' ', ' multiple', '  ', ' spaces', '  ', ' here', '  ']
```

- 缩写分支 `'(?:[sdmt]|ll|ve|re)` 把 `'m`、`'ll` 单独切出。
- `$3.14`：`' $'` 是"可选空格 + 标点"；数字被 `.` 切成 `'3'`、`'.'`、`'14'` 三段——小数点属于标点类。
- 多空格：开头两个空格中，`\s+(?!\S)` 只能吃掉第 1 个（再多就紧跟 `m` 了），第 2 个空格和 `multiple` 组成 `' multiple'`；词与词之间的 3 个空格拆成 `'  '` + 前导空格；末尾的两个空格后面没有非空白字符，整体匹配为 `'  '`。

讲义注释的问题：输入 `"Hello, world! Don't stop."` 以 `H` 开头，**没有前导空格**，正则 ` ?\p{L}+` 中的空格是可选的，所以第一个片段是 `'Hello'`。讲义注释中的 `' Hello'` 是笔误，实际运行输出为 `['Hello', ',', ' world', '!', ' Don', "'t", ' stop', '.']`。这也提醒我们：句首单词和句中单词（`'Hello'` vs `' Hello'`）会被编码成不同的 token。

### Q10 — 参考答案

```python
from main import ProductionTokenizer

LLAMA3_SPECIALS = ["<|begin_of_text|>", "<|start_header_id|>",
                   "<|end_header_id|>", "<|eot_id|>"]

def apply_llama3_template(messages, add_generation_prompt=False):
    text = "<|begin_of_text|>"
    for m in messages:
        text += (f"<|start_header_id|>{m['role']}<|end_header_id|>\n\n"
                 f"{m['content']}<|eot_id|>")
    if add_generation_prompt:           # 让模型接着写 assistant 的回复
        text += "<|start_header_id|>assistant<|end_header_id|>\n\n"
    return text

tok = ProductionTokenizer()
tok.train("You are helpful. Hello there, how are you?", 20)
for s in LLAMA3_SPECIALS:
    tok.add_special_token(s)

msgs = [{"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"}]
s = apply_llama3_template(msgs, add_generation_prompt=True)
ids = tok.encode(s)
assert tok.decode(ids) == s
```

要点：

- 格式严格照抄讲义：头部 `<|start_header_id|>{role}<|end_header_id|>` 后面跟**两个换行**，内容后紧跟 `<|eot_id|>`，整段以 `<|begin_of_text|>` 开头。
- 特殊 token 必须在 `encode` 前注册，否则 `<|eot_id|>` 会被当成普通字符逐字节编码，模型根本认不出来。实际运行中 4 个特殊 token 各自变成一个 ID（如 276–279），往返断言通过。
- `add_generation_prompt=True` 在推理时使用：以 assistant 的头部结尾，让模型从这里开始生成；训练（SFT）时则使用包含 assistant 完整回复的版本。
- 验证方法（讲义建议）：与 Hugging Face `apply_chat_template` 的输出逐字符比对。

### Q11 — 参考回答要点

- **Normalize**：NFKC 等统一字符形式，避免同一个词因为全角/连字等不同写法得到不同 token。
- **Pre-Tokenize**：正则切分词、数字、标点、空白，阻止跨词合并，让 token 更可解释、也让 BPE 训练更快（可以对去重后的片段计数）。
- **BPE Merge**：在每个片段的字节序列上按合并表顺序合并，完成压缩。
- **Special Tokens**：BOS/EOS/PAD、chat 标记等，固定 ID，精确匹配，绕过 BPE。
- **ID 映射**：最终输出整数序列给模型。
- **去掉预分词的后果**：出现 `"e c"`、`" sat on the "` 这类跨词 token，词表被高频短语占据；同一个词在不同上下文中切分不一致；token 失去可解释性（Lesson 01 的 toy tokenizer 正是如此）。
- 加分点：说出速度问题——Python 只适合理解算法，生产用 Rust/C++ 实现，只在 Python 层做包装。

### Q12 — 参考回答要点

- 正则的几个分支：`'(?:[sdmt]|ll|ve|re)` 切英文缩写；` ?\p{L}+` 字母串（可带一个前导空格）；` ?\p{N}+` 数字串；` ?[^\s\p{L}\p{N}]+` 标点/符号串；`\s+(?!\S)` 和 `\s+` 处理空白。
- **前导空格粘在词前**：`"the cat"` → `[" the", " cat"]` 而不是 `["the", " ", "cat"]`。这样句中绝大多数单词都以"空格+词"形式出现，一个 token 就能覆盖，空格不需要单独占 token，序列更短。`\s+(?!\S)` 把多个空格的最后一个留给后面的词，保证 `" cat"` 无论前面有几个空格都是同一个 token。
- **数字特殊处理**：GPT-2 的 ` ?\p{N}+` 让任意长的数字串可以被合并成不规则的块，导致同一个数字在不同上下文中切法不同、位值不对齐。较新的 tokenizer 会限制数字块的长度（如 cl100k_base 的正则把数字按最多 3 位切分），让算术更稳定。
- 加分点：缩写分支对大小写敏感（`'S`、`'T` 不匹配），这是 GPT-2 正则一个已知的小瑕疵，后续 tokenizer 用 `(?i:...)` 修正。
- 常见误区：认为预分词会"丢掉空格"——它只是切分，`"".join(chunks)` 必须等于原文。

### Q13 — 参考回答要点

- **风险**：本节 `SpecialTokenHandler` 会在**任何**输入文本中匹配特殊 token 字符串。实际验证：`tok.encode("user says <|end|> ok")` 中的 `<|end|>` 被编成了特殊 ID。如果用户输入、网页内容、RAG 检索到的文档里包含 `<|im_end|>`、`<|eot_id|>`，就能伪造"消息边界"甚至伪造 system/assistant 轮次——这是一种 prompt injection。
- **正确做法**：
  - 区分"可信的模板文本"与"不可信的用户内容"：只有 chat template 自己插入的标记才编码为特殊 ID；用户内容中的同名字符串按普通文本逐字节编码。
  - tiktoken 的 `encode` 默认在遇到特殊 token 字符串时直接抛错，需要显式通过 `allowed_special` / `disallowed_special` 参数声明如何处理，就是为了防止这类问题。
  - 在进入模型前对用户输入做检测/转义，并在日志中报警。
- 加分点：说明这类问题在 RAG 和 agent 场景更严重，因为不可信文本来源更多。

### Q14 — 参考回答要点

- **停不下来**：
  - 训练时每条样本末尾是否真的加了 EOS / `<|eot_id|>`？如果 pad token 设成了 EOS，而 loss mask 又把所有 pad 位置屏蔽，模型可能从没学过"在这里输出 EOS"。
  - 推理时的停止条件是否包含该模型真正的结束 token（如 Llama 3 用 `<|eot_id|>` 结束一轮，而不只是 `<|end_of_text|>`）？
- **质量下降**：
  - 训练与推理用的 chat template 是否**逐字符一致**（换行数、空格、BOS 是否重复添加）？可以把两侧的 token ID 序列打印出来 diff。
  - 特殊 token 是否被正确识别为单个 ID，而不是被拆成 `<`、`|`、`im`……；新增特殊 token 后 embedding 是否 resize 并参与训练。
  - 是否重复加 BOS（模板里已有 `<|begin_of_text|>`，`encode` 时又默认加了一次）。
- **方法论**：固定一条样本，打印"模板字符串 → token ID → 逐个 decode"三列，对照官方实现（如 HF `apply_chat_template`）。
- 讲义原话可作为结论："Get the template wrong and the model produces garbage."

### Q15 — 参考回答要点

- **好处**：把全角/半角、连字、上标等"看起来相同"的写法统一，减少词表碎片，同一个词得到同一个 token；对来源杂乱的网页语料尤其有用。
- **问题**：
  - **有损**：`decode(encode(x)) != x`，例如 "ﬁle" 解码为 "file"、"ＡＢＣ" 解码为 "ABC"；对需要精确复现原文的场景（代码、数学、法律文本）可能造成语义变化，如 "x²" 变成 "x2"。
  - 训练与推理必须使用**完全相同**的规范化，否则同一段文本两边编码不一致。
  - 对 CJK 文本，全角标点被转换成半角，可能改变文本风格。
- **工程取舍**：GPT-2 式的 byte-level tokenizer 通常不做（或只做很轻的）规范化，依靠字节级覆盖与数据清洗；需要做时，在数据清洗阶段统一处理并保留原文备份，而不是只在 tokenizer 里悄悄做。
- 加分点：本节代码在 `encode` 里做 NFKC，所以对这类输入，演示中的 `Round-trip` 检查会显示 FAIL——这不是 BPE 的 bug，而是规范化的预期行为。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 01 Tokenizers: BPE, WordPiece, SentencePiece](../../01-tokenizers/docs/zh.md)：BPE 训练循环、合并表、byte-level 基础。
- [阶段 05 · 01 文本处理](../../../05-nlp-foundations-to-advanced/01-text-processing/docs/zh.md)：正则表达式、Unicode 与文本清洗。
- [阶段 05 · 19 子词分词](../../../05-nlp-foundations-to-advanced/19-subword-tokenization/docs/zh.md)：子词算法总览。

### 本节被哪些后续内容用到
- [阶段 10 · 03 用于预训练的数据管道](../../03-data-pipelines/docs/zh.md)：用本节的 tokenizer 把清洗后的语料变成 token 序列，并插入 EOS 等文档分隔符。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：词表大小决定 embedding 与输出层形状。
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)：chat template 与特殊 token 是 SFT 数据格式的核心。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：约束解码依赖对 token 边界的理解。
- [阶段 14 · 27 Prompt Injection 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：特殊 token 注入是 prompt injection 的一种形式。
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../../19-capstone-projects/30-bpe-tokenizer-from-scratch/docs/zh.md)：综合项目中的完整 tokenizer 实现。

### 延伸关键词
`NFKC / NFC` · `bytes_to_unicode (Ġ)` · `pre-tokenization regex` · `\p{L} / \p{N}` · `special tokens` · `allowed_special` · `chat template` · `apply_chat_template` · `tiktoken` · `HF tokenizers`
