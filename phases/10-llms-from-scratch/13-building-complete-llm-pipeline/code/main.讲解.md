# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 13 节 构建一个完整的 LLM Pipeline ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [plan|run|gate|demo]`（不带参数即 `demo`） ｜ **依赖**：仅标准库（`hashlib`、`json`、`sys`、`time`、`dataclasses`），无需 GPU、无需网络

---

## 1. 这份代码在考察什么

前 12 节每节都是一个"能跑的 notebook"；这一节不训练任何模型，而是写一个**编排层（orchestrator）**，把那些 notebook 串成一条可审计、可回滚的流水线。代码考察的是"流水线卫生（pipeline hygiene）"的几个基本构件：

1. **DAG**：12 个 stage 及其依赖写成一张表 `STAGES`，07（RLHF）与 08（DPO）是并列分支，09 汇合。
2. **内容寻址的产物仓库**：`ArtifactStore` 用 SHA-256 作为键，模拟 S3/R2/GCS。
3. **哈希链**：每个 stage 的输出哈希由"自身信息 + 上游哈希 + seed"决定，上游任何变化都会传导到下游。
4. **Manifest**：用 dataclass 记录版本、seed、git commit、每个 stage 的记录、gate、eval 指标、预算和总成本。
5. **预算控制**：逐 stage 累加成本，超预算就停机。
6. **Eval gate**：数值阈值逐项比较，输出 `PASS/HOLD` 和最终 `SHIP/HOLD`。

> 一句话：**代码很小，纪律很大**——它用 stdlib 证明"管道的管子是通的"，以便在花 GPU 钱之前发现契约错误。同时它也省略了讲义描述的不少能力，读代码时要分清"演示了什么"和"只在讲义里说了什么"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `STAGES` | 模块级常量（列表） | 12 个 `(名称, 依赖列表, 产物类型)` 三元组，已按拓扑序排列 | 十二 stage 的 DAG |
| `DEFAULT_GATES` | 模块级常量（字典） | 6 个指标的 `op` 与阈值 | Eval gate |
| `StageRecord` | dataclass | 单个 stage 的输入哈希、输出哈希、墙钟、成本、状态 | manifest 中的 stage 条目 |
| `Manifest` | dataclass | 整次运行的描述：版本、seed、stages、gates、指标、预算 | Manifest |
| `ArtifactStore` | 类 | `put/get/has/__len__`，键为 SHA-256 | 内容寻址产物仓库 |
| `simulate_stage` | 函数 | 占位 stage：产出确定性 JSON blob + 查表得到的墙钟与成本 | 可替换为真实训练脚本 |
| `plan` | 函数 | 打印版本、seed、预算、DAG、gate | `plan` 命令 |
| `run` | 函数 | 按顺序执行 stage、写入 store、记账、预算超限即返回、最后注入 eval 指标 | 编排器主循环 |
| `gate` | 函数 | 逐项比较指标与阈值，设置 `manifest.shippable` | Ship gate |
| `manifest_to_json` | 函数 | `asdict` + `json.dumps` 序列化 | Manifest 输出 |
| `main` | 函数 | 解析子命令 `plan/run/gate/demo`，返回退出码 | CLI 入口 |

数据流：`main` 构造 `Manifest` 与 `ArtifactStore` → `plan` 打印 DAG → `run` 沿 `STAGES` 逐个调用 `simulate_stage` → `store.put` 得到哈希 → 记入 `StageRecord` → 填充 `eval_metrics` → `gate` 比较阈值 → 输出 `SHIP` 或 `HOLD`。

---

## 3. 逐段精讲

### 3.1 DAG 与 gate 都是"数据"而不是代码

```python
STAGES = [
    ("01_tokenizer_vocab",         [],                     "tokenizer"),
    ("02_tokenizer_trained",       ["01_tokenizer_vocab"], "tokenizer"),
    ...
    ("07_reward_ppo_policy",       ["06_sft_checkpoint"],  "policy"),
    ("08_dpo_policy",              ["06_sft_checkpoint"],  "policy"),
    ("09_cai_grpo_policy",         ["07_reward_ppo_policy", "08_dpo_policy"], "policy"),
    ("10_eval_report",             ["09_cai_grpo_policy"], "eval_report"),
    ("11_quantized_weights",       ["09_cai_grpo_policy"], "quantized_model"),
    ("12_inference_server",        ["11_quantized_weights"], "server_spec"),
]
```

