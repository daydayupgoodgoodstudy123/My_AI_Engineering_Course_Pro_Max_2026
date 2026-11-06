<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---initialization-scripts-for-agents"></a>

# 任务 - 初始化脚本 Agents

<a id="goal"></a>

## 目标
Build `init_agent.py` 检测运行时间、依赖性、测试命令、 env vars 和状态新鲜度, 然后写入 `init_report.json` 当一个密闭式探测器失败时会大声地停止会话。

<a id="inputs"></a>

## 输入
- 带回购 `requirements.txt` 测试命令,以及课程34中的工作台状态文件
- 课上的探测台( 运行时间、 底盘、 路径、 信封、 状态新鲜度、 最后已知的好) commit)

<a id="deliverables"></a>

## Deliverables
- `init_agent.py` 每个探测器返回时有一个函数 `(name, status, detail)`
- `init_report.json` 带有全探测器和时间戳
- 任何块状探测失败时的非零退出

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 幸福的道路上退出零
- 连续运行两次是无操作的,除了时间戳
- 模拟的 var 探测器表面, 并翻转退出代码

<a id="out-of-scope"></a>

## 超出范围
- 自动安装缺失的依附关系。 脚本停止和表面; 人类修正 。
- 呼叫一个 LLM 探针显示,探子会保持水管定律

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-init-script.md` - 技术
