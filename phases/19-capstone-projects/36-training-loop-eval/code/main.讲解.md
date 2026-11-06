# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 36 节 训练循环与 Evaluation ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；会**覆盖** `../outputs/losses.jsonl`）；测试：`python3 -m pytest -q` 或 `python3 tests/test_training.py`（测试把日志写到临时目录，不会动 `outputs/`） ｜ **依赖**：`torch`（第三方，CPU 即可）；`json`、`math`、`dataclasses`、`pathlib`、`typing`（标准库）

---

## 1. 这份代码在考察什么

这是"从零搭 GPT"系列的第七步：给第 35 节的 GPT 配上一个**会测量的训练循环**。代码考察：

1. **数据与目标对齐**：`make_batches` 生成"输入 / 右移一位的目标"对。
2. **损失计算**：`calc_loss_batch` 把 `(B, T, V)` 展平后算交叉熵。
3. **优化器配置**：AdamW + 衰减/不衰减两组参数 + `betas=(0.9, 0.95)`。
4. **学习率调度**：线性 warmup + cosine 衰减到 `min_lr`。
5. **稳定性**：每步梯度范数裁剪到 1.0。
6. **测量三件套**：每步训练 loss、每 K 步留出集 loss（`evaluate_model`）、每 K 步固定 prompt 的生成样本（`generate_and_print_sample`）。
7. **可持久化的日志**：每步一行 JSONL。

> 一句话：**把"训练"变成一个每一步都留下证据的过程**。但要注意 demo 的验证集与训练集不是同一分布，val loss 一路上升，这条曲线不能用来判断过拟合（第 3.7 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HERE` / `OUTPUTS` / `LOG_PATH` | 模块级常量 | 定位 `outputs/losses.jsonl`，导入时就创建目录 | 产物路径 |
| `TrainConfig` | dataclass | batch 4、上下文 32、80 步、每 20 步评估、4 个验证 batch、LR 3e-3→3e-4、warmup 10、wd 0.01、clip 1.0 | 训练超参数 |
| `ModelConfig` | dataclass | vocab 256、d 64、4 头、2 层 | 模型超参数 |
| `LayerNorm` … `GPTModel` | `nn.Module` | 第 35 节模型的精简副本（去掉了长度检查） | 被训练的模型 |
| `make_batches` | 生成器函数 | 用独立 `Generator` 无限地随机采样窗口，产出 `(inputs, targets)` | 数据加载 |
| `calc_loss_batch` | 函数 | 前向 + 展平 + `F.cross_entropy` | 训练目标 |
| `evaluate_model` | 函数（`@torch.no_grad()`） | 取前 `max_batches` 个验证 batch 求平均 loss，恢复训练状态 | 留出集评估 |
| `generate_and_print_sample` | 函数（`@torch.no_grad()`） | 独立随机数生成器 + top-k 采样，打印 token | 定性探针 |
| `build_param_groups` | 函数 | 一维或名为 `.bias/.shift/.scale` 的参数不衰减 | AdamW 分组 |
| `cosine_with_warmup` | 函数 | 给定步数返回学习率 | LR 调度 |
| `train` | 函数 | 主循环：设 LR → 取 batch → 反传 → 裁剪 → 更新 → 记录 → 探针 | 训练循环 |
| `_synthetic_byte_tokens` | 函数 | 周期 32 的随机模式 + 10% 噪声 | 合成数据 |
| `demo` | 函数 | 生成数据、建模型、训练、打印结果并断言 loss 下降 | 演示 |

数据流：`_synthetic_byte_tokens` → `make_batches` → `(inputs, targets)` `(4, 32)` → `GPTModel` → logits `(4, 32, 256)` → 交叉熵 → `backward` → `clip_grad_norm_` → `AdamW.step` → `record` → 写入 JSONL；每 20 步额外：`evaluate_model` + `generate_and_print_sample`。

---

## 3. 逐段精讲

### 3.1 模块级路径与配置

```python
HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)
LOG_PATH = OUTPUTS / "losses.jsonl"
```

- `Path(__file__).resolve().parent` 是 `code/` 目录的绝对路径；`/` 运算符拼接路径。无论从哪个目录运行脚本，日志都写到 `<小节>/outputs/losses.jsonl`。
- `mkdir(parents=True, exist_ok=True)` 在**导入时**执行：测试 `import main` 也会创建这个目录（已存在则什么都不做）。这种"导入有副作用"的写法在库代码里应避免。
- 两个 dataclass 分别管训练超参数和模型超参数。`ModelConfig` 默认 `dropout=0.1`，但 demo 中改成了 0.0。

### 3.2 模型副本

`LayerNorm`、`MultiHeadAttention`、`FeedForward`、`TransformerBlock`、`GPTModel` 是第 35 节的精简副本：结构、tying、std 0.02 初始化、残差投影 `1/√(2·num_layers)` 缩放都相同；区别是 `MultiHeadAttention.forward` 和 `GPTModel.forward` 都**去掉了序列长度检查**，`_init_weights` 改成了 `@staticmethod`。demo 中 `context_length=32`，`make_batches` 和生成函数都保证输入不超过 32，所以不会出问题。

### 3.3 `make_batches`：无限的批次生成器

```python
    generator = torch.Generator().manual_seed(seed)
    max_start = token_ids.numel() - context_length - 1

    while True:
        starts = torch.randint(0, max_start + 1, (batch_size,), generator=generator)
        inputs = torch.stack([token_ids[s : s + context_length] for s in starts.tolist()])
        targets = torch.stack(
            [token_ids[s + 1 : s + 1 + context_length] for s in starts.tolist()]
        )
        yield inputs, targets
