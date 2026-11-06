# 测验 · 多头 Attention（Multi-Head Attention）

> **阶段 07 · Transformers 深入 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要多头 | 单头只有一个 softmax 分布，多种关系（主谓一致、指代、长程语篇）会被"抹"在一起；多头让每个头在自己的子空间里专注一种关系 |
| 2 | Split（拆头） | `(N, d_model)` → reshape 成 `(N, h, d_head)` → transpose 成 `(h, N, d_head)`；第 h 个头拿到的是 Q 的第 `h·d_head` 到 `(h+1)·d_head − 1` 列 |
| 3 | 并行计算 | 各头独立做 scaled dot-product attention，在 GPU 上是一次批量 matmul `(h, N, d_head) × (h, d_head, N) → (h, N, N)` |
| 4 | Combine + `W_o` | 拼回 `(N, d_model)` 后乘 `W_o (d_model, d_model)`；头与头之间的信息**只在 `W_o` 处混合** |
| 5 | 参数量不变 | `d_head = d_model / h`，Q/K/V/O 四个投影总参数始终是 `4·d_model²`（不计 bias），多头不增加参数 |
| 6 | d_head 的经验值 | 生产模型几乎都是 64 或 128；Llama 3 70B 是 `d_model = 8192, 64 头, d_head = 128` |
| 7 | MQA | 所有 Q 头共享 1 组 K/V，KV cache 最小，有一定质量损失（PaLM、Falcon） |
| 8 | GQA | K/V 只有 `G = n_kv_heads` 组，每组被 `n_heads / G` 个 Q 头共享；KV cache 缩小 `n_heads / G` 倍，质量接近 MHA，是 2026 年的默认选择 |
| 9 | MLA | DeepSeek-V2/V3：把 K/V 压缩成低秩 latent 存进 cache，计算时再投影回来——多花 FLOPs，省更多显存 |
| 10 | 头的分工 | 探针研究发现位置头、前一 token 头、复制头、induction head（与 in-context learning 相关）等不同角色 |

### 核心技能（能动手做到）

- [ ] 说清 `split_heads` 的列切分与 NumPy 版 `reshape(n, h, d_head).transpose(1, 0, 2)` 完全等价，并解释为什么不能直接 `reshape(h, n, d_head)`
- [ ] 手算 `main.py` 中 MHA 与 GQA 两种配置的参数量和 KV cache 元素数（256 vs 192；96 vs 48）
- [ ] 解释 `Kh_small[i // repeat]` 的分组映射，并验证 `n_kv_heads == n_heads` 时 GQA 与 MHA 输出完全相同
- [ ] 为给定模型配置（层数、KV 头数、d_head、精度、上下文长度）估算 KV cache 显存
- [ ] 把 `grouped_query_attention` 改成 MQA（`n_kv_heads = 1`）并说出参数与 cache 的变化
- [ ] 根据参数预算、上下文长度、部署显存，给出 `n_heads / n_kv_heads / d_head` 的合理配置并满足 `d_model = n_heads·d_head`、`n_heads % n_kv_heads == 0`

---

## 二、基础自测（选择题）

**Q1.** `d_model = 4096`，`n_heads = 32`。每个头的维度 `d_head` 和 `W_q` 的形状分别是：

- A. 4096；`(4096, 4096 × 32)`
- B. 128；`(4096, 4096)`
- C. 128；`(128, 128)`
- D. 32；`(4096, 32)`

**Q2.** 在标准多头 attention 中，不同头之间的信息在哪里第一次发生混合？

- A. 在 softmax 里，各头的分数会一起归一化
- B. 在拼接之后的输出投影 `W_o` 处
- C. 在计算 Q、K、V 的时候，各头共享同一组 Q
- D. 从不混合，各头的输出直接作为下一层输入

**Q3.** 对一个 `(N, d_model)` 的 Q 做拆头，下列哪种写法是**错误**的？

- A. `Q.reshape(N, h, d_head).transpose(1, 0, 2)`
- B. 对每个头 h 取 `Q[:, h*d_head:(h+1)*d_head]` 再堆叠
- C. `Q.reshape(h, N, d_head)`
- D. `np.stack(np.split(Q, h, axis=1))`

