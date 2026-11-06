# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 40 节 从零实现直接偏好优化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下，CPU 约 6 秒；原始 margin 上升且 loss 下降时退出码 0）；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests` ｜ **依赖**：`torch`、`numpy`（第三方）；`math`、`random`、`sys`、`dataclasses`、`typing`（标准库）。不写文件，不需要网络。

---

## 1. 这份代码在考察什么

这份代码把 DPO 论文中的一行公式落成可运行、可测试的代码：

1. **DPO loss**：`L = −log σ(β·[(log π_θ(y_w) − log π_ref(y_w)) − (log π_θ(y_l) − log π_ref(y_l))])`，用数值稳定的 `F.logsigmoid` 实现。
2. **序列对数概率**：`sequence_log_prob` 拼接 prompt + completion，只对 completion 位置取 log-prob 并求和。
3. **参考模型不变性**：参考模型冻结、其 log-prob 训练前一次性缓存、策略从参考模型复制权重。
4. **训练循环**：对 12 个 (prompt, chosen, rejected) 三元组逐个计算 loss 并更新策略。
5. **变体与诊断工具**：`ipo_loss`、`length_normalised_log_prob`、`margin_table`。
6. **测试锁定数学性质**：零 margin 时 loss = ln 2、梯度符号、参考偏移抵消、参考 log-prob 不变等。

> 一句话：**DPO = 四个对数概率 + 一个 logsigmoid，奖励模型和 PPO 都被闭式解吸收掉了**。但运行结果同时展示了 DPO 的三个经典问题：长度偏差（训练前原始 margin 就有 +257）、sigmoid 饱和后的过度优化（loss 第 2 个 epoch 起为 0.0000、rejected 被压低约 107 nats）、以及 chosen 的对数概率本身也在下降。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `InstructionTokenizer` | 类 | `encode_prompt` → `[INST] 字节 [RESP]`；`encode_completion` → 字节 | 与第 39 节相同的模板 |
| `CausalSelfAttention` / `Block` / `TinyGPT` | `nn.Module` | 2 层、hidden 64、4 头、max_len 96 的因果 decoder（139,008 参数） | 策略 / 参考模型 |
| `make_preferences` | 函数 | 12 个三元组：chosen 简短准确，rejected 啰嗦或跑题 | 偏好数据 |
| `sequence_log_prob` | 函数 | completion 的 token 级 log-prob 之和；含左截断逻辑 | `log π(y|x)` |
| `dpo_loss` | 函数 | 返回 `(loss, margin)`，margin = log-ratio 之差（未乘 β） | DPO 目标 |
| `ipo_loss` | 函数 | `(margin − 1/(2β))²` | IPO 变体 |
| `length_normalised_log_prob` | 函数 | 序列 log-prob ÷ completion 长度 | 长度偏差诊断 |
| `MarginRow` / `margin_table` / `print_margin_table` | dataclass / 函数 | 每个三元组在给定模型下的 chosen、rejected log-prob 与原始 margin | 调试报表 |
| `DPOConfig` | dataclass | β 0.2、lr 1e-3、30 epoch、warmup 8 epoch | 超参 |
| `build_models` | 函数 | 建参考与策略，策略 `load_state_dict` 参考，冻结参考 | 参考不变性 |
| `warmup_pretrain` | 函数 | 在 prompt + chosen 上做 next-token 训练，给参考模型一个"SFT 起点" | 简化版 SFT |
| `DPOReport` / `evaluate_margins` / `train_dpo` | — | 训练循环与原始 margin 评估 | 训练 |
| `run_demo` | 函数 | 建模 → warmup → 复制 → DPO → 报表 → 退出码 | 演示 |

数据流：`make_preferences` → `build_models` → 解冻参考 → `warmup_pretrain(参考)` → `policy.load_state_dict(参考)` → 冻结参考 → `train_dpo`（缓存参考 log-prob → 每个三元组：策略 log-prob ×2 → `dpo_loss` → Adam）→ `margin_table` → 比较 initial / final。

---

## 3. 逐段精讲

### 3.1 模板与模型：与第 39 节同构，但更简

