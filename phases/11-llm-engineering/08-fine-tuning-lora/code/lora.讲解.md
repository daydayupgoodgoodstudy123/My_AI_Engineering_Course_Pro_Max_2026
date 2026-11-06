# 代码讲解 · lora.py

> **所属小节**：阶段 11 · LLM 工程 · 第 08 节 Fine-Tuning 与 LoRA & QLoRA ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python lora.py`（无参数） ｜ **依赖**：`torch`（第三方，CPU 即可）；其余为标准库 `math`、`tempfile`、`os`

---

## 1. 这份代码在考察什么

这份代码不依赖 PEFT 等库，用几十行 PyTorch 从零实现 LoRA 的完整生命周期，并在一个 3 层 MLP 上演示：

1. **LoRA 层本身**：冻结原 `nn.Linear`，旁路加一个低秩分支 `x @ A @ B × (α/r)`，B 初始化为 0。
2. **注入（inject）**：遍历模型，把名字匹配的线性层替换成带 LoRA 的包装层，并冻结其他所有参数。
3. **参数统计**：可训练 / 冻结参数的数量和比例，以及不同 rank 下的变化。
4. **模拟 QLoRA**：对冻结的基座权重做分块 4-bit 量化再反量化，观察量化误差与内存。
5. **合并（merge）**：把 `(α/r)·(AB)ᵀ` 加回原权重，去掉 LoRA 层，验证输出不变。
6. **适配器的保存、加载与"多适配器"**：只保存 A、B，在另一个同基座模型上恢复。

> 一句话：**用一个玩具 MLP 把"冻结 → 注入 → 训练 → 量化 → 合并 → 存取适配器"整条 LoRA 工作流跑通**。数学部分（初始化、缩放、合并）是正确的；"NF4"、"QLoRA 内存"、"多适配器服务"三处则做了明显简化，正好用来对照真实实现。

> **运行情况说明**：编写本讲解的环境没有安装 PyTorch（按要求不自行安装），代码**未实际运行**。第 6 节中的参数量与内存字节数由张量形状精确算出；loss、量化误差等随机相关的数值只给出推断或 NumPy 模拟值，并逐一注明，绝非真实输出。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `LoRALayer` | `nn.Module` | 持有 A `(in, r)`、B `(r, out)`，前向 `x@A@B*scaling` | 低秩分支 ΔW |
| `LinearWithLoRA` | `nn.Module` | 包住原 `nn.Linear` 并冻结，输出 `linear(x) + lora(x)` | `y = Wx + (α/r)BAx` |
| `inject_lora` | 函数 | 冻结全模型 → 按名字匹配线性层 → `setattr` 替换 | target modules |
| `count_parameters` | 函数 | 统计 total / trainable / frozen / 百分比 | 参数效率 |
| `merge_lora_weights` | 函数 | `weight += (A@B*s).T`，再把包装层换回原 Linear | 合并适配器 |
| `quantize_to_nf4` / `dequantize_from_nf4` | 函数 | 每 64 个值一组，absmax/7 缩放，取整到 [-8, 7] | 分块 4-bit 量化（简化版） |
| `quantize_model` | 函数 | 对冻结的二维参数做"量化—反量化"，写回 fp32 | 模拟 QLoRA 的量化误差 |
| `train_lora` | 函数 | AdamW 只优化可训练参数，MSE 损失，小批量 | 训练循环 |
| `save_lora_adapter` / `load_lora_adapter` | 函数 | 只存取 LoRA 的 A、B（及 rank、alpha） | 适配器文件 |
| `create_demo_model` / `create_demo_data` | 函数 | 256→512→512→10 的 MLP；500 个随机样本 + 随机 one-hot 标签 | 演示数据 |
| `if __name__ == "__main__":` | 主程序 | Step 1–8 逐步演示 | — |

数据流：`create_demo_model` → `inject_lora`（Step 2）→ 多 rank 训练对比（Step 3）→ 新模型注入后 `quantize_model`（Step 4）→ `train_lora`（Step 5）→ `merge_lora_weights` 并比对输出（Step 6）→ `save/load_lora_adapter`（Step 7）→ 偶数/奇数样本各训一个适配器（Step 8）。

---

## 3. 逐段精讲

### 3.1 `LoRALayer`：低秩分支

```python
class LoRALayer(nn.Module):
    def __init__(self, in_features, out_features, rank=8, alpha=16):
        super().__init__()
        self.rank = rank
        self.alpha = alpha
        self.scaling = alpha / rank

        self.A = nn.Parameter(torch.randn(in_features, rank) * (1 / math.sqrt(rank)))
        self.B = nn.Parameter(torch.zeros(rank, out_features))

    def forward(self, x):
        return (x @ self.A @ self.B) * self.scaling
