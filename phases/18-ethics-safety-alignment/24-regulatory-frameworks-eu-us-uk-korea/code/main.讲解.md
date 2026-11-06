# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 24 节 监管框架：欧盟、美国、英国、韩国 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（实际上只用到内置函数 `print`），无需网络

---

## 1. 这份代码在考察什么

本节是一节 **Learn（学习型）** 课，讲义标注"Languages: none"，Use It 一节甚至写着"No code"。但目录里仍有这个约 50 行的脚本：它把讲义里散落各处的监管里程碑汇总成**一条跨法域的统一时间线**并打印出来，最后给出一句总结。

它考察的不是编程技巧，而是：

1. **记住关键日期**：EU AI Act 的"生效 → 6 / 12 / 24 / 36 个月分阶段适用"，GPAI Code of Practice、第 50 条透明度守则的草案节奏，英美 AISI 更名，韩国 AI 基本法的通过—颁布—生效。
2. **跨法域并排看**：同一时间段里，欧盟在加码执法、英国在收窄范围、美国在转向 pro-growth、韩国在落地全面立法。
3. **把"法规数据"当作数据来管理**：这份脚本本身就是一个反面教材——日期格式、排序、精度、确定性都没有被结构化表示（见第 3、7 节）。

> 一句话：**时间线是合规映射的骨架**；但要让它能被程序查询和比较，日期精度、法域、事件类别必须显式建模。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 模块 docstring | 字符串 | 说明用途："Reference-only; primary sources cited in docs/en.md" | 事实来源在讲义 |
| `TIMELINE` | 列表，元素为 `(日期字符串, 事件描述)` 元组 | 14 条里程碑：EU AI Act 适用阶段 5 条、GPAI Code / 透明度守则 4 条、韩国 3 条、英国 1 条、美国 1 条 | 跨法域时间线 |
| `main()` | 函数 | 打印标题 → 逐条打印 → 打印 TAKEAWAY | 汇总结论 |
| `if __name__ == "__main__"` | 入口 | 直接运行时调用 `main()` | 脚本入口 |

数据流：`TIMELINE`（硬编码常量）→ `main()` 中 `for date, event in TIMELINE` 原样打印 → 固定的四行结论。

---

## 3. 逐段精讲

### 3.1 `TIMELINE`：硬编码的里程碑

```python
TIMELINE = [
    ("2024-08-01", "EU AI Act enters into force"),
    ("2024-12-00", "Korean AI Framework Act passed by National Assembly"),
    ("2025-01-00", "Korean AI Framework Act enacted (effective Jan 2026)"),
    ("2025-02-02", "EU AI Act: prohibited practices and AI literacy apply"),
    ("2025-02-00", "UK AISI renamed -> AI Security Institute"),
    ("2025-06-00", "US AISI renamed -> CAISI (Center for AI Standards and Innovation)"),
    ("2025-07-10", "GPAI Code of Practice published (3 chapters, 12 commitments)"),
    ("2025-08-02", "EU AI Act: GPAI + governance obligations apply"),
    ("2025-12-17", "Transparency Code for Article 50 first draft"),
    ("2026-01-00", "Korean AI Framework Act effective"),
    ("2026-03-00", "Transparency Code second draft"),
    ("2026-06-00", "Transparency Code final version"),
    ("2026-08-02", "EU AI Act: full applicability + Article 50 transparency + penalties"),
    ("2027-08-02", "EU AI Act: legacy GPAI + embedded high-risk systems"),
]
```

逐条对照讲义：

| 日期 | 事件 | 讲义原文 / 说明 |
|---|---|---|
| 2024-08-01 | EU AI Act 生效 | "In force 1 August 2024" |
| 2024-12 / 2025-01 / 2026-01 | 韩国法通过 / 颁布 / 生效 | "Passed December 2024. Enacted January 2025. Effective January 2026." |
| 2025-02-02 | 禁止性实践 + AI 素养 | 生效后约 6 个月（185 天） |
| 2025-02 | 英国 AISI 更名 | "AI Security Institute (February 2025)" |
| 2025-06 | 美国 CAISI | "US CAISI (June 2025)" |
| 2025-07-10 | GPAI Code of Practice 发布 | 三章、12 项承诺 |
| 2025-08-02 | GPAI + 治理 | 生效后 12 个月（366 天） |
| 2025-12-17 / 2026-03 / 2026-06 | 透明度守则第一稿 / 第二稿 / 定稿 | 讲义写"Final version June 2026"；第 23 节讲义注明"截至 2026 年 4 月仍是草案，时间表可能变化" |
| 2026-08-02 | 全面适用 + 第 50 条 + 罚则 | 生效后 24 个月（731 天） |
| 2027-08-02 | 存量 GPAI + 嵌入式高风险 | 生效后 36 个月（1096 天） |

