# 测验 · 流水线并行与流水线气泡分析（Pipeline Parallel and Bubble Analysis）

> **阶段 19 · 综合项目 · 第 79 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（测试：[tests/test_pipeline.py](../tests/test_pipeline.py)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 流水线并行 | 按深度把模型切成 N 个 stage，每个 rank 一个 stage；前向时激活从 stage 0 传到 stage N−1，反向时梯度逆向传回 |
| 2 | 显存收益 | 每个 rank 只存 1/N 的层（参数、梯度、优化器状态），代价是 stage 之间必须串行 |
| 3 | micro-batch | 把一个 batch 切成 M 个 micro-batch 依次送入流水线，让不同 stage 同时处理不同的 micro-batch；有效 batch = M × B |
| 4 | 气泡（bubble） | 流水线填充（fill）和排空（drain）阶段的空闲时间；GPipe 的气泡比例为 `(N−1)/(M+N−1)` |
| 5 | GPipe 调度 | 先做完全部 M 个前向，再逆序做 M 个反向；总时长 `2(M+N−1)` 个时间片（F、B 各 1 单位），每 stage 有效工作 2M |
| 6 | GPipe 的显存问题 | 每个 stage 要同时保存 M 个 micro-batch 的激活，激活显存 ∝ M |
| 7 | 1F1B 调度 | 预热若干前向后"一前一后"交替；气泡与 GPipe 相同，但 stage s 最多只保存 `N−s` 份激活（与 M 无关） |
| 8 | stage 均衡 | 每个时间片由最慢的 stage 决定；应按**计算量**而不是参数量切分（embedding 参数多、计算少） |
| 9 | 梯度语义 | 一个 step 内 M 个 micro-batch 的梯度累积后才更新；要与全 batch 等价，每个 micro-batch 的 loss 应除以 M |
| 10 | 本节代码的边界 | Gantt 图与气泡是**按公式构造**的时间表；真实的 2-rank 例子是逐个 micro-batch 串行收发，并没有流水线重叠 |

### 核心技能（能动手做到）

- [ ] 给定 N、M，手算 GPipe 的总时间片数、气泡比例，并画出 Gantt 图
- [ ] 写出 1F1B 调度，验证它与 GPipe 气泡相同、激活峰值为 `N−s`
- [ ] 估算 stage 不均衡时的 step 时间与利用率
- [ ] 用 `dist.send / dist.recv` 在两个进程之间传递激活与激活梯度，完成跨 rank 的反向传播
- [ ] 证明流水线梯度累积与全 batch 梯度等价（并发现本节代码少除了 M）
- [ ] 指出讲义与代码的不一致（类名、模拟时钟常量、"真实流水线"、过时的 PyTorch API）

---

## 二、基础自测（选择题）

**Q1.** N = 4 个 stage、M = 8 个 micro-batch，GPipe 的气泡比例是：

- A. 37.5%
- B. 27.27%
- C. 50%
- D. 4.48%

**Q2.** 本节 `gpipe_schedule(4, 8)` 中每个前向、反向都占 1 个时间片。整个 step 一共占用多少个时间片（Gantt 图有多少列）？

- A. 16
- B. 11
- C. 32
- D. 22

**Q3.** 在 N = 4、M = 8 的 GPipe 调度中，每个 stage 在某一时刻最多要同时保存几个 micro-batch 的激活（前向已做、反向未做）？换成 1F1B 呢？

- A. GPipe 每个 stage 都是 8；1F1B 下 stage 0～3 分别是 4、3、2、1
- B. GPipe 每个 stage 都是 4；1F1B 每个 stage 都是 1
- C. 两者都是 8
- D. GPipe 是 1；1F1B 是 8

**Q4.** 代码定义了 `FORWARD_UNITS = 1`、`BACKWARD_UNITS = 2`，但调度函数从未使用它们（前向、反向都按 1 个时间片计）。如果真的让反向耗时是前向的 2 倍（各 stage 相同），GPipe 的气泡比例会：