```python
    def encode_prompt(self, prompt: str) -> List[int]:
        ids = [self.INST_ID]
        ids.extend(prompt.encode("utf-8", errors="ignore"))
        ids.append(self.RESP_ID)
        return ids
```

- prompt 编码为 `[INST] 字节 [RESP]`，completion 只是字节，**没有 EOS**——与第 39 节同样的问题：偏好"更短的回答"无法被模型表达成"在这里停止"。
- `CausalSelfAttention` 只有因果 mask，没有 key padding mask，也没有 `nan_to_num`：因为本节每次只前向一条序列，不存在 padding。
- `TinyGPT` 参数量实测 139,008：token 260×64 = 16,640，位置 96×64 = 6,144，每 block 49,728，×2 = 99,456，`ln_f` 128，head 260×64 = 16,640（不 tie）。

### 3.2 偏好数据：内置的长度捷径

```python
        {
            "prompt": "What is the capital of France?",
            "chosen": "Paris.",
            "rejected": "France is in Europe and has many beautiful cities including Paris.",
        },
```

- 12 条覆盖首都、算术、列表、定义、代码 5 类（讲义说"same task families as lesson 39"）。
- **注意**：实测长度：chosen 2–48 字节，rejected 46–78 字节，**每一条 rejected 都比 chosen 长**。因为序列 log-prob 是逐 token 求和，长度本身就决定了大部分 margin：随机初始化的模型平均原始 margin 已是 +293（例如第一条 chosen −34.8、rejected −372.9）。这是讲义 stretch goal 1 所说"length bias"的极端版本：在这个 fixture 上，"偏好"与"长度"完全混在一起。

### 3.3 `sequence_log_prob`：只对 completion 计分

```python
    full = list(prompt_ids) + list(completion_ids)
    if len(full) > model.max_len:
        full = full[-model.max_len :]
        prompt_len = max(0, len(full) - len(completion_ids))
    else:
        prompt_len = len(prompt_ids)
    ids = torch.tensor([full], dtype=torch.long, device=next(model.parameters()).device)
    logits = model(ids)
    log_probs = F.log_softmax(logits, dim=-1)
    completion_targets = torch.tensor(full[prompt_len:], dtype=torch.long, device=ids.device)
    pred_positions = torch.arange(prompt_len - 1, len(full) - 1, device=ids.device)
    if prompt_len == 0:
        pred_positions = torch.arange(0, len(full) - 1, device=ids.device)
        completion_targets = torch.tensor(full[1:], dtype=torch.long, device=ids.device)
    gathered = log_probs[0, pred_positions, completion_targets]
    return gathered.sum()
```

- 核心对齐：completion 第 k 个 token 位于下标 `prompt_len + k`，由下标 `prompt_len + k − 1` 的输出预测，所以 `pred_positions` 从 `prompt_len − 1`（RESP 位置）开始。例：prompt 长 4、completion 长 3 → `pred_positions = [3, 4, 5]`，`targets = full[4:7]`。
- `log_probs[0, pred_positions, completion_targets]`：两个等长索引张量做**成对**的高级索引，一次取出每个位置上目标 token 的 log-prob，形状 `(len(completion),)`。
- `F.log_softmax` 比 `log(softmax)` 数值稳定。
- `next(model.parameters()).device`：从模型参数推断设备，保证输入张量与模型在同一设备上。
- 空 completion 返回 0（测试 `test_log_prob_of_empty_completion_is_zero`），任何非空 completion 的结果 ≤ 0（`test_log_prob_is_negative_or_zero`）。
- **注意**：**左截断**：超过 `max_len` 时从左边丢 token，保留 completion。fixture 中 France 的 rejected 拼起来 98 个 token，会丢掉 INST 和 `'W'`——策略与参考用同一套截断，log-ratio 仍然自洽，但条件分布变了。
- **注意**：`prompt_len == 0` 分支：completion 本身超长时，保留部分的**第一个** token 也不计分（它没有前文），实测 `max_len = 8`、completion 长 10 时只累加 7 项。本 fixture 不会触发。

