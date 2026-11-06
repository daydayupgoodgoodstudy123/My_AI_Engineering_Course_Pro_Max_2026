# 测验 · 训练循环与 Evaluation（Training Loop and Evaluation）

> **阶段 19 · 综合项目 · 第 36 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 输入/目标对齐 | 输入取 `tokens[s : s+T]`，目标取 `tokens[s+1 : s+1+T]`；交叉熵在 `(B·T, V)` 与 `(B·T,)` 上计算 |
| 2 | 一步训练的顺序 | 设置 LR → 取 batch → `zero_grad` → 前向算 loss → `backward` → `clip_grad_norm_` → `optimizer.step()` → 记录 |
| 3 | AdamW 分组 | 二维及以上的权重（线性层、embedding 表）做 weight decay；LayerNorm 的 `scale/shift` 和所有 bias 不做 |
| 4 | Warmup + cosine | 前 `warmup_steps` 步线性升到 `max_lr`，之后按余弦曲线降到 `min_lr` |
| 5 | 梯度裁剪 | 把全体参数梯度的总 L2 范数限制在 `max_norm=1.0` 以内，方向不变 |
| 6 | 留出集评估 | `evaluate_model`：`no_grad` + `eval()`，固定数量、固定种子的验证 batch，求平均 loss，结束后恢复训练状态 |
| 7 | 定性探针 | 每 `eval_every` 步用固定 prompt、独立随机数生成器采样一段 token，捕捉 loss 看不出的问题 |
| 8 | JSONL 日志 | 每步一行 `{"step", "train_loss", "lr"}`（探针步加 `val_loss`），崩溃后仍可读、可 grep、可画图 |
| 9 | 验证集必须同分布 | 本节 demo 的验证数据用不同种子生成了**另一种模式**，val loss 从 6.58 升到 7.49，高于均匀猜测的 `ln 256 ≈ 5.55`——这测的是"换了分布"，不是过拟合曲线 |
| 10 | 理论下限 | 90% 按周期重复、10% 随机替换的数据，条件熵下限约 0.876 nats；训练 loss 低于它意味着在记忆噪声 |

### 核心技能（能动手做到）

- [ ] 写出 `make_batches`，并用测试证明目标恰好是输入右移一位
- [ ] 写出 `build_param_groups` 并能列出 demo 模型中哪 10 个张量做 weight decay、哪 18 个不做
- [ ] 手算 warmup + cosine 调度在任意一步的学习率
- [ ] 判断一条训练/验证曲线反映的是正常学习、过拟合，还是"验证集分布不一致"
- [ ] 为训练循环加上 checkpoint 保存与**逐位一致**的恢复（模型、优化器、步数、数据流位置）
- [ ] 在日志中加入梯度范数、吞吐量，并据此诊断训练问题

---

## 二、基础自测（选择题）

**Q1.** `token_ids = [10, 11, 12, 13, 14, 15]`，`context_length=3`，`make_batches` 采到起点 `s=1`。这一行的输入与目标是：

- A. 输入 `[10, 11, 12]`，目标 `[11, 12, 13]`
- B. 输入 `[11, 12, 13]`，目标 `[11, 12, 13]`
- C. 输入 `[11, 12, 13]`，目标 `[12, 13, 14]`
- D. 输入 `[11, 12, 13]`，目标 `[14]`

**Q2.** demo 模型（2 层、`d_model=64`、tying）经 `build_param_groups` 分组后，下列说法正确的是：

- A. LayerNorm 的 `scale`/`shift` 和所有 bias 共 18 个张量进入不衰减组；token/位置 embedding 与 8 个线性层权重共 10 个张量进入衰减组
- B. 所有参数都进入衰减组，只是 LayerNorm 的衰减系数更小
- C. embedding 表进入不衰减组，因为它是查表而不是矩阵乘法
- D. `lm_head.weight` 会作为单独的张量再出现一次，进入衰减组

**Q3.** 默认 `TrainConfig`（`warmup_steps=10, num_steps=80, max_lr=3e-3, min_lr=3e-4`）下，`cosine_with_warmup` 的值，正确的是：

- A. 第 0 步为 0，第 10 步为 3e-3
- B. 第 9 步为 2.7e-3，第 10 步才达到峰值
- C. 最后一步（第 79 步）恰好等于 `min_lr`
- D. 第 0 步为 3e-4，第 9 步已达峰值 3e-3，第 79 步约为 3.01e-4，略高于 `min_lr`

