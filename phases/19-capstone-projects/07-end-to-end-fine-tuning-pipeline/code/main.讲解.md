# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 07 节 端到端 Fine-Tuning 流程——从数据、SFT、DPO 到模型服务 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`hashlib`、`json`、`time`、`dataclasses`、`typing`）；不需要 GPU、不训练任何模型

---

## 1. 这份代码在考察什么

讲义描述的是一条真实的 35 小时综合项目：Datatrove 去重 → 污染检查 → Axolotl SFT → TRL DPO → GPTQ/AWQ/GGUF 量化 → vLLM + EAGLE-3 服务 → 评估矩阵 → MOF 2026 model card。这些步骤需要 8×H100，显然没法在一个脚本里跑。

所以 `main.py` 是一个**编排器脚手架（orchestrator scaffold）**，只抓住讲义里"最难的架构原语"（docstring 原话："The hard architectural primitive is a reproducible pipeline DAG"）：

1. **每个阶段是一个函数**：输入"之前的 manifest + 配置"，输出一个新的 `Artifact`。
2. **artifact 按内容求哈希**：同样的内容 → 同样的 ID，这是"一条命令可复现"的基础。
3. **下游记录上游哈希**：形成血缘链（lineage），能从 model card 一路追溯到数据集。
4. **污染检查是一个独立阶段**：对应讲义的 split hygiene。

所有"训练结果"（val_loss、量化体积、EAGLE 接受率、评估增量）都是写死的常量，取自讲义 Use It 部分的示意输出。

> 一句话：**这份代码教的不是怎么训练模型，而是怎么把训练流水线组织成一个可追溯、可复现的 artifact DAG**——同时它自己在几处把血缘链弄断了，这正是最值得读的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Artifact` | dataclass | 一个阶段的产出物：名字、类型、payload、生产者、时间；`content_hash()` 求内容哈希 | artifact / 内容寻址 |
| `Manifest` | dataclass | 以 artifact 名为键保存全部产出；`summary()` 输出四元组列表 | 流水线清单 |
| `Stage` | 类型别名 | `Callable[[Manifest, dict], Artifact]`：所有阶段函数的统一签名 | DAG 节点接口 |
| `stage_data` | 函数 | 按固定比例模拟去重、质量过滤、PII 清洗 | Data 阶段 |
| `stage_contamination` | 函数 | 模拟与三个基准的 MinHash 比对，输出 clean/dirty | split hygiene |
| `stage_sft` / `stage_dpo` | 函数 | 记录 SFT、DPO checkpoint 元数据 | 训练阶段 |
| `stage_quantize` / `stage_serve` | 函数 | 记录三种量化体积、服务指标 | 量化与服务 |
| `stage_eval` / `stage_model_card` | 函数 | 评估增量、MOF model card 元数据 | 评估与发布 |
| `PIPELINE` | 列表 | 8 个 `(名字, 函数)`，定义执行顺序 | 线性化的 DAG |
| `run_pipeline` | 函数 | 依次执行阶段、加入 manifest、打印哈希 | 编排器 |
| `main` | 函数 | 构造配置、跑流水线、打印 manifest 与两份 JSON | 入口 |

数据流：`cfg` → `stage_data`（dataset）→ `stage_contamination`（读 dataset）→ `stage_sft`（读 dataset）→ `stage_dpo`（读 sft）→ `stage_quantize`（读 dpo）→ `stage_serve`（取了 quants 但没用）→ `stage_eval`（读 dpo）→ `stage_model_card`（读 sft）→ 打印。

---

## 3. 逐段精讲

### 3.1 `Artifact`：内容哈希是可复现的地基

```python
@dataclass
class Artifact:
    name: str
    kind: str         # "dataset" | "checkpoint" | "quant" | "endpoint" | "report"
    payload: dict
    produced_by: str
    produced_at: float = field(default_factory=time.time)

    def content_hash(self) -> str:
        blob = json.dumps(self.payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]
