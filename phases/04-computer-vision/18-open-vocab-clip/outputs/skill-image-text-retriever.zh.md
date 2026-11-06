---
name: skill-image-text-retriever
description: Build an image embedding index with any CLIP checkpoint; support query-by-text and query-by-image
version: 1.0.0
phase: 4
lesson: 18
tags: [clip, retrieval, faiss, zero-shot]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="image-text-retriever"></a>

# 图文检索器

使用 CLIP embeddings 将图像文件夹转换为可搜索索引。

<a id="when-to-use"></a>

## 何时使用

- 在内部目录上构建 zero-shot 图像搜索。
- 通过 embedding 距离对几乎相同的图像进行重复数据删除。
- 构建一个快速“查找相似”组件，无需标记数据集。

<a id="inputs"></a>

## 输入

- `image_folder`：图像文件目录。
- `clip_model`：HuggingFace id，如 `openai/clip-vit-base-patch32` 或 `google/siglip-base-patch16-224`。
- `index_type`：平 | 体外受精 | HNSW.
- `embedding_dim`：从模型推断。

<a id="steps"></a>

## 步骤

1. 加载 CLIP 模型和预处理器。
2. 对文件夹中的每个图像进行批量编码。将 embeddings 保存为 (N, D) float32 + 文件名列表。
3. 在 embeddings 上构建 FAISS 索引。对 cosine similarity 的 L2 归一化向量使用内积。
4. 暴露两个查询接口：
   - `search_by_text(text, k)` — 嵌入文本、搜索。
   - `search_by_image(image_path, k)` — 嵌入图像，搜索。

<a id="output-template"></a>

## 输出模板

```python
import os
import glob
import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor
import faiss


class ImageTextRetriever:
    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        self.model = CLIPModel.from_pretrained(model_name).eval()
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.dim = self.model.config.projection_dim
        self.index = None
        self.filenames = []

    @torch.no_grad()
    def _encode_images(self, paths, batch=16):
        embs = []
        for i in range(0, len(paths), batch):
            imgs = [Image.open(p).convert("RGB") for p in paths[i:i + batch]]
            inputs = self.processor(images=imgs, return_tensors="pt")
            out = self.model.get_image_features(**inputs)
            out = out / out.norm(dim=-1, keepdim=True)
            embs.append(out.cpu().numpy())
        return np.concatenate(embs).astype(np.float32)

    @torch.no_grad()
    def _encode_text(self, texts):
        inputs = self.processor(text=texts, return_tensors="pt", padding=True)
        out = self.model.get_text_features(**inputs)
        out = out / out.norm(dim=-1, keepdim=True)
        return out.cpu().numpy().astype(np.float32)

    def build_index(self, folder, index_type="flat"):
        exts = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp")
        files = []
        for ext in exts:
            files.extend(glob.glob(os.path.join(folder, ext)))
        self.filenames = sorted(files)
        embs = self._encode_images(self.filenames)
        if index_type == "IVF":
            quantizer = faiss.IndexFlatIP(self.dim)
            nlist = min(256, max(4, len(embs) // 32))
            self.index = faiss.IndexIVFFlat(quantizer, self.dim, nlist)
            self.index.train(embs)
        elif index_type == "HNSW":
            self.index = faiss.IndexHNSWFlat(self.dim, 32, faiss.METRIC_INNER_PRODUCT)
        else:
            self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(embs)

    def search_by_text(self, text, k=5):
        q = self._encode_text([text])
        dist, idx = self.index.search(q, k)
        return [(self.filenames[i], float(d)) for d, i in zip(dist[0], idx[0])]

    def search_by_image(self, image_path, k=5):
        q = self._encode_images([image_path])
        dist, idx = self.index.search(q, k)
        return [(self.filenames[i], float(d)) for d, i in zip(dist[0], idx[0])]
```

<a id="report"></a>

## 报告

```
[retriever]
  model:          <name>
  num_images:     <int>
  dim:            <int>
  index_type:     flat | IVF | HNSW
  index_size_mb:  <float>
```

<a id="rules"></a>

## 规则

- 在索引之前始终对 embeddings 进行 L2 归一化； FAISS 在归一化向量上的内积等于 cosine similarity。
- 对于 < 100k 图像，`IndexFlatIP`（精确）是最简单且最快的。
- 对于 100k-10M，`IndexIVFFlat` 是标准权衡。
- 对于 > 10M，请使用 HNSW 或乘积量化变体。
- 切勿在每个查询上重建索引；嵌入一​​次，搜索多次。