**Q4.** demo 输出中 val loss 依次为 6.58、7.53、7.32、7.49，**高于**随机初始化时的约 5.55。最根本的原因是：

- A. 学习率太大导致训练发散
- B. 验证 token 用 `seed=2` 生成，基础模式与训练集（`seed=1`）完全不同；模型越自信地预测训练模式，在另一种模式上的交叉熵就越高
- C. `evaluate_model` 没有关闭 dropout
- D. 验证 batch 每次都不一样，噪声太大

**Q5.** demo 打印 `model params : 118,528 (untied count)`。这个标签：

- A. 是错的——`model.parameters()` 对共享参数去重，118,528 是 **tied** 的参数量；untied 应为 134,912
- B. 是对的，因为 `sum(p.numel() for p in ...)` 不去重
- C. 是对的，因为 demo 的 `ModelConfig` 关闭了 tying
- D. 无法判断

**Q6.** 关于 `evaluate_model` 与它在 `train` 中的调用方式，正确的是：

- A. 它在评估时会更新模型参数
- B. 每次评估都从验证集取不同的随机 batch，以覆盖更多数据
- C. 它被 `@torch.no_grad()` 装饰、切到 `eval()`、只在原来处于训练模式时恢复 `train()`；`train` 每次探针都用 `seed=cfg.seed+1` 新建验证 loader，所以每次评估用的是同一组 batch
- D. 它返回所有验证 batch 的 loss 之和

**Q7.** 我们在 demo 中记录了 `clip_grad_norm_` 的返回值：80 步里有 78 步的梯度总范数大于 1（最大约 2.72）。下列说法正确的是：

- A. 梯度裁剪只在 loss 出现尖峰时才会生效
- B. 裁剪会把每个参数的梯度分别截断到 [−1, 1]
- C. 这说明训练已经发散
- D. 小模型训练早期梯度范数常大于 1，此时裁剪几乎每步都触发；它把整个梯度向量等比例缩小到范数 1，方向不变（对 Adam 这种按坐标归一化的优化器影响相对有限）

**Q8.** 讲义称 JSONL 日志让你"可以通过读取最后一步来恢复训练"。对照本节 `train` 的实现，正确的是：

- A. 本节已经实现了断点续训
- B. `train` 开始时会删除已有的日志文件，也不保存模型/优化器状态，所以目前**不能**续训；要续训还需要 checkpoint（讲义练习 4）
- C. JSONL 文件里保存了模型权重
- D. 只要不删日志就能续训

---

## 三、动手 / 代码题

**Q9.** 修正 demo 的验证集，让它与训练集**同分布但不重叠**。写出修改，并预测/验证修改后 val loss 的走势。

**Q10.** 计算题。`_synthetic_byte_tokens` 生成的数据中，每个位置以 90% 概率是周期为 32 的固定模式，以 10% 概率被替换为 `[0, 256)` 上的均匀随机 token（替换值也可能恰好等于原值）。

1. 假设模型完美掌握了模式、噪声完全不可预测，下一个 token 的交叉熵下限是多少？
2. 在 Q9 的同分布实验中，第 79 步训练 loss 为 0.586、val loss 为 1.301。你如何解读？

**Q11.** 讲义练习 4：为训练循环加入 checkpoint 与 `resume_from`。要求"跑 40 步 → 保存 → 恢复 → 再跑 40 步"与"一口气跑 80 步"的每步 loss **逐位相同**。写出需要保存的状态与恢复步骤，并说明哪一步最容易被遗漏。

**Q12.** 讲义练习 1：为 `build_param_groups` 写单元测试。除了已有的三个测试，你还会断言哪些性质？写出测试代码。

---

## 四、面试高频题

**Q13.**（基础必考）写出一个标准 LLM 训练 step 的伪代码，并说明 `zero_grad`、`backward`、`clip_grad_norm_`、`step`、学习率调度的顺序为什么不能乱。

**Q14.**（原理深挖）AdamW 和"Adam + L2 正则"有什么区别？为什么 LayerNorm 参数和 bias 通常不做 weight decay？embedding 要不要做？

**Q15.**（原理深挖）为什么 LLM 训练普遍使用"线性 warmup + cosine 衰减"？warmup 解决的是什么问题？

**Q16.**（工程实践）如何设计一个可信的验证集与评估流程？val loss 与 perplexity 是什么关系？val loss 高于 `ln V` 说明什么？

