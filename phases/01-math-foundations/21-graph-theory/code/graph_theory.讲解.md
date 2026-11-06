# 代码讲解 · graph_theory.py

> **所属小节**：阶段 01 · 数学基础 · 第 21 节 机器学习的图论 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python graph_theory.py`（无命令行参数，不写任何文件） ｜ **依赖**：`numpy`；标准库 `collections.deque`

---

## 1. 这份代码在考察什么

这份文件约 300 行，把"图 → 矩阵 → 谱 → GNN"这条主线完整串起来：

1. **两种表示的转换**：用邻接表（字典）存图、做遍历，用邻接矩阵（NumPy）做线性代数——这是所有图算法和 GNN 框架的基本套路。
2. **两种遍历**：BFS（队列，求无权最短跳数）和 DFS（栈），以及用遍历求连通分量。
3. **拉普拉斯谱**：`L = D − A` 的零特征值个数 = 连通分量数；Fiedler 向量的正负号 = 最佳二分。
4. **消息传递 = 矩阵乘法**：`A_norm @ H @ W` 就是 GNN 一层的核心（去掉了非线性）。
5. **PageRank**：随机游走 + 随机跳转 + 悬挂节点处理，用幂迭代求平稳分布。

> 一句话：**图算法的一半是遍历（邻接表），另一半是线性代数（邻接矩阵）**。这份代码让你在两种视角之间来回切换。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Graph` | 类 | 邻接表存图；导出邻接矩阵、度矩阵、拉普拉斯 | `G=(V,E)`、A、D、`L = D − A` |
| `bfs(graph, start)` | 函数 | 队列遍历，返回访问顺序 + 每个节点的跳数 | BFS、无权最短路 |
| `dfs(graph, start)` | 函数 | 显式栈遍历，返回访问顺序 | DFS |
| `connected_components(graph)` | 函数 | 从每个未访问节点跑 BFS | 连通分量 |
| `spectral_clustering(graph, k)` | 函数 | k=2 用 Fiedler 向量符号；k>2 用特征向量 + 自写 k-means | 谱聚类 |
| `message_passing(graph, features, W)` | 函数 | 行归一化邻接矩阵 × 特征 × 权重 | GNN 消息传递 |
| `pagerank(graph, ...)` | 函数 | 幂迭代求 PageRank | 随机游走、平稳分布 |
| `demo_*`（4 个） | 演示函数 | 社交网络遍历 / 拉普拉斯与连通分量 / 消息传递 / 谱聚类 + PageRank | — |

调用关系：所有算法都只通过 `graph.neighbors()`、`graph.degree()`、`graph.adjacency_matrix()`、`graph.laplacian()` 访问图，`connected_components` 内部复用 `bfs`。

---

## 3. 逐段精讲

### 3.1 `Graph`：字典套字典的邻接表

```python
class Graph:
    def __init__(self, n_nodes, directed=False):
        self.n = n_nodes
        self.directed = directed
        self.adj = {i: {} for i in range(n_nodes)}

    def add_edge(self, u, v, weight=1.0):
        self.adj[u][v] = weight
        if not self.directed:
            self.adj[v][u] = weight

    def neighbors(self, node):
        return list(self.adj[node].keys())

    def degree(self, node):
        return len(self.adj[node])

    def weighted_degree(self, node):
        return sum(self.adj[node].values())
```

- `self.adj[u]` 是一个字典 `{邻居: 权重}`。外层用**字典推导式**一次性建好 n 个空字典。相比"列表的列表"，内层用字典有三个好处：查边 `v in self.adj[u]` 是 O(1)；可以顺便存权重；重复加同一条边只会覆盖、不会重复。
- 无向图在 `add_edge` 里**写两次**（u→v 和 v→u），所以邻接矩阵自动对称。
- `neighbors` 返回的顺序就是加边的顺序（Python 3.7+ 字典保持插入顺序）——BFS/DFS 的访问顺序因此是确定的。
- 两种度：`degree` 数邻居个数（PageRank 用它当出度）；`weighted_degree` 对权重求和（度矩阵用它）。对无权图两者相同。

