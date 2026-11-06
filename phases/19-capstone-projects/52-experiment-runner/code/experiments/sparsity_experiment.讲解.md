# 代码讲解 · sparsity_experiment.py

> **所属小节**：阶段 19 · 综合项目 · 第 52 节 实验执行器 ｜ 讲义：[../../docs/zh.md](../../docs/zh.md) ｜ 测验：[../../quiz/quiz.md](../../quiz/quiz.md)
>
> **运行方式**：通常由 `main.py` 的 `ExperimentRunner` 启动；也可单独运行 `python3 experiments/sparsity_experiment.py <config.json>` ｜ **依赖**：标准库 + `numpy`（第三方）

---

## 1. 这份代码在考察什么

这是 runner 要执行的"被测对象"——一个**模拟实验脚本**。讲义："The simulation is not training anything real... The point of the lesson is the runner, not the simulation. A real experiment script would import a model."

它的价值在于把"实验脚本应遵守的约定"写成了一个最小可运行样例：

1. **输入约定**：从 `argv[1]` 读取 config 文件路径，解析 JSON；读取保留键 `__seed`。
2. **输出约定**：每步打印一行 JSON（中间指标），结束时打印一行包含全部指标的 JSON（最终指标），并且每次都 `flush=True`。
3. **退出码约定**：成功返回 0，参数或配置错误返回 2。
4. **可控的"故障注入"旋钮**：`sleep_s` 用来制造超时，`allocate_mb` 用来制造内存超限——runner 的测试与演示都靠这两个 knob。
5. **确定性**：`np.random.default_rng(seed)` 让同 seed 结果逐位相同。

> 一句话：**一个守规矩的实验脚本长什么样**——runner 的所有分支（ok / timeout / oom / 确定性）都靠它来触发。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 模块 docstring | 文档 | 列出支持的 5 个 knob | 配置契约 |
| `main()` 参数检查 | 代码段 | 缺少 argv 或 config 解析失败 → stderr 打印 JSON 错误，返回 2 | 失败即退出码 |
| 读取 knob | 代码段 | `__seed / k / steps / sleep_s / allocate_mb`，带默认值与类型转换 | 输入约定 |
| `bytearray` 分配 | 代码段 | 按 `allocate_mb` 占用内存 | OOM 故障注入 |
| 训练循环模拟 | `for` 循环 | 合成 loss 曲线，每步打印中间指标，可选 sleep | 学习曲线 / 超时注入 |
| 最终指标 | 代码段 | 打印包含 `steps_completed / k / seed` 的最后一行 | 最终指标 |
| `sys.exit(main())` | 入口 | 把返回值变成进程退出码 | 退出码约定 |

数据流：`argv[1]` → `json.load` → knob → `default_rng(seed)` →（可选分配内存）→ 循环 `steps` 次：算 loss → 打印 JSON →（可选 sleep）→ 打印最终 JSON → `return 0` → 退出码 0。

---

## 3. 逐段精讲

### 3.1 参数与配置读取：错误也要结构化

```python
    if len(sys.argv) < 2:
        print(json.dumps({"error": "missing config path"}), file=sys.stderr)
        return 2
    cfg_path = sys.argv[1]
    try:
        with open(cfg_path, "rt", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"bad config: {exc}"}), file=sys.stderr)
        return 2
```

- 错误信息写到 **stderr**，不污染 stdout 上的指标协议；runner 会把 stderr 原样存进 `stderr_tail`。
- 退出码 2 是 Unix 惯例里"用法错误"的常用值；runner 看到非零退出码就标记为 `crash`。
- 实测：不给参数 → `{"error": "missing config path"}`、退出码 2；config 内容是 `notjson` → `{"error": "bad config: Expecting value: line 1 column 1 (char 0)"}`、退出码 2。

### 3.2 读取 knob：默认值 + 显式类型转换

```python
    seed = int(cfg.get("__seed", 0))
    k = int(cfg.get("k", 8))
    steps = max(1, int(cfg.get("steps", 4)))
    sleep_s = float(cfg.get("sleep_s", 0.0))
    allocate_mb = int(cfg.get("allocate_mb", 0))
```

- `dict.get(key, default)`：缺键时用默认值，所以空 config `{}` 也能跑（实测得到 `k=8, seed=0`）。
- `int(...)` / `float(...)` 做类型规整：JSON 里写成字符串 `"8"` 也能工作。
- `max(1, ...)`：至少跑一步。⚠️ 这意味着 `steps=0` 会被悄悄改成 1，最终行报告 `steps_completed: 1`——"静默修正输入"在真实实验里可能掩盖配置错误，更稳妥的做法是直接以退出码 2 拒绝。
- `__seed` 由 runner 注入（`merged_config["__seed"] = spec.seed`），脚本只负责读取。

### 3.3 随机数与内存占用

```python
    rng = np.random.default_rng(seed)
    held = None
    if allocate_mb > 0:
        held = bytearray(allocate_mb * 1024 * 1024)
```