```

- **形状**：`x (N, in) @ A (in, r) → (N, r) @ B (r, out) → (N, out)`。先降到 r 维再升回去，这就是"低秩"：`A @ B` 是一个 `(in, out)` 矩阵，秩至多为 r。
- **与论文的对应**：论文写 `ΔW = BA`，`A ∈ R^{r×d_in}`、`B ∈ R^{d_out×r}`，作用在列向量上；代码按 PyTorch "行向量右乘"的习惯写成 `x @ A @ B`，所以代码的 A、B 是论文 A、B 的**转置**，角色不变：A 在输入侧随机初始化，B 在输出侧零初始化。
- **B = 0**：训练开始时 LoRA 分支输出恒为 0，模型行为与原模型完全一致。B 的梯度 `∂L/∂B = (xA)ᵀ · ∂L/∂y · s` 不为 0，所以第一步就能更新 B，之后 A 也开始有梯度。若 A、B 都为 0，两者梯度都恒为 0，永远学不动。
- **A 的尺度**：`randn × 1/√r` 让 A 每个元素的标准差为 `1/√r`（r = 8 时约 0.354），于是 `xA` 每个分量的方差约为 `in_features / r`（256/8 = 32，标准差约 5.7）。这和 PEFT 默认的 Kaiming-uniform（尺度随 `in_features` 缩放）不同：这里 `xA` 偏大，相当于放大了 B 的有效学习率。玩具任务上无伤大雅，真实模型中初始化尺度会影响稳定性。
- **`scaling = α/r`**：Step 2 中 `16/8 = 2.0`；Step 3 使用 `alpha=rank*2`，所以所有 rank 的缩放都是 2——这是社区"α = 2r"惯例的直接体现。

### 3.2 `LinearWithLoRA`：包装并冻结

```python
class LinearWithLoRA(nn.Module):
    def __init__(self, linear, rank=8, alpha=16):
        super().__init__()
        self.linear = linear
        self.lora = LoRALayer(linear.in_features, linear.out_features, rank, alpha)
        for param in self.linear.parameters():
            param.requires_grad = False

    def forward(self, x):
        return self.linear(x) + self.lora(x)
```

- 原 `nn.Linear`（weight 和 bias）被冻结，只有 `self.lora.A`、`self.lora.B` 可训练。
- 把原层作为子模块 `self.linear` 保存，而不是拷贝权重：合并时可以直接改它的 `weight`，再把它"放回"原位置。
- 推理时比原层多两次小矩阵乘（`x@A`、`@B`）——这就是"未合并时的推理开销"。
- 注：真实 LoRA 通常还有 `lora_dropout`（讲义 "Use It" 中 `lora_dropout=0.05`），作用在进入 A 之前的输入上；这里省略了。

### 3.3 `inject_lora`：按名字替换模块

```python
def inject_lora(model, target_modules, rank=8, alpha=16):
    for param in model.parameters():
        param.requires_grad = False

    lora_layers = {}
    for name, module in list(model.named_modules()):
        if isinstance(module, nn.Linear):
            if any(t in name for t in target_modules):
                parent_name = ".".join(name.split(".")[:-1])
                child_name = name.split(".")[-1]
                if parent_name:
                    parent = dict(model.named_modules())[parent_name]
                else:
                    parent = model
                lora_linear = LinearWithLoRA(module, rank, alpha)
                setattr(parent, child_name, lora_linear)
                lora_layers[name] = lora_linear
    return lora_layers