**Q4.** GQA 相比 MHA 节省的主要是什么？

- A. `QKᵀ` 的计算量，因为 Q 头数减少了
- B. 推理时 KV cache 的显存（以及 decode 时读取 cache 的带宽），缩小 `n_heads / n_kv_heads` 倍
- C. 输出投影 `W_o` 的参数量
- D. 训练时激活值的显存，因为 attention 矩阵变少了

**Q5.** 关于 MHA、GQA、MQA 三者的关系，正确的是：

- A. GQA 在 `n_kv_heads = 1` 时退化为 MHA
- B. GQA 在 `n_kv_heads = n_heads` 时退化为 MHA，在 `n_kv_heads = 1` 时退化为 MQA
- C. MQA 的 Q 头也只有 1 个
- D. 三者的 attention 权重矩阵数量不同：MQA 只有 1 个 `(N, N)` 矩阵

**Q6.** 与 GQA 相比，DeepSeek 的 MLA（Multi-head Latent Attention）的核心取舍是：

- A. 减少 Q 头数，牺牲质量换速度
- B. 把 K/V 压缩成低秩 latent 存入 cache，计算时再投影回去：多花计算，换更小的 cache
- C. 完全去掉 KV cache，每步重新计算所有历史 token
- D. 用稀疏 attention 只关注部分 token

**Q7.** 下列关于多头参数量的说法，正确的是（不计 bias）：

- A. 头数翻倍，参数量翻倍
- B. 无论头数多少，Q/K/V/O 四个投影的总参数都是 `4·d_model²`
- C. 多头需要额外的"头选择"参数
- D. 多头的参数量是 `4·d_model²·n_heads`

---

## 三、动手 / 代码题

**Q8.** 阅读 `split_heads`：

```python
def split_heads(X: Matrix, n_heads: int) -> List[Matrix]:
    assert X.cols % n_heads == 0, "d_model not divisible by n_heads"
    d_head = X.cols // n_heads
    heads = []
    for h in range(n_heads):
        H = Matrix(X.rows, d_head)
        for i in range(X.rows):
            for j in range(d_head):
                H.set(i, j, X.get(i, h * d_head + j))
        heads.append(H)
    return heads
```

(a) 主程序中 `Q` 是 `6×8`，`n_heads = 2`。head 1 拿到的是 Q 的哪几列？
(b) 用 NumPy 写出等价的一行代码，并说明为什么 `Q.reshape(n_heads, 6, d_head)` 是错的（可用 `np.arange(12).reshape(3, 4)`、`h = 2` 举例）。

**Q9.** 阅读 `grouped_query_attention` 的分组逻辑：

```python
    Qh = split_heads(Q, n_heads)
    Kh_small = split_heads(K, n_kv_heads)
    Vh_small = split_heads(V, n_kv_heads)
    repeat = n_heads // n_kv_heads
    Kh = [Kh_small[i // repeat] for i in range(n_heads)]
    Vh = [Vh_small[i // repeat] for i in range(n_heads)]
```

(a) `n_heads = 4, n_kv_heads = 2` 时，Q 头 0–3 分别使用哪个 KV 头？
(b) 如果把 `i // repeat` 改成 `i % n_kv_heads`，结果在数学上还对吗？加载别人训练好的 GQA 权重时会有什么问题？
(c) 设计一个实验验证"`n_kv_heads == n_heads` 时 GQA 与 MHA 完全等价"。
(d) 主程序里 `Wk` 的形状为什么是 `(d_model, (d_model // n_heads) * n_kv)`？

**Q10.** 主程序的 KV cache 计算只数了"元素个数"：

```python
kv_cache_full = n_heads * n * (d_model // n_heads) * 2
kv_cache_gqa = n_kv * n * (d_model // n_heads) * 2
```

(a) 写出它打印的两个数字，并解释公式里的 `* 2`。
(b) 写一个函数 `kv_cache_bytes(n_layers, n_kv_heads, d_head, seq_len, batch=1, bytes_per_elem=2)`，并计算一个 Llama-3-70B 规模的配置（80 层、64 个 Q 头、8 个 KV 头、`d_head = 128`、fp16）在 8K 上下文下，GQA / MHA / MQA 各需要多少显存。

