# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 17 节 自监督视觉——SimCLR、DINO、MAE ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，CPU 上瞬间完成） ｜ **依赖**：`torch`（`torch.nn`、`torch.nn.functional`）；无需联网、无需数据集

---

## 1. 这份代码在考察什么

三大自监督家族各取一个"最核心的零件"，用几十行代码实现并做 sanity check：

1. **对比学习（SimCLR）**：`info_nce`——把两个视图拼成 `(2N, 2N)` 相似度矩阵，屏蔽对角线，用交叉熵实现 InfoNCE。
2. **掩码重建（MAE）**：`random_mask_indices`——随机保留 25% 的 patch，其余遮住。
3. **师生蒸馏（DINO）**：`DinoHead`——student / teacher 不同温度的 softmax、teacher 输出的 centering 与 stop-gradient、centre 的 EMA 更新。
4. **用"极端情况"检验损失函数**：相同视图的损失应接近 0，随机视图的损失应很高——这是写任何损失函数时都值得养成的习惯。

> 一句话：**自监督的全部魔法都藏在"目标怎么构造、坍塌怎么避免"里**；这份代码把三种构造方式各浓缩成一个函数或类。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `info_nce(z1, z2, tau)` | 函数 | 两组 L2 归一化嵌入的 InfoNCE 损失 | SimCLR 对比损失 |
| `random_mask_indices(num_patches, mask_ratio, seed)` | 函数 | 返回排好序的可见下标和遮盖下标 | MAE 随机遮盖 |
| `DinoHead` | `nn.Module` | 共享投影层；`student()` 输出 log-softmax，`teacher()` 输出 centering + sharpening 后的 softmax；`update_centre()` 做 EMA | DINO 防坍塌机制 |
| `main()` | 演示入口 | 三段 sanity check 并打印 | — |

三个部分互不调用，是并列的三个演示。

---

## 3. 逐段精讲

### 3.1 `info_nce`：把对比学习写成一个分类问题

```python
def info_nce(z1, z2, tau=0.1):
    N, D = z1.shape
    z = torch.cat([z1, z2], dim=0)
    sim = z @ z.T / tau
    mask = torch.eye(2 * N, dtype=torch.bool, device=z.device)
    sim = sim.masked_fill(mask, float("-inf"))
    targets = torch.cat([torch.arange(N, 2 * N), torch.arange(0, N)]).to(z.device)
    return F.cross_entropy(sim, targets)
```

逐行对照讲义公式 `L_ij = −log( exp(sim(zᵢ,zⱼ)/τ) / Σ_{k≠i} exp(sim(zᵢ,z_k)/τ) )`：

| 代码 | 含义 |
|------|------|
| `z = torch.cat([z1, z2])` | `(2N, D)`：前 N 行是视图 1，后 N 行是视图 2；样本 i 的两个视图在第 i 行和第 i+N 行 |
| `z @ z.T / tau` | `(2N, 2N)` 的两两点积。输入已经 L2 归一化，点积就是余弦相似度；除以 τ 就是 softmax 的 logit |
| `torch.eye(...)` + `masked_fill(mask, -inf)` | 把对角线（每个嵌入与自己的相似度）设为 `-inf`，`exp(-inf) = 0`，对应公式中的 `k ≠ i` |
| `targets` | 第 i 行的正样本在第 i+N 列，第 i+N 行的正样本在第 i 列，所以是 `[N..2N−1, 0..N−1]` |
| `F.cross_entropy(sim, targets)` | 每一行当作一个 2N 类的分类问题，"正确类别"是正样本所在的列；自动做 log-softmax 并对 2N 行取平均 |

