# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 79 节 流水线并行与流水线气泡分析 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（在 `code/` 目录下）；测试：`python -m unittest discover tests`（在小节根目录下） ｜ **依赖**：标准库 `multiprocessing` + 第三方 `torch`（CPU 即可，`torch.distributed` gloo 后端）

---

## 1. 这份代码在考察什么

流水线并行按深度把模型切成 N 个 stage，每个 rank 一段。它的核心难题不是"怎么切"，而是"切完之后大家怎么不闲着"。这份代码分两部分：

1. **调度分析（纯 Python）**：构造 GPipe 调度表（哪个时间片、哪个 stage、哪个 micro-batch、前向还是反向），画成文本 Gantt 图，统计空闲格子得到气泡比例，并与闭式公式 `(N−1)/(M+N−1)` 对比；再打印 N = 4 时气泡随 M 的变化。
2. **真实两进程"流水线"（gloo）**：rank 0 持有 stage 0、rank 1 持有 stage 1，通过 `dist.send / dist.recv` 传递激活和激活的梯度，完成跨进程的反向传播和 SGD 训练。

> 一句话：**气泡 = 填充 + 排空时的空闲，增大 micro-batch 数 M 能把它摊薄**；跨 stage 的反向传播只需要把"激活的梯度"送回上一个 stage。但要看清：第一部分的"measured"并不是测量出来的，第二部分也不是真正的流水线（两个 rank 从不同时工作），而且梯度少除了 M。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SEED=23 / NUM_STAGES=4 / NUM_MICROBATCHES=8` | 常量 | demo 配置 | — |
| `FORWARD_UNITS=1 / BACKWARD_UNITS=2` | 常量 | ⚠️ 定义了但从未使用 | 模拟时钟（未实现） |
| `bubble_fraction` | 函数 | 闭式公式 `(N−1)/(M+N−1)` | 气泡比例 |
| `gpipe_schedule` | 函数 | 生成 `(cycle, stage, mb, phase)` 列表 | GPipe 调度 |
| `render_gantt` | 函数 | 把调度表画成 stage × cycle 的文本网格 | 可视化 |
| `measure_bubble` | 函数 | 统计调度表中的空闲格子 | 气泡（"测量"） |
| `StageMLP` | `nn.Module` | 一个 stage：两层线性 + ReLU | stage |
| `_pipe_worker` | 函数 | 两个 rank 的训练循环：前向 send 激活、反向 send 梯度 | 跨进程反向传播 |
| `run_pipeline` | 函数 | spawn 2 个进程并收集结果 | 启动器 |
| `main` | 函数 | 打印 Gantt 图、气泡对比、气泡-M 表，跑两进程例子 | demo |

数据流：`main` → `gpipe_schedule(4, 8)` → `render_gantt` 打印 → `bubble_fraction` 与 `measure_bubble` 对比 → 循环打印 M ∈ {1,…,64} 的气泡 → `run_pipeline`（rank 0：生成 x → stage0 → send 激活 → recv 梯度 → backward；rank 1：recv 激活 → stage1 → MSE → backward → send 激活梯度）→ 打印 rank 1 的 loss 个数和两个 stage 的参数范数。

---

## 3. 逐段精讲

### 3.1 `bubble_fraction`：闭式公式

```python
def bubble_fraction(num_stages: int, num_microbatches: int) -> float:
    n = num_stages
    m = num_microbatches
    return (n - 1) / (m + n - 1)
```

推导（每个前向、反向各 1 个时间片）：

- 前向段：最后一个 micro-batch 在最后一个 stage 完成于第 `M + N − 2` 片，前向段共 `M + N − 1` 片；
- 反向段同样 `M + N − 1` 片，总计 `2(M + N − 1)`；
- 每个 stage 有效工作 `2M` 片，空闲 `2(N − 1)` 片；
- 气泡比例 `2(N−1) / 2(M+N−1) = (N−1)/(M+N−1)`。

N = 1 时为 0（无需流水线）；M → ∞ 时趋近 0。若各 stage 的前向耗时 `t_f`、反向耗时 `t_b` 相同（不必相等），比例依然成立；不均衡的 stage 才会改变它。

### 3.2 `gpipe_schedule`：构造时间表

```python
    for mb in range(m):
        for stage in range(n):
            cycle = mb + stage
            schedule.append((cycle, stage, mb, "F"))
    forward_end = m + n - 1
    for mb in range(m):
        for stage in reversed(range(n)):
            cycle = forward_end + (m - 1 - mb) + (n - 1 - stage)
            schedule.append((cycle, stage, mb, "B"))