### 3.4 `dpo_loss` 与 `ipo_loss`

```python
def dpo_loss(logp_w_pol, logp_l_pol, logp_w_ref, logp_l_ref, beta):
    diff_w = logp_w_pol - logp_w_ref
    diff_l = logp_l_pol - logp_l_ref
    margin = diff_w - diff_l
    z = beta * margin
    loss = -F.logsigmoid(z)
    return loss, margin
```

- 逐行对应讲义公式：`diff_w`、`diff_l` 是两条回答的 log-ratio（乘 β 即隐式奖励 `r̂`），`z` 是 sigmoid 的参数。
- `-F.logsigmoid(z)` 等于 `softplus(−z) = log(1 + e^{−z})`，在 z 很大或很小时都不会溢出；手写 `-torch.log(torch.sigmoid(z))` 在 z ≪ 0 时会得到 `log(0) = −inf`。
- 几个可以手算的值（β = 0.2，实测）：margin 0 → 0.693；margin +5 → 0.313；margin −5 → 1.313；margin +98 → 3.1×10⁻⁹。
- 梯度：`∂L/∂logp_w_pol = −β·σ(−z)`。β = 1、z = 0 时为 −0.5（autograd 实测）。
- **注意**：返回的 `margin` 是 log-ratio 之差（未乘 β），文档字符串称之为"implicit reward difference"不准确——按讲义定义，隐式奖励差是 `β × margin = z`。
- `ipo_loss` 用 `(margin − 1/(2β))²`：在 margin 超过目标 `1/(2β)` 时会把它往回拉，不会饱和。讲义写的是简化版 `(z − 1)²`，形式不同但思想一致。

### 3.5 `build_models` 与 `warmup_pretrain`：构造"SFT 参考模型"

```python
    torch.manual_seed(cfg.seed)
    reference = TinyGPT(cfg.vocab, cfg.hidden, cfg.heads, cfg.depth, cfg.max_len)
    torch.manual_seed(cfg.seed)  # reseed so the policy weights match before any training
    policy = TinyGPT(cfg.vocab, cfg.hidden, cfg.heads, cfg.depth, cfg.max_len)
    policy.load_state_dict(reference.state_dict())
    for p in reference.parameters():
        p.requires_grad = False
    reference.eval()
```

- 讲义 "Reference Invariance" 的三条性质在这里落地：策略复制参考、参考 `requires_grad=False`、参考 `eval()`。第二次 `manual_seed` 是多余的（随后的 `load_state_dict` 已经保证一致），但无害。
- `warmup_pretrain` 在 `prompt + chosen` 的完整序列上做普通 next-token 训练（**不 mask prompt**），8 个 epoch 后 loss 从 4.71 降到 0.586。它扮演"SFT 模型"的角色：真实流程中参考模型就是在 chosen 风格数据上 SFT 过的模型。
- `run_demo` 的顺序很关键：解冻参考 → warmup → **把 warmup 后的权重复制给策略** → 重新冻结参考。若先复制再 warmup，策略和参考就不在同一起点，第一步的 loss 就不再是 ln 2。

### 3.6 `train_dpo`：缓存参考 log-prob + 逐三元组更新

```python
    opt = torch.optim.Adam(policy.parameters(), lr=cfg.lr)
    ref_logps: List[Tuple[torch.Tensor, torch.Tensor]] = []
    with torch.no_grad():
        for tri in triples:
            ...
            lp_w_ref = sequence_log_prob(reference, prompt, chosen).detach()
            lp_l_ref = sequence_log_prob(reference, prompt, rejected).detach()
            ref_logps.append((lp_w_ref, lp_l_ref))
    report.initial_margin = evaluate_margins(policy, reference, tok, triples)
    for ep in range(1, cfg.epochs + 1):
        policy.train()
        for tri, (lp_w_ref, lp_l_ref) in zip(triples, ref_logps):
            ...
            lp_w_pol = sequence_log_prob(policy, prompt, chosen)
            lp_l_pol = sequence_log_prob(policy, prompt, rejected)
            loss, margin = dpo_loss(lp_w_pol, lp_l_pol, lp_w_ref, lp_l_ref, beta=cfg.beta)
            opt.zero_grad()
            loss.backward()
            opt.step()
```

