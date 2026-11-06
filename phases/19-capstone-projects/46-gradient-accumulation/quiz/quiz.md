# 测验 · Gradient Accumulation（梯度累积）（Gradient Accumulation）

> **阶段 19 · 综合项目 · 第 46 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/test_main.py](../code/test_main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)（测试并入该讲解第 9 节）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 有效 batch 恒等式 | `effective_batch = micro_batch × accum_steps × world_size`；单机时 world_size = 1 |
| 2 | 梯度为什么能"累积" | PyTorch 的 `backward()` 默认把梯度**加**到 `param.grad` 上，只要不清零，多次反向的梯度就会求和 |
| 3 | loss 缩放 | 每个 micro-batch 的 loss 先除以 `accum_steps` 再反向；不除的话梯度方向正确但大小是 N 倍，SGD 的一步也大 N 倍 |
| 4 | 等价性 | 当 loss 是逐 micro-batch 取平均、且各 micro-batch 大小相同时，累积梯度与一次全 batch 反向的梯度只差浮点求和顺序（本节实测最大差 7.45e-9） |
| 5 | 优化器只在窗口末尾走一步 | `optimizer.step()`、调度器、Adam 的矩估计和 step 计数都按"有效步"推进，而不是按 micro-batch |
| 6 | sync-on-last-step | 多卡 DDP 中，非最后的 micro-batch 放进 `no_sync()` 跳过梯度 all-reduce，最后一个 micro-batch 一次性归约累积好的梯度；N 个 micro-batch 只通信 1 次 |
| 7 | 代价 | 用时间换显存：每个 micro-batch 仍要一次前向一次反向，`accum_steps` 翻倍，每个优化器步的耗时也约翻倍 |
| 8 | 吞吐曲线 | 固定 micro-batch 增大 accum，样本/秒先升后平——每个优化器步的固定开销被摊薄，之后受硬件上限约束 |
| 9 | 与学习率的关系 | 有效 batch 变大通常需要相应调大学习率并配合 warmup（讲义提到 2017 年起讨论的 linear scaling rule） |
| 10 | 三个旋钮的分工 | micro-batch 由显存决定、有效 batch 由学习率/调度决定、`accum_steps` 是二者之间唯一可在运行时调整的桥 |

### 核心技能（能动手做到）

- [ ] 写出"缩放 loss → 累积反向 → 窗口末尾 step → 下个窗口前清零"的完整循环
- [ ] 用两个同种子模型验证累积梯度与全 batch 梯度一致，并解释容差来源
- [ ] 指出 micro-batch 大小不等、按 token 求平均、含 BatchNorm 等情形下"除以 N"不再严格等价，并给出修正
- [ ] 把梯度累积与第 44 节的调度、第 45 节的 GradScaler 和梯度裁剪正确组合（unscale 与裁剪各只做一次）
- [ ] 在 DDP 中用 `no_sync()` 跳过非最后 micro-batch 的通信，并能计算节省的 all-reduce 次数
- [ ] 读懂吞吐扫描表：样本/秒、每步中位耗时、同步次数分别说明什么

---

## 二、基础自测（选择题）

**Q1.** 8 张卡做数据并行，每张卡 micro-batch 为 4，`accum_steps = 16`。有效 batch 是多少？

- A. 64
- B. 512
- C. 128
- D. 32

**Q2.** 用 SGD 训练，4 个等大 micro-batch 累积，但**忘了**把 loss 除以 4。与正确做法相比：

- A. 梯度方向错误，模型会朝错误方向更新
- B. 没有任何区别，PyTorch 会自动平均
- C. 梯度变成 1/4，更新太小
- D. 累积梯度是正确值的 4 倍，SGD 这一步的位移也是 4 倍

**Q3.** 使用 AdamW 和本节的 `train_one_optimizer_step`，跑了 3 个有效步、每步 4 个 micro-batch。之后 AdamW 内部某个参数的 `state["step"]` 是：