### 3.2 从邻接表到矩阵：A、D、L

```python
    def adjacency_matrix(self):
        A = np.zeros((self.n, self.n))
        for u in range(self.n):
            for v, w in self.adj[u].items():
                A[u][v] = w
        return A

    def degree_matrix(self):
        D = np.zeros((self.n, self.n))
        for i in range(self.n):
            D[i][i] = self.weighted_degree(i)
        return D

    def laplacian(self):
        return self.degree_matrix() - self.adjacency_matrix()
```

- 邻接矩阵每次调用都**重新构建**，O(n²) 内存——小图演示没问题，大图要用稀疏矩阵。
- 度矩阵用 `weighted_degree` 是**关键的正确选择**：这样 L 的每一行之和都为 0（`Σⱼ A[i][j] = D[i][i]`），全 1 向量才是特征值 0 的特征向量，L 才半正定。讲义 Build It 里的 `degree_matrix` 写的是 `self.degree(i)`（边数），对带权图会出错：例如边 `0-1(2.0)`、`1-2(3.0)` 的图，用边数做 D 得到的"拉普拉斯"特征值是 `[−2.14, 1, 5.14]`，出现负值；用权重和则是 `[0, 2.35, 7.65]`。以本代码为准。

### 3.3 `__repr__`：无向边去重

```python
    def __repr__(self):
        edges = []
        seen = set()
        for u in range(self.n):
            for v, w in self.adj[u].items():
                key = (min(u, v), max(u, v)) if not self.directed else (u, v)
                if key not in seen:
                    seen.add(key)
                    if w == 1.0:
                        edges.append(f"{u}-{v}")
                    else:
                        edges.append(f"{u}-{v}({w})")
        return f"Graph(n={self.n}, edges=[{', '.join(edges)}])"
```

- 无向边在邻接表里存了两份。用 `(min, max)` 作为**规范化的键**放进集合，第二次遇到同一条边时跳过。元组可以哈希，所以能放进 `set`。
- `', '.join(edges)` 把字符串列表用逗号拼接。权重为 1 时省略不写，输出更干净。

### 3.4 `bfs`：入队时就标记已访问

```python
def bfs(graph, start):
    visited = set()
    order = []
    distances = {}
    queue = deque([(start, 0)])
    visited.add(start)
    while queue:
        node, dist = queue.popleft()
        order.append(node)
        distances[node] = dist
        for neighbor in graph.neighbors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return order, distances
```

- **为什么用 `deque`**：`list.pop(0)` 要把后面所有元素前移，是 O(n)；`deque.popleft()` 是 O(1)。BFS 整体因此是 O(V+E)。
- 队列里存 `(节点, 距离)` 元组，距离随节点一起传递，出队时直接记录——不需要额外的"层"循环。
- **入队时就标记 visited**（而不是出队时）：保证每个节点只入队一次。如果等出队再标记，同一节点可能被多个邻居重复入队。
- 正确性来自 FIFO：距离为 d 的节点全部出队之前，距离为 d+1 的节点不会出队，所以第一次发现时的距离就是最短跳数。

### 3.5 `dfs`：显式栈 + 弹出时检查

```python
def dfs(graph, start):
    visited = set()
    order = []
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        for neighbor in reversed(graph.neighbors(node)):
            if neighbor not in visited:
                stack.append(neighbor)
    return order
```

- Python 的 `list` 本身就是高效的栈：`append` 和 `pop()`（弹出末尾）都是 O(1)。
- 与 BFS 不同，这里在**弹出时**检查 visited：同一节点可能被压栈多次（演示图中节点 2 就被压入两次），第二次弹出时直接 `continue`。这是迭代 DFS 的标准写法，保证访问顺序与递归 DFS 一致。
- `reversed(...)`：栈后进先出，逆序压入后，第一个邻居最先弹出，访问顺序与"按邻居列表顺序递归"相同。演示图得到 `[0, 1, 3, 2, 4, 5]`；去掉 `reversed` 则是 `[0, 2, 3, 4, 5, 1]`。讲义里 DFS 的手推示例先访问节点 2，对应的是不加 `reversed` 的写法，两者都是合法的 DFS。
- ⚠️ 用显式栈而不是递归，是为了避免 Python 默认约 1000 层的递归深度限制——长链图上递归 DFS 会栈溢出。

