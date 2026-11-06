<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---the-minimal-agent-workbench"></a>

# 任务 - 最小 Agent Workbench

<a id="goal"></a>

## 目标
将三个文件的最低工作台(路线、州、任务板)设置为一个新的 `workdir/` 证明一个 agent 转弯可以读取状态,拉出任务,写到范围,并持续更新状态。

<a id="inputs"></a>

## 输入
- 空的 `workdir/` 课程代码旁边的目录
- 了解这三个文件: `AGENTS.md`, `agent_state.json`, `task_board.json`

<a id="deliverables"></a>

## Deliverables
- `code/main.py` 创建三个文件并运行一个转
- `workdir/AGENTS.md` 指向州、板和核查命令的短路由器
- `workdir/agent_state.json` 具有活动任务id, 被触动的文件, 下个动作
- `workdir/task_board.json` 积压和地位小的

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 第一次和第二次运行时退出零
- 第二道跑去接第一个左转的地方,不是从零开始
- 脚本打印的 Diff 显示被切换到的文件

<a id="out-of-scope"></a>

## 超出范围
- Scope contracts, verification gates, reviewer agents。在后期课程中,这些层在上面。
- 长长的单曲 `AGENTS.md`。路由器故意保持短促。

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-minimal-workbench.md` - 技术