- A. 3
- B. 12
- C. 4
- D. 0，因为累积期间不会创建状态

**Q4.** 在多卡 DDP 中把非最后的 micro-batch 包进 `model.no_sync()`，目的是：

- A. 让各卡的随机种子保持同步
- B. 防止梯度被累积
- C. 跳过这些反向结束时的梯度 all-reduce，只在最后一个 micro-batch 归约一次累积好的梯度，节省 N−1 次通信
- D. 关闭 autograd 以节省显存

**Q5.** 一个 16 样本的 batch 被切成大小为 10 和 6 的两个 micro-batch，每个用 `CrossEntropyLoss()`（默认 `mean`）再除以 2 后反向。与全 batch 反向相比：

- A. 完全等价，差异只在浮点误差量级
- B. 只有参数更新不同，梯度相同
- C. 不等价：每个样本的权重变成 `1/(2·10)` 或 `1/(2·6)`，而不是统一的 `1/16`；本节模型上实测梯度最大差约 0.037
- D. 会直接报错，因为 micro-batch 必须等大

**Q6.** 运行 `python3 main.py --no-write`，扫描表中 5 个配置的 `loss` 都在 2.776–2.780 之间。最合理的解释是：

- A. `synthetic_batch` 的标签是均匀随机的，输入与标签无关，模型无规律可学，交叉熵停留在 `ln 16 ≈ 2.7726` 附近
- B. 学习率太小，25 步还没来得及下降
- C. 梯度累积导致梯度被抵消
- D. 损失没有除以 `accum_steps`，被放大了

**Q7.** 在 `run_config` 中，`sync_calls` 统计的是什么？以 `accum=16`、`num_steps=25` 为例，它的值是多少？

- A. 所有 micro-batch 的反向次数，400
- B. `no_sync_context` 被进入的次数，375
- C. 优化器 step 次数乘以 world_size，25 × 8
- D. 进入"最后一个 micro-batch"分支（即会触发同步）的次数，每个有效步 1 次，共 25

**Q8.** 扫描表中，固定 micro-batch = 4，`accum` 从 1 增加到 16，样本/秒从约 5,900 升到约 12,200 后趋于平缓。主要原因是：

- A. 更大的有效 batch 让单个样本的前向变快
- B. 每个优化器步都有固定开销（清零、算梯度范数、`optimizer.step()` 等），accum 越大，这部分开销被越多样本摊薄；摊薄之后受硬件计算上限约束
- C. `no_sync_context` 在单进程中跳过了真实的通信
- D. 交叉熵在大 batch 上计算更便宜

---

## 三、动手 / 代码题

**Q9.** 讲义练习 2：添加"不做缩放"的错误变体，比较第 1 步后的参数差异。

使用 `equivalence_check` 的默认配置（`in_dim=32, hidden=48, out_dim=8, big_batch=16, accum_steps=4, lr=0.1, seed=7`），分别用 SGD 和 AdamW（lr=0.1）：

1. 写出"不除以 `accum_steps`"的累积代码，并预测 SGD 下累积梯度与全 batch 梯度的比值。
2. 实测 SGD 与 AdamW 下"错误变体 vs 全 batch"的最大参数差分别是多少量级？为什么 AdamW 下这个 bug 的影响小得多？
3. 既然 AdamW 对这个 bug 不敏感，是不是就可以不除了？举出至少两个仍然会出问题的场景。

**Q10.** 语言模型训练中，每个 micro-batch 的有效 token 数（去掉 padding 后）往往不同。下面的写法有什么问题？请给出修正版本。

```python
for x, y in micro_batches:                    # y 中 padding 位置为 -100
    logits = model(x)
    loss = F.cross_entropy(logits.view(-1, V), y.view(-1), ignore_index=-100)
    (loss / accum_steps).backward()
optimizer.step()
```

**Q11.** 把本节的累积与第 44、45 节组合：用 `GradScaler`（CUDA、FP16）、全局范数裁剪 `max_norm=1.0`、余弦调度 `schedule.lr(step)`。请写出一个有效步的代码，并回答：