- A. 变成原来的 2 倍
- B. 变成原来的一半
- C. 不变，仍是 `(N−1)/(M+N−1)`：填充/排空的空闲与有效工作按同样的比例放大
- D. 变成 0

**Q5.** 关于 `_pipe_worker` 中的"2-stage real pipeline"，下列说法正确的是：

- A. 它实现了 GPipe：rank 0 连续发出 4 个 micro-batch 的前向，再统一接收梯度
- B. 它对每个 micro-batch 都是"rank 0 前向 → 发送 → **等待**梯度返回 → 反向"之后才处理下一个，两个 rank 从不同时工作，相当于气泡 50% 的朴素模型并行
- C. 它实现了 1F1B
- D. 它让两个 rank 各自独立训练一份完整模型

**Q6.** `_pipe_worker` 中每个 micro-batch 都执行 `loss = loss_fn(pred, y); loss.backward()`，`step` 之前没有除以 micro-batch 数。我们把两个 stage 合在一个进程里、对拼接后的完整 batch 做对比，发现：

- A. 与"完整 batch 的平均 loss"梯度完全相同
- B. 梯度是完整 batch 梯度的 1/M
- C. 梯度随机不同
- D. 梯度是完整 batch 平均梯度的 **M 倍**，等价于学习率被放大 M 倍（与"完整 batch loss × M"的参考结果逐位一致）

**Q7.** 讲义强调"equal compute per stage matters more than equal parameter count per stage"。原因是：

- A. 参数量相同的 stage 一定计算量也相同
- B. embedding 层计算量大、参数少
- C. 每个时间片都要等最慢的 stage；embedding 之类的层参数很多但计算很少，按参数量均分会让某些 stage 计算远多于其他 stage
- D. 参数量不影响显存

**Q8.** 16 张 GPU 上组合"4 段流水线 × 4 路数据并行"（每个 stage 被复制到 4 个 rank）。梯度同步应该怎么做？

- A. 在每个 stage 的 4 个数据并行副本之间各自做 allreduce（4 个独立的 DP 组），不同 stage 之间不需要对梯度做 allreduce
- B. 16 个 rank 一起对所有参数做一次全局 allreduce
- C. 只在 stage 0 上做 allreduce
- D. 流水线并行不需要任何梯度同步

---

## 三、动手 / 代码题

**Q9.** 讲义练习 1：实现 1F1B 调度。规则（非交错版）：stage s 先做 `min(N−s−1, M)` 个前向预热，然后"一前一后"交替，最后把剩余的反向做完；每个操作必须等待依赖（`F(s, mb)` 依赖 `F(s−1, mb)`；`B(s, mb)` 依赖 `B(s+1, mb)`，最后一个 stage 依赖自己的 `F(s, mb)`）。

1. 写出生成调度的函数（输出格式与 `gpipe_schedule` 相同：`(cycle, stage, mb, phase)`）。
2. N = 4、M = 8 时总时间片数和气泡比例是多少？各 stage 的激活峰值是多少？

**Q10.** 讲义练习 3："Add gradient accumulation across pipeline microbatches and check the gradient equals the gradient of the equivalent full-batch forward."

1. 写一个单进程参考：用相同的种子构造两个 `StageMLP`（rank 0 用 `SEED`，rank 1 用 `SEED + 1`），用相同的生成器顺序生成 M 个 micro-batch 并拼接，做一次完整前向/反向。当前代码与之相比差在哪里？
2. 修改 `_pipe_worker`，使其与"完整 batch 的平均 loss"等价。

**Q11.** 阅读 `_pipe_worker` 中 rank 1 的分支：

```python
            else:
                act = torch.zeros(batch, mid_dim, requires_grad=True)
                buf = torch.zeros(batch, mid_dim)
                dist.recv(buf, src=0)
                act = buf.detach().requires_grad_(True)
                pred = stage(act)
                y = torch.zeros(batch, out_dim)
                loss = loss_fn(pred, y)
                loss.backward()
                dist.send(act.grad.detach(), dst=0)
                losses.append(loss.item())
```

