# 测验 · 构建一个完整的 LLM Pipeline（Building a Complete LLM Pipeline）

> **阶段 10 · 从零构建 LLM · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 十二个 stage 组成一张 DAG | tokenizer → 数据 → 预训练 → 扩展 → SFT →（RLHF‖DPO）→ CAI/GRPO →（eval、量化 → serving）→ ship gate；07 与 08 可并行，其余是硬依赖 |
| 2 | 失效传播 | 某 stage 变化会让它**和全部后代**失效：改 tokenizer（02）作废所有下游；改 eval（10）只作废 ship 决策 |
| 3 | Manifest | 一个足以重放整次运行的文件：pipeline 版本、seed、git commit、每个 stage 的配置/输入哈希/输出哈希/耗时/成本、gate 阈值 |
| 4 | 哈希链（hash chain） | stage N 的输出哈希就是 stage N+1 的输入哈希，任何不一致立即停机——这是尽早发现数据损坏的手段 |
| 5 | 内容寻址（content-addressed） | 产物按 SHA-256 存取而不是按文件名；`latest.pt` 是"脚枪"，`ckpt-...-sha256:abc.safetensors` 是契约 |
| 6 | 产物类型化（artifact typing） | 每个 stage 输出有名字、有 schema 的类型（Tokenizer、Dataset、Checkpoint、Policy…），防止把 DPO 输出当 SFT 输入这类错误 |
| 7 | Eval gate | 运行前定好的数值阈值，全部通过才可 ship；任何一项失败就 HOLD，只能由具名 reviewer 覆盖且覆盖要写入 manifest。最关键的两道：回归 gate 与 KL budget gate |
| 8 | 成本控制 | 运行前估算（预训练 FLOPs ≈ 6 × 参数 × token，再除以峰值算力 × MFU）超预算则拒绝启动；运行中逐 stage 记账 |
| 9 | 可复现 ≠ 确定性 | 分布式归约顺序、GPU kernel 非确定性、混合精度舍入让权重在 1e-5 量级不同；记录输入/输出哈希和核心指标即可判定"已复现" |
| 10 | 回滚计划三档 | 便宜（小时：tokenizer、eval、量化、serving）、中等（天：SFT、DPO、CAI）、昂贵（周、百万美元：预训练——回退到最后一个好 checkpoint 而不是重跑） |

### 核心技能（能动手做到）

- [ ] 读懂 `STAGES` 列表表示的 DAG，给出任意 stage 失败时需要重跑的集合（失败 stage + 全部后代）
- [ ] 解释 `simulate_stage` 的输出为什么是确定性的，以及为什么改动 seed 或任一上游 stage 会让下游**全部**哈希改变
- [ ] 跑通 `plan / run / gate / demo` 四个子命令，并说出各自的退出码含义
- [ ] 指出本节编排器相对讲义缺失的能力（缓存跳过、哈希完整性校验、类型校验、运行前成本估算、写出 manifest 文件），并能补上其中一两项
- [ ] 按"6 × 参数 × token / (峰值 × MFU)"手算一次预训练的 GPU 小时与美元成本
- [ ] 为一次模型发布设计一组数值化的 eval gate（含回归、KL、安全、污染、成本）

---

## 二、基础自测（选择题）

**Q1.** 在本节代码中，每个 stage 的 `output_hash` 是怎么得到的？

- A. 对 `{"stage", "type", "inputs", "seed"}` 做 `json.dumps(..., sort_keys=True)` 后计算 SHA-256；`inputs` 里装的是上游的输出哈希
- B. 对 stage 名称字符串计算 MD5
- C. 每次运行生成一个随机 UUID，保证不重复
- D. 对当前时间戳和 `wall_clock_sec` 计算 SHA-256

**Q2.** 根据本节 `STAGES` 定义的依赖关系，如果 `08_dpo_policy` 的产物被发现损坏，需要作废并重跑的 stage 集合是：