---

## 四、面试高频题

**Q11.**（基础必考）为什么 Transformer 要用多头 attention？多头和"一个 `d_model` 维的大单头"相比，参数量和计算量有什么变化？好处在哪？

**Q12.**（工程实践）讲一讲 MHA、MQA、GQA、MLA 的区别。为什么 GQA 能成为主流？如果手里只有一个 MHA checkpoint，怎么得到 GQA 模型？

**Q13.**（工程实践）为什么说 LLM 的 decode 阶段通常是"显存带宽受限"的？GQA 为什么能同时降低显存占用并提升 decode 速度？

**Q14.**（追问型）"多头里每个头真的学到了不同东西吗？头越多越好吗？`d_head` 为什么几乎总是 64 或 128？"

**Q15.**（场景设计）要为一个 `d_model = 2048`、目标上下文 32K、部署在 24GB 显卡上的约 1B 模型设计 attention 配置，你会怎么选？请给出 `n_heads / n_kv_heads / d_head` 和理由。

---

## 五、参考答案与解析

### Q1 — 答案：B

`d_head = 4096 / 32 = 128`。实现上所有头的 Q 投影合成一个 `(4096, 4096)` 矩阵，算完后再拆成 32 份 `(N, 128)`。A 把头数乘在了输出维度上（那是"每头都用满维度"的错误理解）；C 是每头内部的维度，但投影矩阵的输入仍是 `d_model`；D 混淆了头数与头维度。

### Q2 — 答案：B

讲义原话："The heads operate on different subspaces … and never talk during the attention computation itself"，"`W_o` is where heads get to mix"。每个头的 softmax 只在自己的 `(N, N)` 分数矩阵内按行归一化（A 错）；MHA 里各头有独立的 Q（C 错，共享 K/V 的是 MQA/GQA）；拼接后的 `W_o` 是一个完整的 `(d_model, d_model)` 矩阵，每个输出维度都是所有头输出的线性组合。

### Q3 — 答案：C

`Q.reshape(h, N, d_head)` 按行优先顺序重新切分内存，会把**不同 token 的数据**混进同一个头。用 `np.arange(12).reshape(3, 4)`（3 个 token、4 维、2 头）验证：正确拆法得到头 0 = `[[0,1],[4,5],[8,9]]`（每个 token 的前两维），而直接 reshape 得到 `[[0,1],[2,3],[4,5]]`——第 0 个 token 的后两维被当成了第 1 个 token。A、B、D 都是"按列切、每头保留全部 token"的等价写法。

### Q4 — 答案：B

GQA 只减少 K/V 的头数，Q 头数不变，所以 `QKᵀ` 的计算量基本不变（A 错）；`W_o` 不变（C 错）。KV cache 只需要存 `n_kv_heads` 份 K、V，缩小 `n_heads / n_kv_heads` 倍：Llama 3 70B 是 64 个 Q 头、8 个 KV 头，缩小 8 倍。decode 每步都要把整个 cache 从显存读一遍，cache 小了，带宽压力也小了。

### Q5 — 答案：B

GQA 是两者之间的连续谱：`n_kv_heads = n_heads` 每个 Q 头独享一组 K/V，即 MHA；`n_kv_heads = 1` 所有 Q 头共享一组，即 MQA。C 错：MQA 依然有 N 个 Q 头；D 错：三者都有 `n_heads` 个 `(N, N)` 权重矩阵——因为 Q 头不同，即使共享 K，分数也不同。代码中 `grouped_query_attention` 对每个 Q 头都调用一次 attention 正好体现了这一点。

### Q6 — 答案：B

讲义："MLA goes further by compressing K/V into a latent space, then projecting back at compute time — costs FLOPs, saves a lot more memory." A 描述的不是 MLA；C 是"不用 cache"，会让 decode 代价变成平方级；D 是稀疏 attention（第 15 节、阶段 10 的 NSA）。

### Q7 — 答案：B

