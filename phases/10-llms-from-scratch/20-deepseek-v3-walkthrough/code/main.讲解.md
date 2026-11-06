# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 20 节 DeepSeek-V3 架构详解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

这是一个"读 config → 算参数"的计算器，专门针对 DeepSeek-V3：

1. **按组件数参数**：embedding、MLA 注意力、稠密 MLP、单个专家、共享专家、路由器、RMSNorm、MTP 模块。
2. **总参数 vs 激活参数**：MoE 层全部 256 个专家都计入总参数，但每个 token 只激活 top-8 + 1 个共享专家。
3. **KV cache**：128K 上下文下 MLA（只存潜向量）与一个假想 GQA（8 个 KV 头 × 128 维）基线的对比。
4. **What-if 变体**：MLA rank 256、512 个专家、top-16 路由，观察三个指标各自怎么变。

它对应讲义的 "The config, field by field"、"Parameter accounting"、"The 671B / 37B ratio" 三节，以及练习 1–3。

最重要的学习点恰恰是它**算不准**的地方：代码给出 664.5B / 30.4B，而官方是 671B / 37B。我们验证过，只要修正两处——MLA 的头维度、LM head 不与 embedding 共享——就能精确得到 671.0B / 37.6B（见 3.3 与测验 Q9）。

> 一句话：**学会把一份 config 拆成"每个组件多少参数、哪些每 token 都激活"**，并能识别计算器与讲义中的错误口径。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEEPSEEK_V3` | 字典常量 | 简化版 config | 读 config |
| `ComponentParams` | dataclass | 各组件参数量 | 参数拆分 |
| `mla_attention_params` | 函数 | Q 低秩路径 + KV 低秩路径 + 输出投影 | MLA |
| `swiglu_mlp_params` | 函数 | `3 · h · ff` | SwiGLU MLP / 专家 |
| `router_params` | 函数 | `h × n_experts` | MoE 路由器 |
| `rmsnorm_params` | 函数 | `2h`（实际 RMSNorm 只有 h） | 归一化 |
| `mtp_module_params` | 函数 | 投影 `2h²` + 注意力 `4h²` + 稠密 MLP + 2 个 norm | MTP 模块 |
| `compute_components` | 函数 | 从 config 算出 `ComponentParams` | 组件参数 |
| `ArchReport` | dataclass | 汇总：总参数、激活、比例、KV cache 等 | 报告 |
| `compute_totals` | 函数 | 组装稠密层/MoE 层/激活 MoE 层，算总数与 KV cache | 总量与激活量 |
| `fmt` / `fmt_bytes` | 函数 | 数字与字节格式化 | 输出 |
| `print_report` | 函数 | 打印一份配置的报告 | 输出 |
| `main` | 函数 | 原始配置 + 3 个 what-if 变体 + HEADLINE | 演示入口 |

数据流：`DEEPSEEK_V3`（或其副本变体）→ `compute_components` → `compute_totals`（层数 × 每层参数、激活量、KV cache）→ `print_report` 格式化打印。

---

## 3. 逐段精讲

### 3.1 config 字典

```python
DEEPSEEK_V3 = {
    "hidden_size": 7168,
    "intermediate_size": 18432,
    "moe_intermediate_size": 2048,
    "num_hidden_layers": 61,
    "first_k_dense_layers": 3,
    "num_attention_heads": 128,
    "num_key_value_heads": 128,
    "kv_lora_rank": 512,
    "q_lora_rank": 1536,
    "num_experts": 256,
    "num_experts_per_tok": 8,
    "shared_experts": 1,
    ...
}
```

- 键名做了简化（Hugging Face 上的真实名字是 `n_routed_experts`、`n_shared_experts`、`first_k_dense_replace` 等），讲义已注明"simplified"。
- ⚠️ 缺少 MLA 最关键的三个维度：`qk_nope_head_dim = 128`、`qk_rope_head_dim = 64`、`v_head_dim = 128`。正因为缺了它们，代码只能用 `h // n_heads` 猜头维度（见 3.3）。
- `num_key_value_heads`、`rope_theta`、`max_position_embeddings`（只在未传 `ctx` 时用到）、`moe_router_enabled` 在计算中都没有实际作用；`from typing import Any` 也没有用到。

