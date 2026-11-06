# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 06 节 指令微调（SFT） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数；需保持仓库目录结构，因为它会从 `../../04-pre-training-mini-gpt/code/main.py` 导入 `MiniGPT`） ｜ **依赖**：`numpy`（第三方）；`sys`、`os`（标准库）；无需 GPU、无需网络。

---

## 1. 这份代码在考察什么

这份代码想演示把 base 模型变成"会听指令"的助手的完整 SFT 流水线：

1. **指令数据集**：8 条（指令, 回复）对，对应讲义的 Alpaca 风格数据。
2. **Chat template**：用 3 个特殊 token（`INST_START` / `INST_END` / `RESP_START`）把指令和回复拼成一条字节级 token 序列。
3. **Loss mask**：只在回复 token 上计 loss——本节最核心的概念。
4. **Masked cross-entropy**：分母是回复 token 数，而不是序列长度。
5. **SFT 训练循环**：低学习率（2e-5）、多 epoch、每 epoch 打乱样本。
6. **评估**：在指令格式的输入上生成回复；在原始文本上测 loss，检查灾难性遗忘。

> 一句话：**SFT = 预训练的同一个训练循环 + 对话模板 + 只对回复计 loss**。但请特别注意：本文件的"训练"步骤**并没有使用梯度**，打印出的训练与遗忘结果全部没有意义——看清这一点，比看懂其余代码更重要。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sys.path.insert` + `from main import ...` | 导入 | 复用第 04 节的 `MiniGPT` 等类 | 在预训练模型上继续训练 |
| `INSTRUCTION_DATA` | 常量（list of dict） | 8 条指令–回复对 | Alpaca 格式数据 |
| `SPECIAL_TOKENS` | 常量（dict） | 253/254/255 三个角色标记 | chat template 的特殊 token |
| `tokenize_instruction_pair` | 函数 | 字节编码 + 拼接角色标记 | chat template |
| `create_loss_mask` | 函数 | `RESP_START` 之后为 1，其余为 0 | loss masking |
| `masked_cross_entropy_loss` | 函数 | log-softmax → 逐 token loss → 乘 mask → 除以回复 token 数 | masked loss |
| `sft_train` | 函数 | 格式化数据 → 每 epoch 打乱 → 前向 + loss → （伪）更新 | SFT 训练循环 |
| `generate_response` | 函数 | 带 temperature 的自回归采样 | 推理 |
| `evaluate_instruction_following` | 函数 | 用模板包装问题并生成 30 个 token | 指令遵循评估 |
| `measure_forgetting` | 函数 | 原始文本上按 64 字节窗口算平均交叉熵 | 灾难性遗忘指标 |
| `__main__` | 脚本入口 | 建模型 → 测基线 → SFT → 再测 → 生成 → 打印数据格式与 loss 曲线 | — |

数据流：`INSTRUCTION_DATA` → `tokenize_instruction_pair` → `create_loss_mask` → `sft_train`（`model.forward` → `masked_cross_entropy_loss` → 随机扰动 FFN）→ `measure_forgetting` / `evaluate_instruction_following`。

---

## 3. 逐段精讲

### 3.1 从第 04 节导入模型

```python
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "..", "04-pre-training-mini-gpt", "code"
    ),
)
from main import MiniGPT, LayerNorm, FeedForward, MultiHeadAttention, TransformerBlock, Embedding
```

- `os.path.dirname(__file__)` 是本文件所在目录；`..`、`..` 回到 `10-llms-from-scratch/`，再进入第 04 节的 `code/`。
- `sys.path.insert(0, ...)` 把这个目录放到模块搜索路径的**最前面**，于是 `from main import ...` 找到的是第 04 节的 `main.py`，而不是本文件。
- 实际只用到了 `MiniGPT`，其余 5 个类导入后未使用。
- ⚠️ **同名模块陷阱**：本文件和被导入的文件都叫 `main.py`。直接 `python main.py` 运行没问题（本文件作为 `__main__` 运行，不占用 `main` 这个名字）；但如果在别处 `import main` 导入本文件，Python 会把本文件注册为 `main`，执行到 `from main import MiniGPT` 时取到的是"自己"（尚未初始化完），报 `ImportError: cannot import name 'MiniGPT' from partially initialized module 'main'`。我们写验证脚本时实际遇到了这个错误，只能改用 `importlib.util.spec_from_file_location` 以别名加载。生产代码应把共享模型放进一个正式的包里（如 `minigpt/model.py`）。

### 3.2 数据与 chat template

```python
SPECIAL_TOKENS = {
    "INST_START": 253,
    "INST_END": 254,
    "RESP_START": 255,
}

