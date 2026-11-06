# 测验 · 端到端 Fine-Tuning 流程——从数据、SFT、DPO 到模型服务（End-to-End Fine-Tuning Pipeline (Data to SFT to DPO to Serve)）

> **阶段 19 · 综合项目 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 流水线五大阶段 | 讲义：Data（去重、质量过滤、PII 清洗、split hygiene）→ SFT → DPO/GRPO → Quantize → Serve，外加 eval 与 model card；代码把它拆成 8 个 stage |
| 2 | 数据卫生（data hygiene） | MinHash/Datatrove 去重、Nemotron-CC 风格质量分类器、Presidio 清洗 PII、显式 seed 切分 train/val |
| 3 | 污染检查（contamination check） | 用 MinHash 把训练/验证数据与 MMLU-Pro、MT-Bench-v2、RewardBench-2 测试集比对，**有任何重叠就拒绝**；否则 eval 分数是"作弊"出来的 |
| 4 | SFT → DPO/GRPO 的组合 | SFT 用标注好的完成样本建立领域行为；DPO 用偏好对（chosen/rejected）对齐，GRPO 用可验证奖励（数学/代码）做 RL；讲义配置是 DPO 1 epoch、β 需要扫参 |
| 5 | 三种量化格式 | GPTQ-INT4-Marlin（GPU 服务）、AWQ-INT4、GGUF-Q4_K_M（llama.cpp/CPU/边缘）；讲义：4.6 / 4.8 / 5.1 GB |
| 6 | 投机解码（speculative decoding） | EAGLE-3 draft heads 一次预测 N 个 token，目标模型一次前向验证；acceptance rate（接受率）衡量 draft 与目标模型的吻合度；讲义称吞吐提升 2–3 倍且无质量损失 |
| 7 | 服务指标 | bs=1/8/32 的 tokens/s、p99 延迟、EAGLE-3 接受率、$/1M tokens；K8s 用 queue-wait（排队等待时间）驱动 HPA |
| 8 | 消融实验是交付物 | base vs SFT-only vs SFT+DPO vs SFT+GRPO，在 lm-eval-harness、RewardBench-2、MT-Bench-v2、MMLU-Pro 上出表 |
| 9 | 可复现性 | 一条命令（`./pipeline.sh config/...yaml`）端到端重跑；固定 seed、附 YAML 与 commit SHA；代码用"按内容哈希的 artifact manifest"建模血缘 |
| 10 | Model card（MOF 2026） | 讲义：按 2026 Model Openness Framework 模板写数据、训练、评估、安全（Llama Guard 4 通过率）、许可、可复现性 |

### 核心技能（能动手做到）

- [ ] 画出 data → contamination → SFT → DPO → quantize → serve → eval → model card 的 DAG，并说出每一阶段的输入 artifact 和输出 artifact
- [ ] 读懂 `Artifact.content_hash()`：解释为什么要 `json.dumps(..., sort_keys=True)`，以及为什么下游 payload 要记录上游哈希
- [ ] 指出本节代码中"血缘断裂"的地方（`stage_serve` 没有记录上游哈希、`dpo_beta` 配置被忽略），并动手修复
- [ ] 把模拟的污染检查换成真正的 MinHash Jaccard 估计，并让流水线在 `status == "dirty"` 时中止（讲义练习 4 的 CI gate）
- [ ] 用 tokens/s 和 $/1M tokens 反推每小时 GPU 成本；用接受率估算投机解码每步期望产出的 token 数
- [ ] 设计一张消融表（base / SFT / SFT+DPO / SFT+GRPO × 多个基准），并说明为什么要在量化后的模型上再测一次

---

## 二、基础自测（选择题）

**Q1.** 讲义要求在数据阶段之后做 contamination check。它防范的是：

- A. 公开基准（如 MMLU-Pro、MT-Bench-v2）的测试题泄漏进训练数据，导致评估分数虚高
- B. SFT 阶段和 DPO 阶段使用的 tokenizer 不一致
- C. 训练集群与服务集群的 GPU 驱动版本不一致
- D. 不同版本 llama.cpp 之间 GGUF 格式不兼容

