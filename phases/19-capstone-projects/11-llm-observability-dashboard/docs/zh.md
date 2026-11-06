<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-11--llm-observability--eval-dashboard"></a>

# 综合项目 11：LLM Observability 与评估仪表盘

> 朗福斯进入开放状态。亚利兹·凤凰城发表了2026年GenAI Semconv地图。希利科内和脑信公司在每用户成本归属上都翻了一番。 Traceloop的 OpenLLLMetry成为了“反面” SDK 仪器。 生产形状是 ClickHouse for traces元数据后盖, UI 的下划,以及一小批电子工作(EepEval,RAGAS, LLM- 法官)通过抽样处理 traces。至少从四个人中建立一个自托管 SDK 5分钟内就会发生注射回归

**类型:** Capstone
**语言:** TypeScript (UI), Python / TypeScript (最大值+评估) SQL (ClickHouse)
**先修要求:** 第11阶段(LLM 工程,第13阶段(工具),第17阶段(基础设施),第18阶段(安全)
**实施阶段:** P11 P13 P17 P18 P18
**时间:** 25小时

<a id="problem"></a>

## 问题

2026年所有从事生产活动的人工智能团队 都拥有 observability 飞机旁边的模型,成本归属 Hallucination 侦测,漂浮监测 Jailbreak 信号、 SLO 仪表板、 PII 泄漏警报。 公开源码引用 — 朗弗斯、 凤凰、 OpenLLMetry — 以 OpenTeetrical genAI 语义学公约作为新星的图案。 您可以现在使用仪器 OpenAI, Anthropic谷歌, LangChain, LlamaIndex, 和 vLLM 以一个 SDK 船的宽度

建一个自营仪表板 最少四个人会吃 SDK 家庭,运行 少量的反演任务 traces,检测漂移和警报。 prompt 5分钟后发出警报

<a id="concept"></a>

## 概念

最热门的是 OTLP HTTP. 该 SDK 生成 GenAI- emconv 横跨 : `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.response.id`, `llm.prompts`, `llm.completions`。 Spans 将位于 ClickHouse ,用于分栏分析;元数据(用户、会话、应用程序)将位于 Postgres 。

批量工作运行于抽样 traces。深 Eval 分数的忠诚度、毒性和回答相关性。 trace 带有检索上下文。 LLM- 法官进行特定域的检查(PII泄漏, off-policy 响应) Eval 运行回写到与父文件夹连接的 Eval 窗口 trace.

漂移探测手表 embedding- 一段时间内的空间分布(PSI或KL差数) prompt embeddings警告会给Prometheus 警报管理员提供信息,然后是 Slack/ PagerDuty。 UI是下图15。js 15 配有 Recharts。

<a id="architecture"></a>

## 建筑

```
production apps:
  OpenAI SDK  +  Anthropic SDK  +  Google GenAI SDK
  LangChain + LlamaIndex + vLLM
       |
       v
  OpenTelemetry SDK with GenAI semconv
       |
       v  OTLP HTTP
  collector (ingest, sample, fan-out)
       |
       +-------------+-----------+
       v             v           v
   ClickHouse    Postgres    S3 archive
   (spans)       (metadata)  (raw events)
       |
       +---> eval jobs (DeepEval, RAGAS, LLM-judge)
       |     sampled or all-trace
       |     write eval spans back
       |
       +---> drift detector (PSI / KL on prompt embeddings)
       |
       +---> Prometheus metrics -> Alertmanager -> Slack / PagerDuty
       |
       v
   Next.js 15 dashboard (Recharts)
```

<a id="stack"></a>

## 堆栈

- 指数:开放遥测 SDKs + GenAI语义学公约; OTLP HTTP transport
- 采集器: 尾巴为 Open遥测采集器sampling 处理器(用于成本控制)
- 存储: 点击房屋以覆盖范围, 发布元数据, S3 用于原始事件归档
- Evals:深爱华,RAGAS 0.2,Arize凤凰评估包,定制 LLM-judge
- 漂流:PSI/KL集合 prompt embeddings (sentence-transformers)每周
- 警告:普罗米修斯警报管理者 - > 黑/ 页码Duty
- 用户界面: 下个.js 15 App路由器+ Recharts+服务器动作
- SDKs 支持的框外 : OpenAI, Anthropic谷歌GenAI, 谷歌GenAI,, LangChain, LlamaIndex, vLLM

```figure
ce-otel-drift
```

<a id="build-it"></a>

## 动手实现

1. **收藏家配置 。** OTLP 的开放遥测采集器 HTTP 接收器, 尾巴保护器, 100%保存错误 traces 以及10%的成功, 出口商点击House和S3。

2. **点击House Schema。** Table `spans` 与GenAI Semconv 相仿的列 `gen_ai_system`, `gen_ai_request_model`, `input_tokens`, `output_tokens`, `latency_ms`, `prompt_hash`, `trace_id`, `parent_span_id`,加上 JSON 用于长有效载荷的包。按用户添加次要索引_id 和应用程序_id.

3. **SDK 覆盖测试。** 使用每个小客户端程序写入 SDK (OpenAI, Anthropic谷歌, LangChain, LlamaIndex, vLLM) 使用 OpenLellMetry 自动仪器。 校验每个生成的 GenAI 的计算机横跨了在 ClickHouse 中的那块土地 。

4. **工作重现** 预定的工作读取最后15分样本 traces 并运行 EpenEval 忠实性、毒性和回答相关性。 产出是连接到父的反向 trace.

5. **Custom LLM-judge.** 一名PII泄漏法官:如果回答,请叫警卫 LLM 以分数概率的 PII 泄漏。 高分数响应 地在排队中 。

6. **漂浮探测** 每周计算本周的PSI prompt embeddings 4周的基线,如果PSI超过门槛值,警报。

7. **Dashboard.** 下j15页:概览(范围/秒、成本/用户、第95页) traces (搜索+瀑布)、反量值(信仰趋势、毒性)、漂移(长期的PSI)、警报。

8. **警报链** Prometheus出口商阅读了电子评分总和和潜值百分位数; 警告管理者前往黑地的警告路线和致命的破坏事件。

9. **后退探测器** 输入错误: 被评估的聊天机开始泄漏1%的假 SNSN。 测量 MTTR: 从错误被安装到 Slack 警报 。

<a id="use-it"></a>

## 实际应用

```
$ curl -X POST https://my-otel-collector/v1/traces -d @trace.json
[collector]  accepted 1 trace, 3 spans
[clickhouse] inserted 3 spans (app=chat, user=u_42)
[eval]       DeepEval faithfulness 0.82, toxicity 0.03
[drift]      weekly PSI 0.08 (below 0.2 threshold)
[ui]         live at https://obs.example.com
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-llm-observability.md` 是一个交付品。 LLM 程序,仪表板将 traces,运行 evals, 有关漂移的警报, 以及下js 的表面成本/用户解析。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | Trace- 系统覆盖 | 数目 SDK 生产金字塔的家族(目标:6+) |
| 20 | 度量校正度 | 深 Eval/ RAGAS 分数与手贴的集 |
| 20 | 仪表板 UX | 注入回归时的MTTR(5分钟以下的目标) |
| 20 | 费用/比额表 | 持续1公里的摄入量/无积压的秒数 |
| 15 | 警报+漂移探测 | 普罗米修斯/ 加速管理链一直到最后 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 添加 Haystack 框架的自定义仪器。 以忠实的方式校验 ClickHouse 中的光栅横跨土地 `gen_ai.*` attributes.

2. 向凤凰队评价员交换深电波 traces。测量两个电子发动机之间的分数漂移。

3. 锐化漂移探测器: 计算每个应用程序id的 PSI , 而不是全球范围。 显示每个应用程序的漂移路径 。

4. 添加“用户冲击”页面:每个用户的成本和故障率,每个用户的火花线。

5. 建立尾巴...sampling 保持100% traces 毒性大于0.5加上10%分层样本 rest计量 sampling 引入了偏见。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 吉纳·塞姆科夫 | "OTel LLM attributes" | 2025年开放遥测参数 LLM 横跨属性( 系统、 模型、 tokens) |
| Tail sampling | "Post-trace sample" | 收藏家决定保留或丢弃 trace 完成后( 能够偷看错误) |
| PSI | “人口稳定指数” | 对比两种分布的漂移度; > 0.2 典型信号表示有意义的漂移 |
| LLM-judge | "以val为模范" | 一个 LLM 另得一分 LLM符号上的输出( 忠诚、 毒性、 PII) |
| Tail-sampling policy | "Keep-rule" | 决定 traces 以持续对下降;错误+样本率 |
| 无效间隔 | "连锁评估" trace" | 与原始数据连接的反射分 LLM 调用范围 |
| 每名用户的费用 | "单位经济" | 归属于用户的美元费用_窗口上的id; 关键产品度量 |

<a id="further-reading"></a>

## 进一步阅读

- [Langfuse](https://github.com/langfuse/langfuse) 参考开放核心 observability platform
- [亚里兹·凤凰城](https://github.com/Arize-ai/phoenix) 提供强有力的漂移支持的替代参考
- [OpenLL 算法( 跟踪圈)](https://github.com/traceloop/openllmetry) 自动文书 SDK family
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/) 最令人厌恶的阴谋
- [Helicone](https://www.helicone.ai) 候补主机 observability
- [Braintrust](https://www.braintrust.dev) 备用的Eval-First平台
- [单击主机文档](https://clickhouse.com/docs) 列间宽存储
- [DeepEval](https://github.com/confident-ai/deepeval) 评估图书馆
