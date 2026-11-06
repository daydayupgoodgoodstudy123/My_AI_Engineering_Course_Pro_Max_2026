---
name: skill-function-calling-patterns
description: Decision framework for implementing function calling in production -- tool design, error handling, security, and provider patterns
version: 1.0.0
phase: 11
lesson: 09
tags: [function-calling, tool-use, agents, mcp, security, openai, anthropic]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="function-calling-patterns"></a>

# Function Calling Patterns

当建造 LLM 应用工具的应用程序,应用本决定框架。

<a id="when-to-use-function-calling"></a>

## 何时使用 function calling

**使用 function calling 当:**
- 该模型需要实时数据(天气、股票价格、数据库查询)
- 任务需要副作用( 发送邮件、 创建记录、 部署代码)
- 模式必须选择基于用户意图的多个动作
- 你在造一个 agent 与外部系统互动

**使用 structured outputs 改为:**
- 您需要从文本中提取数据( 不需要外部呼叫)
- 产出是最终产品,不是中间步骤
- 你有一个单一的策略, 没有多重工具可以选择

**使用两个时间 :**
- 模型调用工具, 然后将工具结果结构成特定输出格式

<a id="tool-design-guidelines"></a>

## 工具设计准则

1. **一个工具,一个动作。** 一个名为工具 `manage_database` 处理查询、插入、更新和删除的宽度过大。 `query_records`, `insert_record`, `update_record`。模型使用特定工具选择得更好。

2. **说明是 prompts.** 模型读取工具描述来决定选择。 写成它们时会像您为初级开发者写入指令一样。 包含工具返回的内容, 而不是它所做的 。

3. **和内脏的束缚** 如果为 parameter 具有 3- 10 有效值, 请使用 enum。 模型将生成字符串 - "celus", "Celsius", "C", "description" - 除非您加以约束 。

4. **少点工具更好** GPT-4o 处理5-10个工具的功能良好。在 20 个工具上,选择精度会下降。在 50 个工具上,预期10-15%的工具选择错误。 组合相关功能或使用路由层 。

5. **需要钱** 仅标记 parameter 如果工具没有它就无法运行,则需要。 parameters 默认值良好减少 tool call failures.

<a id="provider-specific-patterns"></a>

## 具体提供者模式

<a id="openai-gpt-4o-o3-gpt-4o-mini"></a>

### OpenAI (GPT-4o, o3, GPT-4o-mini)

```python
tools=[{"type": "function", "function": {"name": ..., "parameters": ...}}]
tool_choice="auto"       # model decides
tool_choice="required"   # must call at least one tool
tool_choice={"type": "function", "function": {"name": "specific_tool"}}
```

- 平行支持 tool calls (multiple `tool_calls` 答复)
- Tool call 身份证必须带回结果
- `gpt-4o-mini` 10x便宜,处理简单工具路由
- Structured outputs 模式使用工具 parameters 保证计划得到遵守

<a id="anthropic-claude-35-sonnet-claude-4-opus"></a>

### Anthropic (Claude 3.5 索纳特, Claude 4 行动)

```python
tools=[{"name": ..., "description": ..., "input_schema": ...}]
tool_choice={"type": "auto"}     # model decides
tool_choice={"type": "any"}      # must call at least one tool
tool_choice={"type": "tool", "name": "specific_tool"}
```

- Tool calls 显示为包含 `type: "tool_use"`
- 成果进入 user messages 与 `type: "tool_result"`
- 字段名称为 `input_schema`, 不 `parameters` (常见迁移错误)
- 支持多个 tool calls 答复

<a id="google-gemini-20-flash-gemini-20-pro"></a>

### 谷歌( 谷歌)Gemini 2.0 Flash, Gemini 2.0 Pro)

```python
function_declarations=[{"name": ..., "description": ..., "parameters": ...}]
function_calling_config={"mode": "AUTO"}   # or "ANY" or "NONE"
```

- 使用 `function_declarations` 上层
- 调查结果通过 `function_response` parts
- 平行支持 function calling

