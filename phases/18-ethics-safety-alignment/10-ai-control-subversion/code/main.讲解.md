# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 10 节 AI 控制：面对蓄意破坏仍能保障安全 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

代码在一个"代码后门"玩具任务上模拟 Greenblatt et al.（arXiv:2312.06942, ICML 2024）比较的四种 control 协议：

1. **三种资源的分工**：U（不可信强模型，`u_produce`）、T（可信弱模型，`t_edit`）、H（预算有限的人工审计，`h_budget`）。
2. **四种协议**：baseline、upfront auditing、untrusted monitoring、trusted editing，各自在"有用性（useful）"与"安全性（发布后门率 backdoor）"之间的取舍。
3. **共谋（collusion）**：第二个 U 实例作为监控器时，可能放过同伙的后门。
4. **预算约束**：H 只能审计一部分输出，预算耗尽后协议的行为决定了安全性的上限。

> 一句话：**把"不信任 U 也要安全地用 U"变成可以扫描参数的计数实验**。但要清楚：玩具中 Trusted Editing 的胜利很大程度上是被建模假设"写死"的，Untrusted Monitoring 还多吃了一个记账 bug 的亏。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(23)` | 模块级语句 | 固定随机数 | 可复现 |
| `u_produce` | 函数 | U 以概率 `backdoor_rate` 产出后门 | 红队控制的 U |
| `t_edit` | 函数 | T 以 `t_skill` 移除后门；对良性输出以 5% 误拒 | Trusted Editing 中的 T |
| `untrusted_monitor` | 函数 | 第二个 U 实例打分；以 `collusion` 概率放过后门 | Untrusted Monitoring 与共谋 |
| `run_protocol` | 函数 | 按协议名分支，跑 n 条样本，打印 useful / backdoor / H used | 协议比较 |
| `main` | 函数 | 三种后门率 × 四种协议；再做共谋扫描 | 安全—有用性前沿 |

数据流：`main` → `run_protocol(name, ...)` → 每条样本 `u_produce` → 按协议调用 `t_edit` 或 `untrusted_monitor` → 根据 H 预算决定"审计 / 发布 / 丢弃" → 累计三个计数 → 打印比例。

---

## 3. 逐段精讲

### 3.1 `u_produce`：红队控制的 U

```python
def u_produce(backdoor_rate: float) -> tuple[str, bool]:
    is_backdoor = random.random() < backdoor_rate
    return ("useful" if not is_backdoor else "backdoor"), is_backdoor
```

- 每条输出独立地以 `backdoor_rate` 概率带后门，否则是有用的正确解答。
- 这是一个**非自适应**的红队：后门率固定，不看协议、不挑时机。讲义说论文中的红队"is allowed to see all protocol internals"，现实的红队会针对协议选择最优策略（比如极低的后门率，见测验 Q12）。
- 返回的字符串 `"useful"/"backdoor"` 在 `run_protocol` 中被 `_` 丢弃，真正用到的只有布尔值。

### 3.2 `t_edit`：可信弱模型 T 的编辑

```python
def t_edit(output: str, is_backdoor: bool, t_skill: float,
           overreject: float = 0.05) -> tuple[str, bool, bool]:
    if is_backdoor:
        if random.random() < t_skill:
            return ("useful", False, False)
        return ("backdoor", True, True)
    if random.random() < overreject:
        return ("rejected", False, True)
    return ("useful", False, False)
```

返回 `(编辑后的输出, 是否仍有后门, T 是否低置信度)`：

| 输入 | 概率 | 返回 | 含义 |
|------|------|------|------|
| 后门 | `t_skill`（0.7） | `("useful", False, False)` | T 移除后门，且结果**仍然有用** |
| 后门 | `1 − t_skill`（0.3） | `("backdoor", True, True)` | T 没移除，但**一定**标为低置信度 |
| 良性 | `overreject`（0.05） | `("rejected", False, True)` | T 误拒，标低置信度 |
| 良性 | 0.95 | `("useful", False, False)` | 原样通过 |

- ⚠️ **假设一：T 完美自知**。没能移除的后门 100% 被标为低置信度——等于说 T 知道自己什么时候失败。现实中"T 漏掉的后门"恰恰是 T 没察觉的那部分。
- ⚠️ **假设二：编辑零成本**。移除后门后的代码被视为"有用"，所以 Trusted Editing 的 useful 能**超过 baseline**。论文中 T 的编辑通常会降低正确率，这是 Trusted Editing 的主要代价。
- 参数 `output` 从未被使用（调用处传入 `"x"`）。

### 3.3 `untrusted_monitor`：另一个 U 当监控器

```python
def untrusted_monitor(is_backdoor: bool, collusion: float) -> bool:
    if not is_backdoor:
        return random.random() < 0.05
    if random.random() < collusion:
        return False
    return random.random() < 0.80
