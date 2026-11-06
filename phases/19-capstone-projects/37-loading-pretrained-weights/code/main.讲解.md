# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 37 节 加载预训练 Weights ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；会在 `../outputs/` 写入约 7.4 MB 的 `gpt2-stub.safetensors`，并临时写入、随后删除 `gpt2-bad.safetensors`）；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests` ｜ **依赖**：`torch`（第三方，CPU 即可）、`safetensors`（第三方，`pip install safetensors`）；`math`、`dataclasses`、`pathlib`（标准库）。无网络。

---

## 1. 这份代码在考察什么

这份代码把"把别人发布的权重装进自己写的模型"拆成了几个可以单独检验的步骤：

1. **目标架构**：一个与第 35 节相同命名的 GPT（`tok_embed`、`pos_embed`、`blocks.N.{ln1, attn.qkv, attn.out_proj, ln2, mlp.fc1, mlp.fc2}`、`final_ln`、`lm_head`），让本节自给自足。
2. **名字映射**：`make_pretrained_to_local` 把 GPT-2 发布时的名字（`wte`、`h.N.attn.c_attn` …）展开成一张 dict。
3. **布局转换**：GPT-2 的 `Conv1D` 权重是 `(in, out)`，`nn.Linear` 是 `(out, in)`，三种后缀需要转置。
4. **形状检查与"先校验后赋值"**：任何 shape mismatch 都会让整次加载不写入任何参数。
5. **weight tying**：LM head 不在文件里，靠与 `tok_embed` 共享存储获得权重。
6. **可观测性**：`LoadReport` 汇总结果；用参数"指纹"和贪心生成样本做加载前后的冒烟测试。
7. **离线 fixture**：`make_stub_safetensors` 生成一个与真实 GPT-2 命名、布局完全相同的小文件。

> 一句话：**权重加载的本质是对齐"名字、形状、字节布局"三重身份，并且要让失败大声说出来**。同时也要看清：形状检查查不出方阵的转置错误、"缺张量"时并不是原子的——这些是本节代码最值得追问的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ModelConfig` | dataclass | 模型超参（默认等于 GPT-2 Small：50257 / 1024 / 768 / 12 头 / 12 层） | 配置 |
| `LayerNorm` | `nn.Module` | 手写 LayerNorm，参数名为 `scale` / `shift` | 本地命名约定 |
| `MultiHeadAttention` | `nn.Module` | 融合 `qkv` 线性层 + `split` + 因果 mask + `out_proj` | 融合 QKV |
| `FeedForward` | `nn.Module` | `fc1 → GELU(tanh) → fc2` | GPT-2 MLP |
| `TransformerBlock` | `nn.Module` | pre-norm：`x + attn(ln1(x))`、`x + mlp(ln2(x))` | 第 35 节 block |
| `GPTModel` | `nn.Module` | 组装；`lm_head.weight = tok_embed.weight` | weight tying |
| `LoadReport` | dataclass | `loaded / missing / unexpected / shape_mismatch` + `summary()` / `ok()` | 加载报告 |
| `CONV1D_SUFFIXES` / `_needs_transpose` | 常量 / 函数 | 判断哪些张量要 `.t()` | Transpose-on-load |
| `make_pretrained_to_local` | 函数 | 生成完整 name map（4 + 12 × 层数 条） | Name map |
| `load_safetensors` | 函数 | 读文件 → 映射 → 转置 → 形状检查 → 统一赋值 → 重建别名 → 报告 | Loader 主流程 |
| `make_stub_safetensors` | 函数 | 生成 GPT-2 命名的随机权重文件 | Stub fixture |
| `quick_generate` | 函数 | 贪心生成，用于前后对比 | 健全性检查 |
| `_state_fingerprint` | 函数 | 所有参数 L2 范数之和 | 粗粒度指纹 |
| `demo` | 函数 | 串起全部流程，含一次故意的 shape mismatch | 演示 |

数据流：`demo` → `make_stub_safetensors` 写文件 → `GPTModel(cfg)` 随机初始化 → 记录指纹与贪心样本 → `load_safetensors`（`safe_open` → name map → 转置 → shape check → `pending` → `no_grad` 下 `copy_`）→ 再记录指纹与样本并断言不同 → 检查 `data_ptr` → 构造坏文件走一遍 mismatch 路径。

---

## 3. 逐段精讲

### 3.1 模块级常量：导入即建目录

```python
HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)
STUB_PATH = OUTPUTS / "gpt2-stub.safetensors"
```

- 路径基于 `__file__` 计算，所以无论从哪个目录运行，fixture 都写到 `<小节>/outputs/`。
- **注意**：`mkdir` 写在模块顶层：**只要 `import main` 就会创建 `outputs/` 目录**，测试文件 `from main import ...` 时也会触发。这类副作用通常应放进 `demo()` 里。

### 3.2 本地模型：命名就是"契约"

```python
class LayerNorm(nn.Module):
    def __init__(self, d_model: int, eps: float = 1e-5) -> None:
        super().__init__()
        self.eps = eps
        self.scale = nn.Parameter(torch.ones(d_model))
        self.shift = nn.Parameter(torch.zeros(d_model))
