# 测验 · 文本的 CNNs 和 RNNs（CNNs and RNNs for Text）

> **阶段 05 · NLP 基础到进阶 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要词序 | TF-IDF / Word2Vec 平均向量分不清 `dog bites man` 和 `man bites dog`；CNN、RNN 把顺序信息带回来 |
| 2 | TextCNN（Kim, 2014） | 在词向量序列上做 1D 卷积，宽度为 k 的 filter 就是一个可学习的 k-gram 检测器；多种宽度并联 |
| 3 | 全局最大池化 | 每个 filter 只保留最强激活 → 定长、与位置无关的特征（"not good" 出现在开头或中间触发同一特征） |
| 4 | RNN 递推 | `h_t = f(W·x_t + U·h_{t-1} + b)`，参数跨时间共享；分类时对 `h_1…h_T` 做 max / mean / last 池化 |
| 5 | 梯度消失 / 爆炸 | 梯度沿时间连乘循环权重：`0.9¹⁰⁰ ≈ 2.7e-5`（消失），`1.1¹⁰⁰ ≈ 1.4e4`（爆炸） |
| 6 | LSTM 与 GRU | LSTM 用输入/遗忘/输出三个门 + 以加法为主更新的 cell state 作为"梯度高速公路"；GRU 两个门、参数更少、效果相近 |
| 7 | 双向 RNN | 前向 + 后向隐状态拼接，每个 token 同时看到左右上下文；序列标注必备 |
| 8 | RNN 的三个遗留问题 | 时间维无法并行；encoder-decoder 的定长上下文向量瓶颈；200+ 步的远距离依赖仍然困难 → attention |
| 9 | 2026 年仍适用的场景 | 端侧/边缘推理、流式逐 token 处理、快速小基线、小数据序列标注（BiLSTM-CRF） |

### 核心技能（能动手做到）

- [ ] 不用框架，从零实现"1D 卷积 + ReLU + 全局最大池化"，并手算出一个窗口的激活值
- [ ] 能写出 TextCNN 每一步的张量形状：`[B, L] → [B, L, E] → [B, E, L] → [B, F, L-k+1] → [B, F] → [B, F·|widths|]`
- [ ] 能用 NumPy 把纯 Python 的三重循环卷积向量化，并与原实现输出逐项对齐
- [ ] 能用 `w^T` 估算普通 RNN 在 T 步之后的梯度衰减/放大，并说明 LSTM、梯度裁剪各自解决哪一个
- [ ] 能写出 LSTM / GRU 的门控公式，并算出 PyTorch `nn.LSTM`、`nn.GRU` 的参数量
- [ ] 能在 TextCNN、BiLSTM、BiLSTM-CRF、Transformer 之间，根据数据量、延迟、部署目标做出选型并说明理由

---

## 二、基础自测（选择题）

**Q1.** 一个 TextCNN 使用宽度 (3, 4, 5) 的卷积，每种宽度 100 个 filter，之后做全局最大池化并拼接。输入句子长度从 20 变成 200，拼接后的特征维度：

- A. 从 300 增大到 3000
- B. 始终是 300
- C. 始终是 100
- D. 取决于 embedding 维度

**Q2.** PyTorch 实现 TextCNN 时，embedding 输出 `[batch, seq_len, embed_dim]` 后要先 `.transpose(1, 2)` 再送入 `nn.Conv1d`，原因是：

- A. 为了把 batch 维放到最后
- B. `nn.Conv1d` 把中间那一维当作通道（channels），卷积沿最后一维滑动；embedding 维应作为通道
- C. 为了让卷积沿 embedding 维滑动
- D. 为了节省显存

**Q3.** 关于 TextCNN 的全局最大池化，下列说法**错误**的是：

- A. 输出长度与输入句长无关
- B. 同一个 n-gram 出现在句首或句中会触发同一个特征
- C. 它保留了"该 n-gram 出现了几次、出现在哪里"的信息
- D. 它让每个 filter 只保留最强的那一次匹配

