# 00-setup-and-tooling：CoderPad 练习

本章 12 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [Dev Environment](01-dev-environment/coderpad/README.md) | 开发环境探针汇总 | 版本兼容判断 |
| 02 | [Git & Collaboration](02-git-and-collaboration/coderpad/README.md) | Git 变更分类 | 内容指纹与漂移 |
| 03 | [GPU Setup & Cloud](03-gpu-setup-and-cloud/coderpad/README.md) | 模型参数与内存估算 | 并行加速上限 |
| 04 | [APIs & Keys](04-apis-and-keys/coderpad/README.md) | 配置合同校验 | 结构化日志脱敏 |
| 05 | [Jupyter Notebooks](05-jupyter-notebooks/coderpad/README.md) | 耗时聚合 | 均值与总体方差 |
| 06 | [Python Environments](06-python-environments/coderpad/README.md) | 版本兼容判断 | 配置合同校验 |
| 07 | [Docker for AI](07-docker-for-ai/coderpad/README.md) | 内容指纹与漂移 | 精确命令策略 |
| 08 | [Editor Setup](08-editor-setup/coderpad/README.md) | 开发环境探针汇总 | 配置合同校验 |
| 09 | [Data Management](09-data-management/coderpad/README.md) | 可复现数据划分 | 内容指纹与漂移 |
| 10 | [Terminal & Shell](10-terminal-and-shell/coderpad/README.md) | 精确命令策略 | 词法路径包含边界 |
| 11 | [Linux for AI](11-linux-for-ai/coderpad/README.md) | 词法路径包含边界 | 独立权限与批准 |
| 12 | [Debugging and Profiling](12-debugging-and-profiling/coderpad/README.md) | 耗时聚合 | 分位数与 Goodput |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