1. 为什么必须 `buf.detach().requires_grad_(True)`？`act.grad` 发回 rank 0 后，rank 0 用 `act.backward(grad)` 做了什么？
2. 指出这段代码里的**两处**问题（提示：第一行；`y` 与 `StageMLP.forward` 的最后一个激活函数）。
3. 怎样改写 rank 0 / rank 1 的循环，让两个 rank 真正重叠工作（GPipe 风格）？

**Q12.** 4 个 stage 的前向耗时分别为 `[1, 1, 2, 1]`（单位时间），反向耗时是前向的 2 倍，M = 8，GPipe 调度。

1. 估算一个 step 的总时长和整体利用率（有效计算 / (N × 总时长)）。
2. 如果把总计算量重新均分成 4 个各 1.25 的 stage，总时长和利用率是多少？

---

## 四、面试高频题

**Q13.**（基础必考）什么是流水线并行？什么是 bubble？如何减小 bubble？

**Q14.**（原理深挖）GPipe 和 1F1B 有什么区别？为什么 1F1B 的气泡没有变小，却被 Megatron-LM 等框架普遍采用？interleaved 1F1B 又改进了什么？

**Q15.**（工程实践）你要训练一个 70B 模型，有 64 张 80 GB GPU。数据并行、ZeRO、张量并行、流水线并行你会怎么组合？流水线的 stage 数和 micro-batch 数怎么选？

**Q16.**（场景设计）流水线训练中发现 GPU 利用率只有 50% 左右，profile 显示 stage 2 明显比其他 stage 慢。你会如何诊断和优化？

**Q17.**（追问型）流水线并行中 stage 之间的 send/recv 为什么可能死锁？本节代码为什么没有死锁？micro-batch 越多越好吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

`(N−1)/(M+N−1) = 3/11 ≈ 27.27%`，与 demo 输出的 closed-form 和 measured 一致。

- A（37.5%）是 `3/8`，即误用 `(N−1)/M`；
- C（50%）对应 M = 3 时的 `3/6`；本题 M = 8，而 M = 4 时也只是 `3/7 = 42.86%`；
- D（4.48%）是 M = 64 时的值。

### Q2 — 答案：D

前向：micro-batch 7 在 stage 3 的时间片是 `7 + 3 = 10`，前向共占 0～10 共 11 片；反向从 `forward_end = M + N − 1 = 11` 开始，再占 11 片，最后一个是 stage 0 的 `B0` 在第 21 片。总计 `2(M+N−1) = 22`（Gantt 图表头 0～21）。

- A（16）是每个 stage 的有效工作量 `2M`；
- B（11）只算了前向；
- C（32）是 `N × 2M`，所有 stage 有效工作量之和。

### Q3 — 答案：A

GPipe：stage s 的前向在 `mb + s` 完成，反向要等全部前向结束后才开始，所以在开始反向之前，8 个 micro-batch 的激活全都在显存里——每个 stage 峰值都是 M = 8（我们按调度表逐时间片统计验证）。1F1B：stage s 只预热 `N−s−1` 个前向，之后每做一个前向就做一个反向，峰值为 `N−s`，即 4、3、2、1（模拟验证，见 Q9）。

这就是讲义说的"Activations from every microbatch must be held until its backward, so memory grows linearly with M"以及"1F1B ... activation memory is bounded by the pipeline depth"。

### Q4 — 答案：C

各 stage 的前向耗时 `t_f`、反向耗时 `t_b` 相同时：总时长 = `(M+N−1)·t_f + (M+N−1)·t_b`，每个 stage 的有效工作 = `M·(t_f + t_b)`，比例仍为 `(N−1)/(M+N−1)`。我们用异构时长模拟器验证：`t_f = 1, t_b = 2`、N = 4、M = 8 时总时长 33 = `11 × 3`，利用率 72.7%（气泡 27.27%）。

真正会改变气泡比例的是**各 stage 耗时不均**（见 Q12）。两个常量没被使用，讲义说的"simulated wall-clock per stage"在代码中并不存在——时间表是按"每操作 1 个时间片"直接构造的。

### Q5 — 答案：B