**Q4.** 普通 RNN 中，若把梯度回传简化为"每一步乘以循环权重 w"，下列说法正确的是：

- A. w = 0.9 时，100 步后梯度约为原来的 2.7e-5，前面时间步几乎学不到东西
- B. w = 1.1 时，100 步后梯度约为原来的 0.1
- C. 只要用 ReLU 激活函数就不会出现梯度消失
- D. 梯度消失只会在序列长度超过 1000 时出现

**Q5.** LSTM 能缓解梯度消失，最核心的结构原因是：

- A. 它的参数比普通 RNN 少
- B. cell state 主要通过加法更新（遗忘门做逐元素缩放），梯度可以沿这条"高速公路"较少衰减地回传
- C. 它用 sigmoid 替代了 tanh
- D. 它在每一步都对隐状态做归一化

**Q6.** 下列哪个任务**不适合**直接使用双向 LSTM？

- A. 命名实体识别
- B. 词性标注
- C. 逐 token 实时生成下一个词的语言模型
- D. 离线情感分类

**Q7.** 讲义指出，即使有了 LSTM，仍有三个问题促成了 attention 的出现。下列哪一项**不在其中**？

- A. 时间维度上必须串行计算，无法并行
- B. encoder-decoder 中 decoder 只能看到一个定长的编码向量
- C. 无法处理变长输入
- D. 超过约 200 步的远距离依赖仍然难以精确传递

---

## 三、动手 / 代码题

**Q8.** 本节 `main.py` 中的卷积函数如下：

```python
def conv1d_over_embeddings(embeddings, filter_matrix, bias=0.0):
    filter_width = len(filter_matrix)
    embed_dim = len(embeddings[0])
    out = []
    for i in range(len(embeddings) - filter_width + 1):
        total = bias
        for k in range(filter_width):
            for d in range(embed_dim):
                total += embeddings[i + k][d] * filter_matrix[k][d]
        out.append(max(total, 0.0))
    return out
```

已知：

```python
embeddings = [
    [1.0, 0.2, 0.5],
    [0.8, 0.9, 0.1],
    [0.3, 0.4, 0.7],
    [0.6, 0.5, 0.5],
    [0.1, 0.8, 0.2],
]
filter_w2 = [[0.5, 0.0, 0.5], [0.2, 0.3, 0.1]]
act_w2 = conv1d_over_embeddings(embeddings, filter_w2, bias=-0.5)
```

(a) `act_w2` 有几个元素？宽度为 3 的 filter 呢？给出一般公式。
(b) 手算 `act_w2[0]`。
(c) 如果传入一个宽度为 6 的 filter，`conv1d_over_embeddings` 和 `max_pool` 分别返回什么？这在真实的 PyTorch TextCNN 中对应什么问题？

**Q9.** 用 NumPy 把 `conv1d_over_embeddings` 向量化（不允许 Python 层面的 `for` 循环遍历窗口），要求对本节数据输出与原函数一致。再说明：如果要把 `filter_w2` 装进 PyTorch 的 `nn.Conv1d(3, 1, kernel_size=2)`，它的 `weight` 形状是什么，需要怎样变换？

**Q10.** 本节的梯度消失模拟：

```python
def vanishing_gradient_sim(seq_len, recurrent_weight=0.9):
    return math.pow(recurrent_weight, seq_len)
```

(a) w = 0.9 时，序列长度至少多少，衰减就会小于 `1e-3`？
(b) 把 w 改为 1.1，长度 100 时结果大约是多少？这种情况叫什么，工程上用什么手段处理？
(c) 这个模拟把真实情况简化了什么？

---

## 四、面试高频题

**Q11.**（基础必考）为什么普通 RNN 会梯度消失 / 爆炸？LSTM 是怎么缓解的？梯度爆炸又怎么处理？

