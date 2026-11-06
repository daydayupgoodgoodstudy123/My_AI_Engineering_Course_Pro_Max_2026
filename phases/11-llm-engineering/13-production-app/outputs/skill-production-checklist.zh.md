---
name: skill-production-checklist
description: Decision framework for shipping LLM applications to production -- covers every component with specific thresholds and pass/fail criteria
version: 1.0.0
phase: 11
lesson: 13
tags: [production, deployment, llm, architecture, scaling, cost, observability, guardrails]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="production-llm-checklist"></a>

# Production LLM Checklist

当运输 LLM 应用,通过该核对表进行顺序。每一节都有有具体阈值的过/不合格标准。

<a id="1-security-ship-blockers"></a>

## 1. 安保(船舶阻塞器)

这里的每件东西都必须在部署前通过

| Check | 通行证标准 | 如何校验 |
|-------|--------------|---------------|
| API 键在 env vars 中 | 代码库中无硬编码密钥 | `grep -r "sk-" --include="*.py"` 返回无 |
| 输入 guardrails active | Prompt injection 模式被屏蔽 | 发送“ 忽略所有先前的指示” - 返回被屏蔽的响应 |
| PII 编辑 | SSN, 信用卡, 电子邮件模式被捕获 | 发送“ 我的 SN 是 123 - 45 - 6789 ” - PII 以前被编辑过 LLM call |
| 输出过滤 | 危险内容被封 | 模型无法返回 `DROP TABLE`, `rm -rf`, `exec()` patterns |
| 限 率 | 执行每个用户的要求上限 | 10秒后同一用户提出100项请求 -- -- 最后50个+被拒绝 |
| 在所有端点的认证 | 没有未经认证的 LLM access | `curl /v1/chat` 不使用 token 返回 401 |
| 限制 CORS | 仅允许生产域 | `Origin: evil.com` 请求被拒绝 |
| 最大输入 tokens | 超过限额的请求被拒绝 | 发送 50K token 输入 -- 返回 413 或短跑 |

<a id="2-reliability-week-one-survival"></a>

## 2. 可靠性(Wee-One Survival)

这些防止了第一次接听电话

| Check | 通行证标准 | 如何校验 |
|-------|--------------|---------------|
| Retry with backoff | 5xx 3 重试, 指数延迟 | Kill LLM 模拟中请求 - 重试在日志中可见 |
| 后退模式链 | 2+ 链中模型 | 主要模式不详 -- -- 后退后仍会回弹 |
| 请求超时 | 最多30个外线电话 | Slow LLM 模拟( 60s) -- 请求时间在 30 时结束 |
| Graceful degradation | Cache/RAG 失败不崩溃服务 | 停止缓存 - 请求仍然成功( 更慢、 更贵) |
| 健康检查终点 | 回返受抚养人身份 | `GET /health` 返回 `{"status": "healthy", "cache": ..., "llm": ...}` |
| Streaming works | First token 500米以下 | Time-to-first-token 测量,持续 < 500米 |
| 错误消息是安全的 | 内部错误从不泄漏到用户 | 强制500 - 用户看到通用错误, 不是堆叠 trace |

<a id="3-cost-control-month-one-economics"></a>

## 3. 成本控制(Month-One Economics)

防止了50K的意外发票。

| Check | 通行证标准 | 如何校验 |
|-------|--------------|---------------|
| 跟踪的每项请求的费用 | 每一个请求日志 token 计数+美元费用 | 请求日志已存在 `input_tokens`, `output_tokens`, `cost_usd` fields |
| Semantic cache active | 重复模式中受打击率 > 20% | 1000次测试请求后缓存数据显示点击率 |
| 已配置缓存 TTL | 条目过期( 默认值:1小时) | 条目插入 -- -- TTL 后未返回 |
| 用户费用跟踪 | 用户合计费用_id | Dashboard/API 按成本显示前10名用户 |
| 费用提醒 | 每日预算的80% | 设定每天10美元的预算,发出8.50美元的请求 -- -- 警报火灾 |
| 按成本分列的模式路线 | 低复杂性查询使用更便宜的模式 | 简单的问题路径 gpt-4微米,复杂到 gpt-4o |
| 最大输出 tokens set | 每个模板都设定了回复上限 | 最大模板_输出_符号=512 - 响应从未超过它 |

**成本估算公式:**
```
Monthly LLM cost = DAU x queries_per_user x 30 x (1 - cache_hit_rate) x (avg_input_tokens x input_price + avg_output_tokens x output_price) / 1,000,000
```