```

- 参数叫 `scale` / `shift` 而不是 PyTorch 内置 `nn.LayerNorm` 的 `weight` / `bias`，所以 name map 必须写 `ln_1.weight → ln1.scale`、`ln_1.bias → ln1.shift`。测试 `test_layer_norm_weight_maps_to_scale_and_bias_to_shift` 就是在验证这一条。
- `var(..., unbiased=False)` 用总体方差，与 GPT-2 / `nn.LayerNorm` 的定义一致；用无偏方差会让加载后的数值与原模型有细微差别。

```python
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=cfg.use_bias)
        ...
        qkv = self.qkv(x)
        q, k, v = qkv.split(self.d_model, dim=-1)
```

- **融合 QKV**：一个 `d → 3d` 的线性层，前向时按最后一维切成三段。`qkv.weight` 形状为 `(3d, d)`，GPT-2 的 `c_attn.weight` 是 `(d, 3d)`，转置一次就对上。切分顺序 Q、K、V 也与 GPT-2 一致，这是"融合矩阵可以直接搬"的前提——如果本地实现是 K、Q、V 的顺序，形状照样对得上，但结果全错。
- 因果 mask 用 `register_buffer(..., persistent=False)`：它不是参数、也不进 `state_dict`，因此不需要（也不应该）从文件加载。

```python
        self.act = nn.GELU(approximate="tanh")
```

- GPT-2 的 GELU 是 tanh 近似版；用精确版 GELU 加载后数值会有微小偏差。加载别人的权重时，**激活函数的变体也属于"架构契约"的一部分**。

```python
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        if cfg.weight_tying:
            self.lm_head.weight = self.tok_embed.weight