def tokenize_instruction_pair(instruction, response, vocab_size=256):
    inst_tokens = list(instruction.encode("utf-8"))
    resp_tokens = list(response.encode("utf-8"))

    inst_tokens = [min(t, vocab_size - 4) for t in inst_tokens]
    resp_tokens = [min(t, vocab_size - 4) for t in resp_tokens]

    tokens = (
        [SPECIAL_TOKENS["INST_START"]]
        + inst_tokens
        + [SPECIAL_TOKENS["INST_END"]]
        + [SPECIAL_TOKENS["RESP_START"]]
        + resp_tokens
    )
    return tokens
```

- **字节级 tokenizer**：`str.encode("utf-8")` 得到 `bytes`，`list()` 后每个元素是 0–255 的整数，直接当 token ID 用（与第 04 节一致，词表大小 256）。
- **特殊 token 复用 253–255**：这三个字节值在合法 UTF-8 中永远不会出现（0xF5–0xFF 都是非法字节），所以不会与真实文本冲突；`min(t, 252)` 对合法 UTF-8 实际上什么也不做，只是一道"保险"。
- 生成的序列形如：

  ```text
  [253] W h a t   i s ... ? [254] [255] T h e   c a p i t a l ... .
  ```

  对应讲义 ChatML 里的 `<|im_start|>user ... <|im_end|> <|im_start|>assistant ...`。
- ⚠️ **没有结束符**：回复后面没有 EOS / `<|im_end|>`，模型永远学不会"什么时候停"（讲义的掩码示意图里有 `[EOS]`，代码没有实现）。
- ⚠️ 没有 system prompt（讲义练习 1）和多轮对话（练习 4）。

### 3.3 loss mask

```python
def create_loss_mask(tokens):
    mask = np.zeros(len(tokens), dtype=np.float32)
    in_response = False

    for i, token in enumerate(tokens):
        if token == SPECIAL_TOKENS["RESP_START"]:
            in_response = True
            continue
        if in_response:
            mask[i] = 1.0
    return mask
```

- 一个简单的状态机：遇到 `RESP_START` 后打开开关，`continue` 让分隔符本身保持 0，之后每个 token 都置 1。
- 例 1（"What is the capital of France?"，30 字节；"The capital of France is Paris."，31 字节）：总长 `1 + 30 + 1 + 1 + 31 = 64`，mask 中 31 个 1、33 个 0，与运行输出"64 tokens, 31 response tokens (48%)"一致。
- 这个 mask 是**按 token 本身**标注的（"这个 token 属于回复吗"）。训练时还要再错开一位，见 3.5。

### 3.4 masked cross-entropy

```python
def masked_cross_entropy_loss(logits, targets, loss_mask):
    batch, seq_len, vocab_size = logits.shape
    logits_flat = logits.reshape(-1, vocab_size)
    targets_flat = targets.reshape(-1)
    mask_flat = loss_mask.reshape(-1)

    max_logits = logits_flat.max(axis=-1, keepdims=True)
    log_softmax = logits_flat - max_logits - np.log(
        np.exp(logits_flat - max_logits).sum(axis=-1, keepdims=True)
    )

    per_token_loss = -log_softmax[np.arange(len(targets_flat)), targets_flat]

    masked_loss = per_token_loss * mask_flat
    num_response_tokens = mask_flat.sum()
    if num_response_tokens == 0:
        return 0.0
    loss = masked_loss.sum() / num_response_tokens
    return loss
```

| 步骤 | 形状（例 1，B=1, S=63, V=256） |
|------|------|
| `logits` | `(1, 63, 256)` |
| `logits_flat` | `(63, 256)` |
| `log_softmax` | `(63, 256)`，log-sum-exp 技巧保证数值稳定 |
| `per_token_loss` | `(63,)`，花式索引取出每个位置"正确 token"的负对数概率 |
| `masked_loss` | `(63,)`，指令位置被乘成 0 |
| `loss` | 标量 = 回复位置 loss 之和 / 31 |

- **分母是回复 token 数**：讲义"If you divide by the total sequence length, longer instructions dilute the gradient signal."
- `num_response_tokens == 0`（例如截断把回复全部截掉）时返回 0.0，避免除零。但这个 0 仍会被计入 epoch 平均，拉低平均 loss——更好的做法是跳过这条样本。
- 等价的生产写法：把非回复位置的 label 设为 `-100`，用 PyTorch `F.cross_entropy(..., ignore_index=-100)`。

### 3.5 SFT 训练循环（⚠️ 没有真正的梯度更新）

```python
            input_ids = np.array(tokens[:-1]).reshape(1, -1)
            target_ids = np.array(tokens[1:]).reshape(1, -1)
            loss_mask = np.array(mask[1:]).reshape(1, -1)
