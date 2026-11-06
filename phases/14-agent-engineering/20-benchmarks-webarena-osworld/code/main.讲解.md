# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 20 节 基准评测：WebArena 与 OSWorld ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），不需要浏览器、虚拟机或网络

---

## 1. 这份代码在考察什么

这份 157 行的代码把 WebArena / OSWorld 的两条评估思想做成一个可运行的玩具 harness：

1. **基于执行的评估（execution-based evaluation）**：不看 agent "说了什么"，而是在任务结束后检查应用的**最终状态**——订单里有没有正确的商品。对应讲义："Evaluation is execution-based via gym APIs — was the order placed, was the issue closed, was the CMS page updated?"
2. **轨迹效率（trajectory efficiency）**：用 agent 步数除以 gold（人类最少）步数，衡量"成功得有多绕"。对应讲义的 OSWorld-Human："top agents use 1.4-2.7x more steps than necessary"。

被测环境是一个最小的购物应用（类比 WebArena 的购物站），三个"agent"是写死的脚本函数。

> 一句话：**用一个有状态的购物应用 + 三个脚本 agent + "最终状态谓词 + 步数/金标准步数"两把尺子，演示 web/desktop agent 基准怎么打分**；同时也要看到：步数是从 agent 自报的 trace 数出来的、成功谓词不检查副作用、gold 步数并非最短——这些正是真实 harness 必须处理的度量问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ShoppingApp` | 类 | 商品表、购物车、订单列表；`list_items` / `add_to_cart` / `remove_from_cart` / `checkout` | 自托管的被测应用（gym 环境） |
| `Task` | dataclass | 任务 ID、描述、agent 函数、gold 步数、成功谓词 | 基准任务实例 |
| `_agent_task_1/2/3` | 函数 | 脚本化 agent：调用应用方法并返回文字 trace | 被测 agent（替身） |
| `main` | 函数 | 为每个任务新建应用 → 运行 agent → 检查状态 → 计算效率 → 汇总 | 评估 harness |

数据流：`Task` → `app = ShoppingApp()`（每任务重置）→ `trace = task.agent(app)` → `ok = task.success(app)`（状态检查）→ `steps = len(trace)`，`efficiency = steps / gold_steps` → 打印每任务结果 → 汇总成功率与 `总步数 / 总 gold 步数`。

---

## 3. 逐段精讲

### 3.1 `ShoppingApp`：最小的被测环境

```python
class ShoppingApp:
    def __init__(self) -> None:
        self.items = {
            "sku-001": {"name": "headphones", "price": 199},
            "sku-002": {"name": "keyboard", "price": 129},
            "sku-003": {"name": "mouse", "price": 59},
        }
        self.cart: dict[str, int] = {}
        self.orders: list[dict[str, Any]] = []

    def list_items(self) -> list[dict[str, Any]]:
        return [{"sku": sku, **meta} for sku, meta in self.items.items()]
```

- 三类状态：商品目录（只读）、购物车（sku → 数量）、订单列表（评估器检查的对象）。
- `list_items` 用列表推导式 + 字典解包，把 `{"sku-001": {"name": ..., "price": ...}}` 展平为 `[{"sku": "sku-001", "name": ..., "price": ...}, ...]`。
- 每个任务都会新建一个 `ShoppingApp`，相当于真实基准中"每个任务从同一快照启动"的**状态重置**。

```python
    def add_to_cart(self, sku: str, qty: int = 1) -> str:
        if sku not in self.items:
            return "error: unknown sku"
        self.cart[sku] = self.cart.get(sku, 0) + qty
        return f"added {qty} x {sku}"

    def remove_from_cart(self, sku: str) -> str:
        if sku not in self.cart:
            return "error: not in cart"
        del self.cart[sku]
        return f"removed {sku}"
```

- 错误以字符串返回而不是抛异常，agent 可以"看到"错误并调整——这与真实 web 页面显示错误提示类似。
- `self.cart.get(sku, 0) + qty`：不存在时从 0 开始累加。
- ⚠️ 没有检查 `qty`：我们实测 `add_to_cart("sku-001", -3)` 后 `checkout()` 生成了一个 `total = -597` 的订单。真实应用会校验输入，而 agent 在边界条件上的行为往往正是基准要测的东西。
- `remove_from_cart` 直接删除整个条目，不支持"减少数量"。

```python
    def checkout(self) -> str:
        if not self.cart:
            return "error: empty cart"
        total = sum(self.items[sku]["price"] * qty
                    for sku, qty in self.cart.items())
        oid = f"ord-{len(self.orders) + 1:03d}"
        self.orders.append({"oid": oid, "items": dict(self.cart), "total": total})
        self.cart = {}
        return oid
