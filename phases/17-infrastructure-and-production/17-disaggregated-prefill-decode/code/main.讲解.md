# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 17 节 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`from __future__ import annotations`），无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这是一个只有 60 多行的"单请求时延计算器"，用几条算术公式对比同一个请求在两种部署方式下的端到端时延：

1. **同机部署（colocated）**：同一张 GPU 先做 prefill、再做 decode。
2. **分离式部署（disaggregated）**：prefill pool 做 prefill → 通过 NIXL 把 KV cache 传给 decode pool → decode pool 用更快的"显存优化型"GPU 做 decode；分别模拟 RDMA（100 GB/s）和 TCP（10 GB/s）两种传输。

它想让你建立的直觉是讲义里的三件事：prefill 时间 ∝ prompt 长度、decode 时间 ∝ 输出长度、KV 传输时间 ∝ prompt 长度 ÷ 带宽。

> 一句话：**用"prefill + 传输 + decode"三段时延的加法，体会分离式的"传输税"与"decode 加速"之间的权衡**——但要注意，这份代码的常数设置让分离式在所有 case 都赢，打印出来的结论与它自己的公式方向相反，这是本节最值得挖的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PREFILL_TOK_PER_MS = 40.0` | 模块常数 | 单卡 prefill 速度：40 token/ms（4 万 token/s） | prefill 是 compute-bound，按 token 线性 |
| `DECODE_TOK_PER_MS_COLOCATED = 0.10` | 模块常数 | 同机 decode 速度：0.1 token/ms（100 token/s） | decode 是 memory-bound |
| `DECODE_TOK_PER_MS_DECODE_GPU = 0.18` | 模块常数 | decode pool 速度：180 token/s（"H200-like"） | 按瓶颈选硬件 |
| `KV_BYTES_PER_TOKEN_70B_FP8 = 125_000` | 模块常数 | 每 token 的 KV 字节数 | KV cache 大小 |
| `NIXL_RDMA_GB_S` / `NIXL_TCP_GB_S` | 模块常数 | 100 / 10 GB/s | NIXL 的 RDMA 与 TCP 回退 |
| `ms_colocated(prompt, output)` | 函数 | prefill + decode | 同机部署 |
| `ms_disaggregated(prompt, output, use_rdma)` | 函数 | prefill + KV 传输 + 更快的 decode | 分离式部署 |
| `main()` | 函数 | 扫 8 组 (prompt, output)，打印三列时延与胜者 | 寻找 crossover |

数据流：`main()` 中的 `cases` 列表 → 对每组分别调用 `ms_colocated` 与两次 `ms_disaggregated` → 比较 colocated 与 RDMA → 打印表格与 "Read:" 结论。

---

## 3. 逐段精讲

### 3.1 常数：一个 70B FP8 模型在 H100 级 GPU 上的"示意"参数

```python
# illustrative 2026 constants for 70B FP8 on H100 class
PREFILL_TOK_PER_MS = 40.0         # prefill throughput per GPU per ms
DECODE_TOK_PER_MS_COLOCATED = 0.10
DECODE_TOK_PER_MS_DECODE_GPU = 0.18   # memory-optimized pool (H200-like)
KV_BYTES_PER_TOKEN_70B_FP8 = 125_000
NIXL_RDMA_GB_S = 100
NIXL_TCP_GB_S = 10
```

- 注释写得很清楚：**illustrative**（示意值）。单位统一成"每毫秒"，后面直接做除法即可得到毫秒。
- prefill 40 token/ms 比 decode 0.1 token/ms 快 400 倍：这就是"prefill 一次前向处理很多 token、decode 一次前向只出 1 个 token"的直观体现。
- 注意 decode 速度是**单个请求**的生成速度（100 token/s），代码里没有 batch 的概念——真实 decode 的效率高度依赖并发（讲义："Batch efficiency is good only at high concurrency"）。
- ⚠️ `125_000` 字节/token 偏小。按 Llama 3.x 70B 的真实结构（80 层、8 个 KV 头、head_dim 128）计算：`2 × 80 × 8 × 128 × 1 字节 = 163,840` 字节/token（FP8）。代码常数让 4K token 的 KV 恰好等于 512 MB，对上了讲义练习 4 的"约 500 MB"，但比真实值低约 24%。
- ⚠️ `0.18` 与 `0.10` 的差距来自"换了 H200 类显存型 GPU"，并不是分离这一架构本身带来的——这一点决定了后面整张表的结论（见 3.3 与第 6 节）。

### 3.2 同机部署：两段相加

```python
def ms_colocated(prompt: int, output: int) -> float:
    prefill_ms = prompt / PREFILL_TOK_PER_MS
    decode_ms = output / DECODE_TOK_PER_MS_COLOCATED
    return prefill_ms + decode_ms
