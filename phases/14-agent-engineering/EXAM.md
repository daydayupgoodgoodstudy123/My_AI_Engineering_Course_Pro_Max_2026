# 第 14 章分关面试题

每课的 `exam/` 是一套 60 分钟的结对编程题：一个写好一半的服务，5 个测试用 `@pytest.mark.skip("Part N")` 锁住，一次解锁一关。题面是英文 README，用法见每套的 `使用说明.md`。需要 Python 3.10+ 和 pytest，代码只用标准库。

| 课 | 服务 | 1 修 | 2 存 | 3 算 | 4 流 | 5 构 |
|---|---|---|---|---|---|---|
| [01 Agent 循环](01-the-agent-loop/exam/) | reactloop | 观察、思考与行动循环 | JSON 转录快照 | ReAct 文本驱动 | 分离推理通道的 SSE | 嵌套工具观察展开 |
| [02 ReWOO 与计划执行](02-rewoo-plan-and-execute/exam/) | rewoo | Workers 的证据替换 | JSONL 蒸馏计划数据集 | 局部依赖重规划 | 计划就绪即执行的证据流 | 子计划展开与重命名 |
| [03 Reflexion 语言强化学习](03-reflexion-verbal-rl/exam/) | reflexion | 反思与试次循环 | Markdown 学习记录 | 评估器裁决与重试 | 并发学习曲线 CSV | 任务类反思作用域 |
| [04 ToT 与 LATS 搜索](04-tree-of-thoughts-lats/exam/) | thoughtree | Tree of Thoughts 搜索 | 二进制搜索检查点 | MCTS | token 预算内的评估 NDJSON | 表达式树还原 |
| [05 Self-Refine 与 CRITIC](05-self-refine-and-critic/exam/) | critic | 迭代精修循环 | 修订差分链 | 按声明类型核验与人工接手 | SSE 输出护栏 | 嵌套要点批评 |
| [06 工具使用与函数调用](06-tool-use-and-function-calling/exam/) | toolcall | 参数校验与超时 | dbm 用例库 | BFCL 式评分 | 并发用例 TAP | 调用链结果引用 |
| [07 虚拟上下文与记忆分页](07-memory-virtual-context-memgpt/exam/) | memgpt | 记忆工具与分页 | SQLite archival memory | BM25 与 recall@k | 中断式分页 NDJSON | 类型化 core memory |
| [08 记忆块与睡眠计算](08-memory-blocks-sleep-time-compute/exam/) | memblocks | 块工具与 sleep pass | 块版本追加日志 | sleep-time 陈旧与重复清理 | 并发块更新与 unified diff | 派生记录传递失效 |
| [09 混合记忆](09-hybrid-memory-mem0/exam/) | hybridmem | 作用域检索与图存储 | SQLite 三存储 | 向量、图与 KV 融合打分 | 记忆写入审计 CSV | 图的历史时点查询 |
| [10 Voyager 技能库](10-skill-libraries-voyager/exam/) | voyager | 技能库检索与更新 | 内容寻址代码与清单 | 下一任务课程提议 | 迭代改进 NDJSON | 组合技能版本锁定 |
| [11 HTN 与进化规划](11-planning-htn-and-evolutionary/exam/) | htnplan | 分解与回溯规划 | INI 方法库 | 确定性进化搜索 | 异步变异与代际 CSV | 分解树独立校验 |
| [12 Anthropic 工作流模式](12-anthropic-workflow-patterns/exam/) | workflows | 四种工作流模式 | XML 运行审计 | 编排者与工作者 | 实时工单路由 NDJSON | 嵌套工作流成本上界 |
| [13 有状态图编排](13-langgraph-stateful-graphs/exam/) | stategraph | 暂停与恢复 | SQLite 检查点 | 外部结果录制与重放 | 节点增量 SSE | 嵌套子图 |
| [14 Actor 异步运行时](14-autogen-actor-model/exam/) | actorrt | 消息路由与运行时 | 二进制收件箱日志 | 轮转与 selector 群聊 | 跨主机长度前缀帧 | spawn 子树停止 |
| [15 角色分工团队](15-crewai-role-based-crews/exam/) | crewflow | crew 与 Flow | dbm 实体记忆 | 经理路由与草稿依赖 | Flow 步骤 logfmt | 好坏运行逐步比对 |
| [16 OpenAI Agents SDK](16-openai-agents-sdk/exam/) | handoffs | runner、护栏与交接 | SQLite 会话库 | 交接时折叠历史 | span 结束即写 NDJSON | 交接图与护栏可达性 |
| [17 Harness 与会话存储](17-claude-agent-sdk/exam/) | harness | 子 agent harness | JSONL 会话镜像 | 分批上下文与成本规划 | 并行子 agent 结果 SSE | 子 agent 树与空闲清理 |
| [18 生产级 Agent 运行时](18-agno-and-mastra-runtimes/exam/) | agnomastra | 实例化与类型化运行时 | 记忆、快照与日志组合存储 | 请求路径容量规划 | HTTP chunked 字节流 | 嵌套工作流类型检查 |
| [19 SWE-bench 与 GAIA](19-benchmarks-swebench-gaia/exam/) | swebench | 补丁测试与评测闸门 | 运行与测试结果 CSV | Verified、SWE-bench+ 与分位数 | 并发评测 NDJSON | GAIA 问题分解分级 |
| [20 WebArena 与 OSWorld](20-benchmarks-webarena-osworld/exam/) | webgym | 套件运行与结果统计 | 内容寻址应用快照 | 轨迹对齐与超额步数 | 隔离并行回合 CSV | 嵌套成功条件与解释 |
| [21 Computer Use](21-computer-use-agents/exam/) | computeruse | 屏幕操作 Agent 循环 | 内容寻址截图与轨迹清单 | 跨页面逐步安全判定 | 逐步轨迹 logfmt | 缩放坐标与界面树命中 |
| [22 语音 Agent](22-voice-agents-pipecat-livekit/exam/) | voiceframe | 打断与帧流水线 | 二进制通话录制 | 用户轮次与 bot 停止 | Prometheus 分窗指标 | 嵌套语音链延迟预算 |
| [23 GenAI 语义约定](23-otel-genai-conventions/exam/) | semconv | Agent span 与归属 | SQLite 捕获内容库 | 工具错误按模型归因 | 实时 span NDJSON | 嵌套 Agent 用量汇总 |
| [24 Agent 可观测性](24-agent-observability-platforms/exam/) | tracejudge | 会话看板统计 | SQLite 标注队列 | 退化 prompt 版本二分 | 批量摄取与 SSE 看板 | trace 树结构聚类 |
| [25 多 Agent 辩论](25-multi-agent-debate/exam/) | debate | 辩论 runner | 二进制辩论记录 | 稀疏拓扑与置信度投票 | 并发轮次 CSV | 读取图成本与传播距离 |
| [26 Agent 失败模式](26-failure-modes-agentic/exam/) | failtag | 失败模式检测器 | JSON trace 与基线 | 模式率闸门与漂移告警 | 在线 syslog 标注 | 根因失败的级联半径 |
| [27 PVE 注入防御](27-prompt-injection-defense/exam/) | pvegate | PVE 会话安全门 | SQLite 来源与污点记忆 | 工具参数来源检查 | PVE 逐调用与通知语义 | 嵌套内容注入扫描 |
| [28 编排拓扑](28-orchestration-patterns/exam/) | orchestra | 监督者路由 | JSON 拓扑快照 | 按上下文预算构造层级 | JSON-RPC 工具式监督 | 层级路由与死路回溯 |
| [29 队列、事件与 Cron](29-production-runtimes/exam/) | runshape | 作业队列 | SQLite 持久作业表 | cron 触发与停机补跑 | 慢客户端 SSE | 事件级联传播 |
| [30 评测驱动开发](30-eval-driven-agent-development/exam/) | evalgate | 单轮约束、反馈与 flaky 窗口 | 按 commit 保存的 JSON 快照 | 对照 main 的合并闸门 | GitHub Actions 日志 | 护栏与规则的用例覆盖图 |
| [31 Agent 工作台失效分析](31-agent-workbench-why-models-fail/exam/) | surfaces | 运行对照与失败报告 | CSV 体检记分卡 | 失败拦截矩阵与下一步 | 运行事件 NDJSON | harness 原语检查 |
| [32 最小 Agent 工作台](32-minimal-agent-workbench/exam/) | workbench | 回合状态与按需文档 | JSON Lines 任务看板 | 取任务与陈旧状态拒绝 | 回合 JSON Patch | Epic 状态汇总 |
| [33 可执行指令约束](33-instructions-as-executable-constraints/exam/) | rulecheck | 规则报告 | Markdown 规则文件 | 按事件顺序判定规则 | 运行时拦截 TAP | 两跳规则路由可达性 |
| [34 仓库记忆与持久状态](34-repo-memory-and-state/exam/) | statefile | 类型校验与批量原子更新 | 崩溃安全 JSON 快照 | 状态 schema 迁移链 | 多会话 CAS 提交 NDJSON | 分支合并迁移图寻路 |
| [35 初始化脚本](35-initialization-scripts/exam/) | initprobe | 初始化探针运行器 | JSONL 运行历史 | 依赖探针编排与启动判定 | 逐探针 TAP | HEAD 与 LKG 树差异 |
| [36 范围合同与任务边界](36-scope-contracts/exam/) | taskscope | 范围 checker | 不可覆盖的 JSON 归档 | 合同 glob 方言与路径规范化 | diff 检查 SARIF 式 JSONL | 嵌套合同链解释 |
| [37 运行时反馈循环](37-runtime-feedback-loops/exam/) | feedlog | 命令 runner | 轮转 JSONL 反馈日志 | 确定性首尾截断 | 有界内存实时字节流 | 命令重试链 |
| [38 验证闸门](38-verification-gates/exam/) | verifygate | 验收检查与覆盖 | HMAC 签名覆盖日志 | 四份工件归并为结论 | Markdown 验证摘要流 | 堆叠提交逐层验证 |
| [39 独立 Reviewer](39-reviewer-agent/exam/) | reviewer | rubric 与签收队列 | 内容寻址评审历史 | 证据评分与双评审对账 | 构建评审交替 CSV | 评审意见线程 |
| [40 多会话交接](40-multi-session-handoff/exam/) | handoffpkt | 交接包生成 | 每会话 JSON 交接历史 | 交接前清理检查 | 超长日志单遍裁剪 NDJSON | 分支交接链 |
| [41 真实仓库工作台](41-workbench-for-real-repos/exam/) | realrepo | 五项结果测量 | SQLite 结果库 | 两条流水线配对比较 | 运行里程碑 CSV | 变更影响的测试图 |
| [42 工作台交付综合项目](42-agent-workbench-capstone/exam/) | wbpack | 安装器所有权与版本锁 | TSV 清单哈希与权限 | 语义版本与三方升级 | itemize 安装日志与回滚 | 组件依赖闭包与排除 |
| [43 编码前的任务框架](43-frame-the-task-before-code/exam/) | taskframe | 任务框架与事实凭据校验 | 引用行内容寻址与漂移检测 | 决策证据覆盖与开工判定 | 按未决问题提前停止侦察 | 允许路径的最小安全划分 |
| [44 基于证据的执行计划](44-plan-from-evidence/exam/) | evidplan | 计划校验与精确环成员 | JSON 计划与追加进度日志 | 产物修订后的传递重开 | 中断接续的 Markdown 清单 | 证明义务拆分与 resolver 前置 |
| [45 隔离委派与合并合同](45-delegate-with-isolation/exam/) | delegate | 所有权规范与只读隔离 | 独占创建的原始字节证据 | 证明回执与整合决策 | NDJSON 交接依赖门 | 全前缀所有者与并发冲突 |
| [46 把纠正转成系统改进](46-turn-feedback-into-system/exam/) | promote | 更正归属、提升门槛与原因合并 | SQLite 完整棘轮快照 | 按原因选最早有效控件 | SSE 严重或复发即时提升 | 为什么图的最深有效归属 |
| [47 先定义结果再选择产物](47-outcomes-before-output/exam/) | outcomes | 结果泄漏、边界与技术证据 | 内容寻址的框架修订史 | 有限短语最长匹配与原文区间 | 编辑序号与完整问题差量块 | 结果树的用户、约束与非目标 |
| [48 发现真实工作流](48-discover-the-real-workflow/exam/) | flowmap | 逐步证据与百分比舍入 | SQLite 工作流与多条证据 | 四类风险、交接与未确认线索 | CSV 录屏分段与等待归属 | 保留真实终点的工作流变体树 |
| [49 假设地图与风险优先](49-map-assumptions-and-risk/exam/) | riskmap | 证据极性、未决选择与风险排名 | CSV 假设与预注册实验 | 首批样本与严格预注册判定 | logfmt 实验完成与未满批收尾 | 三值假设树与仍有效的下一实验 |
| [50 选择能改变决定的最小切片](50-choose-the-smallest-testable-slice/exam/) | slicepick | 评分前提、可逆代价与候选身份 | JSON 完整切片决策快照 | 相对证明需求的假最小值与停止规则 | SSE 连续错误停止规则 | 工作流最少缺失节点补全 |
| [51 保留判断空间的规格](51-write-specifications-that-preserve-judgment/exam/) | specmodes | 边界、例子、理由与有序编译 | JSONL 决策理由修订史 | 主张与有限证明的精确匹配 | NDJSON 动作前边界与人工检查点 | 边界 AST 许可与阻塞路径 |
| [52 结果出现前定义成功指标](52-design-success-metrics/exam/) | metricplan | 指标合同、反指标与源快照读取 | SQLite 原始回放与真实时序 | 预定批次与安全优先复合判定 | TAP 样式批次与写入终止 | GQM 共享指标与最差状态追溯 |
| [53 明确选择原型、试点或生产环境](53-prototype-pilot-or-production/exam/) | stagegate | 阶段责任、声明与活跃用户计数 | SQLite 原始声明与独立技术标记 | 累计暴露与既定责任漂移 | syslog 样式告警与安全步骤放行 | 必要依赖义务与缺口证据路径 |
| [54 用反馈棘轮明确责任与退役条件](54-build-the-feedback-ratchet/exam/) | ratchet | 目标元数据、双轨影响与复审日期 | CSV 全局修订与双轨控件历史 | 复审触发与有证据的退役 | NDJSON 累积证据与独立动作 | 传递取代与退役后的回退控制 |

每套的 `verification.txt` 由 [check_traps.py](../../scripts/exam_curriculum/check_traps.py) 在临时副本上生成：五关默认锁住，参考答案全过，原始代码全挂，Part 1 逐层修复的顺序符合设计，`solution/traps.json` 里的每种错误修法都会被抓住。难度和 60 分钟的时间分配还没有经过真人计时校准。
