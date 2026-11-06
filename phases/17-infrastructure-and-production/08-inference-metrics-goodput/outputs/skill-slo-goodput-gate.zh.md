---
name: slo-goodput-gate
description: Produce a CI/CD-ready benchmark recipe that gates LLM deploys on goodput, not throughput, with P50/P90/P99 percentiles and a documented tool choice.
version: 1.0.0
phase: 17
lesson: 08
tags: [inference-metrics, goodput, ttft, tpot, itl, slo, benchmarking]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于工作量(模型、硬件、目标同货币、用户-直观互动类型), streaming 聊天/ 一发子弹/声音/ agent),产生 goodput- CI/CD的SLO门

显示 :

1. 标准规则。 三个阈值: TTFT P99 绑定, TPOT P99 绑定, E2E P99 绑定。 从交互类型中选择可辩护的值( )streaming 聊天:TTFT 500毫秒,TPOT 25毫秒,E2E 3秒;声音:TTFT 300毫秒更紧; agent:E2E 5松绑。
2. 基准配方。 工具选择( LLMPerf 或 GENAI- Perf ) , 请描述您选择的配方和原因 。 Prompt 分布( 平均+输入和输出的 stddev) tokens货币清查(目标的25%、50%、100%、150%)。
3. Goodput 计算。公式:满足所有三种限制的要求的分数。目标99%用于生产,95%用于金丝雀。
4. 百分比报告:每条指标,报告P50、P90、P99(绝不是单枪匹马),注解仅指检查是否正常。
5. 工具陷阱注释。 请指出该工具是否包含或将TTFT排除在国际交易日志之外。 在对各个团队进行比较之前先修改定义 。
6. 格丁逻辑。 CI通过,如果 goodput 目标方位 目标方位 goodput 将5分以上货币贬值100%至150%,这表明没有进行负荷测试的正室。

艰难的拒绝 :
- 仅仅靠量力而努力,拒绝和要求 goodput.
- 汇报意味着没有P99,拒绝
- 用户名和工具版本。 拒绝 。
- 仅以目标货币为基准;总是进行扫描。

拒绝规则 :
- 如果用户没有 SRO 写下来, 拒绝并首先根据交互类型写入 。
- 如果 prompt 分布为“ 相同” prompts 在一个循环中,拒绝——这是 prompt- 一致性陷阱,需要现实的合成
- 如果基准值 < 30 个运行或 < 100个运行请求,则拒绝数量在统计上不足。

输出: 单页 SLO 门框列出阈值、 基准配方、 工具选择、 百分位报告模板以及 CI 出入/ 失败规则。 结尾处有一个“ 如何测量下一个” 段落命名 goodput 与货币曲线 prompt- 分配敏感度,或块prefill 视已知弱点而定,对尾巴进行开/离轨比较。
