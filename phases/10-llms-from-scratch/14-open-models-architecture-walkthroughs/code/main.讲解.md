# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 14 节 开放模型：架构详解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`dataclasses`），无需 torch、无需下载权重

---

## 1. 这份代码在考察什么

这是一个"架构计算器"：输入 HuggingFace 风格的 config 字典，输出各组件参数量、总参数与激活参数、每层注意力和 MLP 参数、MLP 比例、最大上下文下的 KV cache，以及一行架构摘要。它对应讲义的三个核心目标：

1. **读 config**：`hidden_size`、`intermediate_size`、`num_attention_heads`、`num_key_value_heads`、`vocab_size`、`max_position_embeddings` 各自决定了模型的哪一部分。
2. **六个旋钮的代价**：RMSNorm 与 LayerNorm 的参数差、SwiGLU 的 3 矩阵 MLP、GQA 对 K/V 投影和 KV cache 的缩减、MLA 的潜变量缓存、MoE 的总参数/激活参数。
3. **从 config 推出部署成本**：参数量 → 权重显存；KV 头数 × head_dim × 层数 × 上下文 → KV cache。

> 一句话：**"不看权重，只看 config，就能估出一个模型的体量和显存账"**。但它是一个粗算器——LM head、bias、学习式位置 embedding、MLA 的真实维度都做了简化，读输出时要知道它偏在哪里（见 3.6 与第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CONFIGS` | 模块级字典 | 7 个模型的简化 config（GPT-2 Small、Mistral 7B、Llama 3 8B/70B、Mixtral 8x7B、Qwen 2.5 72B、DeepSeek-V3） | 读 config.json |
| `Breakdown` | dataclass | 一次分析的全部结果 | 输出 schema |
| `attention_scheme` | 函数 | 由 Q/KV 头数判断 MHA / MQA / GQA / MLA | 旋钮 4 |
| `attention_params_per_layer` | 函数 | Q/K/V/O 投影参数，GQA 按 KV 头缩减，MLA 用低秩近似 | 旋钮 4 |
| `mlp_params` / `mlp_params_per_layer` | 函数 | SwiGLU `3·h·ff`，否则 `2·h·ff` | 旋钮 3 |
| `layer_norm_params_per_layer` | 函数 | RMSNorm `2h`，LayerNorm `4h` | 旋钮 1 |
| `analyze` | 函数 | 汇总 dense / MoE 的总参数、激活参数、KV cache、MLP 比例、摘要 | 核心计算 |
| `fmt_billions` / `fmt_bytes` | 函数 | 数字格式化（B/M；B/KB/MB/GB，按 1024 进位） | 输出 |
| `print_breakdown` / `main` | 函数 | 逐模型打印明细，再打印一张总表 | 入口 |

数据流：`main` 遍历 `CONFIGS` → `analyze(name, config)` 调用各个 `*_params` 函数 → 组装 `Breakdown` → `print_breakdown` 打印 → 第二轮遍历打印 `HEADLINE RATIOS`。

---

## 3. 逐段精讲

### 3.1 `CONFIGS`：真实字段 + 教学用标签

```python
    "llama3-8b": {
        "hidden_size": 4096, "intermediate_size": 14336,
        "num_hidden_layers": 32, "num_attention_heads": 32,
        "num_key_value_heads": 8, "vocab_size": 128256,
        "max_position_embeddings": 131072,
        "activation": "swiglu", "norm": "rmsnorm",
        "position": "rope", "moe": False,
    },