**Q17.**（场景设计）你在看一条训练曲线：①train loss 持续下降、val loss 上升；②loss 突然尖峰后恢复；③loss 一直不动；④loss 变成 NaN。分别可能是什么原因？你需要日志里有哪些字段才能诊断？

---

## 五、参考答案与解析

### Q1 — 答案：C

```python
        inputs = torch.stack([token_ids[s : s + context_length] for s in starts.tolist()])
        targets = torch.stack(
            [token_ids[s + 1 : s + 1 + context_length] for s in starts.tolist()]
        )
```

`s=1` 时输入为下标 1–3 即 `[11, 12, 13]`，目标为下标 2–4 即 `[12, 13, 14]`：每个位置的目标是它的下一个 token，一行提供 3 个训练信号。A 起点错了；B 没有错位，模型会学"预测自己"（讲义："converges to zero loss while learning nothing useful"）；D 只给了最后一个位置的目标，浪费了其他位置。

### Q2 — 答案：A

规则是 `param.dim() < 2` 或名字以 `.bias/.shift/.scale` 结尾 → 不衰减。我们实测：衰减组 10 个张量共 116,736 个元素（`tok_embed`、`pos_embed`、两层各 4 个线性权重），不衰减组 18 个张量共 1,792 个元素（5 个 LayerNorm 各 2 个 + 8 个线性层 bias）。B 错：不衰减组的 `weight_decay` 为 0，不是更小；C 错：embedding 是二维矩阵，按讲义"matrix shaped tensors (linear weights, embedding tables) get decay"；D 错：`named_parameters()` 对共享参数去重，tied 的 `lm_head.weight` 不会重复出现（否则同一参数会被优化器更新两次）。

### Q3 — 答案：D

```python
    if step < warmup_steps:
        return max_lr * (step + 1) / max(warmup_steps, 1)
    progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
```

实测：第 0 步 3e-4（`3e-3 × 1/10`，与 `losses.jsonl` 第一行一致），第 9 步 3e-3，第 10 步 3e-3（progress=0），第 45 步 1.65e-3（正好一半），第 79 步 3.01e-4。因为 `(step+1)` 的写法，第 0 步就不是 0（A 错），第 9 步已到峰值（B 错）；最后一步的 progress 是 `69/70` 而不是 1，所以没有精确到 `min_lr`（C 错）——测试 `test_decay_reaches_min_lr_at_end` 用的是 `step=100=total_steps`，训练循环永远到不了这一步。

### Q4 — 答案：B

`_synthetic_byte_tokens(..., seed=1)` 与 `seed=2` 的 32 个基础 token 完全不同（实测只有 3 个 token 值重合）。模型在训练中越来越确定"下一个是训练模式中的那个 token"，遇到验证序列时给正确答案分配的概率比均匀分布还低，交叉熵因此高于 `ln 256`。初始化时 val loss 实测 5.554（≈ `ln 256 = 5.545`）。A 错：train loss 正常降到约 1.07；C 错：`evaluate_model` 调用了 `model.eval()`，而且 demo 的 `dropout=0.0`；D 错：每次评估用同一个种子，batch 是固定的。讲义说"Reporting the held out loss next to the training loss is how you spot overfitting"，但这个 demo 的验证集不是"留出的同分布数据"，曲线无法用来判断过拟合；代码注释"the eval loss should drop visibly during the demo"与实际输出相反。

### Q5 — 答案：A

`nn.Module.parameters()` 默认对共享参数去重，因此 `sum(p.numel() for p in model.parameters())` 得到的是 tied 的参数量：`256×64 + 32×64 + 2 × 49,984 + 128 = 118,528`。untied 时还要再加一份 `256 × 64 = 16,384`，即 134,912。这一行还额外构造了一个 `GPTModel` 只为了计数，顺带消耗了全局随机数。

### Q6 — 答案：C

```python
@torch.no_grad()
def evaluate_model(model, val_loader, max_batches):
    was_training = model.training
    model.eval()
    ...
    if was_training:
        model.train()
    return total / max(count, 1)
```

测试 `test_evaluate_keeps_model_in_eval_when_called_during_eval` 专门验证了"原来是 eval 就保持 eval"。`train` 中每次探针都 `make_batches(val_tokens, ..., seed=cfg.seed + 1)`，生成器重新播种，所以 4 个验证 batch 每次相同——这正是讲义"Eval batches drawn from a fixed slice"想要的可比性（讲义说"sliced once at script start"，代码是用固定种子重新采样，效果等价）。A 错（no_grad、无 step）；B 错；D 错，返回的是平均值。

### Q7 — 答案：D