**Q12.**（原理深挖）写出 LSTM 和 GRU 的门控公式。一个 `nn.LSTM(input_size=300, hidden_size=256)` 有多少参数？GRU 呢？

**Q13.**（工程实践）一个 batch 里句子长度不一，用 LSTM / TextCNN 做分类时要注意什么？讲义里的 `out.max(dim=1)` 有什么隐患？

**Q14.**（场景设计）要在手机输入法里做离线意图分类（10 类，约 2 万条标注，延迟 < 10ms，模型 < 5MB）。你会选什么架构，怎么训练和监控？

**Q15.**（追问型）讲义说"流式场景 RNN 仍然胜过 Transformer"。可是 decoder-only Transformer 也能用 KV cache 逐 token 处理，这个说法还成立吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

每个 filter 经过全局最大池化后只输出 1 个数，3 种宽度 × 100 个 filter = 300 维，与句长无关。这正是 TextCNN 能直接接全连接分类头的原因。A 混淆了全局池化与普通池化；C 漏算了宽度种类；embedding 维度（D）只影响卷积的输入通道数，不影响输出维度。

### Q2 — 答案：B

`nn.Conv1d` 的输入约定是 `[batch, channels, length]`，卷积核沿最后一维（length）滑动、在 channels 维上全连接。我们希望 filter 沿时间（词序）滑动、同时看到每个词的完整 embedding，所以要把 `embed_dim` 放到通道位置：`[B, L, E] → [B, E, L]`。C 正好说反；转置本身不省显存（D）。

### Q3 — 答案：C

最大池化只保留"最强的一次匹配"，**丢掉了位置和次数信息**：一个 n-gram 出现 1 次还是 5 次、出现在第几个词，池化后都一样。这既是优点（位置不变性，讲义的 "not good" 例子），也是局限——超过 filter 宽度的顺序关系 TextCNN 看不到。A、B、D 都是正确描述。

### Q4 — 答案：A

`0.9¹⁰⁰ ≈ 2.66e-5`（本节代码实际输出 `2.66e-05`），损失对前面时间步的梯度几乎为 0。B 错：`1.1¹⁰⁰ ≈ 1.38e4`，是梯度**爆炸**。C 错：ReLU 不能保证循环权重的连乘不衰减/不爆炸，普通 RNN 用 ReLU 反而更容易爆炸。D 错：w = 0.9 时 50 步就衰减到 `5.15e-3`。

### Q5 — 答案：B

LSTM 的 cell state 更新是 `c_t = f_t ⊙ c_{t-1} + i_t ⊙ g_t`，`∂c_t/∂c_{t-1}` 主要就是遗忘门 `f_t`（逐元素、可学习、可以接近 1），而不是"循环矩阵乘以激活导数"的反复连乘，所以梯度能沿 cell state 稳定地回传。A 错，LSTM 参数是同尺寸普通 RNN 的约 4 倍；C、D 都不是 LSTM 的机制。

### Q6 — 答案：C

双向 LSTM 的后向分支需要**未来的 token**，生成时下一个词还不存在，所以自回归语言模型只能用单向（因果）结构。NER、POS、离线分类都能拿到整句，双向是标配（讲义："Essential for tagging tasks"）。

### Q7 — 答案：C

RNN 天然支持变长输入（逐 token 处理任意长度），这恰恰是它的优点。讲义列出的三个问题是：串行瓶颈（A）、定长上下文向量（B，第 09 节详细讲）、远距离依赖精度天花板（D）。attention 同时解决了这三个问题。

### Q8 — 参考答案

(a) 输出长度 = `seq_len - filter_width + 1`（无 padding、步长 1，即 "valid" 卷积）。`act_w2` 有 5-2+1 = **4** 个元素，宽度 3 的有 **3** 个。实际输出：`[0.69, 0.2, 0.32, 0.33]` 和 `[0.94, 0.88, 0.62]`。

(b) 窗口是第 0、1 个 token：