`W_q、W_k、W_v、W_o` 都是 `(d_model, d_model)`，与头数无关，总计 `4·d_model²`。头数只决定"如何把 `d_model` 维切分"。以 `main.py` 的 MHA 为例：`4 × 8 × 8 = 256`。（GQA 会减少 `W_k、W_v` 的输出维度，因此参数会变少——见 Q9(d) 中的 192。）

### Q8 — 参考答案

(a) `d_head = 8 // 2 = 4`，head 1 拿第 `1·4 + j`（j = 0..3）列，即 **第 4、5、6、7 列**，6 个 token 全部保留。

(b) 等价写法：

```python
import numpy as np

def split_heads_np(Q, n_heads):
    n, d = Q.shape
    d_head = d // n_heads
    return Q.reshape(n, n_heads, d_head).transpose(1, 0, 2)   # (h, n, d_head)

X = np.arange(12).reshape(3, 4)          # 3 个 token，d_model = 4
print(split_heads_np(X, 2)[0])           # [[0 1] [4 5] [8 9]]   ← 每个 token 的前两维
print(X.reshape(2, 3, 2)[0])             # [[0 1] [2 3] [4 5]]   ← 错：token 0 的后两维混进来了
```

原因：NumPy 默认按行优先（C order）存储，`reshape` 只是换一种方式"读"同一块连续内存。先 `reshape(n, h, d_head)` 只在每一行（一个 token）内部切分，不跨 token；再 `transpose` 把头维挪到最前面。直接 `reshape(h, n, d_head)` 则是从头到尾按 `d_head` 个一组、`n` 组一个头地切，跨越了 token 边界。我们也验证了 `split_heads` 的结果与 `split_heads_np` 逐元素相同。

### Q9 — 参考答案

(a) `repeat = 4 // 2 = 2`，`i // 2` 对 i = 0、1、2、3 得到 `0, 0, 1, 1`：Q 头 0、1 共享 KV 头 0，Q 头 2、3 共享 KV 头 1——相邻的 Q 头为一组。这与讲义里 `np.repeat(kv, repeat, axis=0)` 的结果一致（`[kv0, kv0, kv1, kv1]`）。

(b) `i % n_kv_heads` 得到 `0, 1, 0, 1`（交错分组）。**单独看数学**，只要训练和推理用同一种约定，两种分组都能训练出等价的模型。但**加载已有权重时会出错**：Q 头的顺序（`W_q` 的列顺序）是按"连续分组"训练出来的，换成交错分组后，Q 头 1 会去和 KV 头 1 配对，而训练时它是和 KV 头 0 一起学的，输出就乱了，不会报错但结果错误。工程上要与框架约定保持一致（例如 PyTorch 生态常用的 `repeat_interleave` 就是连续分组）。

(c) 用同一组 `Wq、Wk、Wv、Wo`（都是 `d_model × d_model`），分别调用 `multi_head_attention(X, ..., n_heads=4)` 和 `grouped_query_attention(X, ..., n_heads=4, n_kv_heads=4)`，比较两个输出矩阵的 `data` 最大绝对差：

```python
o_mha, _ = multi_head_attention(X, Wq, Wk, Wv, Wo, n_heads=4)
o_gqa = grouped_query_attention(X, Wq, Wk, Wv, Wo, n_heads=4, n_kv_heads=4)
print(max(abs(a - b) for a, b in zip(o_mha.data, o_gqa.data)))   # 实测 0.0
```

`repeat = 1`，`Kh[i] = Kh_small[i]`，两条路径的计算完全相同。

(d) 每个 KV 头的维度要与 Q 头的 `d_head = d_model // n_heads = 2` 相同（否则 `QKᵀ` 维度对不上），共有 `n_kv = 2` 个 KV 头，所以 K、V 的总宽度是 `2 × 2 = 4`，`Wk` 形状为 `(8, 4)`。这正是 GQA 省参数的来源：`Wk、Wv` 各从 64 降到 32，总参数从 256 降到 192。

### Q10 — 参考答案

(a) 输出：

```text
KV cache elements (MHA):  96
KV cache elements (GQA):  48  (2x smaller)
```

`4 × 6 × 2 × 2 = 96`，`2 × 6 × 2 × 2 = 48`。最后的 `* 2` 是因为要同时缓存 **K 和 V** 两份。