`clip_grad_norm_` 先计算所有参数梯度拼成的大向量的 L2 范数 `‖g‖`，若大于 `max_norm`，就把所有梯度乘以 `max_norm / ‖g‖`；返回值是裁剪**前**的范数。demo 中前 5 步范数为 2.72、2.65、2.02、1.66、1.75，80 步中 78 步被裁剪（实测）。这并不意味着发散（C 错），只是小模型 + 平均 loss 下的正常尺度；也说明 `max_norm=1.0` 并非对所有设置都"几乎不触发"。B 描述的是 `clip_grad_value_`。加分点：AdamW 的更新量 `m/√v` 对梯度的整体缩放不太敏感，所以每步都裁剪对它的影响比对 SGD 小，但会改变一阶/二阶矩中不同步之间的相对权重。

### Q8 — 答案：B

```python
    if log_path.exists():
        log_path.unlink()
```

`train` 一开始就删掉旧日志，循环中也只写 loss 与 LR，不保存模型和优化器状态，所以无法续训。JSONL 只是"训练的证词"，续训还需要 checkpoint（Q11）。

### Q9 — 参考答案

把同一条合成序列切成前后两段：

```python
    full_tokens = _synthetic_byte_tokens(length=5120, vocab_size=mcfg.vocab_size, seed=1)
    train_tokens = full_tokens[:4096]
    val_tokens = full_tokens[4096:]
```

两段共享同一个周期模式，但噪声位置不同，且没有任何 token 重叠，符合"留出集"的定义。实测（其余设置与 demo 相同）：

| step | train_loss | val_loss |
|------|-----------|----------|
| 19 | 2.755 | 2.754 |
| 39 | 1.678 | 1.524 |
| 59 | 1.293 | 1.337 |
| 79 | 0.586 | 1.301 |

val loss 先随训练下降，后期趋于平稳，而 train loss 继续下降——这才是可以用来判断"开始过拟合"的曲线。对比原 demo：val loss 一路升到 7.49。真实语料中常见的做法是按文档切分（例如 90/10），而不是按 token 随机抽取，避免同一篇文档的片段同时出现在两边。

### Q10 — 参考答案

1. 若模式下一个 token 为 `c`：它出现的概率 `p = 0.9 + 0.1/256 ≈ 0.9004`（噪声替换也可能恰好是 c），其余 255 个 token 各 `q = 0.1/256`。熵 `H = −p ln p − 255 · q ln q ≈ 0.876 nats`（已用 Python 计算）。这是在"噪声不可预测"前提下任何模型都无法超越的期望交叉熵。
2. val loss 1.301 高于下限，合理（还没学完，或上下文中的噪声 token 干扰了判断）。train loss 0.586 **低于**理论下限：训练集只有 4096 个 token、模型有约 11.8 万参数，噪声在训练流中的位置是固定的，模型可以把"哪段上下文后面跟着哪个噪声 token"记下来——这就是记忆/过拟合。需要注意单步 train loss 只基于一个 batch（4×32 个目标），本身也有波动，应该看多步平均。讲义的观点"train loss 和 held-out loss 一起看才能发现过拟合"在这里体现得很清楚。

### Q11 — 参考答案

需要保存与恢复的状态：

```python
# 保存（例如每 eval_every 步）
torch.save({"step": step + 1,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict()}, ckpt_path)

# 恢复
ck = torch.load(ckpt_path)
model.load_state_dict(ck["model"])
optimizer.load_state_dict(ck["optimizer"])
start = ck["step"]
train_loader = make_batches(train_tokens, cfg.batch_size, cfg.context_length, seed=cfg.seed)
for _ in range(start):            # 快进数据流到相同位置
    next(train_loader)
for step in range(start, cfg.num_steps):
    lr = cosine_with_warmup(step, ...)   # LR 由 step 计算，自然对齐
    ...
```

我们实测：一口气跑 80 步与"40 步 + 保存 + 恢复 + 40 步"的 80 个 loss **完全相同**（最大差 0.0）；如果恢复时**不快进数据流**（直接从新的 loader 开始），loss 序列就不同了。所以最容易遗漏的是**数据加载器的位置/随机数状态**（以及 dropout 用到的全局 RNG 状态，demo 中 dropout 为 0 才没有影响）。其他要点：

