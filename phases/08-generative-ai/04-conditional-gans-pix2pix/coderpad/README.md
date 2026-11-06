# 08/04：Conditional GANs & Pix2Pix

**45 分钟 CoderPad 风格练习：核心「二维仿射变换」，加分「回归误差与形状」。**

题目依据本地课程正文与学习目标，抽取适合现场实现的编码范围。
来源：[本地课程材料](../docs/en.md)。准确输入输出合同见 [PROMPT.md](PROMPT.md)，
具体输入与期望结果见 [fixtures.json](fixtures.json)。
本套与第 13 章试点使用相同的核心/加分测试入口；全部标准库、离线运行。
45 分钟是建议练习上限，基础题可能提前完成，难度与用时尚未经过学员计时校准。

## 从这里开始

在本文件所在的 `coderpad/` 打开终端：

```bash
python3 --version
python3 run_tests.py --list
python3 run_tests.py --core
```

要求 Python 3.10+。`--list` 只收集测试。未完成 TODO 时核心失败正常；
实跑参考记录见 [verification.txt](verification.txt)，初始成绩见 [starter_baseline.txt](starter_baseline.txt)。

## 本次写什么

| 优先级 | 文件与函数 | 练习能力 |
| --- | --- | --- |
| 核心 | `starter/main.py` → `transform` | 二维仿射变换 |
| 加分 | 同文件 → `mse` | 回归误差与形状 |

核心和加分相互独立；只修改 starter，可以新增自己的测试文件。
测试辅助文件不包含这两个 TODO 的答案；原课完整实现和参考答案仅供计时结束后复盘。
相关课共享基础算法，具体组合和 kernel 名称见 [SCOPE.json](SCOPE.json)。
如果曾做过同一核心，请把这轮标成“重复练习”，不要当作未见题成绩。

## 原课学习目标（阅读范围，不是额外评分需求）

- 原课程没有可提取的 Learning Objectives；请对照上述代码来源和本题限定合同。

## 面试节奏

| 时间 | 行动 |
| --- | --- |
| 0–5 分钟 | 阅读合同和例子，复述输入输出，提出澄清 |
| 5–12 分钟 | 讲实现顺序，完成一个成功路径 |
| 12–30 分钟 | 核心边界、错误处理、不可变输入 |
| 30–39 分钟 | 核心通过后做加分，补自己的反例测试 |
| 39–45 分钟 | 跑核心和全量，保存，解释复杂度与限制 |

```bash
python3 run_tests.py --core
python3 run_tests.py --bonus
python3 run_tests.py
# 计时结束后才选择独立参考答案，不覆盖 starter
python3 run_tests.py --solution
```

每套核心 6 cases、加分 2 cases。新增自己的测试会在全量命令执行，但不会并入这两个固定分母。
`python3 -m unittest discover -s tests -v` 默认也测试 starter。
本地没有真正隐藏的评测服务器，也不会强制停止计时。

需要主持时可说：“按这套 [INTERVIEWER.md](INTERVIEWER.md) 开始面试，一次只问一个问题。”
结束后复制 [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md)，先记录计时成绩，再查看
[中文复盘解释](solution/EXPLANATION.md)。重做前另存自己的代码，避免用 git reset/clean 重置上层课程。