```

- 前 7 个字段与 HF config 同名，数值与讲义"Reading a config.json"一致。
- `activation`、`norm`、`position`、`moe`、`attention` 是**本文件自造的标签**，真实 config 里不叫这些名字（例如 HF 用 `hidden_act: "silu"` 表示 SwiGLU 的激活，用 `model_type` 区分架构）。所以这份计算器不能直接吃真实的 `config.json`，需要先做字段映射。
- `deepseek-v3` 额外有 `moe_intermediate_size`（每个专家 MLP 宽度 2048）、`first_dense_layers: 3`（前 3 层用 dense MLP）、`shared_experts: 1`、`kv_lora_rank: 512`。
- ⚠️ 讲义"Use It"说脚本里有 Llama 3 405B 的 config 可供与 DeepSeek-V3 比较 KV cache，但 `CONFIGS` 里**没有** 405B，也没有讲义表中的 Gemma 2；docstring 列出的模型也漏写了实际存在的 `llama3-70b`。
- `max_position_embeddings: 131072` 对 Llama 3 8B 而言是 128k 版本（讲义表格也按 128k 写），计算 KV cache 时以此为准。

### 3.2 `attention_scheme`：由头数判断方案

```python
def attention_scheme(config: dict) -> str:
    if config.get("attention") == "mla":
        return "MLA"
    q_heads = config["num_attention_heads"]
    kv_heads = config["num_key_value_heads"]
    if kv_heads == 1:
        return "MQA"
    if kv_heads == q_heads:
        return "MHA"
    return f"GQA ({q_heads}/{kv_heads})"
```

- 判断顺序很重要：先看 MLA 标签（DeepSeek-V3 的 `num_key_value_heads` 也是 128，若不先判断会被误识别为 MHA）。
- `kv_heads == 1` 是 MQA，`== q_heads` 是 MHA，介于两者之间是 GQA。这正是讲义表格"MHA / GQA / MQA / MLA"的分类依据。

### 3.3 `attention_params_per_layer`：GQA 让 K/V 投影变窄

```python
    head_dim = h // q_heads
    ...
    q_proj = h * h
    kv_proj = 2 * h * (kv_heads * head_dim)
    out_proj = h * h
    return q_proj + kv_proj + out_proj
```

- Q 投影和输出投影都是 `h × h`；K、V 投影的输出维度是 `kv_heads × head_dim`，GQA 下比 `h` 小。
- Llama 3 8B：`head_dim = 4096 / 32 = 128`，`kv_proj = 2 × 4096 × 1024 = 8,388,608`，合计 `2 × 4096² + 8,388,608 = 41,943,040`，即输出中的 `attn / layer : 41.9M`。若是 MHA 则为 `4h² = 67.1M`。
- 没有 bias：Llama/Mistral 确实无 bias；GPT-2 与 Qwen 2.5 的 QKV 有 bias，这里被忽略（量很小）。
- ⚠️ MLA 分支：

```python
    if config.get("attention") == "mla":
        lora = config.get("kv_lora_rank", 512)
        return h * h + 2 * (h * lora + lora * q_heads * head_dim) + h * h
```

  用 `h·h`（Q）+ K、V 各一组"下投影 `h→512` + 上投影 `512→heads·head_dim`"+ `h·h`（输出）近似。问题在于 `head_dim = 7168 / 128 = 56`，而 DeepSeek-V3 每头 Q/K 是 192 维（128 + 64 RoPE）、V 是 128 维，Q 也有自己的低秩压缩（1536），K、V 共用一次下投影。结果每层算出 117.4M，按真实维度应约 187.1M（测验 Q9 给出了完整公式）。

### 3.4 MLP 与 norm 参数

```python
def mlp_params(h: int, ff: int, activation: str) -> int:
    if activation == "swiglu":
        gate_and_up = 2 * h * ff
        down = ff * h
        return gate_and_up + down
    return 2 * h * ff


def layer_norm_params_per_layer(config: dict) -> int:
    h = config["hidden_size"]
    if config.get("norm") == "rmsnorm":
        return 2 * h
    return 4 * h