**Q2.** 为什么流水线先做 SFT、再做 DPO（或 GRPO），而不是直接做 DPO？

- A. DPO 不能在量化后的权重上运行
- B. Axolotl 不支持 DPO，只能用 TRL
- C. SFT 先用标注的完成样本建立领域行为，DPO/GRPO 再在偏好对或可验证奖励上对齐；DPO 还需要一个参考策略，通常就是 SFT 模型
- D. DPO 必须使用与 SFT 不同的模型架构

**Q3.** 运行 `python main.py`，`raw_examples=300_000`，`stage_data` 最终保留（`after_pii_scrub`）的样本数是多少？

- A. 280,000（与讲义 Use It 输出一致）
- B. 288,000
- C. 256,620
- D. 255,336

**Q4.** 关于投机解码的 acceptance rate（接受率），下列说法正确的是：

- A. 它是目标模型在 MMLU-Pro 上的准确率
- B. 它是 draft 提出的 token 中被目标模型接受的比例，越高说明 draft 与目标模型越吻合、加速越明显
- C. 它越低越好，表示目标模型更严格、输出质量更高
- D. 它只取决于 batch size，与数据领域无关

**Q5.** 讲义要求同时产出 GPTQ-INT4-Marlin、AWQ-INT4、GGUF-Q4_K_M 三种量化。最主要的理由是：

- A. 三种格式取平均可以抵消量化误差
- B. 只有同时存在三种格式，vLLM 才能启动
- C. INT4 比 FP16 精度更高
- D. 部署灵活性：GPTQ/AWQ 面向 GPU 服务（如 vLLM），GGUF 面向 llama.cpp 的 CPU/边缘场景

**Q6.** 在本节代码中，用不同的 `base_model` 或不同的 `seed` 重跑流水线，哪个 artifact 的哈希**始终不变**？

- A. `endpoint`
- B. `sft_checkpoint`
- C. `quants`
- D. `model_card`

**Q7.** 讲义中 K8s 的 HPA（Horizontal Pod Autoscaler）基于什么指标扩缩服务副本？

- A. GPU 温度
- B. CPU 利用率
- C. queue-wait（请求排队等待时间）
- D. 网络出口字节数

**Q8.** `Artifact.content_hash()` 的实现如下。关于它，说法正确的是：

```python
    def content_hash(self) -> str:
        blob = json.dumps(self.payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]
```

- A. 因为 `produced_at` 是当前时间，所以每次运行的哈希都不同
- B. 只对 `payload` 求哈希；`sort_keys=True` 保证键顺序不同但内容相同的 dict 得到相同哈希，所以同配置重跑哈希可复现
- C. `[:12]` 截断后得到 12 字节（96 bit）的摘要
- D. `name` 和 `produced_by` 也参与了哈希计算

---

## 三、动手 / 代码题

**Q9.** 阅读 `stage_contamination` 与 `run_pipeline`：

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


def run_pipeline(cfg: dict) -> Manifest:
    m = Manifest()
    for name, stage_fn in PIPELINE:
        print(f"[{name:14s}] running...")
        art = stage_fn(m, cfg)
        m.add(art)
        print(f"[{name:14s}] -> artifact '{art.name}' hash={art.content_hash()}")
    return m
