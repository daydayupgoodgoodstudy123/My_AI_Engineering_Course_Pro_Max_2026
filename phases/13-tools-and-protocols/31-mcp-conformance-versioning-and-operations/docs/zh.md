<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-conformance-engineering-versioning-evidence-and-operations"></a>

# MCP 一致性工程：版本管理、证据与运维

> 服务器不兼容, 因为它的幸福路径通过一个 SDK. 遵守规定的情况存在于电线、版本边界、通过中介和在 rollback.

**类型：** 构建
**语言:** Python
**先修要求:** 阶段13 · 0 9(运输),阶段13 · 17(门路),阶段13 · 30(登记入册)
**时间:** ~ 100分钟

<a id="learning-objectives"></a>

## 学习目标

- 转而规范 MCP 规则变成金和负的电线记录
- 保持严格 `2026-07-28` 行为与被束缚的遗产后退分开。
- 区分未知添加字段与无效未知字段 `resultType`.
- 比较原始 JSON-RPC 证据 SDK- 正常的视野
- 证明头和身体的完整性 通过真正的代理边界。
- 配有编辑的笔录、健康及 rollback evidence.

<a id="the-problem"></a>

## 问题

你的客户打电话来 `tools/list` 通过 SDK 并获得工具。整合测试通过。

结果,一些重要问题没有得到答复:

- 请求是否包含现代的每个请求协议元数据?
- Did `MCP-Protocol-Version`, `Mcp-Method`, 和 `Mcp-Name` 匹配 JSON-RPC body?
- 回复是否包含有效的 `resultType` 或没有 SDK 合成一个?
- 客户会保留未来的添加字段吗?
- 被承认的现代错误会不会不小心触发遗产握手?
- 代理服务器是否保存了来源状态 。 JSON-RPC 错误?
- 连环报道员有没有发出禁止的答复?
- 行动能否证明为什么在不保存秘密的情况下,就推广或撤回释放?

合规性是一组可观察到的变量。 harness 就能捕捉那些不轨分子 然后再让生产量被发现

```figure
mcp-conformance-operations
```

<a id="start-with-version-eras"></a>

## 以版本 Eras 开始

MCP `2026-07-28` 使用自成一体的每个请求元数据。 `params._meta.io.modelcontextprotocol/protocolVersion` 和 `params._meta.io.modelcontextprotocol/clientCapabilities`。精确的命名间距键物质;光 `protocolVersion` 或 `clientCapabilities` 化名是错的。 当镜像路由信头出现在 HTTP 边界,他们的价值观必须符合 JSON-RPC 现代成功结果 `resultType`.

版本通过 `2025-11-25` 使用早期初始化时代。 `resultType` 只有在客户选择了早期时,才会被解释为完整。

不创建一个同时接受两个形状的允许验证符。 使用 2 branches:

| Branch | 入境证据 | Missing `resultType` | 初始化 |
|---|---|---|---|
| Modern | Successful `server/discover` 或公认的现代反应 | 无效 | 不是默认路径 |
| Legacy | 配置允许列表并添加有效遗产 `initialize` 后结果 | 口译为完整 | 时代要求的 |

分离防止了对不健全的现代同行的奖励,使其获得的验证力较弱。

<a id="strict-mode"></a>

### 严格模式

严格模式需要证明现代行为。 `server/discover` 证明现代 branch公认的现代 JSON-RPC 错误也证明了这一点。 校正请求或停止。 服务器返回后, 不再降级 `-32020`, `-32021`, 或 `-32022`.

<a id="fallback-mode"></a>

### 后退模式

后退模式运行一个连接的现代探测器。 超时、 空响应、 关闭连接或未确认的响应是没有结果的。 它不能证明对等点是遗留的。 只有明确配置或允许兼容的端点才能接收连接的遗留探测器, 而客户选择了遗留的 branch 只有在验证了探测器之后 `initialize` 成果和谈判后遗留问题的修订。

后退不是“ 在任何错误之后尝试遗留下来的 ” 。 被识别的现代错误包含有用的更正信息。 它可以隐藏页眉错配、 缺少能力声明或未支持的版本后进行下行 。