```

- `prompt / 40` 就是 prefill 时间；`output / 0.10` 就是 decode 时间。以 `(4096, 500)` 为例：`102.4 + 5000 = 5102.4 ms`。
- decode 占了 98% 的时间——对于"输出几百 token"的请求，端到端时延几乎全由 decode 决定，这也是 TPOT（每输出 token 时间）如此重要的原因。
- 模型里**没有干扰**：真实同机部署的核心问题是 prefill 与 decode 抢同一个批次、互相拖慢，这里完全没有体现。

### 3.3 分离式部署：多了一段传输，换来更快的 decode

```python
def ms_disaggregated(prompt: int, output: int, use_rdma: bool = True) -> float:
    prefill_ms = prompt / PREFILL_TOK_PER_MS
    kv_bytes = prompt * KV_BYTES_PER_TOKEN_70B_FP8
    transport = NIXL_RDMA_GB_S if use_rdma else NIXL_TCP_GB_S
    transfer_ms = (kv_bytes / 1e9) / transport * 1000
    decode_ms = output / DECODE_TOK_PER_MS_DECODE_GPU
    return prefill_ms + transfer_ms + decode_ms
```

- `kv_bytes / 1e9` 把字节换成 GB，`/ transport` 得到秒，`* 1000` 得到毫秒。`(4096, 500)`：KV = 0.512 GB，RDMA 5.12 ms，TCP 51.2 ms——与讲义练习 4 的"RDMA 5 ms / TCP 50 ms"一致。
- `transport = A if cond else B` 是条件表达式，根据参数选择带宽。
- decode 用 `0.18`：`500 / 0.18 = 2777.8 ms`，比同机的 5000 ms 少 2222 ms，而传输只多了 5 ms。
- **盈亏平衡推导**：两式相减，prefill 抵消：
  - `disagg − colo = prompt × t_xfer − output × (10 − 5.556)`
  - RDMA 下 `t_xfer = 0.00125 ms/token`，TCP 下 `0.0125 ms/token`；
  - 分离式更慢 ⇔ `prompt / output > 3,556`（RDMA）或 `> 356`（TCP）。
- 所以在这个模型里，**prompt 越长分离式越吃亏、输出越长分离式越占便宜**。讲义"短 prompt 不值得分离"的结论在这个模型里推不出来。

### 3.4 `main()`：扫描 8 组请求形状

```python
    cases = [
        (256, 100), (512, 200), (1024, 300), (2048, 400),
        (4096, 500), (8192, 800), (16384, 1200), (32768, 2000),
    ]
    for prompt, output in cases:
        colo = ms_colocated(prompt, output)
        rdma = ms_disaggregated(prompt, output, use_rdma=True)
        tcp = ms_disaggregated(prompt, output, use_rdma=False)
        winner = "colocated" if colo < rdma else "disaggregated"
        print(f"{prompt:>7}  {output:>7}  {colo:>14.1f}  {rdma:>17.1f}  {tcp:>16.1f}  {winner}")
