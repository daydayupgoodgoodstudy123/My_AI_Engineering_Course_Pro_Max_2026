# 测验 · GPU 设置和云（GPU Setup & Cloud）

> **阶段 00 · 环境搭建与工具 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/gpu_check.py](../code/gpu_check.py) ｜ 代码讲解：[code/gpu_check.讲解.md](../code/gpu_check.讲解.md)
>
> **用法**：学完讲义、在本机或 Colab 上跑过 `gpu_check.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要 GPU | 阶段 1–3 用 CPU 足够；从 CNN、Transformer、LLM（阶段 4+）开始，GPU 能把 8 小时的训练缩到 10 分钟量级 |
| 2 | 三种获取 GPU 的方式 | 本地 NVIDIA 卡（日常使用）、Google Colab 免费 T4（快速实验）、云 GPU（Lambda/RunPod/Vast.ai，约 0.20–2.00 美元/小时，认真训练） |
| 3 | `nvidia-smi` | 检查 NVIDIA 驱动是否正常、看到哪些卡、显存与占用；Colab 里用 `!nvidia-smi` |
| 4 | PyTorch 的 CUDA API | `torch.cuda.is_available()`、`torch.version.cuda`、`get_device_name(0)`、`get_device_properties(0).total_memory` |
| 5 | 设备无关写法 | `device = torch.device("cuda" if torch.cuda.is_available() else "cpu")`，同一份代码有卡用卡、没卡用 CPU |
| 6 | GPU 是异步执行的 | Python 发出 GPU 指令后立刻返回；计时前后必须 `torch.cuda.synchronize()`，否则测到的只是"发指令"的时间 |
| 7 | VRAM | GPU 上独立于系统内存的显存，决定能放多大的模型和多大的 batch |
| 8 | fp16 经验法则 | 每个参数 2 字节：可容纳参数量 ≈ 显存字节数 / 2，如 24 GB ≈ 12B 参数（只算权重） |
| 9 | Tensor Core 与半精度 | Tensor Core 是专做矩阵乘的硬件单元；fp16 比 fp32 省一半显存、精度损失很小 |

### 核心技能（能动手做到）

- [ ] 运行 `nvidia-smi`（或在 Colab 中切换到 T4 后运行 `!nvidia-smi`），读出 GPU 型号、显存总量和当前占用
- [ ] 运行 `python gpu_check.py`，说清它在"没装 torch / 没有 CUDA / 有 CUDA"三种情况下分别会输出什么
- [ ] 写出正确的 CPU vs GPU 矩阵乘基准测试：包含 warm-up、两次 `synchronize`、多次取平均，并解释每一步
- [ ] 给定显存大小，用 fp16 法则估算能装下的最大模型；再说明训练时为什么远远装不下这么大
- [ ] 把一段只能在 CPU 上跑的代码改成设备无关写法（模型和张量都 `.to(device)`）
- [ ] 能为"免费试一试 / 每天用 / 大规模训练"三种场景分别选择 Colab、本地卡或云 GPU，并估算云 GPU 的费用

---

## 二、基础自测（选择题）

**Q1.** GPU 训练神经网络比 CPU 快得多，最根本的原因是：

- A. GPU 的时钟频率比 CPU 高
- B. GPU 有成千上万个核心，能同时并行执行大量矩阵运算
- C. GPU 使用了更高效的编程语言
- D. GPU 的内存比 CPU 大

**Q2.** 在 GPU 计时代码中，`c = a_gpu @ b_gpu` 之后为什么必须先调用 `torch.cuda.synchronize()` 再停止计时？

- A. 为了把结果从 GPU 拷回 CPU
- B. GPU 操作是异步的，Python 立即返回，必须等 GPU 真正算完计时才准确
- C. 为了释放 GPU 显存
- D. 为了把 GPU 频率恢复到基础频率

**Q3.** 按 fp16 经验法则（每参数 2 字节），24 GB 显存大约能装下多少参数的模型权重？

- A. 6B
- B. 12B
- C. 24B
- D. 48B

**Q4.** 一个 7B 参数的模型，如果用 **fp32** 存储权重，大约需要多少显存（只算权重）？

- A. 7 GB
- B. 14 GB
- C. 28 GB
- D. 56 GB

**Q5.** 在一台 M2 MacBook 上，PyTorch 已安装且 `torch.backends.mps.is_available()` 为 True。运行本节的 `gpu_check.py` 会看到：

- A. 打印 MPS 设备信息并跑 CPU vs MPS 基准
- B. 打印 `No GPU detected. That's fine for most lessons.` 后结束
- C. 抛出 `RuntimeError`，因为没有 CUDA
- D. 打印 `PyTorch not installed`