```

- `yield` 让函数变成**生成器**：每次 `next(loader)` 运行到下一个 `yield` 并返回一个 batch，`while True` 意味着永不结束。
- 起点在 `[0, N − T − 1]` 内均匀采样（`randint` 上界不含，所以写 `max_start + 1`），保证目标的最后一个下标 `s + T ≤ N − 1` 不越界。
- 独立的 `torch.Generator`：同一个种子得到同一串 batch（测试 `test_seed_makes_batches_reproducible`），且不受全局随机数影响。
- 输入与目标错开一位：每一行提供 T 个"预测下一个 token"的训练信号。
- 开头两项校验：必须是一维张量、长度至少 `T + 1`。

### 3.4 `calc_loss_batch` 与 `evaluate_model`

```python
def calc_loss_batch(model, inputs, targets):
    logits = model(inputs)
    return F.cross_entropy(
        logits.reshape(-1, logits.size(-1)),
        targets.reshape(-1),
    )
```

- `(4, 32, 256)` → `(128, 256)`，目标 `(4, 32)` → `(128,)`。`F.cross_entropy` 内部做数值稳定的 log-softmax 并对 128 个位置取平均。
- 初始化时每个位置的分布接近均匀，loss ≈ `ln 256 = 5.545`；demo 第 0 步实测 5.5610，未训练模型在验证集上 5.554。

```python
@torch.no_grad()
def evaluate_model(model, val_loader, max_batches):
    was_training = model.training
    model.eval()
    total = 0.0
    count = 0
    for inputs, targets in val_loader:
        if count >= max_batches:
            break
        loss = calc_loss_batch(model, inputs, targets)
        total += float(loss.item())
        count += 1
    if was_training:
        model.train()
    return total / max(count, 1)
```

- `@torch.no_grad()` 作为**装饰器**，整个函数体都不记录计算图。
- 因为 `make_batches` 是无限生成器，必须用 `count >= max_batches` 主动 `break`。
- `max(count, 1)` 防止除零（虽然无限生成器不会出现 0 个 batch）。
- 状态恢复：只有原来处于训练模式才切回 `train()`。⚠️ 与第 35 节的 `try/finally` 不同，这里如果中途抛异常，模型会停留在 eval 模式。

### 3.5 `generate_and_print_sample`：局部随机数的探针

```python
    sample_gen = torch.Generator(device=prompt.device).manual_seed(seed)
    ...
        next_token = torch.multinomial(probs, num_samples=1, generator=sample_gen)