1. `scaler.unscale_` 与裁剪应该在每个 micro-batch 后做，还是只在窗口末尾做一次？
2. 调度器的 step 计数应该按什么推进？
3. 如果某个窗口的梯度出现 Inf 被 GradScaler 跳过，这个窗口的 micro-batch 怎么处理？

**Q12.** 关于本节的扫描与输出文件：

1. 仓库中提交的 `outputs/accum-curve.json` 只有 3 个点、每点 `steps = 8`，而 `python3 main.py` 默认扫描 `1,2,4,8,16` 共 5 个点、每点 25 步。这个文件是用什么参数生成的？如何验证？
2. 直接运行 `python3 main.py`（不加 `--no-write`）会对仓库产生什么副作用？
3. 计时区间 `t0 ... wall_ms` 里包含了哪些不属于"训练"的开销？对结论有什么影响？
4. 扫描对所有有效 batch 使用同一个 `lr=0.05`，这对比较不同配置的 `avg_loss` 意味着什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是梯度累积？它解决什么问题、付出什么代价？写出核心代码。

**Q14.**（原理深挖）梯度累积在哪些情况下与"真正的大 batch"不等价？请至少列出三种，并说明如何处理。

**Q15.**（工程实践）在 DDP 多卡训练中如何实现梯度累积？请说明 `accum_steps` 的计算、`no_sync` 的使用、梯度裁剪与学习率调度放在哪里。

**Q16.**（场景设计）你只有一张卡，最多放 32 条样本，但论文配方要求有效 batch 512。你会怎么设计训练？除了梯度累积还有哪些手段可以提升 micro-batch？

**Q17.**（追问型）有效 batch 越大越好吗？把有效 batch 从 512 加到 4096，学习率要不要变？吞吐和收敛会怎样？

---

## 五、参考答案与解析

### Q1 — 答案：B

`4 × 16 × 8 = 512`。讲义 Key Terms："Effective batch — Micro batch times accum steps times data parallel world size"；"Use It"部分给出 `accumulation_steps = effective_batch // (micro_batch * world_size)`。A 漏了 world_size；C 漏了 accum 的一半；D 只算了 `micro × world_size`。

### Q2 — 答案：D

已实测：不除以 4 时，累积梯度与全 batch 梯度的比值恰为 4.0，SGD 一步后参数最大差 0.0215。讲义："Without scaling, the gradient direction is correct but the magnitude is wrong, and the optimizer step is 16 times too big."（讲义例子是 16 个 micro-batch）。A 错，方向没变；B 错，PyTorch 对梯度是**求和**而不是平均；C 方向反了。

### Q3 — 答案：A

已实测：`state["step"] = 3`。`train_one_optimizer_step` 在所有 micro-batch 反向之后只调用一次 `optimizer.step()`，所以 Adam 的一阶/二阶矩和偏差修正计数都按有效步推进。讲义："The optimizer's state (momentum buffers, Adam moments) advances once per effective step, not once per micro-batch." B 是"每个 micro-batch 都 step"的错误写法才会得到的值。

### Q4 — 答案：C

DDP 默认在每次 `backward()` 结束时 all-reduce 梯度。累积窗口中前 N−1 次反向的梯度不需要立即同步，`no_sync()` 让它们只在本地累积，最后一次反向再把累积结果一次性归约。讲义："the last micro-batch reduces the full accumulated gradient in one pass instead of paying the network cost N times." 本节单进程中 `no_sync_context` 只是空上下文（stand-in）。A、B、D 都不是它的作用。

### Q5 — 答案：C

全 batch 的 mean loss 中每个样本权重为 `1/16`；切成 10 + 6 后每个 micro-batch 内部先取平均，再除以 2：前 10 个样本权重 `1/20`、后 6 个样本权重 `1/12`。已实测：`[10, 6]` 切分的梯度最大差 0.0368、`[12, 4]` 为 0.0629，而等分的 `[4,4,4,4]`、`[8,8]`、`[2]×8` 都只有 7.45e-9。代码本身不报错（D 错），`run_config` 只是用 `assert effective_batch % accum_steps == 0` 保证了等分。