- A. 只有 08
- B. 07 和 08
- C. 08、09、10、11、12
- D. 06 到 12 全部

**Q3.** 直接运行 `python3 main.py`（默认 `demo`），打印的 `total cost_usd` 是多少？

- A. $1,541
- B. $1,641
- C. $1,891
- D. $1,941

**Q4.** 关于"可复现（reproducible）"与"确定性（deterministic）"，讲义的观点是：

- A. 现代 LLM 训练既可复现也是确定性的，只要固定 seed 就能得到逐比特相同的权重
- B. 现代 LLM 训练可复现但不是确定性的：权重在 1e-5 量级上不同，但下游指标不变；判定"已复现"看各 stage 的输入/输出哈希和核心指标
- C. 只要关闭混合精度，分布式训练就一定是确定性的
- D. 可复现要求权重逐比特一致，确定性只要求指标一致

**Q5.** 把 `Manifest` 的 `budget_usd` 改成 `1000.0` 后调用 `run()` 再调用 `gate()`，会发生什么？

- A. 跑到 `06_sft_checkpoint` 时累计成本 1010 > 1000，该 stage 记为 `halted_over_budget` 并返回；store 中已有 6 个产物；`eval_metrics` 为空，`gate` 对 6 个指标全部报 `HOLD: missing metric`
- B. `run()` 在开始前估算总成本 1941 > 1000，直接拒绝启动，一个 stage 都不执行
- C. 跑到 `05_scaled_recipe` 就停下，累计成本记为 1005
- D. 12 个 stage 全部执行完，仅 `cost_total_usd` 这一道 gate 失败

**Q6.** 讲义说"两道 gate 能拦住大多数灾难，每条生产 pipeline 都有"。这两道是：

- A. 成本 gate 与延迟 gate
- B. 安全拒答率 gate 与 TruthfulQA gate
- C. 数据污染 gate 与成本 gate
- D. 回归 gate（新模型在核心基准上不能比上一版差）与 KL budget gate（对齐后的策略相对 reference 的漂移不能超过上限）

**Q7.** 讲义练习 3：7B 模型、2T token，预训练 FLOPs 按 6 × 参数 × token 估算，H100 BF16 峰值 989 TFLOPs、MFU 40%、$2.50/GPU 小时。估算结果最接近：

- A. 约 2.36 万 GPU 小时，约 $5.9 万
- B. 约 5.9 万 GPU 小时，约 $14.7 万
- C. 约 4.3 万 GPU 小时，约 $10.7 万
- D. 约 590 万 GPU 小时，约 $1,470 万

**Q8.** 关于本节代码中 `gate()` 函数的行为，下列说法正确的是：

- A. 某个指标在 `eval_metrics` 里缺失时会被跳过，视为通过
- B. 阈值是相对 baseline 的（如 `>= baseline + 0.5`），与讲义 YAML 示例一致
- C. 只识别 `">="`，其它任何 op 都按 `"<="` 处理；因此把 mmlu 的 gate 写成 `{"op": ">", "value": 99}` 时，`mmlu=68.4` 会被判为 PASS
- D. `gate` 子命令会读取 `run` 写出的 `manifest.out.yaml` 再判断

---

## 三、动手 / 代码题

**Q9.** 阅读 `run()` 的核心循环：

```python
    for name, deps, stage_type in STAGES:
        input_hashes = [name_to_hash[d] for d in deps]
        for h in input_hashes:
            if not store.has(h):
                raise RuntimeError(f"input hash missing for stage {name}: {h[:12]}...")

        blob, wall, cost = simulate_stage(name, stage_type, input_hashes, manifest.seed)
        output_hash = store.put(blob)

        manifest.total_cost_usd += cost
        if manifest.total_cost_usd > manifest.budget_usd:
            record = StageRecord(..., status="halted_over_budget")
            manifest.stages.append(record)
            return manifest
```

