---
name: llm-observability
description: Build a self-hosted LLM observability dashboard that ingests OpenTelemetry GenAI spans, runs evals, and catches injected regressions in under five minutes.
version: 1.0.0
phase: 19
lesson: 11
tags: [capstone, observability, otel, langfuse, phoenix, evals, drift, clickhouse]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


生产情况 LLM 流量至少超过 6 SDK 家庭(单位: 单位: 家庭)OpenAI, Anthropic谷歌GenAI, 谷歌GenAI,, LangChain, LlamaIndex, vLLM,部署一个自营的 observability 飞机上,OTLP GenAI-Semconv 横跨,运行评估,检测漂移和警报。

构建计划 :

1. OTLP 的开放遥测采集器 HTTP 接收器,尾巴...sampling 处理器(保持100%的错误,10%的成功,100%的高毒性/PII), 出口者点击House+S3。
2. 点击房屋横跨 GenAI emconv: gen 的图案_系统, gen_请求、模型、使用、投入/产出_标记, 潜伏_毫秒, 用户_ID, 应用程序_身份,加 JSON 包为 prompts/completions.
3. 用于应用程序、用户、会话、批注队列的 Postgres 元数据存储器。
4. 客户端应用程序的 OpenLLMetry 自动提示 SDK 家庭; 验证横跨陆地的金刚石。
5. 深爱瓦尔+RAGAS+凤凰评估包预定在取样中进行 traces; 自定义 LLM- PII和PI法官 off-policy.
6. 每周PSI/KL 集合漂移探测器 prompt embeddings; 警戒阈值 0.2。
7. Prometheus 电子评分总和和延迟百分位数出口商; 警告管理者到 Slack(警告)+ PagerDuty(临界)。
8. 15 App路由仪表板:概览, trace 搜索 + 瀑布、 反向趋势、 漂移图、 警报 。
9. 回归探测器:输入一种反应模式,以泄漏1%的时间假的SSN;测量MTTR(待命-火速时间)。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | Trace- 系统覆盖 | 数目 SDK 生产金字塔的家族(目标6+) |
| 20 | 度量校正度 | 深 Eval/ RAGAS 分数与手贴的集 |
| 20 | 仪表板 UX | 注射回归时的MTTR(目标在5分钟以下) |
| 20 | 费用/比额表 | 维持1k 宽/ 秒最少,无积压 |
| 15 | 警报+漂移探测 | 普罗米修斯/ 加速管理链一直到最后 |

艰难的拒绝 :

- 用于生成非在 OpenTelephy GenAI emconv 中的属性名称的 Span 方案 。
- Tail-sampling 减少错误的政策(众所周知的反模式)。
- 以摄取率运行的逆差 sampling (费用不可接受)。
- 显示“延迟”的仪表板,没有第50/p95/p99页的分隔。

拒绝规则 :

- 拒绝坚持 prompts 或没有PII编辑政策完成。
- 拒绝 " 多 -SDK 支持",没有每个 -SDK canonical-span regression test.
- 拒绝在没有基线窗口的情况下运送漂移探测; zero-shot 漂移是没用的。

输出: 包含收藏器配置、 点击House schema、 下15 个仪表板、 电子算法、 漂移探测器、 提醒链、 10 k-trace 带有附加注释回归的演示数据集, 以及用于输入 PII 回归的MTTR 和在迭代中将 MTTR 降为空的顶端三张仪表板 UX 改进的写入记录。