- 每个元素是"名称、依赖、产物类型"。依赖关系与讲义的 mermaid 图完全对应：06 分叉成 07/08，09 汇合，09 再分叉成 10（eval）和 11→12（量化→serving）。
- 列表顺序**已经是拓扑序**，`run` 直接按列表顺序执行。讲义说编排器要"Resolve the DAG from the manifest"，但代码并没有做拓扑排序——如果有人把 `09` 挪到 `07` 前面，`name_to_hash[d]` 会抛 `KeyError`。这是简化之处。
- 产物类型（`tokenizer`、`checkpoint`、`policy`…）对应讲义"Artifact Typing"表，但代码**只用它查成本表**，并没有校验"下游拿到的上游类型是否正确"。
- `DEFAULT_GATES` 把 gate 写成 `{"op": ">=", "value": 65.0}` 这样的数据，讲义强调"Every gate is a numeric threshold. No 'looks good' gates."

### 3.2 `StageRecord` 与 `Manifest`：dataclass 作为 manifest schema

```python
@dataclass
class StageRecord:
    name: str
    stage_type: str
    input_hashes: list[str] = field(default_factory=list)
    output_hash: str = ""
    wall_clock_sec: float = 0.0
    cost_usd: float = 0.0
    status: str = "pending"


@dataclass
class Manifest:
    pipeline_version: str = "1.0.0"
    seed: int = 42
    git_commit: str = "unknown"
    stages: list[StageRecord] = field(default_factory=list)
    gates: dict = field(default_factory=lambda: dict(DEFAULT_GATES))
    ...
    shippable: bool = False
```

- 字段与讲义 manifest YAML 示例一一对应（`pipeline_version`、`seed`、`git_commit`、每 stage 的 `input_hash/output_hash/wall_clock_sec/cost_usd`）。
- 可变默认值（list、dict）必须用 `field(default_factory=...)`，否则所有实例共享同一个对象（dataclass 会直接报错阻止你写 `stages: list = []`）。
- ⚠️ **浅拷贝陷阱**：`dict(DEFAULT_GATES)` 只复制了外层字典，内层 `{"op", "value"}` 仍与全局常量共享。实测：`a = Manifest(); a.gates["mmlu"]["value"] = 99.0` 之后，新建的 `Manifest()` 和 `DEFAULT_GATES` 里的 mmlu 阈值都变成了 99.0。应改用 `copy.deepcopy`（见测验 Q11）。
- 讲义中写的是 `Stage` dataclass，代码里叫 `StageRecord`，含义相同。

### 3.3 `ArtifactStore`：内容寻址

```python
    def put(self, blob: bytes) -> str:
        h = hashlib.sha256(blob).hexdigest()
        self._store[h] = blob
        return h
```

- 地址就是内容的 SHA-256（64 个十六进制字符）。同样的字节一定得到同样的地址；不同内容几乎不可能碰撞。
- 天然去重：同一 blob 放两次只占一个键。
- `__len__` 让 `len(store)` 可用，demo 里打印 `artifacts stored : 12`。
- ⚠️ `get` 不校验内容是否仍与地址一致——真实对象存储可能出现损坏或被覆盖，生产代码在读取时会重新哈希。

### 3.4 `simulate_stage`：确定性的占位 stage

```python
    payload = {"stage": name, "type": stage_type, "inputs": inputs, "seed": seed}
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")

    cost_table = {
        "tokenizer":        (60,    5),
        "dataset":          (1800,  50),
        "checkpoint":       (7200,  400),
        ...
    }
    wall, cost = cost_table.get(stage_type, (100, 5))
```

- payload 只包含"我是谁 + 我的输入哈希 + seed"，所以输出完全确定。`sort_keys=True` 保证序列化字节稳定。
- 因为 `inputs` 是上游哈希，哈希形成**链式依赖**：实测 seed=42 跑两次 12 个哈希全同，seed=43 时 12 个哈希全部不同；改动任一上游也会让它的全部后代改变——这就是讲义"A change in stage 02 (tokenizer) invalidates every downstream artifact"的代码体现。
- `wall`、`cost` 不是测出来的，而是按产物类型查表（单位：秒、美元）。真实系统会测量墙钟（讲义编排器职责第 3 条"measure wall clock and cost"），这里只是让记账逻辑有数可用。
- `dict.get(key, default)`：未知类型回退为 `(100, 5)`。

### 3.5 `plan`：只读的预检

