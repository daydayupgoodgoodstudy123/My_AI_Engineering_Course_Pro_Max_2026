<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="why-multi-agent"></a>

# 为什么需要多 Agent？

> One agent 撞墙,聪明的动作不是更大的 agent - 更难 agents.

**类型：**学习
**语言:** TypeScript
**先修要求:** 第14阶段(Agent Engineering)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 识别单agent 上限(文本溢出、混合专门知识、相继瓶颈),并解释何时分裂成多个 agents 是正确动作
- Compare orchestration 模式(管道、平行扇形出、上司、等级),并为特定任务结构选择右侧
- 设计一个多agent 具有明确作用界限、共同状态和通信合同的系统
- 分析多重交易的权衡agent 复杂度( 延迟、 成本、 调试难度) 相对于单agent simplicity

<a id="the-problem"></a>

## 问题

你造了一个单人 agent 。 它可以读取文件,运行命令,调用 APIs,并解释结果。然后你把它指向一个真正的代码库:200份文件,三种语言,测试取决于基础设施,以及研究外部的要求 APIs 写代码之前。

该 agent 窒息,不是因为 LLM 愚蠢,但因为任务超越了 agent loop 能够处理。 context window 填满文件内容。 agent 忘记了读过什么 tool calls 之前,它试图做一个研究人员,一个编码员, 一个同时进行审评的, 并且所有三个都做得不好。

这是单人...agent 最高天花板,每次任务需要时你都会撞到

- **上下文大于适合一个窗口的** - 读取50份文件 爆炸超过200k tokens
- **不同阶段的不同专门知识** - 研究需要不同于代码生成的提示
- **平行工作** - 为什么在可以同时阅读的时候, 连续阅读三个文件?

<a id="the-concept"></a>

## 概念

<a id="the-single-agent-ceiling"></a>

### 单人Agent Ceiling

单 agent 是一个循环,一个 context window,一个 system prompt。想象一下:

```
┌─────────────────────────────────────────┐
│            SINGLE AGENT                 │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │         Context Window            │  │
│  │                                   │  │
│  │  research notes                   │  │
│  │  + code files                     │  │
│  │  + test output                    │  │
│  │  + review feedback                │  │
│  │  + API docs                       │  │
│  │  + ...                            │  │
│  │                                   │  │
│  │  ██████████████████████ FULL ███  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  One system prompt tries to cover       │
│  research + coding + review + testing   │
│                                         │
│  Result: mediocre at everything         │
└─────────────────────────────────────────┘
```

三件事断了:

1. **Context saturation** - 工具结果堆积起来,30码 agent 已经消耗150公里 tokens 选择文件内容、命令输出和先前推理。 第5转弯的关键细节丢失 。

2. **角色混淆** - 一个 system prompt 上面写着"你是研究员, 代码员, 审校, 和测试员" agent 半研究,半代码, 从来没有完成审查。

3. **序列瓶颈** - 该 agent 读取文件A, 然后文件B, 然后文件C。 三串 LLM 三次连续处决工具,没有平行

<a id="the-multi-agent-solution"></a>

### 多重 - 共 -Agent Solution

分头工作,各给各 agent 一份工作,一份工作 context window,一个 system prompt 专为这份工作而调制

```
┌──────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│                                                          │
│  "Build a REST API for user management"                  │
│                                                          │
│         ┌──────────┬──────────┬──────────┐               │
│         │          │          │          │               │
│         ▼          ▼          ▼          ▼               │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│   │RESEARCHER│ │  CODER   │ │ REVIEWER │ │  TESTER  │  │
│   │          │ │          │ │          │ │          │  │
│   │ Reads    │ │ Writes   │ │ Checks   │ │ Runs     │  │
│   │ docs,    │ │ code     │ │ code     │ │ tests,   │  │
│   │ finds    │ │ based on │ │ quality, │ │ reports  │  │
│   │ patterns │ │ research │ │ finds    │ │ results  │  │
│   │          │ │ + spec   │ │ bugs     │ │          │  │
│   └─────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│         │           │            │             │         │
│         └───────────┴────────────┴─────────────┘         │
│                          │                               │
│                     Merge results                        │
└──────────────────────────────────────────────────────────┘
```

每个 agent 具有:
- 重点 system prompt ("你是个代码审查员,你唯一的工作就是找到错误")
- 自己的 context window（不被其他 agents 的工作内容污染）
- 明确的投入/产出合同(收到研究说明、产出代码)

<a id="real-systems-that-do-this"></a>

### 这样做的真正系统

