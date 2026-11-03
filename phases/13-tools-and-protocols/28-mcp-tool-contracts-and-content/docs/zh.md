<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-tool-contracts-and-content"></a>

# MCP Tool Contracts 与内容

> 只有在发现、争论、结果、页码和运输元数据就一项合同达成一致时,工具才安全自动。

**类型:** Build
**语言:** Python
**先修要求:** 第13阶段,第07、09和10期
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 定义工具投入和产出 JSON 2020-12年计划。
- 核实结构化结果,而不假定其为 JSON objects.
- 在文本、图像、音频、资源链接和嵌入资源之间选择 。
- 拒绝不安全 `x-mcp-header` 工具到达模型之前的定义。
- Encode parameter-头目的值和校验准确的头对体对等。
- 绕过光标页, 不解释光标值 。
- 约束和授权 `completion/complete` suggestions.

<a id="the-problem"></a>

## 问题

调用 Python 功能很容易。通过 AI 主机呼叫远程能力是一个合同问题 。

服务器发布描述符。 客户端将描述符转换为模式上下文和用户界面。 模型创建参数。 网关可以从镜像头中选择请求路线。 服务器执行工具。 然后客户端决定结果是否安全且有效, 足以返回到模型 。

一条薄弱的边界腐蚀了整个链条。

考虑五个失败:

- 描述符说结果是一个对象,但服务器返回一个数组。
- 客户端停止页码 `nextCursor` 是一个空字符串。
- 一个 token parameter 被反射成 HTTP 头,并成为可见的中介。
- 一个 Unicode 路径值以原始页眉形式发送,然后网关和来源解释不同的字节。
- 完成点意味着一个无法进入的呼叫者有生产环境。

这些失败没有一个是通过更好的激励来弥补的,它们需要明确的协议和申请合同。

<a id="the-contract-pipeline"></a>

## 合同管道

每人一个 tool call 5个门

1. **Discover.** 读取确定性、 粘贴的工具列表 。
2. **Admit.** 验证每个描述符并适用当地安全政策。
3. **Invoke.** 校验参数并构建传输元数据 。
4. **Execute.** 运行处理器并正确分类失败 。
5. **Consume.** 验证内容区块和 structured output 模型使用前。

```figure
mcp-contract-pipeline
```

服务器不能强迫客户相信其注释、图案或输出。

<a id="json-schema-is-a-runtime-boundary"></a>

## JSON 方案是一个运行时间边界

在 MCP `2026-07-28`, `inputSchema` 和 `outputSchema` 使用 JSON 计划 `$schema` 默认方言为 2020-12。

输入图案必须是一个系统图案对象。 一个工具, 没有参数, 仍然应该说它接受什么 :

```json
{
  "type": "object",
  "additionalProperties": false
}
```

这比... `{ "type": "object" }`,该原则接受任意性财产。

输出模式是可选的。 一旦服务器发布, 每个完整的工具
结果 commits 返回符合 `structuredContent`包括结果
与 `isError: true`。错误标记对执行结果进行分类;它不
放弃已公布的输出合同。 客户应该验证结果
相信描述者。

<a id="structured-content-is-any-json-value"></a>

### 结构化内容为 JSON 值

不要硬码 `structuredContent` 以字典的形式出现。 它可以是:

- 物体;
- 数组;
- 字符串;
- a 数字;
- 布尔恩;
- `null`.

此工具返回一个数组 :

```json
{
  "name": "tag_catalog",
  "inputSchema": {
    "type": "object",
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "array",
    "items": {"type": "string"}
  }
}
```