**Q6.** 你家里没有 GPU，只想快速跑几个小实验，讲义推荐的最省事选择是：

- A. 购买一块本地显卡
- B. 租用云 GPU 并通过 SSH 安装环境
- C. Google Colab 免费版，在 Runtime 中切换到 T4 GPU
- D. 只能放弃 GPU 课程

**Q7.** 关于 VRAM，下列说法正确的是：

- A. VRAM 就是系统内存的一部分，可以随意共享
- B. VRAM 是 GPU 上独立于系统 RAM 的显存，它限制了模型大小和 batch size
- C. VRAM 是操作系统用于交换（swap）的虚拟内存
- D. VRAM 越大，GPU 的计算速度一定越快

---

## 三、动手 / 代码题

**Q8.**（预测输出）假设某块 GPU 的 `props.total_memory` 恰好是 `24 * 1024**3 = 25_769_803_776` 字节（即 24 GiB）。根据 `gpu_check.py` 的以下代码，写出打印的 `Memory:` 行和最后一行的估算结果，并解释为什么和"24 GB → 12B"对不上。

```python
    props = torch.cuda.get_device_properties(0)
    print(f"Memory: {props.total_memory / 1e9:.1f} GB")
    # ...
    vram_gb = props.total_memory / 1e9
    params_fp16 = vram_gb * 1e9 / 2
    params_billions = params_fp16 / 1e9
    print(f"\nEstimated max model size (fp16): ~{params_billions:.0f}B parameters")
```

**Q9.**（解释代码）`gpu_check.py` 的 GPU 计时部分如下。请回答：(a) 两次 `torch.cuda.synchronize()` 各自的作用；(b) 如果把第二次删掉，测出的 `Speedup` 会偏大还是偏小？(c) 为什么 `.to("cuda")` 放在计时之外？

```python
    a_gpu = a.to("cuda")
    b_gpu = b.to("cuda")
    torch.cuda.synchronize()

    start = time.time()
    _ = a_gpu @ b_gpu
    torch.cuda.synchronize()
    gpu_time = time.time() - start
```

**Q10.**（改进代码）本节的基准测试只跑一次矩阵乘、没有预热（warm-up），也不支持 Apple MPS。请写一个改进版函数 `bench(device, size=4000, iters=10)`：支持 `"cpu"`、`"cuda"`、`"mps"`，先预热再计时、用 `time.perf_counter()`、返回平均每次耗时（秒），并正确处理不同设备的同步。

---

## 四、面试高频题

**Q11.**（基础必考）CPU 和 GPU 的架构差异是什么？为什么深度学习特别适合 GPU？Tensor Core 又是什么？

**Q12.**（原理深挖）一个 7B 参数的模型，fp16 推理大约需要多少显存？如果用 Adam 做全参数训练呢？显存都花在了哪里？

**Q13.**（工程实践）如何正确地给 GPU 代码做性能基准测试？列出你会注意的点。

**Q14.**（场景设计）你需要在两周内完成一个中等规模模型的微调实验，预算有限。如何在本地 GPU、Colab、云 GPU 之间做选择？上云后有哪些省钱和防踩坑的做法？

**Q15.**（追问型）训练时报 `CUDA out of memory`，你会按什么顺序排查和解决？

---

## 五、参考答案与解析

### Q1 — 答案：B

神经网络训练的主体是大规模矩阵乘法，每个输出元素的计算彼此独立，天然可以并行。GPU 拥有成千上万个相对简单的核心，适合"同一操作作用于海量数据"；CPU 核心少但单核强、擅长复杂分支逻辑。A 错：GPU 时钟频率通常**低于** CPU。D 错：显存通常比系统内存小。