- **为什么用 `cross_entropy` 而不是手写 log-softmax**：它内部使用数值稳定的 log-sum-exp，`-inf` 也能被正确处理；而且两个视图互为 anchor，2N 个损失一次就算完了（对称损失）。
- **函数假设输入已经 L2 归一化**（讲义："调用前先 L2 归一化"），函数内部不再归一化。⚠️ 如果忘了归一化，点积会随向量模长增长，模型可以靠"放大模长"来降低损失，而不是学习方向上的区分。
- **`D` 解包后没有用到**：只是让形状更清晰的写法。
- **温度**：τ=0.1 是 SimCLR 的默认值。τ 越小，logit 的差距被放大得越多：对齐良好的嵌入损失更低，随机嵌入的损失更高（见第 6 节）。
- ⚠️ 简化之处：真实的 SimCLR 在 encoder 之后还有一个 MLP 投影头，损失作用在投影后的 `z` 上；下游任务使用的是投影头**之前**的表示。

### 3.2 `random_mask_indices`：MAE 的随机遮盖

```python
def random_mask_indices(num_patches, mask_ratio=0.75, seed=0):
    g = torch.Generator().manual_seed(seed)
    n_keep = int(num_patches * (1 - mask_ratio))
    perm = torch.randperm(num_patches, generator=g)
    visible = perm[:n_keep]
    masked = perm[n_keep:]
    return visible.sort().values, masked.sort().values
```

- **独立的随机数生成器**：`torch.Generator().manual_seed(seed)` 创建一个私有的 RNG，传给 `randperm`。好处是结果只由 `seed` 决定，**不影响也不受影响于**全局随机状态（`torch.manual_seed`）——讲义说的"对给定 seed 是确定的"。`manual_seed` 返回生成器本身，所以可以链式写在一行里。
- **随机排列再切分**：`randperm(196)` 是 0–195 的一个随机排列，前 `n_keep` 个作为可见、其余作为遮盖——保证两者互不重叠，并集恰好是全部 patch。
- **`sort().values`**：`Tensor.sort()` 返回一个包含 `values` 和 `indices` 的命名元组；排序只是为了打印和阅读方便，不影响集合本身。
- **196 = 14×14**：对应 224×224 图像、16×16 patch 的 ViT-B/16；遮盖 75% 后可见 49 个、遮盖 147 个。
- ⚠️ **浮点截断陷阱**：`int(num_patches * (1 - mask_ratio))` 向零截断。0.75 在二进制中能精确表示，所以没有问题；但 `random_mask_indices(100, 0.9)` 会得到 `int(9.999999999999998) = 9`，而不是 10。更稳妥的写法是 `int(round(...))`。（官方 MAE 代码也是同样的写法，换比例时要留意。）
- ⚠️ 简化之处：只为一个"样本"生成一组遮盖。真实 MAE 在 batch 内为每个样本独立遮盖：对形状 `(B, L)` 的随机噪声做 `argsort`，同时保存逆排列 `ids_restore`，供 decoder 把 token 放回原位（测验 Q10 有 NumPy 实现）。

### 3.3 `DinoHead`：centering + sharpening

```python
class DinoHead(torch.nn.Module):
    def __init__(self, in_dim=64, out_dim=128, momentum=0.9):
        super().__init__()
        self.proj = torch.nn.Linear(in_dim, out_dim)
        self.register_buffer("centre", torch.zeros(out_dim))
        self.momentum = momentum

    def student(self, x, temp=0.1):
        return F.log_softmax(self.proj(x) / temp, dim=-1)

    def teacher(self, x, temp=0.04):
        out = self.proj(x)
        return F.softmax((out - self.centre) / temp, dim=-1).detach()

    @torch.no_grad()
    def update_centre(self, teacher_out):
        self.centre.mul_(self.momentum).add_(teacher_out.mean(dim=0), alpha=1 - self.momentum)
```