1. `store.has(h)` 这个检查在当前代码里有可能失败吗？为什么？它和讲义说的"verify the output hash against the downstream stage's expected input hash"差在哪里？
2. 预算检查放在哪里？这会导致什么后果（钱、store 内容两方面）？
3. 请改写这段循环：(a) 运行**前**检查"已花费 + 本 stage 预计成本"是否超预算；(b) 取输入时重新计算 `sha256(store.get(h))` 校验完整性；(c) 校验上游产物类型是否符合本 stage 期望（例如 `10_eval_report` 只接受 `policy`）。

**Q10.** 讲义练习 4 要求实现部分回滚：stage 09 失败后，只重跑 09–12，01–08 按哈希命中缓存直接跳过。

1. 写一个函数 `invalidated(failed: str) -> set[str]`，基于 `STAGES` 计算"失败 stage + 全部后代"。
2. 用 `simulate_stage` 的 `wall` 值，计算 09 失败时部分回滚比全量重跑省下多少模拟墙钟时间（秒和百分比）。
3. 说明为什么本节的哈希设计天然支持"按哈希跳过"：01–08 的输出哈希在重跑时会不会变？

**Q11.** 下面这段代码打印什么？为什么？如何修复？

```python
import main as m
a = m.Manifest()
b = m.Manifest()
a.gates["mmlu"]["value"] = 99.0
print(b.gates["mmlu"], m.DEFAULT_GATES["mmlu"])
```

**Q12.** 讲义中的 gate 是相对 baseline 的（`mmlu: >= baseline + 0.5`、`truthfulqa: >= baseline`），而代码里是绝对阈值，且只认 `>=`。请重写 `gate()`，使其：(a) 支持 `>=`、`<=`、`>`、`<`、`==` 五种 op，遇到未知 op 直接报错；(b) 支持 `{"op": ">=", "baseline_delta": 0.5}` 这种相对写法，baseline 指标字典作为参数传入（生产中来自上一次成功运行的 manifest）；(c) 缺 baseline 时 HOLD 并说明原因。

---

## 四、面试高频题

**Q13.**（基础必考）什么是训练 pipeline 的 manifest？为什么产物要"内容寻址"而不是按文件名存？请举一个按文件名存导致事故的例子。

**Q14.**（原理深挖）为什么大规模分布式 LLM 训练很难做到逐比特确定？既然做不到，团队怎么判断"同事在另一个集群上复现了我的结果"？

**Q15.**（工程实践）你负责一个对齐后模型的发布。请设计一套 eval gate：包含哪些指标、阈值怎么定、数据从哪里来、失败了怎么处理？

**Q16.**（场景设计）一次计划 50 天的预训练进行到第 30 天，发现第 25 天之后的 checkpoint 训练 loss 出现异常尖峰且无法恢复，数据团队同时报告某个数据分片混入了评测集。你的回滚方案是什么？哪些 stage 要重跑、哪些不用？

**Q17.**（追问型）讲义说编排器"不是 Airflow，不是 Kubeflow，而是你自己写的无聊代码"。你同意吗？另外，若让 07（RLHF）和 08（DPO）并行跑，怎么保证 09 的输入哈希仍然是确定的？

---

## 五、参考答案与解析

### Q1 — 答案：A

代码原文：

```python
    payload = {"stage": name, "type": stage_type, "inputs": inputs, "seed": seed}
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    ...
    output_hash = store.put(blob)   # put 内部 hashlib.sha256(blob).hexdigest()
```

`inputs` 是上游的输出哈希列表，所以哈希沿 DAG 层层"嵌套"：改 seed 或任一上游，下游全部改变。本地实测：seed=42 跑两次，12 个哈希全部相同；seed 改成 43，12 个哈希**全部**不同。`sort_keys=True` 保证字典键顺序固定，否则同样内容可能序列化成不同字节。B、C、D 都不是内容寻址：B 与内容无关，C 不可复现，D 每次运行都变。

### Q2 — 答案：C