```

- `kind` 只是注释约定的 5 种字符串，没有用 `Enum` 或 `Literal` 约束，写错不会报错。
- `produced_at` 用 `field(default_factory=time.time)`：每次创建对象时才调用 `time.time()`。如果写成 `= time.time()`，默认值会在**类定义时**算一次，所有实例共用同一个时间。
- `content_hash` **只对 payload 求哈希**，不含 `produced_at`——所以同一配置重跑，哈希完全一致（实测 `dataset` 恒为 `ca747e11e566`）。这是有意为之：时间戳不是"内容"。
- `sort_keys=True`：保证 dict 键顺序不影响结果（`{"b":1,"a":2}` 与 `{"a":2,"b":1}` 哈希相同，已验证）。没有它，同样的内容可能因为插入顺序不同产生不同哈希，可复现性就破了。
- `default=str`：遇到 `datetime`、`Path` 等 JSON 不认识的对象时转成字符串，而不是抛 `TypeError`。
- `[:12]`：取前 12 个十六进制字符 = 48 bit。按生日界，10⁶ 个 artifact 时碰撞概率约 0.18%，演示够用，生产应保留完整哈希。
- ⚠️ `name`、`kind`、`produced_by` 不参与哈希：两个不同阶段只要 payload 相同就会得到同一个哈希。

### 3.2 `Manifest`：一个以名字为键的字典

```python
@dataclass
class Manifest:
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    def add(self, a: Artifact) -> None:
        self.artifacts[a.name] = a

    def get(self, name: str) -> Artifact:
        return self.artifacts[name]
```

- `field(default_factory=dict)`：dataclass 不允许可变默认值（`= {}` 会直接报 `ValueError`），必须用工厂函数。
- `add` 同名会覆盖；`get` 取不到会抛 `KeyError`。实测单独调用 `stage_sft(Manifest(), {...})` 会得到 `KeyError: 'dataset'`——阶段之间的依赖是**隐式**的，靠 `PIPELINE` 的顺序保证，而不是显式声明 `depends_on`。
- 真实的 DAG 编排器（Airflow、Dagster、Prefect 等）会显式声明依赖，才能并行执行无依赖的阶段（例如 GPTQ、AWQ、GGUF 三个量化可以并行）。

### 3.3 `Stage` 类型别名与数据阶段

```python
Stage = Callable[[Manifest, dict], Artifact]


def stage_data(m: Manifest, cfg: dict) -> Artifact:
    raw_n = cfg.get("raw_examples", 300_000)
    dedup_ratio = 0.94
    qual_ratio = 0.91
    pii_ratio = 0.995
    kept = int(raw_n * dedup_ratio * qual_ratio * pii_ratio)
    return Artifact("dataset", "dataset", {
        "raw_examples": raw_n,
        "after_dedup": int(raw_n * dedup_ratio),
        "after_quality": int(raw_n * dedup_ratio * qual_ratio),
        "after_pii_scrub": kept,
        "seed": cfg.get("seed", 7),
    }, produced_by="Datatrove+Nemotron-CC+Presidio")
```

- 统一签名让所有阶段都能放进同一个列表循环调用——这是"插件式流水线"的最小形态。
- 实际数字：300,000 → 去重 282,000 → 质量过滤 256,620 → PII 清洗 255,336。
- ⚠️ 与讲义 Use It 输出"300k deduped, 12k filtered, 280k accepted"对不上，而且讲义那行自己也不自洽（300k − 12k = 288k）。
- ⚠️ 比例是常量，不是测出来的；PII 清洗通常是**替换/打码**而非删除样本，这里建模成"删掉 0.5%"也是一种简化。
- `seed` 放进 payload，所以改 seed 会改变 dataset 哈希并传递到下游（见第 6 节对比表）。

### 3.4 污染检查：一个"永远绿灯"的门禁

```python
def stage_contamination(m: Manifest, cfg: dict) -> Artifact:
    ds = m.get("dataset")
    overlap = []
    for bench in ("MMLU-Pro", "MT-Bench-v2", "RewardBench-2"):
        # simulated MinHash check; real pipeline uses Datatrove MinHashLSH
        overlap.append({"bench": bench, "overlap_examples": 0})
    return Artifact("contamination_check", "report", {
        "dataset_hash": ds.content_hash(),
        "overlaps": overlap,
        "status": "clean" if all(o["overlap_examples"] == 0 for o in overlap) else "dirty",
    }, produced_by="minhash-lsh")