```

- **前向**：micro-batch `mb` 在第 `mb` 片进入 stage 0，每过一片前进一个 stage，所以在 stage `s` 的时间是 `mb + s`。同一 stage 上相邻 micro-batch 相差 1 片，不会冲突。
- **反向**：从 `forward_end = M + N − 1` 开始，按**逆序**处理 micro-batch（最后进入的 `mb = M−1` 最先反向），在 stage `s` 的时间是 `forward_end + (M−1−mb) + (N−1−s)`。stage N−1 的 `B7` 在第 11 片，紧接在 `F7`（第 10 片）之后。
- 依赖关系成立：`B(s, mb)` 比 `B(s+1, mb)` 晚 1 片；`B(N−1, mb)` 在所有前向之后。我们检查了 (4,8)、(4,4)、(2,16) 三组参数，没有两个操作占用同一个 (stage, cycle) 格子。
- 这是一个**按公式写出来的**调度表，不是由依赖关系模拟出来的；也没有使用 `FORWARD_UNITS / BACKWARD_UNITS`。讲义说"orchestrates the GPipe schedule on simulated stages using simulated wall-clock per stage"，并提到 `Pipeline(stages, num_microbatches)` 和 `PipelineStage` 类，代码中都不存在（实际是函数 `gpipe_schedule` 与类 `StageMLP`）。

### 3.3 `render_gantt` 与 `measure_bubble`

```python
    max_cycle = max(c for c, _, _, _ in schedule)
    grid = [["." for _ in range(max_cycle + 1)] for _ in range(n)]
    for cycle, stage, mb, phase in schedule:
        grid[stage][cycle] = f"{phase}{mb}" if phase != "." else "."
```

- 先建一个全是 `.` 的 `N × (max_cycle+1)` 网格，再把每个操作写进对应格子。`phase != "."` 的分支永远为真（调度表里没有空闲条目），参数 `num_microbatches` 也没用到。
- 每个格子右对齐 2 字符（`f"{cell:>2}"`），micro-batch 编号 ≥ 10 时（如 `F12`）列会错位。

```python
def measure_bubble(num_stages, num_microbatches):
    schedule = gpipe_schedule(num_stages, num_microbatches)
    max_cycle = max(c for c, _, _, _ in schedule)
    total_slots = num_stages * (max_cycle + 1)
    used = len(schedule)
    return (total_slots - used) / total_slots
```

- "空闲格子 / 总格子"：`(4 × 22 − 64) / 88 = 24/88 = 27.27%`。
- ⚠️ 这里的"measured"只是对同一个按公式构造的调度表计数，和闭式公式基于相同的假设，二者相等几乎是必然的；它没有测量任何真实耗时。另外它假设调度表无冲突——若有两个操作占同一格，`len(schedule)` 会多算。要做真正的验证，应该用依赖驱动的模拟器生成调度（测验 Q9、Q12 的做法），或者在真实多进程运行中计时。

### 3.4 `StageMLP`

```python
class StageMLP(nn.Module):
    def __init__(self, in_dim, hid_dim, out_dim):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hid_dim)
        self.fc2 = nn.Linear(hid_dim, out_dim)

    def forward(self, x):
        return torch.relu(self.fc2(torch.relu(self.fc1(x))))
```

- rank 0：`16 → 32 → 16`；rank 1：`16 → 32 → 4`。两段拼起来是一个 4 层 MLP。
- ⚠️ 输出层之后也有 ReLU：对 stage 0 没问题（中间激活），对最后一个 stage 意味着模型输出永远 ≥ 0，作为回归输出层不合适。

### 3.5 `_pipe_worker`：跨进程的前向与反向

```python
    torch.manual_seed(SEED + rank)
    ...
    g = torch.Generator().manual_seed(SEED + 99)
    for step in range(steps):
        optim.zero_grad(set_to_none=True)
        for _ in range(microbatches):
            if rank == 0:
                x = torch.randn(batch, in_dim, generator=g)
                act = stage(x)
                dist.send(act.detach(), dst=1)
                grad = torch.zeros_like(act)
                dist.recv(grad, src=1)
                act.backward(grad)
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
        optim.step()