### Q2 — 答案：B

CUDA 操作是**异步**的：`a_gpu @ b_gpu` 只是把计算任务放进 GPU 的执行队列，Python 立即返回。不同步就停表，测到的几乎只是"排队"的时间，GPU 会显得快得离谱。`synchronize()` 会阻塞 CPU 直到 GPU 上之前的所有任务完成。A 描述的是 `.cpu()` / `.to("cpu")`。

### Q3 — 答案：B

24 GB ÷ 2 字节/参数 = 12 × 10⁹ = 12B 参数。注意这只是**权重**；推理还需要激活和 KV cache，训练还需要梯度和优化器状态，实际能跑的模型要小得多。

### Q4 — 答案：C

fp32 每参数 4 字节：7 × 10⁹ × 4 = 28 × 10⁹ 字节 ≈ 28 GB。换成 fp16 是 14 GB，int8 约 7 GB，int4 约 3.5 GB——这就是量化能让大模型跑在消费级显卡上的原因。

### Q5 — 答案：B

`gpu_check.py` 只检查 `torch.cuda.is_available()`，Mac 上没有 CUDA，所以走"没有 GPU"分支：

```text
No GPU detected. That's fine for most lessons.
For GPU-heavy lessons, use Google Colab (free).
```

这是脚本的一个局限：第 01 节的 `verify.py` 会检测 MPS，而本节脚本不会。D 错在 torch 已安装；C 错在脚本先判断再使用 CUDA，不会抛异常。

### Q6 — 答案：C

讲义的三个选项中，Colab 免费、无需设置，适合"家里没有 GPU、做快速实验"；本地卡适合日常使用和大数据集；云 GPU（约 0.20–2.00 美元/小时）适合认真训练和大模型。Colab 中通过 Runtime > Change runtime type > T4 GPU 开启，再用 `!nvidia-smi` 验证。

### Q7 — 答案：B

讲义 Key Terms：VRAM 是 GPU 上的显存，与系统 RAM 分离，限制了模型大小。D 错：计算速度取决于核心数量、Tensor Core、显存带宽等，显存大小主要决定"放不放得下"。

### Q8 — 参考答案

```text
Memory: 25.8 GB
...
Estimated max model size (fp16): ~13B parameters
```

计算过程：`25_769_803_776 / 1e9 = 25.77` → 打印 `25.8 GB`；`25.77 / 2 = 12.88` → `:.0f` 四舍五入为 `13`。

为什么对不上：代码用的是**十进制 GB**（`1e9` 字节），而显卡标称的"24 GB"通常是 **24 GiB**（`1024³` 字节）。1 GiB ≈ 1.074 GB，所以 24 GiB ≈ 25.8 GB。估算的分子和分母单位一致（都是"字节 / 2"），本身是对的；只是"24 GB → 12B"这句经验法则把 GB 与 GiB 混用了。工程上 1.07 倍的误差无关紧要，但看到 `25.8 GB` 不要以为脚本算错。另外 `vram_gb * 1e9 / 2 / 1e9` 中先乘 `1e9` 再除 `1e9` 是为了把"字节 → 参数数 → 十亿"三步写得一目了然，可以化简为 `vram_gb / 2`。

### Q9 — 参考答案

(a)
- 第一次 `synchronize()`（计时前）：确保之前排进 GPU 队列的工作（包括数据拷贝等）全部完成，计时起点"干净"，不会把前面的工作算进矩阵乘的耗时。
- 第二次 `synchronize()`（计时后）：等待矩阵乘**真正算完**再停表。

(b) 偏**大**。没有第二次同步，`time.time() - start` 只包含把 kernel 提交到队列的时间（通常远小于实际计算），`gpu_time` 被严重低估，`cpu_time / gpu_time` 就会被夸大，甚至出现离谱的上万倍"加速"。

(c) 本基准想比较的是**纯计算**速度。把数据从 CPU 内存拷到显存（经过 PCIe）的开销单独存在，放在计时外更公平。但要意识到：真实训练中如果每一步都在 CPU 和 GPU 之间来回搬数据，传输可能成为瓶颈——所以工程上会让数据和模型常驻 GPU、用 `pin_memory` 和异步数据加载。