```

- 良性输出：5% 误报。
- 后门输出：先以 `collusion` 概率共谋（不标记）；不共谋时以 0.8 概率标记。所以后门被标记的总概率是 `(1 − c) × 0.8`。
- 共谋在这里被建模为每条样本独立的随机事件；讲义提到的共谋通道（隐写线索、共享先验）以及抗共谋手段（改写、混淆）都没有建模。

### 3.4 `run_protocol`：四种协议的计数逻辑

```python
    useful, shipped_backdoor, used_h = 0, 0, 0
    for _ in range(n):
        _, is_bd = u_produce(backdoor_rate)
        if name == "baseline":
            ...
```

**baseline**：良性 → useful；后门 → 发布。期望 useful = 1 − b，backdoor = b。

**upfront**：

```python
        elif name == "upfront":
            if used_h / n < h_budget:
                used_h += 1
                if not is_bd:
                    useful += 1
            else:
                if not is_bd:
                    useful += 1
                else:
                    shipped_backdoor += 1
```

- `used_h / n < h_budget` 是"先到先得"：只审计**前** `h_budget × n` 条（这里是前 100 条），之后全部直接发布。
- H 审计到后门就丢弃，审计到良性就发布。
- ⚠️ 没有"发现后门即停用 U（shutdown）"的逻辑，所以 upfront 只比 baseline 少发布前 10% 中的后门（200 种子平均：b = 0.1 时 0.0897 vs 0.0997）。在控制框架下，抓到一次后门本应是决定性的证据。

**untrusted**：

```python
        elif name == "untrusted":
            flagged = untrusted_monitor(is_bd, collusion)
            if flagged:
                if used_h / n < h_budget:
                    used_h += 1
                else:
                    if not is_bd:
                        useful += 1
                    else:
                        shipped_backdoor += 1
            else:
                ...
```

- 被标记且预算还在 → H 审计；预算耗尽 → 照常发布（包括被标记的后门）。
- ⚠️ **记账 bug**：H 审计到**良性**输出后没有 `useful += 1`，等于把审核通过的正确代码扔掉了；而 upfront 与 trusted_ed 分支都会计入。修复后 b = 0.1、c = 0.3 时 useful 从 0.858 升到 0.901（200 种子平均），发布后门率不变。

**trusted_ed**：

```python
        elif name == "trusted_ed":
            edited, still_bd, low_conf = t_edit("x", is_bd, t_skill)
            if low_conf and used_h / n < h_budget:
                used_h += 1
                if not is_bd:
                    useful += 1
            else:
                if edited == "useful":
                    useful += 1
                elif still_bd:
                    shipped_backdoor += 1
```

- T 低置信度且有预算 → H 审计（后门被抓、良性被放行）。
- 否则：T 编辑后有用就计 useful；仍有后门就发布；`"rejected"`（误拒且无预算）既不有用也不发布。
- 由于假设一，后门只有在 H 预算耗尽后才会被发布；低置信度事件比例为 `b × 0.3 + (1 − b) × 0.05`，b = 0.2 时恰为 0.10，与预算持平。

最后的打印：

```python
    print(f"\n{name:>12s}  useful={useful/n:.3f}  backdoor={shipped_backdoor/n:.3f}"
          f"  H used={used_h/n:.3f}")
```

两个相邻的 f-string 会被自动拼接成一个字符串；`{name:>12s}` 右对齐到 12 个字符。

### 3.5 `main`：两组实验

```python
    for br in (0.05, 0.10, 0.20):
        for proto in ("baseline", "upfront", "untrusted", "trusted_ed"):
            run_protocol(proto, backdoor_rate=br, h_budget=0.10, n=1000)

    for col in (0.0, 0.20, 0.50, 0.80):
        run_protocol("untrusted", backdoor_rate=0.10, h_budget=0.10, n=1000,
                     collusion=col)