这使得攻击者、停机或过滤代理无法通过放弃现代反应迫使下调。 记录终点政策、无结果的现代观察、准确的正面遗留证据以及选择的时代。

记录每个抄本的选定时代。 没有这个事实, 一个缺失的字段可以在一次测试中被接受, 在另一次测试中无效 。

<a id="build-a-transcript-corpus"></a>

## 创建一个分页框

记录了跨越边界的 SDK call:

```json
{
  "name": "golden-modern-list",
  "era": "modern",
  "headers": {
    "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": "tools/list"
  },
  "request": {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  },
  "responseStatus": 200,
  "responseBody": {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
      "resultType": "complete",
      "tools": []
    }
  }
}
```

保留两类固定装置。

<a id="golden-transcripts"></a>

### 金本记录

金字典证明行为是可以接受的:

- 现代发现或方法请求, 与匹配元数据及信头
- 完整结果, 包含所需的字段
- `input_required` 当方法可以要求更多输入时结果
- 仅在相应能力公布后才产生扩展结果
- 遗迹结果 `resultType`,但仅在选定遗留时代
- 通知处理无 JSON-RPC response

金笔录是精确的, 不是很大。 保持波动的ID和时间戳在比较前确定或正常化 。

<a id="negative-transcripts"></a>

### 负记录誊本

拒绝行为:

- 页眉和体型不匹配
- 每项请求能力缺失
- 不支持匹配的协议版本
- 缺少现代 `resultType`
- 未知或未发布 `resultType`
- response `jsonrpc` 其它项目 `2.0` 或数值不同的代号,或 JSON 类型
- 包含两个答复 `result` 和 `error`,或两者
- 不带整数的错误 `code` 字符串 `message`
- 绘制错误的已知协议错误 HTTP status
- 通知中的答复
- malformed JSON-RPC envelope
- 协议错误的代理崩溃

对于每个负的, 请声明拒绝边界和稳定错误代码。 “ 调用失败” 过于薄弱 。 代理生成500 和源代码 `-32020` 两者都看起来像失败 却告诉操作员完全不同的故事

头像比对固定必须包含服务器的实际 HTTP 400 JSON-RPC 与匹配的请求 ID 和错误代码响应 `-32020`。每当当地验证人观察到,自动执行该命令 `HeaderMismatch`;不将响应核查作为可选固定标志。 HTTP 即便当地拒绝代码正确,500个尸体也没有故障。 harness 而不是服务器的电线行为

官方 MCP 符合性工程作为外部套件和版本的引用很有用。 也保留您的本地记录。 它们会捕捉您的代理, SDK,验证、扩展和释放路径,普通套件无法知道。

<a id="header-values-must-match-the-rpc-body"></a>

## 页眉值必须匹配 RPC 体

在现代流体中 HTTP,中间人可以使用镜像头选择或执行政策。 JSON-RPC 物体仍然是协议的真理来源。 错配是一个完整性失败, 不是选择一个值的提示 。

以此顺序验证 :

1. 分析并验证 JSON-RPC 信封和元数据类型。
2. Compare `MCP-Protocol-Version` 与 `params._meta.io.modelcontextprotocol/protocolVersion`.
3. Compare `Mcp-Method` 与 `method`.
4. 当方法有一个路径名称时, 请比较 `Mcp-Name` 与相应的体值。
5. 平等确立后,决定匹配版本和能力组是否得到支持。

此顺序区分不匹配 `-32020` 从不支持的版本 `-32022`。它也阻止了在源头执行不同体名时授权页眉名称的通道。

HTTP 字段名称不区分大小写,而其值则对大小写敏感。在查找前先将标题名称正常化,拒绝相互冲突的重复。对于不安全、非-ASCII,或引导或操纵的白色空间 `Mcp-Name`,解码 `=?base64?{Base64EncodedValue}?=` UTF-8 传感器, 然后再与身体比较。 拒绝不完整的监视器、 无效的 Base64、 无效的 UTF-8 或原始不安全值 `-32020`。即使身体含有相同的字符,但绕白空格转动无效,因为该值在运输前需要哨点编码。