```python
    for name, deps, stage_type in STAGES:
        dep_str = ", ".join(deps) if deps else "-"
        lines.append(f"  {name:28s}  [{stage_type}]  <- {dep_str}")
```

- 打印 DAG 和 gate 列表，不执行任何 stage，"Running `plan` is free"。
- ⚠️ 函数 docstring 写"compute the cost estimate"，讲义也说 plan 要"compute cost estimate"，但代码**没有计算成本估算**，也没有对比预算。补上的方法很简单：把 `cost_table` 提到模块级，`sum(cost_table[t] for _, _, t in STAGES)` 即可得到 1941，与 `budget_usd` 比较。

### 3.6 `run`：编排器主循环

```python
    name_to_hash: dict[str, str] = {}

    for name, deps, stage_type in STAGES:
        input_hashes = [name_to_hash[d] for d in deps]
        for h in input_hashes:
            if not store.has(h):
                raise RuntimeError(...)

        blob, wall, cost = simulate_stage(name, stage_type, input_hashes, manifest.seed)
        output_hash = store.put(blob)

        manifest.total_cost_usd += cost
        if manifest.total_cost_usd > manifest.budget_usd:
            record = StageRecord(..., output_hash="", status="halted_over_budget")
            manifest.stages.append(record)
            return manifest

        record = StageRecord(..., output_hash=output_hash, status="ok")
        manifest.stages.append(record)
        name_to_hash[name] = output_hash
```

逐行理解：

- `name_to_hash` 是"stage 名 → 输出哈希"的映射，下游据此拿到上游哈希。`input_hashes` 按 `deps` 的**声明顺序**构造，所以 09 的输入永远是 `[07 的哈希, 08 的哈希]`，与执行先后无关——这为讲义练习 1 的并行化打好了基础。
- `store.has(h)` 检查"上游产物在仓库里"。⚠️ 在当前代码中它**永远不会失败**：`name_to_hash` 只在 `store.put` 后写入。它也不校验内容完整性。
- 预算检查在 stage **执行之后**：钱先花了、产物先存了，才判断是否超支。实测把预算设为 1000：01–05 累计 860，06 加 150 后 1010 > 1000，06 被标为 `halted_over_budget`，但 store 里已有 6 个产物（包括 06 的"孤儿产物"）。讲义描述的是"Pre-run estimate ... refuses to start"和"after every stage, the remaining budget is checked"，代码只实现了后者，且是"花完再查"。
- 超预算时**提前 return**，不会走到下面填充 `eval_metrics` 的代码，因此随后 `gate` 会对全部指标报 `missing metric`。
- 最后一段：

```python
    manifest.eval_metrics = injected_eval if injected_eval is not None else {
        "mmlu": 68.4, "humaneval": 42.1, "truthfulqa": 53.7,
        "safety_refusal_rate": 0.03, "kl_from_reference": 18.5,
        "cost_total_usd": manifest.total_cost_usd,
    }
```

  eval 指标是写死的假数据（或由参数注入），真实系统里这些数字来自 stage 10 的 eval report 产物。注意 `is not None` 判断：传入空字典 `{}` 也会被采用（实测所有 gate 都报 missing），而不是退回默认值。
- 讲义编排器职责中的第 2 条（产物已存在则跳过）和第 5 条（失败时写出部分 manifest 并以非零退出）在 `run` 中都没有实现：每次都全量重跑；超预算时只是返回，由 `main` 决定退出码。

### 3.7 `gate`：数值阈值比较

```python
    for metric, g in manifest.gates.items():
        value = manifest.eval_metrics.get(metric)
        if value is None:
            reasons.append(f"HOLD: missing metric {metric}")
            all_pass = False
            continue

        passed = (value >= g["value"]) if g["op"] == ">=" else (value <= g["value"])
```

- 缺失指标直接 HOLD——"没测"不等于"通过"，这一点是对的。
- ⚠️ 只识别 `">="`，其余任何 op 都按 `"<="` 处理。实测 `{"op": ">", "value": 99}` 对 `mmlu=68.4` 给出 `PASS`。配置写错时应该报错而不是静默通过（测验 Q12 给出了用 `operator` 模块的修复）。
- ⚠️ 阈值是绝对值（mmlu ≥ 65.0），讲义 YAML 是相对 baseline（`>= baseline + 0.5`），代码中没有 baseline 概念，也就无法真正做"回归 gate"。
- `cost_total_usd` gate 与 `run` 里的预算检查重复（阈值都是 50000）。
- 讲义提到的"具名 reviewer override 并记录到 manifest"没有实现，`shippable` 只是一个布尔值。