```

- 报告记录了 `dataset_hash`：说明"我检查的是哪一版数据"——这一点做对了。
- `all(... for o in overlap)`：生成器表达式 + `all`，三个基准都为 0 才是 clean。
- ⚠️ `overlap_examples` 硬编码为 0，`status` 永远是 `"clean"`；讲义练习 4 的"注入 1% 污染"在这份代码里不可能被发现。
- ⚠️ 即使变成 `"dirty"`，`run_pipeline` 也不检查，流水线照样往下跑；`stage_sft` 也不引用这份报告的哈希。门禁既不阻断，也不进入血缘。修复见测验 Q9。

### 3.5 训练两阶段：SFT 与 DPO

```python
def stage_sft(m: Manifest, cfg: dict) -> Artifact:
    ds = m.get("dataset")
    return Artifact("sft_checkpoint", "checkpoint", {
        "base": cfg["base_model"],
        "dataset_hash": ds.content_hash(),
        "epochs": 3,
        "val_loss": 1.03,
        "hours": 6.2,
        "gpus": 8,
    }, produced_by="axolotl v0.8 + ZeRO-3")


def stage_dpo(m: Manifest, cfg: dict) -> Artifact:
    sft = m.get("sft_checkpoint")
    return Artifact("dpo_checkpoint", "checkpoint", {
        "from": sft.content_hash(),
        "epochs": 1,
        "beta": 0.08,
        "hours": 1.7,
    }, produced_by="trl 0.15 DPO")
```

- SFT 记录 `base` 和 `dataset_hash`：换 base model 或换数据，SFT 哈希都会变。`cfg["base_model"]` 用方括号取值，缺键直接 `KeyError`（`run_pipeline({})` 实测在 sft 阶段崩溃）；而 `stage_data` 用 `.get` 带默认值——两种风格混用。
- DPO 用 `"from": sft.content_hash()` 链接上游，这是血缘链的标准写法。
- 数值对照讲义：6.2 小时 = 6h12m ✓；DPO 1.7 小时 = 1h42m，讲义写 1h40m（小出入）；β = 0.08 ✓。
- ⚠️ `main()` 的 `cfg` 里有 `"dpo_beta": 0.08`，但 `stage_dpo` 写死 `"beta": 0.08`，**从不读配置**。实测把 `dpo_beta` 改成 0.2，所有哈希都不变——讲义"Sweep beta"在这份代码里做不到。
- ⚠️ 讲义说 DPO 用 4×H100，payload 里没记 `gpus`；SFT 记了 `epochs: 3`，但讲义说 2–3 epoch，可配置项都被写成了常量。

### 3.6 量化与服务：血缘在这里断开

```python
def stage_quantize(m: Manifest, cfg: dict) -> Artifact:
    ckpt = m.get("dpo_checkpoint")
    return Artifact("quants", "quant", {
        "from": ckpt.content_hash(),
        "gptq_int4_gb": 4.6,
        "awq_int4_gb": 4.8,
        "gguf_q4_km_gb": 5.1,
    }, produced_by="gptq+awq+llama.cpp")


def stage_serve(m: Manifest, cfg: dict) -> Artifact:
    quants = m.get("quants")
    return Artifact("endpoint", "endpoint", {
        "backend": "vLLM 0.7 + EAGLE-3",
        "quant": "GPTQ-INT4-Marlin",
        "eagle_acceptance": 0.74,
        "p99_bs8_ms": 126,
        "tokens_per_sec_bs32": 6400,
        "dollars_per_mtokens": 0.28,
    }, produced_by="vllm+speculators")
```

- 三种量化放在一个 artifact 里；体积与讲义一致（4.6 / 4.8 / 5.1 GB）。8B 参数 × 4 bit ≈ 4 GB，多出来的是缩放因子、零点和保留高精度的层（如 embedding）；GGUF Q4_K_M 是混合精度的 K-quant，平均位宽高于 4，所以最大。
- `stage_serve` 取了 `quants` 变量**却从未使用**，payload 全是常量。实测在 4 种不同配置下 endpoint 哈希都是 `32584f1dc609`。线上服务的模型无法追溯回具体的 checkpoint 和数据集——血缘链在这里断了。修复：加 `"from": quants.content_hash()`。
- 服务指标可以互相推算：`6400 tok/s × 3600 = 23.04M tok/h`，乘 `$0.28/M` ≈ `$6.45/h`，即隐含一个约 6.45 美元/小时、满载 bs=32 的 GPU 实例。
- 讲义要求报告 bs=1/8/32 三档吞吐，代码只给了 bs=32 的吞吐和 bs=8 的 p99。

### 3.7 评估与 model card

```python
def stage_eval(m: Manifest, cfg: dict) -> Artifact:
    ckpt = m.get("dpo_checkpoint")
    return Artifact("eval_report", "report", {
        "from": ckpt.content_hash(),
        "mmlu_pro_delta": 3.2,
        ...
        "llama_guard_4_pass": 0.987,
    }, produced_by="lm-eval-harness")