- **`register_buffer("centre", ...)`**：buffer 是"模型状态但不是可训练参数"——会随 `state_dict` 保存、随 `.to(device)` 移动，但不会出现在 `parameters()` 里，优化器不会更新它。centre 正是这种需要持久化、却只靠 EMA 更新的量（BN 的 `running_mean` 也是 buffer）。
- **student**：温度 0.1，返回 `log_softmax`。用 log 形式，是为了之后计算交叉熵 `−Σ p_teacher · log p_student` 时数值稳定。
- **teacher**：
  - `out - self.centre`：**centering**，减去各维度的历史均值，防止某一维长期独大；
  - `/ 0.04`：**sharpening**，温度比 student 更低，分布更尖锐，防止输出变成均匀分布；
  - `.detach()`：**stop-gradient**，teacher 的输出只作为目标，梯度不回传。
- **`update_centre`**：`centre ← m · centre + (1 − m) · batch_mean`，`m = 0.9`（与 DINO 论文的 center momentum 一致）。`mul_` / `add_` 是原地操作，`alpha=` 参数让 `add_` 先乘系数再相加，一行完成 EMA。`@torch.no_grad()` 保证这次更新不进入计算图。
- **centre 用的是 softmax 之前的原始输出**：`main()` 里传入的是 `head.proj(feats)`，与 DINO 的做法一致——中心是在 logit 空间上做平移。
- ⚠️ **与真实 DINO 的差别**（docstring 也说明了这是玩具版本）：
  - 真实 DINO 的 student 和 teacher 是**两个**结构相同的完整网络（backbone + 3 层 MLP 头），teacher 的权重是 student 的 EMA（m ≈ 0.996）。这里两者共享同一个 `proj`，只是用不同的温度和 centering 区分；
  - 真实 DINO 用多裁剪（2 个全局视图 + 若干局部视图），teacher 只看全局视图；
  - 这里没有实现损失函数。完整的损失是 `−(teacher(v1) * student(v2)).sum(-1).mean()`，再对称地交换两个视图。

### 3.4 `main()`：三段 sanity check

```python
    torch.manual_seed(0)

    print("[info_nce]")
    z = F.normalize(torch.randn(16, 32), dim=-1)
    loss_identical = info_nce(z, z, tau=0.1).item()
    z_random = F.normalize(torch.randn(16, 32), dim=-1)
    loss_random = info_nce(z, z_random, tau=0.1).item()
    print(f"  identical pairs:  {loss_identical:.3f}  (should be low)")
    print(f"  random pairs:     {loss_random:.3f}  (should be near log(2N-1) = {torch.log(torch.tensor(31.0)):.3f})")
```

- `F.normalize(x, dim=-1)` 把每一行除以它的 L2 范数，得到单位向量。
- **两个极端**：
  - 两个视图完全相同时，正样本的余弦为 1（logit = 10），远大于随机负样本，损失应接近 0；
  - 两个视图完全无关时，正样本和负样本没有区别，损失应该很高。
- ⚠️ **提示语不准确**："should be near log(2N-1) = 3.434" 只在所有 logit 近似相等时成立。在 τ=0.1、D=32 的设定下，随机余弦相似度的波动被放大 10 倍，log-sum-exp 会明显大于 `log 31`——用 NumPy 按同样设定模拟 2000 次，均值约 4.8（见第 6 节）。更准确的说法是"随机配对的损失**至少**在 log(2N−1) 附近，且随 τ 降低而升高"。讲义练习 1 恰好要验证这一点。

```python
    print("\n[dino centring demo]")
    head = DinoHead(in_dim=64, out_dim=16)
    feats = torch.randn(64, 64)
    teacher_out = head.teacher(feats)
    print(f"  teacher output max col mean before update: {teacher_out.mean(dim=0).max().item():.3f}")
    head.update_centre(head.proj(feats))
    teacher_out_after = head.teacher(feats)
    print(f"  teacher output max col mean after update:  {teacher_out_after.mean(dim=0).max().item():.3f}")
```

