---
name: mcp-conformance-release-gate
description: Build an MCP conformance matrix and evidence-backed promote, hold, or rollback decision.
version: 1.0.0
phase: 13
lesson: 31
tags: [mcp, conformance, versioning, transcripts, proxy, operations]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 MCP 客户端,服务器,网关, SDK或运输变化,产生一个线级符合套房和释放决定,并附有经过编辑的证据。

<a id="required-inputs"></a>

## 所需投入

- 支持现代和遗留的协议版本以及每个部署目标的政策。
- 原始请求和回复抓取点 SDK decoding.
- Mirrored HTTP headers, JSON-RPC 体、状态、内容类型和中间型号。
- 广告客户端、服务器和扩展能力。
- SDK 名称、版本、正统值和例外。
- 健康阈值、金丝雀窗、最低样本数和基线测量。
- Exact rollback 版本、接收证据摘要、SHA-256工艺品和描述针、登记状况、当前健康状况、可信赖的释放签名人以及完整证明 rollback payload.
- 重新处理、保留和证据获取政策。

<a id="procedure"></a>

## Procedure

1. 定义明确的协议时代。 需要精确 `io.modelcontextprotocol/protocolVersion` 和 `io.modelcontextprotocol/clientCapabilities` 现代的键 branch将初始化时代的行为通过 `2025-11-25` 在一个单独的遗留适应器中。
2. 选择每个目标的严格或约束的后退策略。 成功 `server/discover` 或被识别的现代错误证明 branch。超时或空响应证明没有效果。允许只对已配置或允许列表的终点进行遗留探测,然后在验证正后选择遗留问题 `initialize` 后,将进行被定的遗产修改。 `-32020`, `-32021`, 或 `-32022`.
3. 为已接受的请求创建黄金记录、针对特定方法的有效结果、公布扩展结果、选定的遗留行为以及通知不答复的变数。
4. 为错误的封套、响应版本或ID错配、结果和错误排他性、错误错误、错误创建负记录 HTTP 映射、缺少元数据、信头和身体不匹配、服务器错误响应缺失、版本未支持、缺少现代 `resultType`、方法不当的有效载荷、未知或未公布的结果类型以及禁止的通知回复。 `HeaderMismatch`,要求和结构验证 HTTP 400 JSON-RPC `-32020` 自动回应 本地的例外不会通过
5. Validate JSON-RPC 先输入元数据类型。 HTTP 标题名称不敏感, 拒绝冲突重复, 解码准确的 Base64 哨兵为不安全 `Mcp-Name` 数值,然后比较 `MCP-Protocol-Version`, `Mcp-Method`,并适用 `Mcp-Name` 使用正文值来计算匹配值的支持。将前导或后行空白视为不安全,即使与正文值相等,在原样发送时也拒绝。
6. 接受已知的现代 `complete` 和 `input_required` 结果。 只有当扩展歧视者的能力被公布时,才接受该歧视者。 拒绝所有未知或未公告的 `resultType`。然后验证方法有效载荷,包括用于 `tools/list`,任务结果所需的生命周期字段,以及 `completion/complete`.
7. 保存原始添加结果 `_meta` 明确决定每个组成部分是否可忽略它们,或必须将其移到前方。
8. 运行每批装运的高风险记录 SDK。将原始铁丝语义与正常回报值进行比较,并报告每个合成、提升、拆卸或改变的字段。
9. 直接执行套件, 并通过每个生产中介机构执行。 抓取被篡改的反向、 来源和反向证据 。 检测状态崩溃 。 JSON-RPC 机构重写、 路径标题不匹配、 缓冲和内容谈判更改 。
10. 在序列化、散列、记录或上传前应用编辑。 大小写字段和页眉名称并删除分隔符, 以便进行 columCase、连字符、 突出显示和点缀变量共享拒绝列表, 然后删除证书, 例如 `Authorization`, `Set-Cookie`, `X-Api-Key`, `accessToken`, `clientSecret`, 和 `registrationAccessToken` 加上方法上特有的敏感参数。 Hash 编辑的证据包 。
11. 对照非空白的确定记录来评估候选人; SDK , 代理证据加上预先声明的健康窗口, 且该窗口的样本数为正最小值。 需要从每个源中获取有效的证据摘要。 省略的边界是失败的门, 不是传递的空列表 。
12. 验证准确的确认, 锁定, 活动, 健康 rollback 目标在升级前。验证准确的字段类型和 SHA-256 摘要,然后根据信任的发布控制器身份加密验证其证明。 只有在符合时才能进行升级, SDK、代理、健康 rollback候选人失败时,只能返回到被证实的目标,否则就坚持