DAG 中 08 的后代：09（依赖 07 和 08）→ 10、11（都依赖 09）→ 12（依赖 11）。所以作废集合是 `{08, 09, 10, 11, 12}`。07 与 08 是兄弟节点（都只依赖 06），不受影响，故 B 错；D 是 06 失败时的集合（讲义原文："A failure at stage 06 (SFT) invalidates 06, 07, 08, 09, 10, 11, 12"）。已用脚本对 `STAGES` 求后代验证。

### Q3 — 答案：D

`cost_table` 中：tokenizer 5（×2）、dataset 50、checkpoint 400（×2，04 和 05 都是 checkpoint）、sft_model 150、policy 300（×3，07/08/09）、eval_report 20、quantized_model 10、server_spec 1。合计 `10 + 50 + 800 + 150 + 900 + 20 + 10 + 1 = 1941`，与实际运行输出 `total cost_usd   : $1,941` 一致。A 漏了 05 的 400；B 少算了一个 policy stage（300）；C 是随手凑的干扰值。

### Q4 — 答案：B

讲义原文："Modern LLM training is reproducible but not deterministic"，差异来自 reduce 顺序、cuBLAS/flash-attn 的 kernel 非确定性与混合精度舍入，量级约 1e-5；"if those match, the run is 'reproduced' even if the weights are not bit-identical"。A 错在"逐比特相同"；C 错，关闭混合精度并不能消除归约顺序与 kernel 的非确定性；D 把两个定义说反了。

### Q5 — 答案：A

实际运行结果：01–05 累计 `5+5+50+400+400 = 860`，06 加 150 后为 1010 > 1000，06 被记为 `halted_over_budget`，`run()` 立即返回。注意两个细节：① `store.put(blob)` 发生在预算检查**之前**，所以 store 里有 6 个产物（包括被"拒绝"的 06）；② `total_cost_usd` 记为 1010，钱已经花了才发现超支。因为提前 return，`eval_metrics` 没有被填充，`gate()` 对 6 个指标都输出 `HOLD: missing metric ...`。B 是讲义描述的"运行前估算"，但代码没有实现；C 算错了停止位置；D 忽略了运行中的预算检查。

### Q6 — 答案：D

讲义原文："A *regression* gate ... catches training bugs. A *KL budget* gate ... catches alignment overcooking. Every production pipeline has both." 其它选项里的指标也重要（安全、成本、污染都在讲义或 outputs 技能文件中出现），但不是讲义点名"拦住大多数灾难"的那两道。

### Q7 — 答案：B

`FLOPs = 6 × 7e9 × 2e12 = 8.4e22`；`8.4e22 / (989e12 × 0.4) ≈ 2.12e8 秒 ≈ 58,982 GPU 小时`；`× $2.50 ≈ $147,455`（已用 Python 计算）。A 是 MFU 按 100% 算的结果（23,593 小时）；C 是按 55% MFU 算的结果（讲义 Key Terms："40% is typical at 70B scale, 55% at 7B"，所以 7B 用 55% 也有道理，但题目指定 40%）；D 多乘了 100。可以作为对照的事实：讲义称 Llama 3 405B 用了约 3,000 万 H100 小时。

### Q8 — 答案：C

代码原文：

```python
        passed = (value >= g["value"]) if g["op"] == ">=" else (value <= g["value"])
```

任何非 `">="` 的 op 都落入 `<=` 分支。实测 `{"op": ">", "value": 99}` 输出 `PASS: mmlu=68.4 > 99`，`{"op": "==", "value": 68.4}` 也是 PASS——这是"静默接受错误配置"的典型 bug。A 错：缺失指标会 `HOLD: missing metric`；B 错：代码是绝对阈值（65.0、40.0…），讲义 YAML 才是相对 baseline；D 错：`gate` 子命令内部重新调用 `run()`，并不读文件，代码也从未写出 `manifest.out.yaml`。

