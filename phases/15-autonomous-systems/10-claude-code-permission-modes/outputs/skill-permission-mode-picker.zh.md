---
name: permission-mode-picker
description: Match a Claude Code task to the correct permission mode, budget caps, and required isolation before starting a run.
version: 1.0.0
phase: 15
lesson: 10
tags: [claude-code, permission-modes, auto-mode, budgets, isolation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议 Claude 代码任务, 选择允许模式, 设定预算, 并指定在使用此选项前所需的最小隔离值 agent 允许开始。

显示 :

1. **任务简介** 一句话是关于任务做的 如果爆炸半径出错的话
2. **模式建议。** 其中一个: `plan`, `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`。请用一句话来说明爆炸半径。
3. **预算数字。** 具体数值 `max_turns`, `max_budget_usd`,以及任何工具箱。对于一个小时的无人看管运行,请指定一个等于或低于您为人类错误所付的美元上限,您不能倒车。
4. **隔离要求。** 文件系统范围( 仅项目目录、 抓取目录、 短容器) 。 网络策略( 无反射、 允许列表、 完整) 。 证书表面( 无, 范围) token,宽 token). 用于 `bypassPermissions` 或 `dontAsk`,运行必须位于一个没有安装生产证书的短暂容器内。
5. **轨迹审计计划。** 人类如何在运行后审查轨道? `auto`, `dontAsk`和任何超过30分钟的距离

艰难的拒绝 :
- `bypassPermissions` 相对于未经承诺的更改的存储处。
- `auto` 没有任何预算上限。
- 以上任何模式 `acceptEdits` 具有广泛的环境资格(澳大利亚、加拿大、智利、哥斯达黎加、捷克共和国、丹麦、芬兰、德国、意大利、意大利、立陶宛、挪威、波兰、葡萄牙、罗马尼亚、西班牙、瑞典、瑞士、瑞士、瑞士、瑞士、大不列颠及北爱尔兰联合王国、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士、瑞士。 GitHub 具有回收范围 PAT)。
- 无人看守的运行时间超过一小时,没有计划进行轨迹审计。
- 声称单靠自动模式分类就足以进行新的任务分配。

拒绝规则 :
- 如果用户无法给出故障的爆炸半径,则拒绝并要求在开始之前明确使用最坏的句子。
- 如果用户要求 `auto` 在一个工作空间内,生产数据库证书可达到,拒绝并要求范围证明或一个短暂的容器。
- 如果拟议的预算上限超过用户在运行不便时愿意失去的数额,则拒绝并需要较低的上限。

输出格式 :

返回一页运行卡,使用:
- **任务摘要** (一句话)
- **爆炸半径** (最坏的情况,一个判决)
- **Mode** (explicit)
- **Budgets** (`max_turns`, `max_budget_usd`,每个工具箱的上限)
- **Isolation** (fs 范围、网络政策、证书表面)
- **审计计划** (谁来回顾轨道,何时,对照什么标语)
