# 全课程 CoderPad 面试练习

覆盖编号章节 00–20 的全部 543 个项目：第 13 章已有 31 套，本轮新增 512 套。
个人学习笔记、认证课程和 outputs 内嵌样例不计为新的章节项目。
组织方式与第 13 章试点一致，每个项目下的 coderpad/ 与 code/docs/assets 同级。

新增题包使用 130 个可复用的基础编码 kernel，逐课显式选择核心/加分组合。
新增部分有 421 种核心/加分组合。所以 543 是按课组织的题包数，不是 543 道互不重复的算法题。
相邻架构课可能复用相同 kernel；SCOPE.json 和下表标明范围，复盘时区分未见题与重复练习。
每套只覆盖适合现场写代码的切面，不能代替原课程完整项目或真实部署验收。

## 开始方法

打开下表某章，选择项目的 coderpad/README.md。Python 3.10+，标准库，无 API key、下载或 GPU。
在选定 coderpad/ 目录运行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
python3 run_tests.py --bonus
```

45 分钟为建议上限，基础题可以提前完成，难度与时间尚未经过学员校准。
初始失败是正常 TODO。计时后再用 `python3 run_tests.py --solution`，不会覆盖 starter。
本地没有真实隐藏测试或强制倒计时；使用自己的计时器。
每套包含面试官指南、参考答案、中文解释、评分与复盘表、参考验证和 starter 基线。
希望助手主持时说：“按这个项目 coderpad/INTERVIEWER.md 开始，一次只问一个问题。”

## 章节入口

| 章节 | 项目数 | 练习索引 |
| --- | --- | --- |
| 00-setup-and-tooling | 12 | [打开](phases/00-setup-and-tooling/CODERPAD.md) |
| 01-math-foundations | 22 | [打开](phases/01-math-foundations/CODERPAD.md) |
| 02-ml-fundamentals | 18 | [打开](phases/02-ml-fundamentals/CODERPAD.md) |
| 03-deep-learning-core | 13 | [打开](phases/03-deep-learning-core/CODERPAD.md) |
| 04-computer-vision | 28 | [打开](phases/04-computer-vision/CODERPAD.md) |
| 05-nlp-foundations-to-advanced | 29 | [打开](phases/05-nlp-foundations-to-advanced/CODERPAD.md) |
| 06-speech-and-audio | 17 | [打开](phases/06-speech-and-audio/CODERPAD.md) |
| 07-transformers-deep-dive | 16 | [打开](phases/07-transformers-deep-dive/CODERPAD.md) |
| 08-generative-ai | 15 | [打开](phases/08-generative-ai/CODERPAD.md) |
| 09-reinforcement-learning | 12 | [打开](phases/09-reinforcement-learning/CODERPAD.md) |
| 10-llms-from-scratch | 24 | [打开](phases/10-llms-from-scratch/CODERPAD.md) |
| 11-llm-engineering | 17 | [打开](phases/11-llm-engineering/CODERPAD.md) |
| 12-multimodal-ai | 25 | [打开](phases/12-multimodal-ai/CODERPAD.md) |
| 13-tools-and-protocols | 31 | [打开](phases/13-tools-and-protocols/CODERPAD.md) |
| 14-agent-engineering | 54 | [打开](phases/14-agent-engineering/CODERPAD.md) |
| 15-autonomous-systems | 22 | [打开](phases/15-autonomous-systems/CODERPAD.md) |
| 16-multi-agent-and-swarms | 25 | [打开](phases/16-multi-agent-and-swarms/CODERPAD.md) |
| 17-infrastructure-and-production | 28 | [打开](phases/17-infrastructure-and-production/CODERPAD.md) |
| 18-ethics-safety-alignment | 30 | [打开](phases/18-ethics-safety-alignment/CODERPAD.md) |
| 19-capstone-projects | 85 | [打开](phases/19-capstone-projects/CODERPAD.md) |
| 20-recursive-self-improvement | 20 | [打开](phases/20-recursive-self-improvement/CODERPAD.md) |

第 20 章的 09–12 原有 docs/en.md 缺失，题包依据现存 code 设计，已在对应 README/SCOPE 标注。
参考验证总表见 [CODERPAD_VALIDATION.json](CODERPAD_VALIDATION.json)。
维护源文件见 [scripts/coderpad_curriculum/README.md](scripts/coderpad_curriculum/README.md)。
