# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 54 节 论文写作器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests`） ｜ **依赖**：仅标准库（`json`、`os`、`re`、`dataclasses`、`typing`、`tempfile`）；编译生成的 `paper.tex` 需要另装 TeX 发行版（`pdflatex` + `bibtex`），代码本身不调用它们

---

## 1. 这份代码在考察什么

自动研究循环跑完实验（52）、得出判决（53）之后，要把结果写成论文。本节的核心主张是：**论文是一个有已知结构的产物，而不是一段自由文本**。

具体考察：

1. **结构即数据**：`Paper / Section / Figure / BibEntry` 四个 dataclass 描述整篇论文。
2. **校验门**：渲染前检查标题、摘要、图 id、bib key、引用与图引用的完整性。
3. **渲染契约**：`\section` + `sec:<id>` 标签、`\begin{figure}` + `fig:<id>` 标签、`\bibliography`。
4. **图注入**：把实验输出清单转换成 `Figure` 记录。
5. **可注入的正文生成器**：`MockProseGenerator` 替代模型，使整个写作器可测试。
6. **三件套输出**：`paper.tex`、`references.bib`、`manifest.json`，其中 manifest 供 55 节 critic 读取。

> 一句话：**先把"论文长什么样"写成数据并校验，再让生成器往槽位里填字**。阅读时要留意：哪些东西被校验了、哪些没有（正文里的引用、正文里的特殊字符、图文件是否存在）——这正是把 mock 换成真实模型后会出问题的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PaperValidationError` | 异常类 | 结构校验失败时抛出 | 校验门 |
| `BibEntry` | dataclass | 一条参考文献，`to_bibtex()` 输出 BibTeX 文本 | 参考文献 |
| `Figure` | dataclass | 图的 id、路径、图注、宽度；`label` 属性返回 `fig:<id>` | 图槽位 |
| `Section` | dataclass | 章节 id、标题、正文、引用 key、图引用；`label` 返回 `sec:<id>` | 章节槽位 |
| `Paper` | dataclass | 元数据 + 章节、图、参考文献三个列表 | 论文结构 |
| `ProseGenerator` | 类型别名 | `Callable[[Section, Paper], str]` | 生成器接口 |
| `_validate` | 函数 | 6 道结构校验 | 校验门 |
| `_escape_latex` | 函数 | 逐字符转义 10 个 LaTeX 特殊字符 | 转义 |
| `render_latex` | 函数 | `Paper` → 完整 LaTeX 文档字符串（纯函数） | 渲染契约 |
| `render_bibtex` | 函数 | `Paper` → `references.bib` 内容 | 参考文献输出 |
| `MockProseGenerator` | 可调用类 | 按 outline 确定性地生成两段正文 | 模型替身 |
| `read_experiment_manifest` | 函数 | 实验清单 → `Figure` 列表 | 图注入 |
| `PaperWriter` | dataclass | `fill_prose` 填正文，`write` 渲染并写三个文件 | 写作器 |
| `demo` | 函数 | 两个模拟实验、三个章节、两条文献的完整示例 | 演示 |

数据流：实验清单 → `read_experiment_manifest` → `Figure` 列表 → 组装 `Paper` → `PaperWriter.write`：`fill_prose`（调用生成器）→ `render_latex`（内部先 `_validate`）→ `render_bibtex` → 写 `paper.tex`、`references.bib`、`manifest.json` → 返回 manifest 字典。

---

## 3. 逐段精讲

### 3.1 四个数据类

```python
@dataclass
class BibEntry:
    key: str
    entry_type: str
    fields: dict

    def to_bibtex(self) -> str:
        lines = [f"@{self.entry_type}{{{self.key},"]
        for k, v in sorted(self.fields.items()):
            safe = str(v).replace("{", "").replace("}", "")
            lines.append(f"  {k} = {{{safe}}},")
        lines.append("}")
        return "\n".join(lines)
