---
name: skill-invocation-router
description: Design and test explicit human, implicit model or agent, programmatic application, bounded skill-composition, and harness activation policies for an Agent Skill catalog.
license: MIT
metadata:
  lesson: "25"
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="skill-invocation-router"></a>

# Skill invocation router

当主机需要可审计的激活政策而不是无区别的政策时, 使用此技能 `invocable` flag.

1. Read `references/invocation-model.md` 并分类请求的频道。
2. Review `assets/host-policy.json` 用作示例适配器配置,而不是便携式标准。
3. Run `python3 scripts/simulate_invocation.py --policy assets/host-policy.json --actor ACTOR --name NAME --description DESCRIPTION --query QUERY [--explicit-name NAME] [--caller-name NAME] [--depth N] [--user-invocable true|false] [--disable-model-invocation true|false]`.
4. 人,应用,技能,或 harness 请求, 要求确切的发现姓名及其频道特定许可列表 。
5. 技术来电者也需要有呼叫者身份、非循环目标以及交界的构成深度。
6. 用于模型或自主 agent 要求,删除候选人 actor 或确认的主机扩展名不合格。
7. 只分到其余描述。 在没有符合资格的候选人清除门槛值时, 选择最强的匹配或弃权 。
8. 回来 JSON 与适配器、频道、评分和政策理由一起决定。

激活会装入指令。 它不批准工具、 文件系统更改、 网络访问、 秘密使用或捆绑脚本 。