- **优化器只包含策略参数**：参考模型从结构上就不可能被更新。
- **参考 log-prob 预计算一次**：参考冻结，所以它的 log-prob 是常数；缓存后每步省掉两次前向。这也是大模型 DPO 的常用省显存技巧。`.detach()` 在 `no_grad` 中是多余的保险。
- 每个三元组一步，batch size = 1、顺序固定不打乱：30 epoch × 12 = **360 次更新**，讲义说的"thirty steps"指的其实是 epoch。
- 日志里的 `margin` 是**隐式 margin**（相对参考的 log-ratio 之差），而 `evaluate_margins` 返回的是**原始 margin**（策略下 chosen − rejected）。两者同名，含义不同：`原始(策略) = 原始(参考) + 隐式`。
- `evaluate_margins` 接收 `reference` 参数但没有使用。

### 3.7 `run_demo`：退出条件

```python
    if report.final_margin <= report.initial_margin:
        ...
        return 1
    if report.losses[-1] >= report.losses[0]:
        ...
        return 1
    return 0
```

- 两个条件：原始 margin 上升、epoch 平均 loss 下降。由于 sigmoid loss 的梯度方向总是"拉大 margin"，只要能训练，这两个条件几乎必然成立——它们证明"实现方向正确"，不证明"学到了有用的偏好"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `F.logsigmoid` 实现 loss | 数值稳定 | — |
| 参考 log-prob 预缓存 | 参考冻结，省前向与显存 | 数据增强/在线采样时无法缓存；生产中也常用"LoRA 关闭即参考"的做法 |
| 优化器只放策略参数 + 参考 `requires_grad=False` + `eval()` | 三重保证参考不变 | — |
| warmup 代替真正的 SFT | 让参考有非平凡分布，自包含 | warmup 不 mask prompt、只训 12 条；真实流程用第 39 节式的 SFT 模型 |
| 序列 log-prob 求和 | 与 DPO 论文一致 | 长度偏差；可选长度归一化（需重调 β） |
| 左截断超长序列 | 保留完整 completion | 丢掉 INST 等前缀；生产中常截断 completion 尾部或过滤 |
| batch size = 1、不打乱 | 代码最简单 | 梯度噪声大、顺序效应明显；生产用小批量，chosen/rejected 同 batch |
| 30 epoch、无早停 | 让 margin "可见地增长" | 12 条数据上严重过度优化（loss ≈ 0、rejected −107）；生产 1–3 epoch 并监控 KL |
| 日志与评估都叫 "margin" | — | 一个是隐式 margin，一个是原始 margin，容易误读；应分别命名 |
| 无 EOS | 沿用第 39 节模板 | 短回答偏好无法变成"停止"行为 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `list.extend` 接收 bytes | `ids.extend(prompt.encode("utf-8"))` | 遍历 bytes 得到整数，逐个追加 |
| `next(iter)` | `next(model.parameters()).device` | 取生成器的第一个元素 |
| 负数切片 | `full[-model.max_len:]` | 取最后 N 个元素（左截断） |
| `torch.arange(a, b)` | `torch.arange(prompt_len - 1, len(full) - 1)` | 生成 `[a, b)` 的整数序列 |
| 成对高级索引 | `log_probs[0, pred_positions, completion_targets]` | 两个等长索引张量逐对取元素 |
| 返回元组 + 类型注解 | `-> Tuple[torch.Tensor, torch.Tensor]`，`loss, margin = dpo_loss(...)` | 多返回值与解包 |
| 条件表达式 | `target = 1.0 / (2.0 * beta) if beta > 0 else 0.0` | 防止除以 0 |
| `@dataclass(frozen=True)` | `MarginRow` | 不可变的记录行 |
| `field(default_factory=list)` | `DPOReport.losses` | 可变默认值 |
| `Callable[[str], None]` 参数 | `log: Callable[[str], None] = print` | 注入日志函数，测试中传 `lambda s: None` |
| `zip` 并行遍历 | `for tri, (lp_w_ref, lp_l_ref) in zip(triples, ref_logps)` | 元组嵌套解包 |
| f-string 符号格式 | `{row.margin:+.4f}`、`{ep:>3d}` | `+` 强制显示正负号；右对齐 |
| 字符串切片 | `row.prompt[:35]` | 截断显示 |
| `with torch.no_grad():` | 缓存参考 log-prob、`margin_table` | 局部关闭梯度 |
| `.item()` / `float(...)` | `loss.item()`、`float(np.mean(margins))` | 0 维张量 / NumPy 标量转 Python 数 |
| `sys.exit(run_demo())` | 文件末尾 | 返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU；约 6.4 秒，退出码 0）：