其成功结果有效:

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "[\"contracts\", \"mcp\", \"stateless\"]"
    }
  ],
  "structuredContent": ["contracts", "mcp", "stateless"],
  "isError": false
}
```

为了兼容性,结构化结果还应包括序列 JSON 。文本不是验证源。 `structuredContent` 是.

<a id="a-small-validator-still-teaches-the-boundary"></a>

### 还有一个小验证师在教边界

课上用的是故意的 JSON 预设子集,因为它留在 Python 标准库。 它检查抽样工具所使用的机制 :

- 对象、数组、字符串、整数、数字、布尔和无符号类型;
- 所需属性;
- `additionalProperties: false`;
- 数组项目;
- 数值;
- 最小字符串长度。

这不是一个完整的生产验证符的替代。 重复使用的课程是验证发生的地方:在发现描述符之后,在执行论证之前,以及在消费结构结果之前。

<a id="content-blocks-carry-different-costs"></a>

## 内容块包含不同费用

该 `content` 矩阵可以合并若干内容类型。

| 类型 | 用来 | 主要边界 |
|------|------------|---------------|
| `text` | 人文和可读模型摘要 | 将文本作为不信任的输出处理 |
| `image` | 编码为基数64的视觉证据 | 校验媒体类型和大小 |
| `audio` | 以基数编码的口述或记录输出64 | 验证媒体类型和期限限制 |
| `resource_link` | 客户端稍后可获取 URI | 重新授权后一资源读取 |
| `resource` | 数据直接嵌入结果 | 强制实施有效载荷和内容限制 |

资源链接不能证明资源出现在 `resources/list`。它是此返回的参考文件 tool call。客户在遵循磁共振时仍然适用其资源政策。

嵌入资源可以避免再次往返, 但却会增加当前响应大小 。 使用链接来移动大型或独立文物 。 使用嵌入资源来生成小证据, 且必须随结果以原子方式运行 。

课上 `evidence_bundle` 后结果包括所有五个类型。客户在接受结果之前对每个区块进行验证。

<a id="x-mcp-header-is-routing-metadata"></a>

## `x-mcp-header` 正在运行元数据

里面的一块财产 `inputSchema` 声明 `x-mcp-header`循环 HTTP客户将这个论点反映到 `Mcp-Param-{name}`.

```json
{
  "region": {
    "type": "string",
    "x-mcp-header": "Region"
  }
}
```

与 `region: "eu-west"`运输工具可以发出:

```http
Mcp-Param-Region: eu-west
```

注释存在, 使负载平衡器、 网关或策略引擎可以不解析 JSON 这儿不是立证的地方

协议限制注解:

- 页眉名称并非空的, 并跟随 HTTP field-name token syntax;
- 标题名称不考虑案件,是独特的;
- 属性类型为字符串、整数或布尔;
- `number` 不允许;
- 只有在直接成员身上出现注释 `inputSchema.properties`;
- 整数留在内 `-9007199254740991` through `9007199254740991`.

位置规则是同步的,故障关闭。
不只是您验证人碰巧理解的属性。
嵌套对象下的注释 `properties`, 一个 `oneOf` branch, `items`, 一个
定义由 `$ref`,或任何输出图。
而不是将引用的节点变成直接的最高属性。

此课添加了部署政策: 拒绝反映名称的描述符, 如 `password`, `secret`, `token`, `api_key`, 或 `authorization`。正式规格建议服务器作者不要反射敏感 parameters。客户可以将建议变成硬性规定。

检查页眉名称, 而不是其价值。 样本代码记录 `Mcp-Param-Region` 保留 `eu-west` 退出审计活动

<a id="encode-values-before-building-http-headers"></a>

### 构建前编码值 HTTP headers

一个 parameter 值只有在非空字符串时才能作为纯文本移动
可见 ASCII 字符来自 `!` through `~` 和不相似
编码监控器。 其它所有东西都使用这个精确的表格 :

```text
=?base64?{Base64UTF8}?=
```

`Base64UTF8` 是标准的基数64 相对于准确的 UTF-8 字节。 不要修整,
普通化, 或者先替换值。 编码 Unicode,空字符串,空格,
选项卡、控制字符、 CR 或 LF、 引导或尾随空白以及任何
开始值 `=?base64?`。再次编码一个显示监控器的值
是什么让接收者回收了文字原文而不是解码
作为一种运输语法

布尔作为小写 `true` 或 `false`。
一定要留在里面 JavaScript 安全整数范围。
而不是由中间人来四舍五入。

<a id="the-server-checks-the-mirrored-copy"></a>

### 服务器检查镜像副本

头代只是客户的一半。 HTTP boundary,
服务器必须 :

1. 查找识别 `Mcp-Param-*` 名称,不考虑标题名;
2. 此时解码准确的基数64 哨兵形式;
3. 比较解码文本 JSON 确切的体力争论;
4. 拒绝缺失、重复、意外、错误或错配
   发送前确认页眉。

拒绝是 HTTP `400` 与 JSON-RPC 错误代码 `-32020`。
或其编码信头表属于审计记录。
仅识别标题名称和拒绝类别。

`code/main.py` 直接模拟此边界 。 [课程09](../../09-mcp-transports/docs/zh.md)
覆盖更大的流 HTTP 审定令,包括方法和
协议转换对等 。

<a id="pagination-cursors-are-opaque"></a>

## 粘贴标尺不透明

MCP 列表操作使用光标页码。服务器选择页面大小和光标格式。客户端得到一个决定:

```python
if result.get("nextCursor") is None:
    break