### 3.8 `main`：子命令与退出码

```python
def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "demo"
    ...
    if command == "run":
        manifest = run(manifest, store)
        print(manifest_to_json(manifest))
        return 0 if all(s.status == "ok" for s in manifest.stages) else 2
    if command == "gate":
        manifest = run(manifest, store)
        ok, reasons = gate(manifest)
        ...
        return 0 if ok else 2
```

| 子命令 | 行为 | 退出码 |
|-------|------|-------|
| `plan` | 打印 DAG 与 gate | 0 |
| `run` | 执行全部 stage，打印 manifest JSON | 全部 ok 为 0，否则 2 |
| `gate` | **重新执行** `run`，然后判 gate | SHIP 为 0，HOLD 为 2 |
| `demo`（默认） | plan → run → 通过的 gate → 人为改坏指标后的 gate | 0 |
| 其它 | 打印用法到 stderr | 1 |

- ⚠️ 讲义说 `run` 写出 `manifest.out.yaml`、`gate` 读取它；代码中 `run` 只把 JSON 打到 stdout，`gate` 自己重跑一遍 pipeline，两者之间没有文件传递。在真实系统里"重跑一遍再判 gate"是不可接受的（重跑意味着再花一次训练费用）。
- 退出码区分 1（用法错误）和 2（HOLD/停机），方便 CI 脚本分别处理。
- `raise SystemExit(main(sys.argv))` 把 `main` 的返回值作为进程退出码。

### 3.9 demo 中的"失败 gate"演示

```python
        manifest.eval_metrics["mmlu"] = 42.0
        manifest.eval_metrics["kl_from_reference"] = 40.0
        ok2, reasons2 = gate(manifest)
```

- 直接改写指标模拟两类典型灾难：能力回归（mmlu 掉到 42）和对齐过度（KL 40 > 25），正好对应讲义"两道 gate 拦住大多数灾难"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| DAG 写成有序列表 | 简单直观，免去拓扑排序 | 顺序写错就 `KeyError`；生产中从 manifest 解析并做拓扑排序，07/08 并行执行 |
| 占位 stage 产出 JSON blob | 无需 GPU 就能验证"管子是通的" | 替换为真实训练脚本后输出不再逐比特确定，缓存命中要改用"输入哈希 + 配置哈希" |
| SHA-256 内容寻址、内存字典存储 | 演示"按哈希不按文件名" | 生产用 S3/R2/GCS，读取时重新哈希校验 |
| 成本与墙钟查表 | 让记账逻辑有数据 | 生产中实测墙钟、按实际 GPU 小时计费 |
| 运行后检查预算 | 实现最简单 | 超支已经发生；应运行前估算（6ND / 峰值 / MFU）并在每个 stage 前检查 |
| eval 指标写死 | 演示 gate 逻辑 | 真实指标来自 stage 10 产物，并附 eval 数据哈希 |
| gate 只支持 `>=`/`<=`、绝对阈值 | 代码短 | 未知 op 静默通过；生产需要 baseline 相对阈值、污染检查、override 日志 |
| `gate` 子命令内部重跑 `run` | 不需要文件 IO | 实际应读取已写出的 manifest，绝不能为判 gate 重跑训练 |
| 不实现缓存跳过和部分回滚 | 聚焦主流程 | 讲义练习 4 要求实现；这是节省时间和金钱的关键 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值，可以在旧版本 Python 中写 `list[str]`、`dict | None` |
| 模块 docstring | 文件开头三引号字符串 | 描述模块用途，`help(main)` 可见 |
| 元组列表 + 解包循环 | `for name, deps, stage_type in STAGES:` | 每个元素是三元组，循环时直接拆成三个变量 |
| `@dataclass` | `class StageRecord:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=...)` | `field(default_factory=list)`、`field(default_factory=lambda: dict(DEFAULT_GATES))` | 可变默认值必须用工厂函数，每个实例一份 |
| `lambda` | `lambda: dict(DEFAULT_GATES)` | 匿名函数；这里是无参数的工厂 |
| 浅拷贝 vs 深拷贝 | `dict(DEFAULT_GATES)` | `dict(x)` 只复制一层，嵌套对象仍共享；用 `copy.deepcopy` 复制全部层级 |
| `asdict` | `asdict(manifest)` | 把 dataclass（含嵌套的 dataclass 列表）递归转成字典 |
| 类型注解 | `def put(self, blob: bytes) -> str:`、`dict[str, bytes]`、`dict | None` | 只是提示，不在运行时强制；`X | None` 表示可为空 |
| 返回元组 | `-> tuple[bytes, float, float]`、`blob, wall, cost = simulate_stage(...)` | 一次返回多个值并解包 |
| 魔术方法 `__len__` | `def __len__(self)` | 让 `len(store)` 生效 |
| `in` 判断字典键 | `return h in self._store` | O(1) 查找 |
| `hashlib` | `hashlib.sha256(blob).hexdigest()` | 计算 SHA-256，返回 64 位十六进制字符串 |
| `json.dumps` 参数 | `json.dumps(payload, sort_keys=True)`、`indent=2` | 键排序保证确定性；缩进用于美观输出 |
| `str.encode` | `.encode("utf-8")` | 字符串转字节，哈希只接受字节 |
| `dict.get` 带默认值 | `cost_table.get(stage_type, (100, 5))` | 键不存在时返回默认值而不报错 |
| 条件表达式 | `", ".join(deps) if deps else "-"`、`... if g["op"] == ">=" else ...` | 一行内的 if/else |
| 列表推导式 | `[name_to_hash[d] for d in deps]` | 由依赖名生成哈希列表 |
| `all()` + 生成器表达式 | `all(s.status == "ok" for s in manifest.stages)` | 全部为真才返回 True |
| f-string 格式符 | `{name:28s}`、`${manifest.budget_usd:,.0f}`、`{s.cost_usd:7.0f}`、`{h[:12]}` | 宽度、千分位、小数位、切片 |
| `raise RuntimeError(...)` | 输入哈希缺失时 | 抛出异常中止执行 |
| `print(..., file=sys.stderr)` | 未知命令时 | 错误信息写到标准错误 |
| `sys.argv` | `argv[1] if len(argv) > 1 else "demo"` | 命令行参数，`argv[0]` 是脚本名 |
| `raise SystemExit(main(sys.argv))` | 文件末尾 | 用返回值作为进程退出码 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3，耗时远小于 1 秒），输出节选：