- LR 调度在本节由 `step` 纯函数计算，只要保存 `step` 即可；若用 PyTorch 的 `LRScheduler` 对象，还要保存它的 `state_dict()`；
- 日志改为追加模式，恢复时不要删除旧文件，可以先截断到 `start` 步再追加；
- `state_dict()` 中 `tok_embed.weight` 与 `lm_head.weight` 两个键都在，加载进同样开启 tying 的新模型即可保持共享（实测）。

### Q12 — 参考答案

```python
class ParamGroupCompletenessTests(unittest.TestCase):
    def test_groups_partition_all_params_exactly_once(self):
        model = GPTModel(_model_cfg())
        decay, no_decay = build_param_groups(model, weight_decay=0.1)
        d = {id(p) for p in decay["params"]}
        n = {id(p) for p in no_decay["params"]}
        all_ids = {id(p) for p in model.parameters()}
        self.assertEqual(d & n, set())              # 不重叠
        self.assertEqual(d | n, all_ids)            # 不遗漏
        self.assertEqual(len(decay["params"]), len(d))   # 组内无重复（tying）

    def test_embeddings_decay_and_weight_values(self):
        model = GPTModel(_model_cfg())
        decay, no_decay = build_param_groups(model, weight_decay=0.1)
        d = {id(p) for p in decay["params"]}
        self.assertIn(id(model.tok_embed.weight), d)
        self.assertIn(id(model.pos_embed.weight), d)
        self.assertEqual(decay["weight_decay"], 0.1)
        self.assertEqual(no_decay["weight_decay"], 0.0)

    def test_every_no_decay_param_is_1d(self):
        model = GPTModel(_model_cfg())
        _, no_decay = build_param_groups(model, weight_decay=0.1)
        self.assertTrue(all(p.dim() == 1 for p in no_decay["params"]))
```

关键性质：**两组构成全体参数的一个划分**（不重叠、不遗漏、tied 参数只出现一次）；embedding 进入衰减组；组的 `weight_decay` 值正确；不衰减组都是一维张量。讲义练习 1 写的函数名是 `weight_decay_groups()`，代码里实际叫 `build_param_groups`。

### Q13 — 参考回答要点

```text
for step in range(total_steps):
    lr = schedule(step); set lr for all param groups
    x, y = next(train_loader)
    optimizer.zero_grad(set_to_none=True)
    loss = cross_entropy(model(x).flatten(0, 1), y.flatten())
    loss.backward()
    grad_norm = clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    log(step, loss, lr, grad_norm, tokens_per_sec)
    if step % eval_every == 0: evaluate(); sample()
```

- `zero_grad` 必须在 `backward` 之前：PyTorch 梯度默认**累加**，不清零会把上一步的梯度混进来（梯度累积正是有意利用这一点）。
- 裁剪必须在 `backward` 之后、`step` 之前：要裁剪的是本步完整的梯度。
- 学习率要在 `step` 之前设置好：本节在每步开头写入 `param_groups`。
- 混合精度时，还要在裁剪前 `scaler.unscale_(optimizer)`（第 45 节）。
- 加分点：日志中同时记录裁剪前的梯度范数，它是发现不稳定的最早信号之一。

### Q14 — 参考回答要点

- **Adam + L2**：把 `λ·w` 加进梯度，再经过 Adam 的自适应缩放 `m/√v`。梯度大的参数被除以大的 `√v`，正则效果被削弱，不同参数受到的正则强度不一致。
- **AdamW**：解耦的 weight decay，更新时直接 `w ← w − lr·λ·w`，与梯度的自适应缩放无关，效果更可预测。PyTorch 的 `torch.optim.AdamW` 就是这种实现（本节 `betas=(0.9, 0.95)` 是 LLM 训练中常见的设置）。
- **LayerNorm 的 scale/shift**：decay 会把 `scale` 拉向 0，削弱归一化后的输出幅度，破坏归一化的作用（讲义："slowly drives the scale to zero and breaks normalization"）；它们参数很少，也几乎不会导致过拟合。
- **bias**：一维、数量少，正则收益很小；讲义认为对 bias 做 decay"数学上无害但浪费计算"。
- **embedding**：本节和讲义都对 embedding 表做 decay；实践中两种做法都有。顾虑是罕见 token 的行几乎得不到梯度，却每一步都被 decay 拉向 0。
- 加分点：分组规则用"维度 < 2"比按名字匹配更稳健；按名字匹配时要防止把形如 `xxx.scale` 的二维参数误分。

### Q15 — 参考回答要点

