# 测验 · 论文写作器（Paper Writer）

> **阶段 19 · 综合项目 · 第 54 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 先骨架、后正文（skeleton first） | 从散文起笔会累积"结构债"；先把章节、图、引用声明为数据，再往槽位里生成正文，结构本身就是契约 |
| 2 | `Paper` 数据模型 | `Paper(title, authors, abstract, sections, figures, bibliography)`；`Section(id, title, body, cites, figure_refs)`、`Figure(id, path, caption, width)`、`BibEntry(key, entry_type, fields)` 都是普通 Python 数据 |
| 3 | 渲染契约 | 每个图输出 `\begin{figure}` 且标签为 `fig:<id>`；每个章节输出 `\section{}` 且标签为 `sec:<id>`；`references.bib` 恰好包含声明的条目 |
| 4 | 校验门（validation gates） | 讲义列 4 条：图 id 唯一、引用 key 已声明、摘要非空、标题非空；代码另加"bib key 唯一"和"引用的图 id 已声明"，共 6 条，失败抛 `PaperValidationError` |
| 5 | 图注入 | `read_experiment_manifest` 把实验清单 `{"name", "artifacts":[{"path","caption"}]}` 转成 `Figure`；id = 实验名 + 全局递增计数器，路径用 `os.path.relpath` 转成相对论文目录 |
| 6 | 可替换的正文生成器 | `ProseGenerator = Callable[[Section, Paper], str]`；测试用确定性的 `MockProseGenerator`，生产换成模型调用，外围流程不变 |
| 7 | LaTeX 转义 | `_escape_latex` 逐字符替换 `\ & % $ # _ { } ~ ^` 十个特殊字符；标题、作者、摘要、章节标题、图注会转义，**正文 body 原样输出** |
| 8 | 三件套输出 | `paper.tex` + `references.bib` + `manifest.json`；下游（55 节 critic）读 manifest，不解析 LaTeX——manifest 才是契约 |
| 9 | "要么全写，要么不写" | 校验失败时不写任何文件；但代码在校验前就调用了正文生成器、修改了输入对象、创建了输出目录，三个文件的写入也不是原子的 |
| 10 | 扩展方向 | 多格式渲染（Markdown/HTML，渲染器做成策略）、按引用 key 自动补全 BibTeX；都不需要改动骨架契约 |

### 核心技能（能动手做到）

- [ ] 用 dataclass 定义一篇论文的结构，并手写出它渲染后的 LaTeX 骨架（标签、图块、参考文献命令）
- [ ] 说出 `_validate` 的 6 道门各拦截什么错误，以及它**拦不住**的错误（例如正文里幻觉出来的 `\cite`）
- [ ] 正确转义 LaTeX 特殊字符，并解释为什么正文中一个未转义的 `%` 会"静默吞掉"后半行内容
- [ ] 把实验产物路径规范化为相对论文目录的路径，并检查图文件是否存在
- [ ] 写一个可注入的正文生成器（mock 或模型），让测试不依赖模型
- [ ] 把多文件输出改造成"先校验、后生成、暂存目录 + 原子替换"的事务式写入

---

## 二、基础自测（选择题）

**Q1.** 讲义主张"先建骨架，再填正文"。下列哪一项最准确地说明了理由？

- A. 结构作为数据提前声明，harness 可以在写任何正文之前校验"每个图都有槽位、每个引用都有条目、每个章节都在目录里"，避免散文式写作累积结构债
- B. LaTeX 编译器要求先写骨架
- C. 骨架可以让模型生成得更快
- D. 骨架能自动修正引用格式

**Q2.** 下列哪一条**不是** `_validate` 实际执行的校验？

- A. 标题去空白后不能为空
- B. 参考文献的 key 不能重复
- C. 每个声明的图都必须被至少一个章节引用
- D. 章节 `figure_refs` 中的 id 必须是已声明的图

**Q3.** `_escape_latex("R&D 50%")` 的返回值是：