def stage_model_card(m: Manifest, cfg: dict) -> Artifact:
    return Artifact("model_card", "report", {
        "standard": "MOF 2026",
        "data_license_declared": True,
        "training_config_hash": m.get("sft_checkpoint").content_hash(),
        "eval_attached": True,
        "safety_attached": True,
        "reproducibility_command": "./pipeline.sh config/llama3.3-8b-domainX.yaml",
    }, produced_by="mof-template")
```

- 评估增量与讲义一致（MMLU-Pro +3.2、MT-Bench-v2 +0.41、RewardBench-2 +0.08）；Llama Guard 4 通过率 0.987 是代码新增的数字，讲义没给具体值。
- ⚠️ `stage_eval` 评估的是 **DPO checkpoint**，而不是实际被服务的**量化模型**。讲义 skill 文件的拒绝规则写明："Refuse to ship a quantized model without measuring quality loss on the eval matrix"。
- ⚠️ 只有一组"相对 base 的增量"，没有讲义要求的 base / SFT-only / SFT+DPO / SFT+GRPO 消融矩阵；`PIPELINE` 里也没有 GRPO 分支。
- ⚠️ `training_config_hash` 的值其实是 **SFT checkpoint 的哈希**，不是配置的哈希；`eval_attached: True` 只是布尔值，没有引用 `eval_report` 的哈希。model card 声称"附了评估"，却无法证明附的是哪一份。
- `reproducibility_command` 写死了 llama3.3 的 YAML 路径，换 base model 也不会变。

### 3.8 编排器与入口

```python
PIPELINE: list[tuple[str, Stage]] = [
    ("data", stage_data),
    ...
    ("model_card", stage_model_card),
]


def run_pipeline(cfg: dict) -> Manifest:
    m = Manifest()
    for name, stage_fn in PIPELINE:
        print(f"[{name:14s}] running...")
        art = stage_fn(m, cfg)
        m.add(art)
        print(f"[{name:14s}] -> artifact '{art.name}' hash={art.content_hash()}")
    return m
