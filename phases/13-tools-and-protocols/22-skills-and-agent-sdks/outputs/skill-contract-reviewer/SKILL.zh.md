---
name: skill-contract-reviewer
description: Validate an Agent Skill package and choose the right instruction, capability, or lifecycle primitive before implementation.
license: MIT
metadata:
  lesson: "22"
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="skill-contract-reviewer"></a>

# 技术合同审查员

当工作流程即将成为可重复使用时使用此技能 agent artifact.

1. Set `SKILL_ROOT` 至包含此安装的绝对目录
   `SKILL.md`。不要假设进程工作目录是捆绑的。
2. Set `TARGET_ROOT` 键入绝对原始工作空间工作目录
   解决根下的推荐技能目录。
3. Read `$SKILL_ROOT/references/contract.md` 并验证便携式
   `SKILL.md` 身份字段。
4. Read `$SKILL_ROOT/references/decision-model.md` 和单独的仓库
   环境、可再使用的方法、外部能力、生命周期时间、
   确定性逻辑和孤立 delegation.
5. 执行前,显示精确解析的参数矢量。运行
   `python3 "$SKILL_ROOT/scripts/check_skill.py" "$TARGET_SKILL"`中,该选项
   `TARGET_SKILL` 绝对推荐技能目录
   `TARGET_ROOT`.
6. 检查 JSON 报表。在讨论主机特性之前先修正所有错误
   extensions.
7. 比较提议的文物
   `$SKILL_ROOT/assets/task-shapes.json` 返回最小的可作曲集
   原始的动物。

不要声称运行时间延长是便携式合同的一部分。 不要将有效技能视为运行脚本或访问工具的许可。

返回验证报告, 选定的原始人, 并有一个句子
解释每个选择。 包含执行证据并写入已解析脚本
路径、已解决的目标路径、 cwd、 精确的 argv 和退出代码。如果主机无法
暴露其中的一点, 标记它未经验证 而不是发明它。