- A. `"R&D 50%"`（只转义反斜杠）
- B. `"R\&D 50\%"`
- C. `"R\\&D 50\\%"`（每个特殊字符前加两个反斜杠）
- D. `"R{&}D 50{%}"`

**Q4.** 对 `Section(id="intro", ...)` 和 `Figure(id="loss-curve-1", ...)`，渲染器生成的标签分别是：

- A. `intro`、`loss-curve-1`
- B. `section:intro`、`figure:loss-curve-1`
- C. `sec-intro`、`fig-loss-curve-1`
- D. `sec:intro`、`fig:loss-curve-1`

**Q5.** demo 中两个实验清单依次为 `{"name": "loss-curve", 1 个产物}` 和 `{"name": "ablation", 1 个产物}`。`read_experiment_manifest` 生成的图 id 是：

- A. `loss-curve-1`、`ablation-1`
- B. `loss-curve-1`、`ablation-2`
- C. `fig-1`、`fig-2`
- D. `loss-curve`、`ablation`

**Q6.** 为什么正文生成器是注入 `PaperWriter` 的一个可调用对象（`prose: ProseGenerator`），而不是 `PaperWriter` 自己的方法？

- A. Python 的 dataclass 不能定义方法
- B. 为了让生成器可以并行运行
- C. 测试可以注入确定性的 `MockProseGenerator`，生产注入模型调用，校验、渲染、写文件的流程完全不变
- D. 因为 LaTeX 渲染器要求如此

**Q7.** 讲义说 "The manifest is part of the contract and the LaTeX is not"。这句话的含义是：

- A. 下游的 critic loop、仪表盘读取结构化的 `manifest.json`（章节、图、引用列表），而不去解析 LaTeX；LaTeX 排版细节可以变，manifest 的字段不能随意变
- B. LaTeX 文件不会被写入磁盘
- C. manifest 包含完整的论文正文
- D. manifest 是给 LaTeX 编译器读的

**Q8.** 某章节 `cites=[]`，但模型生成的 body 是 `"As shown by \cite{ghost2099}."`，参考文献中没有 `ghost2099`。调用 `render_latex` 会怎样？

- A. 抛出 `PaperValidationError: unknown bibliography key`
- B. 自动把 `ghost2099` 加入参考文献
- C. 把 `\cite{ghost2099}` 从正文中删除
- D. 校验通过、正常渲染；问题要到 LaTeX/BibTeX 编译时才以"引用未定义"的形式暴露

---

## 三、动手 / 代码题

**Q9.** 阅读 `PaperWriter.write` 的开头：

```python
    def write(self, paper: Paper, out_dir: str) -> dict:
        os.makedirs(out_dir, exist_ok=True)
        self.fill_prose(paper)
        tex = render_latex(paper)        # 内部第一步才是 _validate(paper)
        bib = render_bibtex(paper)
        ...  # 依次写 paper.tex、references.bib、manifest.json
```

我们构造了一个标题为空、有两个空 body 章节的论文，传入一个会记录调用的生成器。实测：抛出 `PaperValidationError: title is empty`，但生成器**已被调用两次**，两个章节的 `body` 都被改成了生成内容，`out_dir` 被创建为空目录。

1. 指出这里与讲义"在写任何正文之前就能校验""no partial write"不一致的三处问题，并说明在生产中（生成器是付费模型调用）各自的后果。
2. 重写 `write`，做到：先校验、不修改调用方对象、三个文件要么全部出现要么都不出现。

**Q10.** 正文 body 不做转义：

```python
        lines.append(sec.body if sec.body else "% body pending")
```

我们渲染了 body 为 `"Accuracy improved by 5% over & baseline"` 的章节，`pdflatex` 编译**成功、没有任何报错**，但 PDF 中只剩下 `Accuracy improved by 5`。