rank 0 的循环：`act = stage(x)` → `dist.send(act)` → `dist.recv(grad)`（阻塞，直到 rank 1 完成前向、loss、反向并把梯度发回）→ `act.backward(grad)`，然后才进入下一个 micro-batch。rank 1 也是收一个处理一个。所以任一时刻只有一个 rank 在计算，利用率最多 50%——这是"朴素模型并行"，不是 GPipe，也不是 1F1B。它的作用是演示"激活与激活梯度如何跨进程传递"（docstring："to prove the wire works"）。

- A 描述的是 GPipe 应有的做法（见 Q11.3）；
- C 错；
- D：两个 rank 各持一半模型，不是数据并行。

### Q6 — 答案：D

`MSELoss` 默认对每个 micro-batch 取均值，M 次 `backward()` 把梯度累加，得到 `Σ_k ∇mean_k = M × ∇(全 batch 平均 loss)`（每个 micro-batch 大小相同）。我们在单进程中用相同种子构造两个 stage、相同生成器顺序生成数据：

- 参考"完整 batch loss × M"：3 步后范数 `(4.085717724128245, 3.566153545556082)`，与流水线结果**逐位相同**；
- 参考"完整 batch 平均 loss"：`(4.085880…, 3.567292…)`，不同。

讲义说"The gradient at the end of a pipeline step is the gradient on the combined M*B examples"——要做到这一点，每个 micro-batch 的 loss 应除以 M（与梯度累积相同）。

### Q7 — 答案：C

流水线每一拍要等所有 stage 完成，最慢的 stage 决定节拍（讲义："If stage 0 takes 50 ms and stage 1 takes 100 ms, every cycle is gated on stage 1"）。embedding 层参数多（V × d）但只是查表，计算量很小；Transformer 层的计算主要在注意力和 MLP。按参数量切分会让包含 embedding 的 stage 很"轻"，其他 stage 很"重"。

- A 错（反例就是 embedding）；B 说反了；D 错，参数量决定参数/优化器显存。

### Q8 — 答案：A

二维并行中，rank 可以记为 `(pp_stage, dp_index)`。同一个 stage 的 4 个副本持有相同的层，处理不同的数据，所以它们之间需要 allreduce（或 ZeRO 的 reduce_scatter）；不同 stage 持有不同的层，参数根本不同，不能也不需要一起 allreduce。stage 之间只有前向激活和反向激活梯度的点对点 send/recv。

- B：不同 stage 的参数形状都不同，全局 allreduce 没有意义；
- C、D 错误。

讲义练习 5 要求推理这种 2D 调度。

### Q9 — 参考答案

```python
def one_f_one_b(n, m):
    orders = []                                   # 每个 stage 的操作顺序
    for s in range(n):
        warm = min(n - s - 1, m)
        ops = [("F", i) for i in range(warm)]
        f_next, b_next = warm, 0
        while f_next < m:                         # 稳态：一前一后
            ops.append(("F", f_next)); f_next += 1
            ops.append(("B", b_next)); b_next += 1
        while b_next < m:                         # 冷却：剩余反向
            ops.append(("B", b_next)); b_next += 1
        orders.append(ops)

    done, t_free, idx, sched = {}, [0] * n, [0] * n, []
    while any(idx[s] < len(orders[s]) for s in range(n)):
        for s in range(n):
            if idx[s] >= len(orders[s]):
                continue
            ph, mb = orders[s][idx[s]]
            if ph == "F":
                dep = done.get(("F", s - 1, mb)) if s > 0 else 0
            else:
                dep = done.get(("B", s + 1, mb)) if s < n - 1 else done.get(("F", s, mb))
            if dep is None:                       # 依赖未完成，下一轮再看
                continue
            start = max(t_free[s], dep)
            sched.append((start, s, mb, ph))
            done[(ph, s, mb)] = start + 1
            t_free[s] = start + 1
            idx[s] += 1
    return sched
```

N = 4、M = 8 的结果（已运行验证）：