### Q9 — 参考答案

1. **不可能失败**。`input_hashes` 取自 `name_to_hash`，而 `name_to_hash` 只在 `store.put` 之后写入，所以里面的哈希一定在 store 中。这个检查只是"存在性"检查，既不验证内容完整性（没有重新计算 SHA-256），也不验证"上游输出 == 下游期望输入"（下游没有独立声明的期望哈希，例如来自上一次成功运行的 manifest）。真实系统里，存储位翻转、对象被覆盖、读到旧版本都应该在这里被拦下。
2. **预算检查在 stage 执行之后**：先 `simulate_stage` 并 `store.put`，再累加成本、再比较。后果：超预算的那个 stage 已经花了钱（`total_cost_usd` 会超过 `budget_usd`），而且它的产物留在 store 里却没有对应的 `ok` 记录（`output_hash=""`），成了"孤儿产物"。讲义要求的是"Pre-run estimate... If the estimate exceeds the budget gate, the pipeline refuses to start"。
3. 参考改写（已在本地运行验证：预算 1000 时在 06 之前停下，`total_cost_usd` 停在 860，store 只有 5 个产物）：

```python
EXPECTED_INPUT_TYPES = {
    "02_tokenizer_trained": {"tokenizer"}, "03_dataset_sharded": {"tokenizer"},
    "04_pretrained_base": {"dataset"}, "05_scaled_recipe": {"checkpoint"},
    "06_sft_checkpoint": {"checkpoint"}, "07_reward_ppo_policy": {"sft_model"},
    "08_dpo_policy": {"sft_model"}, "09_cai_grpo_policy": {"policy"},
    "10_eval_report": {"policy"}, "11_quantized_weights": {"policy"},
    "12_inference_server": {"quantized_model"},
}

def run_checked(manifest, store, estimate):          # estimate: stage_type -> 预计成本
    name_to_hash, name_to_type = {}, {}
    for name, deps, stage_type in STAGES:
        # (a) 运行前预算检查
        if manifest.total_cost_usd + estimate[stage_type] > manifest.budget_usd:
            manifest.stages.append(StageRecord(name=name, stage_type=stage_type,
                                               status="refused_over_budget"))
            return manifest
        input_hashes = []
        for d in deps:
            h = name_to_hash[d]
            # (b) 完整性校验：内容的哈希必须等于地址
            if hashlib.sha256(store.get(h)).hexdigest() != h:
                raise RuntimeError(f"corrupted artifact for {d}")
            # (c) 类型校验
            if name_to_type[d] not in EXPECTED_INPUT_TYPES[name]:
                raise TypeError(f"{name} got {name_to_type[d]} from {d}")
            input_hashes.append(h)
        blob, wall, cost = simulate_stage(name, stage_type, input_hashes, manifest.seed)
        h = store.put(blob)
        manifest.total_cost_usd += cost
        manifest.stages.append(StageRecord(name=name, stage_type=stage_type,
                                           input_hashes=input_hashes, output_hash=h,
                                           wall_clock_sec=wall, cost_usd=cost, status="ok"))
        name_to_hash[name], name_to_type[name] = h, stage_type
    return manifest
```

要点：预算判断用"已花 + 预计"；完整性用"重新哈希 == 地址"；类型表就是讲义"Artifact Typing"表格的代码化，让"把 DPO 输出当 SFT 输入"变成立即失败而不是第五天才发现。

### Q10 — 参考答案

1. 求后代集合：

```python
def invalidated(failed: str) -> set[str]:
    children = {}
    for name, deps, _ in STAGES:
        for d in deps:
            children.setdefault(d, []).append(name)
    out, stack = set(), [failed]
    while stack:
        n = stack.pop()
        if n not in out:
            out.add(n)
            stack.extend(children.get(n, []))
    return out

# invalidated("09_cai_grpo_policy") -> {09, 10, 11, 12}
# invalidated("11_quantized_weights") -> {11, 12}
```