(b) 参考实现（按"每层每个 KV 头存 `seq_len × d_head` 个元素，K、V 各一份"计算）：

```python
def kv_cache_bytes(n_layers, n_kv_heads, d_head, seq_len, batch=1, bytes_per_elem=2):
    return 2 * n_layers * n_kv_heads * d_head * seq_len * batch * bytes_per_elem


GiB = 2 ** 30
for name, kv_heads in [("MHA", 64), ("GQA", 8), ("MQA", 1)]:
    b = kv_cache_bytes(80, kv_heads, 128, 8192)
    print(f"{name}: {b / GiB:.2f} GiB  ({b / 8192 / 1024:.0f} KiB/token)")
```

结果：

| 变体 | 每 token | 8K 上下文（batch = 1） |
|------|---------|---------------------|
| MHA（64 个 KV 头） | 2560 KiB | 20.00 GiB |
| GQA（8 个 KV 头） | 320 KiB | 2.50 GiB |
| MQA（1 个 KV 头） | 40 KiB | 0.31 GiB |

如果上下文拉到 128K，GQA 也要 40 GiB/序列——这就是长上下文推理需要 cache 量化、PagedAttention、MLA 等进一步手段的原因。

### Q11 — 参考回答要点

- **动机**：单头只有一个 softmax 分布，它会收敛到"对 loss 最有利的那一种关系"，其他关系被平均掉；多头让模型在不同子空间里同时维持多个注意力分布（讲义："one attention head learns one relation at a time"）。
- **参数量**：不变，Q/K/V/O 总计 `4·d_model²`。
- **计算量**：投影部分不变；分数部分 `h × N² × d_head = N² × d_model`，与单头 `d_model` 维相同；只是多了 reshape/transpose 的开销，在 GPU 上作为一次批量 matmul 执行，几乎免费。
- **好处**：表达能力提升（多个低维子空间的 attention 分布 + `W_o` 混合）、头的分工可解释（位置头、induction head 等）。
- **加分点**：指出多头带来的是"多个独立的注意力分布"，而单头大维度只能有一个分布；提到 `W_o` 是头间混合的唯一位置。
- **常见误区**：认为"多头 = 参数量乘以头数"。

### Q12 — 参考回答要点

| 变体 | Q 头 | K/V 头 | KV cache | 代表模型（据讲义） |
|------|------|--------|---------|-------------------|
| MHA | N | N | 最大 | GPT-2、BERT、T5 |
| MQA | N | 1 | 最小，质量有损 | PaLM、Falcon |
| GQA | N | G | 缩小 N/G 倍，质量接近 MHA | Llama 2 70B、Llama 3+、Qwen 2+、Mistral |
| MLA | N | 低秩 latent | 比 GQA 更小，计算更多 | DeepSeek-V2、V3 |

- **GQA 为何成为主流**：在 MHA 的质量和 MQA 的显存之间取得了很好的平衡，实现简单（只是 K/V 头数变少 + 复制），与 Flash Attention、PagedAttention 等工程栈兼容；PyTorch 2.5+ 的 `scaled_dot_product_attention` 已支持 `enable_gqa=True`。
- **MHA → GQA**：讲义引用的 Ainslie et al.（2023）给出了做法——把同一组内各头的 K、V 投影矩阵做平均（mean-pool）合成一个 KV 头，再用原预训练计算量的一小部分继续训练（uptraining）恢复质量。
- **加分点**：能估算具体模型的 KV cache；指出 MLA 在推理时可以把部分投影吸收进其他矩阵以减少额外计算（细节见阶段 10 · 20 DeepSeek-V3）。

### Q13 — 参考回答要点

- **decode 的特点**：每一步只处理 1 个新 token（每个序列），但要读取**全部模型权重**和**全部历史 KV cache**。计算量是 O(参数量)，访存量也是 O(参数量 + cache)，算术强度（FLOPs / 字节）很低，GPU 的算力用不满，瓶颈在 HBM 带宽。
- **GQA 的作用**：
  1. cache 缩小 `n_heads / n_kv_heads` 倍 → 同样显存能放更大 batch 或更长上下文；
  2. 每步要读取的 cache 字节数也缩小同样倍数 → 长上下文时每个 token 的延迟下降；
  3. 更大的 batch 进一步提高权重读取的复用率（一次读权重服务更多序列）。