### Q6 — 答案：A

`synthetic_batch` 每步用 `torch.randn` 生成输入、用 `torch.randint(0, out_dim)` 生成**与输入无关**的标签。最优预测就是均匀分布，交叉熵为 `ln 16 ≈ 2.7726`，实际 2.776–2.780 只是在它附近波动。B 不是根本原因，标签随机时再训练多久也学不到东西；C、D 错，代码确实除了 `accum_steps`，且 `avg_loss` 记录的是**未缩放**的平均 loss。这也意味着本节扫描的 `avg_loss` 列不能用来比较不同 accum 配置的优劣。

### Q7 — 答案：D

`sync_counter[0] += 1` 只出现在 `else` 分支，也就是"最后一个 micro-batch"（或关闭 `no_sync_until_last` 时的每一个）。每个有效步恰好一次，所以 `sync_calls == steps == 25`，测试 `test_sync_calls_equal_step_count` 也断言这一点。讲义把它描述为"how many times we left the no_sync scope"，严格说是"进入同步分支的次数"。A、B 混淆了反向次数与同步次数；C 是虚构的公式。

### Q8 — 答案：B

本次实测样本/秒：`5876 → 8057 → 10321 → 11976 → 12230`，每步中位耗时 `0.59 → 0.92 → 1.46 → 2.65 → 4.81` ms，近似随 accum 线性增长但截距不为 0。每个有效步有一段与 accum 无关的固定开销：`zero_grads`、`global_grad_norm`（每参数一次 `.item()`）、`optimizer.step()`、Python 循环调度等，accum 越大摊得越薄。另外第一个配置还承担了 PyTorch 首次运行的预热开销。A 错，单样本的计算量不变；C 错，单进程根本没有通信；D 无依据。注意计时还包括了数据生成（见 Q12），且 CPU 上结果波动较大。

### Q9 — 参考答案

1. 错误变体：

```python
for cx, cy in zip(torch.split(x, micro), torch.split(y, micro)):
    loss_fn(model_wrong(cx), cy).backward()      # 没有 / accum_steps
opt_wrong.step()
```

   每个 micro-batch 的 mean loss 梯度相当于全 batch 梯度的"1/4 份 × 4"，4 份求和后正好是全 batch 梯度的 4 倍。实测比值 4.0。

2. 实测最大参数差（与全 batch 一步后的参数比较）：
   - SGD：约 **0.0215**（`lr × 3 × |g|` 量级，因为多走了 3 倍梯度）；
   - AdamW：约 **7.8e-4**，小了近 30 倍；正确缩放时 AdamW 的差异只有 3e-8。
   - 原因：Adam 第一步的更新约为 `lr · g / (|g| + ε)`，梯度整体乘 4 时分子分母同比例放大，结果几乎不变，只有当某些分量 `|g|` 小到与 ε 可比时才有差异。Adam 对梯度的整体尺度近似不变。

3. 仍然会出问题的场景：
   - **梯度裁剪**：裁剪看的是梯度绝对范数，放大 N 倍后本来不该裁的步也会被裁，裁剪后的有效步长与预期不同；裁剪阈值的语义随 `accum_steps` 改变。
   - **梯度范数日志与告警**：日志里的范数虚高 N 倍，跨配置不可比，告警阈值失效。
   - **混合精度**：放大 N 倍的梯度更容易在 FP16 中上溢，GradScaler 跳过更多步。
   - **换用 SGD/Momentum** 或 ε 较大的优化器时，bug 立刻显现。
   - 结论：始终除以 `accum_steps`，不要依赖优化器"碰巧不敏感"。

### Q10 — 参考答案

