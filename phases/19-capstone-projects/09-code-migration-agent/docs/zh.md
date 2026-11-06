<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-09--code-migration-agent-repo-level-language--runtime-upgrade"></a>

# 综合项目 09：代码迁移 Agent——仓库级语言与运行时升级

> 亚马逊迁移区( Java 8 to 17) 和 Google 的 App 引擎 Py2-to- Py3 模拟器设置了 2026 条。 现代的 OpenRewrite 将自动重写进行比例化的确定性 AST 重写。 Grit 将同样的问题与编码式 DSL 相匹配。 生产模式将两者结合起来: 安全重写的确定性基底线加上一个 agent 用于模糊案件的一个层 sandbox 用于每 -branch 造物,和试验 harness 综合项目是迁移50个真正的回收品 并公布一个失败分类的通过率

**类型:** Capstone
**编程语言：** Python（agent）、Java / Python（迁移目标）、TypeScript（仪表盘）
**先修要求:** 第五阶段(无法律授权),第七阶段(transformers阶段11(LLM 工程,第13阶段(工具),第14阶段(agents15阶段(自治),17阶段(基础设施)
**实施阶段:** P5 P7 P11 P13 P14 P15 P17 国家妇女委员会
**时间:** 30小时

<a id="problem"></a>

## 问题

大规模代码迁移是2026年最清洁的生产应用之一 coding agents。 地面真相是显而易见的( 测试套件在迁移后通过吗? ) , 奖励是真实的( Java-8 船队迁移是一个人数规模的项目), 基准是公开的( 迁移Bench 50- repo子集 ) 。 现代的 OpenRewrite 处理决定性的一面。 agent 平面处理所有 OpenRewrite 配方无法处理的事物: 模糊重写、 构建系统漂移、 长尾语法、 过渡性依赖断裂 。

你会造一个 agent 需要 Java 8 号回购(或) Python 进行绿色CI迁移 branch。您将测量通过率、测试覆盖率保存、每次回收的成本,并建立一个故障分类。相对于一个确定性基线,单立的分级可以告诉你在哪里。 agent价值实际上就是生命

<a id="concept"></a>

## 概念

管道有两层 **确定基质** (爪哇的开放重写, Python安全操作大部分机械重写器:进口、方法签名、无安全编辑、试用资源、折旧 API 替换。 它快速, 并产生可审计的 diffs。 **agent layer** (OpenAI Agents SDK 或 LangGraph over Claude 行动4.7和 GPT-5.4-Codex处理配方无法处理的案件:建筑文件升级(Maven/Gill/Pyproject)、过渡依赖性冲突、测试片段、定制说明。

每一个回购都买一个代顿纳 sandbox 目标运行时间已预设。 agent 斜体:运行构建、分类失败、应用修正、重运行。 硬值限制: 每回购30分钟, 每回购8美元, 20 agent 如果所有测试都通过, 三角洲的覆盖不是负数, branch 如果不是, 退款会被提交到一个失败类别里

失败分类是可交付的。 在50个回复中, 什么坏了? 过渡性调试? 自定义注释? 创建工具版本? 测试与迁移无关的片段? 每个类都得到一个计数和一个示例。 未来的配方作者可以瞄准前三个。

<a id="architecture"></a>

## 建筑

```
target repo
      |
      v
OpenRewrite / libcst deterministic recipes
   (safe, fast, auditable, ~70-80% of fixes)
      |
      v
Daytona sandbox per branch
      |
      v
agent loop (Claude Opus 4.7 / GPT-5.4-Codex):
   - run build -> capture failures
   - classify failures (build, test, lint)
   - apply fix (patch or retry recipe)
   - rerun
   - budget: 30 min, $8, 20 turns
      |
      v
test + coverage delta gate
      |
      v (passed)
open PR
      |
      v (failed)
file under failure class + attach repro
```

<a id="stack"></a>

## 堆栈

- 确定基质: 打开重写 (Java) 或 libcst (libcst)Python)
- Agent: OpenAI Agents SDK 或 LangGraph over Claude 行动4.7+ GPT-5.4-Codex
- Sandbox代顿纳河沿岸地区 branch,预安装目标运行时间(Java 17/ Python 3.12)
- 建筑系统:马文、格拉德、乌弗(UV)Python)
- 基准:亚马逊移徙区50-repo子集(Java 8-17),谷歌App引擎Py2-to-Py3
- Test harness:平行跑者,通过Jacoco(Java)或覆盖。Python)
- Observability:朗弗斯+ trace 每个 diff 块的包包
- 显示板: 包含每类计数和示例 diffs 的失败分类仪表板

```figure
ce-migration-funnel
```

<a id="build-it"></a>

## 动手实现

1. **食谱通过。** 运行 OpenRewrite (Java) 或 libcst (libcst)Python先吃食谱,再吃70-80%的机械迁移 Commit 以“ recipe” 表示 commit.

2. **建立审判。** Daytona sandbox:安装目标运行时间,运行构建。如果为绿色,跳到测试中。如果为红色,请手拿下来 agent.

3. **Agent loop.** LangGraph 工具 : `run_build`, `read_file`, `edit_file`, `run_test`, `git_diff`. Agent 将失败分类( 调试、 测试、 构建工具) 并应用目标修正。 重运行 。

4. **预算上限。** 每份30分钟墙上时钟,8美元,20美元 agent 任何违反规定的行为都停止,档案列入预算_已经精疲力尽了

5. **测试+覆盖门。** 建设绿后, 运行测试套件。 比较覆盖范围与基础回波。 如果覆盖范围下降超过2%, 文件在“ 覆盖” 下_regression".

6. **公关打开** 成功的时候,推 branch,打开公关,提供切片和摘要,说明哪些配方适用,哪些 commits 该 agent authored.

7. **失败分类学。** 对于每个失败的回邮, 标记为类 : `dep_upgrade_required`, `build_tool_drift`, `custom_annotation`, `test_flake`, `syntax_edge_case`, `budget_exhausted`建立一个仪表板。

8. **50 -repo运行。** 执行整个移民通道子集。 报告每类通行率、成本-每类、覆盖-保护以及比较-Vs-确定性基准。

<a id="use-it"></a>

## 实际应用

```
$ migrate legacy-java-service --target java17
[recipe]   27 rewrites applied (JUnit 4->5, HashMap initializer, try-with-resources)
[build]    FAIL: cannot find symbol sun.misc.BASE64Encoder
[agent]    turn 1 classify: removed_jdk_api
[agent]    turn 2 apply: sun.misc.BASE64Encoder -> java.util.Base64
[build]    OK
[tests]    412/412 passing; coverage 84.1% -> 84.3%
[pr]       opened #1841  cost=$3.20  turns=4
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-migration-agent.md` 是一种可交付的。如果是回购,它会执行确定性配方,然后是 agent loop 以产生绿色迁移 branch,或将回购归档到分类学类。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 移徙津贴通过率 | 50- repo 子通行证@ 1 |
| 20 | 试验覆盖保护 | 平均覆盖率 三角洲对基 |
| 20 | 迁移的每个回购的费用 | 转折时的美元/再购 |
| 20 | Agent / 确定性工具整合 | 打开重写处理的修改小数 agent authored |
| 15 | 失败分析写入 | 具有示例的分类完整性 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 只使用 OpenRewrite 运行迁移管道( 无) agent)将通过率与整个输油管进行比较。 agent 单是区别

2. 执行“ 轻便清洁” 检查: 在迁移后, 运行样式 Iinter ( Java 无位数, ruff for Python)如果出现新的线性错误,则公关无效。

3. 添加“ 最小尺寸” optimizer: 在 agent的 branch 通过测试, 使用第二遍修剪不必要的更改。 报告 diff 大小 。

4. 扩大至第三批移民:第18节到22节,重新使用 sandbox 包扎; 将配方层转换为自定义编码器 。

5. 测量一至一绿色建设(TTFGB)作为UX测量标准。目标:10分钟以下,p50。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 确定性基质 | "回声引擎" | 打开重写/ libcst: 带有安全保障的宣示性 AST 重写 |
| Codemod | "改变代码程序" | 机械修改源代码的重写规则 |
| 构建漂移 | "工具版本扭曲" | 主要版本之间的细小拼图/拼图/缩略图行为变化 |
| 失败类 | 学桶 | 标签上的原因没有迁移: delp, 语法, 测试, 建筑工具, 预算 |
| 覆盖面 三角洲 | "保护服务" | 测试覆盖率变化(%) branch |
| Agent turn | "敲响警钟" | 一项计划 -- -- > 行动 -- -- > 观察周期 agent loop |
| 预算用尽 | 敲天花板,你别乱动 | 折叠币在30分/ 8分/ 20分的翻转时间里没经过 |

<a id="further-reading"></a>

## 进一步阅读

- [亚马逊移徙区](https://aws.amazon.com/blogs/devops/amazon-introduces-two-benchmark-datasets-for-evaluating-ai-agents-ability-on-code-migration/) - 2026年卡尼科尔基准
- [现代.io OpenRewrite 平台](https://www.moderne.io) 确定性基底参考
- [打开重写文档](https://docs.openrewrite.org) 食谱的作者
- [Grit.io](https://www.grit.io) - 备用代码 DSL
- [OpenAI 沙箱迁移烹饪手册](https://developers.openai.com/cookbook/examples/agents_sdk/sandboxed-code-migration/sandboxed_code_migration_agent) — 该 Agents SDK reference
- [Google App 引擎 Py2 呼叫 Py3 模拟器](https://cloud.google.com/appengine) 备选移徙基准
- [libcst](https://github.com/Instagram/LibCST) — Python 确定基质
- [Daytona sandboxes](https://daytona.io) 参考文件branch sandbox
