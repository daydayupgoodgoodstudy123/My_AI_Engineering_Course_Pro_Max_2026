<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="skill-libraries-and-lifelong-learning-voyager"></a>

# 技能库与终身学习（Voyager）

> 旅行者(Wang等人,TMLR 2024)将可执行代码视为一种技能。 技能被命名、 可检索、 可配置和通过环境反馈加以完善。 这是用于此目的的参考结构 。 Claude Agent SDK 技能,技能, 和2026 技能图书馆模式。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 -07(MemGPT),阶段14 -08(莱塔区块)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 命名旅行者的三个组成部分——自动课程、技能图书馆、迭代促动和每个组成部分的作用。
- 解释为什么旅行者会编造动作空间代码,而不是原始指令。
- 建立一个具有注册、检索、组成和故障驱动改进功能的Stdrip技能库。
- 将旅行者的模式映射到2026年 Claude Agent SDK 技能和技能生态系统。

<a id="the-problem"></a>

## 问题

Agents 重建每一个能力 从零开始 在每一场会议做三件事错误:

1. **Waste tokens.** 每一项任务都重复了同样的推理。
2. **失去进步** A课学到的更正不会转移到B课
3. **长视距的成分失效** 复杂任务需要能力等级;一枪毙命 prompts 无法表达这些。

旅行者的答复:将每个可重复使用的能力作为存放在图书馆的代号,通过相似性检索,与其他技能一起合成,并通过执行反馈加以改进。

<a id="the-concept"></a>

## 概念

<a id="three-components"></a>

### 三个组成部分

旅行者(arXiv:2305.16291) agent around:

1. **自动课程。** 由好奇心驱动的求婚者根据 agent目前的技能组和环境状态。 探索是自下而上。
2. **技能库。** 每种技能都是可执行的代码。 当任务成功时, 将添加新的技能。 技能通过查询到描述相似性来获取 。
3. **循环促进机制。** 失败时 agent 接收执行错误、环境反馈和自我验证输出,然后改进技能。

矿工 evaluation (Wang等人,2024年):3.3x较独特的物品,8.5x较快的石器,6.4x较快的铁工具,2.3x较长的地图穿透与基线。数字是针对矿工的,但模式转移。

<a id="action-space--code"></a>

### 活动空间=代码

Most agents 原始命令。 旅行者发出 JavaScript 函数。 一种技能是:

```
async function craftIronPickaxe(bot) {
  await mineIron(bot, 3);
  await mineStick(bot, 2);
  await placeCraftingTable(bot);
  await craft(bot, 'iron_pickaxe');
}
```

由次技能构成,储存在描述和 embedding。作为一个程序检索,而不是一个 prompt.

这是2026年的 Claude Agent SDK 技能:一个命名的、可检索的代码块加说明 agent 随叫随到

<a id="skill-retrieval"></a>

### 技能回收

新的任务"制造钻石的摘轴。" Agent:

1. 包含任务描述。
2. 查询技能库,以获取最先进的类似技能。
3. Retrieves `craftIronPickaxe`, `mineDiamond`, `placeCraftingTable` 等
4. 将新技能从回收的原始 + 新逻辑中合成。

这就是模式 MCP 资源(第13阶段)和 Agent SDK 技能实施: 以当前任务为范围, 以知识/ 代码表面进行检索 。

<a id="iterative-refinement"></a>

### 迭代性精炼

旅行者反馈循环 :

1. Agent 写一个技能。
2. 技能是对环境的。
3. 三个信号中有一个返回: `success`, `error` (与堆叠 trace), `self-verification failure`.
4. Agent 将信号作为上下文重写技能 。
5. 绕到成功或最大回合

这是自定义(Lesson 05),用于有环境根据的核查的代码生成。 CRITIC (Lesson 05)与外部工具的格局相同。

<a id="curriculum-and-exploration"></a>

### 课程和探索

