---
name: mcp-contract-reviewer
description: Review MCP tool descriptors, results, pagination, completions, and parameter-header policy before exposing tools to a model.
version: 1.0.0
phase: 13
lesson: 28
tags: [mcp, tools, json-schema, pagination, completion, security]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


审查所提供的 MCP 工具表面对协议版本 `2026-07-28`.

如有这种信息,请询问:

1. 完整 `tools/list` 描述页,包括 `nextCursor` field.
2. 每个工具至少一个成功结果和一个失败结果。
3. 流传 HTTP parameter- 使用后,标头图
4. 完成推荐、呼叫者课程和示例建议。
5. 能够改变可见工具集的授权背景 。

与这些章节一起编写一份简要报告。

<a id="descriptor-admission"></a>

## 描述性录取

对于每个工具:

- 验证非空白稳定名称;
- 需要对象 `inputSchema`;
- 识别 JSON 方言,在省略时默认为2020-12;
- validate `outputSchema` 在场时;
- 将注释作为不信任的提示而不是政策列出;
- 返回 `ADMIT`, `REJECT`, 或 `CONDITIONAL` 只有一个确切的原因

拒绝一个错误的描述符, 不拒绝不相关的有效工具 。

<a id="result-contract"></a>

## 合同结果

包括一个 `isError: true`:

- 需要 `resultType: complete`;
- 每一内容块按类型进行验证;
- treat `structuredContent` 一样 JSON 值,不只指对象;
- 需要 `structuredContent` 遵守《公约》的情况 `outputSchema` 存在时;
- 要求结构化结果的相容文本块;
- 区分资源与嵌入资源的联系;
- 状态大小和媒体类型限制。

将错误的请求归类为 JSON-RPC 错误。 分类可执行
失败为完整结果 `isError: true`,不绕过
公布的产出合同。

<a id="parameter-headers"></a>

## Parameter headers

每一个 `x-mcp-header`:

- 需要有效、非空的 HTTP field-name token;
- 要求不区分案件的独特性;
- 需要字符串、整数或布尔类型;
- 穿行整个输入图,包括嵌套属性、组合器,
  矩阵项目,以及 `$ref`;
- 仅允许直接在 `inputSchema.properties` 成员及
  拒绝在其他地方或 `outputSchema`;
- reject `number` 和外的整数 `-9007199254740991` through
  `9007199254740991`;
- 拒绝证明, token、秘密、密码、授权和PII字段,按部署政策;
- 仅在非空值可见时才直接传输值 ASCII 并且确实
  开始不是 `=?base64?`;
- 否则就完全释放 `=?base64?{Base64UTF8}?=` 无需修剪或
  使原始值正常化;
- encode Unicode,空空空格,控制,CR或LF,加插,以及
  显示显示的字符串, 并制作布尔值为小写文字 ;
- 时间 HTTP 边界, 已识别解码 `Mcp-Param-*` 值,比较标题
  与 JSON 体,和
  拒绝丢失、复制、意外、格式错误或不匹配的副本为
  HTTP `400` plus JSON-RPC `-32020`;
- 记录最后的标题和拒绝类别,不记录参数值
  或编码有效载荷。

<a id="pagination"></a>

## Pagination

Trace 每一个列表请求。 继续 `nextCursor` 是一个存在且不中值的字符串,包括当它是空字符串时。从光标中不要解码、修改、加注、顺序或产生含义。报告工具重复、页面缺失和顺序不稳定。

<a id="completion"></a>

## Completion

每种 prompt 或资源参考 :

- 证明参考和论点;
- 通过打电话者的授权过滤建议;
- 将结果上限为100值;
- 定义客户端卸载和服务器 rate limits;
- 测试隐藏的租户、资源和环境名称不会泄漏。

<a id="verification-matrix"></a>

## 核查矩阵

至少还回这些支票:

| Check | Fixture | 预期结果 |
|------|---------|-----------------|
| Non-object structured output | 有效阵列, 标量, 或无符号 | 遵守时接受 |
| 输出不匹配 | Wrong JSON 类型或缺失的属性 | 在模型使用前被拒绝 |
| 输出错配出错 | `isError: true` 缺少或结构化内容无效 | 在模型使用前被拒绝 |
| 空光标 | `nextCursor: ""` | 后续请求发送精确的光标 |
| 不安全信头 | Token 无效字段名称 | 拒绝描述符 |
| 内嵌头条注释 | `oneOf`, `items`,嵌套对象,或 `$ref` definition | 全树入院时拒绝的描述符 |
| 编码信头值 | Unicode,新行、编织或显示显示的文字 | 精确的基数 64 UTF-8 哨兵圆形 |
| 整数页眉值 | 安全界限和超过每个界限的一个值 | 安全界通过; 拒绝使用不安全的价值观 |
| 标题和机体均等 | 案件变体、 缺少副本和解码错配 | 大小写变体传球; 丢失或错配返回 HTTP 和(续) JSON-RPC -32020 |
| 混合内容 | 文本、媒体、链接、嵌入资源 | 每个区块独立验证 |
| 完成隔离 | 低特权的来电者 | 未回复特惠建议 |
| 错位分层 | 未知的工具和业务失败 | JSON-RPC 错误和 `isError: true` 保持差异 |

仅包括成功证据时拒绝批准 tool call要求查找网页、接收决定和验证结果装置。