2. 09–12 的模拟墙钟：`5400 + 600 + 300 + 30 = 6330` 秒；全量为 `37050` 秒。省下 `30720` 秒，约 **82.9%**（已用 Python 计算）。成本方面只需重花 `300 + 20 + 10 + 1 = $331`，而不是 $1,941。
3. 01–08 的 payload 只由 stage 名、类型、上游哈希和 seed 决定，与 09 无关，所以重跑时哈希完全不变；编排器只要在执行前检查"预期输出哈希已在 store 中"就能跳过——这正是讲义编排器职责第 2 条"check if the expected output already exists at the correct hash (skip if so)"。当前 `run()` 没有实现这一步，每次都全量重跑。需要注意：真实训练的输出不是逐比特确定的（见 Q4），所以生产中"跳过"的依据通常是"输入哈希 + 配置哈希命中缓存"，而不是"重新算一遍输出再比较"。

### Q11 — 参考答案

打印：

```text
{'op': '>=', 'value': 99.0} {'op': '>=', 'value': 99.0}
```

（已实际运行。）原因：`field(default_factory=lambda: dict(DEFAULT_GATES))` 只做了**浅拷贝**——外层字典是新的，但每个值（`{"op": ..., "value": ...}`）仍是 `DEFAULT_GATES` 里的同一个对象。修改 `a.gates["mmlu"]["value"]` 等于修改全局默认值，于是 `b` 和以后创建的所有 `Manifest` 都被污染。在 manifest 驱动的系统里，这会让"本次运行的 gate"悄悄变成"上次某处临时改过的 gate"。

修复：`field(default_factory=lambda: copy.deepcopy(DEFAULT_GATES))`，或写成 `{k: dict(v) for k, v in DEFAULT_GATES.items()}`；更进一步把 gate 定义成 `frozen=True` 的 dataclass，让它不可变。注意 `demo` 里 `manifest.eval_metrics["mmlu"] = 42.0` 改的是 `eval_metrics`，不受此问题影响。

### Q12 — 参考答案

```python
import operator

OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt,
       "<": operator.lt, "==": operator.eq}

def gate_v2(manifest, baseline: dict) -> tuple[bool, list[str]]:
    reasons, all_pass = [], True
    for metric, g in manifest.gates.items():
        if g["op"] not in OPS:
            raise ValueError(f"unknown op {g['op']!r} for {metric}")   # 配置错误直接失败
        value = manifest.eval_metrics.get(metric)
        if value is None:
            reasons.append(f"HOLD: missing metric {metric}"); all_pass = False; continue
        if "baseline_delta" in g:
            if metric not in baseline:
                reasons.append(f"HOLD: no baseline for {metric}"); all_pass = False; continue
            threshold = baseline[metric] + g["baseline_delta"]
        else:
            threshold = g["value"]
        ok = OPS[g["op"]](value, threshold)
        reasons.append(f"{'PASS' if ok else 'HOLD'}: {metric}={value} {g['op']} {threshold}")
        all_pass &= ok
    manifest.shippable = all_pass
    return all_pass, reasons
```

已在本地运行验证：baseline `mmlu=68.0`、gate `{"op": ">=", "baseline_delta": 0.5}`，`mmlu=68.4` 时阈值 68.5 → `HOLD: mmlu=68.4 >= 68.5`；不传 baseline 时输出 `HOLD: no baseline for mmlu`。（注意先把 `manifest.gates` 深拷贝再改，见 Q11。）要点：未知 op 必须**响亮失败**而不是静默当成 `<=`；缺 baseline 等于没有回归检测（outputs 技能文件："A run with no baselines is a run with no regression detection"），必须 HOLD；生产中还应把比较结果连同 baseline 来源（哪个 run、哪个哈希）一起写入 manifest。

### Q13 — 参考回答要点