旅行者课程模块建议任务,例如“在湖边建造一个避难所”,依据是 agent 提议者利用环境状态+技能清单来挑选一项仅高于当前能力的任务——勘探甜点。

用于生产 agents 这可以转换为“ 缺少什么” 操作器: 鉴于当前技术库和域, 我们还没有覆盖什么技能? 团队通常会手工执行这个课程审查 。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **技术库烂了** 相同的技能增加了10倍,描述略有不同。在写作中添加重复;检索只返回一个。
- **混编的致命性漂移** 父母的技能取决于孩子的精细。 版本技能; 被钉在V1的家长不会神奇地接进 v3 。
- **检索质量 。** 矢量检索相对于技能描述会随着图书馆的成长而降低, 超过几百。 附加标签过滤器和硬性限制 (“ 只有技能才能被 `category=tooling`").

```figure
voyager-skills
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个标准技能库:

- `Skill` 名称、描述、代码(作为字符串)、版本、标记、依赖性。
- `SkillLibrary` 登记、查询(token 重合、拼凑(结构学类差)和精细化(版本加新)。
- 脚本 agent 记录三种原始技能, 构成第四, 打击失败, 并精细。

运行：

```
python3 code/main.py
```

该 trace 显示图书馆的写作、检索、组成、执行失败和 v2 改进-旅行者循环结束到结尾。

<a id="use-it"></a>

## 实际应用

- **Claude Agent SDK skills** (Anthropic2026年的参考:每种技能都有说明、编码和指示;在使用计算机时按需要装载。 agent session.
- **skillkit** (npm交叉的: 技能agent skill 管理32+AI coding agents.
- **自定义技能库** 具体领域(SQL 数据技能 agents下方的Terraform技能 agents旅行者模式向下缩放 。
- **OpenAI Agents SDK `tools`** ——在低端;每个工具都是轻量级技能。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-skill-library.md` 创建旅行者型技能库,在任何目标运行时间进行注册、检索、编译和精细调整。

<a id="exercises"></a>

## 练习

1. 添加一个依赖周期检测器到 `compose()`。如果技能 A 依赖B 取决于A? 错误与警告?
2. 执行按技能分列的版本插针。 当父母的技能构成孩子时 `crafting@1`,对 `crafting@2` 不得静默地提升父辈。
3. Replace token- 重复检索,加上句子...transformers embeddings (或一个 BM25 标准lib 灵巧。 测量检索@ 5 在50 级玩具库中 。
4. 添加“ 曲线” agent:鉴于目前的图书馆和域名描述,建议5种缺失的技能。每周调用它。
5. Read Anthropic的 Claude Agent SDK 将玩具库移植到 SDK技能计划,发现能力有什么变化?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Skill | “可再使用能力” | 命名代码+描述块, 可通过相似性检索 |
| 技能库 | "Agent memory 如何"的,我们 | 长期保存技能、可搜索和可作曲 |
| Curriculum | 问询者 | 由当前能力差距驱动的自下而上目标发电机 |
| 成分 | 杀DAG | 技能的运用;按执行方式进行统计分类 |
| 迭代性精炼 | "自我修正循环" | 信封反馈+错误+自我核查折叠回下一个版本 |
| Action-space-as-code | “方案行动” | 时间延伸行为时, 退出函数, 不是原始命令 |
| 写入时的死 | 死亡崩溃 | 几乎重复的描述崩溃为一种金刚技能 |

<a id="further-reading"></a>

## 进一步阅读

- [Wang等人,旅行者(arXiv:2305.16291)](https://arxiv.org/abs/2305.16291) 原始技能图书馆文件
- [Claude Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview) 技能作为2026年的成品
- [Anthropic大楼 agents 与 Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk) 技能及 subagents 实际中
- [Madaan等人,自备(arXiv:2303.17651)](https://arxiv.org/abs/2303.17651) 旅行者下面的精细循环
