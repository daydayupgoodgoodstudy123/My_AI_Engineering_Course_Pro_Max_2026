<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mission---the-workbench-on-a-real-repo"></a>

# 任务 - 工作台在现实回收站上

<a id="goal"></a>

## 目标
运行相同 `/signup` 通过 prompt- 仅用管道和工作台引导的管道来对着相同的样本应用,然后在比较报告之前/之后发出一个怀疑者读取的信息。

<a id="inputs"></a>

## 输入
- `sample_app/` 与 `app.py` (无验证), `test_app.py` (一个快乐的测试) `README.md`, `scripts/release.sh` 做为禁区诱饵
- 这两条管道都完全编好,没有真实的 LLM calls

<a id="deliverables"></a>

## Deliverables
- `code/main.py` 将两条管道都用同一根管子
- `before-after-report.md` 与五个成果表
- `comparison.json` 用于下游制图

<a id="acceptance"></a>

## Acceptance
- `python3 code/main.py` 退出为零
- 报告衡量了所有五个结果:实际进行的测试、达到的接受程度、范围以外的文件、 handoff 质量,审查者总数
- 工作台的输油管打得比 prompt- 至少在五人中四个人身上有输油管

<a id="out-of-scope"></a>

## 超出范围
- 插在真实的 LLM管道的脚本可以复制。
- 测试模型,通过构造,比较能维持模型的常态

<a id="references"></a>

## References
- `docs/en.md` - 全部课
- `code/main.py` - 参考执行
- `outputs/skill-workbench-benchmark.md` - 技术