值得注意的问题：

- ⚠️ **`-00` 伪日期**：用"第 0 天"表示"只知道月份"。`datetime.date.fromisoformat("2025-02-00")` 实测抛出 `ValueError: day is out of range for month`。ISO 8601 的月精度写法是 `2025-02`。
- ⚠️ **顺序不一致**：`"2025-02-02"` 排在 `"2025-02-00"` 前面；按字符串排序会把二者对调。打印时看不出问题，一旦有人"顺手 sort 一下"或做日期比较，结果就会改变。
- ⚠️ **确定性没有区分**：`2026-06-00 Transparency Code final version` 在讲义里是"预计"，却和已经发生的事件同样呈现。
- ⚠️ **缺少法域、类别字段**：只能靠描述文本里的 "EU AI Act:"、"Korean" 等前缀区分。
- 讲义提到的"Commission proposed adjusting the high-risk timeline to 16 months in late 2025"没有出现在时间线里，读者容易把 2026/2027 的高风险日期当成确定无疑。
- 列表元素是**元组** `(date, event)`，元组不可变，适合存放"一条记录"；但字段没有名字，读代码时只能靠位置理解含义。

### 3.2 `main()`：原样打印

```python
def main() -> None:
    print("=" * 78)
    print("AI REGULATORY TIMELINE (Phase 18, Lesson 24)")
    print("=" * 78)
    for date, event in TIMELINE:
        print(f"  {date}  {event}")
    print("\n" + "=" * 78)
    print("TAKEAWAY: EU AI Act sets the global bar. full enforcement August 2026.")
    ...
```

- `for date, event in TIMELINE` 在循环头里直接**解包**每个二元组。
- ⚠️ 循环变量名 `date` 与标准库 `datetime.date` 同名。本文件没有 import `datetime`，所以不冲突；但如果后续改造时 `from datetime import date`，循环变量就会遮蔽（shadow）这个类，导致难以发现的 bug。改名为 `day` 或 `when` 更安全。
- TAKEAWAY 的四句话对应讲义"Cross-jurisdiction dynamics"：欧盟设全球基准、英国收窄到前沿安全、美国转向 pro-growth、韩国是亚洲首部全面框架、多法域部署"comply with the strictest, which is usually the EU"。
- ⚠️ "full enforcement August 2026" 略有夸大：2027-08-02 仍有存量 GPAI 与嵌入式高风险系统的义务未适用，且委员会已提议调整高风险时间表。
- ⚠️ "comply with the strictest" 是简化说法：韩国的本地代表、美国州法的特定披露等义务在欧盟法中没有一一对应的条款，实践中要取各法域义务的**并集**（测验 Q17）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 硬编码列表 | 学习型课程，零依赖、一眼看完 | 法规会变（草案、提议调整）；生产中应放在可版本化的数据文件（YAML/JSON）并记录来源与核实日期 |
| 日期用字符串 | 打印方便 | 无法比较/计算；应用 `datetime.date` + 精度字段 |
| `-00` 表示月精度 | 让字符串看起来"对齐" | 非法日期、排序错乱；应写 `2025-02` 或单独记录精度 |
| 只有 `(日期, 描述)` 两个字段 | 简单 | 不能按法域/类别筛选；应使用 dataclass 或字典 |
| 不区分"已发生 / 预计" | 简化 | 合规判断可能把计划当事实；应加 `tentative` 标志 |
| 只打印，不提供查询 | 符合"Reference-only" | 讲义练习 2 那样的映射问题需要"某日已生效哪些义务"的查询能力 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的三引号字符串 | 模块说明，可用 `help(main)` 查看 |
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解；本文件只有 `-> None` 一处注解，实际可省略 |
| 元组列表 | `TIMELINE = [("2024-08-01", "..."), ...]` | 列表里每个元素是一个不可变的二元组 |
| 循环解包 | `for date, event in TIMELINE:` | 每次迭代把二元组拆成两个变量 |
| 返回类型注解 | `def main() -> None:` | 表示函数不返回值 |
| 字符串乘法与拼接 | `"=" * 78`、`"\n" + "=" * 78` | 生成分隔线；`\n` 是换行符 |
| f-string | `f"  {date}  {event}"` | 把变量插入字符串 |
| 主入口 | `if __name__ == "__main__": main()` | 直接运行时执行，被 import 时不执行（测验 Q10 中就是 import 了 `TIMELINE` 来复用数据） |
| （扩展）`datetime.date` | `date.fromisoformat("2026-08-02")`、`(d2 - d1).days` | 解析 ISO 日期、计算相隔天数；`"2025-02-00"` 会抛 `ValueError` |
| （扩展）`@dataclass(frozen=True)` | 测验 Q9 的 `Milestone` | 自动生成 `__init__`/`__repr__`/`__eq__`，`frozen=True` 使实例不可修改 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，耗时约 0.02 秒）：