1. 解释为什么没有报错却丢了内容。
2. 为什么不能简单地对 body 调用 `_escape_latex`？
3. 设计一个"占位符"方案：生成器输出纯文本 + `[[fig:<id>]]`、`[[cite:<key>]]` 标记，由写作器负责转义和替换，并顺便解决 Q8 的幻觉引用问题。写出 `render_body` 函数。

**Q11.** `BibEntry.to_bibtex` 的实现：

```python
        for k, v in sorted(self.fields.items()):
            safe = str(v).replace("{", "").replace("}", "")
            lines.append(f"  {k} = {{{safe}}},")
```

对 `title = "{BERT}: Pre-training & {Fine}-tuning"`，实测 BibTeX 生成的参考文献条目变成了 `Bert: Pre-training & fine-tuning.`，随后 `pdflatex` 报错 `! Misplaced alignment tab character &.`。

1. 解释两个问题各自的原因。
2. 改写字段值的处理方式：保留（并检查）成对的花括号，转义 `& % $ # _`。

**Q12.** demo 的实验清单使用相对路径 `figs/loss.pdf`，输出目录是一个临时目录。实测 `paper.tex` 中的图路径是 `../../home/claude/work/phases/19-capstone-projects/54-paper-writer/code/figs/loss.pdf`。

1. 这个路径是怎么算出来的？为什么换一个工作目录运行，生成的 LaTeX 就不同？
2. 讲义说 harness 可以 "list missing figure files"，但代码并没有检查文件是否存在。请改写 `read_experiment_manifest`：清单携带 `base_dir`，相对路径相对它解析，同时返回缺失文件列表。

---

## 四、面试高频题

**Q13.**（基础必考）用 LLM 生成长文档（论文、报告、设计文档）时，为什么推荐"结构即契约 / 先骨架后填充"？它和直接让模型一次写完相比有什么优劣？

**Q14.**（原理深挖）LLM 写论文最危险的问题之一是"幻觉引用"。本节的设计挡住了哪一部分？还漏了哪些？你会怎样做成端到端可验证的引用管线？

**Q15.**（工程实践）一个写作器要输出多个相互依赖的文件（tex、bib、manifest），并且可能被重试。如何保证原子性和幂等性？

**Q16.**（场景设计）同一个 `Paper` 需要同时输出 LaTeX（投稿）、Markdown（博客）、HTML（预览）。请给出设计，并说明正文中的图引用和引用文献在三种格式中如何表示。

**Q17.**（追问型）本节用 `MockProseGenerator` 测试写作器。mock 能保证什么、保证不了什么？接入真实模型后你会怎样测试和评估？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："A skeleton inverts that. The structure is declared up front as data... The harness can validate, before any prose is written, that every figure has a slot, every citation has an entry, and every section appears in the table of contents." 并且这与前面课程对计划、工具调用、trace 的做法一脉相承："The structure is the contract."

- B 错：LaTeX 并不要求"先写骨架"，这是工程纪律而不是编译器规定。
- C 错：骨架与生成速度无关。
- D 错：骨架只能发现问题，不会自动修正。

### Q2 — 答案：C

`_validate` 实际做 6 件事：标题非空、摘要非空、图 id 唯一、bib key 唯一、章节 `cites` 都已声明、章节 `figure_refs` 都已声明。它**不要求**每个图都被引用——声明了却没人引用的图会照常渲染到文末。讲义只列了 4 条（没有"bib key 唯一"和"图引用存在"），代码更严格。另外注意 A 用的是 `.strip()`，纯空白标题同样被拒绝。

### Q3 — 答案：B

```python
    repl = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", ...}
    for ch in text:
        out_chars.append(repl.get(ch, ch))
```