中介人可以拒绝畸形 HTTP 请求送达 MCP 服务器,因此其失败可能是 HTTP 无错误 JSON-RPC。从中间人或来源获取拒绝。 MCP 服务器在处理有效时应该使用协议错误合同 JSON-RPC request.

<a id="unknown-fields-are-not-unknown-results"></a>

## 未知字段不是未知结果

向前兼容需要两种不同的规则。

<a id="additive-unknown-fields"></a>

### 添加未知字段

结果物体和 `_meta` 地图可以获取字段。 验证人应该根据其作用保存或忽略添加字段, 除非字段违反保留合同。 样本将全部原始结果保存为证据并接受 `futureHint` 和已知的结果。

如果您是一个透明的代理, 保存未知字段通常比剥除该字段更安全。 如果您是应用程序客户端, 忽略它也可以有效 。 您的差别测试仍然应该显示 SDK 省略了,所以行为是故意的

<a id="unknown-resulttype"></a>

### Unknown `resultType`

`resultType` 是一个歧视者。 `complete` 或 `input_required`。只有在能力被公布时,扩展才能添加另一个值。例如,任务扩展可以添加 `task` 以这种谈判能力为背景

未知或未公告的歧视者不能安全地被视为完整。 客户不知道它会丢弃的生命周期。 拒绝它 。

因此,同样的原始反应可能包含一个可接受的未知领域和一种不可接受的未知结果类型。

区分器只是第一层。 验证其后的方法特定有效载荷。 完整 `tools/list` 需要结果a `tools` 矩阵,其描述符具有独特的非空白名称、有用描述和对象根 `inputSchema` 数值。 A `task` 结果仅适用于符合条件的 `tools/call` 具备任务能力和需求 `taskId`,已知状态、创建和更新时间戳,以及 `ttlMs`,加上有效的可选投票间隔。 `completion/complete` 需要结果 `completion` 对象,其字符串值不大于100,可选的非负整数 `total` 与返回的值不小,且可选布尔值 `hasMore`拼写精准 `resultType` 无法使有效载荷符合错误。

<a id="the-notification-invariant"></a>

## 通知不动

一个 JSON-RPC 通知没有 `id`。接收者不得发送 JSON-RPC 成功或错误响应 。

被接受的 HTTP 通知形状, harness 期待一个 HTTP `202` 空着身体 MCP `2026-07-28` 定义没有用于流式的客户端对服务器的核心通知 HTTP。样本使用命名空间线扩展通知,仅用于测试单向序列器变异。不要将其作为新的核心方法。

测试序列器, 不仅仅是操作器。 操作器可以返回 `None` 中间软件包在 JSON 成功对象。捕获最后的偏移字节 。

<a id="add-an-sdk-differential"></a>

## 添加一个 SDK Differential

SDKs 通常将线性对象转换为方便的语言类型。 这很有用, 但一个普通的物体无法证明收到的东西 。

每一个高风险固定装置,捕捉:

1. 原始状态、信头和应对机构 SDK decoding.
2. SDK- 正常的回报值或例外 。
3. 所选时代的语义预测 。
4. 地块被抬起、合成、剥光或被 SDK.

样本允许 SDK- 仅删除已知的电汇簿,例如 `resultType`, `_meta`, `ttlMs`, 和 `cacheScope` 比较应用有效载荷时,报告一个投放 `futureHint` 因为未知的语义领域消失了

不要以为每一个区别都是 SDK 错误。 关键是要让转换为可见。 决定您的组件是应用端点, 可能忽略添加字段, 还是透明中介点, 从而保存它 。

运行差数对每个 SDK 并编译您 的船。 SDKs 解禁政策应该说哪一种行为可以接受,

<a id="capture-proxy-evidence"></a>

## 抓取代理证据

大部分生产 MCP 失败发生在一个以上的进程。 记录三个视图 :