cursor = result["nextCursor"]
```

不要写这个 :

```python
if not result.get("nextCursor"):
    break
```

空字符串是一个有效的光标。 真相会过早停止 。

客户不能解码光标, 增加它, 比较它和先前的光标排序, 或者推断一个页码。 服务器可以签名光标, 将其绑定到目录版本, 或者将其映射到私人状态 。 这是服务器执行的细节 。

样本服务器故意返回 `""` 首页之后。 客户端必须在第二个请求中发送准确的值 。 trace 是:

```text
<first request with no cursor>
<second request with cursor "">
```

无效的光标生成 JSON-RPC 无效参数, 代码 `-32602`.

<a id="completion-is-an-authorization-surface"></a>

## 完成为授权表面

`completion/complete` 提供建议 prompt 参数和资源牌块参数。它对于交互式表格有用,但可以泄露普通列表方法保护的名称。

填写完成请求书时列出参考资料和正在完成的论据:

```json
{
  "method": "completion/complete",
  "params": {
    "ref": {
      "type": "ref/prompt",
      "name": "deployment_review"
    },
    "argument": {
      "name": "environment",
      "value": "st"
    }
  }
}
```

结果返回最多100个值, 并可能报告 `total` plus `hasMore`.

应用引用时所用的相同授权边界 prompt 样本中的分析员收到 `development` 和 `staging`。只有操作员才能接收 `production`.

完成生产还需要:

- 输入验证;
- 电话过滤器;
- 请求客户进行辩驳;
- 服务器的费率限制;
- 约束结果计数;
- 不暴露敏感建议值的日志 。

完成是帮助,不是发现绕道。

<a id="two-error-layers"></a>

## 两个错误图层

协议错误与工具执行错误分开。

使用 a JSON-RPC 错误 MCP 无法正确发送请求 :

- 未知的工具名称;
- 请求形状格式错误;
- 缺少请求元数据;
- 无效的光标 。

使用完整的工具结果 `isError: true` 当该工具的引用到达该工具,而该工具报告发生可操作的失败时:

- 无法提供报告来源;
- 日期不在所支持的范围之内;
- 商业规则拒绝要求的操作。

模型通常可以修复工具执行错误。 它们无法修复违反自身输出模式的服务器 。

如果工具声明输出模式, 则在其中模拟一个可操作的失败
样板 `route_report` 失败返回请求的区域
`accepted: false`,与可读人类错误文本并 `isError: true`.

<a id="build-it"></a>

## 动手实现

`code/main.py` 与两边的边界 Python 标准库。

服务器执行 :

- per-request MCP 元数据验证;
- `server/discover` 具备工具和完成能力;
- deterministic `tools/list` pagination;
- 4个工具描述符,包括必须拒绝的描述符;
- array structured output;
- 每一个当前工具内容块类型;
- a 可流动 HTTP 解码确认的对等门 parameter 页眉和
  返回 HTTP `400` plus JSON-RPC `-32020` 有关不匹配;
- 核准完成和费率限制。

客户执行:

- 说明性承认;
- full-tree `x-mcp-header` 安置鉴定和敏感实地政策;
- 完全可以看得见ASCII 或基数64 UTF-8 值编码;
- 沿着空字符串运行的不透明光标环;
- 论证和结果验证;
- 内容区块验证;
- 包含名称但不含数值的页眉审计事件。

故意不安全的描述符是教学数据。 它证明一个被拒绝的工具并不妨碍有效的工具装入。

<a id="use-it"></a>

## 实际应用

从仓库根 :

```bash
cd phases/13-tools-and-protocols/28-mcp-tool-contracts-and-content/code
python3 main.py
python3 -m unittest discover tests -v
```

试印上录用的工具 拒绝的描述符 两者都不同
请求、结构化数组内容、内容区块类型、镜像信头
名称,是否需要编码, HTTP 平等地位,以及
呼叫过滤完成值 。

<a id="interactive-lab"></a>

## 交互式实验

Open `code/main.py` 并定位 `TOOLS`.

1. Change `tag_catalog.outputSchema.type` 来自 `array` 以 `object`.
2. 运行演示。 客户端应拒绝返回的数组 。
3. 恢复原样
4. 保留第一页 `nextCursor` 作为 `""`,然后将最后一页
   `nextCursor: None` 而不是忽略字段。
5. 运行测试并比较光标 trace.
6. Add `x-mcp-header: "Authorization"` 字符串属性。
7. 确认声明书的承认,在援引前予以拒绝。
8. Try `region` 包含 Unicode,一条新线,周围的空间,
   字面文字 `=?base64?SGVsbG8=?=`。解码每个被排放页眉并证明
   原值完全活下来
9. 将注释移到下面 `oneOf`, `items`, 或一个 `$ref` 确认
   每一描述符即使被拒绝也不予接受 branch 演示从未使用过
10. 删除识别的页眉或更改其解码值。 HTTP
    边界返回状态 `400` 和 JSON-RPC code `-32020`.

关键不是背一个 JSON 形状。它就是看每个门在边界上失效。

<a id="practice-lab"></a>

## 练习实验

延长合同实验室 `search_evidence` tool.

Requirements:

1. 其输入模式接受 `query`, `limit`,和一个保险箱 `region` 路由场
2. 输出图是一组对象, `uri`, `title`, 和 `score`.
3. 结果包括兼容文本和每个项目的资源链接。
4. 参数拒绝未知属性 。
5. `limit` 受应用程序验证的约束。
6. 无法访问一个 URI 的呼叫者从不通过完成或工具输出看到 URI 。
7. 测试包括不相符的分数、无效的标题注释和两页列表。
8. 信头值测试覆盖可见 ASCII, Unicode,控制字符,
   白色空间, 显示监控文字, 以及两者 JavaScript-安全整形界限
9. 该 HTTP 固定选项接受不区分大小写的标题, 但拒绝丢失
   具有状态的确认值或不匹配值 `400` 和代码 `-32020`.

<a id="shipped-artifact"></a>

## 交付成果

`outputs/skill-mcp-contract-reviewer.md` 是一个平坦的、可重复使用的审查技能。 它会给它一个工具描述符、样本结果、 弹进行为和完成策略。 它会返回一个接收决定、 结果验证计划、 头条政策和具体失败测试 。

<a id="verify-it"></a>

## 验证

当这些说法属实时,这一教训就已经讲完了:

- `tools/list` 返回重复调用时的同一逻辑顺序。
- 客户在 `nextCursor` 是 `""`.
- 排除了不安全的敏感标题描述符,而其他工具仍然可用。
- 阵列通过阵列输出图案。
- 对象无法完成相同的矩阵图案 。
- 错误结果不能省略或违反已公布的输出模式。
- 文本、图像、音频、资源链接和嵌入的资源块验证 。
- 标题审计活动包含名称,没有价值。
- 可见 ASCII 保持平坦; Unicode,控制,加插,空的,
  以 tencils - lookel 值为圆形,通过精确的 base64 UTF-8 编码。
- 镜像整数 JavaScript 安全区域被拒绝 。
- 说明下 `oneOf`, `items`,嵌套对象, `$ref` 定义,或
  输入时拒绝输出图案。
- 仅在解码值时才通过不区分大小写识别信头的名称
  完全吻合尸体; 缺少或错配副本 HTTP `400`
  和 JSON-RPC `-32020`.
- 分析员完成后再也不会返回 `production`.
- 工具失败使用 `isError: true`; 错误的协议调用 JSON-RPC `error`.

<a id="production-failure-modes"></a>

## 生产失败模式

| Failure | 学者所见 | 正确回应 |
|---------|-----------------------|------------------|
| 客户假设对象输出 | 有效数组失败或被静默包扎 | 对照已公布的无对象类型模式校验 |
| 空光标被作为假处理 | 最后的页面消失 | 继续 `nextCursor` 存在和非无效 |
| 反射敏感值 | 秘密出现在代理,WAF,或 trace data | 拒绝描述符, 在受保护的请求数据中保留机密 |
| Raw Unicode 或镜像的空白 | 网关和来源不一致,否则价值正常化 | 使用精确的基数64 UTF-8 信使编码,并在解码后进行比较 |
| 隐藏在图案中的注解 branch | 客户在接收时丢失了路径元数据 | 绕过整个树图, 只允许直接顶层属性 |
| 大型整数反射 | JavaScript 中间绕行路线值 | 拒绝值 JavaScript 安全整数范围 |
| 头和身体不尽相同 | 通道路径一号, 目标一号, 目标一号 | 发送前拒绝 HTTP `400` 和 JSON-RPC `-32020` |
| 输出计划被忽略 | 下流代码消耗腐败的结构 | 在模型或应用程序使用前验证 |
| 自动信任的资源链接 | 呼叫者跟踪未经授权的 URI | 重新授权所有资源读取 |
| 完成共享全球建议 | 隐藏的租户名称泄漏 | 通过打电话、引用和授权过滤 |
| 工具说明作为政策处理 | 破坏性操作绕过确认 | 强制执行授权和核准(说明外) |
| 一个错误的工具断开发现 | 整个服务器无法使用 | 独立拒绝错误的描述并承认有效工具 |

<a id="capstone-connection"></a>

## 与综合项目的联系

阶段13的综合项目需要一个可以从多个服务器上整合工具的网关。 此课程提供了它的接收核心 。

用这件文物来分级四级 墓碑证据

- 确定性和彻底的被遗忘的发现;
- 模型暴露前的描述性验证;
- validated structured output 加上捆绑的内装物块;
- 完成并输入保存授权界限的元数据

不主张成功者对网关的兼容性 `tools/call` 单独。 抓取描述符, 页 trace,已接受的工具包,已拒绝的工具包,以及一个验证的结果。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| `inputSchema` | JSON 用于定义已接受的工具参数的 Schema 对象 |
| `outputSchema` | 可选 JSON 方案定义 `structuredContent` |
| `structuredContent` | 任意 JSON 工具结果产生的值 |
| 内容块 | 输入文本、图像、音频、资源链接或嵌入资源 |
| `x-mcp-header` | 将原始的争论反映为可流的示意图 HTTP metadata |
| 不透明光标 | 服务器发行的页码 token 客户端没有解释其价值 |
| 完成参考 | Prompt 正在完成参数的 URI/模板名称或资源 |
| Admission | 客户决定披露或拒绝已发现的描述符 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP Completion](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/completion)
- [MCP Pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination)
- [MCP Streamable HTTP Parameter Headers](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http#custom-headers-from-tool-parameters)
