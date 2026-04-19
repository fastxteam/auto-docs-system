# Python 脚本文档系统

这套方案基于 `MkDocs + Material for MkDocs`，外层再包一层很薄的 Python 构建脚本，满足下面几个要求：

- 所有 Python 脚本都放在 `app/`
- 递归扫描 `app/**/*.md`
- 按目录结构生成静态站点路由
- 使用 `uv` 管理依赖
- 一条命令构建成 HTML

## 为什么选这个方案

`MkDocs` 本身就是现成方案，天然把 Markdown 渲染为静态 HTML，适合做脚本目录、工具说明、运行手册。  
这里额外加了 `auto_docs/docsite.py`，专门负责文档扫描和构建，`app/` 只保留业务脚本与业务文档：

- `app/` 里可以同时放 `.py` 和 `.md`
- 扫描时只提取文档相关文件
- `README.md` 会自动映射为同目录的 `index.md`
- 如果同目录同时存在 `index.md` 和 `README.md`，优先使用 `index.md`
- 最终路由更接近目录语义，而不是出现 `/readme/`

## 目录约定

```text
auto_docs/
  docsite.py
app/
  index.md
  scripts/
    cleanup.py
    index.md
    report/
      README.md
```

示例路由：

- `app/index.md` -> `/`
- `app/scripts/index.md` -> `/scripts/`
- `app/scripts/report/README.md` -> `/scripts/report/`

## 使用方式

```powershell
uv sync
uv run scan-docs
uv run build-docs
```

构建产物输出到：

```text
dist/html
```

## 你最关心的两个问题

### 1. 是否有现成方案

有，优先推荐 `MkDocs`，而不是自己写 Markdown 渲染器。

### 2. 是否能扫描所有 Markdown

能。当前脚本会递归扫描 `app/` 下所有 `.md`，并保留目录层级来生成页面路径。