```

- 与第 35 节的 `generate` 相比，最重要的改进是**用独立的 `Generator`** 而不是 `torch.manual_seed`：探针采样不会扰乱训练的全局随机状态（训练中 dropout 依赖全局 RNG）。
- `train` 中每次探针传入 `seed=step`、`temperature=0.8`、`top_k=20`，所以不同探针点的样本可比（同一个 prompt，固定的随机流）。
- top-k 逻辑与第 35 节的 `top_k_filter` 相同，只是内联了。
- ⚠️ 打印的是 token id 而不是文本；对字节级数据可以用 `bytes(seq).decode("utf-8", errors="replace")` 直接显示（讲义练习 2）。

### 3.6 `build_param_groups` 与 `cosine_with_warmup`

```python
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if param.dim() < 2 or name.endswith(".bias") or name.endswith(".shift") or name.endswith(".scale"):
            no_decay.append(param)
        else:
            decay.append(param)
```

- 规则："一维、或名字像 bias/shift/scale" → 不衰减；其余（线性层权重、embedding 表）→ 衰减。实测 demo 模型：衰减组 10 个张量（`tok_embed`、`pos_embed`、两层各 `qkv/out_proj/fc1/fc2` 的权重）共 116,736 个元素；不衰减组 18 个张量共 1,792 个元素。
- `named_parameters()` 对共享参数去重，tied 的 `lm_head.weight` 不会出现第二次——否则同一参数会在优化器里被更新两次。
- 名字规则与维度规则其实重复（本模型中 bias/shift/scale 都是一维），名字规则起"双保险"作用。
- 返回的列表直接传给 `torch.optim.AdamW`：每个字典是一个 param group，可以有自己的 `weight_decay`。

```python
def cosine_with_warmup(step, warmup_steps, total_steps, max_lr, min_lr):
    if step < warmup_steps:
        return max_lr * (step + 1) / max(warmup_steps, 1)
    progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
    progress = min(max(progress, 0.0), 1.0)
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    return min_lr + (max_lr - min_lr) * cosine
```

| step | LR（默认配置，实测） | 说明 |
|------|------|------|
| 0 | 3.0e-4 | `(0+1)/10 × 3e-3`，第 0 步就不是 0 |
| 9 | 3.0e-3 | warmup 最后一步已到峰值 |
| 10 | 3.0e-3 | cosine 起点，progress = 0 |
| 45 | 1.65e-3 | progress = 0.5，正好在中点 |
| 79 | 3.01e-4 | progress = 69/70，没有精确到 `min_lr` |
| 80 | 3.0e-4 | 训练循环到不了这一步 |

- `min(max(progress, 0), 1)` 把进度夹在 `[0, 1]`，超过 `total_steps` 后保持 `min_lr`。
- 第 9、10 两步都是峰值，最后一步差一点到 `min_lr`——这是"`step + 1`"与"`total_steps − warmup_steps`"两种计数方式混用造成的小的 off-by-one，不影响训练效果，但测试 `test_decay_reaches_min_lr_at_end` 用 `step=100=total_steps` 才能命中 `min_lr`。

### 3.7 `train`：主循环

```python
    torch.manual_seed(cfg.seed)
    optimizer = torch.optim.AdamW(
        build_param_groups(model, cfg.weight_decay),
        lr=cfg.max_lr,
        betas=(0.9, 0.95),
    )
    train_loader = make_batches(train_tokens, cfg.batch_size, cfg.context_length, seed=cfg.seed)

    if log_path.exists():
        log_path.unlink()