### 3.6 `connected_components`

```python
def connected_components(graph):
    visited = set()
    components = []
    for node in range(graph.n):
        if node not in visited:
            order, _ = bfs(graph, node)
            visited.update(order)
            components.append(order)
    return components
```

- 思路：从每个还没被访问过的节点出发跑一次 BFS，BFS 能到达的节点就是一个连通分量。
- `order, _ = ...`：用 `_` 表示"这个返回值（距离）我不需要"。`visited.update(order)` 把整个列表加入集合。
- 总复杂度仍然是 O(V+E)，因为每个节点只会被一次 BFS 访问。⚠️ 这只对**无向图**有意义；有向图要区分弱连通和强连通（需要 Tarjan / Kosaraju 算法）。

### 3.7 `spectral_clustering`：k=2 与 k>2 两条路

```python
def spectral_clustering(graph, k=2):
    if graph.n < 2:
        raise ValueError("spectral_clustering requires at least 2 nodes")
    if not (2 <= k <= graph.n):
        raise ValueError(f"k must satisfy 2 <= k <= {graph.n}, got k={k}")

    L = graph.laplacian()
    eigenvalues, eigenvectors = np.linalg.eigh(L)

    if k == 2:
        fiedler = eigenvectors[:, 1]
        labels = np.zeros(graph.n, dtype=int)
        labels[fiedler < 0] = 1
        return labels
```

- 开头的参数校验用了**链式比较** `2 <= k <= graph.n`，非法输入直接抛出带说明的 `ValueError`。
- `np.linalg.eigh` 专用于对称矩阵：比通用的 `eig` 更快、更稳定，保证返回实数特征值，并按**升序**排列。所以 `eigenvectors[:, 0]` 对应 λ₁ = 0（连通图上是常向量），`eigenvectors[:, 1]` 就是 Fiedler 向量。注意特征向量是**按列**存放的。
- `labels[fiedler < 0] = 1`：`fiedler < 0` 生成布尔数组，用它做**布尔掩码赋值**，一行完成"负值节点标为 1"。
- ⚠️ 特征向量的符号是任意的（v 和 −v 都是特征向量），所以哪一组叫 0、哪一组叫 1 没有意义。演示中团 `{0..4}` 被标成了 1。

```python
    features = eigenvectors[:, 1:k + 1]
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    norms[norms == 0] = 1
    features = features / norms

    rng = np.random.RandomState(42)
    centroids = features[rng.choice(graph.n, k, replace=False)]

    for _ in range(100):
        dists = np.zeros((graph.n, k))
        for c in range(k):
            dists[:, c] = np.linalg.norm(features - centroids[c], axis=1)
        labels = np.argmin(dists, axis=1)

        new_centroids = np.zeros_like(centroids)
        for c in range(k):
            mask = labels == c
            if mask.any():
                new_centroids[c] = features[mask].mean(axis=0)

        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids

    return labels
```