```

- SwiGLU：gate 和 up 两个 `h→ff`，加 down 一个 `ff→h`，共 `3·h·ff`。Llama 3 8B：`3 × 4096 × 14336 = 176,160,768`。
- GELU（GPT-2）：up 和 down 两个矩阵，`2·h·ff = 2 × 768 × 3072 = 4,718,592`；未计 bias。
- 讲义说 SwiGLU 参数对齐时 `ff = 8/3·h`，但 Llama 3 是 `3.5·h`，MLP 实际比 GPT-2 式 4 倍 dense 多约 31%（`10.5h²` 对 `8h²`）。代码打印的 `ratio ff/h = 3.50` 可以直接验证这一点。
- RMSNorm 每个只有 γ（`h`），每层两个 → `2h`；LayerNorm 有 γ、β → `4h`。最终 norm 在 `analyze` 中单独加：RMSNorm `h`，LayerNorm `2h`。

### 3.5 `analyze`：dense 分支

```python
    emb = vocab * h
    attn = attention_params_per_layer(config)
    dense_mlp = mlp_params(h, dense_ff, activation)
    norm = layer_norm_params_per_layer(config)
    final_norm = h if config.get("norm") == "rmsnorm" else 2 * h
    ...
    else:
        dense_block_params = attn + dense_mlp + norm
        total = emb + n_layers * dense_block_params + final_norm
        active = total
```

- 总参数 = embedding + 层数 × 每层（注意力 + MLP + norm）+ 最终 norm；dense 模型激活参数等于总参数。
- ⚠️ **没有 LM head**：对 weight tying 的模型（GPT-2）这样恰好对；对 Llama 3、Mistral、Qwen、Mixtral、DeepSeek-V3 这些不共享权重的模型，少算了一份 `vocab × h`。Llama 3 8B 因此显示 7.5B（补上后 8.03B）。
- ⚠️ **没有学习式位置 embedding 与 bias**：GPT-2 因此显示 123.6M，比真实 124,439,808 少 869,376（位置 786,432 + bias 82,944）。

### 3.6 `analyze`：MoE 分支

```python
        n_experts = config["num_experts"]
        experts_per_tok = config["experts_per_token"]
        shared = config.get("shared_experts", 0)
        moe_ff = config.get("moe_intermediate_size", dense_ff)
        expert_mlp = mlp_params(h, moe_ff, activation)
        first_dense = config.get("first_dense_layers", 0)
        n_moe_layers = n_layers - first_dense
        router = h * n_experts

        dense_block_params = attn + dense_mlp + norm
        moe_block_params = attn + expert_mlp * n_experts + expert_mlp * shared + router + norm
        active_moe_block = attn + expert_mlp * (experts_per_tok + shared) + router + norm
```

- **每个专家**是一个完整的 SwiGLU MLP，宽度为 `moe_intermediate_size`（Mixtral 没有该字段，回退为 `intermediate_size = 14336`；DeepSeek-V3 是 2048——细粒度专家）。
- **router** 是一个 `h × n_experts` 的线性层，所有 token 都要算，所以同时计入总参数和激活参数。
- **总参数**中 MoE 层包含全部路由专家 + shared expert；**激活参数**只含 top-k 个路由专家 + shared expert。
- **前几层 dense**：DeepSeek-V3 前 3 层用 `intermediate_size = 18432` 的普通 MLP，其余 58 层是 MoE。
- Mixtral 实测：每层 MLP 总量 `8 × 176.2M`，激活 `2 × 176.2M`，加上共享的注意力与 embedding，得到 46.6B / 12.7B（补 LM head 后 46.7B / 12.9B，与讲义的 47B / 13B 吻合）。
- 注意 `mlp = expert_mlp`：MoE 模型打印的 `mlp / layer` 是**单个专家**的参数（DeepSeek-V3 为 44.0M），不是整层 MLP；`mlp_ratio` 同理是 `2048 / 7168 = 0.29`，不要与 dense 模型的 3.5 直接比较。

### 3.7 KV cache 与架构摘要

```python
    head_dim = h // config["num_attention_heads"]
    max_seq = config["max_position_embeddings"]
    if config.get("attention") == "mla":
        latent = config.get("kv_lora_rank", 512)
        kv_cache_bytes = 2 * n_layers * latent * max_seq * 2
    else:
        kv_heads = config["num_key_value_heads"]
        kv_cache_bytes = 2 * n_layers * kv_heads * head_dim * max_seq * 2