```

1. 这个检查能否捕获讲义练习 4 中"注入 1% MMLU-Pro 答案"的污染？为什么？
2. 即使 `status` 变成 `"dirty"`，流水线会停下来吗？SFT 阶段与污染检查结果之间有没有血缘关系？
3. 写出一个最小修改，让流水线在污染时中止，并让 `sft_checkpoint` 记录污染报告的哈希。

**Q10.** 用不同配置运行流水线后对比各 artifact 的哈希（已实际运行）：

| artifact | 基线（llama, seed=7） | seed=8 | base=qwen3-14b | 加 `dpo_beta=0.2` |
|---|---|---|---|---|
| dataset | ca747e11e566 | e57570370585 | ca747e11e566 | ca747e11e566 |
| sft_checkpoint | fdd2cd361ca9 | 8b20c51c6d1b | ee4c1c79a353 | fdd2cd361ca9 |
| dpo_checkpoint | ef90ec046fe3 | 4512b01af414 | d9b92ab80d1b | ef90ec046fe3 |
| quants | 528d8fe6207f | 242211feddfe | 170650bc8703 | 528d8fe6207f |
| endpoint | 32584f1dc609 | 32584f1dc609 | 32584f1dc609 | 32584f1dc609 |

1. 为什么改了 `dpo_beta`，所有哈希都不变？
2. 为什么 `endpoint` 在所有配置下都不变？这对"可复现、可追溯"意味着什么？
3. 给出修复方案。

**Q11.** 代码中 `stage_serve` 给出 `tokens_per_sec_bs32 = 6400`、`dollars_per_mtokens = 0.28`、`eagle_acceptance = 0.74`。

1. 如果 $/1M tokens 是由"每小时 GPU 成本 / 每小时产出 token 数"算出来的，那么隐含的每小时成本是多少？
2. 设 draft 每次提出 k 个 token，且每个 token 独立以概率 α 被接受（Leviathan 等人的简化模型），一次验证的期望产出 token 数为 `(1 − α^(k+1)) / (1 − α)`。取 α = 0.74，分别计算 k = 3 和 k = 5 的值。
3. 为什么讲义练习 3 要在"领域数据"和"通用 ShareGPT"上分别测接受率？

**Q12.** 讲义 Use It 输出的数据行是 `[data] 300k deduped, 12k filtered, 280k accepted (seed=7)`，而代码的 `stage_data` 用三个固定比例（0.94、0.91、0.995）。请（1）写出代码实际每一步剩多少、每一步去掉多少；（2）指出讲义这行输出自身的算术问题；（3）说明把这些比例写死在代码里，对"数据卫生"这一评分项意味着什么。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述一个从原始数据到上线服务的 LLM fine-tuning 流水线，每个阶段的关键工具、关键配置和产出物是什么？

**Q14.**（原理深挖）SFT、DPO、GRPO 各自优化的目标是什么？DPO 的 β 起什么作用、为什么要扫参？什么场景下选 GRPO 而不是 DPO？

**Q15.**（工程实践）如何让一个 fine-tuning 流水线"一条命令可复现"？除了固定 seed，还要记录哪些东西？内容哈希式的 artifact manifest 解决了什么问题？

**Q16.**（场景设计）你的模型在 MMLU-Pro 上比基座高了 9 分，远超预期。你会怎么排查？如何把这种排查固化为 CI gate？

**Q17.**（追问型）上线前要量化到 INT4、再加 EAGLE-3 投机解码。这两步分别可能怎样影响质量和延迟？你会怎么验证"没有质量损失"？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义 Key Terms："Contamination check — MinHash-based detection of test-set leakage into training"。如果训练数据里含有基准测试题（甚至答案），模型在该基准上的分数会虚高，消融结论失去意义。B、C、D 都是真实存在的工程问题，但都不是 contamination check 的目的。

### Q2 — 答案：C

SFT 让模型学会领域内"应该怎么回答"（模仿标注完成样本）；DPO 在偏好对上让 chosen 的相对概率高于 rejected，GRPO 用可验证奖励（数学答案、代码测试）做组内相对的强化学习。DPO 的损失以参考策略 `π_ref` 为锚，实践中 `π_ref` 通常就是 SFT 模型——没有 SFT，DPO 的起点会离目标分布很远。A 错：量化发生在训练之后，与 DPO 能否运行无关；B 错：讲义 Key Terms 明确说 Axolotl 是"统一的 YAML 驱动 trainer，支持 SFT、DPO 和蒸馏"；D 错：DPO 在同一架构上训练。

### Q3 — 答案：D

实际运行（`after_pii_scrub` 字段）：`int(300000 × 0.94 × 0.91 × 0.995) = 255,336`。C（256,620）是质量过滤后、PII 清洗前的数；B 是讲义"300k − 12k"的算术结果；A 是讲义 Use It 输出里的"280k accepted"，与代码不一致（见 Q12）。

### Q4 — 答案：B

讲义 Key Terms："Acceptance rate — Fraction of drafted tokens the target model accepts"。接受率越高，每次目标模型前向能"确认"的 token 越多，加速越明显。A 混淆了质量指标；C 说反了——接受与否由目标模型的分布决定，被拒绝的 token 会由目标模型重新采样，输出分布不变，接受率低只意味着白做 draft；D 错，接受率强烈依赖数据分布（这正是讲义练习 3 的用意）。

### Q5 — 答案：D

讲义："GPTQ + AWQ + GGUF for deployment flexibility"。GPTQ（配 Marlin kernel）与 AWQ 是 GPU 推理常用的 INT4 权重格式，vLLM 都支持；GGUF 是 llama.cpp 的格式，适合 CPU、Mac、边缘设备。A 错：不会把三个模型做平均；B 错：vLLM 只需加载其中一种（代码 `stage_serve` 选的是 `GPTQ-INT4-Marlin`）；C 错：INT4 精度低于 FP16，量化是用精度换显存/带宽。

### Q6 — 答案：A

`stage_serve` 虽然取了 `quants = m.get("quants")`，但 payload 里没有放任何上游哈希，全是常量，所以 `endpoint` 的哈希在任何配置下都是 `32584f1dc609`（见 Q10 实测表）。B、C、D 的 payload 都直接或间接包含上游哈希（`dataset_hash`、`from`、`training_config_hash`），会随 seed 或 base_model 变化。

### Q7 — 答案：C

讲义 Concept 与 Stack："K8s deployment, HPA on queue-wait"。LLM 服务的瓶颈通常在 GPU，CPU 利用率（B）不能反映负载；排队等待时间直接反映"请求是否在等 GPU"，是更贴近用户延迟的扩缩信号。A、D 与负载无直接关系。

### Q8 — 答案：B

- 哈希只覆盖 `payload`：`produced_at`、`name`、`kind`、`produced_by` 都不参与，因此 A、D 错。实测同一配置连续运行，哈希完全一致（`dataset` 恒为 `ca747e11e566`）。
- `sort_keys=True`：`{"b":1,"a":2}` 与 `{"a":2,"b":1}` 序列化成同一字符串 `{"a": 2, "b": 1}`，哈希相同（已验证）。
- `default=str`：遇到不能 JSON 序列化的对象时转成字符串，避免报错。
- C 错：`hexdigest()` 每个字符是 4 bit，12 个十六进制字符是 48 bit（6 字节）。按生日界估算，100 万个 artifact 时碰撞概率约 0.18%，对演示足够，生产中应保留完整 64 位十六进制。

### Q9 — 参考答案

1. **不能**。循环里 `overlap_examples` 被硬编码为 0，根本没有读取数据或基准内容，`status` 恒为 `"clean"`。注释也写明"simulated MinHash check"。无论注入多少污染，结果都一样——这是一个"永远绿灯"的检查。
2. **不会停**。`run_pipeline` 只是按顺序执行，不读取任何 stage 的 `status`。而且 `stage_sft` 只依赖 `dataset`，payload 里没有 `contamination_check` 的哈希，污染报告和模型之间没有血缘关系，事后也无法证明"这个 checkpoint 是在通过污染检查的数据上训练的"。
3. 最小修改（示意）：

```python
class PipelineHalt(RuntimeError):
    pass