```

- 经典的"错开一位"：位置 i 的输入是 `tokens[i]`，标签是 `tokens[i+1]`，权重是 `mask[i+1]`。
- 因此：在 `INST_END` 位置预测 `RESP_START`（mask 0）不计；在 `RESP_START` 位置预测回复第一个字节（mask 1）计入。我们实测例 1 中第一个计入 loss 的位置下标为 32，输入 255、目标 84（`'T'`）。

```python
            probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
            probs = probs / probs.sum(axis=-1, keepdims=True)
            dlogits = probs.copy()
            dlogits[np.arange(batch_size)[:, None], np.arange(s_len), target_ids] -= 1.0

            mask_expanded = loss_mask[:, :, np.newaxis]
            num_resp = loss_mask.sum()
            if num_resp > 0:
                dlogits = dlogits * mask_expanded / num_resp
```

- 这部分是**正确的** masked loss 对 logits 的梯度：`(softmax − one_hot) × mask / 回复 token 数`。
- `loss_mask[:, :, np.newaxis]` 把 `(1, 63)` 变成 `(1, 63, 1)`，以便广播乘到 `(1, 63, 256)` 上，让指令位置整行梯度为 0。

```python
            for block in model.blocks:
                block.ffn.W1 -= lr * np.random.randn(*block.ffn.W1.shape) * 0.01
                block.ffn.W2 -= lr * np.random.randn(*block.ffn.W2.shape) * 0.01
                block.ffn.b1 -= lr * np.random.randn(*block.ffn.b1.shape) * 0.01
                block.ffn.b2 -= lr * np.random.randn(*block.ffn.b2.shape) * 0.01
```

- ⚠️ **这是本文件最严重的问题**：`dlogits` 算完后再也没有被使用。"更新"只是给 FFN 权重加上 `2e-5 × 0.01 × N(0,1)` 的随机噪声（量级约 2e-7），方向与 loss 无关；注意力、LayerNorm、embedding 完全不变。
- 我们实测：3 个 epoch 后 `blocks[0].ffn.W1` 的最大变化只有约 4.6e-6。
- 后果：
  - 3 个 epoch 的平均 loss 完全相同（5.6570），loss "曲线"只是 8 条样本各自 loss 的随机波动；
  - 原始文本 loss 前后都是 5.6048，"Minimal forgetting"是因为什么都没学，而不是因为学得好；
  - 讲义"Only response tokens push the weights"对这份代码不成立。
- 讲义 Build It 中的代码与此一字不差，属于讲义与代码共同的问题。修复见第 7 节练习 1 和测验 Q9。
- `np.random.permutation(len(formatted_data))`：每个 epoch 随机打乱样本顺序。
- 截断：长于 `seq_len` 的序列直接截掉尾部；本例最长 111 token，`seq_len=128` 时不触发。

### 3.6 生成与指令遵循评估

```python
        next_logits = next_logits / max(temperature, 1e-8)
        probs = np.exp(next_logits - next_logits.max())
        probs = probs / probs.sum()
        probs = np.clip(probs, 1e-10, 1.0)
        probs = probs / probs.sum()
```

- 与第 04 节相比做了两处防御：`max(temperature, 1e-8)` 避免除以 0；`np.clip` 后再归一化，避免出现精确为 0 的概率。注意 temperature 极小时 logits 会变得极大，但先减最大值再 `exp` 不会溢出，结果近似贪心。
- `tokens.append(int(next_token))`：把 NumPy 整数转成 Python `int`。
- 每步都对整个上下文重新前向（没有 KV cache），上下文窗口为 `max_seq_len=128`。

```python
        response_bytes = bytes([t for t in response_tokens if t < 128])
        response_text = response_bytes.decode("utf-8", errors="replace")
        print(f"  A: {response_text[:80]}")