<a id="required-matrix"></a>

## 所需矩阵

每一个案例都报告:

- 稳定大小写名称和规范变量
- 协议时代和选择证据
- 客户端、服务器 SDK、代理和构建版本
- 预期状态、 响应形状、 结果类型或错误代码
- 观察到的反向、来源和反向证据摘要
- SDK normalization differences
- 在每个边界处通过或失败
- 编辑政策版本
- 最后原因代码

这些案件至少包括:

- 金色现代发现或方法呼叫
- 带有添加字段的金色已知完整结果
- 金色遗产丢失 `resultType` 在选定的遗留时代
- 金色广告扩展结果
- 金色有效 `completion/complete` 结果
- 金色通知,无 JSON-RPC response
- 负页眉和体型不匹配
- 缺少负能力
- 负不支持匹配版本
- 缺少现代 `resultType`
- 未知或未广告的负数 `resultType`
- 负代理状态或体质转换
- 负 SDK 语义字段损失
- 负反形 `completion/complete` 结果

<a id="hard-rejects"></a>

## 艰难的拒绝

- 要求符合 SDK 返回值,没有原始线证。
- 一个默默接受现代和传统形态的解说家
- 传统在现代错误后退缩
- 遗产的倒退仅以超时、沉默、连接关闭或未经承认的反应为依据。
- 传递一个负请求的大小写, 而不捕捉和验证服务器的错误响应 。
- Making HTTP 400 JSON-RPC `-32020` 本地文件后可选择的 `HeaderMismatch` detection.
- 计算出失踪的完整 `resultType` 选择一个遗留时代之前
- 将未知歧视者视为完整的歧视者。
- 拒绝所有未知添加字段, 而不保留字段理由 。
- 发送任何 JSON-RPC 对通知的答复。
- 接受已知的 `resultType` 但不验证特定方法的有效载荷。
- 授权镜像头,而不检查与身体的平等。
- Treating HTTP 字段名称为区分大小写或比较编码 `Mcp-Name` 无需精确的哨兵解码
- 接受原始 `Mcp-Name` 使用引导或尾随的白色空间,而不是需要监控编码。
- 接受一个没有有效约束字符串值的完成对象的完成结果。
- 将代理程序生成的 500 视为源协议错误 。
- 写入文件的挂载器 tokens饼干 秘密 或敏感的论点 变成证据
- 使用编辑 normalization 使骆驼细胞或分离器变异 绕过卡门式的证书拒绝名单
- 宣布无样的金丝雀健康
- 处理空白的笔录, SDK,或代理证据作为跨越边界。
- 处理真实的字符串或未经认证的字符串 rollback 字典是经核实的证据
- 回到一个版本,没有准确的承认, 针,状态和健康证据。
- 培养生产候选人,然后证明健康 rollback target.

<a id="produce"></a>

## Produce

返回这些区域:

1. 时代政策:现代证据,严格的目标, 受约束的后退触发器, 和禁止降级信号。
2. 路径矩阵: 金色和负形的病例,预期有线结果。
3. 成果兼容性:核心歧视者、广告扩展、附加的外地政策和遗产 inference boundary.
4. SDK 差异:原始和正常的消化器加上提升、剥除、合成和改变的字段。
5. 代理证据: 反向、来源和反向结果 与精确的失败跳。
6. 编辑报告:政策版本,删除字段类别,以及编辑的证据摘要。
7. 健康窗口:样本、误差率、潜伏率、 saturation、期限、阈值和基准比较。
8. Rollback 证据:确切目标、入境摘要、插针、登记状况、健康状况、签字人身份、经核实的证明和路线修复计划。
9. Decision: `promote`, `hold`, 或 `rollback`,有稳定的理性代码和完整的证据摘要。

以第一个失效的边界结束。 如果所有边界都通过, 请说明允许全面升级的金丝雀完成条件 。
