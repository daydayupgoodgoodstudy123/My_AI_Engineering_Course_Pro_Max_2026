---
name: skill-catalog-builder
description: Build a bounded Agent Skill catalog across explicit discovery scopes and report collisions before loading instruction bodies.
license: MIT
metadata:
  lesson: "24"
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="skill-catalog-builder"></a>

# Skill catalog builder

使用此项技能 agent 主机需要在一个以上的技能目录中进行确定性发现。

1. Read `references/discovery-contract.md`.
2. 审查主机政策范例 `assets/scope-policy.json`;不假定其秩序是普遍的。
3. Run `python3 scripts/build_catalog.py project=PATH user=PATH` 范围从最高到最低。
4. 检查 JSON `collisions` 和 `omitted` 激活一项技能之前的数组。
5. 只装入选中的 SKILL. md 体。 仅在该体命名时装入直接引用 。

在发现时, 永远不要执行捆绑的脚本。 永远不要选择以文件系统命令来重复相同的显示 。

返回目录预算、选定条目、碰撞分辨率和遗漏。