```text
DPO FROM SCRATCH DEMO
triples=12 beta=0.2 lr=0.001 epochs=30

[warmup] short pretrain on chosen completions (8 epochs)...
         warmup final loss = 0.5856
         initial chosen-rejected margin = +257.1123     ← 原始 margin，主要来自长度差

[dpo training]
  epoch   1: loss=0.0687  margin=+38.4219               ← 隐式 margin；只有第一步 loss 是 ln2
  epoch   2: loss=0.0000  margin=+83.0720               ← 已饱和
  epoch   3: loss=0.0000  margin=+93.4099
  ...
  epoch  30: loss=0.0000  margin=+98.0749               ← 平台期：梯度≈0，但仍在缓慢漂移

[per-triple margins after training]
  margin   chosen_lp   rejected_lp   prompt
  +465.9271   -5.9865    -471.9135     What is the capital of France?
  +340.8153   -1.5386    -342.3539     Compute 2 + 3.
  +372.3200   -79.3108    -451.6308     Define function.
  ...

FINAL margin = +355.1893  (initial was +257.1123)        ← 257.11 + 98.07 ≈ 355.19
FINAL loss   = 0.0000  (epoch-1 loss was 0.0687)
```

逐项解读：

- **initial +257**：不是"参考模型已经偏好 chosen"那么简单。额外实测随机初始化（未 warmup）的模型就有 +293；长度归一化后参考模型的 margin 只有 3.66 nats/token。
- **loss 瞬间归零**：第 1 个 epoch 的第一步 z = 0、loss = ln 2；之后共享参数让所有三元组的 margin 迅速变大，epoch 1 平均只有 0.069，epoch 2 平均 1.1×10⁻⁶。margin ≈ 98 时 z ≈ 19.6，梯度在 float32 下已为 0——讲义说的"sigmoid 饱和抑制梯度"清晰可见。
- **chosen 并没有真正上升**：对比参考与策略（额外实测），12 个 chosen 中 10 个的 log-prob 下降，平均 −8.5（"Define function." 从 −32.9 降到 −79.3）；rejected 平均下降 106.6。margin 变大几乎全靠压低 rejected。长度归一化 margin 从 3.66 升到 4.87。
- **IPO 对照**（额外实测，把 `dpo_loss` 换成 `ipo_loss`，其余不变）：平均隐式 margin 前几个 epoch 振荡后稳定在 2.47–2.54（目标 1/(2β) = 2.5），rejected 只下降约 8.1、chosen 约 5.6——没有过度优化。

测试运行：`python3 -m pytest -q tests` → `19 passed in 2.81s`。

---

## 7. 动手改一改

1. **分清两种 margin**：把 `train_dpo` 日志里的 `margin` 改名为 `implicit_margin`，另外每个 epoch 打印隐式奖励准确率（`margin > 0` 的比例）和 `β × margin`。
2. **讲义 stretch goal 1**：加入 `length_normalise` 选项（测验 Q10），观察需要把 β 调到多大才能得到与原版相近的 loss 曲线。
3. **讲义 stretch goal 2 / 3**：用 `ipo_loss` 训练、再实现 label smoothing 版（测验 Q11），三者对比最终隐式 margin、chosen/rejected 绝对 log-prob 的变化。
4. **加 NLL 正则**：loss 改为 `dpo + λ·(−lp_w_pol / len(chosen))`，λ 取 0.1、1.0，观察 chosen 的 log-prob 是否不再下降。
5. **去掉长度捷径**：把 rejected 改写成与 chosen 等长但错误的答案（如 "Lyon."、"6."），重新看 initial margin 和训练后的生成偏好。
6. **批量化 + 打乱**：用测验 Q12 的 `batch_log_probs` 把 12 条三元组做成 batch（chosen 与 rejected 拼在一起），每 epoch 打乱，对比 loss 曲线与最终 margin。