逐字符替换，`&` → `\&`、`%` → `\%`。C 是把 Python 字符串的 repr 当成了实际内容（在 repr 中反斜杠会显示成 `\\`）。逐字符而不是 `str.replace` 链式替换有一个好处：替换结果中新出现的 `\`、`{`、`}` 不会被二次转义。实测 `_escape_latex(r"50% of R&D costs $3 #1 a_b {x} ~ ^ \ ")` 的结果为 `50\% of R\&D costs \$3 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{} \textbackslash{} `。

### Q4 — 答案：D

```python
    @property
    def label(self) -> str:
        return f"sec:{self.id}"      # Section
        ...
        return f"fig:{self.id}"      # Figure
```

讲义的渲染契约："a stable label of the form `fig:<id>`... `sec:<id>`"。标签由 id 派生且稳定，交叉引用 `\ref{fig:...}` 才不会断。

### Q5 — 答案：B

```python
    counter = 0
    for m in manifests:
        ...
        for art in artifacts:
            ...
            counter += 1
            fid = re.sub(r"[^a-zA-Z0-9]+", "-", f"{name}-{counter}").strip("-").lower()
```

计数器在**所有清单之间共享**，不会在每个实验内部重置，所以第二个实验的图是 `ablation-2`。A 是"每个实验各自计数"的误解。全局计数器的好处是：即使两个实验名规范化后相同（实测 `"a b"` 与 `"a-b"` 都变成 `a-b`），id 也不会冲突（得到 `a-b-1`、`a-b-2`）。代价是：在列表前面插入一个新实验，后面所有图的 id 都会变，章节里写死的 `figure_refs` 随之失效。

### Q6 — 答案：C

讲义："the test substitutes a deterministic one, production substitutes a model one, the rest of the pipeline is identical." 这是依赖注入：`PaperWriter` 只依赖"一个接受 `(Section, Paper)`、返回 `str` 的可调用对象"这个接口。`MockProseGenerator` 实现了 `__call__`，所以实例本身就可调用；测试里甚至可以直接传 `lambda s, p: ""`。A 错（dataclass 可以有方法，`PaperWriter` 本身就有 `fill_prose`、`write`）；B、D 与设计无关。

### Q7 — 答案：A

讲义："The manifest is what a downstream evaluator or critic loop reads. It does not parse LaTeX; it reads the manifest. The next lesson, the critic loop, takes this manifest as input." 结构化数据是给机器消费的稳定接口；LaTeX 是给排版系统和人看的，模板、宏包、措辞都可能变。B 错（tex 会写入）；C 错（manifest 只记 `body_chars`，不含正文）；D 错。

### Q8 — 答案：D

`_validate` 只检查结构化字段 `sec.cites` 和 `sec.figure_refs`，从不扫描 body 文本。实测 body 为 `As shown by \cite{ghost2099} and Figure~\ref{fig:nope}.` 的论文校验通过、渲染成功。编译时 LaTeX 只会给出 "Citation ... undefined" 警告，PDF 中显示 `[?]`。在 mock 生成器下这不是问题（mock 只引用 `section.cites` 中的 key），但换成真实模型后，模型完全可能"编"出不存在的引用。修法见 Q10、Q14。

### Q9 — 参考答案

1. 三处问题：
   - **生成先于校验**：`fill_prose` 在 `render_latex`（内含 `_validate`）之前执行。生产中生成器是模型调用：一篇结构不合法的论文会先花掉 N 次付费调用和几十秒延迟，最后才因为"标题为空"失败。讲义的说法是"validate, before any prose is written"。
   - **修改调用方对象**：`fill_prose` 直接给 `sec.body` 赋值。失败后调用方手里的 `Paper` 已经被污染；重试时这些章节 body 非空，就**不会再生成**，于是重试会带着上一次的（可能是半成品的）正文继续，行为与首次调用不同。
   - **部分写入**：`os.makedirs` 在校验前就创建了空目录；三个文件依次写入，若写完 `paper.tex` 后磁盘满或进程被杀，就会留下 tex 与 bib/manifest 不一致的目录。下游的 critic 若只检查"目录存在"，会读到不完整的产物。
2. 参考实现（已实测：非法论文时生成器调用 0 次、输入未被修改、输出目录不存在；合法论文时三个文件全部出现）：

```python
import copy, shutil, tempfile

    def write(self, paper: Paper, out_dir: str) -> dict:
        _validate(paper)                         # 1. 先验结构，不调用生成器
        filled = copy.deepcopy(paper)            # 2. 不修改调用方对象
        for sec in filled.sections:
            if not sec.body:
                sec.body = self.prose(sec, filled)
        tex = render_latex(filled)               # 生成后再验一次（防止生成器改了结构）
        bib = render_bibtex(filled)
        manifest = self._manifest(filled, out_dir)   # 原 manifest 构造逻辑抽成方法

        parent = os.path.dirname(os.path.abspath(out_dir)) or "."
        os.makedirs(parent, exist_ok=True)
        staging = tempfile.mkdtemp(prefix=".paper-staging-", dir=parent)  # 与目标同一文件系统
        try:
            for name, content in (("paper.tex", tex), ("references.bib", bib)):
                with open(os.path.join(staging, name), "w", encoding="utf-8") as f:
                    f.write(content)
            with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
            if os.path.exists(out_dir):
                shutil.rmtree(out_dir)
            os.replace(staging, out_dir)         # 3. 目录级换名
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return manifest
```

   说明：`os.replace` 在同一文件系统内是原子的，所以暂存目录要建在目标目录的父目录下；"先删旧目录再换名"之间仍有一个很短的窗口，更严格的做法是写到带版本号的新目录，再原子地切换一个指向它的符号链接。

### Q10 — 参考答案

1. `%` 在 LaTeX 中是**注释符**，从它到行尾的内容全部被忽略。`5% over & baseline` 中，`%` 后面的 ` over & baseline` 整段被注释掉——连本该报错的 `&` 也一起被注释了，所以编译成功、没有任何警告，内容却静默丢失（实测 `pdftotext` 输出只有 `Accuracy improved by 5`）。这比编译失败更危险：写作器和 critic 都以为正文完整。
2. 当前的 body 是"受信任的 LaTeX"：`MockProseGenerator` 会故意输出 `Figure~\ref{fig:...}`、`~\cite{...}` 这样的命令。如果整体转义，这些命令会变成字面文本 `\textbackslash{}ref\{...\}`，交叉引用全部失效。问题在于"命令"和"文本"混在同一个字符串里。
3. 占位符方案——生成器只输出纯文本和受控标记，写作器负责全部 LaTeX 细节（已实测）：

```python
import re