### Q10 — 参考答案

```python
import time
import torch


def _sync(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()
    elif device == "mps":
        torch.mps.synchronize()


def bench(device: str, size: int = 4000, iters: int = 10) -> float:
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, size, device=device)

    for _ in range(3):          # 预热：触发库初始化、kernel 选择、内存分配
        _ = a @ b
    _sync(device)

    start = time.perf_counter()
    for _ in range(iters):
        _ = a @ b
    _sync(device)               # 等最后一次计算完成
    return (time.perf_counter() - start) / iters


if __name__ == "__main__":
    devices = ["cpu"]
    if torch.cuda.is_available():
        devices.append("cuda")
    if torch.backends.mps.is_available():
        devices.append("mps")
    results = {d: bench(d) for d in devices}
    for d, t in results.items():
        print(f"{d:>4}: {t * 1000:.1f} ms/iter  ({results['cpu'] / t:.0f}x vs cpu)")
```

要点：
- **预热**：第一次调用 GPU 时会有 CUDA 上下文/cuBLAS 初始化、显存分配等一次性开销，不预热会把这些算进去，让 GPU 显得比实际慢。
- **多次取平均**：单次测量受系统抖动影响大。
- **`time.perf_counter()`**：专为测量时间间隔设计的高精度单调时钟，比 `time.time()`（墙上时间，可能被系统校时调整）更合适。
- **按设备同步**：CUDA 用 `torch.cuda.synchronize()`，MPS 用 `torch.mps.synchronize()`，CPU 本来就是同步执行。
- 直接用 `device=` 在目标设备上创建张量，省去拷贝。

### Q11 — 参考回答要点

- **架构差异**：CPU 少量强大的核心，大缓存、复杂的分支预测和乱序执行，擅长延迟敏感、逻辑复杂的串行任务；GPU 有成千上万个简单核心，擅长吞吐量导向、数据并行的计算。
- **为什么适合深度学习**：前向/反向传播主体是矩阵乘和逐元素运算，计算量巨大但结构规整、高度可并行。
- **Tensor Core**：GPU 中专门做矩阵乘累加的硬件单元，对 fp16/bf16 等低精度格式吞吐极高（讲义给出的量级是比普通核心快 4–8 倍）。这也是混合精度训练如此流行的原因之一。
- **加分点**：提到显存带宽同样关键——很多算子（如逐元素操作、LLM 推理的 decode 阶段）是"访存受限"而不是"计算受限"。
- **常见误区**："GPU 主频更高所以更快"——恰恰相反。

### Q12 — 参考回答要点

- **fp16 推理**：权重 7B × 2 字节 ≈ 14 GB；另加 KV cache（随 batch 和上下文长度线性增长）和激活、框架开销，实际 16 GB 的卡会比较紧张，24 GB 的卡比较从容。量化到 int8/int4 可降到约 7 GB / 3.5 GB。
- **Adam 全参训练（混合精度）**：常用估算约 **16 字节/参数**——fp16 权重 2 + fp16 梯度 2 + fp32 主权重 4 + Adam 一阶矩 4 + 二阶矩 4。7B × 16 ≈ 112 GB，**还没算激活**，单张消费级显卡根本放不下。
- **应对**：LoRA/QLoRA 只训练少量参数；梯度检查点（gradient checkpointing）用重算换激活显存；ZeRO/FSDP 把优化器状态和参数切分到多卡；更小的 batch + 梯度累积。
- **加分点**：能解释讲义的"2 字节/参数"只是**权重**的下界，并主动区分推理与训练。
- **常见误区**：用"24 GB 能装 12B"去判断能不能训练 12B 模型。

### Q13 — 参考回答要点