```

- 8 组 case 的 prompt/output 比值从 2.56 到 16.4，远低于 356 的 TCP 临界值，所以**不可能出现 crossover**。
- ⚠️ `winner` 只比较 `colo` 与 `rdma`，`tcp` 列只打印不参与判定。
- `f"{prompt:>7}"`：右对齐、宽 7；`{colo:>14.1f}`：右对齐、宽 14、保留 1 位小数。表头宽度用 `"-" * len(header)` 生成等长分隔线。
- 最后的 "Read:" 是**写死的文字**，并不是根据计算结果生成的；它声称"disaggregation wins at longer prompts ... TCP transport raises the break-even"，与公式推出的方向相反（见 3.3）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只算单请求串行时延 | 公式一眼能看懂 | 没有 batch、并发、队列，无法体现分离式消除干扰、提高 goodput 的真正收益；生产要用负载回放或压测 |
| decode pool 用更快的常数 0.18 | 体现"decode 池可以换显存型 GPU" | 把硬件升级的收益算到了分离式头上；若两边同为 H100，分离式永远更慢（多出传输时间） |
| KV 大小用一个常数 | 简单 | 与真实 GQA 结构不符（低估约 24%）；应按 `2 × 层 × KV 头 × head_dim × 字节` 计算 |
| 传输 = 数据量 ÷ 带宽 | 理想链路模型 | 忽略协议开销、分块打包、内存注册、拥塞；讲义概念部分给的实际值是 20–80 ms |
| 只输出时延 | 代码短 | 讲义说会报告吞吐、每请求成本和 crossover，均未实现；应加 GPU 占用时间 × 单价 |
| "Read:" 结论写死 | 方便打印讲解 | 与计算结果脱节；应根据结果动态生成结论或至少与之一致 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头的 `"""Colocated vs disaggregated ..."""` | 描述整个文件的用途，`help()` 可以看到 |
| `from __future__ import annotations` | 第一行 import | 让类型注解延迟求值；本文件注解都是内置类型，加上它是项目统一风格 |
| 模块级常数（全大写） | `PREFILL_TOK_PER_MS = 40.0` | Python 没有真正的常量，全大写是"不要修改"的约定 |
| 数字下划线分隔 | `125_000` | 等于 `125000`，只为可读性 |
| 类型注解 | `def ms_colocated(prompt: int, output: int) -> float:` | 说明参数和返回值类型，运行时不检查 |
| 默认参数 | `use_rdma: bool = True` | 调用时可省略 |
| 关键字参数调用 | `ms_disaggregated(prompt, output, use_rdma=False)` | 写出参数名，含义更清楚 |
| 条件表达式 | `NIXL_RDMA_GB_S if use_rdma else NIXL_TCP_GB_S` | 一行内的 if/else，返回一个值 |
| 元组列表 + 解包 | `for prompt, output in cases:` | 每个元素是二元组，循环时直接拆成两个变量 |
| f-string 格式符 | `{prompt:>7}`、`{colo:>14.1f}`、`{'prompt':>7}` | `>` 右对齐，数字是宽度，`.1f` 保留 1 位小数；花括号里也可以放字符串字面量 |
| 字符串乘法 | `"=" * 95`、`"-" * len(header)` | 重复字符串，常用来画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行（测验里我们 import 了这两个函数做推导） |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3，耗时不到 0.1 秒；代码无随机性，结果完全可复现）：

```text
===============================================================================================
DISAGGREGATED vs COLOCATED — same request, different GPU placement
===============================================================================================
 prompt   output   colocated (ms)   disagg RDMA (ms)   disagg TCP (ms)  Winner
------------------------------------------------------------------------------
    256      100          1006.4              562.3             565.2  disaggregated
    512      200          2012.8             1124.6            1130.3  disaggregated
   1024      300          3025.6             1693.5            1705.1  disaggregated
   2048      400          4051.2             2276.0            2299.0  disaggregated
   4096      500          5102.4             2885.3            2931.4  disaggregated
   8192      800          8204.8             4659.5            4751.6  disaggregated
  16384     1200         12409.6             7096.7            7281.1  disaggregated
  32768     2000         20819.2            11971.3           12339.9  disaggregated

