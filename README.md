# Python 脚本文档系统

这套方案基于 `MkDocs + mkdocs-shadcn`，外层再包一层很薄的 Python 构建脚本，满足下面几个要求：

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
- 只有 `README.md` 会作为目录首页
- 其他非 `README.md` 的 Markdown 都会作为普通内容页
- 普通内容页路由按“目录 + 文件名”生成
- 如果两个文件会生成同一路由，构建时直接报错
- 针对 `mkdocs-shadcn` 在 Windows 下的路径警告做了运行时修补
- 构建结果使用文件式链接，便于拷到其他电脑直接打开

## 目录约定

```text
auto_docs/
  docsite.py
app/
  README.md
  scripts/
    cleanup.py
    README.md
    cleanup.md
    report/
      README.md
```

示例路由：

- `app/README.md` -> `/index.html`
- `app/scripts/README.md` -> `/scripts/index.html`
- `app/scripts/cleanup.md` -> `/scripts/cleanup.html`
- `app/scripts/report/README.md` -> `/scripts/report/index.html`

## 使用方式

```powershell
uv sync
uv run scan-docs
uv run scan-releases
uv run build-docs
```

构建产物输出到：

```text
dist/html
```

## 版本发布管理

每个子模块目录都可以放一个 `release.toml`，用来描述版本、发布通道和架构信息。  
`uv run build-docs` 时会自动：

- 扫描所有子模块的 `release.toml`
- 生成 `release-center/index.html`
- 把汇总统计注入首页的“版本发布总览”模块

也可以单独执行：

```powershell
uv run scan-releases
```

示例：

```toml
[module]
name = "scripts"
summary = "脚本主模块"
owner = "Platform Team"
home = "README.md"

[version]
current = "1.3.0"
channel = "stable"
released_at = "2026-04-23"
notes = "统一文档构建与版本汇总入口。"

[architecture]
style = "CLI + Batch"
runtime = "Python 3.13"
entrypoints = ["cleanup.py"]
interfaces = ["CLI", "Markdown Docs"]
platforms = ["Windows"]
dependencies = []
notes = "由 auto_docs 统一扫描和汇总。"
```

## 你最关心的两个问题

### 1. 是否有现成方案

有，优先推荐 `MkDocs`，而不是自己写 Markdown 渲染器。

### 2. 是否能扫描所有 Markdown

能。当前脚本会递归扫描 `app/` 下所有 `.md`，并按下面的规则生成页面路径：

- `README.md` -> 当前目录首页页面
- 其他 `*.md` -> 当前目录下的独立页面
- 例如 `app/tools/README.md` -> `/tools/index.html`
- 例如 `app/tools/install.md` -> `/tools/install.html`
- 例如 `app/index.md` -> `/index/index.html`
