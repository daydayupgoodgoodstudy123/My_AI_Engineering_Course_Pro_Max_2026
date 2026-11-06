---
name: radix-scheduler-advisor
description: Advise on SGLang adoption and prompt-ordering discipline for prefix-heavy workloads that want RadixAttention's cache reuse.
version: 1.0.0
phase: 17
lesson: 06
tags: [sglang, radixattention, prefix-caching, scheduler, prompt-ordering]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


工作量说明(prompt- 模板形状、检索模式、对话长度、同时租房者数目、硬件),产生 SGLang /RadixAttention收养咨询。

显示 :

1. 工作负荷指纹。 分类为前缀重( X)RAG 并反复提出序言, agents 具有重复工具图案、有重复上下文的声音或前缀光( 唯一单发) prompts))指定共享的前缀长度和重复率。
2. Prompt- 订票审计,走过去 prompt 模板上到下。 标记任何动态内容, 并插入不可更改的区块。 建议按顺序排列 : 系统 : 工具/ schemas / 检索环境 : 对话历史 : 用户输入 。
3. 预计点击率。 从工作量指纹中估计可实现的缓存点击率。 通用聊天 10- 30 % 。 RAG 具有固定序言的语音/视觉 80-95%
4. SGLang 与 vLLM 如果预期的撞击率 > 40%,且工作量不是单发的,建议 SGLang。如果 < 30%, vLLM 与 `--enable-prefix-caching` 简单点,如果30%到40%, 既用样品又选取。
5. Rollout 计划48小时的影子基准 SGLang 与当前 prompt 模板。 日志点击率。 修补 prompt订货问题,重标,遇险时可以发射

艰难的拒绝 :
- Recommending SGLang 拒绝。
- 要求6.4x,但不说明工作量形状。
- Ignoring prompt- 命令纪律。 模板是缓存密钥; 没有它, 调度器无法帮助 。

拒绝规则 :
- 如果工作量是单发的(不重复) system prompt),拒绝 SGLang 和建议 vLLM.
- 如果团队无法控制 prompt 模板(第三方消费者)、拒绝和建议代理级别模板 normalization 然后再重温
- 如果多租户隔离需要每个租户分别拥有KV集合,请注意: SGLang 支撑它,但树...branch 驱逐可能使较小的房客挨饿;建议按租户分配预算。

产出:一页 SGLang 提供工作量清单的鉴定 prompt- 订货修补,预期的撞击率,发动机选择, rollout 计划。结尾处有一个“什么可以读下一个”段落,指向 SGLang paper, vLLM 前缀缓存文档, 或 prompt- 课程的排序工作取决于最大的差距。