- **manifest**：描述一次运行的单一文件，足以重放：pipeline 版本、seed、git commit、每个 stage 的 recipe/配置、输入哈希、输出哈希、墙钟、成本，以及 gate 阈值。原则是"pipeline 产生的任何东西都不能依赖 manifest 之外的状态"。
- **内容寻址**：产物以内容的 SHA-256 为地址，不可变。好处：同名不同内容不可能混淆；下游可以通过重新哈希验证完整性；相同内容自动去重；缓存命中判断变得简单。
- **事故例子**：两个实验都往 `s3://.../latest.pt` 写，评测脚本读到的是另一组实验的 checkpoint，评测结论错配；或者 checkpoint 上传中断留下半个文件，文件名仍然是 `latest.pt`，下一 stage 读到损坏权重。讲义："A filename like `latest.pt` is a foot-gun"。
- 加分点：manifest 检查器把本次 manifest 与上一次成功运行做 diff，预期之外的字段变化（除成本、墙钟外）都是红旗。

### Q14 — 参考回答要点

- **非确定性来源**（讲义列出三类）：分布式 all-reduce 的归约顺序不同 → 浮点加法不满足结合律；cuBLAS、flash-attn 等 kernel 使用原子操作或依赖调度的并行规约；混合精度（BF16/FP16）下舍入误差被放大。差异约在 1e-5 量级。
- **判定复现**：比较每个 stage 的输入哈希（数据、tokenizer、配置是否一致）、输出产物的头部指标（loss 曲线、eval 分数）是否在噪声范围内一致。讲义："if those match, the run is 'reproduced' even if the weights are not bit-identical"。
- **何时需要确定性**：调试数值 bug、做逐比特 diff 时。此时可以开启框架的确定性模式、固定归约顺序、单卡小规模复现，代价是速度。
- 常见误区：以为固定 `seed=42` 就能得到相同权重。

### Q15 — 参考回答要点

- **指标**：核心能力回归（MMLU-Pro、MATH、HumanEval+、GPQA 等或领域指标，相对上一版本 baseline）；KL budget（相对 reference 的累计 KL 上限）；安全（拒答率、有害输出率，有上限也要有下限以防过度拒答）；数据污染（训练分片与 eval 集 13-gram 重叠 < 0.1%，讲义练习 2 与 outputs 技能文件）；成本上限。
- **阈值**：运行**前**写进 manifest，全部是数值，不允许"looks good"。回归用 `>= baseline + δ` 或 `>= baseline`。
- **数据来源**：每个 gate 必须有"测量来源"——哪个 stage、哪个 eval 数据哈希；不能在训练数据上测；LLM-as-judge 时 judge 不能与被测模型同族（outputs 技能文件中的红旗）。
- **失败处理**：HOLD 不是失败而是决策点；由具名 reviewer 决定 override（写入 manifest 留痕）或执行回滚。
- 加分点：保留一个从不公开的私有 held-out 集（讲义 2026 配方里的"private held-out set the public never sees"），防止对公开基准过拟合。

### Q16 — 参考回答要点

- **先定位范围**：污染分片被哪些 stage 消费？如果它属于预训练数据（03），理论上 03 及所有后代都失效；但预训练是"昂贵"档，回滚计划不是"重跑"。
- **预训练**：回退到第 25 天之前最后一个"好"checkpoint（loss 正常、哈希可验证），从数据集中剔除受污染分片、生成新的数据集哈希，从该 checkpoint 继续训练剩余步数（必要时调整学习率调度）。
- **下游**：SFT、DPO/RLHF、CAI、eval、量化、serving 全部基于新的 base checkpoint 重跑（中等 + 便宜档）。
- **eval**：污染意味着之前测到的分数不可信，eval gate 必须用新的污染检查重新判定；如果评测集泄露严重，换用私有 held-out 集。
- **记录**：在 manifest 中写清失败 stage、回退的 checkpoint 哈希、新数据集哈希、预计新增成本，并重新过成本 gate。
- 加分点：说明为什么事先写好回滚计划重要——讲义"avoids improvising while the team is exhausted at 4am"；以及 checkpoint 要定期保存并做哈希校验，否则"最后一个好 checkpoint"可能并不存在。