```

- 订单 ID 由订单数生成，`:03d` 补零到三位，如 `ord-001`。
- `dict(self.cart)` 复制一份购物车写入订单，之后再清空购物车——如果直接存 `self.cart` 的引用，后续修改购物车会"改写历史订单"。
- `total` 被计算并存储，但没有任何任务的成功谓词检查金额。

### 3.2 `Task`：把"成功"写成状态谓词

```python
@dataclass
class Task:
    tid: str
    description: str
    agent: Callable[[ShoppingApp], list[str]]
    gold_steps: int
    success: Callable[[ShoppingApp], bool]
```

- `success` 接收运行结束后的应用对象，返回布尔值——这就是"基于执行的评估"：判据是**环境状态**，与 agent 的输出文本无关。
- `gold_steps` 是人类最短路径的步数，用于计算效率。
- 注意 `agent` 字段直接绑定了一个脚本函数，所以每个任务的"agent"其实不同；真实基准中是**同一个 agent** 读取任务描述去完成所有任务。脚本 agent 也从不读取 `description`。

### 3.3 三个脚本 agent

```python
def _agent_task_1(app: ShoppingApp) -> list[str]:
    trace: list[str] = []
    trace.append(f"list_items -> {len(app.list_items())} items")
    trace.append(f"add_to_cart sku-001 -> {app.add_to_cart('sku-001')}")
    trace.append(f"checkout -> {app.checkout()}")
    return trace
```

- 每一步都在 f-string 里**调用**应用方法，并把返回值写进 trace。f-string 的 `{...}` 中可以放任意表达式，包括有副作用的方法调用——简洁，但阅读时容易忽略"这里修改了状态"。

```python
def _agent_task_2(app: ShoppingApp) -> list[str]:
    trace: list[str] = []
    trace.append(f"list_items")
    app.list_items()
    ...
```

- 这里先 `append` 一个**没有占位符的 f-string**（`f"list_items"`，代码检查工具会提示多余的 `f`），再单独调用 `app.list_items()` 并丢弃返回值。trace 行与真实操作只是"碰巧"一一对应。

```python
def _agent_task_3(app: ShoppingApp) -> list[str]:
    ...
    trace.append(f"add_to_cart sku-001 -> {app.add_to_cart('sku-001')}")
    trace.append(f"add_to_cart sku-002 -> {app.add_to_cart('sku-002')}")
    trace.append("revised_choice: remove keyboard")
    trace.append(f"remove_from_cart sku-002 -> {app.remove_from_cart('sku-002')}")
    trace.append(f"add_to_cart sku-003 -> {app.add_to_cart('sku-003')}")
    trace.append(f"checkout -> {app.checkout()}")
```

- 模拟一个"中途改主意"的 agent：先加了键盘，再删掉换成鼠标。这是讲义所说"轨迹效率差距"的缩影——结果正确，但走了弯路。
- ⚠️ `"revised_choice: remove keyboard"` 是一行"思考"，没有调用任何应用方法，却会被 `len(trace)` 计为一步。真实操作只有 6 次。

### 3.4 成功谓词

```python
            success=lambda app: any(
                o["items"].get("sku-001") == 1 for o in app.orders
            ),
            ...
            success=lambda app: any(
                o["items"].get("sku-001") == 1 and
                o["items"].get("sku-003") == 1 and
                "sku-002" not in o["items"]
                for o in app.orders
            ),
```

- `any(生成器)`：只要有一个订单满足条件就返回 `True`。
- `dict.get(key)` 在键不存在时返回 `None`，`None == 1` 为 `False`，所以不会报 `KeyError`。
- `revised_order` 的谓词额外要求"键盘不在订单里"，这是一个**不变量检查**（不该出现的东西没有出现）。
- ⚠️ `buy_headphones` 与 `buy_bundle` 的谓词没有这种检查。我们实测：同一单里多买一个鼠标、或先误下一单键盘再下一单耳机，`buy_headphones` 都判为成功——副作用没有被惩罚。更严格的写法见测验 Q9。
- 任务描述 "swap keyboard for mouse mid-order" 与谓词（耳机 + 鼠标、不含键盘）需要结合 agent 脚本才能看懂：应用初始购物车是空的，"swap" 指的是 agent 自己先加了键盘再换掉。

### 3.5 评估循环与汇总

```python
    for task in tasks:
        app = ShoppingApp()
        trace = task.agent(app)
        ok = task.success(app)
        steps = len(trace)
        efficiency = steps / task.gold_steps
        ...
        total_steps += steps
        total_gold += task.gold_steps

    print(f"  success rate:     {total_success}/{len(tasks)}")
    print(f"  step efficiency:  {total_steps / total_gold:.2f}x over gold")