```text
==============================================================================
AI REGULATORY TIMELINE (Phase 18, Lesson 24)
==============================================================================
  2024-08-01  EU AI Act enters into force
  2024-12-00  Korean AI Framework Act passed by National Assembly
  2025-01-00  Korean AI Framework Act enacted (effective Jan 2026)
  2025-02-02  EU AI Act: prohibited practices and AI literacy apply
  2025-02-00  UK AISI renamed -> AI Security Institute        ← 与上一行顺序颠倒
  2025-06-00  US AISI renamed -> CAISI (Center for AI Standards and Innovation)
  2025-07-10  GPAI Code of Practice published (3 chapters, 12 commitments)
  2025-08-02  EU AI Act: GPAI + governance obligations apply
  2025-12-17  Transparency Code for Article 50 first draft
  2026-01-00  Korean AI Framework Act effective
  2026-03-00  Transparency Code second draft
  2026-06-00  Transparency Code final version                  ← 讲义中为预计日期
  2026-08-02  EU AI Act: full applicability + Article 50 transparency + penalties
  2027-08-02  EU AI Act: legacy GPAI + embedded high-risk systems

==============================================================================
TAKEAWAY: EU AI Act sets the global bar. full enforcement August 2026.
UK narrowed to frontier security. US pivoted pro-growth. Korea is the
first Asian comprehensive framework. deployers in multiple jurisdictions
comply with the strictest, which is usually the EU.
==============================================================================
```

解读：

- 输出是确定性的（没有随机性），与源码中的列表一一对应。
- 从时间线可以读出 EU AI Act 的"6 / 12 / 24 / 36 个月"阶梯：2024-08-01 起分别相隔 185、366、731、1096 天（用 `datetime` 实际计算）。
- **韩国法比欧盟全面适用早约 7 个月生效**（2026 年 1 月 vs 2026-08-02）——对同时服务两地的公司，韩国义务先到期。
- 2025 年上半年英美两国的 AISI 更名紧挨在一起，与欧盟 2025-08-02 开始适用 GPAI 义务形成对照，这就是讲义说的"Competing regulatory philosophies"。

---

## 7. 动手改一改

1. **修正数据格式**：把 `-00` 改为月精度写法 `2025-02`，并让打印对齐（提示：`f"{day:<10}"`）；按日期排序后检查输出顺序的变化。
2. **结构化**：用测验 Q9 的 `Milestone` dataclass 重写 `TIMELINE`，增加 `jurisdiction`、`kind`、`tentative` 字段，打印时给预计日期加 `(planned)` 标记。
3. **按法域筛选**：加一个命令行参数（`sys.argv` 或 `argparse`），`python3 main.py --jurisdiction KR` 只打印韩国相关里程碑。
4. **查询某日状态**：实现 `milestones_on("2026-03-15")`，对月精度事件输出"本月内，无法确定"而不是武断地判为已发生（测验 Q10）。
5. **倒计时**：给定"今天"的日期，列出未来 365 天内即将适用的义务及剩余天数——这是合规团队最常用的视图。
6. **（讲义练习 2 的工具化）** 写一个 `map_deployment(provider, infra, users)`，按 `outputs/skill-regulatory-map.md` 的五个部分返回字典，并对 "is this deployment compliant" 这类问题返回"需要逐法域映射"而不是 True/False。

---

## 8. 常见坑

- **把"生效"当"适用"**：EU AI Act 2024-08-01 生效，但大部分义务 2026-08-02 才适用。
- **用字符串比较日期**：只有在格式严格一致（`YYYY-MM-DD`、无伪日期）时字符串比较才等价于日期比较。
- **`-00` 这类伪日期进入下游系统**：数据库或日期库会直接报错，或被静默转换成错误的日期。
- **把预计日期当既成事实**：草案时间表会变化（第 23 节讲义特别注明了这一点）。
- **循环变量遮蔽标准库名字**：`for date, event in ...` 在 `from datetime import date` 之后会覆盖 `date` 类。
- **读中文译文记错数字**：中文讲义把"15M EUR"译成"15万欧元"、把 GPAI 译成"全球公共管理倡议"，一定要对照英文原文；另外"15M / 3%"也只是罚则的其中一档（测验 Q12）。