```

- 只保留 ASCII 字节（`< 128`），把特殊 token 和非 ASCII 字节都过滤掉，再截取前 80 个字符。
- ⚠️ 固定生成 30 个 token，没有在任何 token 处停止——既因为模板里没有 EOS，也因为评估代码没有停止条件。过滤和截断会掩盖"停不下来"、"输出了特殊 token"等问题。

### 3.7 灾难性遗忘的测量

```python
def measure_forgetting(model, test_text, seq_len=64):
    tokens = np.array(list(test_text.encode("utf-8")[:512]))
    ...
    for start in range(0, len(tokens) - seq_len - 1, seq_len):
        input_ids = tokens[start : start + seq_len].reshape(1, -1)
        target_ids = tokens[start + 1 : start + seq_len + 1].reshape(1, -1)
        ...
        loss = -log_softmax[np.arange(len(targets_flat)), targets_flat].mean()
```

- 把原始文本切成**不重叠**的 64 字节窗口，算每个窗口的平均交叉熵，再对窗口取平均。`test_text` 共 287 字节，`range(0, 222, 64)` 只产生 4 个窗口，最后 30 字节没有用到。
- 思路是对的：SFT 后原始文本的 loss 明显上升，就说明通用语言能力受损（讲义：上升超过 10–15% 说明 SFT 太激进）。
- ⚠️ 但这里的 "base model" 是**随机初始化**的 `MiniGPT`（loss 5.6048 ≈ `ln 256 = 5.545`，即随机猜测水平），根本没有可被遗忘的能力。正确做法是先加载第 04 节预训练好的权重。
- ⚠️ `__main__` 用 `abs(sft_loss - base_loss) / base_loss < 0.15` 判断，loss 大幅**下降**也会被报告为 "Significant forgetting"。

### 3.8 `__main__`

- `MiniGPT(vocab_size=256, embed_dim=128, num_heads=4, num_layers=4, max_seq_len=128, ff_dim=512)`：比第 04 节演示多了一倍的位置 embedding（128 行），参数量 840,448（= 832,256 + 64 × 128）。
- 依次打印：基线 loss → SFT 训练 → SFT 后 loss 与变化率 → 3 个问题的生成结果 → 前 3 条样本的 token 统计 → 把 24 个 step 的 loss 按 4 个一组求平均。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字节级词表 + 复用 253–255 作特殊 token | 不需要新的 tokenizer，复用第 04 节模型 | 生产中把特殊 token 追加到词表末尾、分配独立 ID，并扩充 embedding |
| 没有 EOS、没有 system、单轮 | 代码最短 | 模型学不会停止；生产模板必须含结束符并计入 loss |
| 0/1 mask 相乘 | 直观展示"只对回复计 loss" | 生产中用 `labels=-100` + `ignore_index` |
| 分母 = 回复 token 数 | 不受指令长度影响 | batch 训练时要决定 per-token 还是 per-sample 平均，并保证梯度累积时一致 |
| batch size 1、无 padding | 免去 padding / attention mask | 生产中用 padding 或 sequence packing 提高吞吐 |
| 随机噪声"更新" | 推测是占位实现 | **完全没有学习**；应使用 autograd + AdamW 对全部参数（或 LoRA 参数）更新 |
| lr = 2e-5（照搬 Llama 2） | 与讲义超参数表一致 | 2e-5 是 AdamW 的学习率，朴素 SGD 下几乎不动 |
| 用随机初始化模型测"遗忘" | 不需要先跑预训练 | 结论无意义；应加载预训练权重并用更大的通用评测集 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `sys.path.insert` | `sys.path.insert(0, os.path.join(...))` | 临时把目录加到模块搜索路径最前面 |
| `os.path` 拼路径 | `os.path.join(os.path.dirname(__file__), "..", ...)` | 跨平台拼接路径；`__file__` 是当前文件路径 |
| `from 模块 import 多个名字` | `from main import MiniGPT, LayerNorm, ...` | 一次导入多个类 |
| 字典列表 | `INSTRUCTION_DATA = [{"instruction": ..., "response": ...}, ...]` | 最常见的"记录集合"写法，相当于 JSON 数组 |
| 带尾逗号的字面量 | `"response": "...",` | 多行字面量末尾的逗号合法，方便增删行 |
| `str.encode` / `bytes.decode` | `instruction.encode("utf-8")`、`.decode("utf-8", errors="replace")` | 文本 ↔ 字节；`errors="replace"` 用 `�` 代替非法字节 |
| 列表推导式 + 条件 | `[min(t, vocab_size - 4) for t in inst_tokens]`、`[t for t in response_tokens if t < 128]` | 逐元素变换 / 过滤 |
| 列表拼接 | `[A] + inst_tokens + [B] + [C] + resp_tokens` | `+` 连接列表，生成新列表 |
| 用括号续行 | `tokens = ( ... + ... )` | 括号内可以自由换行 |
| `enumerate` | `for i, token in enumerate(tokens)` | 同时拿到下标和元素 |
| `continue` | `if token == ...: in_response = True; continue` | 跳过本次循环剩余部分 |
| 布尔状态变量 | `in_response = False` | 简单状态机 |
| `dtype` | `np.zeros(len(tokens), dtype=np.float32)` | 指定数组元素类型 |
| 元组列表与解包 | `formatted_data.append((tokens, mask))`、`tokens, mask = formatted_data[idx]` | 把相关数据打包，用时再拆开 |
| 生成器表达式求和 | `sum(len(t) for t, _ in formatted_data)` | `_` 表示忽略的元素 |
| `np.random.permutation` | `indices = np.random.permutation(len(formatted_data))` | 返回 0..n−1 的随机排列 |
| `np.newaxis` | `loss_mask[:, :, np.newaxis]` | 增加一个长度为 1 的维度，便于广播 |
| 星号解包参数 | `np.random.randn(*block.ffn.W1.shape)` | 把形状元组 `(128, 512)` 展开成两个位置参数 |
| 花式索引赋值 | `dlogits[np.arange(B)[:, None], np.arange(S), target_ids] -= 1.0` | 三组索引广播成 `(B, S)`，一次修改所有正确类别位置 |
| `np.clip` | `np.clip(probs, 1e-10, 1.0)` | 把数值限制在区间内 |
| `max()` 防除零 | `max(temperature, 1e-8)`、`max(num_batches, 1)` | 简单的下界保护 |
| `int()` 转换 | `tokens.append(int(next_token))` | NumPy 整数转为 Python `int` |
| 切片步长写法 | `range(0, len(tokens) - seq_len - 1, seq_len)` | 按窗口大小跳跃 |
| f-string 格式符 | `{lr}`、`{avg_loss:.4f}`、`{change:+.1f}%`、`{ratio:.0%}`、`{i:3d}`、`{n:,}` | 小数位、带正负号、百分比、宽度、千分位 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行（Python 3 + NumPy，`np.random.seed(42)`，耗时约 1 秒）：

```text
Model: 840,448 parameters                ← 832,256 + 多出的 64 行位置 embedding（64×128）
PRE-SFT: Measuring base model loss on raw text
  Base model loss: 5.6048                ← 随机初始化，≈ ln 256 = 5.545，没有任何"能力"

