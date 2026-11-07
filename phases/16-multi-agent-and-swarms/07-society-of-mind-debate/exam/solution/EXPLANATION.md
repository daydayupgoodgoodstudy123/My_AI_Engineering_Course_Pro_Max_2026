# 参考实现说明

## Part 1

`make_round_record` 保留原 finite float。最终 renderer 才使用源代码样式的 `.2f` 展示，完整 raw precision 仍可用于计算与持久化。report 同时给出 agreement 和独立 truth error；无 truth 时 error/correctness 都为 None，agreement 不生成真实性标签。

一维最大 pairwise gap 等于最大答案减最小答案，只有一个或零个输入时为零。完整 RoundDesk report 包含每个参与者、原 record、display、均值、agreement、truth error、correctness 和 diameter；所有业务输出检查都在 timer 内。这个 helper 没有权重更新逻辑。

## Part 2

文件保存全局有序名字表和每个 round 的 index、独立 truth、按名字对齐的 answer/confidence。每轮临时排列变化不改变配对。truth=0.0 和 None 含义不同。即使封口 agent 向量不变，每个已完成轮次的 index 仍独立保存，不能对相邻相同向量去重。完整 GIVEN binary64/text/optional codec 负责实际位级格式与生命周期；精度断言验证集成，候选领域工作在布局和命名对齐。

## Part 3

按 source 公式计算 own 与全部 peers 的 Σ(weight×answer)/Σweight。输入 binary64 用 Fraction 精确表达、累计，最后转一次 float，因此有限凸均值不因中间 overflow 或 cancellation 丢失仍可表示的残差；这明确是局部数值合同，不声称原 main 使用了精确算术。总权重零拒绝。

每轮使用正确 GIVEN frozen vector。每个 agent commit 同一组前轮值求得的答案，自己的 confidence=min(old×1.05,1.0)，并追加新答案。先记录初值，再严格执行 requested extra rounds，不因 agreement、truth 或答案稳定提前结束。完整全连接且包含自己的更新一轮后产生一个公共加权均值；后续 confidence 仍按合同变化，不意味着事实改进。

## Part 4

projection 从一个 sealed round 产生 N 个 agent 行和一条 diagnostics 行。agent 值取本人的 answer/confidence，全部行的 agreement/error 取完整 vector 的 report。完整 GIVEN async driver 提供 header、逐轮发布、源关闭和 CSV codec。

## Part 5

RoundCatalog 正确给定 round/name 解析与 previous handle。候选构建每轮一个向量节点，所有本轮 agent 的推导共享同一个 prior vector，边权记录上一轮 confidence。追踪从请求 target 出发，只沿非零权重访问祖先；初始 target 只依赖自己的原答案。多个因果根按初始 agent 顺序返回，不能按名字排序。返回节点保持对同一 registry 节点的共享引用，不递归复制每个 agent 的历史树，也不把 truth 当证据重新求解。

完整 RoundDesk.record 的 7,000 位参与者输出全部在 timer 内检查。独立完整校准组限值 0.10 秒，三次慢版 0.896–0.904 秒、三次快版 0.0054–0.0065 秒，双侧余量 8.96×/15.41×。六个测量副本仅把 elapsed 限值断言换成实际测量打印，慢版另换 diameter 实现，其余五关功能检查保留；原样计时断言由规定 checker 验证。这是本机数值服务检查，不是生产 SLA。

## 证据边界与证明限度

source main 实际将 live Agent 对象放入 others 后顺序更新，和 docs 的上一轮读取要求不同。完整 GIVEN snapshot 采用正文语义。source 的 agreement_score 是均值 tolerance 内比例，single_shot_majority 实际也是算术均值；这里固定为 numeric adapter，不宣称字面多数投票。rounds 按 source loop 表示初始作答之外的额外交换。

7,000 位参与者只构成纯数值诊断的完整输出压力 fixture，不是建议的真实 LLM agent 数量；没有逐行模型调用或 sleep。

source 只提供 scripted numeric dynamics；binary archive、CSV projection、Fraction 稳定合同和推导 DAG 都是为完整本地服务设计的显式适配。没有真实 LLM、联网、自然语言推理、质量提升或生产吞吐结论。60 分钟只是练习预算，尚无人类候选人计时校准。上述本机校准只验证完整指定路径；Python3.10 仅静态语法/API 兼容检查，实际解释器另记。

本机墙钟受运行环境影响。完整独占组慢版为 0.896–0.904 秒；两次普通 checker 的同一路径业务 timer 另观察到 5.246 秒与 1.752 秒，完整原始报告都保留，尚无证据说明差异的进程原因。约定校准门槛按整组六样本判断；测得余量不构成任意系统负载下的通用墙钟上界。