```text
token0 · filter[0] = 1.0×0.5 + 0.2×0.0 + 0.5×0.5 = 0.75
token1 · filter[1] = 0.8×0.2 + 0.9×0.3 + 0.1×0.1 = 0.44
total = -0.5 + 0.75 + 0.44 = 0.69 → ReLU → 0.69
```

(c) `range(5 - 6 + 1) = range(0)`，循环一次都不执行，返回 `[]`；`max_pool([])` 走 `if values else 0.0` 分支返回 `0.0`，这与 ReLU 的下界 0 一致，所以是一个"安全的默认值"。在 PyTorch 中，当句长（含 padding）小于最大卷积宽度时，`nn.Conv1d` 会直接报错（输出长度 ≤ 0）。工程做法：把每个 batch 至少 pad 到 `max(filter_widths)`。

### Q9 — 参考答案

```python
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

def conv1d_np(embeddings, filter_matrix, bias=0.0):
    E = np.asarray(embeddings, dtype=float)       # (seq_len, embed_dim)
    F = np.asarray(filter_matrix, dtype=float)    # (k, embed_dim)
    k = F.shape[0]
    if E.shape[0] < k:
        return np.zeros(0)
    windows = sliding_window_view(E, (k, E.shape[1]))[:, 0]   # (seq_len-k+1, k, embed_dim)
    raw = np.einsum("nkd,kd->n", windows, F) + bias
    return np.maximum(raw, 0.0)
```

本节数据上（已运行验证）：`np.round(conv1d_np(embeddings, filter_w2, -0.5), 2)` → `[0.69 0.2 0.32 0.33]`，宽度 3 → `[0.94 0.88 0.62]`，与原函数一致。

说明：
- `sliding_window_view` 生成所有长度为 k 的窗口视图（不复制数据），`einsum("nkd,kd->n")` 对每个窗口做"逐元素相乘再求和"，这就是卷积（深度学习里的"卷积"其实是互相关，不翻转核）。
- PyTorch 的 `nn.Conv1d(in_channels=3, out_channels=1, kernel_size=2)` 的 `weight` 形状是 `(out_channels, in_channels, kernel_size) = (1, 3, 2)`；本节的 `filter_matrix` 是 `(kernel_size, embed_dim) = (2, 3)`，所以要转置后再加一个输出通道维：`weight = torch.tensor(filter_w2).T.unsqueeze(0)`，`bias` 设为 `-0.5`，再接 `F.relu`。

### Q10 — 参考答案

(a) 解 `0.9ᵀ < 1e-3` ⇒ `T > ln(1e-3) / ln(0.9) ≈ 65.6`，所以 **T = 66**（`0.9⁶⁶ ≈ 9.55e-4`，`0.9⁶⁵ ≈ 1.06e-3`）。

(b) `1.1¹⁰⁰ ≈ 1.38e4`，即**梯度爆炸**：参数更新一步跳得极远，loss 出现 NaN。标准处理是**梯度裁剪**（按全局范数裁剪，如 PyTorch 的 `torch.nn.utils.clip_grad_norm_`），再配合较小学习率、合理的权重初始化（如正交初始化）。注意：门控结构主要缓解的是**消失**，爆炸通常仍靠裁剪。

(c) 真实的回传是一串雅可比矩阵连乘：`∂h_T/∂h_1 = Π diag(f'(·)) · Uᵀ`。它涉及矩阵（看最大奇异值/谱半径而非一个标量）、激活函数导数（tanh 的导数 ≤ 1，会进一步加速衰减）以及每一步不同的输入。标量 `wᵀ` 只是抓住了"连乘"这个本质的直觉模型。

### Q11 — 参考回答要点