SFT Training: 8 examples, 3 epochs, lr=2e-05
Total tokens: 724                         ← 8 条样本的 token 总数（含特殊 token）

Epoch 1/3 | Avg Loss: 5.6570
Epoch 2/3 | Avg Loss: 5.6570
Epoch 3/3 | Avg Loss: 5.6570              ← 三个 epoch 完全相同：参数基本没变

POST-SFT: Measuring fine-tuned model loss on raw text
  SFT model loss: 5.6048
  Change: -0.0%
  Minimal forgetting (< 15% change)       ← "没遗忘"是因为什么都没学

  Q: What is the capital of France?
  A: 0	f_}f G&]"<2n                      ← 随机 ASCII 字节（含制表符、换行）
  Q: Name a programming language.
  A: b$z+-
9xm>}
  Q: Define gravity.
  A: dRL*M01I.E
TYz

  Example 1: 64 tokens, 31 response tokens (48% of sequence)
  Example 2: 106 tokens, 71 response tokens (67% of sequence)
  Example 3: 111 tokens, 78 response tokens (70% of sequence)

  Steps   0-  3: avg loss = 5.6447
  Steps   4-  7: avg loss = 5.6694
  ...
  Steps  20- 23: avg loss = 5.6437        ← 只是不同样本 loss 的随机波动，没有下降趋势