```

- 非 MLA：讲义公式 `2(K,V) × 层数 × KV 头数 × head_dim × 序列长度 × 2 字节(BF16)`。Llama 3 8B：`2 × 32 × 8 × 128 × 131072 × 2 = 17,179,869,184` 字节。
- ⚠️ MLA：开头的 `2` 把 K、V 当成两份缓存。MLA 缓存的是 K、V **共享**的一个潜变量 `c_KV`（512 维）外加一个共享的 64 维 RoPE key，每 token 每层 576 个值。按此计算 DeepSeek-V3 在 128k 下约 8.58 GiB，代码给出 15.2 GiB，高估约 1.8 倍。
- 摘要拼接：

```python
    flags.append(config.get("norm", "layernorm").upper())
    ...
    if config.get("moe"):
        flags.append(f"MoE {config['num_experts']}e/top-{config['experts_per_token']}")
    verdict = " · ".join(flags)
```

  `dict.get` 的默认值体现了"缺省就是 GPT-2 式"（LayerNorm、GELU、learned）的假设。

### 3.8 格式化与打印

```python
def fmt_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}PB"
```

- 按 1024 进位，标签却写 `GB`，实际是 GiB。所以 Llama 3 8B 的 17.18×10⁹ 字节显示为 `16.0GB`，与讲义的 "17.2 GB" 字节数相同、单位不同。
- `fmt_billions` 只区分 B（十亿）和 M（百万），用十进制。
- `main` 中 `analyze` 被调用两遍（明细一遍、总表一遍），对这么小的计算无所谓；若要复用结果可先存进列表。
- `ratio = b.active_params / b.total_params if b.total_params else 1.0` 防除零，`:.2%` 直接把比例格式化成百分数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用简化 config 字典 + 自造标签 | 字段少、易读，突出六个旋钮 | 不能直接读 HF `config.json`；生产工具需映射 `hidden_act`、`tie_word_embeddings`、`rope_scaling` 等真实字段 |
| 不算 LM head | 代码短 | 不共享权重的模型少算 `V·h`（Llama 3 8B 少 525M）；应按 `tie_word_embeddings` 决定 |
| 不算 bias 和学习式位置 | 现代模型多数无 bias、用 RoPE | GPT-2、Qwen 2.5 会有小误差（GPT-2 少 0.87M） |
| MLA 用 `kv_lora_rank` 粗略近似 | 避免引入 6 个 MLA 专有字段 | DeepSeek-V3 每层注意力少算约 70M，总参数少约 4.25B；KV cache 高估约 1.8 倍 |
| router 计入激活参数 | router 对每个 token 都要算 | 正确；还应考虑专家负载不均、capacity factor 等运行时因素 |
| KV cache 一律按 BF16、满上下文 | 给出"最坏情况"上界 | 实际服务用 PagedAttention 按需分配，可再做 FP8 KV 量化 |
| 不算激活显存 | 讲义只给了经验公式 | 讲义称"See code/main.py for the exact formulas"，但代码中没有；训练显存估算需另行补上 |
| `fmt_bytes` 按 1024 进位却标 GB | 习惯写法 | 与讲义十进制数字差约 7.4%，比较时需统一单位 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，旧版本 Python 也能写 `dict`、`int` 等新式注解 |
| 嵌套字典字面量 | `CONFIGS = {"gpt2-small": {...}, ...}` | 外层按模型名索引，内层是字段 |
| 数字下划线分隔 | `1_000_000_000` | 只为可读性，等价于 `1000000000` |
| `@dataclass` | `class Breakdown:` | 自动生成构造函数；字段带类型注解 |
| 类型注解 | `def analyze(name: str, config: dict) -> Breakdown:`、`-> None` | 说明参数和返回值类型，不在运行时强制 |
| `dict.get(key, default)` | `config.get("activation", "gelu")`、`config.get("shared_experts", 0)` | 键不存在时返回默认值，用于可选字段 |
| `dict[key]` 直接取值 | `config["num_attention_heads"]` | 必填字段，缺失时抛 `KeyError`——让错误尽早暴露 |
| 整除 `//` | `head_dim = h // q_heads` | 结果为整数；不能整除时会悄悄截断（这里应保证整除） |
| 原地除法 `/=` | `b /= 1024` | 把 `b` 变成浮点数后继续比较 |
| `for ... in` + 提前 `return` | `fmt_bytes` 中的循环 | 找到合适单位立即返回；循环结束仍未返回则落到 `PB` |
| f-string 格式符 | `{x / 1e9:.1f}`、`{x:,}`、`{name:18s}`、`{...:>8s}`、`{ratio:.2%}`、`{b.mlp_ratio:.2f}` | 小数位、千分位、左/右对齐宽度、百分比 |
| 多行 f-string 拼接 | `print(f"  mlp  / layer : ..." f"(ratio ...)")` | 相邻字符串字面量自动拼接 |
| `str.upper()` / `str.join` | `config.get("norm", ...).upper()`、`" · ".join(flags)` | 大写化；用分隔符连接列表 |
| 条件表达式 | `h if config.get("norm") == "rmsnorm" else 2 * h` | 一行 if/else |
| 括号内换行 | `total = (emb + first_dense * ... + final_norm)` | 长表达式用括号包起来即可跨行 |
| `dict.items()` 遍历 | `for name, config in CONFIGS.items():` | 同时取键和值 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行，方便在别处复用 `analyze` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（瞬间完成），输出节选：

