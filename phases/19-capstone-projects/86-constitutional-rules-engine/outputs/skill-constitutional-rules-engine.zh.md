---
name: skill-constitutional-rules-engine
description: Declarative YAML rules engine for output constraints with severity, explanation, fixer operations, and structured diff
version: 1.0.0
phase: 19
lesson: 86
tags: [safety, rules, constitutional]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="constitutional-rules-engine"></a>

# 宪法规则引擎

宪法是 YAML 文件。 每一个规则都包含 `name`, `severity` (低 | 中等 | 高), `applies_when` (predicate), `must` (predicate), `explanation`,并且可选 `fix`.

<a id="predicates"></a>

## Predicates

Atomic:

- `contains_regex` / `not_contains_regex`
- `starts_with_regex` / `ends_with_regex`
- `max_words` / `min_words`

Compositional:

- `all_of: [...predicates]`
- `any_of: [...predicates]`
- `not_: predicate`

<a id="fix-operations"></a>

## 修复操作

- `append_if_missing: <suffix>`
- `prepend_if_missing: <prefix>`
- `replace_regex: { pattern: <regex>, replacement: <text> }`

<a id="engine-output"></a>

## 引擎输出

`Engine.evaluate(text) -> EngineReport` 返回 1 `RuleResult` 规则中 `status` 在 `pass`, `violation`, `not_applicable`. `report.violations()` 过滤到违反事件 `report.max_severity()` 返回当前最差的刻度。

<a id="artifact"></a>

## Artifact

`outputs/rules_report.json` 随身携带草稿、订正和结构化的每件案件。