- 流程：取低端特征向量作为每个节点的新坐标 → 每行单位化（Ng-Jordan-Weiss 算法的做法）→ 自写 k-means（随机选 k 个点作初始中心，最多迭代 100 次，中心不再变化就停止）。
- `keepdims=True` 让 `norms` 的形状是 `(n, 1)` 而不是 `(n,)`，这样 `features / norms` 能按行**广播**。`norms[norms == 0] = 1` 防止除以 0。
- `rng.choice(graph.n, k, replace=False)`：不放回地抽 k 个不同节点的下标作为初始中心，`RandomState(42)` 保证结果可复现。
- ⚠️ **取了多少个特征向量值得商榷**：k 个簇的标准做法是前 k 个特征向量（含平凡的常向量），等价于 **k−1 个非平凡向量**；这里跳过第一个后又取了 k 个（`1:k+1`），多出的那个描述的是簇**内部**结构。测验 Q11 给出了反例：3 个三角形串成一串，`k=3` 时返回 `[1 1 1 2 2 2 2 0 0]`，节点 6 被分错；改成 `eigenvectors[:, 1:k]` 后得到正确的三组。并且 `k == 2` 分支本身只用了 1 个非平凡向量，两个分支的取法不一致。
- ⚠️ 其他简化：k-means 只初始化一次（生产中会用 `n_init=10` 多次初始化取最优）；簇变空时中心会变成 0 向量；用的是未归一化拉普拉斯，而行单位化原本搭配的是 `L_sym`。

### 3.8 `message_passing`：GNN 的一层（去掉激活）

```python
def message_passing(graph, features, weight_matrix):
    A = graph.adjacency_matrix()
    row_sums = A.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    A_norm = A / row_sums

    aggregated = A_norm @ features
    output = aggregated @ weight_matrix
    return output
```

- `A / row_sums`：每行除以该行之和（即度），得到**行随机矩阵** `D⁻¹A`，每行和为 1。`A_norm @ features` 的第 i 行 = 节点 i 邻居特征的**平均值**（AGGREGATE = mean）。
- `row_sums[row_sums == 0] = 1`：孤立节点度为 0，不处理就会出现 0/0 = NaN；替换成 1 后它的聚合结果是全 0 向量。
- `@ weight_matrix`：线性变换（UPDATE），把 3 维特征映射到 2 维，所有节点**共享**同一个 W——这就是 GNN 参数量与图大小无关的原因。
- ⚠️ 与讲义公式 `σ(A_norm·H·W)` 相比，有两处刻意简化：
  1. **没有非线性 σ**：两层叠加等于 `A_norm²·H·W₁W₂`，整体仍然是线性模型。
  2. **没有自环**：节点 i 聚合时不包含自己的特征。后果是两轮之后得到的是"恰好走两步"能到达的节点，而不是"两跳以内"的全部节点。演示图里节点 4 的唯一邻居是 3，但 `A_norm²` 的第 4 行是 `[0, 0, 0.5, 0, 0.5]`——**节点 3 的原始特征对节点 4 的两轮输出毫无影响**。所以演示标题 "2-hop neighborhood info" 不够准确。GCN 用 `A + I` 正是为了解决这个问题。

### 3.9 `pagerank`：幂迭代 + 悬挂节点

```python
def pagerank(graph, damping=0.85, max_iter=100, tol=1e-6):
    n = graph.n
    scores = np.ones(n) / n

    for _ in range(max_iter):
        new_scores = np.ones(n) * (1 - damping) / n
        dangling_sum = 0.0
        for u in range(n):
            out_deg = graph.degree(u)
            if out_deg > 0:
                for v in graph.neighbors(u):
                    new_scores[v] += damping * scores[u] / out_deg
            else:
                dangling_sum += scores[u]
        new_scores += damping * dangling_sum / n
        if np.abs(new_scores - scores).sum() < tol:
            scores = new_scores
            break
        scores = new_scores

    return scores
```

- 初始为均匀分布 `1/n`。每轮：先给每个节点 `(1−d)/n` 的"随机跳转"份额；再让每个节点 u 把 `d·score(u)` 平均分给它的出边邻居。
- **悬挂节点**（出度为 0，例如只被链接、不链接别人的网页）：它的分数无处可去，如果直接丢掉，总分会越来越少。这里把它们的分数汇总到 `dangling_sum`，再平均分给所有节点，保证 `Σ scores = 1`（实测有向小图的和为 `1.0000000000000002`）。
- 收敛判据是 L1 距离 `Σ|new − old| < tol`。
- 有向图中 `self.adj[u]` 只存出边，所以 `degree(u)` 就是出度，代码对有向图同样正确。
- ⚠️ 用的是 `degree`（边数）而非权重，**忽略了边权**；带权 PageRank 应按 `w(u,v) / weighted_degree(u)` 分配。