def run_pipeline(cfg: dict) -> Manifest:
    m = Manifest()
    for name, stage_fn in PIPELINE:
        art = stage_fn(m, cfg)
        m.add(art)
        if art.kind == "report" and art.payload.get("status") == "dirty":
            raise PipelineHalt(f"stage {name} failed: {art.payload}")
    return m

def stage_sft(m: Manifest, cfg: dict) -> Artifact:
    ds = m.get("dataset")
    cc = m.get("contamination_check")
    return Artifact("sft_checkpoint", "checkpoint", {
        "base": cfg["base_model"],
        "dataset_hash": ds.content_hash(),
        "contamination_hash": cc.content_hash(),   # 把门禁结果写进血缘
        # ...
    }, produced_by="axolotl v0.8 + ZeRO-3")
```

真正的 `overlap_examples` 应该由 MinHash 计算：把文本切成 n-gram shingle，用多组哈希取最小值得到签名，签名相同位置的比例估计 Jaccard 相似度，超过阈值（例如 0.8）就计为重叠。小实验：两句只差一个词的 14 词句子，5-gram 的真实 Jaccard 为 0.818，128 维 MinHash 估计为 0.820；与无关句子的估计为 0。生产中用 Datatrove 的 MinHashLSH 做分桶，避免两两比较。

### Q10 — 参考答案

1. `main()` 的 `cfg` 里有 `"dpo_beta": 0.08`，但 `stage_dpo` 写死了 `"beta": 0.08`，从不读 `cfg["dpo_beta"]`。配置改了、artifact 不变——这是"配置漂移"：manifest 声称的 β 与配置文件不一致时，复现会得出错误结论。讲义要求"Sweep beta"，现在的代码根本无法扫参。修复：`"beta": cfg.get("dpo_beta", 0.08)`。（同理，SFT 的 `epochs: 3`、`val_loss: 1.03` 也都是常量。）
2. `stage_serve` 取了 `quants` 却没用，payload 不含上游哈希。后果：无论服务的是哪个 base、哪个 seed 训出的模型，endpoint 的"身份"都一样；线上出问题时无法从 endpoint 追溯到具体的量化文件、checkpoint 和数据集。哈希链在倒数第三环断了，"按内容哈希串联 DAG"的设计目标（docstring："each stage consumes the previous stage's artifact by content hash"）没有兑现。
3. 修复：在 `stage_serve` 的 payload 里加入 `"from": quants.content_hash()`；`stage_eval` 也应同时记录被评估的是 DPO checkpoint 还是被服务的量化模型；`stage_model_card` 记录 `eval_report`、`endpoint` 的哈希，以及真实的配置哈希（例如 `hashlib.sha256(json.dumps(cfg, sort_keys=True))`），而不是把 `sft_checkpoint` 的哈希命名为 `training_config_hash`。

### Q11 — 参考答案

1. 每小时产出 `6400 × 3600 = 23,040,000` 个 token；`23.04 × 0.28 ≈ $6.45/小时`。也就是说这组数字隐含"一个约 6.45 美元/小时的 GPU 实例，在 bs=32 下满负荷运行"。注意它只在**满载**时成立：bs=1 时吞吐低得多，$/1M tokens 会成倍上升，所以讲义要求分别报告 bs=1/8/32。
2. 计算（已用 Python 验证）：k = 3 时 `(1 − 0.74⁴)/0.26 ≈ 2.69`；k = 5 时 `(1 − 0.74⁶)/0.26 ≈ 3.21`。也就是一次目标模型前向平均产出约 2.7–3.2 个 token，再扣掉 draft 的开销，与讲义"2–3x"的量级相符。k 越大收益递减，而且 draft 越长，被拒后浪费的计算越多。
3. 接受率取决于 draft 能否猜中目标模型在**这类数据上**的输出。在领域数据（例如合同、医疗）上，如果 EAGLE-3 draft heads 是用通用数据训练的，接受率可能明显下降，加速比和延迟预算都要重新估算；反过来也说明需要用领域数据训练/校准 draft heads（讲义提到用 Red Hat Speculators 或 SGLang SpecForge 训练）。

### Q12 — 参考答案

1. 代码实际（已运行）：

| 步骤 | 剩余 | 本步去掉 |
|---|---|---|
| 原始 | 300,000 | — |
| 去重（×0.94） | 282,000 | 18,000 |
| 质量过滤（×0.91） | 256,620 | 25,380 |
| PII 清洗（×0.995） | 255,336 | 1,284 |

2. 讲义那一行"300k deduped, 12k filtered, 280k accepted"：300k − 12k = 288k，而不是 280k，自身算术就对不上；而且"300k deduped"的说法意味着去重后还剩 300k，和代码"原始 300k、去重后 282k"也不一致。讲义的 Use It 输出只是示意，与 `main.py` 的实际输出没有对应。
3. 比例写死意味着"去重率、过滤率"不是测出来的，而是假设出来的。讲义评分表里 Data hygiene 占 20 分，衡量的正是"dedup rate、PII scrub coverage、contamination check green"——这些都必须从真实数据上统计得到。本节代码只是在建模 artifact 的**形状**，不能拿来当证据。

### Q13 — 参考回答要点

- **数据**：Datatrove MinHash 去重 → Nemotron-CC 风格质量分类器 → Presidio 清洗 PII → 带 seed 的 train/val 切分；产出数据集 + 统计报告。
- **污染检查**：与 MMLU-Pro、MT-Bench-v2、RewardBench-2 测试集做 MinHash 比对，有重叠就拒绝；产出污染报告，作为门禁。
- **SFT**：Axolotl YAML，ZeRO-3、Flash Attention 3、sequence packing、cosine 调度，2–3 epoch，8×H100；W&B 记录；产出 SFT checkpoint。
- **偏好对齐**：TRL DPO 1 epoch、扫 β；或 GRPO 用可验证奖励；产出对齐 checkpoint。
- **量化**：GPTQ-INT4-Marlin、AWQ-INT4、GGUF-Q4_K_M；记录体积和名义吞吐，**并在评估矩阵上测量量化损失**（讲义 skill 文件的拒绝规则）。
- **服务**：vLLM + EAGLE-3（或 SGLang + SpecForge），K8s 部署，HPA 基于 queue-wait；测 bs=1/8/32 tokens/s、p99、接受率、$/1M tokens。
- **评估与安全**：lm-eval-harness、RewardBench-2、MT-Bench-v2、MMLU-Pro 对 base/SFT/SFT+DPO/SFT+GRPO 出消融表；Llama Guard 4 通过率。
- **Model card**：MOF 2026 模板，附 YAML 和 commit SHA。
- 加分点：说清楚每一阶段"消费哪个 artifact、产出哪个 artifact"，并提到门禁（污染、安全、量化损失）失败要中止。

### Q14 — 参考回答要点

- **SFT**：在 (prompt, response) 上最大化 response 的对数似然（只对 response 部分计算 loss），让模型模仿高质量答案。
- **DPO**：在偏好对 (x, y_w, y_l) 上最小化 `−log σ(β[(log π_θ(y_w|x) − log π_ref(y_w|x)) − (log π_θ(y_l|x) − log π_ref(y_l|x))])`，不需要单独训练 reward model，也不需要在线采样。
- **β 的作用**：控制策略偏离参考模型的程度。β 小 → 约束弱，可以离 SFT 模型更远，但容易过拟合偏好数据、出现奇怪的长度或风格偏好；β 大 → 更保守。数值示例：β = 0.08 时，如果 chosen 相对参考的 log-ratio 为 +2.0、rejected 为 −1.5，sigmoid 里的值是 0.08 × 3.5 = 0.28，loss ≈ 0.563；未训练时（差值为 0）loss = ln2 ≈ 0.693。β 的最优值依赖数据和任务，所以讲义要求 sweep。
- **GRPO**：讲义 Key Terms："DeepSeek R1 的 RL 配方，配合可验证奖励"。对同一个 prompt 采样一组回答，用组内奖励的相对值（减均值、除以标准差）作为 advantage，省掉 PPO 的 value 网络。
- **选择**：有人工/模型标注的偏好对、目标是风格与有用性 → DPO；任务有可自动判定的正确性（数学答案、单元测试）→ GRPO。
- 常见误区：认为 DPO 可以替代 SFT；忽略 DPO 也需要参考模型（显存要放两份权重，或预先计算参考 logprob）。

### Q15 — 参考回答要点

- **要记录的东西**：所有 seed（数据切分、训练、采样）；全部 YAML 配置；代码 commit SHA（训练框架、lm-eval-harness 也要记版本——讲义 skill 文件："拒绝发布没有附 lm-eval-harness commit SHA 的 benchmark 分数"）；数据集版本与过滤参数；依赖版本（容器镜像 digest）；硬件信息（GPU 型号、数量）。
- **内容哈希 manifest 的价值**：每个 artifact 由内容决定 ID，下游记录上游哈希，形成一条可验证的血缘链；同输入同输出 → 可以做缓存/跳过已完成阶段；任何上游变化都会"传染"到下游哈希，不会悄悄用旧产物。
- **本节代码的不足**：`dpo_beta` 被忽略、`endpoint` 不含上游哈希、`training_config_hash` 实际上是 checkpoint 的哈希；真实流水线还应对**模型权重文件本身**求哈希，而不是只对元数据求。
- 加分点：GPU 上的非确定性（原子加法、cuDNN 算法选择）会让"完全相同 seed"仍出现微小差异，可复现性的标准应是"指标在容差内一致"，而不是逐位相同；可用 DVC、MLflow、W&B Artifacts 等工具管理。

### Q16 — 参考回答要点

- **先怀疑污染**：讲义练习 4 正是演示"泄漏 1% MMLU-Pro 答案 → 准确率不切实际地跳升"。排查：
  - 对训练数据（SFT、DPO 两部分都要查）与 MMLU-Pro 测试集做 n-gram/MinHash 重叠检测；
  - 对比"原题"与"改写后的同义题"上的准确率，差距大说明是记忆而非能力；
  - 看分数提升是否集中在少数学科、是否伴随其它基准没有同步提升；
  - 检查模型能否不看题干补全选项（成员推断类测试）。
- **其它可能**：eval 配置变了（few-shot 数、prompt 模板、答案抽取正则）；对比的 base 分数是在不同设置下测的。
- **固化为 CI gate**：数据合并进训练集之前必须跑 MinHash 检查，重叠数 > 0 直接失败；检查结果哈希写入 checkpoint 的 manifest；eval 报告必须附 harness commit SHA 和配置哈希；再放一组"金丝雀"测试题，监控它们是否出现在数据中。

### Q17 — 参考回答要点

- **INT4 量化**：显存约降为 FP16 的 1/4，decode 阶段（带宽瓶颈）通常更快；质量可能在推理、数学、长上下文、多语言任务上下降。GPTQ/AWQ 依赖校准数据，校准数据与领域不匹配时损失更大。
- **EAGLE-3**：按标准的拒绝采样验证，输出分布与目标模型一致（讲义："without quality loss"），收益是延迟/吞吐；但接受率低时 draft 开销反而拖慢速度；batch 很大时 GPU 已经算力饱和，投机解码收益下降。
- **验证方法**：在**被服务的那个量化模型**上重跑同一套评估矩阵，与 FP16/BF16 对比（讲义 skill："拒绝在没有测量量化质量损失的情况下发布量化模型"——注意本节代码 `stage_eval` 评估的是 DPO checkpoint 而非量化后的模型）；在真实领域流量上测接受率；测 bs=1/8/32 下的 p50/p99。
- 加分点：投机解码的"无损"依赖正确的验证实现；温度采样与贪心解码下接受率不同，需要分开报告。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 03 用于预训练的数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：去重、过滤、分片等数据工程基础。
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：SFT 阶段的目标与数据格式。
- [阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：DPO 损失与 β 的含义。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：lm-eval-harness 与基准污染问题。
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：INT4 量化原理。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：讲义练习 5 的 LoRA 替代方案。

### 本节被哪些后续内容用到
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../../17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/zh.md)：服务阶段的投机解码细节。
- [阶段 17 · 09 生产环境中的 Quantization](../../../17-infrastructure-and-production/09-production-quantization/docs/zh.md)：AWQ、GPTQ、GGUF K-quants 的取舍。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling](../../../17-infrastructure-and-production/03-gpu-autoscaling-kubernetes/docs/zh.md)：HPA 与 GPU 调度。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../../18-ethics-safety-alignment/26-model-system-dataset-cards/docs/zh.md)：model card 应包含什么。
- [阶段 19 · 14 推测解码 Inference 服务端](../../14-speculative-decoding-server/docs/zh.md)：自己实现投机解码服务。
- [阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../39-instruction-tuning-sft/docs/zh.md)、[阶段 19 · 40 从零实现直接偏好优化](../../40-dpo-from-scratch/docs/zh.md)：从零实现 SFT 与 DPO。

### 延伸关键词
`Axolotl` · `TRL` · `Unsloth` · `ZeRO-3` · `sequence packing` · `DPO β` · `GRPO` · `MinHash LSH` · `benchmark contamination` · `GPTQ / AWQ / GGUF` · `EAGLE-3` · `acceptance rate` · `$/1M tokens` · `Model Openness Framework` · `artifact lineage`