问题：`ignore_index` 下 `cross_entropy` 默认对**该 micro-batch 内有效 token 数**取平均。若四个 micro-batch 的有效 token 数分别为 1000、200、800、50，每个 token 的权重就是 `1/(4·1000)`、`1/(4·200)`…，token 少的 micro-batch 中每个 token 被放大，结果既不等于"全 batch 按 token 平均"，也会随切分方式变化（与 Q5 同理，只是这里的"大小"是 token 数）。

修正：先统计整个窗口的有效 token 总数，用 `sum` 归约再除以总数：

```python
n_tokens = sum(int((y != -100).sum()) for _, y in micro_batches)   # 窗口内总 token 数
for x, y in micro_batches:
    logits = model(x)
    loss_sum = F.cross_entropy(logits.view(-1, V), y.view(-1),
                               ignore_index=-100, reduction="sum")
    (loss_sum / n_tokens).backward()
optimizer.step()
```

这样每个 token 的权重都是 `1/n_tokens`，与一次全 batch 前向完全等价。多卡时 `n_tokens` 还需要跨卡 all-reduce 求和（或者各卡按本地 token 数归一化并接受近似）。如果所有 micro-batch 都是等长、无 padding 的打包序列，原写法才等价。

### Q11 — 参考答案

```python
optimizer.zero_grad(set_to_none=True)
for i, (x, y) in enumerate(micro_batches):
    ctx = model.no_sync() if (ddp and i < accum_steps - 1) else contextlib.nullcontext()
    with ctx:
        with torch.amp.autocast("cuda", dtype=torch.float16):
            loss = loss_fn(model(x), y) / accum_steps
        scaler.scale(loss).backward()               # 每个 micro-batch 都缩放后反向

for g in optimizer.param_groups:                    # 调度：按有效步
    g["lr"] = schedule.lr(global_step)
scaler.unscale_(optimizer)                          # 窗口末尾只做一次
grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
scaler.step(optimizer)                              # 有 inf 时内部自动跳过
scaler.update()
global_step += 1
```

1. **只在窗口末尾做一次**。`unscale_` 每个优化器每次 `update()` 之间只能调用一次（重复调用会报错），而且在中途 unscale 会让后续 micro-batch 的缩放梯度与已 unscale 的梯度混在一起。裁剪的对象是"整个有效 batch 的梯度"，中途裁剪会把每个 micro-batch 分别裁剪，改变累积结果。
2. **按有效步（优化器步）推进**。讲义 skill 文件："the learning rate schedule ticks once per effective batch"。按 micro-batch 推进会让调度以 `accum_steps` 倍的速度"烧完"。`total_steps` 也要以有效步为单位配置。
3. 整个窗口的累积梯度被丢弃（`scaler.step` 跳过 `optimizer.step()`），`scaler.update()` 把缩放因子减半；下一个窗口照常清零重新累积。是否推进 `global_step` 是一个需要明确的约定（第 45 节的代码在跳过时也推进步号）。

### Q12 — 参考答案

1. 用 `--accum-grid 1,2,4 --num-steps 8` 生成。验证：以 `--no-write` 运行这组参数，得到的 `loss` 列为 `2.7746 / 2.7787 / 2.7735`，与文件中的 `avg_loss`（`2.77463…`、`2.77874…`、`2.77353…`）一致——loss 只取决于种子和配置，与机器无关；而样本/秒、耗时会随机器变化，无法对上。讲义只说"The output lands in `outputs/accum-curve.json`"，没有说明生成参数。
2. 不加 `--no-write` 时，`write_curve(points, LOG_PATH)` 会把 `outputs/accum-curve.json` **覆盖**成当前机器的 5 点结果，产生无意义的 git diff（吞吐数字每次都不同）。在共享仓库中跑演示时应加 `--no-write` 或改输出路径。
3. 计时区间内还包含：用 `torch.randn`/`randint` 生成 `accum_steps` 个 micro-batch 的数据、`global_grad_norm` 中每个参数一次 `.item()`、Python 列表与循环开销。数据生成与 accum 成正比，会被算进"训练吞吐"；而 `.item()` 同步、`optimizer.step()` 是每个有效步一次的固定开销，正是 Q8 中吞吐随 accum 上升的来源之一。结论是"趋势可信、绝对数值不代表真实训练"。
4. 不同有效 batch 下最优学习率不同（讲义："Large effective batches need scaled learning rates and warmup"），统一 `lr=0.05` 意味着各配置处于不同的"有效步长"状态；再加上标签随机、无可学习信号，`avg_loss` 列不能作为"哪个 accum 更好"的证据。讲义自己也说"the lesson here is mechanical, not statistical"。