- **原因**：BPTT 中，`∂L/∂h_1` 需要乘以 `T-1` 个雅可比 `diag(f'(z_t))·Uᵀ`。若这些矩阵的谱半径 < 1，乘积指数衰减（消失）；> 1 则指数增长（爆炸）。讲义直觉：`0.9¹⁰⁰ ≈ 2.7e-5`。
- **后果**：消失 ⇒ 模型学不到远距离依赖（讲义例子：判断 A 是否出现在 100 词序列开头）；爆炸 ⇒ 训练发散、NaN。
- **LSTM**：cell state 走以加法为主的路径 `c_t = f_t ⊙ c_{t-1} + i_t ⊙ g_t`，遗忘门可学到接近 1，梯度沿"高速公路"回传；GRU 用更新门 `z_t` 在新旧状态间插值，原理相似。
- **爆炸的处理**：梯度裁剪（clip by global norm）、降低学习率、正交初始化、LayerNorm。
- **加分点**：常见技巧是把遗忘门 bias 初始化为 1，让训练初期默认"记住"；指出 LSTM 只是**缓解**而非根治，讲义说 200+ 步仍困难。
- **常见误区**：认为换 ReLU 就能解决 RNN 梯度消失。

### Q12 — 参考回答要点

- **LSTM**（σ 为 sigmoid，⊙ 为逐元素乘）：
  - `i_t = σ(W_i x_t + U_i h_{t-1} + b_i)`（输入门）
  - `f_t = σ(W_f x_t + U_f h_{t-1} + b_f)`（遗忘门）
  - `o_t = σ(W_o x_t + U_o h_{t-1} + b_o)`（输出门）
  - `g_t = tanh(W_g x_t + U_g h_{t-1} + b_g)`（候选值）
  - `c_t = f_t ⊙ c_{t-1} + i_t ⊙ g_t`，`h_t = o_t ⊙ tanh(c_t)`
- **GRU**：更新门 `z_t`、重置门 `r_t`；候选 `h̃_t = tanh(W x_t + U (r_t ⊙ h_{t-1}))`；`h_t = (1 - z_t) ⊙ h_{t-1} + z_t ⊙ h̃_t`。没有独立的 cell state，两个门（讲义："Two gates instead of three"）。
- **参数量**（PyTorch 每层每方向有 `weight_ih`、`weight_hh`、`bias_ih`、`bias_hh` 四组）：
  - LSTM：`4·h·(in + h) + 8·h = 4·256·(300+256) + 8·256 = 569,344 + 2,048 = 571,392`
  - GRU：`3·h·(in + h) + 6·h = 3·256·556 + 1,536 = 427,008 + 1,536 = 428,544`，约为 LSTM 的 3/4。
  - 双向再 ×2。
- **加分点**：GRU 参数少、训练快，小数据上常与 LSTM 持平；LSTM 的 cell/hidden 分离在部分长序列任务上更稳。讲义结论："Similar accuracy, fewer parameters."

### Q13 — 参考回答要点

- **padding**：变长句子要 pad 到同一长度，用 `padding_idx=0` 让 pad 的 embedding 为零向量且不更新。
- **LSTM 的隐患**：pad 位置的 embedding 虽为 0，但 LSTM 在 pad 位置的输出**不是 0**（仍有偏置和上一步状态），`out.max(dim=1)` 可能把 pad 位置的激活当成最大值；双向 LSTM 的后向分支还会**先读一串 pad** 再读真实内容，污染状态。
- **正确做法**：
  1. 用 `pack_padded_sequence` / `pad_packed_sequence` 让 LSTM 跳过 pad；
  2. 池化前用 mask 把 pad 位置设为 `-inf`（max）或排除出均值（mean）；
  3. last-state 池化要取每句**真实最后一个 token**的状态，而不是第 L 个位置。
- **TextCNN**：pad 后的窗口也会产生激活；句长要 ≥ 最大卷积宽度；按长度分桶（bucketing）减少 pad 浪费。
- **加分点**：讲义的 `BertCNN` 同样没有用 `attention_mask` 屏蔽 pad 位置的 hidden state 再做 max-pool，生产中要补上；讲义技能卡建议监控"按长度分组的准确率"。

### Q14 — 参考回答要点