- **warmup 的作用**：训练开始时 Adam 的二阶矩估计 `v` 只来自很少几步，噪声大，更新幅度不可靠；参数也处在随机初始化附近，大步长容易把模型推到坏区域（post-LN 结构尤其敏感，第 34 节）。用几百到几千步把 LR 从很小升到峰值，让优化器状态"热身"（讲义："so the optimizer state has time to populate"）。
- **cosine 衰减**：前期保持较高 LR 快速下降，后期 LR 平滑地降到很小，让模型在低噪声下精细收敛；相比阶梯衰减没有突变。
- **min_lr**：常设为峰值的 10% 左右（讲义练习 3），避免最后阶段 LR 过小、训练基本停滞。本节默认 `min_lr = max_lr / 10`。
- 加分点：也有 WSD（warmup-stable-decay）等变体，便于在训练中途决定何时结束；本节实现的边界细节（第 0 步就是 `max_lr/warmup`、最后一步没到 `min_lr`）见 Q3。

### Q16 — 参考回答要点

- **数据**：验证集必须与训练集**同分布、不重叠**；按文档或时间切分，防止泄漏；对去重后的语料再切分。本节 demo 的反例：验证集是另一种模式（Q4）。
- **可比性**：固定的验证 batch（固定种子或预先切片）、固定的 batch 数、`eval()` + `no_grad`，不同实验之间才能比较（讲义 "Eval batches drawn from a fixed slice"）。
- **perplexity**：`PPL = exp(平均交叉熵)`。均匀猜测时 loss = `ln V`，PPL = V；本节 val loss 7.49 对应 PPL ≈ 1790，比"在 256 个 token 里瞎猜"还差。
- **val loss > ln V**：模型不仅没学到验证分布，还对错误答案非常自信——分布偏移、数据泄漏方向反了、或标签错位。
- **超出 loss 的评估**：定性采样（本节的 `generate_and_print_sample`）、下游任务基准（阶段 10 第 10 节、第 41、49 节）。
- 加分点：评估频率与成本的权衡——大模型训练中验证只用固定的少量 batch，定期再跑完整评测。

### Q17 — 参考回答要点

| 现象 | 可能原因 | 需要的日志/检查 |
|------|---------|---------------|
| train 降、val 升 | 过拟合（数据少、训练太久、正则不足）；或验证集分布不同（本节 demo） | 同时记录 `train_loss`、`val_loss`；检查验证集的构造方式 |
| 尖峰后恢复 | 异常 batch、LR 过大、数值不稳定 | 每步 `grad_norm`、`lr`、batch 来源（数据索引）；必要时跳过该 batch |
| loss 不动 | LR 太小或太大（第 34 节 post-LN 在 1e-3 卡在 `ln V`）、梯度没有传到参数（`requires_grad`、`detach`）、目标没有错位 | 每层梯度范数、参数更新量与参数范数之比、初始 loss 是否 ≈ `ln V` |
| NaN | LR 过大、fp16 溢出、`-inf` 整行屏蔽、除零 | `grad_norm` 何时变成 inf；开启 `torch.autograd.detect_anomaly()` 定位 |

- 通用日志字段：`step`、`train_loss`、`val_loss`、`lr`、`grad_norm`（裁剪前）、`tokens/sec`（讲义练习 5）、样本文本、checkpoint 路径。
- 加分点：把 JSONL 读入 pandas，用滑动平均画 loss 曲线，并把 LR 曲线画在同一张图上对照。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 31 使用滑动窗口构建分词后的数据集](../../31-tokenized-dataset-sliding-window/docs/zh.md)：输入/目标错位一位的数据构造。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：本节训练的模型（代码在本地重新实现了一遍）。
- [阶段 03 · 05 Loss Functions](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：Adam 与 AdamW。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：学习率调度。

### 本节被哪些后续内容用到
- [阶段 19 · 37 加载预训练 Weights](../../37-loading-pretrained-weights/docs/zh.md)：用同样的评估函数比较自训练与预训练模型。
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：本节调度函数的深入版本。
- [阶段 19 · 45 Gradient Clipping（梯度裁剪）与 Mixed Precision（混合精度）](../../45-gradient-clipping-amp/docs/zh.md)：裁剪与混合精度的配合。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：在本节循环中加入梯度累积。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：Q11 的完整工程化实现。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：交叉熵之外的评估。

### 延伸关键词
`next-token prediction` · `AdamW` · `decoupled weight decay` · `warmup + cosine` · `clip_grad_norm_` · `held-out evaluation` · `perplexity` · `JSONL logging` · `checkpoint / resume` · `tokens per second` · `overfitting` · `distribution shift`