```text
PLAN
============================================================
pipeline_version  : 1.2.3
seed              : 42
budget_usd        : $50,000

dag:
  01_tokenizer_vocab            [tokenizer]  <- -
  ...
  09_cai_grpo_policy            [policy]  <- 07_reward_ppo_policy, 08_dpo_policy
  10_eval_report                [eval_report]  <- 09_cai_grpo_policy
  11_quantized_weights          [quantized_model]  <- 09_cai_grpo_policy
  12_inference_server           [server_spec]  <- 11_quantized_weights

============================================================
RUN
============================================================
  01_tokenizer_vocab           ok                   hash=d1c8213826 cost=$      5  wall=    60s
  02_tokenizer_trained         ok                   hash=f7a2706ef2 cost=$      5  wall=    60s
  03_dataset_sharded           ok                   hash=a60d4ee090 cost=$     50  wall=  1800s
  04_pretrained_base           ok                   hash=e02bde743a cost=$    400  wall=  7200s
  05_scaled_recipe             ok                   hash=0fbfee09b3 cost=$    400  wall=  7200s
  06_sft_checkpoint            ok                   hash=17925691c3 cost=$    150  wall=  3600s
  07_reward_ppo_policy         ok                   hash=9a0cbf54ff cost=$    300  wall=  5400s
  08_dpo_policy                ok                   hash=733f6c37cb cost=$    300  wall=  5400s
  09_cai_grpo_policy           ok                   hash=bd76c49ae2 cost=$    300  wall=  5400s
  10_eval_report               ok                   hash=7c57d5f516 cost=$     20  wall=   600s
  11_quantized_weights         ok                   hash=898b3785e9 cost=$     10  wall=   300s
  12_inference_server          ok                   hash=e630b63af9 cost=$      1  wall=    30s

artifacts stored : 12
total cost_usd   : $1,941
wall (simulated) : 0.000s of orchestrator overhead

GATE (passing eval)
  PASS: mmlu=68.4 >= 65.0
  ...
  PASS: cost_total_usd=1941.0 <= 50000.0
  -> SHIP

GATE (failing eval)
  HOLD: mmlu=42.0 fails gate >= 65.0
  PASS: humaneval=42.1 >= 40.0
  PASS: truthfulqa=53.7 >= 50.0
  PASS: safety_refusal_rate=0.03 <= 0.05
  HOLD: kl_from_reference=40.0 fails gate <= 25.0
  PASS: cost_total_usd=1941.0 <= 50000.0
  -> HOLD
```