```

**跨进程反向传播的关键三步**：

| 步骤 | rank 0 | rank 1 |
|------|--------|--------|
| 前向 | `act = stage(x)`，`send(act.detach())` | `recv(buf)`；`act = buf.detach().requires_grad_(True)`（新的叶子节点）；`pred = stage(act)` |
| 反向 | `recv(grad)`；`act.backward(grad)` 把上游梯度接入本地计算图 | `loss.backward()` 后 `act.grad = ∂loss/∂act`；`send(act.grad)` |
| 更新 | 各自 `optim.step()` 只更新自己的 stage | 同左 |

- `dist.send / dist.recv` 是阻塞的点对点通信；`recv` 需要预先分配好形状和 dtype 正确的缓冲区（`torch.zeros_like(act)`、`torch.zeros(batch, mid_dim)`）。
- `act.backward(grad)`：对非标量张量调用 `backward` 必须提供同形状的"上游梯度"，结果等价于对 `(act * grad).sum()` 求导——这就是链式法则在设备边界上的拼接。
- 数据只在 rank 0 生成（rank 1 也创建了同样种子的生成器但没有使用）；目标 `y` 全为 0。
- 各 stage 用不同的种子初始化（`SEED + rank`）——这里不需要 broadcast，因为两个 rank 持有的是**不同的**参数。

⚠️ **这不是流水线**：rank 0 发出激活后在 `recv(grad)` 上阻塞，直到 rank 1 完成前向、loss、反向并把梯度发回，才开始下一个 micro-batch。任何时刻只有一个 rank 在算，利用率不超过 50%，等价于"朴素模型并行"，与上面的 GPipe Gantt 图无关。要真正重叠，rank 0 应先连续做完（或预热若干个）micro-batch 的前向并异步发送（`isend`），再依次接收梯度（见测验 Q11）。

⚠️ **梯度尺度**：每个 micro-batch 的 `MSELoss` 已经是均值，M 次 `backward()` 累加后得到的是"完整 batch 平均梯度 × M"。我们在单进程里用相同的种子和数据顺序对拍：流水线 3 步后两段范数 `4.085717724128245 / 3.566153545556082`，与"完整 batch loss × M"的参考**逐位相同**，与"完整 batch 平均 loss"的参考不同（`4.085880… / 3.567292…`）。讲义说流水线 step 的梯度是"the gradient on the combined M*B examples"，要成立需把 loss 除以 M。

⚠️ 其它：`act = torch.zeros(..., requires_grad=True)` 是死代码；目标全 0 + 输出 ReLU 让任务几乎平凡——loss 从一开始就只有约 0.005。

### 3.6 `run_pipeline` 与 `main`

- `run_pipeline` 的 spawn、文件 rendezvous、结果回收、清理与第 77、78 节相同，world_size 固定为 2。只有 rank 1 记录 loss，所以 `results[0][0]` 是空列表。
- `main` 打印 Gantt 图、两种气泡值、M ∈ {1, 2, 4, 8, 16, 32, 64} 的气泡表，然后跑 `steps=3, batch=8, microbatches=4` 的两进程例子，只打印 loss 的**个数**（12 = 3 × 4）和两段参数范数，不打印 loss 曲线本身。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用公式直接构造调度表 | 简洁，Gantt 图一目了然 | 不能表达不等长的 F/B、不均衡 stage；"measured"不是独立验证；生产用依赖驱动的调度器 |
| F、B 都按 1 个时间片 | 公式推导最简单 | 实际反向约为前向 2 倍（常量定义了却没用）；均衡时不影响比例 |
| 只实现 GPipe | 最容易理解 | 激活显存 ∝ M；生产用 1F1B / interleaved 1F1B |
| 两进程例子逐 micro-batch 串行 | 收发顺序清晰、不会死锁 | 完全没有流水线重叠；真实实现用 `isend/irecv` 或 `batch_isend_irecv` |
| 每个 micro-batch 的 loss 不除以 M | 少一行代码 | 梯度是全 batch 的 M 倍，等价于学习率 × M |
| 目标全 0、输出带 ReLU | 不需要额外数据 | 训练几乎没有信号，无法观察"学习"；应构造有意义的回归目标 |
| 只有 rank 0 生成数据 | 符合"数据只进入第一个 stage" | 真实系统中最后一个 stage 也需要标签，需要额外传输或各自加载 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表元素为元组 | `schedule.append((cycle, stage, mb, "F"))` | 用元组表示一条记录 |
| 元组解包 + `_` | `for cycle, stage, mb, phase in schedule`、`max(c for c, _, _, _ in schedule)` | `_` 表示忽略的字段 |
| `reversed(range(n))` | `for stage in reversed(range(n))` | 倒序遍历 n−1, …, 0 |
| 二维列表推导式 | `[["." for _ in range(max_cycle + 1)] for _ in range(n)]` | 每行独立的列表 |
| 条件表达式 | `f"{phase}{mb}" if phase != "." else "."` | 三元运算 |
| 字符串转义 | `"stage \\ cycle  "` | `\\` 表示一个反斜杠字符 |
| `str.join` + 生成器 | `" ".join(f"{c:>2}" for c in range(max_cycle + 1))` | 用空格连接格式化后的单元格 |
| f-string 宽度与百分比 | `{closed * 100:.2f}%`、`{m:<6}`、`{bubble_fraction(4, m)*100:<10.2f}` | 2 位小数；左对齐 |
| 关键字参数 | `run_pipeline(steps=3, batch=8, microbatches=4)` | 可读性好 |
| `nn.Module` 子类 | `class StageMLP(nn.Module)` + `self.fc1 = nn.Linear(...)` | 属性赋值即注册子模块 |
| 嵌套函数调用 | `torch.relu(self.fc2(torch.relu(self.fc1(x))))` | 由内向外执行 |
| `detach().requires_grad_(True)` | `act = buf.detach().requires_grad_(True)` | 切断与之前计算图的联系，再声明为需要梯度的叶子 |
| 非标量 `backward` | `act.backward(grad)` | 传入上游梯度（vector-Jacobian product） |
| `torch.Generator` | `torch.randn(batch, in_dim, generator=g)` | 独立随机数流，保证数据可复现 |
| 阻塞点对点通信 | `dist.send(t, dst=1)`、`dist.recv(buf, src=0)` | 收方要先准备好同形状的缓冲区 |

---

## 6. 运行结果解读

实际运行（Linux、Python 3.13、torch 2.14.1 CPU，约 4 秒，退出码 0）：

```text
GPipe schedule analysis: stages=4, microbatches=8
stage \ cycle   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21
stage 0         F0 F1 F2 F3 F4 F5 F6 F7  .  .  .  .  .  . B7 B6 B5 B4 B3 B2 B1 B0
stage 1          . F0 F1 F2 F3 F4 F5 F6 F7  .  .  .  . B7 B6 B5 B4 B3 B2 B1 B0  .
stage 2          .  . F0 F1 F2 F3 F4 F5 F6 F7  .  . B7 B6 B5 B4 B3 B2 B1 B0  .  .
stage 3          .  .  . F0 F1 F2 F3 F4 F5 F6 F7 B7 B6 B5 B4 B3 B2 B1 B0  .  .  .