### Q13 — 参考回答要点

- **定义**：把一个大的有效 batch 拆成 N 个能放进显存的 micro-batch，逐个前向、反向，让梯度在 `param.grad` 中累加，N 个之后才 `optimizer.step()`。
- **解决的问题**：显存只放得下小 batch，但优化需要大 batch（更平滑的梯度、与学习率配方匹配）。
- **代价**：时间——每个 micro-batch 都要完整前向反向，每个优化器步耗时约为 N 倍；优化器步数相同时总训练时间变长。显存不随 N 增长（激活只保留一个 micro-batch 的）。
- **核心代码**：

```python
optimizer.zero_grad()
for x, y in micro_batches:                 # N 个
    (criterion(model(x), y) / N).backward()
optimizer.step()
```

- 加分点：能说出等价性的前提（等大 micro-batch、mean 归约、无 BatchNorm），以及优化器状态与调度按有效步推进。
- 常见误区：忘除 N；在窗口中间 `zero_grad`；每个 micro-batch 都 step。

### Q14 — 参考回答要点

- **micro-batch 大小不等**（如数据集末尾的残批）：mean 归约后再除以 N 会给不同样本不同权重（Q5 实测差 0.037）。处理：用 `reduction="sum"` 后除以窗口总样本数，或丢弃残批。
- **按 token 平均的语言模型 loss**：每个 micro-batch 有效 token 数不同（Q10）。处理：除以窗口内总 token 数。
- **BatchNorm**：统计量在每个 micro-batch 上计算，等价于用小 batch 做归一化，与大 batch 不同。处理：用 LayerNorm/GroupNorm（Transformer 本来就用 LayerNorm），或 SyncBN 等。
- **浮点求和顺序**：结果只在 ~1e-8 量级不同（本节 7.45e-9），通常可忽略，但会让"位级可复现"失效。
- **Dropout 等随机性**：每个 micro-batch 抽到的随机掩码不同于大 batch 一次性抽取，统计上等价但数值不同。
- **依赖 batch 内交互的 loss**：如对比学习（in-batch negatives）中负样本只来自同一 micro-batch，累积并不能增加负样本数量。处理：跨 micro-batch 缓存 embedding（gradient cache 类方法）。
- 加分点：讲义练习 5 要求比较 2×8 与 4×4 的切分，等大切分下实测差异仍是 7.45e-9 量级。

### Q15 — 参考回答要点

- **accum_steps**：`effective_batch // (micro_batch × world_size)`，并断言整除。
- **no_sync**：前 N−1 个 micro-batch 的前向和反向都放在 `with model.no_sync():` 里（前向也要在内，DDP 在前向时登记 hook），最后一个正常执行，触发一次 all-reduce。每个有效步通信次数从 N 降到 1（讲义练习 4："Confirm sync_calls drops by N-1 per effective batch"）。
- **loss 缩放**：每个 micro-batch 除以 `accum_steps`；DDP 的 all-reduce 本身做的是跨卡**平均**，所以不需要再除以 world_size。
- **梯度裁剪**：在最后一个 micro-batch 反向（all-reduce 完成）之后、`optimizer.step()` 之前做一次；用 AMP 时先 `unscale_`。
- **调度器**：每个有效步 `scheduler.step()` 一次。
- **日志**：每个有效步记录一次 loss（窗口平均）、梯度范数、lr、吞吐；讲义建议按有效 batch 记录 `samples_per_sec`、`median_step_ms`、`sync_calls` 等 JSON。
- **数据**：每张卡的 sampler 要保证窗口内不同卡、不同 micro-batch 拿到不同数据。
- 常见误区：在 `no_sync` 里只包反向不包前向；或者对所有 micro-batch 都同步，"network bound for no statistical gain"（skill 文件原话）。

