<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-15--constitutional-safety-harness--red-team-range"></a>

# 综合项目 15：宪法式安全 Harness 与红队演练场

> Anthropic宪法分类, Meta's Llama 4号警卫,谷歌的盾牌Gemma-2号,NVIDIA的尼莫特罗3号内容安全,以及多语种覆盖的X-Guard 定义了2026年的安全分类堆。 evaluation 工具。 emo Guardrails v0.12 将它们连接到生产管道中。 这块石碑线将它全部连在一起: 一层层的安全性 harness 围绕目标应用程序, 一个自主的红色队 agent 运行6+攻击家庭, 和宪法的自我批评运行 产生一个可衡量的无损三角洲。

**类型:** Capstone
**语言:** Python (安全管道,红色团队) YAML (政策配置)
**先修要求:** 第10阶段(LLMs 11阶段(从零开始)LLM 工程,第13阶段(工具),第14阶段(agents),第18阶段(道德、安全、 alignment)
**实施阶段:** P10 P11 P13 P14 P18 国家妇女委员会
**时间:** 25小时

<a id="problem"></a>

## 问题

边界 LLM 安全性在2026年不是分类者是否起作用(他们是否起作用,大致上),而是如何在不引起过度反弹或留下明显漏洞的情况下,正确地围绕生产应用程序进行构思。 Llama 警卫4处理违反英语政策的行为。 X-Guard(132种语言)处理多种语文 jailbreak盾牌Gemma-2 捕获图像 prompt injectionNVIDIA 尼莫特龙3 内容安全涵盖企业类别。 Anthropic宪法分类法是培训期间采用的一种单独方法,而不是服务。

攻击进化也很重要。 PAIR 和 TAP 自动化 jailbreak 发现。 GG 运行 gradient- 后缀攻击,多转和代码开关攻击 agent memory部署的 LLM 需要红色小队——加拉克和PyRIT是导火索——加上有记录的缓解措施和CVSS的分类结果。

您将硬化目标应用程序( 要么是 8B 指令调控模型, 要么是 RAG 其它墓碑上的聊天机,运行6+攻击家庭,并制作无损前/后计量。

<a id="concept"></a>

## 概念

安全管道有五层 **输入净化**: 脱去零维字符,解码64/rot13, 正常化 Unicode. **政策层面**: 内莫 Guardrails v0.12 铁路(地外、毒性、PII提取)。 **分类器门**: Llama 4号警卫,输入,X号警卫 非英语,SheelGemma-2号警卫,图像输入 **模型**:目标 LLM. **输出过滤器**: Llama 4号警卫,请输入Presidio PII清洗,酌情执行引证。 **HITL 级**: 输出标记高风险, 转到黑队列 。

红队在排程器上运行。 PAIR 和 TAP 自动发现 jailbreaks。 GG 运行 gradient- 基地后缀攻击 ASCII / base64 / rod13 编码攻击。 多转式攻击( 人被收养、 记忆开发) 。 代码转换攻击( 与斯瓦希里语或泰语混合英语) 。 每运行一次都生成一个结构化的发现文件, 包含 CVSS 评分和披露时间轴 。

宪法的自我约束是训练时间的干预。 prompts, 给模型起草一个回应, 批评它反对成文宪法( 避免伤害规则) , 并重新培训批评循环。 在不懈的评审中测量前方/后方无损三角洲。

<a id="architecture"></a>

## 建筑

```
request (text / image / multilingual)
      |
      v
input sanitize (strip zero-width, decode, normalize)
      |
      v
NeMo Guardrails v0.12 rails (off-domain, policy)
      |
      v
classifier gate:
  Llama Guard 4 (English)
  X-Guard (multilingual, 132 langs)
  ShieldGemma-2 (image prompts)
  Nemotron 3 Content Safety (enterprise)
      |
      v (allowed)
target LLM
      |
      v
output filter: Llama Guard 4 + Presidio PII + citation check
      |
      v
HITL tier for flagged outputs

parallel:
  red-team scheduler
    -> garak (classic attacks)
    -> PyRIT (orchestrated red team)
    -> autonomous jailbreak agent (PAIR + TAP)
    -> GCG suffix attacks
    -> multilingual / code-switch
    -> multi-turn persona adoption

output: CVSS-scored findings + disclosure timeline + before/after harmlessness delta
```

<a id="stack"></a>

## 堆栈

- 安全分类器 : Llama 4号护卫舰,盾牌Gemma-2号,NVIDIA 尼莫特龙3号 内容安全,X-Guard
- Guardrail 框架: NeMo Guardrails 5年12月12日+《行动计划》
- 红队司机:Garak(荷兰),PyriT(微软阿祖尔),Nividia Aegis, 迅速式
- Jailbreak agents:PAIR(Chao等人,2023年),“塔克树”,GCG后缀
- 宪法培训: Anthropic- 风格的自我精选循环+ SFT 批评
- PII 擦拭: 普里西迪奥
- 目标:8B 调制导模型或另一块顶石 RAG chatbots

```figure
cf-safety-stack
```

<a id="build-it"></a>

## 动手实现

1. **设定目标** 立起8B 指令调制模型 vLLM (或再利用a) RAG 聊天室, 这是正在测试的应用程序 。

2. **安全管道包装** 围绕目标线条连接五层管道。 检查每个层可单独观测( 兰富斯 每层的平面) 。

3. **分类覆盖。** Load Llama 4号警卫(多语种),SheelGemma-2号(图像),每个都用一个小标签设置来设定基线。

4. **红队排程器** 平底笔,平底笔 agent, TAP , agent,一个 GG 跑者,一个多方向攻击者,和一个代码开关攻击者。每个跑步者都排队。

5. **攻击套房** 6个攻击家庭:(1) 帕伊尔自动 jailbreak(2) 技术咨询方案攻击树,(3) GCG gradient 后缀, (4) ASCII / base64 / rod13 编码,(5) 多方向人,(6) 多语言代码开关。报告每个家庭的成功率。

6. **宪法上的自我批评** 曲线 1k 有害企图 prompts目标对每个目标都起草答复。 critic LLM 拒绝非法要求。 Prompts 区域 critic 对象会被重新写; 目标微调在评论改进的对子上。 在搁置的电子逆向拍卖中, 测量是否无害。

7. **过度反悔测量** 跟踪良性值的错误阳性率 prompt 套房(例如,XSTest) 目标必须始终有助于处理良性的问题。

8. **中央车辆安全系统评分** 每一个成功者 jailbreak,CVSS 4.0(攻击矢量、复杂性、影响)得分。

9. **射程自动化。** 上面所有的东西都用拐角运行; 发现会写到队列上; 过度反弹回归会提醒 Slack 的火。

<a id="use-it"></a>

## 实际应用

```
$ safety probe --model=target --family=PAIR --budget=50
[attacker]   PAIR agent running on target
[attack]     attempt 1/50: disguise query as academic research ... blocked
[attack]     attempt 2/50: appeal to roleplay ... blocked
[attack]     attempt 3/50: chain-of-thought coax ... SUCCEEDED
[finding]    CVSS 4.8 medium: roleplay bypass on target
[range]      7 successes out of 50 (14% success rate)
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-safety-harness.md` 生产级的层安全管道,加上一个在无损三角洲前后可复制的红色星系范围。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 攻击地面覆盖 | 6+攻击家庭演习,2+语言 |
| 20 | 真实正/假正对折 | 攻击区块率与 XSTest 良性通过率 |
| 20 | 三角洲自律 | 推迟的反省之前/之后无害 |
| 20 | 文件和披露 | 具有时间表的中央自愿安保系统分类结果 |
| 15 | 自动和可重复性 | 所有的事物都带着警钟 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 运行 Garak 插件 prompt-注射注射 RAG 聊天机,比较攻击成功率 和没有输出过滤器层。

2. 加上第七个攻击家庭: indirect prompt injection 通过检索到的文件 测量所需的额外防御

3. 执行“ 使用帮助反省” 模式: 当 guardrail 区块,目标提供更安全的相关答案,而不是完全拒绝。

4. 多语言覆盖差距: 找到 X 保护器表现不佳的语言。 提议针对它进行微调数据集 。

5. 运行30B模型的宪法自我批评 并测量三角洲是否规模

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 层层安全 | "Defense in depth" | Multiple guardrails 输入、大门、输出、 HITL 时 |
| Llama 警卫4 | "梅塔的安全分类员" | 2026年参考输入/产出内容分类 |
| PAIR | "Jailbreak agent" | 纸张(赵等人) LLM-driven jailbreak discovery |
| TAP | "Tree-of-Attacks" | PAIR 树类搜索变量 |
| GCG | "格里迪坐标" gradient" | Gradient- 基于对抗后缀的攻击 |
| 宪法的自我约束 | "Anthropic- 训练风格" | 目标草稿 - > critic 分数 - > 重写 - > 重新培训 |
| XSTest | "本体探测器" | 过度反向回归的基准 |
| 中央志愿人员服务系统 4.0 | "分数" | 安全结论标准脆弱性评分 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic 宪法分类](https://www.anthropic.com/research/constitutional-classifiers) 培训-时间参考
- [Meta Llama 警卫4](https://www.llama.com/docs/model-cards-and-prompt-formats/llama-guard-4/) - 2026年输入/产出分类
- [谷歌盾牌Gemma-2](https://huggingface.co/google/shieldgemma-2b) 图像+多式联运安全
- [NVIDIA 尼莫特龙 3 内容安全](https://developer.nvidia.com/blog/building-nvidia-nemotron-3-agents-for-reasoning-multimodal-rag-voice-and-safety/) 企业参考资料
- [X-Guard(arXiv:2504.0848)](https://arxiv.org/abs/2504.08848) - 132种语文的安全
- [garak](https://github.com/NVIDIA/garak) - NVIDIA 红队工具包
- [PyRIT](https://github.com/Azure/PyRIT) - 微软红色团队框架
- [NeMo Guardrails v0.12](https://docs.nvidia.com/nemo-guardrails/) 铁路框架
- [计算机(ALXIV:2310.08419)](https://arxiv.org/abs/2310.08419) — jailbreak agent paper
