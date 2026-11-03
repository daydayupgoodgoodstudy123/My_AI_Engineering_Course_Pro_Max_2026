# 20：脱敏 Trace 与耗时统计

**原创 CoderPad 风格模拟面试，45 分钟，基础到中等。**

遍历嵌套属性做脱敏，再计算按操作聚合的耗时。使用可控时间戳，区分总耗时与子 span 时间叠加。

题目基于[本课课程材料](../docs/en.md)改编；准确行为以 [英文面试题 PROMPT.md](PROMPT.md) 为准。
这是面试能力训练，不是 Edison 原题，也没有使用真实公司的内部评分。
每套是独立的标准库 Python 项目；不需要服务、API key、付费调用或新依赖。
建议时间与难度是试点设计值，尚未经真实学员计时校准。

## 第一次开始

终端进入本文件所在的 `coderpad/`，然后运行：

```bash
python3 --version
python3 run_tests.py --list
python3 run_tests.py --core
```

要求 Python 3.10+。初始核心测试失败是正常的 TODO 起点；当前生成版本的实跑记录见
[starter_baseline.txt](starter_baseline.txt) 和 [verification.txt](verification.txt)。
`--list` 只收集测试，不执行 TODO。无需先运行原课程 `code/main.py`。

## 你要修改的地方

只在 [starter/main.py](starter/main.py) 完成功能。可以新增自己的测试；不要改变原有测试来获得通过。
给定的构造器、异常类、辅助函数和 fake 依赖可直接使用。TODO 编号按源文件顺序排列，
核心/加分归属以 PROMPT 合同为准，不要求按编号顺序做完。

| TODO | 函数或方法 |
| --- | --- |
| 1 | `redact` |
| 2 | `summarize` |
| 3 | `critical_span` |

## 面试节奏

| 时间 | 行动 |
| --- | --- |
| 0–5 分钟 | 阅读 PROMPT、starter、测试，复述输入输出并提出澄清 |
| 5–10 分钟 | 说出实现顺序，完成最小成功路径 |
| 10–30 分钟 | 完成核心行为、边界和失败后的状态保护 |
| 30–39 分钟 | 修复核心，再尝试加分项 |
| 39–45 分钟 | 核心与全量测试、保存、记录未完成项 |

```bash
# 核心 / 加分分开计分；测试失败时退出码为 1
python3 run_tests.py --core
python3 run_tests.py --bonus
python3 run_tests.py

# 过滤名称；将 keyword 换成 --list 显示的测试名片段
python3 run_tests.py --core -k keyword

# 计时结束后才运行参考答案；不会修改 starter
python3 run_tests.py --solution
```

评分单位是 unittest test case；同一方法里的多个 subTest 输入不分别加分。
一个 subTest 失败就算该 case 失败。加分分开记录，不补偿核心缺失。
直接运行 `python3 -m unittest discover -s tests -v` 默认测试 starter；统一入口仍推荐 run_tests.py。

## 两种练习方式

- **独立限时**：使用自己的计时器，只看候选人材料；关闭答案、原课完整实现和 AI 代写。计时后再复盘。
- **面试官陪练**：告诉助手“按这套 coderpad/INTERVIEWER.md 开始面试”，或请朋友主持。面试官分阶段澄清与提示，你独立写代码。

这些规则是训练约定；本地文件无法真正隐藏测试或强制锁定倒计时。
第一轮可先看课程学习，另记为学习轮；后续使用未做过的题练独立表现。

计时结束复制 [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md) 记录成绩，再阅读
[参考解释](solution/EXPLANATION.md)。重做前保留自己的 starter 副本；不要使用上层 `git reset` 或 `git clean`。