### Q16 — 参考回答要点

- **基本方案**：micro-batch = 32（显存上限），`accum_steps = 512 / 32 = 16`；loss 除以 16；每 16 个 micro-batch 走一步优化器；调度和 warmup 按有效步配置；学习率沿用论文中有效 batch 512 的配方。
- **吞吐估算**：每个优化器步耗时 ≈ 16 × 单个 micro-batch 的前向反向时间；若总优化器步数按论文设定，总训练时间相应增加，需要提前评估。
- **提升 micro-batch 的手段**：
  - 混合精度（BF16/FP16，第 45 节）：激活和部分计算减半；
  - Gradient checkpointing（激活重计算）：用约一次额外前向换大幅降低激活显存；
  - 缩短序列或使用更省显存的注意力实现；
  - 优化器状态的低精度或分片（ZeRO 类方法，多卡时）。
- **权衡**：讲义："The micro-batch size is chosen to saturate device memory. Anything smaller wastes accelerator cycles."——在显存允许的前提下 micro-batch 越大，同样的有效 batch 需要的 accum 越少，固定开销越少。
- 加分点：上线前先用第 9 题式的等价性检查验证实现正确；记录吞吐曲线确认没有异常瓶颈。

### Q17 — 参考回答要点

- **不是越大越好**：有效 batch 变大时，梯度估计方差变小，但每个样本带来的"优化进度"递减；在相同样本预算下优化器步数变少。讲义："The literature treats large batch and small batch as different optimization problems."
- **学习率**：通常需要按比例增大（Goyal 等人 2017 年提出的 linear scaling rule：batch 放大 k 倍，lr 也放大 k 倍），并配合 warmup 防止初期发散；但线性放大有上限，超过某个规模后再放大 lr 会不稳定，需要实验确定。
- **吞吐**：单卡累积时，样本/秒在摊薄固定开销后趋于平缓（本节实测 accum 8→16 只从 11,976 升到 12,230），把 512 加到 4096 主要只是让每个优化器步慢 8 倍；多卡时更大的有效 batch 可以通过更多卡并行实现，提高实际吞吐。
- **收敛**：若总样本数固定，有效 batch 增大 8 倍意味着优化器步数减少 8 倍，可能达不到同样的 loss。
- 加分点：提到"关键 batch 大小"（critical batch size）这类概念——超过它之后增大 batch 主要浪费算力；以及调大 batch 后需要重新调 warmup、weight decay 等超参数。
- 常见误区：只改 `accum_steps` 而不改学习率和调度，然后得出"大 batch 效果差"的结论。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：调度按有效步推进。
- [阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：累积窗口末尾的 unscale 与裁剪。
- [阶段 19 · 43 HDF5 格式的分词语料](../../43-hdf5-tokenized-corpus/docs/zh.md)：提供 micro-batch 的数据加载器。
- [阶段 03 · 03 Backpropagation 从头开始](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：理解梯度为什么可以线性累加。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：SGD 与 Adam 对梯度尺度的不同敏感性。

### 本节被哪些后续内容用到
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：长时间累积训练需要在有效步边界保存与恢复。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)、[阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：真实的 all-reduce 与 `no_sync`。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：把累积、裁剪、调度、checkpoint 组装到一起。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：大规模训练中的有效 batch 与通信开销。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：另一种用计算换显存、增大 micro-batch 的手段。

### 延伸关键词
`micro-batch` · `effective batch size` · `DistributedDataParallel.no_sync` · `all-reduce` · `linear scaling rule` · `critical batch size` · `reduction="sum"` · `token-level loss normalization` · `BatchNorm vs LayerNorm` · `gradient cache` · `samples per second`