```text
llama3-8b
----------------------------------------------------------------------
  architecture    : RMSNORM · SWIGLU · ROPE · GQA (32/8)
  total params    : 7.5B           ← 少了不共享的 LM head 525M，补上为 8.03B
  active params   : 7.5B
  embedding       : 525.3M
  attn / layer    : 41.9M          ← 2·4096² + 2·4096·1024
  mlp  / layer    : 176.2M  (ratio ff/h = 3.50)
  context length  : 131,072
  KV cache BF16   : 16.0GB  (per sequence at max context)   ← 实为 16.0 GiB = 17.2 GB

mixtral-8x7b
  architecture    : RMSNORM · SWIGLU · ROPE · GQA (32/8) · MoE 8e/top-2
  total params    : 46.6B
  active params   : 12.7B
  KV cache BF16   : 4.0GB

deepseek-v3
  architecture    : RMSNORM · SWIGLU · ROPE · MLA · MoE 256e/top-8
  total params    : 665.9B         ← 讲义 671B
  active params   : 32.4B          ← 讲义 37B
  attn / layer    : 117.4M         ← MLA 维度被简化，真实约 187.1M
  mlp  / layer    : 44.0M  (ratio ff/h = 0.29)   ← 单个专家
  KV cache BF16   : 15.2GB         ← 按 c_KV + RoPE key 应约 8.58 GiB

HEADLINE RATIOS
  gpt2-small          total=  123.6M  active=  123.6M  active/total=100.00%  attn=MHA
  mistral-7b          total=    7.1B  active=    7.1B  active/total=100.00%  attn=GQA (32/8)
  llama3-8b           total=    7.5B  active=    7.5B  active/total=100.00%  attn=GQA (32/8)
  llama3-70b          total=   69.5B  active=   69.5B  active/total=100.00%  attn=GQA (64/8)
  mixtral-8x7b        total=   46.6B  active=   12.7B  active/total=27.37%  attn=GQA (32/8)
  qwen2.5-72b         total=   71.5B  active=   71.5B  active/total=100.00%  attn=GQA (64/8)
  deepseek-v3         total=  665.9B  active=   32.4B  active/total=4.86%  attn=MLA
```

逐项解读（数字均已用 Python 复核）：

