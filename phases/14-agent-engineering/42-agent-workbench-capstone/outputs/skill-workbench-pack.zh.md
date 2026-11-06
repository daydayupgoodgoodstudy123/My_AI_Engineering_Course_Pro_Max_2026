---
name: workbench-pack
description: Generate a project-tuned drop-in agent workbench pack — rules sharpened to the team's history, scope globs matched to the repo, rubric dimensions extended with one domain-specific entry.
version: 1.0.0
phase: 14
lesson: 42
tags: [capstone, workbench-pack, installer, schemas, drop-in]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以回购、团队事件记录和 agent 产品在其中运行, 发布调试 agent- 工作包和安装器

显示 :

1. `agent-workbench-pack/` 匹配语法布局的目录 : AGENTS. md, docs/, schemas/, 脚本/, bin/, README. md, VERSION。
2. 一个 `bin/install.sh` 拒绝撕裂一个现有的包 `--force` 并写 `.workbench-version` 进入目标回收站
3. 项目调制版本 `agent-rules.md` (根据小组过去六起事件,每类至少有一项规则), `reviewer-rubric.md` (有第六领域层面),以及 `scope_contract.schema.json` (与具体项目有关)
4. 一个 `lint_pack.py` 无法在脚本和图案之间或VERSION和图案之间漂移的脚本' `schema_version`.
5. 选择在演示时安装包的 CI 集成 branches 运行 verification gate 与一项已知的善行相对抗。

艰难的拒绝 :

- 一组包含特定项目任务的任务,任务在目标回收站的董事会上
- 连着一个卖家的包 SDK. 仅限框架不可知性; SDK 线路是目标重购的工作
- 用于变换状态文件的安装器。 安装器是一流的表面; 状态属于 agent 和人类
- 规则没有相应的检查功能。 愿望规则属于加入, 而不是在包中 。

拒绝规则 :

- 如果事件历史是空的, 拒绝发送调试器 `agent-rules.md`。使用金字塔默认值并显示空白。
- 如果目标重写光标的光标与安装不兼容( 否) `.github/workflows/`,不对应),拒绝选择的 CI 步数并记录手动路径。
- 如果团队使用私人叉子, 请拒绝写入公共安装器。 私人安装器携带私人的变数 。

产出结构:

```
agent-workbench-pack/
├── AGENTS.md
├── docs/
├── schemas/
├── scripts/
├── bin/install.sh
├── lint_pack.py
├── VERSION
└── README.md
```

结尾处指向“ 下一步要读什么” :

- 基准前后的第41课,本套课程有改进。
- 课程30(Eval-Driven) Agent 发展)的反val循环 消耗了全组的判断。
- [SkillKit](https://github.com/rohitg00/skillkit) 用于在32AI上分发包裹 agents.