```

- `betas=(0.9, 0.95)`：β2 比默认的 0.999 小，二阶矩对近期梯度更敏感，是 LLM 预训练的常见设置。
- 开始前**删除旧日志**：保证日志只对应这一次运行；代价是无法续训（讲义说 JSONL 可以用于"resume training by reading the last step"，但代码没有实现这一点）。

```python
    for step in range(cfg.num_steps):
        lr = cosine_with_warmup(step, cfg.warmup_steps, cfg.num_steps, cfg.max_lr, cfg.min_lr)
        for group in optimizer.param_groups:
            group["lr"] = lr

        inputs, targets = next(train_loader)
        optimizer.zero_grad(set_to_none=True)
        loss = calc_loss_batch(model, inputs, targets)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=cfg.grad_clip)
        optimizer.step()

        record = {"step": step, "train_loss": float(loss.item()), "lr": lr}
```

- 手动给每个 param group 写入 LR，而不是用 `torch.optim.lr_scheduler`：调度完全由 `step` 决定，续训时只需保存步数。
- 顺序：清梯度 → 前向 → 反传 → **裁剪** → 更新。裁剪必须在 `backward` 之后、`step` 之前。
- `clip_grad_norm_` 返回裁剪前的总范数，代码丢弃了它。我们另行记录：前 5 步范数 2.72、2.65、2.02、1.66、1.75，80 步里 78 步大于 1 被裁剪——在这个小模型上，裁剪几乎每步都在起作用。把它写进 `record` 是很有价值的改进。

```python
        if (step + 1) % cfg.eval_every == 0 or step == cfg.num_steps - 1:
            val_loader = make_batches(
                val_tokens, cfg.batch_size, cfg.context_length, seed=cfg.seed + 1
            )
            val_loss = evaluate_model(model, val_loader, cfg.eval_batches)
            record["val_loss"] = val_loss
            print(...)
            generate_and_print_sample(
                model, prompt, cfg.sample_max_new_tokens, temperature=0.8, top_k=20, seed=step
            )

        records.append(record)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
```

- 探针在第 19、39、59、79 步（`(step+1) % 20 == 0`）。每次用 `seed + 1` 重新建验证 loader，所以 4 个验证 batch 每次完全相同，结果可比。
- 每步以追加模式（`"a"`）打开、写一行、关闭。频繁开关文件稍慢，但任何时刻崩溃都只损失最后一行，日志始终可读（讲义 "Resumable JSONL logging"）。
- ⚠️ 讲义说输出有 "per step loss line"，但代码只在探针步打印，其余步只写日志。

### 3.8 合成数据与 demo

```python
    rng = torch.Generator().manual_seed(seed)
    base = torch.randint(0, vocab_size, (32,), generator=rng)
    repeats = (length + base.numel() - 1) // base.numel()
    tokens = base.repeat(repeats)[:length]
    noise = torch.randint(0, vocab_size, (length,), generator=rng)
    mask = (torch.rand(length, generator=rng) < 0.1)
    tokens = torch.where(mask, noise, tokens)
```

- 先采 32 个 token 作为"基础模式"，重复铺满；再以 10% 的概率替换为随机 token（实测训练集 10.3% 的位置与模式不同）。
- `(length + n − 1) // n` 是向上取整的整数写法。
- 理论下限：模式 token 的概率 `0.9 + 0.1/256`，其余各 `0.1/256`，熵约 **0.876 nats**（测验 Q10）。

⚠️ **demo 的关键问题**：

```python
    train_tokens = _synthetic_byte_tokens(length=4096, vocab_size=mcfg.vocab_size, seed=1)
    val_tokens = _synthetic_byte_tokens(length=1024, vocab_size=mcfg.vocab_size, seed=2)
```

两个种子产生**两种完全不同的基础模式**（32 个 token 中只有 3 个值重合）。模型学会训练模式后，在验证集上的预测比均匀猜测还差：val loss 6.58 → 7.53 → 7.32 → 7.49，都高于 `ln 256 = 5.55`。docstring 写"the eval loss should drop visibly during the demo"，与实际相反。修正方法是从同一条序列切出训练段与验证段（测验 Q9：同分布切分后 val loss 为 2.754 → 1.524 → 1.337 → 1.301）。