- **"max col mean"** 的含义：对 64 个样本的 teacher 概率分布按维度求平均，得到每一维的"平均占比"，再取最大值。它衡量"有没有某一维独大"——若完全均匀，16 维时为 1/16 = 0.0625；若所有样本都选同一维，则接近 1。
- 更新一次 centre 之后，再用同样的特征计算 teacher 输出，观察这个指标是否下降。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| InfoNCE 写成 `(2N,2N)` 矩阵 + `cross_entropy` | 一次算完全部 2N 个对称损失，数值稳定 | 显存随 batch 平方增长；超大 batch 时需要跨 GPU 收集嵌入（all-gather） |
| 用 `-inf` 屏蔽对角线 | 精确实现 `k ≠ i` | 若某一行全为 `-inf` 会得到 NaN（这里不会发生） |
| 假设输入已归一化 | 函数职责单一 | 调用方忘记归一化不会报错；可在函数内部加 `F.normalize` 防御 |
| 遮盖用私有 `Generator` | 可复现、不污染全局 RNG | 只支持单样本；真实 MAE 用批量 argsort |
| `int()` 截断计算保留数 | 与官方 MAE 一致 | 某些比例下会因浮点误差少保留 1 个 |
| DinoHead 共享一个 `proj` | 用最少的代码展示 centering + sharpening + stop-grad | 不是真正的师生网络；没有 EMA teacher 和损失 |
| centre 用 buffer + EMA | 随模型保存、不被优化器更新 | momentum 太大会反应慢，太小会抖动 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def info_nce(z1, z2, tau=0.1)` | 不传 τ 就用 0.1 |
| 元组解包 | `N, D = z1.shape` | 一次拿到行数和维度 |
| `@` 矩阵乘与 `.T` 转置 | `z @ z.T / tau` | `(2N,D) @ (D,2N) → (2N,2N)` |
| 关键字参数 | `torch.eye(2 * N, dtype=torch.bool, device=z.device)` | 指定类型和设备，避免设备不一致 |
| `float("-inf")` | `sim.masked_fill(mask, float("-inf"))` | Python 中表示负无穷的写法 |
| 方法链 | `torch.Generator().manual_seed(seed)`、`.sort().values` | 每个方法返回对象，可以连续调用 |
| 切片 | `perm[:n_keep]`、`perm[n_keep:]`、`visible[:5]` | 取前若干个 / 剩余部分 |
| 多返回值 | `return visible.sort().values, masked.sort().values` | 返回一个元组，调用方 `visible, masked = ...` 解包 |
| 文档字符串 | `"""Toy DINO head to demonstrate ..."""` | 说明类的用途与局限 |
| 类继承与 `super()` | `class DinoHead(torch.nn.Module)`、`super().__init__()` | 必须先初始化父类，才能注册子模块与 buffer |
| 装饰器 | `@torch.no_grad()` | 整个方法内不记录梯度 |
| 原地操作（下划线结尾） | `self.centre.mul_(...).add_(..., alpha=...)` | 直接修改张量本身，不创建新对象 |
| `.item()` / `.tolist()` | `info_nce(...).item()`、`visible[:5].tolist()` | 张量转 Python 数值 / 列表 |
| f-string 格式符与内嵌表达式 | `{loss_identical:.3f}`、`{torch.log(torch.tensor(31.0)):.3f}` | 大括号里可以直接写表达式 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 确定性的部分（遮盖数量）可以直接推出；与随机数相关的数值，我用 NumPy 按完全相同的公式和设定做了模拟，下面给出的是典型范围，具体数值取决于 PyTorch 的随机数生成器：

```text
[info_nce]
  identical pairs:  0.006  (should be low)            ← 模拟：约 0.004–0.009
  random pairs:     4.8 左右  (should be near log(2N-1) = 3.434)   ← 模拟：均值约 4.80，90% 落在 4.0–5.5

[mae mask]
  visible: 49 / 196
  masked:  147 / 196
  first 5 visible indices: [5 个升序的下标，由 seed=0 的 randperm 决定]