```

- **先冻结全部参数**：包括最后一层 `Linear(512→10)` 和所有 bias。所以 demo 中分类头始终保持随机初始化，只靠前两层的 LoRA 去"迎合"这个随机头。
- **`list(model.named_modules())`**：先把迭代器"快照"成列表，再在循环里替换模块，避免一边遍历一边修改模块树。讲义版本少了 `list(...)` 和根模块判断，代码版更稳妥。
- **找父模块再 `setattr`**：模块名 `"0"` 的父名是 `""`（根模块本身），所以要特判；对于 `layers.3.self_attn.q_proj`，父名是 `layers.3.self_attn`，子名是 `q_proj`。`setattr(parent, "0", ...)` 对 `nn.Sequential` 同样有效，因为子模块是按名字存在 `_modules` 里的。（也可以用 `model.get_submodule(parent_name)` 代替每次重建一个 `dict`。）
- ⚠️ **子串匹配**：`any(t in name for t in target_modules)` 中 `"0" in name` 是子串判断。在 demo 的 5 个模块名 `"0"…"4"` 上没问题，但在真实模型里 `"0"` 会匹配 `layers.10`、`layers.20`、`layers.0` 下的所有线性层。应按名字最后一段精确匹配（`name.split(".")[-1] in target_modules`）。PEFT 的 `target_modules=["q_proj", "v_proj"]` 就是按后缀匹配。
- 返回 `{原名字: LinearWithLoRA}`，Step 2 打印的 `LoRA injected into: ['0', '2']` 就来自它。

### 3.4 `count_parameters`：统计口径

```python
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
```

- `numel()` 是张量元素个数。`total` **包含** LoRA 参数，所以百分比的分母是"基座 + LoRA"。
- demo 精确数值：基座 399,370；r = 8 时 LoRA 为 `8×(256+512) + 8×(512+512) = 14,336`，占 `14,336 / 413,706 = 3.47%`。
- ⚠️ 讲义 Step 8 说"~1% trainable"，SUMMARY 打印 "Typical trainable parameters: 0.5-2%"，都与这个 demo 不符。LoRA 占比 ≈ `r·(d_in+d_out)/(d_in·d_out)`，层越窄占比越高；只有在 4096 维这样的大层上，r = 16 才是 0.78%。

### 3.5 `merge_lora_weights`：把适配器"烤进"权重

```python
def merge_lora_weights(model):
    for name, module in list(model.named_modules()):
        if isinstance(module, LinearWithLoRA):
            with torch.no_grad():
                merged = (module.lora.A @ module.lora.B) * module.lora.scaling
                module.linear.weight.data += merged.T
            # ... 找父模块
            setattr(parent, child_name, module.linear)
