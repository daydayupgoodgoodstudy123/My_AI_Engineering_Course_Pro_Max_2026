# 参考实现讲解：SOPForge（16/08）

计时结束后再看。参考实现位于本目录的 `sopforge/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释实现合同，不把静态阅读写成已经运行通过。

## Part 1：结构审阅与完整确定性执行

第一个症状是正确 `callable_lookup` 的 `KeyError`。artifact 只有一个包含 `def add_two...return...` 的字符串 literal，substring critic 却批准了它。`VerificationDesk.inspect` 相信批准后调用 verifier，verifier 再交给 lookup；consumer 要的真实函数从未被定义。根因在 critic，不能修改正确 consumer 将不存在的函数补成默认值。

参考 critic 用 `ast.parse`，在 module body 里找名称等于 `spec.task_name` 的 `FunctionDef`，并检查其下是否有 `Return`。语法错误或缺少约定结构就返回不批准的报告，desk 因此不执行 verifier。这个有限结构合同不把 literal/comment 当函数，也不声称理解任意代码的语义。

verifier 为这次 verification 创建完整 GIVEN `ExecutionSession(artifact)`，调用正确 `compile_trusted_artifact` 得到包含 artifact key、source digest 和真实 code object 的 `CompiledArtifact`，再用 `callable_lookup(program, spec.task_name, session)` 绑定实际 callable。完整 session 校验 program 的来源 identity，只在首次 accept 时 exec 到独立 namespace。每个声明 case 都调用正确 GIVEN `run_case`，收集 passed、failure 或 error，最后统一构造报告。不能用硬编码 `add_two`，也不能首个成功就返回。

候选把 compile/bind 移到 case loop 外，去掉对同一不可变 source 的重复真实编译。once-exec 在两条路径都由完整 session 保证，不是本题第四层候选缺陷。计数函数的一组输出应连续为 1、2、3；第二次完整 inspect 用新 session，又从 1 开始。换 source 后重新创建 session，不能从旧 artifact 或旧 revision 继承 callable。

完整 loader 把实际 compile 或模块 exec 异常包装成 `TrustedLoadError`；正确 desk 只捕获这个类型，并返回 `executed=False`、`passed=False`、空 cases 与 `(error_type, error_message)` 的 `load_error`。这是正确 GIVEN 的次要集成护栏，不是第五个候选缺陷。正确 lookup 的 `KeyError` 不会被该 catch 吞掉，literal false approval 的根因仍自然暴露。

600-case fixture 的 artifact 包含实际 `TABLE` 和真实 callable，每一项都是一次声明调用。fixture 与独立 expected bundle 预先构造；timer 包含完整 `VerificationDesk.inspect` 和整个 bundle 的相等检查，因此原 source、critic/verifier、digest、全部 case 的 args/expected/got/kind 都在护栏内。本机独占完整三慢三快测得慢路径 0.903041 / 0.980894 / 1.125314 秒，参考路径 0.003861 / 0.003669 / 0.004244 秒；限值 0.08 秒，双侧余量为 11.288 / 18.848 倍。六份测量副本仅把 timing assert 换成 elapsed 输出，慢路径另恢复逐 case 的真实 compile/bind；全部功能护栏与另外四关均通过，不表示慢路径通过原限值。原样五测试参考实现已通过；业务 timer 与整个 pytest wall time 分开记录。不能改成固定正确、只跑样本或删输出。

原课 main 的 critic 确实使用 substring，可能被 literal/comment 骗过；原课 verifier 已经一次 `exec` 并遍历全部 tests。本题的硬编码 callable、提前成功和逐 case 重编译是服务化练习的显式教学回归；once-exec 始终由完整 GIVEN session 保证。P1 只处理完整 spec 的结构与执行，不包含 question/revision/resume。

## Part 2：完整 revision dossier

给定 SQLite 表的唯一键是 `(kind, entity, revision)`，候选负责领域布局。`save` 先用完整 `require_bundle_links` 校验 bundle，再在给定事务里清空旧 snapshot，按顺序写 specs，随后为每个 bundle 写 artifact、critic 和 verifier 三种独立行。两种报告可以作出不同判断，不能压缩成同一个 approval。

`load` 先恢复按声明顺序保存的 specs，用 `(spec_id, revision)` 建 spec lookup，用 `(kind, entity, revision)` 建 role lookup，再按 artifact 行顺序重组 bundle。artifact 自身的 `spec_id/spec_revision` 选择正确 spec，artifact 的 ID/revision 选择其独立 critic/verifier。这样同一个 artifact ID 的 revision 1 和 revision 0 可以按原 snapshot 的顺序同时存在，不会串证据。

完整 GIVEN `codec.py` 保存实际类型与值：int 用十进制文本，float 用 hex，tuple/list、dict、dataclass 和 UTF8 文本都有显式 tag。巨型 int、signed zero、嵌套 got/args、原代码和换行的断言验证正确使用这些依赖，不考重新设计精度编码。db helper 已负责建表、事务、物理行顺序和关闭；候选仍需传入完整领域记录并使用提供的校验。

保存的是当前完整 snapshot，尚未产出 artifact 的 planner spec 也按原顺序保留，不能先按 bundles 过滤。替换后的旧 artifact 不再出现。无效 source digest/report binding 被拒绝时，先前有效 snapshot 仍能读取。

## Part 3：问题义务、revision 与局部恢复

三个 TODO 处理不同转换，不能用一个“有字段就跑”的判断代替。

`required_field_questions` 从指定 step 的 `requires` 读取 missing required fields，为每个字段创建带 spec revision、step ID 和 owner 的 Question，并阻塞这个 target。完整 presence helper 区分“不存在”与显式 0；optional 字段不制造问题。其他 step 的 pending questions 与已有 artifacts/reports 保留。

`apply_clarification_answer` 先完整匹配 active question ID、spec ID、base revision、field 和 owner，并要求它确实对应当前 spec revision。只有匹配答案才能调用完整 `answered_revision` 创建下一版；helper 保留原字段并限制最多两次 clarification revisions。新 spec 进入 history；只清除 `requires` 包含已答字段的 step bundle/status，保留 run count，无关 slot 保持原对象。仍未解的 pending step 问题需要保留各自 owner，并按新 revision 重新生成，不能丢掉或留下旧 revision 的问题。

`resume_blocked_step` 在已有 blocked target 时只接受该 target，即使其他 step 已有完整结果，也拒绝恢复其他 step。要求仍缺失时只保留问题，不调用 executor。ready 且无可复用 bundle 时 executor 只执行一次，随后调用真实 `VerificationDesk.inspect`；critic approved、verifier executed 且 passed 才标 complete，否则 rejected。保留的完整 slot 不重复运行。恢复不是重跑全部 pipeline，也不能用 critic 的 notes 制造 deterministic pass。

Question/Answer、history、依赖字段、有限 revision 预算及 slot replay 是 communicative dehallucination 与 loop budget 概念的本地显式实现，原 demo 没有这些完整运行时对象。

## Part 4：真实 case 到 JUnit

`SOPProjection.case_entries` 只读完成的 verifier evidence；未执行 verifier 时返回空 entries。对每条 `VerifierReport.cases` 依次生成一个 `CaseEntry`，classname 是 `spec_id@revision:task_name`，这里使用 spec revision，独立的 artifact revision 不能替代它；name 是实际 `case_id`。

调用完整 `outcome_kind` 分类。passed 的 message/body 为空，正确 XML writer 不生成 failure/error 子节点；failure 的 message 由本 case 的 expected/got 组成，body 保留 args；error 的 message 保留本 case 的异常类型与原消息，body 同样保留本 case 自己的 args，不能复用第一个 case 的参数。`RuntimeError()` 的消息为空也仍是 error，这个判断已经由完整 classifier 给定。

`wire_support.py` 已完整实现 XML escaping、suite counts、async pull/publication 和关闭。候选职责是全部真实 cases、自己的诊断证据和正确身份，不是重写通用 XML、cadence、close 或空消息存在性判断。critic prose 不能替代任何 case 结果，projection 也不重新执行 artifact。

## Part 5：每层角色合同

完整 `SOPCatalog` 处理 full handle/path 身份、cycle/duplicate 检查、payload type 识别以及报告/artifact/spec 的 revision links。候选实现 `audit_sop`，依据 `ROLE_INPUTS` 和 `ROLE_OUTPUT` 检查每个 stage：

1. 每个 required input 必须存在，并来自规定 producer，具有规定 kind 与真实 typed payload。kind 和 payload 正确不能弥补错误 producer。
2. 输出 port、生产角色、kind 和实际 payload 一起符合本角色合同。把 critic 对象标成 artifact 不会使它成为 executor artifact。
3. 只把本层 `outputs` 中符合角色输出 port/producer/kind/payload 合同、且列在 `exposes` 的 port 写入 visible outputs；未知 exposes 产生 unproduced-export issue；exposes 为空则有效的本层输出也保持私有。
4. 按声明 child 顺序递归应用上述合同，保留每层完整 path、issues 和独立 visible outputs。

候选仍须调用完整 `payload_issues` 与 `stage_link_issues`，把给定 revision-link 校验结果加入本层 issues；link issues 与 typed visible-output 投影分别保留，不重新生成 payload。这是使用正确依赖的次要护栏；主要工作仍是 typed role ports、真实 producer/payload 和 declared exposes。这里不考短名作用域解析或通用 recursive ownership，也不重跑 verifier 来证明一个 kind 标签。

## 这套题证明了什么，没证明什么

当前原样五测试参考实现通过；独立 source-first fresh 的 7 个有效 core 方向初抓 1、漏抓 6，最终均为目标关失败且其他四关通过，全部 matching reference 五关通过。27 项登记错修与默认锁、starter、分层修复、reset 已由规定原 TEMP `--write` 检查器全部通过。

若候选实现通过全部原样测试，证据仅支持：在声明的本地可信 fixture 上，能修复分层角色验证、保存 revision-bound dossier、按 owner 澄清并局部恢复、投影真实 case evidence，以及审计 nested SOP 的 typed role 边界。原样五测试参考实现与本机完整三慢三快校准已通过，0.08 秒限值的双侧实测余量为 11.288 / 18.848 倍。测量副本只把限值断言换成 elapsed 输出，慢路径保留全部功能护栏；这不表示慢路径通过原限值。完整数据、代码与输出在各自证据副本中，结果受本机运行环境影响，不构成通用墙钟上界或生产 SLA。

本题的 `exec` 没有隔离、超时或内存限制，不能执行不可信输入。有限 cases 不能证明任意程序正确，也不能消除 test leakage、过拟合或一般 verifier 覆盖不足。结构 critic 不是实际 LLM，确定性 verifier 也只覆盖声明用例。

SQLite snapshot、Question IDs、revision tags、SOP tree 和 JUnit 都是角色分工、明确 I/O schema、提问与验证概念的本地扩展，不声称原课程已有完整服务运行时。没有执行原课程脚本、调用真实模型、联网或核验课程引用的外部统计。60 分钟与关卡分配尚未经过真人计时校准；任何本地性能测量都需要另记完整路径、环境和实际结果，不能变成生产 SLA。