```

- 把 `tok_embed.weight` 这个 `Parameter` 对象直接赋给 `lm_head.weight`：两者是**同一个对象**，`data_ptr()` 相同。`nn.Linear` 计算 `x @ W.T`，`W` 是 `(V, d)`，恰好就是 embedding 表的形状。
- 副作用：`named_parameters()` 去重后只有 52 个条目（demo 配置），不含 `lm_head.weight`；`state_dict()` 却有 53 个键（实测）。这一点会影响 loader 的 `missing` 计算（见 3.6）。
- `position_ids` 也是非持久 buffer，`forward` 里用 `self.position_ids[:seq]` 取位置下标。

### 3.3 `LoadReport`：把结果变成数据

```python
@dataclass
class LoadReport:
    loaded: list[tuple[str, str, tuple[int, ...]]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    shape_mismatch: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.missing and not self.shape_mismatch
```

- 四个列表对应讲义 Key Terms 里的 "Load report"。`loaded` 存 `(源名, 目标名, 形状)` 三元组，便于事后追查"哪个张量落到了哪里"。
- `field(default_factory=list)`：可变默认值必须用工厂函数，否则所有实例会共享同一个列表。
- `ok()` **不看 `unexpected`**：文件里多出来的东西（例如被一起保存的 buffer）不算失败；但这也意味着"checkpoint 层数比模型多"时多出的层会被静默丢弃（测验 Q12）。

### 3.4 Name map 与转置判断

```python
CONV1D_SUFFIXES = ("c_attn.weight", "c_proj.weight", "c_fc.weight")

def make_pretrained_to_local(num_layers: int) -> dict[str, str]:
    mapping: dict[str, str] = {
        "wte.weight": "tok_embed.weight",
        "wpe.weight": "pos_embed.weight",
        "ln_f.weight": "final_ln.scale",
        "ln_f.bias": "final_ln.shift",
    }
    for layer in range(num_layers):
        prefix_src = f"h.{layer}"
        prefix_dst = f"blocks.{layer}"
        mapping[f"{prefix_src}.ln_1.weight"] = f"{prefix_dst}.ln1.scale"
        ...
```

- 4 条全局 + 每层 12 条。demo 4 层共 52 条；GPT-2 Small 12 层共 148 条（实测完整 GPT-2 配置的 `named_parameters()` 恰好 148 个、参数量 124,439,808，与 Hugging Face 的 GPT-2 一致）。
- 映射按 `num_layers` 展开，所以 `h.{num_layers}` 及以上不会出现在 map 里——测试 `test_no_layers_outside_range` 验证这一点。
- `_needs_transpose` 用 `endswith` 判断：`attn.c_proj.weight` 与 `mlp.c_proj.weight` 都以 `c_proj.weight` 结尾，一个后缀覆盖两处。
- **注意**：名字必须**完全匹配**：讲义 "The Problem" 一节写的是 `transformer.h.0.attn.c_attn.weight`，带前缀的文件在本 loader 下会全部进入 `unexpected`（实测 `loaded=0 missing=52 unexpected=52`），需要先剥离前缀（测验 Q11）。

### 3.5 `load_safetensors` 第一阶段：只读、只检查

```python
    with safe_open(str(path), framework="pt") as reader:
        pretrained_names = list(reader.keys())
        for src_name in pretrained_names:
            local_name = mapping.get(src_name)
            if local_name is None:
                report.unexpected.append(src_name)
                ...
                continue
            if local_name not in local_params:
                report.unexpected.append(src_name)
                ...
                continue

            tensor = reader.get_tensor(src_name)
            if _needs_transpose(src_name):
                tensor = tensor.t().contiguous()

            target = local_params[local_name]
            if tuple(tensor.shape) != tuple(target.shape):
                report.shape_mismatch.append(
                    (src_name, tuple(tensor.shape), tuple(target.shape))
                )
                ...
                continue

            pending.append((src_name, local_name, tensor))
```

- `safe_open` 是上下文管理器，`reader.keys()` 只读 header 就能拿到全部名字；`get_tensor` 按名字取单个张量。实测 `keys()` 按字母序返回（`h.0.attn.c_attn.bias` 最先、`wte.weight` 最后）。
- 两种 "unexpected"：①name map 里没有；②map 里有但本地模型没有这个参数（例如 `use_bias=False` 时的 bias）。
- `.t().contiguous()`：`.t()` 只改 stride 不复制，`contiguous()` 复制成连续内存，后续 `copy_` 和保存都更稳妥。
- **形状检查在转置之后**：比较的是"转换成本地布局后"的形状。
- **注意**：形状检查的盲区：`attn.c_proj.weight` 是 `(d, d)` 方阵，转不转置形状都一样。实测把它从转置列表中漏掉，报告依旧 `loaded=52 shape_mismatch=0`、`ok()=True`，但每一层注意力输出投影都是错的。shape check 只是必要条件。
- 这一阶段**不修改模型**：通过检查的张量先放进 `pending`。

### 3.6 第二阶段：统一赋值、重建别名、计算 missing

```python
    if report.shape_mismatch:
        expected = set(local_params.keys())
        for name in sorted(expected - seen_local):
            report.missing.append(name)
        return report

    with torch.no_grad():
        for src_name, local_name, tensor in pending:
            target = local_params[local_name]
            target.copy_(tensor.to(device=target.device, dtype=target.dtype))
            seen_local.add(local_name)
            report.loaded.append((src_name, local_name, tuple(tensor.shape)))
```

- **全有或全无（仅针对 shape mismatch）**：只要有一个张量形状不对，直接返回，`pending` 一个都不写。demo 的坏文件路径实测 `loaded=0`，测试 `test_shape_mismatch_is_recorded_not_assigned` 也确认 `tok_embed` 未被改动。
- `torch.no_grad()`：对 `requires_grad=True` 的叶子参数做原地 `copy_` 必须关掉 autograd，否则会报错（讲义："so autograd does not track the load"）。
- `copy_` 是**原地**写入：`Parameter` 对象不变，所以优化器、别名关系都不受影响；`tensor.to(device=..., dtype=...)` 让文件张量自动跟随目标参数的设备与精度。
- **注意**：`missing` 的语义被混用：mismatch 分支中 `seen_local` 为空，于是 52 个参数**全部**被列为 missing（实测 `missing=52`），看起来像"名字全错了"，其实只有一个张量形状不对。
- **注意**：**"缺张量"不是原子的**：缺失检查在赋值之后。实测删掉 `ln_f.bias` 再加载：`loaded=51 missing=1`、`ok()=False`，但 51 个张量已经写进模型。这与讲义"Always validate the file before any assignment"相悖，修法见测验 Q9。

```python
    if model.cfg.weight_tying:
        if model.lm_head.weight.data_ptr() != model.tok_embed.weight.data_ptr():
            model.lm_head.weight = model.tok_embed.weight
        seen_local.add("lm_head.weight")
```

- 防御性代码：若有人用"替换对象"的方式改了 `tok_embed.weight`，这里把别名接回来。但本流程用的是原地 `copy_`，`data_ptr` 始终相等，`if` 不会进入。
- `seen_local.add("lm_head.weight")` 也不起作用：`local_params` 由去重后的 `named_parameters()` 构成，本来就不含 `lm_head.weight`。若 `weight_tying=False`，`lm_head.weight` 会出现在 `local_params` 中、文件里却没有，于是正确地被报告为 missing。

### 3.7 `make_stub_safetensors`：可复现的假 GPT-2

```python
    generator = torch.Generator().manual_seed(seed)

    def randn(*shape: int) -> torch.Tensor:
        return torch.randn(*shape, generator=generator, dtype=torch.float32)
    ...
        tensors[f"h.{layer}.attn.c_attn.weight"] = (
            randn(3 * cfg.d_model, cfg.d_model).t().contiguous() * 0.02
        )
```

- 用独立的 `torch.Generator`，不受全局 `torch.manual_seed` 影响，同一 `seed` 永远生成同一文件。
- 先按 `nn.Linear` 布局 `(out, in)` 生成，再 `.t()` 存成 Conv1D 布局 `(in, out)`——刻意模拟真实 GPT-2 的存储方式，让 loader 的转置分支被真正执行。实测 `h.0.attn.c_attn.weight` 形状为 `(192, 576)`，`mlp.c_fc.weight` 为 `(192, 768)`，`mlp.c_proj.weight` 为 `(768, 192)`。
- 权重 std 0.02、bias 全 0、LayerNorm scale 全 1：与 GPT-2 初始化风格一致，但它**仍是随机权重**，并不包含任何"语言知识"。
- `save_file(tensors, str(path))`：写成 safetensors。实测文件 7,369,512 字节，其中张量数据 1,841,280 × 4 = 7,365,120 字节，header 约 4.4 KB。
- **注意**：讲义说 fixture 是"12-block model at d_model 192"，而 demo 实际用的是 4 层（`num_layers=4`）、词表 256、上下文 64。

### 3.8 `quick_generate` 与 `_state_fingerprint`

```python
@torch.no_grad()
def quick_generate(model: GPTModel, prompt: torch.Tensor, n: int, seed: int = 0) -> list[int]:
    torch.manual_seed(seed)
    model.eval()
    tokens = prompt.clone()
    for _ in range(n):
        window = tokens[:, -model.cfg.context_length :]
        logits = model(window)
        next_token = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
        tokens = torch.cat([tokens, next_token], dim=1)
    return tokens.tolist()[0]
```

- `@torch.no_grad()` 装饰器：整个函数不建计算图。`model.eval()` 关闭 dropout（本例 dropout=0，影响不大）。
- 取最后 `context_length` 个 token 作为窗口，`argmax` 贪心选下一个 token，`keepdim=True` 让结果是 `(1, 1)`，方便 `cat`。
- **注意**：贪心解码是确定性的，`torch.manual_seed(seed)` 实际不起作用；参数 `seed` 只是为将来改成采样预留。
- `_state_fingerprint` 对每个参数求 L2 范数再求和——粗糙但便宜：只要有任何参数被改写，几乎必然变化。随机初始化时 `tok_embed` 一项就约 221.7（N(0,1) 初始化），加载 stub 后降到约 4.47（std 0.02），所以指纹从 652.3 降到 234.8。

### 3.9 `demo`：三道门禁 + 一条失败路径

```python
    assert before_fp != after_fp, "fingerprint should change after load"
    assert before_tokens != after_tokens, "sample should change after load"
    ...
    tied = model.lm_head.weight.data_ptr() == model.tok_embed.weight.data_ptr()
    assert tied
    ...
    bad_tensors["wte.weight"] = torch.randn(cfg.vocab_size, cfg.d_model + 1)
    save_file(bad_tensors, str(bad_path))
    bad_model = GPTModel(cfg)
    bad_report = load_safetensors(bad_model, bad_path, verbose=False)
    assert bad_report.shape_mismatch, "expected at least one shape mismatch"
    bad_path.unlink()
```

- 门禁 1：指纹变化；门禁 2：贪心样本变化（讲义："if the post-load samples look like the pre-load samples ... the mapping silently missed every tensor"）；门禁 3：别名仍然成立。
- 失败路径：读出全部张量，把 `wte` 换成多一列的矩阵，写成新文件再加载，断言 mismatch 被记录。最后 `unlink()` 删除坏文件。
- **注意**：讲义说输出里有"per-name load log"，但 demo 调用时传了 `verbose=False`，实际不打印逐条日志；想看就改成 `verbose=True`（会打印 52 行 `[ok  ] 源名 -> 目标名 shape=...`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 显式 dict 做 name map | 一眼能看出每个张量去哪；方便打印日志 | 换架构要重写 map；生产中常按模型族维护一组正则/模板 |
| 按后缀判断转置 | 简单，覆盖 GPT-2 的三类 Conv1D | 方阵转置错误 shape check 发现不了；生产中加数值对照（同输入比 logits） |
| 先收集 `pending`、再统一赋值 | mismatch 时不会半加载 | 缺张量时仍会半加载；应把 missing 检查也挪到赋值前 |
| `no_grad` + 原地 `copy_` | 不打断别名、不影响优化器持有的引用 | 需要保证 device/dtype 一致（代码用 `.to` 处理） |
| LM head 用别名而非复制 | 与 GPT-2 一致，省 `V × d` 参数 | 保存时要处理共享张量（`save_file` 会拒绝） |
| `LoadReport` + `ok()` | 让结果可打印、可断言 | `missing` 语义混用；`unexpected` 不影响 `ok`，层数多出时静默 |
| 离线 stub fixture | 测试秒级、不依赖网络与 500 MB 文件 | 随机权重无法验证"语言能力"；真实文件还可能带前缀/额外 buffer |
| 指纹 + 贪心样本做冒烟测试 | 最便宜的端到端门禁 | 只能证明"变了"，不能证明"对了" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 类型注解延迟求值，可以写 `list[str]` 等新式注解而不担心运行时开销 |
| `@dataclass` | `ModelConfig`、`LoadReport` | 自动生成 `__init__`、`__repr__`；字段用类型注解声明 |
| `field(default_factory=list)` | `loaded: list[...] = field(default_factory=list)` | 可变默认值必须用工厂，否则实例间共享同一个列表 |
| 类型注解 | `def load_safetensors(model: GPTModel, path: Path, verbose: bool = True) -> LoadReport` | 说明参数与返回值类型，不影响运行 |
| 嵌套类型 | `list[tuple[str, tuple[int, ...], tuple[int, ...]]]` | `tuple[int, ...]` 表示任意长度的整数元组 |
| `pathlib.Path` | `HERE.parent / "outputs"`、`path.exists()`、`path.stat().st_size`、`bad_path.unlink()` | `/` 拼路径；查询存在性、大小；删除文件 |
| `with` 上下文管理器 | `with safe_open(...) as reader:`、`with torch.no_grad():` | 进入/退出时自动处理资源或状态 |
| 装饰器 | `@torch.no_grad()` | 给整个函数套上 `no_grad` 上下文 |
| 内部函数 + 闭包 | `make_stub_safetensors` 里的 `def randn(*shape)` 使用外层的 `generator` | 闭包捕获外层变量 |
| `*args` | `def randn(*shape: int)`、`torch.randn(*shape, ...)` | 收集任意个位置参数，再展开传递 |
| 生成器表达式 + `any` | `any(pretrained_name.endswith(s) for s in CONV1D_SUFFIXES)` | 惰性判断是否有一个满足 |
| 字典 / 集合操作 | `mapping.get(src_name)`、`expected - seen_local`、`sorted(...)` | `get` 查不到返回 `None`；集合差集 |
| 元组解包 | `for src_name, local_name, tensor in pending:`、`q, k, v = qkv.split(...)` | 一次取多个值 |
| f-string 格式符 | `{STUB_PATH.stat().st_size:,}`、`{before_fp:.4f}` | 千分位；保留 4 位小数 |
| `assert` | `assert tied`、`assert before_fp != after_fp, "..."` | 条件不成立时抛 `AssertionError`，用作自检 |
| 异常 | `raise FileNotFoundError(...)`、`raise ValueError(...)` | 主动报错，调用方可捕获 |
| `super().__init__()` | 各 `nn.Module` 子类 | 调用父类构造函数，注册参数/子模块的前提 |
| `nn.ModuleList` + 列表推导式 | `nn.ModuleList([TransformerBlock(cfg) for _ in range(cfg.num_layers)])` | 让列表里的子模块被正确注册（名字是 `blocks.0`、`blocks.1` …） |
| `register_buffer(..., persistent=False)` | `causal_mask`、`position_ids` | 跟随 `.to(device)` 移动，但不进 `state_dict` |
| 张量切片 | `tokens[:, -model.cfg.context_length :]`、`self.causal_mask[:seq, :seq]` | 负索引取最后 N 个 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `demo()`，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13、torch 2.14 CPU、safetensors 0.8.0；在副本目录运行，耗时约 4.4 秒）：

```text
model config            : vocab=256 d_model=192 layers=4

Writing stub fixture to : .../outputs/gpt2-stub.safetensors
  file size             : 7,369,512 bytes        ← 1,841,280 个 float32 = 7,365,120 字节 + header

Building fresh model (random init)...
  fingerprint           : 652.3114               ← tok_embed 一项约 221.7（N(0,1) 初始化）
  sample (random init)  : [7, 11, 13, 17, 17, 17, 17, 17, 17, 17, 17, 17]   ← 自我复读

Loading stub...
  report                : loaded=52 missing=0 unexpected=0 shape_mismatch=0
  load ok
  fingerprint after load: 234.8000               ← embedding 变成 std 0.02，范数骤降
  sample (loaded)       : [7, 11, 13, 17, 17, 191, 191, 191, 191, 191, 150, 241]

Weight tying check after load:
  lm_head tied to tok_embed: True

Shape mismatch path: injecting a bad tensor and reloading...
  bad report            : loaded=0 missing=52 unexpected=0 shape_mismatch=1
  first mismatch        : ('wte.weight', (256, 193), (256, 192))

Pretrained weight load check passed.
```

逐项解读：

- **参数量 1,841,280**：token 256×192 = 49,152；位置 64×192 = 12,288；每层 qkv 192×576+576 = 111,168、out_proj 37,056、fc1 148,224、fc2 147,648、两个 LN 768，合计 444,864，×4 = 1,779,456；final LN 384。总和 1,841,280（LM head 共享，不重复计）。
- **`loaded=52`**：52 个张量全部映射成功；`missing=0` 说明 52 个本地参数都有来源（LM head 靠别名）。
- **随机初始化时的自我复读**：实测随机模型对任意单 token 输入，`argmax` 都等于输入 token 本身（256/256）。原因是 N(0,1) 的 embedding 主导了残差流，weight tying 下 logits 是 `LN(x)·Eᵀ`，与自己的点积最大。这也说明"前后样本不同"这道门禁之所以有效，部分是因为随机初始化的输出极有规律。
- **加载后的样本**：变成 `191, 191, ... 150, 241`。stub 也是随机权重，所以生成的仍是无意义的 token——这一步只能证明"权重确实落进了模型"，不能证明"权重是对的"。
- **坏文件路径**：`loaded=0` 证明 mismatch 时没有半加载；`missing=52` 是 3.6 节所说的语义混用（其实只缺一个合格的 `wte`）。

测试运行：`python3 -m pytest -q tests` → `11 passed in 1.96s`。

---

## 7. 动手改一改

1. **打开逐条日志**：把 demo 中的 `verbose=False` 改为 `True`，观察 52 行 `[ok  ]` 日志的顺序（字母序），并找出 `c_attn.weight` 转置前后的形状。
2. **讲义练习 1 + 2**：给 `load_safetensors` 增加 `dtype` 与 `expected_layers` 参数（参考测验 Q12）；先 `model.to(torch.bfloat16)` 再加载，确认仍能生成。
3. **修复非原子加载**：把 missing 检查挪到赋值前（参考测验 Q9），并让 mismatch 分支只报告真正缺失的参数；用"删掉 `ln_f.bias`"的文件验证模型指纹不再变化。
4. **前缀与 buffer**：实现 `normalize_name` 剥离 `transformer.` 前缀，并为 `h.N.attn.bias` 这类非参数条目加一个"已知可忽略"白名单（测验 Q11）。
5. **讲义练习 4（导出 + 往返）**：写 `export_safetensors(model, path)`，按 GPT-2 命名导出（三类权重要转置回 `(in, out)`，不导出 `lm_head`），再用 loader 读回，确认 `shape_mismatch=0` 且所有参数 `torch.equal`。
6. **进阶：数值验证**：故意把 `attn.c_proj.weight` 从转置列表中去掉，确认报告仍显示成功；然后写一个"用 stub 权重手工构造的参考前向"或"导出再加载"的对照，设计一个能抓住这类错误的检查。

---

## 8. 常见坑

- **以为 shape check 通过就加载正确**：方阵（`attn.c_proj`、单头时的其它矩阵）转置错误不会改变形状。
- **把 LM head 复制而不是别名**：参数量多 `V × d`，训练时两者分叉；保存时又可能遇到"共享内存张量"错误。
- **用替换对象的方式加载**：`model.tok_embed.weight = nn.Parameter(t)` 会打断别名，也会让优化器里持有的旧参数失效；应在 `no_grad` 下 `copy_`。
- **忘了 `torch.no_grad()`**：对需要梯度的叶子张量做原地修改会报错。
- **只看 `shape_mismatch`**：前缀不匹配时 mismatch 为 0 但一个都没加载（`unexpected=52`）；要看 `ok()`，并检查 `loaded` 的数量。
- **层数不一致被静默吞掉**：checkpoint 层数多于模型时，多出的层只进 `unexpected`，`ok()` 仍为 True。
- **GELU 变体、LayerNorm 方差定义、QKV 拼接顺序不一致**：这些都不会报错，只会让输出"差一点"或"全错"。
- **导入即有副作用**：`import main` 会创建 `outputs/` 目录；跑测试也会触发。

---

## 9. 测试在验证什么

`tests/test_load.py`（`unittest` 风格，pytest 也能收集），用 `vocab=64, context=16, d_model=32, 4 头, 2 层` 的极小配置，所有文件写在 `tempfile.TemporaryDirectory()` 中：

| 测试 | 验证的性质 |
|------|-----------|
| `NameMapTests.test_expands_per_layer_keys` | 每层条目都被展开；`wte → tok_embed.weight`、`ln_f.* → final_ln.scale/shift` |
| `NameMapTests.test_no_layers_outside_range` | 不会为不存在的层（`h.2`）生成条目 |
| `NameMapTests.test_layer_norm_weight_maps_to_scale_and_bias_to_shift` | LayerNorm 的 weight/bias 映射到 scale/shift |
| `TransposeTests.test_only_conv1d_suffixes_transpose` | 只有三种 Conv1D 权重后缀转置；bias、LayerNorm、`wte` 不转置 |
| `LoaderTests.test_load_changes_state_fingerprint` | 正常加载 `ok()` 为 True，且指纹变化 |
| `LoaderTests.test_lm_head_remains_tied_after_load` | 加载后 `lm_head` 与 `tok_embed` 仍共享存储 |
| `LoaderTests.test_shape_mismatch_is_recorded_not_assigned` | 坏 `wte` 被记入 mismatch，`tok_embed` 数值不变（不半加载） |
| `LoaderTests.test_unknown_tensor_goes_to_unexpected` | 未知名字进入 `unexpected` |
| `LoaderTests.test_missing_file_raises` | 文件不存在抛 `FileNotFoundError` |
| `StubFixtureTests.test_stub_writes_expected_tensor_count` | 3 层 stub 有 `4 + 12 × 3 = 40` 个张量 |
| `GenerationConsistencyTests.test_loaded_model_generates_different_tokens_from_random_init` | 加载前后贪心生成结果不同 |

运行方式（在 `code/` 下）：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。实际结果：**11 passed**（约 2 秒）。

测试没有覆盖的地方：缺张量时的半加载行为、前缀不匹配、层数多于模型、方阵转置错误——这些正是第 3、8 节指出的薄弱点，可以作为补充测试的练习。