---

## 8. 常见坑

- **策略与参考不从同一起点出发**：第一步 loss 不是 ln 2 就说明初始化有问题——这是最便宜的健全性检查。
- **参考模型漏冻结 / 进了优化器**：参考也被更新，KL 锚点漂移，DPO 退化。
- **对 prompt 也计分**：prompt 部分在策略与参考中的 log-ratio 会引入噪声，应只对 completion 计分。
- **off-by-one**：completion 第一个 token 应由 RESP 位置的输出预测（`prompt_len − 1`）。
- **用 `log(sigmoid(z))`**：z 很负时下溢为 `−inf`，应使用 `logsigmoid`。
- **只看原始 margin**：被长度主导；要看隐式 margin、奖励准确率、长度归一化 margin。
- **只看 loss 是否下降**：loss → 0 往往意味着过度优化；同时监控 chosen 的绝对 log-prob 和与参考的 KL。
- **截断位置不当**：左截断会丢掉模板标记，最好截 completion 尾部或在数据准备时过滤超长样本。

---

## 9. 测试在验证什么

`tests/test_main.py`（`unittest` 风格，pytest 可收集）共 19 个测试：

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `FixtureTests` | `test_preferences_have_chosen_and_rejected` | 至少 12 条，字段齐全，chosen ≠ rejected |
| `LossMathTests` | `test_zero_margin_loss_is_log_two` | 四项全为 0 时 loss = ln 2、margin = 0 |
| | `test_positive_margin_lowers_loss` / `test_negative_margin_raises_loss` | margin 正负决定 loss 低于/高于 ln 2 |
| | `test_reference_cancels_when_chosen_and_rejected_offsets_match` | 参考 log-prob 同时平移相同的量时 loss 不变（类比 `log Z(x)` 的抵消） |
| `GradientTests` | `test_gradient_increases_chosen_logprob` / `test_gradient_decreases_rejected_logprob` | 对 chosen 的梯度为负、对 rejected 的梯度为正 |
| `SequenceLogProbTests` | `test_log_prob_of_empty_completion_is_zero` | 空 completion 返回 0 |
| | `test_log_prob_is_negative_or_zero` | 对数概率 ≤ 0 |
| | `test_log_prob_sums_independently_of_dummy_batch` | 同一输入两次计算结果一致（确定性） |
| `ReferenceInvarianceTests` | `test_reference_parameters_have_requires_grad_false` | 参考参数全部冻结 |
| | `test_policy_initially_matches_reference` | 训练前策略与参考的 log-prob 相同 |
| | `test_reference_log_probs_unchanged_after_policy_training` | DPO 训练后参考 log-prob 不变 |
| `IPOTests` | `test_ipo_loss_is_non_negative` / `test_ipo_minimum_at_target_margin` | IPO loss ≥ 0，margin = 1/(2β) 时为 0 |
| `LengthNormaliseTests` | `test_length_normalised_matches_raw_divided_by_length` | 归一化值 = 原始值 ÷ 长度 |
| `MarginTableTests` | `test_margin_table_row_per_triple` | 每个三元组一行，`margin = chosen − rejected` |
| `TrainingTests` | `test_train_dpo_decreases_loss` / `test_train_dpo_increases_chosen_margin` | 小配置（1 层、6 条、5 epoch）下 loss 下降、原始 margin 上升 |

运行方式（在 `code/` 下）：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。实际结果：**19 passed**（约 2.8 秒）。

测试没有覆盖：chosen 的**绝对** log-prob 是否上升（实际上多数在下降）、长度偏差、截断分支（`prompt_len == 0`）、过度优化——这些都可以作为补充测试的练习。