### 3.10 四个演示

| 演示 | 图 | 验证什么 |
|------|----|---------|
| `demo_social_network` | 6 节点：`0-1, 0-2, 1-3, 2-3, 3-4, 4-5` | 邻接矩阵对称、各节点度、BFS 距离、DFS 顺序 |
| `demo_laplacian` | 三角形 + 两条孤立边，共 7 节点 | 零特征值个数 = 连通分量数 = 3 |
| `demo_message_passing` | 5 节点，随机特征 `randn(5, 3)`，`W` 为 3×2 | 一轮、两轮消息传递后的特征 |
| `demo_spectral_clustering` | 两个 5 节点完全图 + 桥 `2-7` | Fiedler 二分、λ₂ 很小、PageRank |

- 在 `demo_laplacian` 中，判断"零"用的是 `np.abs(eigenvalues) < 1e-8`，而不是 `== 0`——特征值是数值迭代算出来的，会带 1e-16 量级的误差。
- 在 `demo_message_passing` 中，`rng.randn(3, 2) * 0.5` 把随机权重缩小，避免数值随层数放大。注意第二轮的权重 `rng.randn(2, 2) * 0.5` 是在调用时现场生成的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 邻接表用"字典套字典" | O(1) 查边、能存权重、天然去重、保持插入顺序 | 内存开销大；生产用 CSR/COO 稀疏格式 |
| 邻接矩阵按需用 NumPy 稠密构建 | 便于 `eigh`、`@` 等线性代数运算 | O(n²) 内存；大图用 `scipy.sparse` + `eigsh` |
| 度矩阵用权重和 | 保证 L 行和为 0、半正定 | 无 |
| BFS 用 `deque`，入队即标记 | O(1) 出队，每个节点只入队一次 | 无 |
| DFS 用显式栈 + `reversed` | 避免递归深度限制，顺序与递归版一致 | 节点可能重复入栈，栈大小最坏 O(E) |
| 谱聚类用稠密 `eigh` | 一行求全部特征值，代码简单 | O(n³)；只需少数几个特征向量时用 Lanczos |
| k>2 时自写 k-means，单次初始化 | 不依赖 sklearn，过程透明 | 容易陷入局部最优；特征向量多取了一个（见 3.7） |
| 消息传递无激活、无自环 | 突出"消息传递 = 矩阵乘法"这一核心 | 多层仍是线性模型；节点看不到自己；GCN 用 `σ` 和 `A+I` |
| PageRank 显式处理悬挂节点 | 保证分数总和为 1 | 用双重 Python 循环，O(E) 每轮但常数大；生产用稀疏矩阵乘法 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from ... import` | `from collections import deque` | 从模块中导入指定名字 |
| 默认参数 | `def __init__(self, n_nodes, directed=False)`、`damping=0.85` | 调用时可省略 |
| 字典推导式 | `{i: {} for i in range(n_nodes)}` | 一行构建字典，每个值都是**新的**空字典 |
| 嵌套字典 | `self.adj[u][v] = weight` | 字典的值还是字典 |
| 字典方法 | `.keys()`、`.values()`、`.items()` | 取键、值、键值对 |
| `not` | `if not self.directed:` | 逻辑非 |
| 集合 `set` | `visited = set()`、`.add()`、`.update()`、`in` | O(1) 成员判断，`update` 一次加入多个元素 |
| 元组作字典/集合键 | `key = (min(u, v), max(u, v))` | 元组不可变、可哈希 |
| 条件表达式 | `(...) if not self.directed else (u, v)` | 一行 if/else 取值 |
| `str.join` | `', '.join(edges)` | 用分隔符拼接字符串列表 |
| `deque` | `deque([(start, 0)])`、`.popleft()`、`.append()` | 双端队列，两端操作都是 O(1) |
| 容器的真值 | `while queue:`、`while stack:` | 空容器为 False，非空为 True |
| 元组解包 | `node, dist = queue.popleft()`、`order, _ = bfs(...)` | 一次赋多个变量；`_` 表示丢弃 |
| 列表当栈 | `stack.append(...)`、`stack.pop()` | 后进先出 |
| `reversed()` | `reversed(graph.neighbors(node))` | 返回逆序迭代器，不复制列表 |
| `continue` / `break` | `if node in visited: continue`；`if np.allclose(...): break` | 跳过本轮 / 结束循环 |
| 链式比较 | `2 <= k <= graph.n` | 等价于两个比较用 `and` 连接 |
| `raise ValueError` | `raise ValueError(f"k must satisfy ...")` | 主动抛出带说明的异常 |
| 带条件的列表推导 | `[n for n in range(g.n) if n not in bridge_nodes]` | 过滤元素 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |
| NumPy 构造 | `np.zeros((n, n))`、`np.ones(n) / n`、`np.zeros_like(centroids)`、`dtype=int` | 建全 0 / 全 1 数组；`zeros_like` 复制形状和类型 |
| NumPy 切片取列 | `eigenvectors[:, 1]`、`eigenvectors[:, 1:k + 1]` | `:` 表示所有行，逗号后选列 |
| 布尔掩码 | `labels[fiedler < 0] = 1`、`row_sums[row_sums == 0] = 1`、`features[mask]` | 用布尔数组选取或赋值 |
| 花式索引 | `scores[bridge_nodes]`（`bridge_nodes` 是列表） | 用整数列表一次取多个元素 |
| `axis` 与 `keepdims` | `A.sum(axis=1, keepdims=True)`、`np.linalg.norm(..., axis=1)` | 按行聚合；`keepdims` 保留维度以便广播 |
| 广播 | `A / row_sums`、`features - centroids[c]` | 形状 `(n,n)` 除以 `(n,1)`，自动按行扩展 |
| 矩阵乘法 `@` | `A_norm @ features @ weight_matrix` | 等价于 `np.matmul` |
| 线性代数 | `np.linalg.eigh`、`np.linalg.eigvalsh`、`np.linalg.norm` | 对称矩阵特征分解（升序）、只求特征值、范数 |
| 随机数 | `np.random.RandomState(42)`、`rng.choice(n, k, replace=False)`、`rng.randn(5, 3)` | 独立的可复现随机数生成器 |
| 其他 NumPy | `np.argmin(axis=1)`、`mask.any()`、`.mean(axis=0)`、`np.allclose`、`np.where(...)[0]`、`.astype(int)`、`np.round` | 取最小值下标、是否存在 True、按列求均值、近似相等、找满足条件的下标、类型转换、四舍五入 |

---

## 6. 运行结果解读

实际运行（临时副本中执行 `python3 graph_theory.py`，NumPy 2.5）的关键输出：

```text
Graph: Graph(n=6, edges=[0-1, 0-2, 1-3, 2-3, 3-4, 4-5])
  Node 3: degree=3, neighbors=[1, 2, 4]      ← 节点 3 是枢纽