**Claude Code subagents** - 当 Claude 代码产生 a subagent 与 `Task`,它创造出一个孩子 agent 使用范围任务。 父母保持其上下文的清晰度。 儿童的工作有重点, 并返回摘要 。

**Devin** - 经营一个计划者 agent,一个编码器 agent浏览器 agent。计划者将工作分成若干步。编码员写代码。浏览器研究文档。每个文件都有不同的上下文。

**Multi-agent 编码小组(SWE-Bench)** - SWE-Bench上最出色的系统使用一个阅读代码库的研究人员,一个设计修复的策划者,和一个执行它的编码器。单agent 系统得分较低

**ChatGPT 深层研究** - 产生多重搜索 agents 平行地,每个探索不同的角度,然后合成结果。

<a id="the-spectrum"></a>

### 光谱

Multi-agent 不是一个二进制的。 它是一个频谱 :

```
SIMPLE ──────────────────────────────────────────── COMPLEX

 Single        Sub-         Pipeline      Team         Swarm
 Agent         agents

 ┌───┐       ┌───┐        ┌───┐───┐    ┌───┐───┐    ┌─┐┌─┐┌─┐
 │ A │       │ A │        │ A │ B │    │ A │ B │    │ ││ ││ │
 └───┘       └─┬─┘        └───┘─┬─┘    └─┬─┘─┬─┘    └┬┘└┬┘└┬┘
               │                │        │   │       ┌┴──┴──┴┐
             ┌─┴─┐          ┌───┘───┐    │   │       │shared │
             │ a │          │ C │ D │  ┌─┴───┴─┐    │ state │
             └───┘          └───┘───┘  │  msg   │    └───────┘
                                       │  bus   │
 1 loop      Parent +      Stage by    │       │    N peers,
 1 context   child tasks   stage       └───────┘    emergent
                                       Explicit      behavior
                                       roles
```

**Single agent** - 一个循环,一个 prompt简单的任务很好

**Subagents** 父母为子任务生育子女,父母维持计划,孩子报告。这就是为什么。 Claude 代码是。

**Pipeline** - agents 依序运行。 Agent A的输出成为 Agent B 输入。 可用于分阶段工作流程: 研究 - > 代码 - > 审评 - > 测试 。

**Team** - agents 与共享信息总线平行运行。 每个都有一个角色。 一个管弦坐标。 当需要不同技能时, 使用良好的 。

**Swarm** - 许多相同或接近相同 agents 与共享状态。 没有固定的管弦乐队。 Agents 由队列接下工作, 用于高负荷平行任务 。

<a id="the-four-multi-agent-patterns"></a>

### 四人组合Agent Patterns

<a id="pattern-1-pipeline"></a>

#### 模式1:管道

```
Input ──▶ Agent A ──▶ Agent B ──▶ Agent C ──▶ Output
          (research)  (code)      (review)
```

每个 agent 将数据转换为数据,然后将其传到前面。简单到可以解释。在一个阶段中,失败会将数据 rest.

<a id="pattern-2-fan-out--fan-in"></a>

#### 模式2: 范式/范因

```
                ┌──▶ Agent A ──┐
                │              │
Input ──▶ Split ├──▶ Agent B ──├──▶ Merge ──▶ Output
                │              │
                └──▶ Agent C ──┘
```

将工作平行分割 agents,然后合并结果。对任务进行分解,成为独立的子任务有好处。

<a id="pattern-3-orchestrator-worker"></a>

#### 模式 3: 轮廓工

```
                    ┌──────────┐
                    │  Orch.   │
                    └──┬───┬───┘
                  task │   │ task
                 ┌─────┘   └─────┐
                 ▼               ▼
           ┌──────────┐   ┌──────────┐
           │ Worker A │   │ Worker B │
           └──────────┘   └──────────┘
```

聪明的管弦乐队决定做什么, 代表工人,并合成结果。 agent 配有产卵工的工具

<a id="pattern-4-peer-swarm"></a>

#### 模式 4: 对等点 Swarm

```
         ┌───┐ ◄──── msg ────▶ ┌───┐
         │ A │                  │ B │
         └─┬─┘                  └─┬─┘
           │                      │
      msg  │    ┌───────────┐     │ msg
           └───▶│  Shared   │◄────┘
                │  State    │
           ┌───▶│  / Queue  │◄────┐
           │    └───────────┘     │
      msg  │                      │ msg
         ┌─┴─┐                  ┌─┴─┐
         │ C │ ◄──── msg ────▶ │ D │
         └───┘                  └───┘
```

