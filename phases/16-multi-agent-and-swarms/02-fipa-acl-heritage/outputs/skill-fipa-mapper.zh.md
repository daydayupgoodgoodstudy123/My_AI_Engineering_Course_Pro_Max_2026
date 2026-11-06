---
name: fipa-mapper
description: Map any 2026 agent-protocol spec (MCP, A2A, ACP, ANP, CA-MCP, NLIP, or a new one) onto FIPA-ACL performatives and interaction protocols to decide what is genuine novelty and what is reinvention.
version: 1.0.0
phase: 16
lesson: 02
tags: [multi-agent, protocols, FIPA, speech-acts, interoperability]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给新人 agent- 程序规格,制作FIPA-ACL绘图,使读者能够知道哪些部件是再生的,哪些是真正的新结构。

显示 :

1. **信封映射** 对于每个信件类型, 标注定义的, 命名最近的 FIPA 表现( )`inform`, `request`, `query-if`, `query-ref`, `propose`, `accept-proposal`, `reject-proposal`, `cfp`, `subscribe`, `cancel`, `failure`, `not-understood`如果没有符合要求,请准确描述差距。
2. **关系模型。** 与FIPA的用户相比,该规格如何将请求与回复、取消原始请求和数据流事件联系起来? `:conversation-id` 和 `:reply-with` fields.
3. **内容语言姿态。** 规格是否授权内容图( 类型化的文物, 或) JSON-Schema, 接受自然语言, 还是开放? 比较FIPA的 SL0/ SL1 和本体学字段 。
4. **互动程序库。** FIPA 的哪些互动协议可以在规格之上执行: 合同网、 订阅通知、 请求- 何时、 接受? 列出执行每个协议的信息 。
5. **发现模型。** 怎么样 agent 寻找对应方和能力(MCP `listTools`, A2A Agent 与 FIPA 的目录促进器和黄色页面服务相比, ANP 是否 + 元协议 ?
6. **复兴与创新** 制作一个包含三列的简短表格: [FIPA概念,现代规格等同,什么变化]。将每行标为 [reinvention] 或 [novel-structure]。只有当“新结构”的标本引入了FIPA没有的原始特性时,行才“新结构”——分散特性、打字的多式联运工艺品,以及 LLM- 解释的内容是常见的候选者。

艰难的拒绝 :

- 任何声称规格的地图都是“革命性的”而没有显示原始FIPA。 语言-动作理论+本体学的间接成本是失败模式,而不是原始人。
- 框架比较忽略了发现层。 一个没有发现的图示不完整,不是新奇的。
- 诸如“X议定书取代FIPA”之类的声明,没有涉及当两个缔约方提出时发生的情况。 agents 内容含义(语义流)存在分歧。

拒绝规则 :

- 如果标本是标准化前(草稿短于6个月,没有公开实施),则说明绘图是临时的,并标明三种最可能的变化。
- 如果标本是封闭源码或只限企业(某些非加太语气),请绘制文件记载的内容并标明空白。
- 如果用户只提供博客文章( 没有 spec 文档), 请在绘图前先询问该页面 。

输出: 一页的简要。 从单句摘要开始 (“ X 协议是 FIPA ” `request`/`subscribe` 与 JSON 语法和基于 DED 的发现层。”),然后上面的六个部分, 然后一个结尾段落回答:“这个特征将重新发现哪个旧FIPA失败模式?”