```

- `A @ B` 是 `(in, out)`，`nn.Linear.weight` 是 `(out, in)`（前向 `x @ weight.T + bias`），所以必须加 `merged.T`。推导：`x(W + s(AB)ᵀ)ᵀ = xWᵀ + s·xAB`，与合并前严格相等。
- ⚠️ 对 512→512 这种方阵，忘了 `.T` 不会报错，但结果是错的——这类 bug 只能靠 Step 6 那样的输出比对发现。
- `torch.no_grad()` + `.data`：原地修改权重，不记录到计算图。
- 合并后把 `LinearWithLoRA` 换回原 `nn.Linear`，模型结构恢复成最初的样子，参数量回到 399,370；被换回的 weight 仍是 `requires_grad=False`，所以合并后 trainable 为 0。
- 合并后 A、B 被丢弃，无法再"拆出"适配器；若需要可逆，应事先保存 `inject_lora` 返回的字典（见测验 Q11 的 unmerge）。

### 3.6 模拟 4-bit 量化：`quantize_to_nf4` 与 `quantize_model`

```python
def quantize_to_nf4(tensor, block_size=64):
    original_shape = tensor.shape
    flat = tensor.reshape(-1)
    pad_size = (block_size - flat.shape[0] % block_size) % block_size
    if pad_size > 0:
        flat = torch.cat([flat, torch.zeros(pad_size)])
    blocks = flat.reshape(-1, block_size)
    scales = blocks.abs().max(dim=1, keepdim=True).values / 7.0
    scales = torch.clamp(scales, min=1e-8)
    quantized = torch.round(blocks / scales).clamp(-8, 7).to(torch.int8)
    return quantized, scales, original_shape, pad_size