没有中央指挥员 Agents 将对等点对等点进行通信。 决策来自交互。 更难调试, 但向许多 agents.

<a id="when-not-to-use-multi-agent"></a>

### 当不使用多功能-Agent

Multi-agent 添加复杂。 agents 是一个潜在的失败点。调试从“ 读取一个对话框” 到“ 读取一个对话框 ”trace 五个对齐的信息 agents."

**保持单身agent 当:**
- 任务就在同一条 context window (在~100公里以下) tokens 工作数据)
- 你不需要不一样 system prompts 不同阶段的
- 序列处决足够快
- 任务很简单,分头行动会增加更多的管理费用

**复杂成本:**
- 每个 agent 边界是一个损失压缩步骤 : agent A的完整背景被总结成一个信息 agent B
- 协调逻辑(谁做什么,何时做,按什么顺序)是其自身的虫源
- 延迟增加: N agents 表示 N 序列 LLM 最少打一次,如果需要的话就多打一次
- 成本乘数:每 agent burns tokens independently

拇指规则:如果任务需要少于20个 tool calls 并装在100公里内 tokens单打独斗agent.

```figure
swarm-messages
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-the-overloaded-single-agent"></a>

### 步骤1: 超载单人 Agent

这儿有一张 agent 尝试做一切。 system prompt 和一个 context window 开展研究、编码和审查:

```typescript
type AgentResult = {
  content: string;
  tokensUsed: number;
  toolCalls: number;
};

async function singleAgentApproach(task: string): Promise<AgentResult> {
  const systemPrompt = `You are a full-stack developer. You must:
1. Research the requirements
2. Write the code
3. Review the code for bugs
4. Write tests
Do ALL of these in a single conversation.`;

  const contextWindow: string[] = [];
  let totalTokens = 0;
  let totalToolCalls = 0;

  const research = await fakeLLMCall(systemPrompt, `Research: ${task}`);
  contextWindow.push(research.output);
  totalTokens += research.tokens;
  totalToolCalls += research.calls;

  const code = await fakeLLMCall(
    systemPrompt,
    `Given this research:\n${contextWindow.join("\n")}\n\nNow write code for: ${task}`
  );
  contextWindow.push(code.output);
  totalTokens += code.tokens;
  totalToolCalls += code.calls;

  const review = await fakeLLMCall(
    systemPrompt,
    `Given all previous context:\n${contextWindow.join("\n")}\n\nReview the code.`
  );
  contextWindow.push(review.output);
  totalTokens += review.tokens;
  totalToolCalls += review.calls;

  return {
    content: contextWindow.join("\n---\n"),
    tokensUsed: totalTokens,
    toolCalls: totalToolCalls,
  };
}
```

这种办法的问题:
- 该 context window 每一个阶段都不断增长。在审查的阶段,它包含研究说明和代码以及先前的推理。
- 该 system prompt 通用。无法按每个阶段调整 。
- 没有什么平行运行。

<a id="step-2-specialist-agents"></a>

### 步骤2:专家 Agents

现在分了,每个 agent 获得一份工作:

```typescript
type SpecialistAgent = {
  name: string;
  systemPrompt: string;
  run: (input: string) => Promise<AgentResult>;
};

function createSpecialist(name: string, systemPrompt: string): SpecialistAgent {
  return {
    name,
    systemPrompt,
    run: async (input: string) => {
      const result = await fakeLLMCall(systemPrompt, input);
      return {
        content: result.output,
        tokensUsed: result.tokens,
        toolCalls: result.calls,
      };
    },
  };
}

const researcher = createSpecialist(
  "researcher",
  "You are a technical researcher. Read documentation, find patterns, and summarize findings. Output only the facts needed for implementation."
);

const coder = createSpecialist(
  "coder",
  "You are a senior TypeScript developer. Given requirements and research notes, write clean, tested code. Nothing else."
);

const reviewer = createSpecialist(
  "reviewer",
  "You are a code reviewer. Find bugs, security issues, and logic errors. Be specific. Cite line numbers."
);
```

每个专家都有重点 prompt。每个得到一个干净的 context window 只需要输入它所需要的信息

<a id="step-3-coordinate-through-messages"></a>

### 步骤3:通过信件协调

将专家与明确信息连接在一起:

```typescript
type AgentMessage = {
  from: string;
  to: string;
  content: string;
  timestamp: number;
};