- **架构**：TextCNN（宽度 2/3/4、每种 64–128 个 filter）+ 预训练词向量（GloVe / fastText，fastText 的子词能处理新词和错别字）。讲义："TextCNN with GloVe embeddings is 10-100x smaller than a transformer. If your deploy target is a phone, this is the stack."
- **体积控制**：词表裁剪到高频 2–5 万；embedding 降维到 100 维或做 int8 量化；5MB 预算中 embedding 表通常是大头。
- **训练配方**（5 行）：Adam，lr 1e-3，batch 64，10–20 epoch + early stopping，dropout 0.3–0.5。
- **对比基线**：讲义技能卡的原则——数据量小时，先证明 TextCNN / BiLSTM 基线已经到顶，再考虑 transformer；2 万条数据可以再试蒸馏一个小 transformer 作对照，但要满足 10ms 的延迟。
- **监控**：按句长分组的准确率（CNN/RNN 缺 attention，长句易掉点）、各意图的混淆矩阵、端上延迟 P99。
- **常见误区**：不看部署约束直接上 BERT；讲义原话："Flag edge deployment as needing architecture-before-everything."

### Q15 — 参考回答要点

- **讲义观点的合理部分**：RNN 每来一个 token 只做一次 `O(1)` 的状态更新，内存是固定大小的隐状态；双向 Transformer 编码器（如 BERT）必须等完整序列才能编码。
- **需要补充的细节**：因果（decoder-only）Transformer 配合 KV cache 也能逐 token 增量处理，但每步要对全部历史做 attention，**每 token 计算量和 KV cache 内存都随已处理长度线性增长**；对"无限长、持续不断"的流（传感器文本、实时字幕），RNN 的常数状态更有优势。
- **结论**：在内存/算力受限、流无限长的场景下，循环结构仍有优势；若有服务器资源、需要全局上下文，Transformer 更好。
- **加分点**：近年的状态空间模型（SSM，如 Mamba）和混合架构（Transformer + SSM）正是在追求"训练可并行 + 推理常数状态"的两全；滑动窗口 attention 是 Transformer 一侧的折中。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：`nn.Module`、`nn.Embedding`、`nn.Conv1d`、`nn.LSTM` 的使用。
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../03-word-embeddings-word2vec/docs/zh.md)：TextCNN / LSTM 的输入就是词向量序列。
- [阶段 04 · 02 从零实现卷积](../../../04-computer-vision/02-convolutions-from-scratch/docs/zh.md)：2D 卷积，本节是它在序列上的 1D 版本。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：链式法则连乘是梯度消失/爆炸的根源。

### 本节被哪些后续内容用到
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：BiLSTM-CRF 是小数据 NER 的生产级架构。
- [阶段 05 · 07 词性标注和句法分析](../../07-pos-tagging-parsing/docs/zh.md)：BiLSTM-CRF 标注器在 POS 上可达 98% 左右。
- [阶段 05 · 09 序列到序列模型](../../09-sequence-to-sequence/docs/zh.md)：LSTM encoder-decoder 与"定长上下文向量瓶颈"。
- [阶段 05 · 10 Attention 机制](../../10-attention-mechanism/docs/zh.md)：解决本节列出的三个遗留问题。
- [阶段 07 · 01 为什么是 Transformers](../../../07-transformers-deep-dive/01-why-transformers/docs/zh.md)：彻底抛弃循环、全并行的架构。
- [阶段 10 · 21 Jamba 混合 SSM-Transformer](../../../10-llms-from-scratch/21-jamba-hybrid-ssm-transformer/docs/zh.md)：循环式状态在大模型时代的回归。

### 延伸关键词
`BPTT` · `梯度裁剪 (clip_grad_norm_)` · `pack_padded_sequence` · `遗忘门 bias 初始化` · `空洞卷积 (dilated conv)` · `k-max pooling` · `char-CNN` · `BiLSTM-CRF` · `ELMo` · `SSM / Mamba` · `RWKV`