```

- **分块**：展平后按 64 个一组，每组一个缩放因子 `absmax / 7`；元素数不是 64 的倍数时补零（外层的 `% block_size` 保证整除时补 0 个）。讲义版没有补零逻辑，遇到不整除的张量会在 `reshape` 时报错。
- `clamp(scales, min=1e-8)` 防止全零块除以 0。
- ⚠️ **这不是 NF4**：
  1. 量化级**均匀分布**（对称 absmax INT4），而 NF4 的 16 个级位于标准正态分布的分位数上；
  2. 因为 `|x/scale| ≤ 7`，`-8` 永远取不到，实际只用了 **15 个级**；
  3. 结果存成 `int8`，每个权重 **1 字节**，没有把两个 4-bit 打包进一个字节；
  4. 缩放因子是 fp32，没有 double quantization。
- `quantize_model` 只处理 `not requires_grad and dim() >= 2` 的参数——即三个冻结的 `weight`；bias（一维）和 LoRA 的 A、B（可训练）不量化。量化后**立刻反量化**并写回 `param.data`（fp32），所以后续训练是在"带量化误差的 fp32 基座"上进行的：模拟了误差，没有模拟存储。真实 QLoRA（bitsandbytes）在显存里存 4-bit，前向时按块反量化成 bf16 计算。
- 量化误差的量级（NumPy 模拟，非真实输出）：第 0 层权重服从 `U(−1/16, 1/16)`（`nn.Linear` 默认 Kaiming-uniform，`fan_in = 256`），量化步长约 `0.0625/7 ≈ 0.0089`，最大误差约为步长一半 0.0045，MSE 约 6.3e-6，原始与重建权重的相关系数约 0.9976。

### 3.7 `train_lora`：只优化 LoRA 参数

```python
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=lr
    )
    criterion = nn.MSELoss()
    for epoch in range(epochs):
        indices = torch.randperm(len(data["inputs"]))
        for i in range(0, len(indices), batch_size):
            batch_idx = indices[i : i + batch_size]
            x = data["inputs"][batch_idx]
            y = data["targets"][batch_idx]
            output = model(x)
            loss = criterion(output, y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
```

- 只把 `requires_grad=True` 的参数交给优化器，AdamW 的两份状态也只为这 14,336 个参数分配——这正是 LoRA 省显存的主要来源（冻结参数不需要梯度和优化器状态）。
- 每个 epoch 用 `randperm` 打乱，`batch_size=4`，500 个样本每 epoch 125 步。
- `max(n_batches, 1)` 防止空数据集除零。
- ⚠️ **任务本身没有可学的规律**：`create_demo_data` 的输入是 `randn`，标签是 `randint`，两者独立。loss 下降只能来自"记住"500 个随机样本。用 MSE 拟合 one-hot：若对所有类别都输出 0.1，MSE 恰为 0.09，这是"什么都没学到"的基线；随机初始化网络的初始 MSE 约 0.11（NumPy 按相同结构与初始化模拟估计）。
- ⚠️ 分类任务通常用交叉熵；分类头被冻结、只训练前两层的 LoRA，也让这个 demo 和"微调 q_proj/v_proj"的真实场景差别不小。
- ⚠️ 没有验证集，看不到过拟合；讲义练习 1 期待"r = 8–16 左右出现收益递减"，在随机标签任务上更多反映的是记忆容量，而非真正的任务难度。

### 3.8 适配器的保存与加载

```python
def save_lora_adapter(model, path):
    adapter_state = {}
    for name, module in model.named_modules():
        if isinstance(module, LoRALayer):
            adapter_state[f"{name}.A"] = module.A.data.clone()
            adapter_state[f"{name}.B"] = module.B.data.clone()
            adapter_state[f"{name}.rank"] = module.rank
            adapter_state[f"{name}.alpha"] = module.alpha
    torch.save(adapter_state, path)
    return len(adapter_state) // 4
```

- 键名形如 `0.lora.A`、`0.lora.B`、`0.lora.rank`、`0.lora.alpha`；每层 4 个键，所以 `len // 4` 就是层数（demo 中为 2）。
- 文件里只有 14,336 个 float32，约 56 KB 加上序列化开销；基座（含 LoRA）约 1,616 KB，适配器约为其 3.5%。真实 7B/8B 模型的适配器是 10–100MB（讲义）。
- ⚠️ `load_lora_adapter` 的问题：
  - 读到的 `rank`、`alpha` 从未使用：rank 不一致时 `module.A.data = ...` 直接换掉张量，不做形状检查；alpha 不一致则 scaling 悄悄不对。
  - `if a_key in adapter_state` 不满足时静默跳过，层名对不上时适配器根本没加载，也不报错。
  - `torch.load(path, weights_only=False)` 走完整的 pickle 反序列化，加载不可信的文件可能执行任意代码；应使用 `weights_only=True` 或 safetensors。
- Step 7 的验证逻辑：`base_weights` 是一个新随机模型的 `state_dict`，`model_a` 与 `model_b` 都加载它，各自注入 LoRA（A 随机、各不相同）；`model_a` 训练后保存，`model_b` 加载后 A、B 被覆盖成同样的值，所以两者输出应完全一致，最大差为 0（同一组浮点运算，按代码推断）。

### 3.9 Step 8："多适配器服务"

```python
    model_even = create_demo_model()
    model_even.load_state_dict(base.state_dict())
    inject_lora(model_even, target_modules=["0", "2"], rank=8, alpha=16)
    train_lora(model_even, data_even, epochs=15, lr=1e-3)

    model_odd = create_demo_model()
    model_odd.load_state_dict(base.state_dict())
    # ... 同上，用 data_odd 训练
```

- `data["inputs"][::2]` / `[1::2]`：切片步长 2，取偶数 / 奇数下标的 250 个样本。
- 两个模型共享**同一份初始权重**（`load_state_dict(base.state_dict())`），只有 LoRA 不同，所以输出差异只来自适配器。
- ⚠️ 但这并不是讲义练习 4 描述的"基座只加载一次、切换适配器"：这里在内存里放了**两个完整模型**。真正的多适配器服务是一个基座 + 多组 A/B，按请求切换或在同一批次内分组计算（测验 Q12 给出了在同一模型上切换的写法）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用包装层 `LinearWithLoRA` 替换原层 | 不改原模型代码就能注入 | 推理多两次小 matmul；生产用 PEFT 的 `get_peft_model`，部署时 `merge_and_unload` |
| 子串匹配 `target_modules` | demo 模块名简单 | 真实模型会误伤；应按模块名后缀精确匹配 |
| A 用 `randn/√r` 初始化 | 简单 | 与 PEFT 的 Kaiming-uniform 不同，`xA` 尺度随 `in_features` 变大 |
| 不含 `lora_dropout` | 代码短 | 小数据集上更易过拟合；讲义推荐 0.05 |
| 均匀 absmax 量化、存 int8 | 易懂、易验证误差 | 不是 NF4，也不是 4-bit 存储；生产用 bitsandbytes 的 NF4 + double quant |
| 量化后反量化写回 fp32 | 训练循环无需改动 | 只模拟误差，不省内存 |
| MSE + 随机标签 + 冻结分类头 | 构造简单、可快速跑 | 没有可泛化的规律，loss 只反映记忆能力；真实 SFT 用交叉熵和真实指令数据 |
| `torch.save` 存 dict（含 int） | 一个文件存全部信息 | 需要 `weights_only=False`，有反序列化风险；用 safetensors + 单独的 JSON 配置 |
| 两个完整模型演示多适配器 | 代码直观 | 内存翻倍，没有演示"切换"；应在单一基座上换 A/B |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 继承 `nn.Module` + `super().__init__()` | `class LoRALayer(nn.Module): ... super().__init__()` | 必须先调用父类构造函数，PyTorch 才能注册参数和子模块 |
| `nn.Parameter` | `self.A = nn.Parameter(torch.randn(...))` | 把张量登记为可训练参数，会出现在 `model.parameters()` 中 |
| `forward` 与 `model(x)` | `def forward(self, x)`、`output = model(x)` | 调用模块对象会自动执行 `forward`（以及 hooks） |
| `@` 矩阵乘法 | `x @ self.A @ self.B` | 从左到右结合：`(x @ A) @ B` |
| `requires_grad` | `param.requires_grad = False` | 关闭梯度即冻结参数 |
| `isinstance` | `isinstance(module, nn.Linear)` | 判断对象类型，筛选要替换的层 |
| `setattr` | `setattr(parent, child_name, lora_linear)` | 按字符串名字给对象设置属性，用于动态替换子模块 |
| `list(generator)` 快照 | `list(model.named_modules())` | 先固定遍历对象，避免遍历时修改结构 |
| `str.split` / `join` | `".".join(name.split(".")[:-1])` | 拆出父模块路径；`[:-1]` 去掉最后一段 |
| `any` + 生成器 | `any(t in name for t in target_modules)` | 只要有一个为真就返回 True |
| `sum` + 生成器 | `sum(p.numel() for p in model.parameters() if p.requires_grad)` | 带条件求和 |
| 条件表达式 | `100 * trainable / total if total > 0 else 0` | 防止除零 |
| `with torch.no_grad():` | 合并权重时 | 上下文管理器，块内运算不构建计算图 |
| `.data` / `.clone()` / `.detach()` | `module.A.data.clone()`、`model_q(test_input).detach()` | 取底层张量、深拷贝、脱离计算图 |
| 张量切片与花式索引 | `indices[i : i + batch_size]`、`data["inputs"][batch_idx]`、`[::2]`、`[1::2]` | 切片、按下标张量取行、按步长取 |
| `scatter_` 构造 one-hot | `torch.zeros(n, c).scatter_(1, y.unsqueeze(1), 1.0)` | 在第 1 维按 `y` 指定的位置写入 1；`_` 结尾表示原地操作 |
| `keepdim=True` 与广播 | `blocks.abs().max(dim=1, keepdim=True).values / 7.0`、`blocks / scales` | 保留维度后 `(n, 1)` 可与 `(n, 64)` 广播相除 |
| 链式方法 | `torch.round(blocks / scales).clamp(-8, 7).to(torch.int8)` | 取整 → 截断 → 转类型 |
| 取余技巧 | `(block_size - n % block_size) % block_size` | 整除时补 0 个，否则补到下一个整数倍 |
| 返回多个值 | `return quantized, scales, original_shape, pad_size` | 返回元组，调用方解包 `q, scales, shape, pad = ...` |
| 嵌套字典 | `quantized_state[name] = {"quantized": q, ...}` | 字典的值又是字典 |
| f-string 格式符 | `{params['total']:,}`、`{rank:>2d}`、`{p['trainable']:>6,}`、`{mse:.6f}`、`{merge_diff:.8f}` | 千分位、右对齐宽度、小数位 |
| 相邻 f-string 拼接 | `print(f"  rank=..." f"loss: ...")` | 括号内相邻字符串自动拼接 |
| `print(..., end="")` | `print(f"  e{i}={losses[i]:.4f}", end="")` | 不换行，连续打印在同一行 |
| 局部 import | `import tempfile`、`import os` 写在 `__main__` 内 | 只在需要时导入；风格上一般放文件顶部 |
| `tempfile` + `os.unlink` | `NamedTemporaryFile(suffix=".pt", delete=False)` | 创建临时文件路径，用完手动删除 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行演示 |

---

## 6. 运行结果解读

**未实际运行，原因**：环境中没有安装 PyTorch（`import torch` 报 `ModuleNotFoundError`），按任务要求不自行安装。以下内容分三类：可由形状精确算出的（标"精确"）、按代码逻辑推断的（标"推断"）、用 NumPy 按相同初始化模拟的估计值（标"模拟"）。

**Step 1–2：参数量（精确）**

```text
  Total parameters: 399,370                      ← 131,584 + 262,656 + 5,130
  Trainable: 399,370 (100.0%)
  LoRA injected into: ['0', '2']
  Total parameters: 413,706
  Trainable (LoRA only): 14,336 (3.47%)          ← 6,144 + 8,192
  Frozen (base model): 399,370
```

**Step 3：rank 对比（trainable 精确；loss 无法给出）**

```text
  rank= 2: trainable= 3,584 (0.89%)
  rank= 4: trainable= 7,168 (1.76%)
  rank= 8: trainable=14,336 (3.47%)
  rank=16: trainable=28,672 (6.70%)
  rank=32: trainable=57,344 (12.56%)
```

- 推断：每个 rank 都新建一个**不同随机初始化**的基座（`create_demo_model()` 连续消耗随机数），训练顺序也不同，所以各行 loss 的差异混杂了基座差异，不能完全归因于 rank。
- 推断：第一个 epoch 的平均 loss 应在 0.1 左右（随机网络的初始 MSE 模拟约 0.11，"全输出 0.1"的基线是 0.09），10 个 epoch 后 rank 越大通常降得越多，因为可记忆的容量更大。

**Step 4：模拟 QLoRA（层数与字节数精确；误差为模拟）**

```text
  Quantized layers: 3                            ← 三个 weight；bias 与 LoRA 不量化
  Quantization error (layer 0):
    MSE: 约 6.3e-06 (模拟)
    Max absolute error: 约 0.0045 (模拟)       ← 量化步长 0.0625/7 的一半
    Correlation: 约 0.9976 (模拟)
  Memory comparison:
    Full model (fp32): 1616.0 KB                 ← 413,706 × 4 B，含 LoRA
    Quantized base (simulated NF4): 413.3 KB     ← 398,336 B (int8) + 6,224 个 fp32 缩放
    LoRA adapters (fp32): 56.0 KB
    QLoRA total: 469.3 KB
```

- "Quantized base" 按每权重 1 字节计算，真正 4-bit 打包后元素部分只需约 194.5 KB；1,034 个 bias（4,136 B）在 QLoRA total 中被漏算。
- 讲义练习 3 要求对比 block_size = 32/64/128/256：NumPy 模拟中 MSE 分别约 6.0e-6、6.3e-6、6.5e-6、6.6e-6，块越小误差越小，但缩放因子的开销越大（每块 4 字节）。对均匀分布的初始化权重差别很小；对含离群值的真实权重，块大小的影响会明显得多。

**Step 5：QLoRA 训练（推断）**：20 个 epoch，loss 应逐步下降；打印 e0、e5、e10、e15 四个点。由于基座带有量化误差，与无量化版本相比差别应很小（误差相对权重尺度约 7%）。

**Step 6：合并验证（参数量精确，差值推断）**

```text
  Parameters after merge: 399,370               ← 回到原结构
  LoRA layers remaining: 0
  Max output difference (should be ~0): 预计 1e-7 ~ 1e-6 量级
```

- 合并在数学上严格等价，差值只来自 float32 运算顺序不同。

**Step 7：保存与加载**

```text
  Adapter layers saved: 2                        ← 精确
  Adapter file size: 约 57 KB 以上               ← 推断：56 KB 数据 + torch.save 的 zip/pickle 开销
  Base model size: 1616.0 KB                     ← 精确；分母含 LoRA 参数
  Adapter is 约 3.5% of base model               ← 推断
  Output match after load (max diff): 0.00000000 ← 推断：两模型权重完全相同
```

**Step 8：多适配器（推断）**：两个适配器各在 250 个样本上训练 15 个 epoch，输出平均差应明显大于 0，证明"同一基座 + 不同适配器 → 不同行为"；但如 3.9 所述，它并没有演示单基座切换。

---

## 7. 动手改一改

1. **讲义练习 1（rank 消融）**：固定同一个基座（先 `base = create_demo_model().state_dict()`，每个 rank 都 `load_state_dict(base)`），对 r = 2…64 各训练 20 个 epoch，画"最终 loss – rank"曲线。再把标签换成 `x` 的某个确定函数（例如 `argmax(x[:, :10])`），对比随机标签和有规律标签下的曲线有何不同。
2. **讲义练习 2（目标层对比）**：分别只注入 `"0"`、`"2"`、`"4"` 以及三者全部，比较收敛速度；同时把 `inject_lora` 的匹配改为 `name.split(".")[-1] in target_modules`。
3. **讲义练习 3（量化误差）**：对训练后的权重比较 block_size = 32/64/128/256 的 MSE、最大误差、相关系数；再实现测验 Q10 中按正态分位数取级、4-bit 打包的版本，比较误差和字节数。
4. **讲义练习 4（真正的多适配器服务）**：用测验 Q12 的 `snapshot_adapter` / `use_adapter`，在**同一个**模型上训练并切换两个适配器，验证切换前后输出不同、切回后输出复原。
5. **讲义练习 5（合并 vs 未合并）**：在 100 个输入上验证合并前后输出差 < 1e-5，并用 `time.perf_counter` 比较推理耗时；再实现 unmerge 并验证能恢复原权重。
6. **进阶**：把 `torch.load(..., weights_only=False)` 改成 safetensors 存储张量、JSON 存 rank/alpha，加载时校验形状和超参；或者给 `LoRALayer` 加上 `nn.Dropout(p=0.05)`。

---

## 8. 常见坑

- **忘了冻结基座**：`inject_lora` 第一步就是全模型 `requires_grad = False`；漏掉这一步，优化器会更新全部参数，LoRA 就失去了意义（outputs 中的 skill 文件也列为常见错误）。
- **合并时漏了转置**：方阵层不会报错但结果错误，必须用输出比对验证。
- **把 B 也随机初始化**：模型一开始就偏离原行为；把 A、B 都设为 0 则永远学不动。
- **子串匹配模块名**：`"0"` 会匹配 `layers.10`，导致注入了大量意料之外的层。
- **把"模拟量化"当成真 4-bit**：本代码存的是 int8、训练时用的是 fp32 反量化权重，并不省内存。
- **百分比口径不统一**：分母是否包含 LoRA 参数、是否只算被注入的层，会得到 3.47%、3.59% 等不同数字；汇报时要说明口径。
- **加载适配器不校验**：rank/alpha/层名不一致时静默出错；`weights_only=False` 加载外部文件有代码执行风险。
- **用随机标签判断 rank 好坏**：没有可学规律的数据上，loss 只反映记忆容量，不能直接推广到真实任务。
