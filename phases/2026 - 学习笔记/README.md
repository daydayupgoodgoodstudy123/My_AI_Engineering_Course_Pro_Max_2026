# 2026 学习笔记索引

学习 `phases/` 课程时提出的问题与解答。每条笔记都标注了提问所在的阶段、课程和章节，并链接回原文。

- Codex 新笔记按原课程顺序保存：`<阶段目录>/<课程目录>/<小节编号>-<主题>.md`。
- 小节编号按英文原文的标题顺序计算，例如第 3 个二级标题下第 7 个三级标题为 `03.07`。索引依次按阶段号、课号、小节编号排列，不按记录日期排列。
- 已有的 `<阶段目录>/L<课号>-<主题>.md` 保留原路径；同一小节的后续问答优先合并到已有笔记。
- **Codex 笔记整理**：使用 `$ultracourse-study-notes 整理本次课程对话，并更新笔记索引`，或直接说“使用 ultracourse-study-notes 整理本次对话”。用户级技能入口是 `~/.agents/skills/ultracourse-study-notes/SKILL.md`。
- **Codex 目录与测试指南**：使用 `$ultracourse-lesson-guide 13/02`，或附上课程路径，查看各文件夹的作用、作答位置、测试命令和学习顺序。默认只读介绍，不修改代码或执行测试。用户级技能入口是 `~/.agents/skills/ultracourse-lesson-guide/SKILL.md`。
- **Claude Code**：使用 `/study-notes`；原有技能仍在仓库根目录 `.claude/skills/study-notes/SKILL.md`。

Codex 笔记结构示例：

```text
13-tools-and-protocols/01-the-tool-interface/03.07-prompt-JSON与原生function-calling.md
13-tools-and-protocols/02-function-calling-deep-dive/03.01-共同结构.md
13-tools-and-protocols/02-function-calling-deep-dive/03.02-字段对照.md
```

示例只说明新笔记的命名规则；现有笔记见下表。

## 第 13 阶段：工具和协议

| 课程 | 小节序号与章节 | 问题 | 笔记 | 日期 |
|---|---|---|---|---|
| 01 工具接口：为什么 Agents 需要结构化输入输出 | 03.07 概念 › 为什么不直接通过 prompt 要求模型输出 JSON？ | ① prompt 要求 JSON 与原生 function calling 的区别（附例子）<br>② 原生 function calling 的格式可靠性是怎么训练出来的 | [L01-prompt-JSON-vs-原生function-calling.md](13-tools-and-protocols/L01-prompt-JSON-vs-原生function-calling.md) | 2026-10-12 |
| 22 Agent Skills：可移植契约与运行时边界 | 04.02 概念 › 相邻的抽象 | Prompt、仓库指令、Agent skill、MCP tool、Hook、Subagent、Plugin、习得技能库的区别（附中文版误译更正） | [L22-skill与相邻抽象的区别.md](13-tools-and-protocols/L22-skill与相邻抽象的区别.md) | 2026-10-12 |