```

- 函数是一等公民：`stage_fn` 是函数对象，直接 `stage_fn(m, cfg)` 调用。
- "DAG"在这里退化为**线性列表**：没有并行、没有失败重试、没有"已存在相同哈希就跳过"的缓存——而这正是内容哈希最大的工程价值（例如只改了 DPO 的 β，就不必重跑 SFT）。
- 注释说"snapshots manifest each step"，但实际只是往同一个 `Manifest` 里追加，没有保存每一步的快照，也没有把 manifest 写到磁盘。
- `main()` 里的 `f"  {name:18s} ..."` 对 19 个字符的 `contamination_check` 不够宽，输出里那一行会错位（见第 6 节）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 所有阶段用统一签名 `(Manifest, cfg) -> Artifact` | 插件式，列表里循环即可 | 依赖隐式；生产用 Dagster/Airflow/Prefect 显式声明依赖、支持并行与重试 |
| 只对 payload 求 SHA-256 | 去掉时间戳，保证同配置哈希可复现 | 没有对真实权重文件求哈希；生产应哈希权重、数据分片和配置文件本身 |
| 下游 payload 记录上游哈希 | 形成可追溯的血缘链 | 本代码在 `stage_serve` 断链、model card 只引用 SFT；应每一环都记录 |
| 写死的数值（比例、loss、体积、延迟） | 无 GPU 也能运行，展示 artifact 形状 | 不能当作证据；真实数字必须来自 W&B、lm-eval-harness、vLLM benchmark |
| 污染检查只返回 0 | 只演示报告结构 | 需要真实 MinHash LSH，且 `dirty` 时中止流水线 |
| 线性 `PIPELINE` 列表 | 简单直观 | 无法表达 SFT+DPO 与 SFT+GRPO 两个分支的消融，也无法并行量化 |
| 配置是一个普通 dict | 演示方便 | 讲义用 YAML；`dpo_beta` 被忽略说明需要 schema 校验（如 pydantic）防止配置漂移 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可以写 `dict[str, Artifact]` 等新语法而不担心旧版本 |
| `@dataclass` | `class Artifact:` | 自动生成 `__init__`、`__repr__`、`__eq__`，适合"装数据的类" |
| `field(default_factory=...)` | `field(default_factory=time.time)`、`field(default_factory=dict)` | 每个实例创建时调用工厂函数；可变默认值必须这样写 |
| 类型注解 | `def get(self, name: str) -> Artifact:` | 只是提示，运行时不检查 |
| 类型别名 | `Stage = Callable[[Manifest, dict], Artifact]` | 给复杂类型起名字；`Callable[[参数类型...], 返回类型]` |
| 内置泛型 | `dict[str, Artifact]`、`list[tuple[str, Stage]]` | Python 3.9+ 可直接用内置类型做泛型注解 |
| 数字下划线 | `300_000` | 等于 300000，只为可读 |
| `dict.get` 默认值 | `cfg.get("seed", 7)` | 缺键时返回默认值，不抛异常；对比 `cfg["base_model"]` 缺键会 `KeyError` |
| `json.dumps` 参数 | `sort_keys=True, default=str, indent=2` | 排序键、无法序列化时的回退函数、缩进美化输出 |
| `hashlib` | `hashlib.sha256(blob).hexdigest()[:12]` | 对字节求摘要，`.encode()` 先把字符串转为字节 |
| 生成器表达式 + `all` | `all(o["overlap_examples"] == 0 for o in overlap)` | 惰性逐个判断，遇到 False 立刻停止 |
| 列表推导式 | `[(a.name, a.kind, ...) for a in self.artifacts.values()]` | 一行构造列表 |
| 元组解包 | `for name, stage_fn in PIPELINE:`、`for name, kind, h, by in m.summary():` | 循环时直接拆开元组 |
| 函数作为值 | `("data", stage_data)`、`stage_fn(m, cfg)` | 函数可以放进列表、作为变量调用 |
| f-string 格式符 | `{name:14s}`、`{name:18s}` | 字符串左对齐占满宽度；内容超长时不会截断 |
| 条件表达式 | `"clean" if ... else "dirty"` | 三元运算 |
| `if __name__ == "__main__":` | 文件结尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`，瞬间完成）：

```text
=== fine-tuning pipeline run ===
[data          ] running...
[data          ] -> artifact 'dataset' hash=ca747e11e566
[contamination ] running...
[contamination ] -> artifact 'contamination_check' hash=baf1187d0e41
[sft           ] running...
[sft           ] -> artifact 'sft_checkpoint' hash=fdd2cd361ca9
...
[model_card    ] -> artifact 'model_card' hash=a5b50e5c4185

=== manifest ===
  dataset            dataset    ca747e11e566 by Datatrove+Nemotron-CC+Presidio
  contamination_check report     baf1187d0e41 by minhash-lsh      ← 名字 19 字符超过 18 宽，整行右移 1 格
  sft_checkpoint     checkpoint fdd2cd361ca9 by axolotl v0.8 + ZeRO-3
  dpo_checkpoint     checkpoint ef90ec046fe3 by trl 0.15 DPO
  quants             quant      528d8fe6207f by gptq+awq+llama.cpp
  endpoint           endpoint   32584f1dc609 by vllm+speculators
  eval_report        report     494345497149 by lm-eval-harness
  model_card         report     a5b50e5c4185 by mof-template

=== eval report ===
{
  "from": "ef90ec046fe3",          ← 指向 DPO checkpoint，而非被服务的量化模型
  "mmlu_pro_delta": 3.2,
  "mt_bench_v2_delta": 0.41,
  "rewardbench2_delta": 0.08,
  "llama_guard_4_pass": 0.987
}

=== served endpoint ===
{
  "backend": "vLLM 0.7 + EAGLE-3",
  "quant": "GPTQ-INT4-Marlin",
  "eagle_acceptance": 0.74,
  "p99_bs8_ms": 126,
  "tokens_per_sec_bs32": 6400,
  "dollars_per_mtokens": 0.28    ← 隐含 6400×3600×0.28/1e6 ≈ $6.45/小时
}
```

