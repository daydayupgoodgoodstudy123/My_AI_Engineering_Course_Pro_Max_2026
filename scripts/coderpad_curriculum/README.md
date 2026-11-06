# 全课程 CoderPad 题包维护

本轮覆盖第 13 章以外 512 个编号课程项目。第 13 章的原有 31 套由独立生成器维护，本工具不覆盖它们。

- `routes.py`：逐课显式选择核心与加分，不通过题目关键词自动猜测。
- `kernels/*.py`：130 个共享编码核心、精确合同、实现、每项六个手写例子。
- `notes.py`：对应中文推理解释。
- `CATALOG.json`：生成的逐课映射、学习目标与本地来源 hash。
- `build.py`：生成独立题包，已有内容有差异即拒绝覆盖。
- `verify.py`：在独立进程验证参考答案与 TODO 基线，并只读测试第 13 章参考答案。

每套新增题包有六个核心 case 和两个加分 case。共享 kernel 表示相邻课会有重复能力，不能把题包总数称作独立算法数。
原课程训练、部署和真实运行时验收不由这些本地题包替代。

从仓库根目录：

```bash
# 已有 starter 被学员修改时会报告差异，绝不覆盖
python3 scripts/coderpad_curriculum/build.py --check

# 新目录预览
python3 scripts/coderpad_curriculum/build.py --output /tmp/coderpad-preview
python3 scripts/coderpad_curriculum/verify.py --target /tmp/coderpad-preview

# 临时重建与验证，不修改学员目录或日志
python3 scripts/coderpad_curriculum/verify.py
```

发布维护更新时先在新目录生成和验证，再审阅差异；不要覆盖学员的 starter 或自写测试。
`--target` 验证前会对照生成源检查所有材料，学员已经做题时请用默认临时验证模式。
所有参考输出例子均在 kernel 源文件中显式给定；验证时不以待测函数实时计算期望答案。
用 Python 标准库执行，限定子进程超时，并按固定数量的进程并行检查。