[dino centring demo]
  teacher output max col mean before update: 约 0.13
  teacher output max col mean after update:  约 0.13（通常略低于更新前）
```

逐行解读：

- **identical pairs ≈ 0.006**：正样本的 logit 为 `1/0.1 = 10`；其余 30 个负样本的 logit 是随机余弦除以 0.1（标准差约 1.8），`exp(10)` 远大于它们之和，损失 ≈ `Σ exp(l_k) / e¹⁰` ≈ 0.006。batch 越大、温度越低，这个值越接近 0——讲义："对大 batch 和低温度接近 0"。
- **random pairs ≈ 4.8**：明显高于提示语里的 3.434（原因见 3.4）。用同样的模拟改变温度：τ=1 时均值约 3.45（接近 log 31），τ=0.5 约 3.50，τ=0.2 约 3.80，τ=0.05 约 7.75。
- **visible 49 / masked 147**：`int(196 × 0.25) = 49`。
- **first 5 visible indices**：49 个可见下标中最小的 5 个；`sort()` 之后是升序的。由于使用私有生成器，无论前面消耗了多少全局随机数，这一行的结果都只取决于 `seed=0`。
- **DINO 演示**：`nn.Linear(64, 16)` 默认初始化下，`proj(feats)` 每个输出的标准差约 0.58，除以 0.04 之后 logit 差距很大，teacher 的分布几乎是 one-hot；偏置项让少数维度更容易"赢"，所以"max col mean"约 0.13，高于均匀时的 0.0625。一次 `update_centre`（m=0.9）只把中心移向 batch 均值的 10%，按同样的初始化方式模拟 500 次，指标平均从约 0.131 降到约 0.128（约 87% 的情况下下降）；若直接减去完整的 batch 均值，则约为 0.113。所以这一段的变化很小，它展示的是机制，而不是效果。

---

## 7. 动手改一改

1. **温度扫描（讲义练习 1）**：对 `tau ∈ [0.05, 0.1, 0.2, 0.5]` 分别计算相同视图和随机视图的损失，画成曲线，验证"对齐的随 τ 降低而下降，随机的随 τ 降低而上升"。
2. **验证对角线屏蔽**：去掉 `masked_fill` 那一行，再看随机配对的损失（应接近 10）。
3. **修正遮盖数量**：把 `int(...)` 改成 `int(round(...))`，测试 `random_mask_indices(100, 0.9)` 是否返回 10 个可见下标。
4. **补全 DINO 损失**：写 `dino_loss(head, v1, v2)`，即 `−(teacher(v1) * student(v2)).sum(-1).mean()` 再加上交换视图的一项；然后循环多步，每步更新 centre，观察"max col mean"随步数的变化。
5. **（进阶，讲义练习 2）观察坍塌**：把 `proj` 拆成 student 和 teacher 两个 `Linear`，teacher 用 EMA 更新，在随机特征上训练；对比开启与关闭 centering 时 student 输出各维的方差，看关闭后是否坍塌到同一维。
6. **（进阶）批量遮盖**：按测验 Q10 实现 `(B, L)` 的批量 argsort 遮盖，并返回 `ids_restore`。

---

## 8. 常见坑

- **忘记 L2 归一化**：InfoNCE 会变成"比谁的模长大"，训练不稳定。
- **targets 写错位**：正样本应该在 `i ± N` 列；写成 `arange(2N)` 会让每一行去"预测自己"（而自己已被屏蔽为 `-inf`），损失变成无穷大。
- **teacher 没有 `detach`**：梯度流进目标，双方一起坍塌。
- **把 centre 注册成 `nn.Parameter`**：优化器会去更新它，EMA 失去意义；应该用 `register_buffer`。
- **小 batch 跑 SimCLR**：负样本太少，效果很差；选型 prompt 规定 batch < 1024 时改用 MoCo 的队列方案。
- **linear probe 时不小心更新了 encoder**：那就变成微调了，与论文的数字不可比。