| 查看 | 最低限度证据 |
|---|---|
| Ingress | 请求信头, JSON-RPC 物体、内容类型、验证路径、接收时间 |
| Origin | 转发信头和体文摘、来源状态、响应信头和体 |
| Egress | 客户端可见状态、 页眉、体型和发送时间 |

样本检测到两种常见的变异:

- 来源 HTTP 400或404个 JSON-RPC 错误变成通用代理服务器 500
- 向下移动 JSON-RPC 与原体不同

添加具体部署内容类型声明, `Accept`,压缩、请求范围 SSE、缓存信头和 trace 相关。 捕捉到 TLS 政策允许时终止。 绝不为了证明路径而登录证书 。

<a id="redact-before-evidence-leaves-memory"></a>

## 证据离开记忆前的重编

重新编造是符合操作的一部分, 而不是以后的清理工作。 在序列化、 散列、 日志、 测试文物或失败上传前应用它 。

样本的大小写将关键字翻倍, 在匹配前删除分隔符, 然后递归替换密钥下的值, 如 `Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key`, `accessToken`, `clientSecret`, `registrationAccessToken`, `token`, `password`, `secret`, 和 `api_key`。Canonicalization 和拒绝列表必须使用相同的格式,这样骆驼Case、连字符、加亮和点缀变异器无法绕过对方的政策。一个产品收藏家应该添加特定方法的参数政策,因为一个无害的键像 `query` 仍可包含个人或受管制的数据。

将修改的证据包混在一起。 只有在特定调查需要时, 才会在经过批准的短寿命系统中保留原始捕获。 一份摘要证明是哪个被修改的捆绑驱动了决定; 它不会显示删除的价值 。

<a id="make-health-and-rollback-part-of-the-gate"></a>

## 使健康和 Rollback 门的一部份

协议的一致是必要的,但不足以释放。 符合协议的候选人仍然可以超时、泄漏记忆或过重依赖。

定义之前的健康窗口 rollout:

- 最小样本数
- 最大错误率
- 最大潜伏百分位数
- saturation 资源限额
- 观察时间
- 与所接受基准的比较

Define rollback 证据 rollout too:

- 准确的先前版本
- 录取证据摘要
- SHA-256 工艺品和描述针
- 登记册现状
- 目前的健康结果
- 路线修复程序
- 由信任的发布控制器身份提供的关于这些精确字段的证明

要求 rollback 目标在晋升前得到核实和健康,而不只是在候选人失败后。 没有可用的恢复路径成功释放,无法生产。

如果候选人失败 rollback 目标缺乏证据,不要猜测交通。 “返回那里”不是操作控制。

不要降低对真实性检查的准备程度,例如非空白版本, `healthy: "yes"`,或任意的证据字符串。样本需要精确的类型、活动状态、三个SHA-256摘要、一个信任的签名人以及一份有效的 HMAC-SHA-256 完整证明 rollback 有效载荷。 它的确定性演示键是一个非秘密的固定键。 输入受保护的密钥, KMS 验证结果, 或者在生产中的释放边界上输入公用钥匙验证器 。

释放门也拒绝空的笔录 SDK 差异或代理证据。 每个源必须包含有效的证据摘要。 绿色健康窗口无法填充从未观察到的边界 。

<a id="build-it"></a>

## 动手实现

运行标准图书馆 harness:

```bash
cd phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations
python3 code/main.py
```

演示记录完全运行15个黄金和负记录,包括有效和错误的完成结果,将原始结果与 SDK 查看,检查一个解析源错误的代理文件,评估健康,验证 rollback 证据,选择目标。

预期形状 :

```json
{
  "transcriptsPassed": 15,
  "transcriptsTotal": 15,
  "sdkDroppedFields": ["futureHint"],
  "proxyIssues": [
    "proxy collapsed a protocol error into HTTP 500",
    "proxy changed the origin JSON-RPC body"
  ],
  "releaseAction": "rollback",
  "evidenceDigest": "..."
}
```

Read `code/main.py` 依此顺序:

1. `validate_request()` 执行特定时代的要求和头条规则。
2. `validate_result()` 将遗漏的遗漏歧视者、有效的现代价值观、扩展和未知价值观分开。
3. `select_era()` 执行严格和严格的后退政策。
4. `run_transcript()` 评估金和底的固定装置。
5. `compare_sdk_view()` exposes normalization differences.
6. `inspect_proxy()` 比较入侵、来源和离开的证据。
7. `redact()` 在证据散落之前 清除明显的秘密
8. `rollback_evidence_ready()` 验证准确的针字段和可信赖的释放证明。
9. `ReleaseGate.evaluate()` 与非空的顺从结合, SDK、代理、健康 rollback evidence.

<a id="use-it"></a>

## 实际应用

运行 harness ,在四点:

1. 每一个执行变化都配有流程中的测试适配器。
2. 对抗在实际运输上 建造的客户端和服务器二进制
3. 通过部署的代理或中转环境的网关。
4. 开金丝雀时 rollout 健康,并有生命力 rollback evidence.

保持相同的稳定大小写名称, 跨层 。 `negative-header-body-mismatch` 证据摘要会因边界变化而有所不同;要求不应该改变。

将固定图案存储到版本控制中。 存储在您的释放系统中的运行证据。 仅根据事故访问控制程序存储短寿命原始捕获 。

<a id="interactive-lab"></a>

## 交互式实验

<a id="lab-a-prove-the-era-boundary"></a>

### 实验室A:证明时代边界

来自 `code` 目录, 打开 Python:

```bash
cd phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/code
python3 -q
```

Run:

```python
from main import *
validate_result({"tools": []}, "legacy")
validate_result({"tools": []}, "modern")
```

遗产需要推断 `complete`现代呼唤 `ProtocolViolation`。现在测试后退:

```python
select_era({"kind": "timeout"}, "fallback")
select_era(
    {"kind": "timeout"},
    "fallback",
    legacy_allowed=True,
    legacy_evidence={"kind": "initialize_success", "protocolVersion": LEGACY_VERSION},
)
select_era({"kind": "jsonrpc_error", "code": -32021}, "fallback")
```

第一次超时失败, 因为沉默不是遗留证据。 第二次调用只因为配置允许而选择遗留问题, 并观察到有效的遗留启动结果。 被识别的缺失能力错误证明了现代 branch.

<a id="lab-b-additive-field-versus-discriminator"></a>

### B实验室:添加字段与歧视者

```python
validate_result({"resultType": "complete", "tools": [], "futureHint": True}, "modern")
validate_result({"resultType": "future_mode", "tools": []}, "modern")
```

第一次结果保存 `futureHint`。第二个被否决,因为生命周期歧视者身份不明。

<a id="lab-c-inspect-an-sdk-transformation"></a>

### 实验室C:检查 SDK transformation

```python
compare_sdk_view(
    {"resultType": "complete", "tools": [], "futureHint": {"mode": "new"}},
    {"tools": []},
)
```

决定您的组件是否忽略 `futureHint` 或必须将其转发。 将此选择写入发布策略。 不要默默地删除差异 。

<a id="lab-d-repair-the-proxy"></a>

### 实验室D: 修复代理服务器

修改演示交换, 使 Exgress 保存来源状态和身体。 运行 `python3 main.py` 代理问题应该消失,但 SDK 差分还是阻塞。 `futureHint` 在 SDK 查看并观察更改为 `promote` 等证据源都经过

<a id="practice-lab"></a>

## 练习实验

将请求范围 SSE 记录誊本添加到 harness.

Requirements:

- 抓取响应状态、 内容类型、 命令 SSE 事件和流终止 。
- 证明每个 JSON-RPC 中,该事件具有有效的特定时代结果或错误。
- 添加一个代理文件的负大小写, 以缓冲整个流, 然后转发 。
- 给 SSE 事件添加负实例, 该事件 JSON-RPC id 不同于请求。
- 重编事件数据后再写证据 。
- 包括流的长度、第一次活动时间和事件数。
- 释放门只选择一个证据 rollback 目标 当流线失败时 。

