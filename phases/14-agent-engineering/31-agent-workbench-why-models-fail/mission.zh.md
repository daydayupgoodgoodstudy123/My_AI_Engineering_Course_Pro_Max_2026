<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---agent-workbench-why-capable-models-still-fail"></a>

# 任务 - Agent 工作台:为什么有能力的模型仍然失败

<a id="goal"></a>

## 目标
两次做同样的小折叠任务,一次 prompt- 一次,7个工作台的表面都连接了起来, 并发布一个故障模式报告, 每一个丢失的表面都图解到它造成的症状。

<a id="inputs"></a>

## 输入
- 一根根根头 agent 和一个小 FastAPI- 验证的风格处理器
- 七层清单(指示、状态、范围、反馈、核查、审查、 handoff)

<a id="deliverables"></a>

## Deliverables
- `code/main.py` 双管接连运行
- `failure_modes.json` 总结 prompt- 璶禲
- 工作台运行的单线裁决

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 输出显示两个运行的单边日志
- `failure_modes.json` 列出每个有匹配症状的缺失表面

<a id="out-of-scope"></a>

## 超出范围
- 说得真像,管子是按规矩办事的
- 建造一个深度的表面。这是接下来11个课的目的。

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-workbench-audit.md` - 技术
