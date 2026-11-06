<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-16--github-issue-to-pr-autonomous-agent"></a>

# 综合项目 16：从 GitHub Issue 到 PR 的自主 Agent

> 标签问题,获得公关——2026年的自主产品形状 coding agents:运行 agent 云中 sandbox,核查测试通过,并发布备审的公关说明理由。 Agents光标背景 Agents, OpenAI 代码云,谷歌朱尔斯全部上船。硬部分正在自动复制Repo的建筑环境,防止证书泄漏,强制执行每个Repo的预算,并确保 agent 无法强制推进。 此综合项目构建了自托管版本, 并将其按成本和通过率与主机选项进行比较 。

**类型:** Capstone
**语言:** Python (agent), TypeScript (GitHub App), YAML (Actions)
**先修要求:** 第11阶段(LLM 工程,第13阶段(工具),第14阶段(agents15阶段(自治),17阶段(基础设施)
**实施阶段:** P11 P13 P14 P15 P17 国家妇女委员会
**时间:** 30小时

<a id="problem"></a>

## 问题

灰云 coding agent 是一个与互动不同的产品类别 coding agents 宇宙航空是 GitHub 标签。您将问题标为 `@agent fix this`工人在云中旋转 sandbox,克隆回购,运行测试,编辑文件,校验,并用 agent身体的原理。 没有交互式循环, 没有终端。 AWS 远程 SWE Agents光标背景 Agents, OpenAI 代码云,谷歌朱尔斯, 和工厂机器人都汇集在这一点上。

工程挑战具体表现在:环境再生产(环境再生产) agent 必须在没有缓存的 dev 图像的情况下从头开始创建回波 ) flaky tests (必须重新运行或隔离),资格界定(a) GitHub 使用最短的罚款许可,每天对每份回购实行预算强制执行,以及无力推进政策。 综合项目衡量通过率、成本和安全率与托管替代物的对比。

<a id="concept"></a>

## 概念

触发器是 GitHub Webhook (发行标签或 PR 注释) 。 调度员向 ECS Fargate 或 Lambda 发送文件。 工人将回购拖入 Daytona 或 E2B sandbox ,从回购(语言、框架)中推断出一个通用的 Docker 文件。The the agent 经营迷你丝丝agent 或瑞典妇女网agent v2 循环对着 Claude 行动4.7或 GPT-5.4-Codex 。 转录: 读出代码, 提议修正, 应用 patch做测试

验证是关键步骤, 全部的CI必须进入 sandbox 在公关打开之前。 计算覆盖 delta; 如果负超过阈值, 公关打开但标签 `needs-review`. 该 agent 将理由作为PR说明加上 `@agent` 线 审评员可以拨接后续。

安全范围通过两个不同的 GitHub 表面: App 提供短期安装 token 与 `workflows: read` 和狭窄的回收内容/回收范围; branch 保护( 而非应用程序许可) 强制执行“ 没有直接写到 `main`“和“不强制推进”——应用程序从未添加到绕行列表中。路径范围为只读访问 `.github/workflows` 不是真的,我以为 GitHub 原始应用,所以 agent文档编辑中的允许列表必须强制执行。 调度员对每天每份回购单的预算上限( 例如, 每天每份回购单最多5 个公元, 每份公元20 美元) 。

<a id="architecture"></a>

## 建筑

```
GitHub issue labeled `@agent fix` or PR comment
            |
            v
    GitHub App webhook -> AWS Lambda dispatcher
            |
            v
    ECS Fargate task (or GitHub Actions self-hosted runner)
       - pull repo
       - infer Dockerfile (language, package manager)
       - Daytona / E2B sandbox with target runtime
       - clone -> git worktree -> agent branch
            |
            v
    mini-swe-agent / SWE-agent v2 loop
       Claude Opus 4.7 or GPT-5.4-Codex
       tools: ripgrep, tree-sitter, read/edit, run_tests, git
            |
            v
    verify CI passes in-sandbox + coverage delta check
            |
            v (verified)
    git push + open PR via GitHub App
       PR body = rationale + diff summary + trace URL
       label: needs-review
            |
            v
    operator reviews; can @-mention agent for follow-ups
```

<a id="stack"></a>

## 堆栈

- Trigger: GitHub 添加精细加分 token; 通过 Lambda 或 Fly.io 接收网络钩的 。
- 工人:ECS远距任务(或 GitHub 自动操作运行者)
- Sandbox代顿纳河河道道具或E2B河道 sandbox 每项任务
- Agent loop迷你丝agent 基准或 SWE-agent v2 完毕 Claude 行动4.7 5 GPT-5.4-Codex
- 检索:树迹存储图+回转
- 核实:全线sandbox + 覆盖三角洲大门
- Observability:朗弗斯与每份PR trace 从 PR 机构链接的归档
- 预算:每日美元上限为每瑞普;每日最高官方汇率

```figure
cf-issue-to-pr
```

<a id="build-it"></a>

## 动手实现

1. **GitHub App.** 精细加固装置 token: 问题读取+ write, 拉_要求写入,内容读+write,工作流程读取。 Branch 保护( 唯一能做到这一点的表面) 强制“ 不直接推动 `main`“和“不强制推进”;应用程序不在绕行列表中。 工人执行“ 不写在下面” `.github/workflows`" 作为对拟议diff的允许清单的检查,因为 GitHub 应用程序权限不为路径范围 。

2. **韦伯克接收器** Lambda 函数接受发行标签/ PR 注释 Webhooks。 按标签过滤 `@agent fix this`。 SQS 的条目

3. **Dispatcher.** SQS 的任务执行。 执行每天的每个副本预算。 将 ECS 远距任务与 repo URL、 发行体和新代顿 连接起来 sandbox.

4. **Environment inference.** 检测语言(Python节点,去, Rust和包管理器(UV, pnpm,去模式,货物。如果不存在,则在苍蝇上生成一个多克文件。

5. **Agent loop.** mini-swe-agent 或瑞典妇女网agent v2 与 Claude 工具: 提取、树喷雾图,读取_文件, 编辑_文件,运行_tests, git硬限值:20美元,30分钟墙上,30小时 agent turns.

6. **Verification.** 循环结束后,运行整个测试套房sandbox。如果 CI: 停止, 不要打开公关。 如果覆盖面下降超过 2%: 打开公关 `needs-review` label.

7. **公关发布** 推开 agent branch. 通过 GitHub API 标题、理由、 diff 摘要, trace URL,成本,转弯。

8. **证物卫生** 工人跑步时时间短 GitHub 应用程序安装 token。在存档之前,对日志进行保密。

9. **Eval.** 30个有不同困难的种子内部问题。测量通过率、公关质量(大小、风格、覆盖面)、成本、潜伏度。与光标背景相比 Agents 远程 SWE 和 AWS 远程 SWE 系统 Agents 都问了同样的问题

<a id="use-it"></a>

## 实际应用

```
# on github.com
  - user labels issue #842 with `@agent fix this`
  - PR #1903 appears 14 minutes later
  - body:
    > Fixed NPE in widget.dedupe() caused by null comparator entry.
    > Added regression test widget_test.go::TestDedupeNullComparator.
    > Coverage delta: +0.12%
    > Turns: 7  Cost: $1.80  Trace: langfuse:...
    > Label: needs-review
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-issue-to-pr.md` 是交付品。 GitHub 将标签问题转化为备审公关,

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 30期的通过率 | 端到端成功(CI 绿色+覆盖范围确定) |
| 20 | 公共关系质量 | Diff 大小、 覆盖三角洲、 风格一致性 |
| 20 | 解决的每个问题的费用和延迟期 | 美元和墙上时钟每个公关 |
| 20 | 安全 | Scoped token,每个难民的预算,没有武力推进,有证书的卫生 |
| 15 | 运算符 UX | 理由评论,重试负担,@ mention 后续 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 添加“ 固定” flaky test" 模式:标签 `@agent stabilize-flake TestX` 测试50次sandbox 并提议一个最小的改变,稳定它。

2. 比较成本与光标背景 Agents 三个共享的问题。报告哪些工具赢得了哪里。

3. 实施预算仪表板:每天每份费用、每个用户费用。

4. 建立一个“干运行”模式,打开公关草案而不运行CI, 这样审查者就可以低廉地检查计划。

5. 增加保留政策: branches 超过7天且未合并的自动删除。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| GitHub App | "机体身份" | 应用精细的允许+短寿命安装 token |
| 灰云 agent | "Background agent" | 云中运行的非互动工人 sandbox,而不是终端 |
| Environment inference | "多克文件合成" | 检测语言+软件包管理器, 如果没有的话生成一个 docker 文件 |
| 验证 | "CI-in-sandbox" | 开公关前先在工人内部运行完整的测试套房 |
| 覆盖面 三角洲 | "保护服务" | 测试覆盖率变化(%) agent branch |
| 人均预算 | "天花板" | 调度员强制执行美元和公关计数上限 |
| 基本原理 | "身体解释" | Agent有关哪些变化和原因的概述;公关机构的要求 |

<a id="further-reading"></a>

## 进一步阅读

- [AWS 远程 SWE Agents](https://github.com/aws-samples/remote-swe-agents) 坎尼卡的灰云 agent reference
- [SWE-agent](https://github.com/SWE-agent/SWE-agent) - 国家牵头倡议参考
- [光标背景 Agents](https://docs.cursor.com/background-agent) 商业替代
- [OpenAI 代码( 云)](https://openai.com/codex) 东道竞争者
- [谷歌朱尔斯](https://jules.google) 谷歌主机版本
- [工厂机器人](https://www.factory.ai) ——其他商业参考资料
- [GitHub 应用程序文档](https://docs.github.com/en/apps) - 范围机器人身份
- [戴托纳云 sandboxes](https://daytona.io) 参考 sandbox
