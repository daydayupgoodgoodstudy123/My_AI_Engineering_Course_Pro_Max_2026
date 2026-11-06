<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="agent-rules"></a>

# Agent Rules

<a id="startupstate-file-fresh"></a>

## startup/state-file-fresh
- 类别:启动
- 检查: 状态_file_fresh
Agent 必须读取代理_state.json 之前的任意 tool call.

<a id="forbiddenno-out-of-scope-writes"></a>

## forbidden/no-out-of-scope-writes
- 类别:禁止
- 选中: 无_out_的_scope_writes
永远不要编辑活动任务以外的文件 scope contract.

<a id="donetests-pass"></a>

## done/tests-pass
- 类别:定义_的_done
- 检查: 测试_pass
只有在每次接受命令为零时,才执行任务。

<a id="uncertaintyopen-question-note"></a>

## uncertainty/open-question-note
- 类别:不确定性
- 检查: 打开_question_当_unsure
当信心低于门槛值时,请打开一个问题说明,而不是猜测。

<a id="approvalnew-dependency"></a>

## approval/new-dependency
- 类别:核准
- 选中: 新_dependency_approved
增加一个运行时间依赖性需要明确的人力认可。