- 另一个小问题：`print(f"model params : {sum(p.numel() for p in GPTModel(mcfg).parameters()):,} (untied count)")` 打印的 118,528 其实是 **tied** 参数量（`parameters()` 会去重），untied 应为 134,912；而且为了计数多构造了一个模型，消耗了全局随机数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 无限生成器 + 随机起点 | 实现简单，任意步数都能取 batch | 不保证每个 epoch 覆盖全部数据；生产用 `DataLoader` + 分片 + 确定性 sampler |
| 独立 `Generator` 采样数据与探针 | 可复现，不互相干扰 | 续训时还要恢复生成器状态或快进（测验 Q11） |
| 手写 LR 调度并写入 param group | 调度是 `step` 的纯函数，续训简单 | 首尾有 off-by-one；可以用 `LambdaLR` 统一管理 |
| 按维度 + 名字分组 weight decay | 讲义推荐的标准做法 | 名字规则依赖命名习惯；embedding 是否衰减有争议 |
| 每步都裁剪到 1.0 | 防止坏 batch 毁掉训练 | 小模型上几乎每步都触发（78/80）；应记录裁剪前的范数 |
| 固定种子的验证 batch | 跨运行可比 | demo 的验证集分布错误，导致指标失去意义 |
| 每步追加 JSONL | 崩溃安全、易于 grep/绘图 | 每步开关文件；开始时删除旧日志，无法续训 |
| 定性探针打印 token id | 字节级 vocab，实现简单 | 可读性差；可解码成文本 |
| 模型代码复制一份 | 每节自包含 | 与第 35 节不同步（这里删掉了长度检查） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `pathlib.Path` 与 `/` | `HERE.parent / "outputs"` | 面向对象的路径拼接 |
| `Path.mkdir` / `exists` / `unlink` / `open` | `OUTPUTS.mkdir(parents=True, exist_ok=True)`、`log_path.unlink()` | 建目录、判断存在、删除文件、打开文件 |
| 生成器函数 | `make_batches` 中的 `while True: ... yield inputs, targets` | 惰性产出，配合 `next()` 使用 |
| `typing.Iterator` 注解 | `-> Iterator[tuple[torch.Tensor, torch.Tensor]]` | 标注返回一个迭代器 |
| `next()` | `inputs, targets = next(train_loader)` | 从迭代器取下一个元素 |
| 装饰器 | `@torch.no_grad()`、`@staticmethod`、`@dataclass` | 包装函数/类，改变其行为 |
| 链式调用 | `torch.Generator().manual_seed(seed)` | `manual_seed` 返回生成器本身，可以链式书写 |
| 列表推导 + `torch.stack` | `torch.stack([token_ids[s : s + T] for s in starts.tolist()])` | 把若干一维张量堆成二维 |
| `for ... break` | `evaluate_model` 中 `if count >= max_batches: break` | 从无限迭代器中只取有限个 |
| 字典字面量与增量修改 | `record = {...}`、`record["val_loss"] = val_loss` | 先建基本记录，探针步再加字段 |
| `json.dumps` / `json.loads` | `fh.write(json.dumps(record) + "\n")` | 对象 ↔ JSON 字符串，一行一条即 JSONL |
| `with open(...)` 追加模式 | `with log_path.open("a", encoding="utf-8") as fh:` | 自动关闭文件；`"a"` 表示追加 |
| `min(max(x, lo), hi)` | `progress = min(max(progress, 0.0), 1.0)` | 把值夹在区间内 |
| 整数向上取整 | `(length + n - 1) // n` | 不用 `math.ceil` 的整数写法 |
| `torch.where` 三元选择 | `torch.where(mask, noise, tokens)` | 按布尔条件逐元素选择 |
| 多条件 `or` | `param.dim() < 2 or name.endswith(".bias") or ...` | 短路求值 |
| f-string 格式符 | `{step:4d}`、`{lr:.5f}`、`{train_tokens.numel():,}` | 宽度、小数位、千分位 |
| 默认参数为模块常量 | `log_path: Path = LOG_PATH` | 测试可以传入临时路径 |
| `assert` 带消息 | `assert last_loss < first_loss, "training loss should decrease ..."` | 运行时自检 |