- `np.random.default_rng(seed)` 是 NumPy 推荐的新式随机数生成器（PCG64），**独立于全局状态**，同 seed 产生同样的序列。seed=7 时前 4 个 `normal(0, 0.02)` 抽样为 `[0.0000246, 0.005975, -0.005483, -0.017812]`（实测）。
- `bytearray(n)` 分配 n 个**清零**字节；清零需要真正写入每一页，所以这些内存会计入 RSS——这正是 runner 的内存轮询能"看见"它的原因。
- 分配发生在循环**之前**：实测 `allocate_mb=400, memory_cap_mb=256` 时，进程在打印第一行前就被 kill，结果 `metrics={}`、`intermediate_metrics=[]`。
- docstring 写 "extra bytes to hold"，实际单位是 **MB**。

### 3.4 合成的"训练循环"

```python
    base_loss = 5.0
    losses: list[float] = []
    for step in range(steps):
        noise = float(rng.normal(0, 0.02))
        loss_step = base_loss * (0.9 ** step) - 0.05 * min(k, 32) / 32.0 + noise
        losses.append(round(loss_step, 6))
        intermediate = {
            "step": step,
            "loss": losses[-1],
            "perplexity": round(float(np.exp(losses[-1])), 6),
            "final_loss": losses[-1],
        }
        print(json.dumps(intermediate), flush=True)
        if sleep_s > 0:
            time.sleep(sleep_s)
```

公式拆解：

| 项 | 含义 | 数值（k=16，step=3） |
|----|------|---------------------|
| `5.0 × 0.9^step` | 指数衰减的"训练曲线" | `5 × 0.729 = 3.645` |
| `− 0.05 × min(k, 32) / 32` | k 越大 loss 越低，k ≥ 32 饱和 | `−0.025` |
| `+ noise` | `N(0, 0.02²)`，由 seed 决定 | `−0.017812` |
| 合计 | | `3.602188`（与实际运行一致） |

- `perplexity = e^loss`：困惑度是交叉熵损失的指数，loss 3.6 对应 ppl ≈ 36.7。
- 中间行里**也放了 `perplexity` 和 `final_loss`**。这让 runner 把每一步都当作"覆盖 `metric_keys` 的行"收进 `intermediate_metrics`（学习曲线），但副作用是：超时 / 被 kill 时，最后一条中间行会被当成"最终指标"（测验 Q8）。字段名 `final_loss` 出现在中间行里，本身就有些误导。
- `flush=True` 很关键：stdout 接管道时默认是块缓冲，不 flush 的话进程被 kill 时缓冲区内容全部丢失，runner 就拿不到部分输出。
- `sleep_s` 放在打印**之后**：所以超时测试中至少能看到第 0 步。

### 3.5 最终指标与退出