```

- **状态重置**：`app = ShoppingApp()` 在循环内部，每个任务一个干净环境——满足 `outputs` 的硬规则 "never run one task on state dirtied by another"。如果把它移到循环外，第二个任务看到的 `orders` 里会有上一个任务的订单，`any(...)` 式的谓词就可能被上一个任务"代为满足"。
- **步数**：`len(trace)` 依赖 agent 自报，见 3.3 的问题。应在应用层记录真实操作（测验 Q10 的 `RecordingApp`）。
- **效率**：单任务是 `steps / gold_steps`；总体是"总步数 / 总 gold 步数"（`14 / 12 ≈ 1.17`），不是"各任务效率的平均"（`(1 + 1 + 1.4) / 3 ≈ 1.13`）。两种口径都可以，但要说明。
- 失败的任务也被计入总体效率；有些报告只对成功任务计算效率，口径同样需要注明。
- `outputs` 要求的耗时（elapsed time）与失败分类（grounding / planning）都没有实现。
- `field` 被导入却未使用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 内存中的购物应用 | 零依赖、可复现，类比"自托管 + 版本固定" | 没有页面、截图或 DOM，测不到 grounding；真实基准跑在容器/VM 中 |
| 每任务新建应用 | 状态重置，任务间互不污染 | 真实环境中重置成本高（快照恢复、VM 重启），需要专门的基础设施 |
| 成功 = 最终状态谓词 | 体现基于执行的评估，不依赖轨迹比对 | 谓词偏宽松，副作用不被惩罚；应加不变量检查 |
| 步数 = `len(trace)` | 实现最简单 | agent 自报不可靠，"思考"行被计数；应由环境记录操作 |
| gold 步数手写 | 演示效率指标 | `revised_order` 的 gold（5）大于最短路径（3–4），效率被高估；应由人工录制最短轨迹 |
| 脚本 agent 绑定到任务 | 不需要模型 | 不能代表"同一个 agent 面对不同任务"；没有决策、没有失败分类 |
| 总体效率用总和之比 | 一行代码 | 长任务权重更大；报告需注明口径，并给出每任务分布 |
| 应用不校验数量 | 代码短 | 负数数量产生负金额订单；被测应用应模拟真实约束 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值 |
| 类与实例属性 | `self.cart: dict[str, int] = {}` | 在 `__init__` 中声明带类型注解的属性 |
| 嵌套字典 | `{"sku-001": {"name": "headphones", "price": 199}}` | 用字典模拟商品表 |
| 列表推导 + 字典解包 | `[{"sku": sku, **meta} for sku, meta in self.items.items()]` | 把嵌套字典展平成列表 |
| `dict.items()` | `for sku, qty in self.cart.items()` | 同时遍历键和值 |
| `dict.get(key, default)` | `self.cart.get(sku, 0)`、`o["items"].get("sku-001")` | 缺省值避免 `KeyError`；不给默认值时返回 `None` |
| `del` | `del self.cart[sku]` | 删除字典条目 |
| 生成器 + `sum` | `sum(self.items[sku]["price"] * qty for sku, qty in self.cart.items())` | 计算总价 |
| `dict(...)` 复制 | `dict(self.cart)` | 浅拷贝，避免订单与购物车共享同一对象 |
| f-string 格式符 | `f"ord-{len(self.orders) + 1:03d}"`、`{efficiency:.2f}` | 补零三位、保留两位小数 |
| f-string 中调用方法 | `f"checkout -> {app.checkout()}"` | `{}` 中可放任意表达式（包括有副作用的调用） |
| 无占位符的 f-string | `f"list_items"` | 合法但多余，等价于普通字符串 |
| `@dataclass` + `Callable` 字段 | `agent: Callable[[ShoppingApp], list[str]]` | 把函数当作数据存进对象 |
| `lambda` + `any` | `lambda app: any(o["items"].get("sku-001") == 1 for o in app.orders)` | 一行写出"存在某订单满足条件" |
| 多行布尔表达式 | `a == 1 and \n b == 1 and \n "sku-002" not in ...` | 在括号内可以自由换行 |
| `not in` | `"sku-002" not in o["items"]` | 判断键不存在 |
| 隐式字符串拼接 | `f"  steps:   {steps}  (gold {task.gold_steps}, " f"efficiency {efficiency:.2f}x)"` | 相邻 f-string 自动连接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，瞬间完成，输出确定）：

```text
======================================================================
WEBARENA/OSWORLD-STYLE HARNESS — Phase 14, Lesson 20
======================================================================

[buy_headphones] buy the headphones
  success: True
  steps:   3  (gold 3, efficiency 1.00x)
    - list_items -> 3 items
    - add_to_cart sku-001 -> added 1 x sku-001
    - checkout -> ord-001