- **加分点**：区分 prefill（计算受限，大矩阵乘）与 decode（带宽受限）；提到 PagedAttention 管理 cache 碎片、KV cache 量化等补充手段（阶段 07 · 12、阶段 17 · 04）。

### Q14 — 参考回答要点

- **头确实有分工**：讲义提到探针研究发现了位置头、前一 token 头、复制头、命名实体头和 induction head；Olsson et al.（2022）把 induction head 与 in-context learning 联系起来。
- **但不是所有头都必要**：已有剪枝研究（如 Michel et al. 2019 "Are Sixteen Heads Really Better than One?"）发现，训练好的模型中相当一部分头可以在推理时去掉而性能下降很小——头之间存在冗余。
- **头越多越好吗**：在 `d_model` 固定时，头越多 `d_head` 越小。`d_head` 太小时每个头的 Q·K 只能在很低维空间里表达相似度，表达能力受限（讲义："Drop below 32 and heads start fighting…"）；太大（>256）则失去"许多小专家"的好处。
- **为什么是 64 / 128**：经验 + 硬件。这两个数对 GPU 的 tile 尺寸和 Flash Attention 等 kernel 很友好；讲义的配置表显示 125M–70B 级别模型都落在这两个值上。
- **加分点**：提到讲义练习 1（固定 `d_model = 64`，头数从 1 到 16 做复制任务）正是用实验回答这个问题的方式。

### Q15 — 参考回答要点

一个合理的方案（并给出算账过程）：

- **几何**：`d_head = 128`，`n_heads = 2048 / 128 = 16`（与讲义 "Large ~1B: 2048 / 16 / 128" 一致）；`n_kv_heads = 4`（GQA，每 4 个 Q 头共享 1 组 KV），满足 `16 % 4 == 0`。
- **算账**（假设 24 层、fp16）：每 token 的 cache = `2 × 24 × 4 × 128 × 2 B = 48 KiB`；32K 上下文单序列约 1.5 GiB。若用 MHA（16 个 KV 头）则约 6 GiB/序列，batch 稍大就会挤占 1B 模型权重（fp16 约 2 GB）之外的大部分显存。
- **理由**：32K 上下文下 KV cache 是推理显存的主要变量，GQA 把它压到原来的 1/4，又不明显损失质量；1B 规模不建议上 MLA（配套 skill 也明确：1B 以下除非专门做对比实验，否则不推荐 MLA）。
- **补充**：配合 Flash Attention（prefill 的 N² 显存）和 RoPE（长上下文位置编码，第 04 节）。
- **常见误区**：只给出头数不算 cache；或推荐 `d_head < 32`。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：单头 scaled dot-product attention，本节在其外面套上 split / combine。
- [阶段 01 · 12 Tensor 操作](../../../01-math-foundations/12-tensor-operations/docs/zh.md)：reshape、transpose、行优先存储，拆头的基础。
- [阶段 01 · 01 线性代数直觉](../../../01-math-foundations/01-linear-algebra-intuition/docs/zh.md)：子空间、投影、低秩（理解 MLA 的低秩压缩）。

### 本节被哪些后续内容用到
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：多头 attention 作为每个 block 的子层。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：本节 GQA/MQA 节省的 KV cache 在推理中的完整图景。
- [阶段 10 · 14 开放模型：架构详解](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：各开源模型的头数 / KV 头数配置。
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../../10-llms-from-scratch/20-deepseek-v3-walkthrough/docs/zh.md)：MLA 的完整实现。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：PagedAttention 如何管理 KV cache。
- [阶段 19 · 33 多头 Self-Attention](../../../19-capstone-projects/33-multihead-self-attention/docs/zh.md)：综合项目中的多头实现。

### 延伸关键词
`MQA` · `GQA` · `MLA` · `repeat_interleave` · `enable_gqa` · `KV cache` · `induction head` · `head pruning` · `arithmetic intensity` · `PagedAttention`