成功意味着同一个案例直接和通过代理运行, 并有一份报告, 确定确切的边界 改变行为。

<a id="shipped-artifact"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-conformance-release-gate.md`。使用它来转换服务器、客户端、网关或 SDK 转换成版本的符合矩阵和释放决定。 工艺品需要原始铁丝证据、负案例、明确的时代选择, SDK 差异、代理证明、编辑、健康阈值 rollback evidence.

<a id="verify-it"></a>

## 验证

运行演示和确定性套房:

```bash
cd phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

核查应证明:

- 每一个都包括黄金和负的笔录 达到预期的结果
- 现代请求需要准确的命名空间元数据键
- HTTP 标题名称不区分大小写,并编码 `Mcp-Name` 值被精确解码
- 信头和身体错配返回现代错配代码
- 响应版本、 ID、 结果或错误 排他性、 错误形状 HTTP 绘图得到验证
- 执行特定方法的工具清单、任务和完成有效载荷要求
- 观察到的每件 `HeaderMismatch` 需要实际 HTTP 400 JSON-RPC `-32020` response
- raw `Mcp-Name` 拒绝空白, 而精确的定点编码为空白的圆行
- 失踪 `resultType` 仅在选定遗留时代有效
- 添加字段在未知结果类型失败时通过原始验证
- 扩展结果类型需要其广告能力
- 已经确认的现代错误不会导致遗产的后退
- 通知无 JSON-RPC response
- SDK 记账清除和语义字段损失区分
- 检测到代理错误崩溃, 并按骆驼体和分隔器变量对证书进行递增
- 晋升需要非空白的成绩单, SDK、代理和健康操作证据
- 和 rollback 两者都需要经过鉴定的 固定的 活跃的 健康的 rollback target

<a id="production-failure-modes"></a>

## 生产失败模式

| Failure | 弱的测试报告 | 或 harness 必须证明 |
|---|---|---|
| SDK 合成一个缺失的导师 | “通过的工具/清单” | 原始现代结果缺乏 `resultType` 无效 |
| 客户在 `-32021` | “遗产重审工作” | 公认的现代错误禁止后退 |
| 未知结果类型被视为完整 | “答复解析” | 未公布生命周期歧视者被拒绝 |
| 代理授权一个工具, 源代码执行另一个工具 | “已拨打的请求服务器” | `Mcp-Name` 等于每跳一次时身体的路径名称 |
| Harness 读取服务器响应前丢弃 | “通过头人错配测试” | HTTP 和(续) JSON-RPC `-32020` 获取并验证反应 |
| 代理服务器将400个源头变成通用500个 | “上游错误” | 原产地和出境状况及 JSON-RPC 保存的物体 |
| 通知中间软件发射 `{result: null}` | “手拿手人没有归还任何” | 最终的向导为空, 没有 JSON-RPC 已有响应 |
| SDK 条形宽度 | “类型对象匹配” | 原始和正常视图显示精确的投放字段 |
| 失败的文物泄露给持证人 token | “调试包上传” | 在散列、 记录或上传前发生重编 |
| 认证密钥样式绕过编辑 | “拒绝名单载有_key” | 骆驼卡和分隔器变量共享一个卡门拒绝列表 |
| 加那利没有样本,但看起来健康 | “零差错” | 执行最小样本计数 |
| Rollback 选择未知的构造 | “恢复先前的部署” | 目标版本、入学摘要、插针、状态和健康都存在 |

<a id="operational-rule"></a>

## 操作规则

测试您发送的字节, 每一个中间线向前, 语义各 SDK 暴露,证据操作将在压力下使用。 branch. Rollback 是一个证据支持的释放动作。 也不应是允许解析器的意外副作用 。

<a id="further-reading"></a>

## 进一步阅读

- [MCP 2026-07-28 基本协议](https://modelcontextprotocol.io/specification/2026-07-28/basic)
- [MCP 版本谈判](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)
- [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [Official MCP 合规项目](https://github.com/modelcontextprotocol/conformance)