[buy_bundle] buy keyboard + mouse as a bundle
  success: True
  steps:   4  (gold 4, efficiency 1.00x)
    - list_items
    - add_to_cart sku-002 -> added 1 x sku-002
    - add_to_cart sku-003 -> added 1 x sku-003
    - checkout -> ord-001

[revised_order] swap keyboard for mouse mid-order
  success: True
  steps:   7  (gold 5, efficiency 1.40x)
    - list_items
    - add_to_cart sku-001 -> added 1 x sku-001
    - add_to_cart sku-002 -> added 1 x sku-002
    - revised_choice: remove keyboard
    - remove_from_cart sku-002 -> removed sku-002
    - add_to_cart sku-003 -> added 1 x sku-003
    - checkout -> ord-001

aggregate
  success rate:     3/3
  step efficiency:  1.17x over gold

WebArena: execution-based, gym APIs, state check decides success.
OSWorld-Human: gold trajectories reveal 1.4-2.7x step inefficiency.
```

逐项解读：

- **三个任务的订单号都是 `ord-001`**：说明每个任务都在新的应用实例上运行，状态重置生效。
- **前两个任务效率 1.00x**：脚本 agent 正好走了 gold 路径。
- **`revised_order` 1.40x**：恰好落在讲义 OSWorld-Human 的 1.4–2.7x 区间下沿，但这是"7 行 trace / 5"。改为由应用记录真实操作后是 6 步、1.20x；如果 gold 取真正的最短路径（不含 `list_items` 为 3 步，含则 4 步），效率是 2.0x 或 1.5x——gold 的定义比 agent 的表现对这个数字影响更大。
- **成功率 3/3、总体 1.17x**：总体效率是 `14 / 12`。若修正步数，总体为 `13 / 12 ≈ 1.08x`。
- **两点启示**：
  1. 成功率完全相同的 agent，效率可以差很多——只看成功率会漏掉成本与延迟差异（讲义："Ignoring trajectory length"）；
  2. 效率指标本身依赖"步数怎么数"和"gold 怎么定"，必须由环境记录、由人工校准。

---

## 7. 动手改一改

1. **（入门）** 新增任务"买两副耳机"（gold 3 步），写一个脚本 agent 和成功谓词；再写一个先加错商品后删除的 agent，观察效率变化。
2. **（度量修正）** 实现 `RecordingApp(ShoppingApp)` 在应用层记录每次操作，用 `len(app.actions)` 代替 `len(trace)`；再把 `revised_order` 的 gold 改成最短路径，比较前后的效率（测验 Q10）。
3. **（严格评估）** 写 `strict_success(expected_items)`：恰好一单、商品与数量完全一致、购物车为空；并给 `add_to_cart` 加上"数量必须为正整数"的校验（测验 Q9）。
4. **（讲义练习 3）** 给应用加一个 gold 轨迹从不使用的"干扰工具"（如 `view_reviews(sku)` 或 `apply_coupon(code)`），写一个会被它吸引的脚本 agent，统计"非 gold 操作"的次数。
5. **（讲义练习 1、`outputs` 第 5 条）** 增加第二个应用（论坛：发帖、回帖、关帖）并写 3 个任务与 gold 轨迹；为失败任务实现 grounding / planning 分类（测验 Q11），并记录每任务耗时。
6. **（进阶，讲义练习 4、5）** 阅读 OSWorld-G 与 WebArena 的应用说明，思考：如果把 `ShoppingApp` 换成一个真实的自托管网站，并让 agent 只能通过截图操作，harness 需要增加哪些组件（截图、坐标点击、元素命中记录、快照恢复）？

---

## 8. 常见坑

- **让被测 agent 自报步数**：思考行、重复记录、漏记都会扭曲效率；步数应由环境记录。
- **gold 不是最短路径**：gold 偏大会让 agent 看起来更高效；gold 应由人工录制最短路径并复核。
- **成功谓词只查目标不查副作用**：多买、多下单、改坏无关数据都可能被判为成功；要加不变量检查。
- **任务之间不重置状态**：后面的任务可能被前面任务的残留"代为完成"，所有分数失效。
- **混用聚合口径**：总和之比与平均比值结果不同；报告时注明口径并给出每任务数据。
- **截图基准上使用结构化接口**：在 OSWorld 上用 DOM/无障碍 API 会绕过 grounding，分数不可比；但为自己的产品搭 harness 时，`outputs` 建议截图与 DOM 都提供。
- **应用版本漂移**：自托管应用升级后不重新整理任务，前后分数不可比。
- **在 f-string 里调用有副作用的方法**：阅读时容易忽略状态被修改；关键操作最好单独成行。