### Q17 — 参考回答要点

- **观点**：讲义的意思是"编排器的职责很窄"（解析 DAG、跳过已有产物、执行、校验哈希、失败时写出部分 manifest），这部分逻辑需要完全可读、可审计，不应被通用平台的复杂度淹没；真正跑在集群上的 stage 本身仍用 `torchrun`/`ray`。实际团队中两者常共存：调度/资源管理交给平台，"契约与 gate"逻辑保持在自己的小代码里。实验跟踪讲义反而建议用托管服务（wandb、mlflow 等）。
- **并行 07/08**：用 `concurrent.futures` 同时提交两个 stage（讲义练习 1）。09 的输入哈希必须与完成顺序无关：按 `deps` 声明的顺序（或排序后）组装 `input_hashes`，而不是按"谁先完成谁先 append"。本节代码 `input_hashes = [name_to_hash[d] for d in deps]` 正是按声明顺序取，所以并行后只要仍按此方式构造，09 的 payload 和哈希就不变。
- 常见误区：用"完成顺序"拼输入列表，导致同样的输入产生不同哈希、缓存失效。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 01 Tokenizers](../../01-tokenizers/docs/zh.md)、[阶段 10 · 02 从头开始构建 Tokenizer](../../02-building-a-tokenizer/docs/zh.md)：pipeline 的 stage 01–02。
- [阶段 10 · 03 用于预训练的数据管道](../../03-data-pipelines/docs/zh.md)：stage 03 的数据分片与去重。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)、[阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：stage 04–05，也是成本最高、最难回滚的部分。
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)、[阶段 10 · 07 RLHF](../../07-rlhf/docs/zh.md)、[阶段 10 · 08 DPO](../../08-dpo/docs/zh.md)、[阶段 10 · 09 Constitutional AI 与自我改进](../../09-constitutional-ai-self-improvement/docs/zh.md)：对齐 stage 与 KL budget 的来源。
- [阶段 10 · 10 Evaluation](../../10-evaluation/docs/zh.md)、[阶段 10 · 11 Quantization](../../11-quantization/docs/zh.md)、[阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：eval gate 与 serving 前的最后几步。
- [阶段 07 · 13 Scaling Laws](../../../07-transformers-deep-dive/13-scaling-laws/docs/zh.md)：`6 × 参数 × token` 的 FLOPs 估算与数据预算。

### 本节被哪些后续内容用到
- [阶段 10 · 14 开放模型：架构详解](../../14-open-models-architecture-walkthroughs/docs/zh.md)：pipeline 里 stage 04 选什么架构。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：讲义练习 5 的可观测性落地。
- [阶段 17 · 20 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：ship gate 通过之后如何安全上线与回滚。
- [阶段 17 · 27 LLMs 的 FinOps](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：成本 gate 的延伸。
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../../18-ethics-safety-alignment/27-data-provenance-training-governance/docs/zh.md)：数据哈希、来源追踪与污染治理。
- [阶段 19 · 07 端到端 Fine-Tuning 流程](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)、[阶段 19 · 47 Checkpoint 保存与恢复](../../../19-capstone-projects/47-checkpoint-save-resume/docs/zh.md)、[阶段 19 · 80 分片 Checkpoint 与原子恢复](../../../19-capstone-projects/80-checkpoint-sharded-resume/docs/zh.md)：综合项目中把本节骨架落地。

### 延伸关键词
`manifest` · `content-addressed storage` · `SHA-256` · `DAG / topological sort` · `eval gate` · `regression gate` · `KL budget` · `contamination check (13-gram)` · `MFU` · `6ND FLOPs` · `reproducible vs deterministic` · `rollback plan` · `wandb / mlflow` · `OpenTelemetry`