---

## 6. 运行结果解读

为了不覆盖仓库里已有的 `outputs/losses.jsonl`，我们把 `main.py` 复制到临时目录运行（Python 3.13、torch 2.14 CPU，约 4.4 秒）。生成的日志与仓库中的 `losses.jsonl` 逐行一致（仅浮点末位有差异）。

```text
train tokens   : 4,096
val tokens     : 1,024
model params   : 118,528 (untied count)       ← 实为 tied 参数量

Training run:
step   19 | lr 0.00289 | train_loss 2.9560 | val_loss 6.5783
  sample tokens          : [7, 11, 13, 17, 137, 139, 134, 156, 156, 157, 142, 68, 37, 235, 72, 72, 212, 237, 134, 140]
step   39 | lr 0.00201 | train_loss 1.1025 | val_loss 7.5346
  sample tokens          : [7, 11, 13, 17, 71, 237, 129, 101, 146, 212, 139, 192, 144, 129, 204, 71, 237, 252, 234, 156]
step   59 | lr 0.00086 | train_loss 1.1247 | val_loss 7.3151
  sample tokens          : [7, 11, 13, 17, 71, 237, 252, 134, 25, 178, 20, 254, 101, 146, 212, 139, 252, 234, 156, 157]
step   79 | lr 0.00030 | train_loss 1.0735 | val_loss 7.4909
  sample tokens          : [7, 11, 13, 17, 156, 157, 142, 50, 68, 37, 235, 140, 72, 255, 137, 203, 133, 79, 192, 144]

Final log records (last 3):
  {'step': 77, 'train_loss': 0.8987806439399719, 'lr': 0.00031221782161328814}
  {'step': 78, 'train_loss': 1.0979820489883423, 'lr': 0.00030543470310642724}
  {'step': 79, 'train_loss': 1.07351553440094, 'lr': 0.0003013593601692253, 'val_loss': 7.490936875343323}

First step train_loss  : 5.5610
Last step train_loss   : 1.0735
Training loop check passed.
```

逐项解读：

- **train loss 5.56 → 约 1.07**：起点 ≈ `ln 256`；终点接近理论下限 0.876（第 77 步甚至到了 0.899）。单步 loss 只基于 128 个目标，波动较大（0.90、1.10、1.07）。
- **val loss 6.58 → 7.49**：高于 `ln 256`，原因是验证集是另一种模式（3.8 节）。exp(7.49) ≈ 1790 的困惑度意味着模型在验证集上比"在 256 个 token 中瞎猜"还差。
- **样本**：训练集的基础模式是 `[37, 235, 140, 72, 255, 137, 203, 133, 79, 192, 144, 129, 204, 71, 237, 252, 134, 25, 178, 20, 254, 101, 146, 212, 139, 252, 234, 156, 157, 142, 50, 68]`。第 79 步的样本 `156, 157, 142, 50, 68, 37, 235, 140, 72, 255, 137, 203, 133, 79, 192, 144` 与它的一段完全吻合（`...156, 157, 142, 50, 68` 接回开头 `37, 235, 140, ...`）——定性探针清楚地表明模型学会了训练模式，这正是讲义说的"loss 看不出、样本能看出"的信息。
- **LR 列**：0.00289（第 19 步，cosine 刚开始下降）→ 0.00030（第 79 步，接近 `min_lr`）。

---

## 7. 动手改一改

1. **修正验证集**：用同一条序列切出训练段与验证段（测验 Q9），观察 val loss 先降后平；再把训练步数加到 300，看 train/val 差距何时拉开。
2. **讲义练习 1**：为 `build_param_groups` 补测试——两组不重叠、不遗漏、tied 参数只出现一次、embedding 在衰减组（参考测验 Q12，我们实测新增 3 个测试全部通过）。
3. **讲义练习 2**：用一小段真实文本的字节代替合成 token，并把样本解码成字符串打印。
4. **记录梯度范数与吞吐量（讲义练习 5）**：把 `clip_grad_norm_` 的返回值和 `tokens/sec`（`batch_size × context_length / 每步耗时`）写进 `record`。
5. **讲义练习 4**：每 `eval_every` 步保存 `{"step", "model", "optimizer"}` checkpoint，实现 `resume_from`；恢复时把数据生成器快进 `step` 次。我们实测这样恢复后每步 loss 与不中断训练逐位相同，不快进则不同（测验 Q11）。
6. **修正调度的 off-by-one**：让 warmup 从 0 开始、最后一步精确等于 `min_lr`，并修改相应测试。