_TOKEN = re.compile(r"\[\[(fig|cite):([A-Za-z0-9_\-:.]+)\]\]")

def render_body(text: str, fig_ids: set[str], bib_keys: set[str]) -> str:
    out, pos = [], 0
    for m in _TOKEN.finditer(text):
        out.append(_escape_latex(text[pos:m.start()]))     # 普通文本全部转义
        kind, key = m.group(1), m.group(2)
        if kind == "fig":
            if key not in fig_ids:
                raise PaperValidationError(f"body references unknown figure id {key!r}")
            out.append(f"Figure~\\ref{{fig:{key}}}")
        else:
            if key not in bib_keys:
                raise PaperValidationError(f"body cites unknown bibliography key {key!r}")
            out.append(f"\\cite{{{key}}}")
        pos = m.end()
    out.append(_escape_latex(text[pos:]))
    return "".join(out)
```

   实测：`"Accuracy improved by 5% over R&D baseline [[cite:smith2020]], see [[fig:loss-curve-1]]."` → `Accuracy improved by 5\% over R\&D baseline \cite{smith2020}, see Figure~\ref{fig:loss-curve-1}.`；`"as [[cite:ghost2099]] showed"` → `PaperValidationError: body cites unknown bibliography key 'ghost2099'`。

   好处：(1) 转义成为写作器的职责，生成器（模型）不必懂 LaTeX；(2) body 中出现的每个引用都在渲染时被校验，幻觉引用被拦下；(3) 同一套标记可以渲染成 Markdown/HTML（Q16）。还可以顺便把 body 中实际出现的 key 收集起来，与 `sec.cites` 对账，写进 manifest。

### Q11 — 参考答案

1. **大小写丢失**：BibTeX 的 `plain` 样式会把标题转成"句首大写"，只有被 `{...}` 包住的部分保持原样。`{BERT}` 正是作者用来保护缩写大小写的写法，代码把所有花括号删掉后，BibTeX 输出 `Bert`、`fine-tuning`。**编译错误**：`&` 在 LaTeX 中是表格列分隔符，BibTeX 会把字段内容原样抄进 `.bbl`，正文中出现裸 `&` 就报 `Misplaced alignment tab character`。删花括号本意是"防止破坏 `{...}` 定界"，但它既破坏了合法用法，又没有处理真正危险的字符。
2. 改写（已实测：BibTeX 输出 `{BERT}: Pre-training \& {Fine}-tuning.`，pdflatex 退出码 0）：

```python
_BIB_SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}