```text
stage 0 F0 F1 F2 F3  .  .  . B0 F4 B1 F5 B2 F6 B3 F7 B4  . B5  . B6  . B7
stage 1  . F0 F1 F2  .  . B0 F3 B1 F4 B2 F5 B3 F6 B4 F7 B5  . B6  . B7  .
stage 2  .  . F0 F1  . B0 F2 B1 F3 B2 F4 B3 F5 B4 F6 B5 F7 B6  . B7  .  .
stage 3  .  .  . F0 B0 F1 B1 F2 B2 F3 B3 F4 B4 F5 B5 F6 B6 F7 B7  .  .  .
```

- 总时间片 22，气泡 27.27%——与 GPipe 相同；
- 激活峰值 stage 0～3 为 `[4, 3, 2, 1]`，GPipe 为 `[8, 8, 8, 8]`；M = 16 时 1F1B 仍为 `[4, 3, 2, 1]`（气泡 15.79%）。

可以直接复用 `render_gantt` 和 `measure_bubble` 的统计方式（`measure_bubble` 需要改为接收调度表作为参数）。

### Q10 — 参考答案

1. 参考实现：

```python
def reference(steps=3, batch=8, mbs=4, lr=0.05):
    torch.manual_seed(SEED);     s0 = StageMLP(16, 32, 16)     # 与 rank 0 相同
    torch.manual_seed(SEED + 1); s1 = StageMLP(16, 32, 4)      # 与 rank 1 相同
    opt = torch.optim.SGD(list(s0.parameters()) + list(s1.parameters()), lr=lr)
    g = torch.Generator().manual_seed(SEED + 99)
    for _ in range(steps):
        opt.zero_grad()
        x = torch.cat([torch.randn(batch, 16, generator=g) for _ in range(mbs)])
        loss = nn.MSELoss()(s1(s0(x)), torch.zeros(batch * mbs, 4))
        loss.backward()
        opt.step()
```

  对比结果：流水线 3 步后两个 stage 的范数为 `4.085717724128245` / `3.566153545556082`；参考在 `loss` 乘以 M 时**逐位相同**，按平均 loss 时为 `4.085880…` / `3.567292…`。说明当前代码的梯度是全 batch 平均梯度的 M 倍。
2. 修改：rank 1 中改为 `loss = loss_fn(pred, y) / microbatches`（记录时可以 `losses.append(loss.item() * microbatches)` 保持原数值含义）。rank 0 收到的激活梯度自然也就缩小了 M 倍，不需要另外改。这样流水线与"完整 batch 平均 loss"的参考等价（到浮点误差）。

### Q11 — 参考答案

1. `dist.recv` 写入的 `buf` 只是一块普通内存，与 rank 0 的计算图没有任何联系。`detach().requires_grad_(True)` 把它变成 rank 1 计算图中的**叶子节点**，`loss.backward()` 之后 `act.grad` 就是 `∂loss/∂激活`。rank 0 收到这个张量后调用 `act.backward(grad)`——对非标量张量反向时必须提供"上游梯度"，这相当于把链式法则从 rank 1 接到 rank 0：`∂loss/∂θ0 = (∂act/∂θ0)ᵀ · grad`。这就是流水线反向传播跨设备的全部秘密。
2. 问题：
   - 第一行 `act = torch.zeros(batch, mid_dim, requires_grad=True)` 是死代码，马上被覆盖；
   - 任务退化：目标 `y` 全是 0，而 `StageMLP.forward` 在输出层后也加了 `torch.relu`，最后一个 stage 只要输出非正数就能让 loss 为 0。实际运行中 loss 一开始就只有约 0.005，后面在 0.002～0.004 之间波动，看不出"训练在学东西"；回归输出层也不应接 ReLU。
   - （另外）每个 micro-batch 的 loss 没有除以 M，见 Q10。
3. GPipe 风格的改写思路：
   - rank 0：先对 M 个 micro-batch 依次前向，并用 `dist.isend` 异步发出激活（保存各自的 `act` 与发送句柄）；然后依次 `recv` 每个 micro-batch 的梯度并 `act[k].backward(grad)`；
   - rank 1：依次 `recv` 激活、前向、算 loss；可以立即反向并 `isend` 梯度（这已接近 1F1B），或者先缓存全部 M 个再统一反向（严格 GPipe）；
   - 双方收发顺序必须一致（同一 micro-batch 顺序），最后 `wait()` 所有句柄再 `optim.step()`。这样 rank 0 在算第 k+1 个前向时，rank 1 可以同时算第 k 个，前向阶段产生重叠。