Read: disaggregation wins at longer prompts where decode throughput improvement
on memory-optimized pool outweighs the KV transfer tax. TCP transport raises the
break-even; RDMA makes disaggregation profitable earlier.
```

逐项解读：

- **第一行 `256/100`**：colocated = `6.4 + 1000 = 1006.4`；RDMA = `6.4 + 0.32 + 555.6 = 562.3`；TCP = `6.4 + 3.2 + 555.6 = 565.2`。传输税只有 0.32 / 3.2 ms，decode 却快了 444 ms，分离式稳赢。
- **全部 8 行都是 `disaggregated`**：没有任何 crossover。讲义练习 1 问"在什么 prompt 长度分离式开始胜出"，这份代码给出的答案是"从最短的 256 就开始胜出"，与讲义"prompt < 512 不值得"的说法矛盾。
- **TCP 与 RDMA 的差距随 prompt 变长而扩大**：`32768` 行相差 368.6 ms（= 32768 × 0.01125 ms），印证了"传输税 ∝ prompt 长度"。
- **"Read:" 文本与结果不符**：它说长 prompt 让分离式更划算，但从公式看，长 prompt 只会增加传输税；表中分离式胜出的幅度越来越大，是因为 cases 里输出长度也同步变长了。
- 我们额外用这两个函数验证了 crossover 确实存在、只是不在 cases 里：`(4096, 1)` 时 colocated 112.4 ms、RDMA 113.08 ms、TCP 159.16 ms，同机部署反而最快。
- 若把 `DECODE_TOK_PER_MS_DECODE_GPU` 改成与同机相同的 0.10，`(4096, 500)` 变成 colocated 5102.4 vs RDMA 5107.52——分离式在每一行都输，输的正好是传输时间。

---

## 7. 动手改一改

1. **讲义练习 1 的正确做法**：固定 `output = 1`、`10`、`50`，把 prompt 从 256 扫到 65536，找到 RDMA 与 TCP 各自的 crossover，验证它们满足 `prompt / output ≈ 3556 / 356`。
2. **让 Winner 三选一**：用 `min({"colocated": colo, "disagg-RDMA": rdma, "disagg-TCP": tcp}.items(), key=lambda kv: kv[1])` 输出真正最快的方案，并根据结果动态生成 "Read:" 结论。
3. **按真实结构算 KV**：把常数换成函数 `kv_bytes_per_token(layers=80, kv_heads=8, head_dim=128, bytes_per=1)`，重跑表格并对比练习 4 的数字；再试试误用查询头数 64 会得到什么。
4. **把硬件收益和架构收益拆开**：增加第四列"colocated on H200"（同机但 decode 速度 0.18），看看分离式相对它还有没有优势。
5. **加入成本**：给 H100、H200 设小时单价，按各阶段占用时间算每请求成本（参考测验 Q12），再引入 decode 批大小 B 把成本除以 B。
6. **进阶——建模干扰**：写一个离散时间的小模拟，同机 GPU 每一步要么处理一个 prefill 块、要么处理一批 decode；让长 prompt 的到来拖慢同批次 decode 的 TPOT，比较两种部署下的 TPOT P99。

---

## 8. 常见坑

- **把"换了更快的硬件"当成"分离的收益"**：本代码的胜负完全由 0.18 vs 0.10 决定；评估真实方案时要用相同硬件做对照组。
- **只看平均时延**：分离式真正的价值在 P99（干扰消失）和 goodput，单请求平均时延看不出来。
- **用查询头数算 KV**：70B 的 Llama 有 64 个查询头、8 个 KV 头，误用会高估 8 倍，导致错误地认为"传输太贵"。
- **混淆带宽单位**：`GB/s`（字节）和 `Gbps`（比特）相差 8 倍；代码里的 10 GB/s TCP 相当于 80 Gbps，在很多机房里过于乐观。
- **相信写死的结论文字**：打印的 "Read:" 不是计算结果，要自己从表里读结论。
- **只比较一半的列**：`winner` 没有考虑 TCP 列，如果你的集群只有 TCP，表里的胜者并不代表你的情况。
