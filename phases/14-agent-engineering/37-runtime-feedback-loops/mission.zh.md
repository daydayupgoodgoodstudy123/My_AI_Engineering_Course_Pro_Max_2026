<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---runtime-feedback-loops"></a>

# 任务 - 运行时反馈循环

<a id="goal"></a>

## 目标
Build `run_with_feedback` 环绕 `subprocess.run`,捕捉 stdout、 stderr、退出代码和持续时间,以确定的方式截断输出,并附加 JSONL 记录下一个转弯和 verification gate 都读过

<a id="inputs"></a>

## 输入
- 三个演示命令来练习跑者:一个成功,一个失败,一个缓慢
- Token budget:确定性头部加上尾巴 `...truncated N lines...` marker

<a id="deliverables"></a>

## Deliverables
- `run_with_feedback(command, agent_note)` 写入 `feedback_record.jsonl`
- 一种流出 JSONL 变成 Python list
- 显示每个命令最后记录的打印机

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- `feedback_record.jsonl` 重新运行时每个命令积累一个记录
- 命令 `exit_code: null` 无法通过循环标记成功

<a id="out-of-scope"></a>

## 超出范围
- 遥测管道( OTel, Langfuse) 。 反馈为下一转; 遥测为操作员 。
- 编辑通行证和轮换策略。 prompts 盖上那些

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-feedback-runner.md` - 技术