### 3.2 SwiGLU、路由器、RMSNorm

```python
def swiglu_mlp_params(hidden: int, ff: int) -> int:
    return 2 * hidden * ff + ff * hidden

def router_params(hidden: int, n_experts: int) -> int:
    return hidden * n_experts

def rmsnorm_params(hidden: int) -> int:
    return 2 * hidden
```

- SwiGLU 有 gate、up、down 三块矩阵，`3 · h · ff`。单个专家：`3 × 7168 × 2048 = 44,040,192 ≈ 44M`；稠密 MLP：`3 × 7168 × 18432 ≈ 396.4M`。讲义写的"每个专家 30M、稠密 MLP 260M"都是错的。
- 路由器是一个 `h → n_experts` 的线性层：`7168 × 256 ≈ 1.8M`。真实 V3 还有每个专家一个的 bias（`e_score_correction_bias`，即无辅助损失负载均衡用的那个 bias），每层只有 256 个参数。
- ⚠️ `rmsnorm_params` 返回 `2h`，这是 LayerNorm（γ 和 β）的数量；RMSNorm 只有缩放 γ，应为 `h`。影响极小（每层几万个参数）。

### 3.3 MLA 注意力：本文件最大的误差来源

```python
def mla_attention_params(hidden, n_heads, head_dim, kv_lora, q_lora):
    q_down = hidden * q_lora
    q_up = q_lora * (n_heads * head_dim)
    kv_down = hidden * kv_lora
    k_up = kv_lora * (n_heads * head_dim)
    v_up = kv_lora * (n_heads * head_dim)
    o_proj = (n_heads * head_dim) * hidden
    return q_down + q_up + kv_down + k_up + v_up + o_proj
```

结构上它抓住了 MLA 的要点：

- **Q 路径**：`h → q_lora (1536) → n_heads × head_dim`，两次矩阵乘（低秩分解）。
- **KV 路径**：`h → kv_lora (512)` 压缩成潜向量，再分别上投影出 K 和 V。推理时缓存的就是这 512 维潜向量。
- **输出投影**：`n_heads × head_dim → h`。

但数值上有两个问题：

| 问题 | 代码 | DeepSeek-V3 实际 |
|------|------|-----------------|
| 头维度 | `head_dim = 7168 // 128 = 56` | q/k 每头 192（128 nope + 64 RoPE），v 每头 128 |
| 解耦 RoPE key | 没有 | `kv_a` 输出 `512 + 64`，多出 64 维共享 RoPE key |
| 每层注意力参数 | **84.4M** | **187.1M**（已计算） |

MLA 的头维度与 hidden 无关——这正是它和标准 MHA 的区别之一；套用"hidden 平均分给各头"的习惯就会严重低估。61 层累计少算约 6.27B（总参数和激活参数都受影响）。

### 3.4 MTP 模块

```python
def mtp_module_params(hidden: int, ff: int) -> int:
    projection = 2 * hidden * hidden
    attention = 4 * hidden * hidden
    mlp = swiglu_mlp_params(hidden, ff)
    norms = 2 * rmsnorm_params(hidden)
    return projection + attention + mlp + norms
```

- 按第 18 节的公式：投影 `M_k`（`h × 2h`）+ 一个 block。这里 block 用的是稠密 MLP（ff = 18432），注意力按 MHA 的 `4h²` 估算，得到约 0.70B。
- 官方 MTP 模块为 14B，因为它的 block 是 MoE 层（约 11.5B）。按 MoE block 计约 11.6B；若再计入 checkpoint 中 MTP 层另外存储的 embedding 与输出头（各约 0.93B），约 13.5B，接近 14B（估算）。
- ⚠️ `compute_totals` 把这 0.70B 的 MTP **加进了总参数**（664.5B 中包含它），但官方的 671B 是**不含** MTP 的主模型。口径不一致。

### 3.5 `compute_totals`：组装层与激活量