### Q12 — 参考答案

1. **不均衡 `[1, 1, 2, 1]`**：前向段，流水线节拍由最慢的 stage（2）决定：`(M−1) × 2 + (1+1+2+1) = 14 + 5 = 19`；反向耗时翻倍：`(M−1) × 4 + 10 = 38`；总时长约 **57**。有效计算 `Σ_s M × 3 × t_s = 24 × 5 = 120`，利用率 `120 / (4 × 57) ≈ 52.6%`。
2. **均衡为 4 × 1.25**：前向 `7 × 1.25 + 5 = 13.75`，反向 27.5，总时长 **41.25**，利用率 `120 / (4 × 41.25) ≈ 72.7%`——正好等于 `1 − 27.27%`，即只剩下 GPipe 固有的气泡。

（两组数字都已用逐操作的依赖模拟器验证。）结论：一个 stage 慢一倍，step 时间从 41.25 增加到 57（+38%），这就是讲义强调"Stage balance is measured, not assumed"的原因。

### Q13 — 参考回答要点

- **定义**：按层把模型切成 N 段放到 N 张卡上，激活在相邻 stage 之间点对点传递；每张卡只存一段，显存线性下降。
- **bubble**：流水线开始时后面的 stage 在等第一个 micro-batch 到达，结束时前面的 stage 在等最后一个梯度传回，这段空闲就是气泡。GPipe 气泡比例 `(N−1)/(M+N−1)`。
- **减小气泡**：增大 M（M ≫ N；讲义：M = 64、N = 4 时 4.5%）；interleaved 调度（每张卡负责多个不连续的小 stage，等效减小填充时间）；零气泡类调度（把反向拆成"对输入的梯度"和"对权重的梯度"分别调度）；stage 均衡。
- **增大 M 的代价**：每个 micro-batch 变小，GPU 矩阵乘效率下降；GPipe 下激活显存 ∝ M。

### Q14 — 参考回答要点

- **GPipe**：所有前向做完再做反向（fill-then-drain），简单，但每个 stage 要同时保存 M 份激活。
- **1F1B**：预热 `N−s−1` 个前向后一前一后交替，第一个 micro-batch 的反向尽早开始、尽早释放激活；气泡比例相同（总时间片数不变），但激活峰值只有 `N−s` 份，与 M 无关——所以可以放心增大 M 来减小气泡，这才是它被普遍采用的原因。
- **interleaved 1F1B**（Megatron-LM）：每张卡持有 v 个不相邻的模型块（virtual stages），填充/排空时间缩短为原来的 1/v，气泡约降为 `(N−1)/(v·M)` 量级；代价是点对点通信次数增加 v 倍。
- 加分点：PipeDream 的异步版本用权重暂存（weight stashing）解决前向/反向使用不同版本权重的问题；零气泡流水线把反向拆成 B（输入梯度）与 W（权重梯度）来填补空隙。

### Q15 — 参考回答要点

- **显存估算**：70B 参数，混合精度 Adam 16P ≈ 1.12 TB；即使 ZeRO-3 分到 64 卡也要 17.5 GB/卡，再加上激活。
- **常见组合（3D 并行）**：
  - 机内 8 卡做**张量并行**（TP = 8，依赖 NVLink 高带宽，切分每层的矩阵乘）；
  - 机间做**流水线并行**（如 PP = 2～4，只在 stage 边界传激活，通信量小，适合较慢的机间网络）；
  - 剩余维度做**数据并行**并配合 ZeRO-1（讲义："ZeRO-1 + pipeline is a common combo for the largest open models"）。
  - 例如 64 = TP 8 × PP 2 × DP 4。