逐项解读：

- **哈希是确定的**：在任何机器上用 seed=42 运行，`01_tokenizer_vocab` 的哈希前缀都是 `d1c8213826`。这就是"同事在另一个大洲重放、比对哈希"的最小演示。
- **12 个产物、总成本 $1,941**：`5+5+50+400+400+150+300×3+20+10+1`。模拟墙钟合计 37,050 秒（约 10.3 小时），但这只是表里的数字；`wall (simulated) : 0.000s` 显示的是编排器自身开销，说明编排逻辑几乎不花时间。
- **两次 gate**：第一次全部通过 → SHIP；第二次人为改坏 mmlu 与 KL，两道 gate 报 HOLD → 整体 HOLD。注意每条 gate 都独立报告，便于 reviewer 看清"差在哪"。
- 其它子命令实测：`plan` 只打印前半段；`run` 打印 manifest JSON（`sort_keys=True` 所以键按字母序），退出码 0；`gate` 打印 6 条 PASS 和 `SHIP`，退出码 0；`python3 main.py foo` 打印用法，退出码 1。
- 额外实验（不改原文件，通过 import 调用）：预算设为 1000 时，06 被标记 `halted_over_budget`，`total_cost_usd=1010.0`，store 中 6 个产物，`gate` 输出 6 条 `HOLD: missing metric`。

---

## 7. 动手改一改

1. **补上 plan 的成本估算**：把 `cost_table` 提到模块级，在 `plan` 里打印每个 stage 的预计成本和合计（1941），超出 `budget_usd` 时打印 `REFUSE` 并让 `main` 返回非零。
2. **修复浅拷贝与未知 op**：`Manifest.gates` 改用 `copy.deepcopy`；`gate` 改用 `operator` 映射表并在未知 op 时抛 `ValueError`（测验 Q11、Q12）。
3. **讲义练习 4 · 部分回滚**：实现 `invalidated(failed)` 求后代集合；给 `run` 加一个"已有产物则跳过"的分支；模拟 09 失败后只重跑 09–12，验证模拟墙钟从 37,050 秒降到 6,330 秒（省约 82.9%）。
4. **讲义练习 1 · 并行 07/08**：用 `concurrent.futures.ThreadPoolExecutor` 同时执行 07 与 08，确认 09 的 `input_hashes` 仍按 `deps` 顺序排列、哈希不变。
5. **讲义练习 2 · 污染 gate**：给 `run` 增加"训练语料"和"eval 语料"两个字符串列表，计算 13-gram 重叠率，超过 0.1% 时加入一条 `HOLD: contamination=...`。
6. **讲义练习 3 · 第一性原理成本估算**：写 `estimate_pretrain(params, tokens, mfu=0.4, peak=989e12, price=2.5)`，7B × 2T 应得到约 58,982 GPU 小时、约 $147,455。再把 manifest 写出到文件，让 `gate` 读文件而不是重跑。

---

## 8. 常见坑

- **以为 `store.has` 检查能发现损坏**：它只检查键存在，不重新计算哈希；当前代码里它永远为真。
- **"花完再查"的预算控制**：超支已发生、孤儿产物已写入 store。预算检查要放在 stage 执行之前。
- **dataclass 默认值浅拷贝**：`dict(DEFAULT_GATES)` 让所有 manifest 共享内层 gate 字典，修改一处污染全局。
- **未知比较符静默按 `<=` 处理**：拼写错误的 gate 可能永远 PASS。配置错误必须响亮失败。
- **`injected_eval={}` 不会回退到默认值**：`is not None` 判断让空字典被原样采用，所有 gate 报缺失。
- **按完成顺序拼输入哈希**：做并行化时如果按"谁先完成谁先 append"，09 的哈希会随调度变化；必须按声明顺序。
- **拿 JSON 键序当确定性**：去掉 `sort_keys=True`，在键插入顺序不同的情况下同样内容会得到不同哈希。
- **把讲义里的能力当成代码已实现**：讲义提到的 `Orchestrator.run()`、`EvalGate.check()`、`CostTracker` 类、`manifest.out.yaml`、缓存跳过、类型校验、override 日志，在 `main.py` 中都不存在，需要自己补。
