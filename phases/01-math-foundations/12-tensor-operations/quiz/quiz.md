# 测验 · Tensor 操作（Tensor Operations）

> **阶段 01 · 数学基础 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/tensors.py](../code/tensors.py) ｜ 代码讲解：[code/tensors.讲解.md](../code/tensors.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 张量的基本属性 | 统一 dtype 的多维数组；rank（ndim）= 轴数，shape = 各轴大小，size = 各维之积。张量的 rank 与线性代数里的"矩阵秩"是两回事 |
| 2 | 深度学习的形状约定 | 图像 `(B, C, H, W)`，文本 `(B, T, D)`，多头注意力 `(B, H, T, D_head)`；Linear 权重 `(out, in)`、Conv2D `(out_c, in_c, kH, kW)`、Embedding `(vocab, dim)` |
| 3 | 内存布局与 strides | 张量在内存里是一维的；行优先时 `stride[i] = stride[i+1] × shape[i+1]`，扁平下标 `= Σ indexᵢ × strideᵢ` |
| 4 | reshape / view | 不改变元素的逻辑顺序，只换形状；元素总数必须守恒；`-1` 让框架推断一维 |
| 5 | squeeze / unsqueeze / flatten | 删除 / 插入大小为 1 的轴；`flatten(start_dim=1)` 把除 batch 外的轴压成一维 |
| 6 | transpose / permute 与连续性 | 真实框架里只交换 strides、不移动数据，结果变成非连续（non-contiguous）；PyTorch 的 `view` 此时可能失败，需 `.contiguous()` 或改用 `reshape` |
| 7 | 广播规则 | 从右往左对齐，维度相等或其中一个为 1 才兼容，缺的维度在左边补 1；某些形状错误不会报错，而是悄悄广播出错误结果 |
| 8 | 归约（reduction） | `sum/mean/max` 沿 axis 求值后该轴消失；全局平均池化 `(B,C,H,W).mean((2,3)) → (B,C)`；带 mask 的序列平均池化要除以有效长度 |
| 9 | einsum | 每个轴用一个字母标注；输入有而输出没有的字母被求和（收缩）；计算量 = 所有字母对应大小之积 |
| 10 | 多头注意力的形状流 | `(B,T,E) → 投影 → (B,T,H,D) → 转置 (B,H,T,D) → 分数 (B,H,T,T) → 输出 (B,H,T,D) → 转置+reshape (B,T,E)` |

### 核心技能（能动手做到）

- [ ] 从零实现带 `shape / strides` 的 Tensor 类，能手算任意形状的行优先 strides 和某个下标对应的扁平位置
- [ ] 给出任意两个形状，30 秒内判断能否广播以及结果形状，并能写出实现这一规则的函数
- [ ] 用 einsum 写出点积、外积、矩阵乘、迹、对角线、批量矩阵乘、注意力分数 / 加权和，并说出每个表达式中哪个字母被求和
- [ ] 写出多头注意力 split heads / merge heads 的正确代码，并用 round-trip（拆开再合并后 `allclose`）验证
- [ ] 用 NumPy 的 `.strides`、`.flags['C_CONTIGUOUS']` 检查转置、切片后的内存布局，解释为什么它们是"视图"
- [ ] 估算张量显存（元素数 × 每元素字节数），例如说出 `(16, 12, 512, 512)` 的 float32 注意力分数约 192 MB，且随 T 平方增长
- [ ] 用 mask 正确实现变长序列的 mean pooling，用 `mean(axis=(2,3))` 实现全局平均池化

---

## 二、基础自测（选择题）

**Q1.** 一个形状为 `(2, 3, 4)` 的行优先（C order）连续张量，按**元素个数**计的 strides 是：

- A. `(12, 4, 1)`
- B. `(1, 2, 6)`
- C. `(4, 3, 1)`
- D. `(96, 32, 8)`

**Q2.** 下列哪一对形状**不能**广播？

- A. `(3, 4)` 和 `(4,)`
- B. `(2, 1, 3)` 和 `(1, 4, 3)`
- C. `(5, 3)` 和 `(5,)`
- D. `(8, 1, 6, 1)` 和 `(7, 1, 5)`

**Q3.** `np.ones((3, 3))` 的 `ndim`（张量的 rank）和 `np.linalg.matrix_rank`（矩阵秩）分别是：

- A. 2 和 1
- B. 2 和 3
- C. 3 和 1
- D. 9 和 3

**Q4.** 多头注意力里，把 `x` 从 `(B, T, D)` 拆成 `(B, H, T, D_head)`（`D = H × D_head`）的正确写法是：

- A. `x.reshape(B, H, T, D_head)`
- B. `x.reshape(B, T, H, D_head).transpose(0, 2, 1, 3)`
- C. `x.transpose(0, 2, 1).reshape(B, H, T, D_head)`
- D. `x.reshape(B, T, H, D_head)`，不需要再做别的

**Q5.** 计算注意力分数 `np.einsum("bhtd,bhsd->bhts", Q, K)`，其中 B=16、H=12、T=S=512、D=64。它需要的乘加次数是：

- A. `16 × 12 × 512 × 64`
- B. `16 × 12 × 512 × 512 × 64`
- C. `16 × 12 × 512 × 512`
- D. `16 × 512 × 768`

**Q6.** 在 PyTorch 中，`x` 是形状 `(2, 3)` 的连续张量，执行 `y = x.transpose(0, 1)` 后，下列说法正确的是：

- A. `y` 的数据被复制到一块新的连续内存里
- B. `y` 与 `x` 共享内存，只是 strides 互换了，`y.is_contiguous()` 为 False，`y.view(6)` 会报错
- C. `transpose` 改变了元素总数
- D. `y.view(6)` 可以正常执行，结果与 `x.view(6)` 相同

**Q7.** `hidden` 形状 `(4, 128, 768)`，`mask` 形状 `(4, 128, 1)`，有效位置为 1、padding 位置为 0。正确的序列平均池化是：

- A. `hidden.mean(axis=1)`
- B. `(hidden * mask).sum(axis=1) / mask.sum(axis=1)`
- C. `(hidden * mask).mean(axis=1)`
- D. `hidden.sum(axis=1) / 100`

**Q8.** float32 注意力分数张量 `(16, 12, 512, 512)` 约占 192 MB。其他不变、序列长度 T 翻倍到 1024，它大约占：

- A. 384 MB
- B. 768 MB
- C. 192 MB
- D. 1.5 GB

---

## 三、动手 / 代码题

**Q9.** 使用 `tensors.py` 中从零实现的 `Tensor` 类，写出下面每一行的输出；再回答：同样的 `permute` 如果在 NumPy 中执行（`np.arange(24).reshape(2, 3, 4).transpose(2, 0, 1)`），strides（按元素计）是多少？两者的差别说明了什么？

```python
t = Tensor(list(range(24)), shape=(2, 3, 4))
print(t.strides)
print(t[1, 2, 3])
p = t.permute((2, 0, 1))
print(p.shape, p.strides)
print(p[3, 1, 2])
```

**Q10.** `Tensor._elementwise_op` 要求两个张量形状完全相同，否则抛出 `ValueError(... "Use broadcast() first.")`——但这个类里其实并没有 `broadcast()` 方法。请先实现一个纯 Python 函数 `broadcast_shape(sa, sb)`：返回两个形状广播后的结果形状，不兼容时抛出 `ValueError`。要求对 `demo_broadcasting_numpy` 里的 4 组形状给出与 NumPy 一致的结果，并对 `(5, 3)` 与 `(5,)` 报错。

**Q11.** 下面是 `demo_attention_einsum` 的核心部分（B, H, T, D = 2, 4, 8, 16，E = H × D = 64）。

```python
    Q = Q.reshape(B, T, H, D).transpose(0, 2, 1, 3)
    # ...
    scores = np.einsum("bhtd,bhsd->bhts", Q, K) / np.sqrt(D)

    def softmax(x, axis=-1):
        e = np.exp(x - np.max(x, axis=axis, keepdims=True))
        return e / np.sum(e, axis=axis, keepdims=True)

    weights = softmax(scores, axis=-1)
    attn_output = np.einsum("bhts,bhsd->bhtd", weights, V)
    concat = attn_output.transpose(0, 2, 1, 3).reshape(B, T, E)
```

1. 写出 `scores`、`weights`、`attn_output`、`concat` 的形状。
2. 如果把最后一行写成 `concat = attn_output.reshape(B, T, E)`（省掉 transpose），会报错吗？结果对吗？
3. `softmax` 里为什么要 `keepdims=True`？去掉会怎样？

---

## 四、面试高频题

**Q12.**（基础必考）PyTorch 里 `view`、`reshape`、`transpose`、`permute`、`contiguous` 分别做什么？`view` 什么时候会失败？

**Q13.**（原理深挖）讲一下广播规则。举一个"不报错但结果错误"的广播 bug，你在工程里怎么防范？

**Q14.**（原理深挖）einsum 怎么读？它和 `matmul` / `@` 相比有什么优劣？多操作数 einsum 的计算顺序为什么重要？

**Q15.**（场景设计）给定 batch=16、heads=12、seq_len=512、hidden=768，请逐步写出多头自注意力每一步的张量形状，并估算注意力分数矩阵的显存。如果 seq_len 增长到 8192 会怎样？工业界怎么解决？

**Q16.**（工程实践）NCHW 和 NHWC 有什么区别？什么时候需要在两者之间转换，转换后要注意什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

行优先时最后一维 stride 为 1，往左依次乘上右边的维度大小：`stride[1] = 1 × 4 = 4`，`stride[0] = 4 × 3 = 12`，即 `(12, 4, 1)`——与 `Tensor._compute_strides` 的循环完全对应。D 是 **字节** strides（float64 每个元素 8 字节：`12×8, 4×8, 1×8`），NumPy 的 `.strides` 返回的就是字节数，代码里用 `s // a.itemsize` 换算成元素数。B 是列优先（F order）的 strides。

### Q2 — 答案：C

从右对齐：`(5, 3)` 与 `(5,)` 对齐后比较的是最后一维 `3` vs `5`，既不相等也没有 1，报错。很多人以为 `(5,)` 会对齐到第一维（batch 维），这正是广播最常见的误解——要按行加，需写成 `(5, 1)`。A 对齐后是 `4 vs 4`；B 结果 `(2, 4, 3)`；D 结果 `(8, 7, 6, 5)`（代码 `demo_broadcasting_numpy` 都验证过）。

### Q3 — 答案：A

`ndim` 是轴的个数：2。全 1 矩阵的三行完全相同，线性无关的行只有 1 行，矩阵秩为 1。讲义 Key Terms 专门强调："A matrix has rank 2, not rank equal to its matrix rank"——面试中说"张量的 rank"时要说清指的是维数。

### Q4 — 答案：B

`(B, T, D)` 在内存里每个 token 的 D 个特征是连续的，先 `reshape(B, T, H, D_head)` 是把每个 token 的特征切成 H 段（逻辑顺序不变），再用 transpose 把 H 挪到 T 前面。A 形状正确但内容错误：它把相邻 token 的特征混进同一个"头"里，不会报错，是典型的**静默 bug**（本机验证 `x.reshape(B,H,T,D)` 与正确结果 `allclose` 为 False）。C 先转置会把特征维和时间维搅在一起；D 缺少把 H 提到前面的步骤，后续 `bhtd` 形式的 einsum 会把 H 当成 T。

### Q5 — 答案：B

einsum 的计算量是所有出现过的字母大小之积（保留的 b、h、t、s 和被求和的 d）：`16 × 12 × 512 × 512 × 64 ≈ 3.2 × 10⁹` 次乘加。C 只是输出元素个数——每个输出元素还要做 D=64 次乘加。这个算式也说明注意力的计算量随 T **平方**增长。

### Q6 — 答案：B

transpose 只改元数据：shape 变成 `(3, 2)`，strides 从 `(3, 1)` 变为 `(1, 3)`，数据不动，所以它是一个与 `x` 共享内存的视图，但已不再是行优先连续。`view(6)` 需要按 `y` 的逻辑顺序（`0,3,1,4,2,5`）线性读取，这在原内存上做不到，于是报错；`y.reshape(6)` 或 `y.contiguous().view(6)` 会复制一份再变形。A 错：复制的是 `.contiguous()`，不是 transpose。代码 `demo_memory_layout` 在 NumPy 里展示了同样的事：转置后 strides 从 `(24, 8)` 变为 `(8, 24)`，`C-contiguous: False`。

### Q7 — 答案：B

先用 mask 把 padding 位置清零，再除以**每条序列的有效长度** `mask.sum(axis=1)`（形状 `(4, 1)`，广播到 `(4, 768)`）。A 把 padding 也算进平均；C 清零了 padding，但分母仍是 128，均值被稀释；D 把有效长度写死成 100，序列长度不一时就错了，而且没有清零 padding。这正是代码 `demo_reduction_operations` 中 "Sequence mean pooling" 的写法。

### Q8 — 答案：B

分数矩阵大小 `B × H × T × T`，T 翻倍，元素数变为 4 倍：`192 MB × 4 = 768 MB`（`16×12×1024×1024×4 字节 = 768 MiB`）。这就是长上下文时注意力显存成为瓶颈的原因。

### Q9 — 参考答案

输出：

```
(12, 4, 1)
23
(4, 2, 3) (6, 3, 1)
23
```

- `t[1, 2, 3]` 的扁平位置 `= 1×12 + 2×4 + 3×1 = 23`，数据是 `range(24)`，所以值是 23。
- `permute((2, 0, 1))` 的含义是"新第 0 轴 = 旧第 2 轴，新第 1 轴 = 旧第 0 轴，新第 2 轴 = 旧第 1 轴"，形状变成 `(4, 2, 3)`，并满足 `p[a, b, c] = t[b, c, a]`，所以 `p[3, 1, 2] = t[1, 2, 3] = 23`。
- 从零实现的 `permute` 会**真的搬数据**：新建一块 `[0] * size` 的缓冲区，按新形状重新计算行优先 strides `(6, 3, 1)`，再逐个元素拷贝。

NumPy 中同样的操作，strides（字节）为 `(8, 96, 32)`，按元素计为 `(1, 12, 4)`——就是把原 strides `(12, 4, 1)` 按 `(2, 0, 1)` 重新排列，`C_CONTIGUOUS` 为 False，`np.shares_memory` 为 True，一个字节都没有复制。差别说明：**教学版的 Tensor 把 transpose/permute 实现成了"转置 + contiguous"**，逻辑结果正确，但没有体现讲义所说的"只交换 strides、不移动数据"。真实框架的视图机制是 O(1) 的，代价则是后续操作可能面对非连续内存。

### Q10 — 参考答案

```python
def broadcast_shape(sa, sb):
    ndim = max(len(sa), len(sb))
    pa = (1,) * (ndim - len(sa)) + tuple(sa)   # 规则 3：维数少的在左边补 1
    pb = (1,) * (ndim - len(sb)) + tuple(sb)
    out = []
    for i, (x, y) in enumerate(zip(pa, pb)):
        if x == y or y == 1:                   # 规则 1：相等；规则 2：一方为 1
            out.append(x)
        elif x == 1:
            out.append(y)
        else:
            raise ValueError(
                f"axis {i - ndim}: {x} vs {y} not broadcastable ({sa} vs {sb})"
            )
    return tuple(out)

for sa, sb in [((8, 1, 6, 1), (7, 1, 5)), ((3, 4), (4,)),
               ((2, 1, 3), (1, 4, 3)), ((3, 1), (1, 4))]:
    print(sa, sb, "->", broadcast_shape(sa, sb))
# (8, 7, 6, 5)  (3, 4)  (2, 4, 3)  (3, 4)

broadcast_shape((5, 3), (5,))
# ValueError: axis -1: 3 vs 5 not broadcastable ((5, 3) vs (5,))
```

要点：①先左侧补 1 再逐轴比较，比"从右往左倒着遍历"更不容易写错；②`x == y or y == 1` 时取 x，这样 `(0, 3)` 与 `(1, 3)` 得到 `(0, 3)`，与 NumPy 行为一致（本机已用 `np.broadcast_shapes` 对照验证）；③报错信息要带出具体的轴和形状，方便排查。在此基础上，就可以完成讲义练习 2：给 `Tensor` 加 `broadcast_to(shape)`，并在 `_elementwise_op` 中先广播再逐元素运算。

### Q11 — 参考答案

1. 形状：`scores` 为 `(2, 4, 8, 8)`；`weights` 同为 `(2, 4, 8, 8)`（softmax 不改形状）；`attn_output` 为 `(2, 4, 8, 16)`；`concat` 为 `(2, 8, 64)`。与运行输出一致。
2. **不会报错，但结果错误**。`attn_output` 的轴顺序是 `(B, H, T, D)`，直接 reshape 成 `(B, T, E)` 会把"第 0 个头的 8 个 token"排成一个 token 的 64 维特征，头和时间被搅混。必须先 `transpose(0, 2, 1, 3)` 把轴换回 `(B, T, H, D)`，此时同一个 token 的 H 个头在逻辑上相邻，再 reshape 合并成 E。NumPy 会在 reshape 非连续数组时自动复制（相当于 PyTorch 的 `.contiguous()`）。
3. `np.max(x, axis=-1)` 会把最后一维归约掉，形状变成 `(2, 4, 8)`；与 `(2, 4, 8, 8)` 广播时**从右对齐**，补成 `(1, 2, 4, 8)`，第 2 轴 `2 vs 4` 不兼容，本例会直接报错（本机验证：`operands could not be broadcast together with shapes (2,4,8,8) (2,4,8)`）。更危险的是二维方阵 `(T, T)` 的情形：`(T,)` 会被悄悄广播到最后一维，减去的是"每列"的最大值、除以的是错位的行和，不报错，但每行之和不再为 1（本机 8×8 实测前三行之和为 1.776、1.136、0.894）。`keepdims=True` 保留长度为 1 的轴，得到 `(2, 4, 8, 1)`，才能按行正确广播。减去最大值是为了防止 `exp` 溢出，不改变 softmax 结果（下一节数值稳定性会详细讲）。

### Q12 — 参考回答要点

- **view**：只改 shape/stride 元数据，返回共享内存的视图，要求新形状能用原 strides 表达；**reshape**：能做 view 时返回视图，做不到时自动复制一份——语义上"总能成功"，但你不确定它是否共享内存。
- **transpose / permute**：交换 / 重排轴，同样只改 strides，结果通常不再是行优先连续；**contiguous**：如果不连续，就按当前逻辑顺序复制成一块连续内存。
- **view 失败的典型场景**：对转置 / permute 后的张量 `view` 成需要合并"内存上不相邻的轴"的形状，例如 multi-head 合并时的 `x.transpose(1, 2).view(B, T, D)`。修法：`x.transpose(1, 2).contiguous().view(B, T, D)` 或直接 `reshape`。
- **加分点**：区分"共享内存"带来的副作用（原地修改视图会改到原张量）；知道 `x[:, ::2]` 这类切片也是视图（代码中 strides 从 `(32, 8)` 变为 `(32, 16)`）。
- **常见误区**：以为 reshape 和 transpose 可以互相替代——二者形状可能一样，但元素排列完全不同。

### Q13 — 参考回答要点

- **规则**：从最右侧的维度开始对齐；每一对维度要么相等，要么其中一个为 1（被"拉伸"）；维数少的一方在左边补 1；否则报错。结果每一维取两者的最大值。广播不会真的复制数据（stride 为 0 的虚拟扩展）。
- **静默 bug 示例**：回归任务中 `y_pred` 形状 `(B, 1)`、`y` 形状 `(B,)`，`(y_pred - y) ** 2` 广播成 `(B, B)`，loss 不报错但完全错误（本机 `np.zeros((4,1)) - np.zeros(4)` 得到 `(4, 4)`）；另一个是上题中对 `(T, T)` 方阵做 softmax 却忘了 `keepdims`。
- **防范**：关键位置加 `assert x.shape == (B, D)`；loss 前统一用 `squeeze(-1)` 或 `reshape(-1)` 对齐；用 einops 写带名字的重排；单测里用不相等的维度（如 T≠S、B≠D）以便错误尽早暴露。
- **加分点**：提到 PyTorch 损失函数在形状不一致时可能只给 warning；把"所有维度选不同的数字"作为写测试的习惯。

### Q14 — 参考回答要点

- **读法**：逗号分隔各输入的轴标签，`->` 右边是输出；输出里出现的字母保留，只在输入里出现的字母被求和；同一个输入里重复的字母取对角线（`ii->i`），只有一个输入且无求和就是转置/重排（`ij->ji`）。
- **优点**：一行表达"转置 + 乘 + 求和 + 重排"，形状语义写在字符串里，可读性强（`bhtd,bhsd->bhts` 一眼看出 d 被收缩）；能写 `matmul` 难以直接表达的运算（双线性型 `i,ij,j->`、批量外积 `bi,bj->bij`）。
- **缺点**：字符串里写错一个字母可能仍能运行出错误结果；某些实现下比直接调用 BLAS 的 matmul 慢。
- **计算顺序**：三个及以上操作数时，先收缩哪两个会极大影响计算量和中间张量大小（类似矩阵链乘法）。NumPy 的 `np.einsum` 默认 `optimize=False`（本机签名可查），对多操作数表达式可传 `optimize=True` 或 `'optimal'` 让它搜索收缩路径。
- **加分点**：能估算 einsum 计算量 = 所有字母大小之积。

### Q15 — 参考回答要点

设 B=16、H=12、T=512、D=768、D_head=64：

| 步骤 | 形状 |
|------|------|
| 输入 X | `(16, 512, 768)` |
| Q/K/V 投影 `X @ W_q` | `(16, 512, 768)` |
| 拆头 reshape | `(16, 512, 12, 64)` |
| 转置 | `(16, 12, 512, 64)` |
| 分数 `QKᵀ/√64` | `(16, 12, 512, 512)` |
| softmax | `(16, 12, 512, 512)` |
| 加权求和 `weights @ V` | `(16, 12, 512, 64)` |
| 转置回来 | `(16, 512, 12, 64)` |
| 合并头 reshape | `(16, 512, 768)` |
| 输出投影 | `(16, 512, 768)` |

- **显存**：分数矩阵 `16×12×512×512` 个 float32 ≈ 192 MB（代码 `demo_ai_tensor_shapes` 的输出），softmax 后的权重再来一份。
- **T = 8192**：元素数变为 `(8192/512)² = 256` 倍，单份分数矩阵约 48 GB，单卡显存放不下，训练时还要为反向传播保存。
- **解决思路**：FlashAttention 一类方法分块（tiling）计算注意力，在片上 SRAM 里做在线 softmax，不在显存中物化完整的 T×T 矩阵；推理时配合 KV Cache 避免重复计算；还有稀疏 / 滑动窗口等注意力变体。
- **加分点**：指出计算量（`B·H·T²·D_head`）和显存都随 T 平方增长，而投影层只随 T 线性增长。

### Q16 — 参考回答要点

- **区别**：NCHW（channels-first，PyTorch 默认）同一通道的整张特征图在内存中连续；NHWC（channels-last，TensorFlow 默认）同一像素的所有通道连续。
- **何时转换**：在两个框架 / 库之间交换数据，或者把 OpenCV、PIL 读出的 `(H, W, C)` 图像喂给 PyTorch 模型时；也有为了性能主动切到 channels-last 的情况（不少 GPU 卷积内核在 channels-last 下更高效，PyTorch 提供 `memory_format=torch.channels_last`）。
- **怎么转**：`NCHW → NHWC` 用 `permute(0, 2, 3, 1)`，反过来用 `permute(0, 3, 1, 2)`（代码中 round-trip 验证为 True）。
- **注意**：permute 之后张量非连续，接 `view` 前要 `.contiguous()`；不要用 reshape 代替 permute（形状对、内容错）；布局不匹配可能不会报错，只会悄悄变慢或算错。
- **加分点**：说明"逻辑形状"和"物理内存格式"是两件事——PyTorch 的 channels_last 张量逻辑上仍是 NCHW 形状，只是 strides 不同。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 01 线性代数直觉](../../01-linear-algebra-intuition/docs/zh.md)：向量、矩阵、点积、矩阵秩。
- [阶段 01 · 02 向量、矩阵和运算](../../02-vectors-matrices-operations/docs/zh.md)：矩阵乘法、转置、逐元素运算——本节把它们推广到任意维度。

### 本节被哪些后续内容用到
- [阶段 01 · 13 数值稳定性](../../13-numerical-stability/docs/zh.md)：softmax 减最大值、log-sum-exp 等，都要在正确的轴上用 `keepdims` 归约。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：`torch.Tensor` 的 view / reshape / contiguous、autograd 都建立在本节的形状语义上。
- [阶段 04 · 02 从零实现卷积](../../../04-computer-vision/02-convolutions-from-scratch/docs/zh.md)：`(B, C, H, W)` 张量与卷积核 `(out_c, in_c, kH, kW)` 的形状对齐。
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：`QKᵀ` 的形状与 einsum 写法。
- [阶段 07 · 03 多头注意力](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：split / merge heads 的 reshape + transpose 正是本节的核心练习。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：注意力矩阵随 T² 增长的显存问题与解决方案。

### 延伸关键词
`strides / as_strided` · `contiguous vs non-contiguous` · `channels_last` · `einops (rearrange / reduce)` · `opt_einsum 收缩路径` · `keepdims` · `masked pooling` · `FlashAttention` · `named tensors`