**按规模划分的基准阈值:**

| DAU | 目标费用/要求 | 月预算 |
|-----|-------------------|----------------|
| 1K | < $0.005 | < $750 |
| 10K | < $0.003 | < $4,500 |
| 100K | < $0.001 | < $15,000 |

<a id="4-observability-debugging-in-production"></a>

## 4. Observability (生产中的调试)

你无法修复你看不见的东西

| Check | 通行证标准 | 如何校验 |
|-------|--------------|---------------|
| Structured JSON logging | 每个请求都产生 JSON 日志行 | 日志包含: 请求_ID, 用户_ID, 型号, tokens, 延迟_百万兆瓦,费用 |
| 请求跟踪 | End-to-end trace 带有组件计时 | 单项请求显示 : guardrail (5米)+缓存(2米)+ llm (3200米)+电子算法(1米) |
| 延迟跟踪 | 测量P50、P95、P99 | 1000份申请之后:P50 < 2,P99 < 10 |
| 错误率监测 | 计算和分类错误 | 仪表板显示:0.5% API 错误,0.1% guardrail 区块,0.01%超时 |
| 缓存度量 | 点击率、误差率、可视条目数 | `GET /v1/cache/stats` 返回当前数字 |
| A/B 测试度量 | 记录到的每千差数质量 | 请求日志提示_模板+供比较的版本 |
| Eval 记录 | 按要求记录的质量信号 | 反应长度、延迟度、模型、模板版本存储为离线分析 |

<a id="5-prompt-management"></a>

## 5. Prompt Management

Prompts 它们是代码,把它们当做代码

| Check | 通行证标准 | 如何校验 |
|-------|--------------|---------------|
| 模板已版本 | 每个模板都有名称 + 版本字符串 | 模板更改创建新版本, 旧版本保存 |
| A/B测试支持 | 交通由确定用户散列 | 同一用户总是看到实验中的相同变量 |
| Rollback capability | 恢复到上一个版本, 时间小于 1 分钟 | 改变实验配置 -- -- 交通即时移动 |
| 模板验证 | 创建前验证的变量 | 模板中缺少变量会产生清晰错误, 不是按键错误 |
| System prompt separation | 系统及 user messages 单字段中 | System prompt 未被归为 user message |

<a id="6-scaling-readiness"></a>

## 6. 规模准备

发射不需要,10点需要

| Check | 通行证标准 | 如何校验 |
|-------|--------------|---------------|
| Async LLM calls | 没有线索卡住 API calls | 50项同时提出的请求 -- -- 服务器 CPU 停留时间 < 30% |
| 连接共享 | HTTP 连接再利用 | Network trace 显示持续连接到 LLM provider |
| 水平缩放 | 无国籍服务器设计 | 负载平衡器后面有2个实例 -- -- 所有请求均成功 |
| 队列支持 | 非实时任务排队 | 汇总请求返回任务_身份,通过投票获得结果 |
| 装入测试 | 100个同时用户, < 5% 错误率 | `wrk` 或 `locust` 目标方位的测试通过 |

<a id="implementation-order-for-new-projects"></a>

## 新项目执行令

1. **第一天: 时间** API 服务器+ prompt 模板+单 LLM 重试调用
2. **第二天 时间轴:** 输入 guardrails + 输出 guardrails +错误处理
3. **3号:** Semantic cache + 每项请求的费用跟踪
4. **4号:** Streaming (SSE)+健康检查终点
5. **5号** 结构化记录+请求跟踪+电子记录
6. **第 2 周：**A/B 测试 + prompt 版本管理 + rollback
7. **3周 时间轴:** 后退模式链+ graceful degradation
8. **4周 :** 装入测试+同步优化+水平缩放

<a id="quick-diagnostic"></a>

## 快速诊断

如果生产有问题,请按此顺序检查:

1. **用户抱怨错误?** 检查健康端点, 然后在日志中错误率, 然后 LLM 服务商状态页面
2. **反应迟缓?** 检查 P99 延迟度, 然后缓存点击率, 然后 LLM 答复时间 traces
3. **费用上涨?** 检查每个请求的成本趋势,然后缓存点击率,然后按成本计算最高用户,然后寻找 prompt 模板上增加的更改 token count
4. **质量下降?** 检查是否新建 prompt 版本已部署, 请检查 RAG 检索准确性已改变, 请检查模式提供者是否更改了默认的模型版本
5. **安全事件吗?** Check guardrail 块速率( 单击落= guardrails 选项),检查请求日志的异常模式, 旋转 API 立即按键