<a id="open-source-models-llama-3-hermes-qwen"></a>

### 开放源码模型(Llama 3号,赫尔墨斯 Qwen)

- 无标准格式 -- -- 模式和服务框架不同
- Hermes格式( NousResearch)是最常见的精细调整公约
- vLLM supports OpenAI-compatible tool calling 支持模型
- 奥拉马支援基本 tool calling 与兼容模型
- 生产前测试工具选择的准确性 -- -- 开放模型比 GPT- 伯克利街4号 Function Calling Leaderboard

<a id="error-handling-patterns"></a>

## 处理模式出错

<a id="return-structured-errors"></a>

### 返回结构错误

```json
{"error": true, "message": "City 'Toky' not found. Did you mean 'Tokyo'?", "code": "NOT_FOUND", "suggestions": ["Tokyo"]}
```

包含可操作信息。 “ 未找到” 不好 。 “ 未找到, 您指的是 X吗 ” 是好的。 模型使用错误信息进行自我校正 。

<a id="retry-strategy"></a>

### 重试策略

1. Tool call 失败时有可更正错误( tipo, 错误的 enum 值)
2. 将错误作为工具结果发送回模型
3. 模型调整和重试
4. 最大三条重试 tool call
5. 3个失败后, 将错误返回用户

<a id="timeout-handling"></a>

### 超时处理

设置所有工具执行的超时。 30秒是一个合理的默认值。 如果工具超时, 返回一个结构化超时错误, 这样模型可以通知用户而不是挂挂 。

<a id="security-checklist"></a>

## 安全检查清单

| Check | 为什么 | How |
|-------|-----|-----|
| 允许列表函数 | 防止任意处决代码 | 只登记用户需要的工具 |
| 校验参数类型 | 防止类型混乱攻击 | 执行前检查类型 |
| 保存字符串参数 | 预防注射 | 拒绝或排除特殊字符 |
| 参数化数据库查询 | Prevent SQL injection | 永远不要通过模型生成 SQL directly |
| 过滤工具结果 | Prevent data leakage | Remove API 密钥, PII, 内部错误 |
| Rate limit tool calls | 防止离家出走循环 | 每次谈话最多10-20个电话 |
| 全部登录 tool calls | 审计线索 | 存储工具名称、参数、结果、时间戳 |
| 屏蔽跨行路径 | 防止文件系统访问 | Reject `..` 文件工具中的绝对路径 |
| Sandbox 代码执行 | 防止系统访问 | 使用容器或限制内设 |
| 校验返回大小 | 防止上下文填充 | 超过10KB的运行结果 |

<a id="performance-optimization"></a>

## 业绩优化

- **平行通话 :** 当模型要求多个独立工具时, 与 `asyncio.gather()` 或 `concurrent.futures`
- **Caching:** 同一会话中相同参数的缓存工具结果(weather not change in 60 秒内没有变化)
- **Streaming:** 正在获取工具结果时流出模型的最终响应
- **工具补丁 :** 如果上下文很紧, 只包括与当前查询相关的工具定义( 使用分类器过滤)
- **较小型的路线模式 :** 使用 `gpt-4o-mini` 或 `claude-haiku-4-5` 将结果传递到更强大的合成模型

<a id="common-failure-patterns"></a>

## 常见故障模式

| Failure | 原因 | 修复 |
|---------|-------|-----|
| 选择错误的工具 | 模糊的描述 | 用特定的触发字重写描述 |
| 缺少所需的参数 | 模特儿忘了一个 parameter | 添加明确的例子 parameter descriptions |
| 无穷无尽的工具循环 | 模特儿一直叫同一个工具 | 设定最大迭代( 5- 10) 并检测重复调用 |
| 虚构的参数 | 模型发明了合理但错误的价值观 | 使用符号, 对照已知值验证 |
| 工具结果太大 | API 返回 100KB 数据 | 输入前补丁或摘要 |
| 模式忽略工具结果 | 结果格式混乱 | 干净的返回 JSON 具有清晰字段名称 |