async function multiAgentApproach(task: string): Promise<AgentResult> {
  const messages: AgentMessage[] = [];
  let totalTokens = 0;
  let totalToolCalls = 0;

  const researchResult = await researcher.run(task);
  messages.push({
    from: "researcher",
    to: "coder",
    content: researchResult.content,
    timestamp: Date.now(),
  });
  totalTokens += researchResult.tokensUsed;
  totalToolCalls += researchResult.toolCalls;

  const coderInput = messages
    .filter((m) => m.to === "coder")
    .map((m) => `[From ${m.from}]: ${m.content}`)
    .join("\n");

  const codeResult = await coder.run(coderInput);
  messages.push({
    from: "coder",
    to: "reviewer",
    content: codeResult.content,
    timestamp: Date.now(),
  });
  totalTokens += codeResult.tokensUsed;
  totalToolCalls += codeResult.toolCalls;

  const reviewerInput = messages
    .filter((m) => m.to === "reviewer")
    .map((m) => `[From ${m.from}]: ${m.content}`)
    .join("\n");

  const reviewResult = await reviewer.run(reviewerInput);
  messages.push({
    from: "reviewer",
    to: "orchestrator",
    content: reviewResult.content,
    timestamp: Date.now(),
  });
  totalTokens += reviewResult.tokensUsed;
  totalToolCalls += reviewResult.toolCalls;

  return {
    content: messages.map((m) => `[${m.from} -> ${m.to}]: ${m.content}`).join("\n\n"),
    tokensUsed: totalTokens,
    toolCalls: totalToolCalls,
  };
}
```

每个 agent 仅接收寄给它的信息。 没有上下文污染。 研究人员的50k tokens 文档阅读从不输入审查者的上下文。

<a id="step-4-compare"></a>

### 步骤4:比较

```typescript
async function compare() {
  const task = "Build a rate limiter middleware for an Express.js API";

  console.log("=== Single Agent ===");
  const single = await singleAgentApproach(task);
  console.log(`Tokens: ${single.tokensUsed}`);
  console.log(`Tool calls: ${single.toolCalls}`);

  console.log("\n=== Multi-Agent ===");
  const multi = await multiAgentApproach(task);
  console.log(`Tokens: ${multi.tokensUsed}`);
  console.log(`Tool calls: ${multi.toolCalls}`);
}
```

多重 - 数agent 版本使用更多总计 tokens (three agents,三个分开 LLM 电话),但每个 agent环境保持干净。 每个阶段的质量都会提高, 因为 system prompt 专门化的

<a id="use-it"></a>

## 实际应用

此课可产生可重复使用的内容 prompt 什么时候决定要多...agent。见 `outputs/prompt-multi-agent-decision.md`.

<a id="exercises"></a>

## 练习

1. 加上第四个专家:一个"泰斯特" agent 接收代码的代码,审查来自审查者的反馈,然后写测试
2. 修改管道, 使审评员能够将反馈反馈回编码器, 用于修改循环( 最大 2 发)
3. 将连续管道转换成扇形退出: 运行研究员和“ 需求分析器” agent 平行, 然后在传送到编码器前合并输出

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| Swarm | "艾丽丝的蜂巢之心" agents" | 一组对等点 agents 行为来自当地的互动。 |
| Orchestrator | 老板,我说 agent" | 一个 agent 其工具包括产卵和管理其他 agents. 它计划并代表,但可能不从事实际工作。 |
| Coordinator | "交通警察" | 一个非 -agent 组件(通常只是代码,而不是 LLM将信息传送到 agents 以规则为依据 |
| Consensus | "该 agents agree" | 协议中多个 agents 必须在进行之前达成协议。 当产出出现冲突时,需要解决。 |
| 新出现的行为 | "该 agents 自己想出来的 | 系统一级模式 agent 互动,但没有明确列入方案,可能有用或有害。 |
| 风扇/风扇 | 减量 agents" | 将任务平行分割 agents 将结果合并(fan-in)。 |
| 消息传递 | "Agents 彼此交谈" | 与《公约》第4条有关的 agents:从一个发送的结构化数据 agent 替换共享的 context windows. |

<a id="further-reading"></a>

## 进一步阅读

- [新兴大赦国际的风景 Agent Architectures](https://arxiv.org/abs/2409.02977) - 调查多 -agent patterns
- [自动Gen: 启用下一位 Gen LLM Applications](https://arxiv.org/abs/2308.08155) - 微软的多 -agent 对话框
- [Claude Code subagents documentation](https://docs.anthropic.com/en/docs/claude-code) - 或妓 Claude 带任务的代码代表
- [CrewAI documentation](https://docs.crewai.com/) - 以角色为基础的多功能-agent framework
