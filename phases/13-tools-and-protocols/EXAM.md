# 第 13 章分关面试题

每课的 `exam/` 是一套 60 分钟的结对编程题：一个写好一半的服务，5 个测试用 `@pytest.mark.skip("Part N")` 锁住，一次解锁一关。题面是英文 README，用法见每套的 `使用说明.md`。需要 Python 3.10+ 和 pytest，代码只用标准库。

| 课 | 服务 | 1 修 | 2 存 | 3 算 | 4 流 | 5 构 |
|---|---|---|---|---|---|---|
| [01 工具接口](01-the-tool-interface/exam/) | toolloop | 调用关联、参数校验与熔断 | 会话日志与崩溃恢复 | Rule of Two 确认门 | 逐步 trace 文本流 | 组合工具的后果传播 |
| [02 函数调用详解](02-function-calling-deep-dive/exam/) | fcbridge | 三家请求与回复翻译 | SQLite 规范会话库 | 三家请求渲染与限额 | 并发等价探针 CSV | strict 模式 schema 编译 |
| [03 并行与流式调用](03-parallel-and-streaming-tool-calls/exam/) | fanout | 分片重组与按 id 回答 | 二进制在途调用日志 | 依赖与并发调度 | 边生成边执行的 NDJSON | 增量 JSON 参数解析 |
| [04 结构化输出](04-structured-output/exam/) | invoicekit | 错误路径与拒答分类 | Decimal 结果快照 | 带反馈的提取重试 | 约束解码逐 token 输出 | 按 kind 判别的 oneOf |
| [05 工具 Schema 设计](05-tool-schema-design/exam/) | toollint | 注册表 lint 规则 | 内容寻址发布库 | 破坏性变更判定 | 分页注册表流式 lint | 描述的交叉引用图 |
| [06 MCP 基础](06-mcp-fundamentals/exam/) | mcpcore | 无状态请求元数据 | SQLite transcript 库 | 生命周期检查顺序 | 按 id 配对的 trace 流 | 嵌套能力要求匹配 |
| [07 MCP 服务端](07-building-an-mcp-server/exam/) | notesrv | 通知分派、缓存与笔记 id | 笔记正文与元数据目录 | tools/call 错误与删除授权 | stdio 分帧与逐条响应 | 新旧时代按连接隔离 |
| [08 MCP 客户端](08-building-an-mcp-client/exam/) | multipeer | 多服务路由与 id 关联 | 固定 peer 的 INI 配置 | 新旧代际协商与白名单 | stdio 连接池与重启 | 防冲突命名空间合并 |
| [09 MCP 传输](09-mcp-transports/exam/) | streamhttp | HTTP 路由头唯一性与读体 | SQLite 跨副本草稿 | HTTP 响应映射 | 请求级 SSE | HTTP/SSE/JSON-RPC 分层解码 |
| [10 资源与 Prompts](10-mcp-resources-and-prompts/exam/) | uricatalog | 资源、prompt 与订阅授权 | dbm 响应缓存 | 签名游标分页 | 共享通道多订阅 NDJSON | URI 模板路由树 |
| [11 Sampling 与 MRTR](11-mcp-sampling/exam/) | mrtrkit | MRTR 轮次与状态绑定 | 版本化签名 requestState | 宿主驱动 MRTR 轮次 | 并发审批与主体预算 CSV | 多轮阶段图 |
| [12 作用范围与 Elicitation](12-mcp-roots-and-elicitation/exam/) | scopegate | 工作区范围与防重放 | SQLite 一次性 nonce | 表单确认删除 | URL 模式带外同意流程 | 嵌套工作区授权 |
| [13 Tasks 扩展](13-mcp-async-tasks/exam/) | durabletask | 轮询与取消语义 | 共享目录任务快照 | worker 与按 key 输入 | 任务快照 SSE 订阅 | worker 租约与过期清理 |
| [14 MCP Apps](14-mcp-apps/exam/) | appbridge | UI 绑定与文本回退 | App 条目身份与安全元数据缓存 | 宿主即时权限决策 | postMessage 桥生命周期 | 缓存失效与重挂载 |
| [15 工具投毒](15-mcp-security-tool-poisoning/exam/) | poisonguard | 扫描与整描述符 pin | JSON pin 清单 | 刷新时逐工具判定 | 分页多后端判定 NDJSON | 按策略路径脱敏 |
| [16 MCP 授权](16-mcp-security-oauth-2-1/exam/) | oauthflow | 发现、PKCE 与 iss 校验 | 按 issuer 绑定的凭据文件 | 增量授权与注册优先级 | 回环重定向与表单请求 | 防 SSRF 的重定向链 |
| [17 网关与注册表](17-mcp-gateways-and-registries/exam/) | mcpgateway | 转发、凭据中介与限流 | JSONL 协议证据与秘密脱敏 | 运行时策略与依赖故障 | SSE 中继与任务路由 | 审计调用链重建 |
| [18 生产环境认证](18-mcp-auth-production/exam/) | tokengate | JWKS 缓存与受众检查 | SQLite 内省缓存 | 校验模式与依赖故障 | 事故回放 CSV | DCR 重定向 URI 规则 |
| [19 A2A 协议](19-a2a-protocol/exam/) | agentcard | writer 生命周期与下载 | SQLite 任务库 | 签名 Agent Card 与技能选择 | 长度前缀帧流 | 多跳委托视图 |
| [20 OTel GenAI 追踪](20-opentelemetry-genai/exam/) | genaitrace | 一次运行一条 trace | OTLP/JSON span 日志 | 语义约定与指标 | 按传输传播 context 与分批导出 | 自身耗时与最重链 |
| [21 LLM 路由层](21-llm-routing-layer/exam/) | modelrouter | 脱敏、5xx 回退与计费 | SQLite 微美元成本账本 | 加权池、预算与 EU 驻留 | 延迟路由 CSV | 别名图展开 |
| [22 Agent Skills 契约](22-skills-and-agent-sdks/exam/) | skillpack | frontmatter 解析、重复键与命名 | SKILL.md 原样写回 | 包校验顺序 | 生命周期 TAP | 工作流依赖与安装顺序 |
| [23 工具生态综合项目](23-capstone-tool-ecosystem/exam/) | researchops | 研究任务、轮询与 trace | CSV 论文目录 | 预算内的研究作业 | 按论文顺序的 Markdown 报告 | 证据声明图 |
| [24 技能发现与渐进披露](24-skill-discovery-and-progressive-disclosure/exam/) | skillcat | 浅层发现与冲突裁决 | 发现结果 JSON 快照 | 目录上下文预算 | logfmt 披露日志 | 引用图可达性与距离 |
| [25 技能调用与路由](25-skill-invocation-and-routing/exam/) | skillroute | 先资格后排序的路由 | 可重入运行状态 | 参数三层绑定 | 多轮生命周期 NDJSON | 技能调用链与环检测 |
| [26 技能权限与沙箱](26-skill-permissions-sandboxes-and-trust/exam/) | sandboxpol | origin 与 argv 审查门 | 内容寻址安装库与升级预览 | 启动计划与凭据范围 | 输出字节流中继与脱敏 | 归档成员树检查 |
| [27 技能评测与打包](27-skill-evals-packaging-and-portability/exam/) | skilleval | 触发报告与安装校验 | CSV 观测日志 | 分层发布门与可信证明 | JUnit XML 流 | 宿主能力矩阵 |
| [28 工具契约与内容](28-mcp-tool-contracts-and-content/exam/) | contractkit | 分页发现与结果契约 | 内容块归档与本地负载限额 | 参数头编码、存在性与按序校验 | JSON-RPC 补全防抖 | schema 树注解审计 |
| [29 可靠性与取消](29-mcp-reliability-cancellation-and-flow-control/exam/) | reliablerpc | 取消后停发、严格递增进度与缓冲 | SQLite 幂等账本 | 重试分类与取消信号 | 双时钟 SSE | 竞态交错穷举与最短反例 |
| [30 注册表供应链](30-mcp-registry-supply-chain-and-drift/exam/) | regadmit | 证据来源与哈希链账本 | 账本文件与外部锚点 | 准入控制与精确 pin | 漂移对账 NDJSON | 按账本历史回滚 |
| [31 一致性工程](31-mcp-conformance-versioning-and-operations/exam/) | conformance | 脱敏证据发布门 | 一案一文件的 JSON fixture | 响应一致性规则 | 代理三视图 TAP | 带路径的 SDK 差分 |

每套的 `verification.txt` 由 [check_traps.py](../../scripts/exam_curriculum/check_traps.py) 在临时副本上生成：五关默认锁住，参考答案全过，原始代码全挂，Part 1 逐层修复的顺序符合设计，`solution/traps.json` 里的每种错误修法都会被抓住。难度和 60 分钟的时间分配还没有经过真人计时校准。
