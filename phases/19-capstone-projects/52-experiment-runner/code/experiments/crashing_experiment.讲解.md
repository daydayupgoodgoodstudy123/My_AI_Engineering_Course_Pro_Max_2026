# 代码讲解 · crashing_experiment.py

> **所属小节**：阶段 19 · 综合项目 · 第 52 节 实验执行器 ｜ 讲义：[../../docs/zh.md](../../docs/zh.md) ｜ 测验：[../../quiz/quiz.md](../../quiz/quiz.md)
>
> **运行方式**：由测试 `tests/test_runner.py` 通过 `ExperimentRunner` 启动；也可单独运行 `python3 experiments/crashing_experiment.py` ｜ **依赖**：仅标准库（`json`、`sys`）

---

## 1. 这份代码在考察什么

这是一个**故意失败**的实验脚本（测试夹具，fixture），只有 19 行，用来触发 runner 的 `crash` 分支。它刻意做了三件事：

1. 在 stdout 打印一行 JSON（`{"step": 0, "note": "about to fail"}`）——模拟"失败前已经输出了一些东西"；
2. 在 stderr 打印一行错误信息（`trace: simulated failure`）——模拟异常堆栈；
3. 以**非零退出码 3** 结束——模拟脚本出错。

它验证的是讲义中这条规则："The runner never raises on a non zero exit code; instead it records the code in the result. Any non zero exit is labelled `"crash"` even when the script printed metrics."

> 一句话：**用最小的代码证明"runner 不会因为实验崩溃而崩溃，并能把崩溃原因完整带回来"**。

注：讲义写 "The lesson ships one experiment script"，实际 `experiments/` 目录下有两个脚本，本文件就是讲义没有提到的那个。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 模块 docstring | 文档 | 说明用途：给 runner 测试验证 crash 标签 | 测试夹具 |
| `main()` | 函数 | 打印一行 JSON 到 stdout、一行文本到 stderr，返回 3 | 部分输出 + 失败 |
| `sys.exit(main())` | 入口 | 返回值 3 成为进程退出码 | 非零退出码 |

数据流：启动 → stdout `{"step": 0, "note": "about to fail"}` → stderr `trace: simulated failure` → 退出码 3 → runner 记录 `exit_code=3, terminal="crash"`。

---

## 3. 逐段精讲

### 3.1 全部代码

```python
def main() -> int:
    print(json.dumps({"step": 0, "note": "about to fail"}))
    print("trace: simulated failure", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
```

- **stdout 这一行**：是合法 JSON 对象，但**不包含** `perplexity`。测试里 `metric_keys=["perplexity"]`，所以 `_scan_intermediates` 会跳过它，`metrics={}`。
  - 如果把 `metric_keys` 设为空列表，任何 JSON 对象都合格，`metrics` 就会变成 `{"step": 0, "note": "about to fail"}`——但标签仍然是 `crash`，因为退出码非零。这正好演示了"打印了指标也不算成功"。
- **stderr 这一行**：runner 用 `stderr=subprocess.PIPE` 捕获，原样放进 `ExperimentResult.stderr_tail`。测试用 `assertIn("simulated failure", result.stderr_tail)` 检查错误信息没有丢。
- **返回 3**：选一个不是 0、1、2 的值，便于和"Python 未捕获异常的退出码 1"、"参数错误的退出码 2"区分开。测试只断言 `exit_code != 0`。
- 没有调用 `flush=True`：脚本正常结束时解释器会刷新所有缓冲区，所以输出不会丢；只有被 kill 时才需要显式 flush（对比 `sparsity_experiment.py`）。
- 它不读取 config：runner 仍会把 config 路径作为 `argv[1]` 传进来，脚本直接忽略。

### 3.2 runner 侧看到了什么

`_terminal_label(exit_code=3, timed_out=False, oomed=False, have_metrics=...)`：

- 前两个 `if`（oom、timeout）不满足；
- `exit_code == 0` 的两个分支不满足；
- 落到最后的 `return "crash"`。

无论 `have_metrics` 是真是假，结果都是 `crash`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用独立脚本模拟崩溃 | 走的是真实的子进程路径，比 mock 更可信 | 每个测试都要启动一次解释器（约几十毫秒） |
| 失败前先输出一行 JSON | 覆盖"部分输出 + 失败"的边界情况 | 只覆盖了 stdout 有输出的情形 |
| stderr 写错误信息 | 验证 runner 保留诊断信息 | 真实崩溃的堆栈可能很长，runner 只在 `to_dict` 中保留最后 400 字符 |
| 退出码 3 | 与常见退出码区分 | 无 |
| 不模拟段错误 / 信号退出 | 保持简单 | 真实失败还包括被信号杀死（负退出码）、Python 未捕获异常（退出码 1）等，可另写夹具覆盖 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值注解（本文件中只是保持风格一致） |
| 返回类型注解 | `def main() -> int:` | 声明返回整数（退出码） |
| `json.dumps` | `json.dumps({"step": 0, ...})` | 字典转 JSON 字符串 |
| `print(..., file=sys.stderr)` | 错误信息 | 输出到标准错误流 |
| `sys.exit(code)` | `sys.exit(main())` | 以指定退出码结束进程；0 表示成功 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 |

---

## 6. 运行结果解读

单独运行：

```text
$ python3 experiments/crashing_experiment.py; echo "rc=$?"
{"step": 0, "note": "about to fail"}
trace: simulated failure          ← 这一行来自 stderr
rc=3
```

经 `ExperimentRunner` 运行（实测）：

| `metric_keys` | `terminal` | `exit_code` | `metrics` | `stderr_tail` |
|---------------|-----------|------------|-----------|---------------|
| `["perplexity"]`（测试用） | `crash` | 3 | `{}` | `'trace: simulated failure\n'` |
| `[]` | `crash` | 3 | `{"step": 0, "note": "about to fail"}` | 同上 |

第二行说明：即使 runner 解析到了"指标"，非零退出码也让标签保持 `crash`。

---

## 7. 动手改一改

1. **（入门）** 把 `return 3` 改成 `return 0`，用 `metric_keys=["perplexity"]` 运行，确认结果是 `exit_code=0, terminal="crash"`（退出码为 0 但没有指标）。
2. **（入门）** 改成 `raise RuntimeError("boom")`，观察退出码变成 1，`stderr_tail` 里出现完整的 Python traceback。
3. **（进阶）** 写一个 `segfault_experiment.py`：`import os, signal; os.kill(os.getpid(), signal.SIGSEGV)`，观察 runner 记录的 `exit_code`（应为 −11）和标签；思考是否应该为"被信号杀死"单独设一个标签。
4. **（进阶）** 写一个打印 1 MB stderr 后崩溃的脚本，确认 `to_dict()` 中 `stderr_tail` 只剩最后 400 字符，而对象本身保存了完整内容。

---

## 8. 常见坑

- **以为"打印了 JSON 就算成功"**：runner 的规则是退出码优先，非零即 `crash`。
- **在测试里用 `metric_keys=[]` 跑这个脚本却期望 `metrics == {}`**：空键集时任何 JSON 对象都会被当作指标。
- **只断言 `exit_code == 3`**：测试有意只断言"非零"，避免与具体退出码耦合；被信号杀死时退出码是负数。
- **忽略 stderr**：崩溃诊断信息全在 stderr，评估器 / 人工排查都要看它。