- **stage 数与 micro-batch 数**：stage 数在显存够用的前提下尽量小（气泡与 N 正相关）；M 至少是 N 的 4～8 倍（M = 4N 时气泡为 `(N−1)/(5N−1)`，N = 4 时 `3/19 ≈ 15.8%`），用 1F1B 控制激活显存；全局 batch = M × micro-batch × DP。
- **stage 均衡**：按实测每层耗时切分；首末 stage 包含 embedding/LM head，通常少分配几层 Transformer。
- 加分点：配合 activation checkpointing；评估时 TP 的 allreduce 在每层两次，必须放在 NVLink 域内。

### Q16 — 参考回答要点

- **诊断**：
  - 用 profiler 分别统计每个 stage 每个 micro-batch 的前向/反向耗时与等待时间，确认是"计算不均"还是"通信等待"；
  - 检查 stage 2 的层数、是否包含特殊层（大 vocab 的输出层、MoE 层、长序列注意力）；
  - 检查那台机器的硬件（降频、PCIe/网卡、NUMA）。
- **优化**：
  - 重新划分：把 stage 2 的部分层移到相邻 stage（按实测时间而不是层数；讲义：Megatron 允许按 stage 指定不同层数）；
  - 对 stage 2 单独开启 activation checkpointing 会**增加**计算，反而可能更慢，需权衡；
  - 增大 M、改用 interleaved 1F1B 减小固有气泡；
  - 检查 send/recv 是否与计算重叠（异步通信）。
- 量化：参考 Q12，一个 stage 慢一倍会让整体 step 时间增加约 38%、利用率从 73% 跌到 53%。

### Q17 — 参考回答要点

- **死锁原因**：如果 send 是同步的（要等对端 recv 才返回），两个相邻 stage 同时先 send 给对方，就会互相等待。讲义给出的标准解法："even-rank stages send first then recv, odd-rank stages recv first then send"；或者使用非阻塞的 `isend/irecv` 再统一 `wait`，或批量提交 `batch_isend_irecv`。
- **本节为什么没死锁**：通信是严格单向配对的——rank 0 先 send 激活再 recv 梯度，rank 1 先 recv 激活再 send 梯度，顺序天然互补；而且每次只有一个 micro-batch 在途（见 Q5）。
- **micro-batch 越多越好吗**：不是。M 增大气泡减小，但：每个 micro-batch 变小，矩阵乘效率下降；每个 micro-batch 都有固定的通信/调度开销；GPipe 下激活显存线性增长；全局 batch = M × B 受优化稳定性约束。实践中在 M ≈ 4N～8N 之间取折中。
- 加分点：说出本节代码里"真实流水线"其实是串行的，以及 `torch.distributed.pipeline.sync.Pipe`（讲义提到的 API）在新版 PyTorch 中已不存在，现在是 `torch.distributed.pipelining`。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 76 从零实现集合通信操作](../../76-collective-ops-from-scratch/docs/zh.md)：点对点 send/recv 与集合通信的基础。
- [阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：与流水线正交的数据并行维度。
- [阶段 19 · 78 ZeRO Optimizer 状态分片](../../78-zero-parameter-sharding/docs/zh.md)：常与流水线组合的显存优化。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：micro-batch 梯度累积与 loss 缩放。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：数据/张量/流水线并行的整体图景。

### 本节被哪些后续内容用到
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：按 stage 保存参数分片。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：DDP + ZeRO + 流水线的组合演示。
- [阶段 10 · 19 DualPipe 并行](../../../10-llms-from-scratch/19-dualpipe-parallelism/docs/zh.md)：双向流水线，把通信与计算重叠、进一步压缩气泡。
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../../10-llms-from-scratch/20-deepseek-v3-walkthrough/docs/zh.md)：大规模训练中流水线并行的实际应用。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：与流水线搭配降低激活显存。

### 延伸关键词
`GPipe` · `1F1B` · `interleaved 1F1B / virtual stages` · `zero bubble pipeline` · `PipeDream / weight stashing` · `activation checkpointing` · `3D parallelism (TP × PP × DP)` · `torch.distributed.pipelining` · `batch_isend_irecv` · `stage balancing`
