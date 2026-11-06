"""A tiny root router loads deeper documentation only for this turn's needs."""
from __future__ import annotations
from pathlib import Path,PurePosixPath

def context_paths(requested_paths:list[str])->list[str]:
    """Correct supplied path boundary: repo-relative POSIX paths, normalized and
    stable-deduplicated, with AGENTS.md first exactly once. Inputs name existing
    Markdown regular files inside a fixture repository with no symlinks. Path/security
    validation is given, not a new candidate defect.
    """
    ordered=[];seen=set()
    for raw in ['AGENTS.md',*requested_paths]:
        if not isinstance(raw,str) or not raw or '\\' in raw:raise ValueError('relative context path')
        path=PurePosixPath(raw)
        if path.is_absolute() or '..' in path.parts or str(path)=='.':raise ValueError('relative context path')
        name=path.as_posix()
        if name not in seen:seen.add(name);ordered.append(name)
    return ordered

def read_document(root:Path,name:str)->str:
    """Correct supplied UTF-8 document read preserving its complete text."""
    with (root/name).open(encoding='utf-8',newline='') as f:return f.read()

def load_context(root:Path,requested_paths:list[str])->list[tuple[str,str]]:
    """Return (repo-relative path, complete text): root AGENTS.md first, followed by
    this turn's explicit requested files in normalized first-request order, once.
    Use the supplied path/read helpers. Load only those files, without enumerating
    the workspace or reading unrelated Markdown. Each call reads fresh selected
    documents; no catalog or cross-turn text cache is part of this tiny router.
    """
    return [(name,read_document(root,name)) for name in context_paths(requested_paths)]
