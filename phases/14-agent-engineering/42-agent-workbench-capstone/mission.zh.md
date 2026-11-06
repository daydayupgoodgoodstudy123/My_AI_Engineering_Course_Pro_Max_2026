<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---capstone-ship-a-reusable-agent-workbench-pack"></a>

# 任务 - 顶石:船舶可重复使用 Agent 工作台包

<a id="goal"></a>

## 目标
将先前的11个课程合并为版本 `outputs/agent-workbench-pack/` 带有安装器的目录,该目录将自动设定为目标重写。

<a id="inputs"></a>

## 输入
- 课程32至40的课目、脚本和文件
- 包布局 : `AGENTS.md`, `docs/`, `schemas/`, `scripts/`, `bin/`, `README.md`, `VERSION`

<a id="deliverables"></a>

## Deliverables
- `outputs/agent-workbench-pack/` 与全部布局被覆盖
- `bin/install.sh` (或 `bin/install.py`拒绝覆盖 `--force`
- `VERSION` 文件加一个 `README.md` 描述什么是留在里面,什么是留在外面

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出零,打印包树
- 重新运行装配器是无能的
- `bin/install.sh` 进入一个新目标,留下一个工作台: 州,董事会,规则,范围,首饰,跑者,门,审查者, handoff 全部到位

<a id="out-of-scope"></a>

## 超出范围
- 每个项目的任务内容。任务属于目标回收站董事会,而不是包里。
- Vendor SDK 电话,包是框架的不可知性

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-workbench-pack.md` - 技术
