---
name: skill-end-to-end-safety-gate
description: Three-checkpoint safety gate composing the input detector, streaming token filter, output classifier, and rules engine with a deterministic aggregation table and per-request trace
version: 1.0.0
phase: 19
lesson: 87
tags: [safety, harness, composition]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="end-to-end-safety-gate"></a>

# 端对端安全门

<a id="lifecycle"></a>

## Lifecycle

1. 预兆 - 在 prompt
   - 如果信任 #%% block_门槛:拒绝返回,发放 trace,停下来
2. 元中 - 模型的流, 缓冲两个块, 扫描已知的有害延续
   - 如果匹配: 终止循环, 标记 trace,作为中等严重程度处理
3. 后原 - 如果没有提前终止, 运行课程 85 分类路由器和课程 86 规则引擎
4. 总计 - 使用前、后、后、后、后、后、规则中的最大强度
5. 应用 - 用于块、编辑、警告或允许的地图

<a id="aggregation-table"></a>

## 汇总表

| 信号状态 | 动作 |
|---|---|
| 任何严重性 | block |
| 中等严重性 | redact |
| 任何低度严重性 | warn |
| nothing | allow |

<a id="trace-structure"></a>

## Trace structure

```text
RequestTrace
  request_id: str
  prompt: str
  pre_gen: { category, confidence, fired[] }
  during_gen: { terminated_early, matched_pattern, partial_chunks }
  post_gen: { classifier_action, classifier_severity, rules_max_severity, rules_violations[] } | null
  final_action: block | redact | warn | allow
  final_output: str
  latency_ms: float
```

<a id="artifact"></a>

## Artifact

`outputs/gate_trace.json` 包含摘要和一份 trace 包括50个分类装置和10个良性装置 prompts.