1. **同步**：CUDA 异步执行，计时前后都要 `torch.cuda.synchronize()`，或使用 `torch.cuda.Event(enable_timing=True)` 在 GPU 时间线上计时。
2. **预热**：排除首次调用的初始化、kernel 选择、显存分配开销。
3. **多次重复取统计量**：平均值/中位数，必要时报告方差。
4. **明确测什么**：是否包含数据传输、数据加载、Python 开销，要与真实场景一致。
5. **固定条件**：相同输入形状、相同精度（fp32 vs fp16 差别巨大）、排除其他进程占用（用 `nvidia-smi` 查看）。
6. **用合适的时钟**：`time.perf_counter()` 而不是 `time.time()`。
7. **深入定位用 profiler**：如 `torch.profiler`，看每个算子的耗时。
- **加分点**：指出本节讲义示例为了简洁省略了预热和多次重复，所以"Speedup"只是量级参考。

### Q14 — 参考回答要点

- **决策依据**：显存需求（先按 Q12 估算）、总计算时长、预算、数据隐私、是否需要长时间不间断运行。
- **选择**：
  - Colab 免费 T4：验证代码能跑通、小规模调参；会话有时长限制，不适合长训练。
  - 本地 GPU：边际成本为 0，适合反复迭代；受显存上限约束。
  - 云 GPU（Lambda/RunPod/Vast.ai 等，约 0.20–2.00 美元/小时）：按需租用大显存卡，适合正式训练。费用估算如：40 小时 × 1 美元/小时 = 40 美元。
- **省钱与防坑**：先在 CPU/小数据/Colab 上把流程跑通再上云；定期保存 checkpoint 到持久存储（实例被回收或中断时可恢复）；训练结束**立即停机**，避免空跑计费；用 Docker 镜像或脚本快速复现环境（第 07 节）；在实例上第一件事是 `nvidia-smi` + `torch.cuda.is_available()` 验证。
- **常见误区**：直接在云上从零调试代码，把昂贵的 GPU 时间花在修 bug 上。

### Q15 — 参考回答要点

1. **看清现场**：`nvidia-smi` 看是否有其他进程占用显存（包括你自己没关的 notebook kernel）。
2. **减小显存需求**：减小 batch size（必要时配合梯度累积维持等效 batch）；缩短序列长度；使用混合精度（fp16/bf16）。
3. **用计算换显存**：gradient checkpointing。
4. **减少可训练参数**：LoRA/QLoRA、冻结部分层；或量化加载。
5. **检查代码问题**：在循环中累积带计算图的张量（例如 `total_loss += loss` 而不是 `loss.item()`）会让显存持续上涨；评估时忘了 `torch.no_grad()`。
6. **多卡/分片**：FSDP、ZeRO 等。
- **加分点**：知道 `torch.cuda.empty_cache()` 只能把缓存还给驱动，**不能**释放仍被引用的张量；用 `torch.cuda.memory_allocated()` / `memory_reserved()` 观察显存。
- **常见误区**：上来就换更大的卡，而不先检查显存泄漏。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：按平台安装正确的 PyTorch（CUDA wheel vs Mac 默认版），以及 CUDA/MPS 的初步检测。

### 本节被哪些后续内容用到
- [阶段 00 · 07 用于 AI 的 Docker](../../07-docker-for-ai/docs/zh.md)：在云 GPU 实例上用容器快速复现环境。
- [阶段 00 · 11 面向人工智能的 Linux](../../11-linux-for-ai/docs/zh.md)：云 GPU 基本都是 Linux + SSH，需要相应的命令行能力。
- [阶段 00 · 12 调试与性能分析](../../12-debugging-and-profiling/docs/zh.md)：系统化地测量与分析性能，是本节基准测试的进阶。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：张量、`device`、`.to(device)` 的系统用法。
- [阶段 10 · 11 量化](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：把"每参数 2 字节"进一步降到 1 字节、0.5 字节。
- [阶段 10 · 34 梯度检查点](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：用重算换显存，解决训练时的 OOM。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：推理时除权重外的另一大显存开销。
- [阶段 17 · 02 推理平台经济学](../../../17-infrastructure-and-production/02-inference-platform-economics/docs/zh.md)：GPU 成本核算在生产中的延伸。

### 延伸关键词
`CUDA 异步执行` · `torch.cuda.Event` · `混合精度 (fp16 / bf16)` · `Tensor Core` · `显存带宽 / Roofline` · `GiB vs GB` · `ZeRO / FSDP` · `Spot 实例` · `torch.profiler`