def _bib_value(v) -> str:
    s = str(v)
    depth = 0
    for ch in s:                      # 只要求花括号成对，而不是全部删除
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            raise PaperValidationError(f"unbalanced braces in {s!r}")
    if depth:
        raise PaperValidationError(f"unbalanced braces in {s!r}")
    return "".join(_BIB_SPECIAL.get(ch, ch) for ch in s)

    def to_bibtex(self) -> str:
        lines = [f"@{self.entry_type}{{{self.key},"]
        for k, v in sorted(self.fields.items()):
            lines.append(f"  {k} = {{{_bib_value(v)}}},")
        lines.append("}")
        return "\n".join(lines)
```

   注意不要转义 `\`：BibTeX 字段里常有 `{\"o}` 这类重音写法。另外还应校验 key 只含安全字符（字母、数字、`:-_`），并把"花括号不平衡"作为新的校验门放进 `_validate`，在写文件之前失败。

### Q12 — 参考答案

1. `os.path.relpath("figs/loss.pdf", "/tmp/paper-writer-demo-xxx")` 会先把**相对路径按当前工作目录**解析成绝对路径（`<cwd>/figs/loss.pdf`），再计算它相对论文目录的路径。我们在 `code/` 目录下运行，于是得到 `../../home/.../code/figs/loss.pdf`。换个目录运行，cwd 不同，结果就不同——同样的输入产生不同的 `paper.tex`，违反了"确定性注入"的目标（讲义："The injection is deterministic"）。我们在本地做了验证：在 `figs/` 的父目录下运行、输出到同级的 `out/`，路径变为 `../figs/loss.pdf`，补上占位 PDF 后 `pdflatex → bibtex → pdflatex ×2` 能无错误编译出 2 页 PDF。
2. 参考实现（已实测：`os.chdir("/")` 之后结果依然是 `../figs/loss.pdf`，并报告了不存在的 `figs/none.pdf`）：

```python
def read_experiment_manifest(manifests, paper_dir):
    figs, missing, counter = [], [], 0
    for m in manifests:
        name = m.get("name", "exp")
        base = m.get("base_dir")                     # 清单自己所在的目录
        for art in m.get("artifacts", []):
            path = art.get("path", "")
            if not path:
                continue
            if not os.path.isabs(path):
                if base is None:
                    raise ValueError(f"manifest {name!r}: relative path {path!r} needs base_dir")
                path = os.path.join(base, path)
            path = os.path.normpath(path)
            if not os.path.exists(path):
                missing.append(path)
            counter += 1
            fid = re.sub(r"[^a-zA-Z0-9]+", "-", f"{name}-{counter}").strip("-").lower()
            figs.append(Figure(id=fid, path=os.path.relpath(path, paper_dir),
                               caption=art.get("caption", "") or name))
    return figs, missing
```

   `missing` 可以写进 manifest，或者作为第 7 道校验门（"图文件必须存在"）。Windows 上 `relpath` 跨盘符会抛 `ValueError`，原代码的 `except ValueError: rel = path` 就是在处理这种情况，可以保留。

### Q13 — 参考回答要点

- **为什么**：
  - 长文档的主要失败是**结构性**的：章节内容错位、图在定义前被引用、重复或缺失的参考文献、遗漏必需章节。这些在"结构即数据"时可以用代码在生成前检查，而散文生成后再修复成本高（讲义："the rewriting cost is higher than the writing cost"）。
  - 分槽生成：每个章节单独调用模型，上下文更短、更聚焦，可以并行、可以单独重试。
  - 产物可机读：manifest 让下游 critic、仪表盘、评估无需解析自然语言。
  - 可测试：用 mock 生成器即可覆盖全部结构逻辑。
- **代价**：
  - 章节之间的衔接、全文叙事连贯性需要额外处理（例如把前文摘要传给下一章节，或最后做一次全局润色）；
  - 骨架本身可能不合理，需要允许"修改骨架"的回路（55 节 critic 可以提出结构性意见）；
  - 生成器有可能越界（在正文里引入骨架外的引用、图），需要 Q10 这样的约束。
- 加分点：与 Agent 中"先 plan 再 execute"（[阶段 19 · 24](../../24-plan-execute-control-flow/docs/zh.md)）同构；结构化输出（JSON schema）是同一思想在单次调用上的体现。

### Q14 — 参考回答要点

- **本节挡住的**：结构化字段 `sec.cites` 中的每个 key 必须出现在 `paper.bibliography` 中；`references.bib` 只包含声明的条目。
- **漏掉的**：
  - body 文本中的 `\cite{...}` 不受校验（Q8）；
  - `BibEntry` 本身可能是编造的——字段由谁填写？如果由模型生成标题、作者、年份，整个条目就可能不存在；
  - 引用存在，但不支持正文中的论断（"引用错配"）。
- **端到端可验证的引用管线**：
  1. 引用来源只能是检索结果：51 节的文献检索返回带 ID 的论文记录，`BibEntry` 只能由这些记录生成，不允许模型手写；
  2. 生成时只给模型可用 key 列表，输出用 `[[cite:key]]` 标记，渲染时校验（Q10）；
  3. 对条目做外部核验（DOI / arXiv ID 查询，标题与作者匹配）；
  4. 论断级核验：抽取"论断—引用"对，用检索到的摘要做蕴含判断（可交给 55 节 critic）；
  5. manifest 记录每个引用出现在哪个章节，便于审计。
- 常见误区：以为"BibTeX 编译通过 = 引用真实"。编译只检查 key 能否对上。

### Q15 — 参考回答要点

- **原子性**：
  - 所有内容先在内存中生成完毕并通过校验，再开始写盘；
  - 写入与目标同一文件系统的暂存目录，全部成功后 `os.replace` 换名（单文件同理：写临时文件 + `fsync` + rename）；
  - 失败时清理暂存目录；
  - 需要"多版本 + 切换"时，用带版本号的目录 + 原子更新的符号链接或指针文件。
- **幂等性**：
  - 输入（Paper + 生成器配置 + 模型版本）的哈希作为输出目录名或写进 manifest；相同输入的重试直接复用结果；
  - 不修改调用方对象（Q9），保证重试的输入与首次相同；
  - 生成结果缓存（按章节 id + 输入哈希），重试时只补生成失败的章节，节省模型调用；
  - manifest 中不要写绝对路径、时间戳等每次都会变的内容，或单独放在"运行元数据"字段中（本节 manifest 中的 `tex_path` 就是绝对路径）。
- 加分点：下游读取方应先检查 manifest 是否存在且版本匹配，再读其它文件——manifest 最后写入，可以充当"提交标记"。

### Q16 — 参考回答要点

- **结构**：讲义的方向——"The renderer becomes a strategy on `Paper`"。定义 `Renderer` 协议：`render(paper) -> dict[str, str]`（文件名 → 内容），实现 `LatexRenderer`、`MarkdownRenderer`、`HtmlRenderer`；校验 `_validate` 与格式无关，放在渲染器之外统一执行。
- **正文表示**：正文用与格式无关的中间表示——纯文本 + `[[fig:id]]` / `[[cite:key]]` 标记（Q10），或更完整的 AST（段落、强调、列表、公式节点）。每个渲染器负责自己的转义规则：LaTeX 转义 `& % $ ...`，HTML 转义 `< > &`，Markdown 转义 `* _ [ ]` 等。
- **图引用**：LaTeX 用 `\label{fig:id}` + `\ref`；HTML 用 `<figure id="fig-id">` + `<a href="#fig-id">Figure 2</a>`，编号由渲染器按出现顺序计算；Markdown 用图片语法 + 锚点或文字编号。
- **引用文献**：LaTeX 交给 BibTeX；HTML/Markdown 由渲染器自己按样式生成参考文献列表和 `[1]` 编号，或使用 CSL 这类引用样式处理器。
- **manifest 与格式无关**：所有渲染器共享同一份 manifest，critic 无需关心格式。
- 常见误区：先生成 LaTeX 再用工具转换成 HTML——转换器难以完全覆盖自定义宏，错误难以追溯。

### Q17 — 参考回答要点

- **mock 能保证**：结构逻辑——校验门、标签、图块、bib 输出、manifest 字段、文件写入；而且确定、快速，适合单元测试（本节 15 个测试 0.03 s 跑完）。
- **mock 保证不了**：
  - 模型输出的格式合规性：特殊字符（Q10 的 `%`）、幻觉引用（Q8）、超长输出、空输出、拒答；
  - 内容质量：事实准确性、与实验结果一致、章节之间的连贯；
  - 非确定性与延迟、成本、失败重试。
- **接入真实模型后的测试**：
  - **契约测试**：用一组"对抗性"的 mock 输出（含 `%`、`&`、未知 `\cite`、空串、超长文本）验证写作器的防御；
  - **编译测试**：CI 中实际运行 `pdflatex`/`bibtex`，以"无错误、无 undefined reference 警告"为通过标准（本节我们就是这样发现了 `%` 吞内容和 `&` 报错的问题）；
  - **录制回放**：把真实模型的输出录下来作为固定夹具，保证回归测试确定；
  - **内容评估**：数字一致性检查（正文中出现的数值必须能在 53 节 `Verdict` / 实验结果中找到）、引用支持度检查、LLM-as-judge 打分，以及 55 节的 critic 循环；
  - 记录模型版本、提示词版本，纳入 manifest。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)：实验产物与结果，是图注入的上游。
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：`Verdict` 决定论文"结果"一节写什么。
- [阶段 19 · 51 文献检索](../../51-literature-retrieval/docs/zh.md)：参考文献条目应来自检索结果，而不是由模型编写。
- [阶段 19 · 24 计划—执行控制流程](../../24-plan-execute-control-flow/docs/zh.md)：先声明结构再执行，与"先骨架后正文"同一思路。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：让模型按 schema 输出，是"结构即契约"在单次调用上的体现。

### 本节被哪些后续内容用到
- [阶段 19 · 55 Critic 评审循环](../../55-critic-loop/docs/zh.md)：读取本节的 `manifest.json`，生成评审意见并驱动修订。
- [阶段 19 · 56 迭代调度器](../../56-iteration-scheduler/docs/zh.md)：在研究结果足够时触发论文写作（paper trigger）。
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：把写作器接入完整的自动研究循环。

### 延伸关键词
`skeleton-first generation` · `structure as contract` · `dependency injection` · `LaTeX escaping` · `BibTeX brace protection` · `hallucinated citations` · `citation grounding` · `atomic write / os.replace` · `idempotency` · `strategy pattern` · `intermediate representation` · `manifest-driven pipeline`