```python
    dense_layer = (c.attention_per_layer + c.dense_mlp_per_layer
                   + c.rmsnorm_per_layer)
    moe_layer = (c.attention_per_layer
                 + n_experts * c.expert_mlp_each
                 + c.shared_expert
                 + c.router_per_layer
                 + c.rmsnorm_per_layer)
    active_moe_layer = (c.attention_per_layer
                        + top_k * c.expert_mlp_each
                        + c.shared_expert
                        + c.router_per_layer
                        + c.rmsnorm_per_layer)

    total = (c.embedding
             + first_dense * dense_layer
             + n_moe * moe_layer
             + c.final_norm
             + c.mtp_module)
    active = (c.embedding
              + first_dense * dense_layer
              + n_moe * active_moe_layer
              + c.final_norm)
```

- **总参数** = embedding + 3 个稠密层 + 58 个 MoE 层 + 最终 norm + MTP。其中 MoE 层的 `256 × 44M ≈ 11.27B` 占绝对大头：58 层约 654B 的专家参数，占总参数的 97% 以上。
- **激活参数**：把 256 换成 top-8，加上 1 个共享专家，即每层 9 个专家 ≈ 396M；注意力、稠密层、embedding 全部激活。
- ⚠️ **漏了 LM head**：V3 的 `tie_word_embeddings` 为 false，输出头是另一份 `129280 × 7168 ≈ 0.93B`。讲义 "The invariant core" 写 "Weight-tied embeddings" 对 V3 并不成立。
- 修正注意力（+6.27B）和 LM head（+0.93B）、并去掉 MTP（−0.70B）后：总参数 **671.03B**、激活参数 **37.55B**（已用独立脚本验证）。

### 3.6 KV cache：MLA 与 GQA 基线

```python
    kv_cache = n_layers * cfg["kv_lora_rank"] * max_seq * 2
    kv_heads_hypothetical = 8
    head_dim_hypothetical = 128
    kv_cache_gqa = 2 * n_layers * kv_heads_hypothetical * head_dim_hypothetical * max_seq * 2
```

- MLA：每层每 token 只存 512 维潜向量（K、V 都从它解压），BF16 每值 2 字节：`61 × 512 × 131072 × 2 ≈ 7.6 GiB`。
- GQA 基线：`2（K 与 V）× 61 × 8 × 128 × 131072 × 2 ≈ 30.5 GiB`。讲义称"Llama 3 70B shape"，但用的是 V3 的 61 层（Llama 3 70B 是 80 层，同口径约 40 GiB）。
- ⚠️ 漏了解耦 RoPE key 的 64 维：真实每层每 token 缓存 576 个值，128K 时约 8.58 GiB，相对 GQA 是 3.56× 而不是 4×。
- 更有意义的对比是 V3 若用标准 MHA（128 头，K 192 维、V 128 维）：约 610 GiB——这才说明 MLA 为什么是必需的。
- `ctx or cfg[...]`：传入 `ctx` 就用它，否则用 `max_position_embeddings`。

### 3.7 格式化与报告

```python
def fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}PB"
```

- 每次除以 1024，直到小于 1024 为止。所以显示的 "GB" 实际是 GiB（2³⁰ 字节）：8,187,281,408 字节显示为 7.6GB，按十进制是 8.19 GB。
- `print_report` 中的 "MLA savings" 是 `1 − MLA / GQA基线`，所有变体都对比同一个 GQA 基线（rank-256 变体的 88% 不是相对 rank-512 的节省）。

### 3.8 `main`：变体与 HEADLINE

```python
    variant = dict(DEEPSEEK_V3)
    variant["kv_lora_rank"] = 256
    print_report("DeepSeek-V3 (MLA rank 256 what-if)", variant, ctx=131_072)
```

