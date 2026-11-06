---
name: lm-eval-harness
description: Minimal language model evaluation harness with JSONL task spec, five metrics, swappable adapter, and leaderboard JSON output.
version: 1.0.0
phase: 19
lesson: 49
tags: [evaluation, metrics, leaderboard, harness]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="when-to-use"></a>

## 何时使用

比较两个模型,两个 checkpoints,或者两个 prompt 模板与固定任务相对应。任何船舶和您需要长期监控的事物。

<a id="task-spec"></a>

## 任务规格

One JSONL 示例行数 :

```json
{"id": "ex-001", "prompt": "...", "targets": ["..."], "metric": "exact_match", "extras": {}}
```

文件的所有示例都共享一个度量。 文件名称是任务名称 。

<a id="metrics"></a>

## Metrics

| 公制 | Signature | 用于 |
|--------|-----------|---------|
| exact_match | 将低空格和白空格等同 | 解析,事实解答 |
| substring_contains | 目标必须出现在正常预测中 | 带锚字的自由形式生成 |
| multiple_choice | 第一次匹配字母 | A/B/C/D 风格问题 |
| rouge_l | LCS F1 相对于象征性文本 | 摘要, 引文 |
| code_exec | 运行预测 `f` 开_双对, 数匹配 | 代码生成 |

所有参数返回浮点 [0.0, 1.0]任务分数是坏处

<a id="adapter"></a>

## 适配器

```python
class Adapter(Protocol):
    name: str
    def generate(self, prompts: list[str]) -> list[str]: ...
```

适配器是唯一的模型专用代码。

<a id="leaderboard-json"></a>

## Leaderboard JSON

平面图字符串、 时间戳、 每项任务评分和延迟度, 总体平均值。 在比较运行时包含每例记录, 这样可以看到预测水平的回归 。

<a id="failure-modes"></a>

## 失效模式

- 计量返回外面 [0, 1]:总分数不可解释。
- 任务文件中的混合度量: 声明火灾; 每个文件保留一个度量。
- code_Exec 不受限制的命名空间:任意代号执行。
- 没有系统图案字符串: 格式进化会打破下游仪表板 。