```

- 第一组：三种后门率下比较四种协议，H 预算固定 10%。
- 第二组：共谋扫描。注意默认 `collusion=0.30`，所以第一组的 untrusted 都是 c = 0.3。
- ⚠️ 所有调用共享一个全局 RNG，每个配置只跑一次 1,000 样本，结论容易被噪声左右（见第 6 节的非单调现象）。
- TAKEAWAY 里的 "see Greenblatt 2023" 指 arXiv 2023 年 12 月的预印本，正式发表于 ICML 2024。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 后门率固定、非自适应 | 简单，可直接扫描 | 低估对手；control 评估要让红队知晓协议并选最优策略（例如极低频率植入） |
| 按"每条样本后门率"衡量安全 | 直观 | 控制框架下一次后门即不可接受，应按"整个部署期间从未发布后门的概率"衡量 |
| H 预算先到先得 | 实现简单 | 对手可以等预算耗尽后再攻击；应随机抽样审计并对 U 隐藏审计分布（讲义练习 3） |
| upfront 不 shutdown | 代码最短 | 浪费了"抓到一次就停用"这一最强信号 |
| T 完美自知 + 编辑零成本 | 突出"T 可信，无共谋" | 让 Trusted Editing 必胜；现实中 T 会漏报、编辑会降低正确率 |
| 共谋 = 独立随机事件 | 一个参数控制 | 真实共谋是策略性的（只对特定暗号放行），也有抗共谋手段可对抗 |
| untrusted 分支丢弃审计过的良性输出 | （疑为疏漏） | 低估 Untrusted Monitoring 的有用性 |
| 每配置只跑一次 | 运行快 | 应多种子平均并报告置信区间 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值 |
| 返回元组的类型注解 | `-> tuple[str, bool, bool]` | 说明返回三个值的类型 |
| 默认参数 | `overreject: float = 0.05`、`t_skill: float = 0.7, collusion: float = 0.30` | 调用时可省略，也可用关键字覆盖 |
| 关键字参数调用 | `run_protocol(proto, backdoor_rate=br, h_budget=0.10, n=1000)` | 按名字传参，可读性好、顺序无关 |
| 条件表达式 | `"useful" if not is_backdoor else "backdoor"` | 一行 if-else |
| 括号包裹的返回元组 | `return ("useful", False, False)` | 与不加括号等价 |
| 元组解包与 `_` 占位 | `_, is_bd = u_produce(backdoor_rate)` | 丢弃不需要的返回值 |
| 三元解包 | `edited, still_bd, low_conf = t_edit(...)` | 一次接收三个返回值 |
| 链式赋值初始化 | `useful, shipped_backdoor, used_h = 0, 0, 0` | 元组解包初始化多个计数器 |
| `if / elif` 分派 | `if name == "baseline": ... elif name == "upfront": ...` | 用字符串选择协议（更好的写法是字典映射到函数） |
| 嵌套条件 | `if flagged: if used_h / n < h_budget: ...` | 多层判断 |
| 布尔 `and` | `if low_conf and used_h / n < h_budget:` | 两个条件同时成立 |
| 遍历元组 | `for br in (0.05, 0.10, 0.20):` | 元组也可迭代 |
| f-string 对齐与精度 | `{name:>12s}`、`{useful/n:.3f}` | `>12` 右对齐宽 12；`.3f` 三位小数；花括号内可写表达式 |
| 相邻字符串字面量拼接 | `f"...{x}" f"...{y}"` | 编译期自动拼接，用于跨行写长字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行，方便在其他脚本中复用 `run_protocol` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 1 秒），并附 200 个种子的平均值作对照：

```text
-- backdoor-rate = 0.1, H budget = 0.10, n = 1000 --
    baseline  useful=0.897  backdoor=0.103  H used=0.000   ← 平均 0.900 / 0.100
     upfront  useful=0.886  backdoor=0.100  H used=0.100   ← 平均 0.900 / 0.090
   untrusted  useful=0.863  backdoor=0.042  H used=0.095   ← 平均 0.858 / 0.046
  trusted_ed  useful=0.967  backdoor=0.000  H used=0.086   ← 平均 0.970 / 0.000

-- backdoor-rate = 0.2, H budget = 0.10, n = 1000 --
    baseline  useful=0.803  backdoor=0.197  H used=0.000
     upfront  useful=0.793  backdoor=0.187  H used=0.100
   untrusted  useful=0.778  backdoor=0.122  H used=0.100   ← 预算耗尽
  trusted_ed  useful=0.944  backdoor=0.000  H used=0.091   ← 平均 backdoor 0.0023