BFS from node 0:
  Visit order: [0, 1, 2, 3, 4, 5]
  Distances:   {0: 0, 1: 1, 2: 1, 3: 2, 4: 3, 5: 4}   ← 按层扩展，距离即最短跳数
DFS from node 0:
  Visit order: [0, 1, 3, 2, 4, 5]            ← 0→1→3 一路深入，回溯到 2，再走 4→5
```

```text
Connected components: [[0, 1, 2], [3, 4], [5, 6]]
Eigenvalues: [-0.  0.  0.  2.  2.  3.  3.]
Number of zero eigenvalues: 3
Match: True
```

- `-0.` 是一个约 −1e-16 的浮点误差四舍五入后的显示，本质就是 0。这也是为什么代码要用 `< 1e-8` 判断零。
- 特征值 2 来自两条孤立边（每条边的拉普拉斯 `[[1,−1],[−1,1]]` 的特征值是 0 和 2），两个 3 来自三角形（0, 3, 3）。**不连通图的谱 = 各分量谱的并集**，因为 L 是分块对角的。

```text
After 1 round of message passing (output dim = 2):
  Node 4: [ 0.1035 -0.4057]
After 2 rounds (2-hop neighborhood info):
  Node 4: [0.6676 0.288 ]
```

特征从 3 维变成 2 维（`W` 是 3×2）。如 3.8 所说，节点 4 第二轮的结果只取决于节点 2 和 4 的原始特征。

```text
Spectral clustering labels: [1 1 1 1 1 0 0 0 0 0]
Laplacian eigenvalues: [0.     0.2984 5.     5.     5.     5.     5.     5.     5.     6.7016]
Fiedler value (algebraic connectivity): 0.2984
```

- 两个团被完美分开（标签编号取决于特征向量的符号）。
- λ₂ = 0.2984 很小，而 λ₃ 跳到 5：λ₂ 与 λ₃ 之间的巨大间隔（**谱间隙**）说明"分成 2 类"非常自然。只靠一条桥连接，图的连通性很弱。

```text
  Node 2: 0.1163      Node 0: 0.0959