---

## 8. 常见坑

- **验证集分布不对**：用不同的生成过程/不同来源做验证集，曲线会误导你（本节 demo）。
- **忘记错位**：目标等于输入时 loss 能降到接近 0，但模型什么都没学会。
- **`zero_grad` 放错位置**：放在 `backward` 之后会清掉刚算出的梯度；不清零则梯度在步与步之间累加。
- **裁剪放在 `step` 之后**：等于没裁剪。
- **对 LayerNorm `scale` 做 weight decay**：慢慢把它拉向 0，削弱归一化。
- **tied 参数被分进两个组**：自己用 `named_parameters(remove_duplicate=False)` 遍历时会出现，导致同一参数被更新两次。
- **评估时忘记 `eval()` / `no_grad`**：dropout 让结果不可复现，计算图浪费显存。
- **用 `torch.manual_seed` 给探针采样**：会改变训练的随机流（本节用独立 `Generator` 避免了）。
- **运行 demo 覆盖了日志**：`train` 一开始就删除旧日志；需要保留时请改 `log_path`。

---

## 9. 测试在验证什么

`tests/test_training.py` 共 14 个 `unittest` 测试，用 `pathlib` 把 `code/` 加入 `sys.path` 后导入。训练测试把日志写到 `tempfile.TemporaryDirectory()`，不会改动 `outputs/`。实际运行：`python3 -m pytest -q` → `14 passed in 2.47s`。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `BatchTests` | `test_target_is_input_shifted_by_one` | 用 `arange(200)` 作为 token，逐元素检查 `targets[:, c] == inputs[:, c+1]` |
| | `test_rejects_short_token_stream` | 长度 5 < T+1 = 9 时报错（注意要 `next()` 才会执行生成器体） |
| | `test_seed_makes_batches_reproducible` | 同一种子两次得到相同 batch |
| `LossTests` | `test_loss_returns_scalar` | loss 是 0 维标量且为正 |
| `EvalTests` | `test_evaluate_returns_positive_loss_and_restores_training_mode` | dropout=0.5 的模型在训练模式下评估后仍为训练模式 |
| | `test_evaluate_keeps_model_in_eval_when_called_during_eval` | 原来是 eval 就保持 eval |
| `ParamGroupTests` | `test_layer_norm_scale_and_shift_in_no_decay_group` | LN 的 `scale/shift` 在不衰减组 |
| | `test_linear_weights_in_decay_group` | `fc1.weight` 在衰减组 |
| | `test_biases_in_no_decay_group` | `fc1.bias` 在不衰减组 |
| `ScheduleTests` | `test_warmup_starts_below_max` | 第 0 步 LR 在 (0, max) 之间 |
| | `test_peak_at_warmup_end` | 第 9 步（warmup=10）等于 max |
| | `test_decay_reaches_min_lr_at_end` | `step = total_steps` 时等于 min（训练循环实际到不了这一步） |
| `TrainingLoopTests` | `test_short_run_writes_jsonl_and_reduces_loss` | 30 步训练：JSONL 恰好 30 行、第一行 step=0、最后一行有 `val_loss`、train loss 下降 |
| `GenerationProbeTests` | `test_sample_returns_prompt_plus_new_tokens` | 3 + 4 = 7 个 token |

测试没有覆盖的地方：验证 loss 是否下降（如果加上这条断言，demo 的验证集问题会立刻暴露）、梯度裁剪是否生效、两组参数是否构成完整划分、embedding 是否在衰减组、`evaluate_model` 在异常时的状态恢复。
