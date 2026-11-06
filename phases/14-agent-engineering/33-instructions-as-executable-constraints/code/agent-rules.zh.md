<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="agent-rules"></a>

# Agent Rules

<a id="startupstate-file-fresh"></a>

## startup/state-file-fresh
- 类别:启动
- 检查: 状态_file_fresh
Agent 必须读取代理_state.json 之前的任意 tool call.

<a id="forbiddenno-release-script-edits"></a>

## forbidden/no-release-script-edits
- 类别:禁止
- 选中: 无_release_script_edits
永远不要编辑脚本/ 释放. sh 。

<a id="donetests-pass"></a>

## done/tests-pass
- 类别:定义_的_done
- 检查: 测试_pass
任务只有在它被接受后, 才会完成 。

<a id="uncertaintyopen-question-note"></a>

## uncertainty/open-question-note
- 类别:不确定性
- 检查: 打开_question_当_unsure
当信心低于门槛值时,请写一个问题说明,而不是猜测。

<a id="approvalnew-dependency"></a>

## approval/new-dependency
- 类别:核准
- 选中: 新_dependency_approved
增加一个运行时间依赖性需要明确的人力认可。