- `dict(DEEPSEEK_V3)` 做一份**浅拷贝**，修改变体不会影响原 config（值都是不可变的 int/float/bool，浅拷贝足够）。
- ⚠️ 最后的 HEADLINE 写着 "this calculator hits ~476B-490B"，与程序实际输出的 664.5B 不符，显然是旧版本残留；"差额来自 expert-specific biases、shared expert scaling 等结构性参数"的解释也不成立——真正的差额来自 3.3 和 3.5 的两处口径错误。附带的 skill 文件里"拒绝精确到 100M 的匹配，因为简化计算器无法复现"的规则，同样建立在这个误解上。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写简化 config 字典 | 字段一目了然 | 缺 `qk_nope/rope/v_head_dim`；生产中直接读 HF 的 `config.json` |
| `head_dim = h // n_heads` | 沿用 MHA 习惯 | 对 MLA 不成立，每层注意力低估 2.2 倍 |
| 只计一份 embedding | 假设 weight tying | V3 不共享，少算 0.93B |
| MTP 用稠密 block 并计入总数 | 保守估计、展示开销 | 与官方"671B 不含 MTP、MTP 14B 为 MoE"口径不一致 |
| KV cache 只计 512 维潜向量 | 与讲义公式一致 | 漏了 64 维 RoPE key，低估约 12.5% |
| GQA 基线用 61 层、8 头 × 128 维 | 同层数便于对比 | 并非真实 Llama 3 70B；与 MHA 对比更能说明 MLA 的意义 |
| RMSNorm 计 `2h` | 简单 | 应为 `h`；数值影响可忽略 |
| what-if 用字典浅拷贝 | 一行生成变体 | 嵌套结构时需要 `copy.deepcopy` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，使 `int | None` 在 3.8/3.9 也能写在注解里 |
| 字典常量 | `DEEPSEEK_V3 = {...}` | 全大写表示"约定为常量"；用 `cfg["hidden_size"]` 取值 |
| 数字下划线 | `163_840`、`129_280`、`131_072` | 提高可读性 |
| `@dataclass` | `ComponentParams`、`ArchReport` | 自动生成 `__init__`/`__repr__`，用属性访问字段 |
| 联合类型注解 | `ctx: int | None = None` | 可以是 int 或 None（Python 3.10+ 语法） |
| `or` 提供默认值 | `max_seq = ctx or cfg["max_position_embeddings"]` | `ctx` 为 None（或 0）时取后者 |
| 整除 | `head_dim = h // n_heads` | 结果为 int；这里也是 bug 的来源 |
| 多行表达式 | `dense_layer = (a + b\n + c)` | 用括号包起来即可跨行，无需反斜杠 |
| 关键字实参 | `mla_attention_params(h, n_heads, head_dim, kv_lora=..., q_lora=...)` | 混合使用位置参数和关键字参数 |
| 字典浅拷贝 | `variant = dict(DEEPSEEK_V3)` | 新字典、同样的值；改变体不影响原字典 |
| `for` + 提前 `return` | `fmt_bytes` 的单位循环 | 找到合适单位立即返回 |
| 增强赋值 | `b /= 1024` | 等价于 `b = b / 1024`，b 变成 float |
| f-string 格式符 | `{n / 1e9:.1f}B`、`{r.active_ratio:.1%}`、`{ctx_used:,}` | 小数位、百分比、千分位 |
| f-string 内的表达式 | `{(1 - r.kv_cache_bytes / r.gqa_kv_cache_bytes_ref) * 100:.0f}%` | 花括号里可以写完整表达式 |
| 字符串跨行拼接 | `print(f"  MLA savings : "\n f"{...}")` | 相邻字符串字面量会自动拼接 |
| 转义换行 | `print(f"\n{name}")` | `\n` 先输出一个空行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行，便于被其它脚本 import 复用函数 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.05 秒），节选原始配置与三个变体的关键行：

```text
DeepSeek-V3 (published config)
  total params       : 664.5B        ← 官方 671B；修正后 671.0B
  active params      : 30.4B         ← 官方 37B；修正后 37.6B
  active ratio       : 4.6%          ← 官方 37/671 = 5.5%
  embedding          : 926.7M        ← 129280 × 7168；LM head 另有同样大小
  attention / layer  : 84.4M  (MLA)  ← head_dim=56 所致；真实 187.1M
  moe block / layer  : 11.4B  (total)
  active moe / layer : 482.6M  (per forward)
  KV cache BF16, 131,072 ctx : 7.6GB ← 只计 512；计入 RoPE key 为 8.58 GiB
  GQA(8/128) reference       : 30.5GB
  MLA savings              : 75%

DeepSeek-V3 (MLA rank 256 what-if)
  total params 664.2B | active 30.0B | KV cache 3.8GB | MLA savings 88%

DeepSeek-V3 (512 experts, top-8 what-if)
  total params 1318.6B | active 30.5B | active ratio 2.3% | moe block 22.7B

DeepSeek-V3 (256 experts, top-16 what-if)
  total params 664.5B | active 50.8B | active ratio 7.6% | active moe 835.0M

HEADLINE: total 671B published, this calculator hits ~476B-490B   ← 与上面的 664.5B 矛盾
```