closed-form bubble fraction: 27.27%
measured bubble fraction:    27.27%

bubble vs microbatch count (N=4):
M     bubble %
1     75.00
2     60.00
4     42.86
8     27.27
16    15.79
32    8.57
64    4.48

running 2-stage real pipeline over gloo...
rank 1 saw 12 microbatch losses; final norm rank 0 = 4.0857, rank 1 = 3.5662
```

逐项解读：

- **Gantt 图**：每行 16 个有效格子（8 个 F + 8 个 B）和 6 个空闲格子（`.`）。stage 0 的空闲集中在中间（第 8～13 片，等待最后一个 micro-batch 走完前向、第一个反向传回来）；stage 3 的空闲集中在开头和结尾。每个 stage 的空闲都是 `2(N−1) = 6`。
- **27.27% = 3/11**：与讲义"At M=8, N=4 that is 27%"一致；M = 64 时 4.48%（讲义"4.5%"）。M = 1 时 75%：只有一个 micro-batch，任一时刻只有一个 stage 在工作。
- **气泡曲线**：M 翻倍，气泡大约减半，但收益递减；M ≫ N 才能把气泡压到 10% 以下。
- **两进程例子**：12 = 3 步 × 4 个 micro-batch。我们另外打印了这 12 个 loss：`0.0049, 0.0035, 0.0021, 0.0043, …, 0.003`——从一开始就很小，因为目标全为 0 且输出经过 ReLU，看不出明显的学习过程。两段范数与"完整 batch loss × M"的单进程参考逐位相同（见 3.5）。

---

## 7. 动手改一改

1. **1F1B 调度**（讲义练习 1）：写一个依赖驱动的调度生成器，输出与 `gpipe_schedule` 同格式的列表，复用 `render_gantt` 画图，统计各 stage 的激活峰值（测验 Q9：气泡同为 27.27%，峰值 `[4,3,2,1]` vs GPipe 的 `[8,8,8,8]`）。
2. **真正使用 `FORWARD_UNITS / BACKWARD_UNITS`**：让每个操作占用多个时间片（或改成连续时间），并支持每个 stage 不同的耗时；验证均衡时比例不变、不均衡时利用率下降（测验 Q12：`[1,1,2,1]` 时利用率 52.6%）。
3. **修正梯度尺度**（讲义练习 3）：rank 1 的 loss 除以 `microbatches`，写单进程参考验证与"完整 batch 平均 loss"等价（测验 Q10）。
4. **让两进程真正重叠**：rank 0 先对所有 micro-batch 做前向并 `isend` 激活、保存 `act` 列表，再依次 `recv` 梯度并反向；rank 1 收一个算一个并 `isend` 梯度。用 `time.perf_counter()` 测量两种实现的总耗时。
5. **有意义的任务**：去掉最后一个 stage 输出层的 ReLU，目标改为 `y = x @ W`（rank 1 需要拿到标签：可以让两个 rank 用同一生成器各自生成 x 并计算 y），观察 loss 曲线是否下降。
6. **进阶**（讲义练习 5）：用 4 个进程组成"2 段流水线 × 2 路数据并行"，用 `dist.new_group` 建立两个数据并行组，在每个 stage 的组内 allreduce 梯度。

---

## 8. 常见坑

- **把"measured"当成实测**：本节的 measured 是对公式构造的调度表计数，必然与公式一致。
- **以为增大 M 没有代价**：GPipe 下激活显存 ∝ M；micro-batch 过小会降低矩阵乘效率。
- **micro-batch 的 loss 不除以 M**：梯度放大 M 倍，等于偷偷把学习率乘了 M。
- **接收端没有把激活设成叶子节点**：直接用 `recv` 的缓冲区前向，`act.grad` 为 `None`，没有梯度可以发回。
- **收发顺序不匹配**：两端都先 `send` 或都先 `recv`，在同步通信下会死锁；收发的 micro-batch 顺序也必须一致。
- **按参数量切 stage**：embedding/LM head 参数多但计算少，应该按实测耗时切。
- **使用过时的 API**：讲义提到的 `torch.distributed.pipeline.sync.Pipe` 在本环境的 PyTorch 2.14 中已不存在（导入报 `ModuleNotFoundError`），现在的官方实现是 `torch.distributed.pipelining`。
- **micro-batch 编号 ≥ 10 时 Gantt 图错位**：单元格宽度固定为 2。

---

## 9. 测试在验证什么

测试文件：`tests/test_pipeline.py`（位于小节根目录的 `tests/`），共 6 个用例。运行方式（在小节根目录）：

```bash
python3 -m unittest discover tests -v
```

实际运行结果：`Ran 6 tests in 2.313s  OK`。

| 用例 | 验证的性质 |
|------|-----------|
| `test_closed_form_matches_measured_bubble` | N ∈ {2,3,4}、M ∈ {4,8,16} 的闭式公式与调度表计数一致——两者同源，主要验证 `gpipe_schedule` 的格子总数正确 |
| `test_bubble_shrinks_with_more_microbatches` | 气泡随 M 单调减小（M = 1、16、64） |
| `test_schedule_covers_every_microbatch_through_every_stage` | 调度表中前向、反向各有 `N × M` 条，且前向覆盖所有 (stage, mb) 组合（反向只检查了数量） |
| `test_render_gantt_includes_every_stage` | Gantt 文本包含 "stage 0"～"stage 3" |
| `test_two_rank_real_pipeline_runs` | 两进程例子能跑完，rank 1 记录了 `steps × microbatches = 6` 个 loss |
| `test_bubble_is_zero_when_one_stage` | N = 1 时气泡为 0 |

测试没有覆盖：调度的依赖正确性（`B(s,mb)` 在 `B(s+1,mb)` 之后）、调度表无冲突、两进程训练的梯度与单进程参考是否等价、loss 是否下降。