```python
    final = {
        "perplexity": round(float(np.exp(losses[-1])), 6),
        "final_loss": losses[-1],
        "steps_completed": steps,
        "k": k,
        "seed": seed,
    }
    print(json.dumps(final), flush=True)
    if held is not None:
        held[0] = 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- 最终行把 `k`、`seed` 原样回显：测试 `test_seed_forwarded` 与 `test_ablation_sweep_returns_table` 正是靠这两个字段确认"runner 转发的配置真的到了脚本里"。
- `held[0] = 1`：在最后使用一次 `held`，保证这块内存在整个运行期间都被引用、不被提前回收（在 CPython 中局部变量本来也会一直存活到函数返回，这里更多是"表明意图"）。
- `sys.exit(main())`：把 `main()` 的返回值作为进程退出码（0 成功、2 参数错误）。
- `round(..., 6)`：固定 6 位小数，JSON 序列化结果稳定，确定性测试可以用 `assertEqual` 比较浮点数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| config 走文件路径而不是命令行参数 | 任意嵌套 JSON 都能传，不受命令行长度和转义限制 | 多一次文件 IO；生产中常用 Hydra/YAML 配置文件，同样走路径 |
| 错误 → stderr JSON + 退出码 2 | 不污染 stdout 指标协议，runner 以退出码判断 | 退出码含义需在团队内约定 |
| 中间行也带 `perplexity/final_loss` | 让 runner 自动收集学习曲线 | 中间行与最终行无法区分（测验 Q8、Q10） |
| `sleep_s` / `allocate_mb` 故障注入 | 用确定的方式测试 runner 的超时与 OOM 分支 | 真实脚本中应移除或隔离这类测试钩子 |
| `default_rng(seed)` | 局部生成器，不受其它代码影响，可复现 | 真实训练还要固定框架 / GPU 的随机性 |
| `max(1, steps)` 静默修正 | 避免 `losses[-1]` 在空列表上报错 | 掩盖配置错误；应校验后拒绝 |
| 合成公式代替真实训练 | 毫秒级完成，测试快且确定 | 不反映真实实验的耗时、显存与失败模式 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `sys.argv` | `cfg_path = sys.argv[1]` | 命令行参数列表，`argv[0]` 是脚本名 |
| `print(..., file=sys.stderr)` | 错误信息 | 输出到标准错误流 |
| `print(..., flush=True)` | 每行指标 | 立即刷新缓冲区 |
| `with open(..., "rt", encoding="utf-8")` | 读取 config | 文本模式读取，自动关闭 |
| 捕获多个异常 | `except (OSError, json.JSONDecodeError) as exc:` | 文件错误和 JSON 错误统一处理 |
| f-string 插入异常 | `f"bad config: {exc}"` | 把异常信息放进字符串 |
| `dict.get(key, default)` | `cfg.get("k", 8)` | 缺键返回默认值 |
| 类型注解的局部变量 | `losses: list[float] = []` | 给变量标注类型（只是提示，不强制） |
| `**` 幂运算 | `0.9 ** step` | 指数 |
| 负索引 | `losses[-1]` | 取最后一个元素 |
| `bytearray(n)` | `bytearray(allocate_mb * 1024 * 1024)` | 可变字节数组，初始全零 |
| `np.random.default_rng` | `rng.normal(0, 0.02)` | 新式随机数 API |
| `round(x, n)` | `round(loss_step, 6)` | 四舍五入到 n 位小数 |
| `sys.exit(main())` | 文件末尾 | 返回值作为退出码 |
| `if __name__ == "__main__":` | 文件末尾 | 只在直接运行时执行 |

---

## 6. 运行结果解读

单独运行（config 为 `{"k": 16, "steps": 4, "__seed": 7}`，与 `main.py` demo 的 base 一致）：

```text
{"step": 0, "loss": 4.975025, "perplexity": 144.752444, "final_loss": 4.975025}
{"step": 1, "loss": 4.480975, "perplexity": 88.320743, "final_loss": 4.480975}
{"step": 2, "loss": 4.019517, "perplexity": 55.674209, "final_loss": 4.019517}
{"step": 3, "loss": 3.602188, "perplexity": 36.678399, "final_loss": 3.602188}
{"perplexity": 36.678399, "final_loss": 3.602188, "steps_completed": 4, "k": 16, "seed": 7}
退出码 0
```

- 第 0 步：`5 − 0.025 + 0.0000246 = 4.9750246` → `4.975025`；第 3 步见 3.4 节表格。
- 最后两行数值相同：最终行就是最后一步的 loss，只是多了 `steps_completed / k / seed`。
- 与 `main.py` demo 中 base 结果逐位一致，说明脚本在 runner 内外行为相同。

其它情形（实测）：

| 输入 | 输出 / 退出码 |
|------|-------------|
| 不给参数 | stderr `{"error": "missing config path"}`，退出码 2 |
| config 文件内容非 JSON | stderr `{"error": "bad config: Expecting value: ..."}`，退出码 2 |
| `{}`（全默认） | `k=8, seed=0`，最终 `final_loss=3.634598`，退出码 0 |
| `{"steps": 0, "k": "8"}` | 只跑 1 步，`steps_completed: 1`；字符串 `"8"` 被转成整数 8 |

---

## 7. 动手改一改

1. **（入门）** 把 `0.05` 改成 `0.5`，重新跑 `main.py` 的消融，观察 k 的影响是否盖过噪声；再把噪声标准差调到 0.2，对比"同 seed"和"不同 seed"两种消融表的可读性。
2. **（入门）** 让 `steps <= 0` 时直接报错：stderr 打印 `{"error": "steps must be >= 1"}` 并返回 2，确认 runner 把它标为 `crash`。
3. **（进阶）** 给最终行加 `"__final": true`，同时修改 `main.py` 的 `_scan_intermediates` 只把带该标记的行当作最终指标（测验 Q10 的思路二）。
4. **（进阶）** 把 `allocate_mb` 改成"每步分配一点"（例如每步追加 `allocate_mb/steps` MB），配合 `sleep_s` 观察 `peak_rss_mb` 随时间增长，以及 runner 在哪一步触发 OOM。
5. **（挑战）** 把合成公式换成一个真正的小训练：用 NumPy 在随机数据上训练一个逻辑回归，`k` 作为 L1 正则下保留的非零权重数（"稀疏度"），输出验证集 loss；检查同 seed 是否仍完全可复现。

---

## 8. 常见坑

- **忘记 `flush=True`**：被 kill 时缓冲区里的指标行全部丢失，runner 看到的是空 stdout。
- **把调试信息打印成 JSON 到 stdout**：如果它碰巧包含全部 `metric_keys`，会被 runner 当成指标。调试信息应写 stderr。
- **用全局 `np.random.seed` 而不是局部 `default_rng`**：其它库也可能消耗全局随机数，导致"同 seed 不同结果"。
- **以为 `allocate_mb` 是字节**：单位是 MB（docstring 写的是 bytes）。
- **把 `final_loss` 字段当作"最终"**：中间行里也有这个字段，是否最终要看它在哪一行。
- **静默修正非法配置**：`max(1, steps)` 这种写法会让 `steps=0` 的错误配置"看起来成功"。