- **补 LM head 后与官方数字吻合**：Mistral 7B 7.24B、Llama 3 8B 8.03B、Llama 3 70B 70.55B、Qwen 2.5 72B 72.71B、Mixtral 46.7B / 12.9B。说明代码其余部分的公式基本正确，主要缺口就是 LM head。
- **DeepSeek-V3 需要两处修正**：补 LM head（+0.93B）和用真实 MLA 维度（每层 +69.7M，×61 层 = +4.25B），得到 671.0B / 37.6B，与讲义一致（测验 Q9）。
- **GPT-2 Small 123.6M**：缺学习式位置 embedding 与全部 bias，补上后精确等于 124,439,808。
- **KV cache 对比**：Mistral 7B 与 Mixtral 8x7B 一样都是 4.0 GiB（注意力结构相同，MoE 不影响 KV cache）；Llama 3 70B 与 Qwen 2.5 72B 都是 40 GiB（80 层 × 8 KV 头）；Llama 3 8B 在 128k 下 16 GiB，已与 BF16 权重（约 16 GB）相当——讲义："The KV cache for a single 128k sequence is larger than the weights."
- **active/total 的口径**：Mixtral 27.37%、DeepSeek-V3 4.86% 是"全部激活参数 / 全部参数"，包含注意力等共享部分；按"路由专家"口径则是 25% 与 3.125%。

---

## 7. 动手改一改

1. **补 LM head**：给每个 config 加 `tie_word_embeddings`（GPT-2 为 True，其余为 False），在 `analyze` 中不共享时加 `vocab × h`，确认 Llama 3 8B 变为 8.03B。
2. **补 GPT-2 的位置 embedding 与 bias**：加 `position == "learned"` 时 `max_position_embeddings × h`，以及 `use_bias` 字段，使 GPT-2 输出 124,439,808。
3. **重写 MLA**：增加 `q_lora_rank`、`qk_nope_head_dim`、`qk_rope_head_dim`、`v_head_dim` 字段，按测验 Q9 的公式计算注意力参数和 `(kv_lora_rank + qk_rope_head_dim) × 层数 × 2 字节` 的 KV cache，目标输出 671.0B / 37.6B、约 8.58 GiB。
4. **加入 Llama 3 405B 与 Gemma 2 9B**：405B 用 126 层、16384 hidden、128 Q 头、8 KV 头、53248 intermediate；对比它与 DeepSeek-V3 的 KV cache（讲义"Use It"想让你看到的结论）。Gemma 2 需要额外实现"一半层 sliding window"的 KV cache（讲义练习 4）。
5. **加一个部署检查函数**：`fits(config, vram_gb, context, batch, weight_bytes=2, kv_bytes=2)`，返回权重 + KV cache 是否放得下以及最大并发数；用它回答"Llama 3 8B 在 80GB 卡上 32k 上下文能服务几条会话"（约 14.9 条满长度序列）。
6. **让它读真实 config.json**：写一个 `from_hf_config(path)`，把 `hidden_act`、`num_local_experts`、`num_experts_per_tok`、`n_routed_experts` 等真实字段映射成本文件的格式。

---

## 8. 常见坑

- **忘了 LM head 是否共享**：Llama 3 系列不共享，128K 词表下每份 `V·h` 在 8B 模型上就是 0.5B。
- **用 Q 头数算 KV cache**：GQA/MQA 必须用 `num_key_value_heads`；用错会高估 4–16 倍（第 04 节测验 Q12 的同类问题）。
- **把 MLA 当成"K 和 V 各存一份潜变量"**：MLA 的 K、V 共享同一个 `c_KV`，另加一个小的 RoPE key。
- **`head_dim = hidden / heads` 不总成立**：DeepSeek-V3（192/128）、Gemma 2（256）等模型的 head_dim 是独立配置的，应优先读 `head_dim` 字段。
- **把 MoE 的 `mlp / layer` 当成整层 MLP**：代码里打印的是单个专家的参数。
- **GB 与 GiB 混用**：`fmt_bytes` 按 1024 进位但标 GB，与讲义十进制数字相差约 7.4%。
- **以为 MoE 省显存**：激活参数决定每 token 计算量，显存仍按总参数计算。
- **照抄二手表格**：讲义表中 Llama 3 405B 写作 "GQA (128/16)"，与第 04 节"Llama 3 全系列 8 个 KV 头"的说法矛盾；讲义的激活显存"8 GB"与其自身公式算出的 2.1 GB 不符。以模型官方 config 为准。
