<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---repo-memory-and-durable-state"></a>

# 任务 - 记忆和持久状态

<a id="goal"></a>

## 目标
Author JSON 方案表 `agent_state.json` 和 `task_board.json`,构建一个 `StateManager` 并证明两圈的圆轨

<a id="inputs"></a>

## 输入
- 课程32的三文件工作台形状
- 仅覆盖所需、类型、 enum、 模式和项目的 stdlib 验证符

<a id="deliverables"></a>

## Deliverables
- `agent_state.schema.json` 和 `task_board.schema.json` 代码旁边
- `StateManager.load`, `StateManager.update`, `StateManager.commit` 使用临时和改名写法
- 一次演示, 突变状态横跨两圈, 并重新装入干净

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 拒绝写错字( 缺少所需的字段, 错误的 enum) , 而不持续
- `workdir/agent_state.json` 运行后,验证 与计划

<a id="out-of-scope"></a>

## 超出范围
- SQLite 或外部存储后端。 本地文件是课程 。
- LangGraph 检查器,Letta内存区块。同样的想法,不同的存储器;超出范围。

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-state-schema.md` - 技术