```

- f-string 中 `{{` 和 `}}` 表示**字面花括号**：`f"@{self.entry_type}{{{self.key},"` 生成 `@article{smith2020,`。三重花括号 `{{{x}}}` = 字面 `{` + 变量 + 字面 `}`。
- `sorted(self.fields.items())` 让字段按名字排序输出——同样的输入永远得到同样的文本（确定性）。
- ⚠️ "删掉所有花括号"的处理有两个问题：BibTeX 用 `{BERT}` 保护大小写，删掉后 `plain` 样式会输出 `Bert`；而真正危险的 `&`、`%` 却没有转义，标题含 `&` 时 `pdflatex` 报 `Misplaced alignment tab character &`（实测，见测验 Q11）。

```python
@dataclass
class Figure:
    id: str
    path: str
    caption: str
    width: str = "0.8\\textwidth"

    @property
    def label(self) -> str:
        return f"fig:{self.id}"
```

- `"0.8\\textwidth"`：Python 字符串里 `\\` 表示一个反斜杠，实际值是 `0.8\textwidth`。
- `@property`：`fig.label` 像属性一样访问，但值由 id 计算得出，不会与 id 不同步——这就是讲义说的"稳定标签"。
- `Section` 同理，`label` 返回 `sec:<id>`；`cites`、`figure_refs` 用 `field(default_factory=list)` 避免可变默认值共享。

```python
@dataclass
class Paper:
    title: str
    authors: list[str]
    abstract: str
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    bibliography: list[BibEntry] = field(default_factory=list)


ProseGenerator = Callable[[Section, Paper], str]
```

- `Paper` 与讲义的结构图一一对应：元数据（title / authors / abstract）+ 三个列表。
- `ProseGenerator` 是**类型别名**：任何"接受 `(Section, Paper)`、返回 `str`"的可调用对象都满足，函数、lambda、实现了 `__call__` 的类实例都可以。

### 3.2 `_validate`：六道校验门

```python
def _validate(paper: Paper) -> None:
    if not paper.title.strip():
        raise PaperValidationError("title is empty")
    if not paper.abstract.strip():
        raise PaperValidationError("abstract is empty")

    fig_ids: set[str] = set()
    for fig in paper.figures:
        if fig.id in fig_ids:
            raise PaperValidationError(f"duplicate figure id: {fig.id}")
        fig_ids.add(fig.id)

    bib_keys: set[str] = set()
    for b in paper.bibliography:
        if b.key in bib_keys:
            raise PaperValidationError(f"duplicate bibliography key: {b.key}")
        bib_keys.add(b.key)
    for sec in paper.sections:
        for key in sec.cites:
            if key not in bib_keys:
                raise PaperValidationError(...)
        for fid in sec.figure_refs:
            if fid not in fig_ids:
                raise PaperValidationError(...)
```

| # | 校验 | 讲义是否列出 |
|---|------|-------------|
| 1 | 标题去空白后非空 | 是 |
| 2 | 摘要去空白后非空 | 是 |
| 3 | 图 id 唯一 | 是 |
| 4 | bib key 唯一 | 否（代码新增） |
| 5 | 章节 `cites` 中的 key 都已声明 | 是 |
| 6 | 章节 `figure_refs` 中的 id 都已声明 | 否（代码新增） |

- 用集合（`set`）做成员判断，O(1) 查找；"边遍历边加入"同时完成去重检查和建表。
- 遇到第一个错误就抛异常（fail fast），错误信息精确到章节 id 和 key，`!r` 让字符串带引号显示。
- ⚠️ **拦不住的**：
  - body 文本里的 `\cite{...}`、`\ref{...}` 不被检查（实测 body 写 `\cite{ghost2099}` 校验照样通过）；
  - 图文件是否真的存在不被检查（讲义说 harness 可以 "list missing figure files"，代码没有实现）；
  - 声明了但没有任何章节引用的图、没有被引用的参考文献都不报错。

### 3.3 `_escape_latex`：逐字符转义

```python
def _escape_latex(text: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out_chars: list[str] = []
    for ch in text:
        out_chars.append(repl.get(ch, ch))
    return "".join(out_chars)
```

- 覆盖 LaTeX 的 10 个特殊字符。`r"..."` 是原始字符串，反斜杠不需要再转义。
- **为什么逐字符**：如果用 `str.replace` 链式替换，先把 `\` 换成 `\textbackslash{}`，再替换 `{`、`}` 时就会把刚生成的花括号也转义掉。逐字符一次映射就没有这个顺序问题。
- `~`、`^` 换成 `\textasciitilde{}` 等命令，是因为 `\~`、`\^` 在 LaTeX 中是重音命令。
- 实测：`_escape_latex(r"50% of R&D costs $3 #1 a_b {x} ~ ^ \ ")` → `50\% of R\&D costs \$3 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{} \textbackslash{} `。

### 3.4 `render_latex`：纯函数渲染

```python
def render_latex(paper: Paper) -> str:
    _validate(paper)

    lines: list[str] = []
    lines.append("\\documentclass{article}")
    lines.append("\\usepackage{graphicx}")
    lines.append("\\usepackage{hyperref}")
    lines.append("\\title{" + _escape_latex(paper.title) + "}")
    lines.append("\\author{" + " \\and ".join(_escape_latex(a) for a in paper.authors) + "}")
    ...
    for sec in paper.sections:
        lines.append("\\section{" + _escape_latex(sec.title) + "}")
        lines.append("\\label{" + sec.label + "}")
        lines.append(sec.body if sec.body else "% body pending")
        for fid in sec.figure_refs:
            lines.append("See Figure~\\ref{fig:" + fid + "}.")
        for cite in sec.cites:
            lines.append("See~\\cite{" + cite + "}.")

    for fig in paper.figures:
        lines.append("\\begin{figure}")
        lines.append("\\centering")
        lines.append("\\includegraphics[width=" + fig.width + "]{" + fig.path + "}")
        lines.append("\\caption{" + _escape_latex(fig.caption) + "}")
        lines.append("\\label{" + fig.label + "}")
        lines.append("\\end{figure}")

    if paper.bibliography:
        lines.append("\\bibliographystyle{plain}")
        lines.append("\\bibliography{references}")

    lines.append("\\end{document}")
    return "\n".join(lines) + "\n"
```

- **先校验再渲染**：渲染函数自己调用 `_validate`，保证"不会渲染出一个结构非法的文档"。
- `graphicx` 提供 `\includegraphics`，`hyperref` 让 `\ref`、`\cite` 在 PDF 中可点击。
- 多作者用 `\and` 连接——这是 `\author{}` 中分隔作者的标准写法。生成器表达式 `(_escape_latex(a) for a in paper.authors)` 直接传给 `join`。
- **章节**：标题转义，标签紧跟 `\section` 之后（`\label` 必须在 `\section` 之后才能引用到章节编号）。body 为空时写一行 LaTeX 注释 `% body pending`，文档仍能编译。
- ⚠️ **body 原样输出、不转义**：因为 mock 生成器的正文里本来就有 `\ref`、`\cite` 命令。代价是模型写出的 `%`、`&`、`_` 都会出问题，其中 `%` 最隐蔽——它把后半行变成注释，编译不报错但内容消失（实测 `5% over & baseline` 只剩 `5`，见测验 Q10）。
- ⚠️ **重复的引用句**：渲染器在 body 之后又固定追加 `See Figure~\ref{...}.` 和 `See~\cite{...}.`，而 mock 正文里已经写过一遍，于是 demo 中同一个引用出现两次（见第 6 节）。
- **图**：所有图集中放在文末（LaTeX 的浮动体会自行决定位置）。路径 `fig.path` 不转义——`\includegraphics` 的路径参数按文件名处理，转义反而会出错；但路径中含 `%`、`#`、空格时仍可能有问题。
- **参考文献**：只有在存在条目时才输出 `\bibliographystyle{plain}` 和 `\bibliography{references}`（对应 `references.bib`）。编译时需要 `pdflatex → bibtex → pdflatex → pdflatex` 的完整流程。
- 结尾 `"\n".join(lines) + "\n"`：保证文件以换行结束。

```python
def render_bibtex(paper: Paper) -> str:
    return "\n\n".join(b.to_bibtex() for b in paper.bibliography) + ("\n" if paper.bibliography else "")
```

- 条目之间空一行；没有条目时返回空字符串（仍会写出一个空的 `references.bib`）。讲义契约"exactly the entries declared on the paper, no more and no fewer"由此保证。

### 3.5 `MockProseGenerator`：可调用的模型替身

```python
class MockProseGenerator:
    def __init__(self, outlines: dict[str, str]) -> None:
        self.outlines = outlines

    def __call__(self, section: Section, paper: Paper) -> str:
        seed = self.outlines.get(section.id, section.title)
        first = f"In this section we discuss {section.title.lower()}: {seed}."
        bits: list[str] = []
        for fid in section.figure_refs:
            bits.append(f"Figure~\\ref{{fig:{fid}}} shows the relevant artifact.")
        for c in section.cites:
            bits.append(f"This builds on prior work~\\cite{{{c}}}.")
        second = " ".join(bits) if bits else "We discuss implications below."
        return first + "\n\n" + second
```

- 实现 `__call__` 的对象可以像函数一样调用：`prose(sec, paper)`。它带状态（`outlines`），比普通函数更方便配置。
- outline 缺失时用章节标题兜底（`dict.get` 的默认值），所以测试里传 `outlines={}` 也能工作。
- 两段之间用 `\n\n`：LaTeX 中空行表示分段。
- 讲义："The generated prose name-drops figures and citations exactly when the outline declares them"——mock 只引用 `section.figure_refs` / `section.cites` 中声明过的 id 和 key，所以在 mock 下 body 里永远不会出现未声明的引用；真实模型则不受此约束。
- 注意第二个参数 `paper` 在 mock 中没有使用，但接口保留了它：真实生成器需要全文上下文（标题、摘要、其它章节）才能写出连贯的内容。

### 3.6 `read_experiment_manifest`：从实验清单注入图

```python
def read_experiment_manifest(manifests: Iterable[dict], paper_dir: str) -> list[Figure]:
    figs: list[Figure] = []
    counter = 0
    for m in manifests:
        name = m.get("name", "exp")
        artifacts = m.get("artifacts", [])
        for art in artifacts:
            path = art.get("path", "")
            caption = art.get("caption", "")
            if not path:
                continue
            counter += 1
            try:
                rel = os.path.relpath(path, paper_dir)
            except ValueError:
                rel = path
            fid = re.sub(r"[^a-zA-Z0-9]+", "-", f"{name}-{counter}").strip("-").lower()
            figs.append(Figure(id=fid, path=rel, caption=caption or name))
    return figs
```

- 全程用 `.get(..., 默认值)` 读取，清单缺字段也不会崩溃；空路径的产物被跳过（测试 `test_read_experiment_manifest_skips_empty_path`）。
- **id 生成**：`f"{name}-{counter}"` → 正则把所有非字母数字的连续字符替换为一个 `-` → 去掉首尾的 `-` → 转小写。例如 `"Loss Curve!"` 的第 1 个产物得到 `loss-curve-1`。
- **计数器是全局的**：跨清单递增，保证 id 唯一（即使不同实验名规范化后相同，实测 `"a b"` 与 `"a-b"` 得到 `a-b-1`、`a-b-2`）。代价是 id 依赖清单顺序。
- **图注兜底**：`caption or name`，空图注时用实验名。
- `os.path.relpath` 在 Windows 跨盘符时抛 `ValueError`，此时保留原路径。
- ⚠️ **相对路径按当前工作目录解析**：docstring 说相对路径是 "relative to the manifest's cwd"，但函数并不知道清单的目录，`relpath` 只能用进程的 cwd。demo 在 `code/` 下运行时得到 `../../home/claude/work/phases/.../code/figs/loss.pdf`——生成的 LaTeX 取决于你在哪个目录运行（测验 Q12）。
- ⚠️ 不检查文件是否存在。

### 3.7 `PaperWriter`：填正文、渲染、写文件

```python
@dataclass
class PaperWriter:
    prose: ProseGenerator

    def fill_prose(self, paper: Paper) -> Paper:
        for sec in paper.sections:
            if not sec.body:
                sec.body = self.prose(sec, paper)
        return paper
```

- 只给 body 为空的章节生成正文——已有正文（人工写的或上一轮生成的）不会被覆盖。
- ⚠️ **原地修改**传入的 `paper`，返回的也是同一个对象。

```python
    def write(self, paper: Paper, out_dir: str) -> dict:
        os.makedirs(out_dir, exist_ok=True)
        self.fill_prose(paper)
        tex = render_latex(paper)
        bib = render_bibtex(paper)
        ...
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex)
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib)

        manifest = {
            "title": paper.title,
            "authors": list(paper.authors),
            "sections": [
                {"id": s.id, "title": s.title, "cites": list(s.cites),
                 "figure_refs": list(s.figure_refs), "body_chars": len(s.body)}
                for s in paper.sections
            ],
            "figures": [
                {"id": f.id, "path": f.path, "caption": f.caption, "label": f.label}
                for f in paper.figures
            ],
            "bibliography": [b.key for b in paper.bibliography],
            "tex_path": tex_path,
            "bib_path": bib_path,
        }
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        return manifest
```

- 渲染全部在内存中完成，**校验失败时不会写任何文件**——这部分符合讲义的"no partial write"。
- manifest 记录每个章节的引用、图引用和正文长度 `body_chars`，以及全部图和 bib key——55 节 critic 读的就是它。`sort_keys=True` 让 JSON 键有序，便于 diff。
- ⚠️ 顺序问题（测验 Q9 实测）：
  1. `os.makedirs` 在校验之前执行——校验失败也会留下空目录；
  2. `fill_prose` 在校验之前执行——非法论文也会先调用生成器（生产中是付费的模型调用），并且修改了调用方的对象；
  3. 三个文件依次写入，中途失败会留下不一致的组合。
- ⚠️ manifest 中的 `tex_path`、`bib_path` 是带 `out_dir` 前缀的路径（demo 中是绝对路径），换个目录运行内容就不同。
- ⚠️ 讲义说 manifest 列出 "every figure referenced and every citation used"，实际列的是**全部声明的**图和文献，"被引用"的信息要从各章节的 `figure_refs`、`cites` 里汇总。

### 3.8 `demo` 与入口

```python
def demo(out_dir: str | None = None) -> dict:
    import tempfile as _tempfile
    if out_dir is None:
        out_dir = _tempfile.mkdtemp(prefix="paper-writer-demo-")
    experiments = [
        {"name": "loss-curve", "artifacts": [{"path": "figs/loss.pdf", "caption": "Training loss across epochs"}]},
        {"name": "ablation", "artifacts": [{"path": "figs/ablation.pdf", "caption": "Ablation over decoder width"}]},
    ]
    figs = read_experiment_manifest(experiments, out_dir)
    paper = Paper(..., sections=[
        Section(id="intro", title="Introduction", cites=["smith2020"], figure_refs=[]),
        Section(id="method", title="Method", cites=["jones2021"], figure_refs=[figs[0].id]),
        Section(id="results", title="Results", cites=[], figure_refs=[figs[1].id]),
    ], ...)
```

- 函数内 `import tempfile as _tempfile`：局部导入，只有调用 demo 时才加载。
- `mkdtemp` 创建临时目录但**不会自动删除**——每运行一次 `main.py` 或测试 `test_demo_runs`，`/tmp` 下就多一个 `paper-writer-demo-*` 目录（docstring 说这样"keeps the worktree clean"，但临时目录本身需要手动清理）。
- 章节通过 `figs[0].id` 引用注入的图，而不是写死 `"loss-curve-1"`——这样即使 id 规则变了，引用也不会断。
- `figs/loss.pdf` 等文件并不存在，demo 只生成 LaTeX 源码，不编译。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 论文结构用 dataclass 描述 | 结构可检查、可序列化、可测试 | 只支持一级 `\section`；生产需要子章节、表格、公式等节点 |
| 渲染前强制 `_validate` | 不会渲染出结构非法的文档 | 只校验结构字段，不校验正文内容 |
| `label` 用 `@property` 从 id 派生 | 标签与 id 永远一致 | id 一改，所有引用都要跟着改 |
| 标题、图注等转义，body 不转义 | body 里需要 `\ref`、`\cite` 命令 | 模型输出的 `%`、`&` 会出错或静默丢内容；应改用占位符标记（测验 Q10） |
| bib 字段删除花括号 | 防止破坏 `{...}` 定界 | 丢失大小写保护、不处理 `&`；应校验配对并转义特殊字符 |
| 图 id = 实验名 + 全局计数器 | 简单且保证唯一 | 依赖清单顺序；可改用产物路径的哈希 |
| `relpath` 规范化图路径 | LaTeX 从论文目录解析相对路径 | 相对路径按 cwd 解析，结果依赖运行目录 |
| 生成器作为可注入的可调用对象 | 测试用 mock，生产用模型，流程不变 | 无 |
| 渲染在内存中完成后再写盘 | 校验失败时不写文件 | 生成先于校验、修改输入、多文件写入非原子 |
| manifest 与 LaTeX 一起输出 | 下游读结构化数据，不解析 LaTeX | 含绝对路径，不完全可复现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 自定义异常 | `class PaperValidationError(Exception):` | 只写 docstring 的类体也是合法的 |
| `@dataclass` | `class Section:` | 自动生成 `__init__` 等方法 |
| `field(default_factory=list)` | `cites: list[str] = field(default_factory=list)` | 每个实例独立的空列表 |
| `@property` | `def label(self) -> str:` | 方法当属性用：`sec.label` |
| f-string 中的字面花括号 | `f"@{self.entry_type}{{{self.key},"` | `{{` → `{`，`}}` → `}` |
| 原始字符串 | `r"\textbackslash{}"` | 反斜杠不转义 |
| 字符串中的反斜杠 | `"\\documentclass{article}"` | `\\` 表示一个反斜杠 |
| 类型别名 | `ProseGenerator = Callable[[Section, Paper], str]` | 给复杂类型起名字 |
| `Callable[[参数类型...], 返回类型]` | 同上 | 描述"可调用对象"的类型 |
| `__call__` | `MockProseGenerator.__call__` | 让实例像函数一样被调用 |
| `str.strip()` | `paper.title.strip()` | 去掉首尾空白再判断是否为空 |
| `dict.get(key, default)` | `self.outlines.get(section.id, section.title)` | 缺键时返回默认值 |
| 生成器表达式传给 `join` | `" \\and ".join(_escape_latex(a) for a in paper.authors)` | 不需要先建列表 |
| 条件表达式 | `sec.body if sec.body else "% body pending"` | 一行 if/else |
| `x or y` 兜底 | `caption or name` | `caption` 为空串时用 `name` |
| `re.sub` | `re.sub(r"[^a-zA-Z0-9]+", "-", ...)` | 正则替换：非字母数字的连续字符 → `-` |
| 方法链 | `.strip("-").lower()` | 去掉首尾 `-` 再转小写 |
| `os.path.relpath / join` | `os.path.relpath(path, paper_dir)` | 计算相对路径 / 拼接路径 |
| `os.makedirs(..., exist_ok=True)` | `write` 开头 | 目录已存在时不报错 |
| `try / except ValueError` | `relpath` 跨盘符 | 捕获特定异常并降级处理 |
| 字典 / 列表推导式 | manifest 中的 `[{...} for s in paper.sections]` | 构造嵌套结构 |
| `json.dump(..., indent=2, sort_keys=True)` | 写 manifest | 美化并排序键 |
| 函数内局部导入 | `import tempfile as _tempfile` | 用到时才导入 |
| `X \| None` 默认值 | `out_dir: str \| None = None` | 可选参数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 demo |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`）：

```text
{
  "sections": 3,
  "figures": 2,
  "bib_keys": [
    "smith2020",
    "jones2021"
  ],
  "tex_path": "/tmp/paper-writer-demo-sm5wtrep/paper.tex"    ← 随机临时目录，每次不同
}
```

终端只打印摘要，真正的产物在临时目录里。生成的 `paper.tex`（节选）：

```text
\section{Introduction}
\label{sec:intro}
In this section we discuss introduction: we motivate the auto-research loop.

This builds on prior work~\cite{smith2020}.
See~\cite{smith2020}.                       ← 渲染器追加的引用句，与上一句重复
\section{Method}
\label{sec:method}
In this section we discuss method: we describe the skeleton-first writer.

Figure~\ref{fig:loss-curve-1} shows the relevant artifact. This builds on prior work~\cite{jones2021}.
See Figure~\ref{fig:loss-curve-1}.          ← 同样重复
See~\cite{jones2021}.
...
\begin{figure}
\centering
\includegraphics[width=0.8\textwidth]{../../home/claude/work/phases/19-capstone-projects/54-paper-writer/code/figs/loss.pdf}
\caption{Training loss across epochs}
\label{fig:loss-curve-1}
\end{figure}
...
\bibliographystyle{plain}
\bibliography{references}
\end{document}
```

`references.bib`：

```text
@article{smith2020,
  author = {Smith},
  title = {On harnesses},
  year = {2020},
}
```

逐项解读：

- **3 个章节、2 个图、2 条文献**：与 demo 构造的 `Paper` 一致；图 id 为 `loss-curve-1`、`ablation-2`（全局计数器）。
- **字段按字母序**：`author / title / year`，来自 `sorted(self.fields.items())`。
- **图路径**：相对路径 `figs/loss.pdf` 被按当前目录（`code/`）解析后再相对临时目录计算，得到一长串 `../../home/...`。换个目录运行，路径就不同。
- **重复引用**：mock 正文和渲染器各写了一次，编译后 PDF 中会出现两句意思相同的话。
- **能否编译**：我们在一个独立目录下（`figs/` 与输出目录同级）重新运行 demo，补上占位 PDF 图后执行 `pdflatex → bibtex → pdflatex ×2`，输出 `Output written on paper.pdf (2 pages)`，无错误、无未定义引用。说明在路径正确的前提下，渲染契约产出的是合法 LaTeX。

补充探针结果：

| 场景 | 结果 |
|------|------|
| body 含 `\cite{ghost2099}`、`\ref{fig:nope}` | 校验通过，正常渲染 |
| 标题为空、两个章节 body 为空 | 抛 `title is empty`，但生成器已被调用 2 次、body 被修改、空目录已创建 |
| body 为 `5% over & baseline` | `pdflatex` 退出码 0，PDF 中只剩 `Accuracy improved by 5` |
| bib 标题 `{BERT}: Pre-training & {Fine}-tuning` | `.bbl` 中为 `Bert: Pre-training & fine-tuning.`，`pdflatex` 报 `Misplaced alignment tab character &` |

---

## 7. 动手改一改

1. **（入门）** 删掉 `render_latex` 中追加 `See Figure~\ref...`、`See~\cite...` 的两个循环（或者改为"只在 body 中没有出现时才追加"），消除重复引用句。
2. **（入门）** 给 `_validate` 增加第 7 道门：每个声明的图都必须被至少一个章节引用；再增加第 8 道门：每条参考文献都必须被引用。思考它们应该是错误还是警告。
3. **（进阶）** 实现测验 Q9 的事务式 `write`：先校验、`copy.deepcopy` 后填正文、暂存目录 + `os.replace`；写测试断言"校验失败时生成器调用次数为 0 且输出目录不存在"。
4. **（进阶）** 实现测验 Q10 的占位符正文：生成器输出 `[[fig:id]]`、`[[cite:key]]`，渲染时转义普通文本并校验标记；改写 `MockProseGenerator` 输出这种格式，并写一个包含 `%`、`&`、`_` 的测试。
5. **（进阶）** 按讲义 "Going further" 实现 `MarkdownRenderer`：同一个 `Paper` 输出 `paper.md`，图用 `![caption](path)`，引用渲染为 `[1]` 并在文末生成参考文献列表。
6. **（挑战）** 在测试中加入真实编译检查：如果系统有 `pdflatex`，就生成占位图、编译 demo，并解析 `paper.log` 断言没有 `undefined` 警告（没有 `pdflatex` 时用 `unittest.skipUnless` 跳过）。

---

## 8. 常见坑

- **在正文里写 `%`**：LaTeX 会把后半行当注释，编译不报错但内容消失。百分数要写 `\%`。
- **删掉 BibTeX 字段的花括号**：缩写（BERT、GPT）的大小写保护随之消失。
- **以为校验覆盖了正文**：`_validate` 只看 `cites` / `figure_refs` 字段，正文里的 `\cite` 不受约束。
- **相对路径与 cwd**：`os.path.relpath` 对相对路径按进程当前目录解析，不同目录运行结果不同。
- **重复调用 `write`**：第一次调用已经把正文写进了 `paper.sections[*].body`，第二次不会重新生成；如果你修改了 outline 想重新生成，需要先清空 body。
- **`\label` 放在 `\section` 之前**：会引用到上一个计数器，本节代码顺序是正确的（先 `\section` 再 `\label`）。
- **只运行一次 `pdflatex`**：参考文献和交叉引用需要 `pdflatex → bibtex → pdflatex → pdflatex` 才能全部解析。
- **临时目录堆积**：`demo()` 用 `mkdtemp` 创建的目录不会自动删除。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_paper_writer.py`（`unittest` 风格）。`_paper_min()` 构造只有标题、作者、摘要的最小论文；`TestWrite._paper_full()` 构造 2 个章节、1 个图、1 条文献的完整论文。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestRender.test_skeleton_no_sections_compiles_string` | 无章节时仍输出完整骨架：`\documentclass`、`\begin{document}`、`\end{document}`、`\title{T}`、`abstract` 环境（名字说 "compiles"，实际只检查字符串，不调用 LaTeX） |
| `TestRender.test_section_emits_section_and_label` | 章节输出 `\section{Introduction}` 和 `\label{sec:intro}`，body 原样出现 |
| `TestRender.test_figure_emits_figure_block_and_label` | 图输出 `figure` 环境、`\includegraphics`、`\caption{cap1}`、`\label{fig:f1}` |
| `TestRender.test_latex_escape_on_title` | 标题 `A & B` 被转义为 `A \& B` |
| `TestValidation.test_empty_title_rejected` | 空标题抛 `PaperValidationError` |
| `TestValidation.test_empty_abstract_rejected` | 空摘要抛 `PaperValidationError` |
| `TestValidation.test_duplicate_figure_id_rejected` | 图 id 重复，错误信息含 `duplicate figure id` |
| `TestValidation.test_unknown_citation_rejected` | 引用未声明的 key，错误信息含 `unknown bibliography key` |
| `TestValidation.test_unknown_figure_ref_rejected` | 引用未声明的图，错误信息含 `unknown figure id` |
| `TestFigureInjection.test_read_experiment_manifest_emits_unique_ids` | 两个清单共 3 个产物 → 3 个 id 互不相同，图注都非空 |
| `TestFigureInjection.test_read_experiment_manifest_skips_empty_path` | 空路径的产物被跳过 |
| `TestWrite.test_write_emits_three_files_and_manifest_shape` | 三个文件都存在；manifest 中章节 2 个、图 1 个、含 `k1`；磁盘上的 manifest 可读回 |
| `TestWrite.test_prose_filled_when_body_empty` | 空 body 被 mock 生成器填充，outline 内容（`seed-intro`、`seed-res`）出现在 tex 中 |
| `TestWrite.test_bibtex_written_correctly` | `references.bib` 含 `@article{k1,` 和 `author = {X}` |
| `TestDemo.test_demo_runs` | demo 能跑通，至少 1 个章节、1 个图 |

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q
...............                                                          [100%]
15 passed in 0.03s
```

值得注意：

- 讲义说测试覆盖 "full render with two sections and two figures"，实际 `_paper_full` 只有 1 个图（2 个图的情形只出现在 demo 中）。
- 没有测试"重复 bib key"这道门，也没有测试"校验失败时不写任何文件"（讲义强调的 no partial write）。
- 没有任何测试检查正文中的特殊字符、正文中的未声明引用、图文件是否存在，或者真正编译 LaTeX。
- `test_demo_runs` 每次运行都会在 `/tmp` 下留下一个 `paper-writer-demo-*` 临时目录。