逐项解读：

- **总参数 664.5B**：= 主模型 663.8B + 代码自带的 0.70B MTP。与 671B 的差距来自注意力头维度（−6.27B）与 LM head（−0.93B），而不是"各种结构性小参数"。
- **激活参数 30.4B**：同样少了这两项 7.2B；修正后 37.6B。
- **每层 MoE block 11.4B**：= 注意力 84.4M + 257 个专家 × 44.04M + 路由器 1.8M + norm。讲义写的"7.95B per block"偏小约 30%。
- **rank 256 变体**：总参数只降 0.3B（`kv_down`、`k_up`、`v_up` 变小），KV cache 减半；88% 是相对 GQA 基线。
- **512 专家变体**：总参数几乎翻倍，激活几乎不变——"总参数"和"激活参数"是两个独立的旋钮。
- **top-16 变体**：总参数不变，每层激活多 8 个专家（`8 × 44M ≈ 352M`），总激活 +20.4B，计算量和延迟都显著上升。

---

## 7. 动手改一改

1. **修正 MLA 维度**：在 config 中加入 `qk_nope_head_dim=128`、`qk_rope_head_dim=64`、`v_head_dim=128`，按测验 Q9 重写 `mla_attention_params`，确认每层注意力为 187.1M。
2. **加上 LM head、去掉 MTP 出总数**：在 `compute_totals` 中加 `lm_head = vocab * h`（总参数和激活参数都加），把 MTP 单独报告；验证得到约 671.0B / 37.6B。
3. **修正 KV cache**：把缓存维度改为 `kv_lora_rank + qk_rope_head_dim`，并增加一个"标准 MHA"基线，打印三者对比（讲义练习 2 可在此基础上做 rank 256 的分析）。
4. **讲义练习 3**：对比 (256, top-8)、(512, top-8)、(256, top-16)，额外打印"每 token FLOPs ≈ 2 × 激活参数"和"FP8 权重显存 = 总参数 × 1 字节"，讨论容量、计算、显存三者的取舍。
5. **读取真实 config**：从 Hugging Face 下载 DeepSeek-V3 的 `config.json`（需联网），用 `json.load` 读入并映射到本计算器的字段名，实现"任意 DeepSeek 家族模型都能算"。
6. **讲义练习 5**：增加一个 `--dtype` 选项（BF16/FP8/INT4），计算权重显存，并判断能否放进 8×H100、8×H200、8×MI300X 单节点。

---

## 8. 常见坑

- **用 `hidden // n_heads` 推 MLA 头维度**：MLA 的 q/k/v 头维度是独立超参，V3 中 q/k 为 192、v 为 128。
- **默认 weight tying**：大模型通常不共享 embedding 与 LM head（V3、Llama 3 都不共享），少算一份 `V × h`。
- **把 MTP 参数算进 671B**：官方口径是"671B 主模型 + 14B MTP = 685B"。
- **KV cache 漏掉 RoPE key**：MLA 每层每 token 缓存 512 + 64 = 576 个值。
- **GQA 每 token 要存 K 和 V 两份**：讲义正文"8 × 128 = 1024 floats"漏了因子 2。
- **"MLA savings" 的基准**：代码所有变体都相对同一个 GQA(8/128) 基线，不要误读成变体之间的比较。
- **GB 与 GiB 混用**：`fmt_bytes` 用 1024 进制，与讲义中十进制估算可能差 7%。
- **相信 HEADLINE**：最后几行的"476B–490B""差额来自结构性参数"与程序实际输出、与正确的参数账都不符。