```

逐项解读：

- **loss ≈ 5.65**：比 `ln 256` 略高，因为模型是随机的，回复中的字母不比其他字节更可能被预测到。
- **三个 epoch 的平均 loss 精确相同**：每个 epoch 遍历同样 8 条样本，而模型参数只被加了 ~1e-7 量级的噪声，loss 在四位小数上不变。打乱顺序不影响平均值。
- **遗忘 "-0.0%"**：同上，参数没变，loss 也不变。
- **生成的 "回答"**：随机模型 + temperature 0.6 采样；过滤掉了 ≥ 128 的字节，所以看到的全是 ASCII 乱码。讲义说"在 8 条数据的小模型上回答不会有意义"，但真实原因比这更彻底：模型根本没有被训练。
- **回复 token 占比 48%–70%**：说明短问题短回答时，指令部分占了一半序列；如果不做 mask，模型会有一半的梯度花在"学习提问"上。
- **Total tokens: 724**：8 条样本平均约 90 个 token。

如果把更新步骤修好（见第 7 节练习 1），我们实测"只训练输出头 + 学习率 0.1"时，30 个 epoch 的平均 loss 可以从 4.52 降到 2.85；而学习率仍为 2e-5 时只从 5.53 降到 5.51（朴素 SGD 下 2e-5 太小）。

---

## 7. 动手改一改

1. **修好训练（必做）**：仿照第 04 节，在 `MiniGPT.forward` 之外再算出 `ln_f` 之后的隐藏状态 `x_normed`，用 `grad_token_embed = dlogits[0].T @ x_normed[0]` 更新 `token_embed`；把学习率调到 0.05–0.1，观察 loss 下降。进阶：用 PyTorch 重写，`loss.backward()` + `AdamW(lr=2e-5)`，体会"2e-5 是 Adam 的学习率"。
2. **加入 EOS 并在生成时停止**：增加 `EOS=252`，模板末尾追加 EOS 并计入 loss；`generate_response` 遇到 EOS 就 `break`。打印 token–mask 对齐表自检（测验 Q10）。
3. **讲义练习 1 + 4：system prompt 与多轮对话**：模板改为 `[SYS] ... [USER] ... [ASST] ... [EOS] [USER] ... [ASST] ... [EOS]`，写 `create_multiturn_mask`，确保所有助手轮（含 EOS）为 1、其余为 0。
4. **用真正的 base 模型测遗忘**：先运行第 04 节的预训练并用 `np.save` 保存所有权重，再在本节加载；用更长的通用文本（至少几千字节）测 SFT 前后 loss，并把判断条件改为"只有上升才算遗忘"。
5. **讲义练习 2：数据混合**：每个 epoch 中以 5% 的概率插入一段原始文本（mask 全为 1），比较纯 SFT 与混合训练的遗忘指标。
6. **讲义练习 5：学习率对比**：在修好的训练上分别用 1e-1、1e-2、1e-3（SGD）或 1e-4、2e-5、1e-6（Adam）训练，画出 loss 曲线，观察"下降快但过拟合"与"几乎不动"两种极端。

---

## 8. 常见坑

- **算了梯度却没用**：本文件就是例子。任何训练代码都应检查"训练前后参数是否真的变了"以及"loss 是否有下降趋势"。
- **mask 与标签差一位**：mask 必须和 `targets = tokens[1:]` 对齐，即用 `mask[1:]`；误用 `mask[:-1]`（按输入位置对齐）会漏掉"在 `RESP_START` 位置预测回复第一个 token"——恰恰是决定"开口说什么"的那一步。最稳妥的做法是直接构造与 `targets` 等长的 `labels`，非回复位置填 -100。
- **忘了把结束符计入 loss**：模型学不会停止，推理时一直生成。
- **训练与推理模板不一致**：少一个换行、多一个空格都可能明显降低效果；推理时应使用 tokenizer 自带的 chat template。
- **截断把回复截没了**：长指令 + 短 `seq_len` 时，回复可能被完全截掉，mask 全 0；应优先截断指令或丢弃样本。
- **用 SGD 照搬 Adam 的学习率**：2e-5 对 Adam 合理，对 SGD 几乎为零。
- **用随机模型做"遗忘"基线**：没有能力可遗忘，任何结论都无意义。
- **`abs()` 判断遗忘**：loss 下降不是遗忘，判断应只看上升。
- **两个 `main.py` 互相导入**：作为模块导入本文件会触发循环导入错误；共享代码应放进独立的包。
- **讲义事实需核对**：讲义称"Llama 2 Chat 在 SFT 数据中混入了 2–5% 预训练数据"，这一说法在 Llama 2 论文中不易找到对应描述；更广为人知的"混入预训练数据"做法是 InstructGPT 在 PPO 阶段的 PPO-ptx。把它当作通用缓解手段理解即可。
