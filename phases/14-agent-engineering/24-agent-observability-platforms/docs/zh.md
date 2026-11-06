<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="agent-observability-langfuse-phoenix-opik"></a>

# Agent 可观测性（Observability）：Langfuse、Phoenix、Opik

> 三个开放源码 agent observability 2026年使用Langfuse(MIT)-6M+安装/月,跟踪+ prompt 管理 + 电子vals + 会话重播。 Arize Phoenix (ELAST 2.0) - 深 agent- 特定评估, RAG 相关性, OpenInference 自发仪器。 彗星 Opik (Apache 2. 0) - 自动 prompt optimization, guardrails, LLM-judge hallucination detection.

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 23 (OTel GENAI)
**时间:** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- 命名三个顶级开放源代码 agent observability 平台及其许可证。
- 朗弗斯(Langfuse)是其中最强的。prompt (mgmt)+会话,凤凰城(RAG +自动仪器,Opik(优化+ guardrails).
- 解释为什么89%的组织报告说 agent observability 2026年就位
- 执行标准字 trace- 与 LLM-judge evaluation.

<a id="the-problem"></a>

## 问题

OTel GenAI( 列森 23) 给了您一种模式。 您仍然需要一个能够覆盖, 运行的平台 。 evaluations, 仓库 prompt 三个竞争者强调生命周期的不同部分

<a id="the-concept"></a>

## 概念

<a id="langfuse-mit"></a>

### 兰福斯(麻省理工学院)

- 6M+ SDK 安装/月,19k+ GitHub stars.
- Features:追踪, prompt 管理版本+操场 evaluations (LLM- 以判断、用户反馈、定制),会话重播。
- 2025年6月:原商业单元(LLM-as-a-judge,注释队列, prompt 实验,游戏场) 开放源代码在麻省理工学院。
- 最强的:端到端 observability 紧紧的 prompt- 管理循环。

<a id="arize-phoenix-elastic-license-20"></a>

### 凤凰城(Elatic licat 2.0)

- Deeper agent-specific evaluation: trace 组合、异常点检测、检索 RAG.
- 本地 Openference 自动仪器
- 配有Arize AX 管理的对等设备用于生产。
- 否 prompt 版本——作为漂移/行为倒退工具,与更广泛的平台并列。
- 最强大的是: RAG 相关性,行为漂移,异常点检测

<a id="comet-opik-apache-20"></a>

### 彗星 Opik (Apache 2. 0)

- Automated prompt 通过A/B实验优化。
- Guardrails (《二审组汇编》,专题限制)。
- LLM-judge hallucination detection.
- 彗星自己的测量基准:Opik日志+23.44s 和 Langfuse 327.15s (~14x差距)的估价标准——将供应商基准作为方向性基准。
- 最强大的是:优化循环,自动实验, guardrail enforcement.

<a id="industry-data"></a>

### 工业数据

马克西姆(2026年)实地分析:89%的组织 agent observability 质量问题是生产的最大障碍(32%的答卷人引用了这些问题)。

<a id="picking-one"></a>

### 选一个

| 需要 | 挑选 |
|------|------|
| 全部在一号线 prompt management | Langfuse |
| Deep RAG evaluation + 浮动 | Phoenix |
| 自动优化+ guardrails | Opik |
| 开放许可, 无ELV2 | 朗富斯(MIT)或Opik(Apache 2. 0) |
| 数据犬/ 新版集成 | 任何——他们都出口OTel |

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **没有反弹策略** 追踪而不进行 evaluation 只不过是昂贵的伐木。
- **Self-rolled LLM- 判断没有 grounding.** CRITIC 使用(Lesson 05)模式——法官需要外部工具进行事实核实。
- **Prompt 未绑定版本 traces.** 当曲线倒退时, 你不能将两分 prompt 导致它。

```figure
wb-trace-ingest
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行标准字 trace 收藏家+ LLM- 法官评价员:

- 最古老的GenAI形的横幅。
- 按会话分组, 标记失败运行 (N)guardrail 旅行,低信心评估)。
- 脚本 LLM- 判断得分 agent 在一个卢布上的反应。
- 类似仪表板的汇总:故障率、最高故障原因、电子评分分布。

运行：

```
python3 code/main.py
```

产出:每场的 Eval 分数和失败分类与Langfuse/Phoenix/Opik 显示的相符。

<a id="use-it"></a>

## 实际应用

- **Langfuse** 由自动托管或云;通过OTel或他们的 SDK.
- **亚里兹·凤凰城** 自托管; 自动文书打开引用 。
- **彗星奥皮克** 自托管或云; 自动优化循环。
- **Datadog LLM Observability** 混合行动+ML团队 已经运行数据犬。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-obs-platform-wiring.md` 选择平台和电线 traces + 电子估价+ prompt 版本为现有 agent.

<a id="exercises"></a>

## 练习

1. 导出 OTel 一周 traces 兰富斯云层( 自由级) 。 哪个会话失败? 为什么 ?
2. 写一个 LLM- 法官为您域的标注( 事实正确性、 音调、 范围是否坚持) 。 traces.
3. 比较兰福斯 prompt 和凤凰队对着 trace 组合,这说明什么是更快的断裂?
4. 读 Opik 的 guardrail 博士, 编译 PII 的 线条 guardrail 致你的一个 agent runs.
5. 以您的体积为基准。 忽略销售商公布的数字; 测量您自己的数字 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 追踪 | "收集板" | 最热门的 OTel / SDK 横线; 按会话索引 |
| Prompt management | "Prompt CMS" | Versioned prompts 绑定到 traces |
| LLM-as-judge | "自动电子评估" | Separate LLM scores agent 输出比对一个卢布 |
| 会话重播 | "Trace playback" | 跳过过去运行以调试 |
| RAG relevancy | "检索质量" | 检索的上下文是否匹配查询 |
| Trace clustering | 行为组合 | 类似漂移探测的分组运行 |
| Guardrail enforcement | “ 日志时的政策” | PII/毒性/对记录内容的检查 |

<a id="further-reading"></a>

## 进一步阅读

- [兰弗兹医生](https://langfuse.com/) 追踪,评估, prompt mgmt
- [凤凰医生](https://docs.arize.com/phoenix) 自动仪器、漂流
- [彗星奥皮克](https://www.comet.com/site/products/opik/) 优化+ guardrails
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/) 三个人都消耗的阴谋