-- collusion sweep on untrusted monitoring (backdoor_rate=0.10) --
collusion=0.0   untrusted  useful=0.848  backdoor=0.052  H used=0.100   ← 平均 0.035
collusion=0.2   untrusted  useful=0.867  backdoor=0.033  H used=0.100   ← 平均 0.041
collusion=0.5   untrusted  useful=0.855  backdoor=0.064  H used=0.081   ← 平均 0.060
collusion=0.8   untrusted  useful=0.865  backdoor=0.087  H used=0.048   ← 平均 0.084
```

逐项解读：

- **baseline**：useful + backdoor = 1，完全符合期望。
- **upfront**：useful 与 baseline 相同（审计的良性输出照常发布），只少了前 100 条里的后门，安全收益约 10%。没有 shutdown 规则是它表现差的根本原因。
- **untrusted**：发布后门率约为 baseline 的一半以下，但 useful 比 baseline 还低——一部分是 H 审计带来的"成本"，更多是记账 bug（审核通过的良性输出被丢掉）。b = 0.2 时标记量超过预算，H used = 0.100 封顶，安全性下降。
- **trusted_ed**：backdoor 为 0、useful 高于 baseline。两者都来自 3.2 节的两个过强假设；放宽为"50% 自知、50% 编辑后仍正确"后，我们测得 useful 0.935、backdoor 0.015（仍优于修复后的 untrusted：0.901 / 0.046，但不再"零风险、零成本"）。
- **共谋扫描的非单调**：c = 0 时标记率约 0.125 > 预算 0.10，预算在约第 800 条耗尽，之后被标记的后门照样发布；再叠加单次抽样噪声，才出现 0.052 > 0.033。多种子平均后是单调递增的。
- **H used 随共谋下降**（0.100 → 0.048）：共谋越多，被标记的后门越少，H 越"闲"——监控器"看起来很安静"恰恰可能是危险信号。

---

## 7. 动手改一改

1. **（入门）多种子平均**：把 `run_protocol` 改成返回 `(useful, backdoor, h_used)` 而不是打印，在 `main` 中对 50–200 个种子取平均并打印标准差。
2. **（入门）修复记账 bug**：在 `untrusted` 分支中，H 审计到良性输出时 `useful += 1`，重新比较四种协议。
3. **（进阶）现实化 Trusted Editing**：给 `t_edit` 增加 `miss_flag`（T 对漏掉的后门有多大概率自觉低置信）和 `edit_useful`（编辑后仍正确的概率）两个参数，再扫描 `t_skill`，画出 Trusted Editing 的安全—有用性曲线（讲义练习 1）。
4. **（进阶）shutdown 与整段安全度量**：给 upfront 和 trusted_ed 加上"H 一旦发现后门就停止使用 U"的规则，把安全性改为"1,000 题中从未发布后门"的概率（多次重复估计），并让红队在 b ∈ [0.0005, 0.05] 中搜索最差情形（参考测验 Q12）。
5. **（挑战）新协议**（讲义练习 2）：实现"T 低温度重采样，再让 U 编辑 T 的输出"。思考：U 的编辑权限让它可以在最后一步植入后门，而这一步没有任何人检查——为什么这比 Trusted Editing 失败得更彻底？
6. **（挑战）对 U 隐藏审计分布**（讲义练习 3）：把"先到先得"改成随机抽样审计，再实现一个"会等预算耗尽才攻击"的自适应红队，对比两种审计分配下的安全性。

---

## 8. 常见坑

- **相信玩具里的 "Pareto-dominates"**：它是由"T 完美自知 + 编辑零成本 + 对手记账 bug"共同造成的，不是从模拟中"发现"的。
- **单次运行下结论**：共谋扫描的非单调就是噪声 + 预算耗尽造成的假象。
- **只看 backdoor 率不看 H used**：H 预算是否耗尽决定了协议处于哪个区间，读结果时要同时看三列。
- **"先到先得"的审计**：对手只要等到预算用完再出手；审计应随机化，并对 U 隐藏。
- **用每条样本的后门率衡量安全**：控制框架关心的是"有没有发生过一次不可接受的结果"，两种度量会给出不同甚至相反的排序。
- **把 upfront 理解为"审计前 10% 然后放手"**：真正的价值在于"抓到一次就停用 U"，代码没有实现。
- **把 collusion 理解成"监控器能力不足"**：共谋是监控器**故意**放过，与 0.8 的检出能力是两个不同的参数。