Bridge nodes [2, 7] PageRank: 0.1163
Non-bridge nodes avg PageRank: 0.0959
Bridge nodes have higher PageRank -- they connect communities.
```

最后一句的解释不够准确：节点 2、7 的度是 5，其他节点是 4。无向图上随机游走的平稳分布正比于度（`5/42 ≈ 0.119`，`4/42 ≈ 0.095`），把阻尼调到接近 1 后 PageRank 恰好等于这两个值。分数更高是因为**度更高**，不是因为"连接社区"；衡量桥梁作用应该用介数中心性。

---

## 7. 动手改一改

1. **自环版消息传递**：写 `gcn_layer`，用 `D̂^(−1/2)(A+I)D̂^(−1/2)`，再加上 ReLU（`np.maximum(0, x)`）。打印两轮后的"影响矩阵" `S @ S`，确认节点 4 能看到节点 3。
2. **修复谱聚类**：把 `1:k + 1` 改成 `1:k`，在"3 个三角形串联"的图上对比修改前后的结果；再试试用 `sklearn.cluster.KMeans(n_clusters=k, n_init=10)` 替换自写的 k-means。
3. **Dijkstra**（讲义练习 3）：用 `heapq` 实现带权最短路，在所有边权为 1 的图上与 `bfs` 的 `distances` 对比，应完全一致。
4. **介数中心性**：用 BFS 统计所有节点对之间的最短路径经过每个节点的次数（小图可以暴力计算），在两团图上验证桥节点 2、7 的得分远高于其他节点——与 PageRank 的结果形成对比。
5. **带权 PageRank**：把 `damping * scores[u] / out_deg` 改为按 `w(u,v) / weighted_degree(u)` 分配；构造一个有向带权小图，与 `networkx.pagerank(G, weight="weight")` 对拍。
6. **拓扑排序**：基于 DFS 的完成顺序（后序）实现有向无环图的拓扑排序，并加上环检测（遇到"正在访问中"的节点即为有环）。

---

## 8. 常见坑

- **带权图的度用错**：度矩阵必须用权重和，否则 L 的行和不为 0，不再半正定，"零特征值 = 连通分量数"也随之失效。
- **用 `== 0` 判断特征值**：数值误差会让 0 变成 `±1e-16`，必须用容差。
- **把谱聚类的标签编号当真**：特征向量的符号是任意的，簇 0、簇 1 的编号随时可能互换。
- **BFS 出队时才标记 visited**：同一节点会被重复入队，复杂度和结果都会出问题。
- **以为"K 层消息传递 = K 跳以内"**：没有自环时只覆盖"恰好 K 步"的游走；GCN 必须加 `A + I`。
- **在大图上用稠密矩阵**：`adjacency_matrix()` 和 `eigh` 都是 O(n²) 内存 / O(n³) 时间，几万个节点就会撑爆内存。