逐项解读：

- **哈希是确定的**：多次运行输出完全一致，因为哈希不含时间戳、键已排序。
- **哈希的传播**：我们额外用 4 种配置跑了一遍，对比各 artifact 哈希：

| artifact | 基线 | seed=8 | base=qwen3-14b | dpo_beta=0.2 |
|---|---|---|---|---|
| dataset | ca747e11e566 | **变** | 不变 | 不变 |
| sft_checkpoint | fdd2cd361ca9 | 变 | **变** | 不变 |
| dpo_checkpoint / quants / eval / card | — | 变 | 变 | 不变 |
| endpoint | 32584f1dc609 | **不变** | **不变** | 不变 |

  - 改 seed：从 dataset 开始一路向下全部改变，符合预期。
  - 改 base model：dataset 不变（数据与模型无关），从 SFT 开始改变，符合预期。
  - 改 `dpo_beta`：什么都不变——配置被忽略。
  - endpoint：任何改动都不变——血缘断裂。
- **eval 与 endpoint 的数字**都直接取自讲义 Use It 示意输出，是常量。

---

## 7. 动手改一改

1. **修复配置漂移**：让 `stage_dpo` 读取 `cfg.get("dpo_beta", 0.08)`；再把 SFT 的 `epochs` 也改为可配置。重跑，确认改 β 后 `dpo_checkpoint` 及下游哈希变化、`sft_checkpoint` 不变。
2. **接上断开的血缘**：给 `stage_serve` 加 `"from": quants.content_hash()`；让 `stage_model_card` 记录 `eval_report`、`endpoint` 的哈希和真实的配置哈希 `sha256(json.dumps(cfg, sort_keys=True))`。
3. **让门禁生效**（讲义练习 4）：实现一个真实的 MinHash（5-gram shingle + 128 个哈希函数），用一小段文本模拟"训练集"和"MMLU-Pro 测试集"，注入一条重复题，确认 `status` 变成 `dirty` 且 `run_pipeline` 抛出异常中止。
4. **按哈希缓存**：把每个 artifact 的 payload 存成 `cache/<hash>.json`，再次运行时若某阶段的"输入哈希组合"已存在就跳过。验证"只改 β 时不会重跑 data 和 SFT"。
5. **消融分支**（讲义练习 1）：把线性 `PIPELINE` 改成显式依赖的 DAG，例如 `{"dpo": ["sft"], "grpo": ["sft"], "eval_dpo": ["dpo"], "eval_grpo": ["grpo"]}`，用拓扑排序执行，输出 base / SFT / SFT+DPO / SFT+GRPO 四列的消融表。
6. **进阶**：让 `stage_eval` 依赖 `quants` 而不是 `dpo_checkpoint`，额外输出"量化前后的质量差"，并在差值超过阈值时拒绝生成 model card。

---

## 8. 常见坑

- **以为"有哈希"就等于"可追溯"**：只有每一环都把上游哈希写进 payload，链条才完整；本代码的 `stage_serve` 就是反例。
- **把时间戳、随机 ID 放进 payload**：哈希每次都变，缓存和复现全部失效。时间这类元数据应放在哈希范围之外（本代码的 `produced_at` 做对了）。
- **忘记 `sort_keys=True`**：dict 插入顺序不同就会导致同内容不同哈希。
- **配置写了但没被读**：`dpo_beta` 就是典型的"配置漂移"，用 schema 校验或在每个阶段 payload 中回显实际使用的配置可以发现。
- **门禁只报告不阻断**：`status: "dirty"` 如果没人检查，等于没有门禁。
- **在 checkpoint 上评估、在量化模型上服务**：两者质量可能不同，评估对象必须是实际上线的那一个。
- **dataclass 可变默认值**：写成 `artifacts: dict = {}` 会报错，必须用 `field(default_factory=dict)`。
- **混用 `cfg[...]` 与 `cfg.get(...)`**：前者缺键崩溃、后者静默用默认值，同一个配置对象最好统一策略并在入口校验。
