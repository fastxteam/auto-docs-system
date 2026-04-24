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
- 如果某个目录下没有 `README.md` 或 `index.md`，`build-docs` 会自动生成一个目录级 `index.md`
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
- `app/tools/install.md` 且目录下无 `README.md` 时，会额外自动生成 `/tools/index.html`

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
- 生成 `release-center/history/index.html`
- 生成 `release-center/modules/<module>.html`
- 把汇总统计注入首页的“版本发布总览”模块

也可以单独执行：

```powershell
uv run scan-releases
```

示例 1，单架构工具：

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
doc_checklist = { software_copyright = "", patent = "", user_manual = "README.md", design_spec = "", test_report = "" }

[[history]]
version = "1.3.0"
channel = "stable"
released_at = "2026-04-23"
title = "接入版本中心与发布日志"
summary = "新增汇总页、时间线和模块日志页。"
changes = [
  "自动生成 release-center/index.html",
  "自动生成 release-center/history/index.html",
  "自动生成模块级发布日志页",
]
breaking_changes = []
architecture_notes = "版本信息改为从 release.toml 渲染。"
```

说明：

- `[version]` 表示当前版本快照
- `[architecture]` 表示当前唯一架构线
- `doc_checklist` 表示该架构线下的固定文档点检清单
- `[[history]]` 表示历史发布记录，按版本维度输出日志
- 即使不写 `[[history]]`，系统也会用 `[version]` 自动兜底生成一条当前版本记录

示例 2，同一个工具下按架构线拆分，例如 `ARC_V1` / `ARC_V2`：

```toml
[module]
name = "scripts"
summary = "脚本主模块"
owner = "Platform Team"
home = "README.md"

[[architectures]]
name = "ARC_V1"
summary = "旧架构线，继续维护稳定任务。"
home = "README.md"
style = "CLI + Batch"
runtime = "Python 3.13"
entrypoints = ["cleanup.py"]
interfaces = ["CLI", "Markdown Docs"]
platforms = ["Windows"]
dependencies = []
current = "1.3.0"
channel = "stable"
released_at = "2026-04-23"
notes = "ARC_V1 进入维护期，保持现有批处理能力。"
architecture_notes = "面向现网任务，优先保证兼容性。"
doc_checklist = { software_copyright = "", patent = "", user_manual = "README.md", design_spec = "", test_report = "" }

[[architectures.history]]
version = "1.3.0"
channel = "stable"
released_at = "2026-04-23"
title = "ARC_V1 维护版本"
summary = "补充版本中心和历史日志。"
changes = [
  "接入 release-center",
  "补齐 ARC_V1 当前版本说明",
]
breaking_changes = []

[[architectures]]
name = "ARC_V2"
summary = "新架构线，用于承接后续模块化改造。"
home = "README.md"
style = "CLI + Modular Pipeline"
runtime = "Python 3.13"
entrypoints = ["cleanup.py"]
interfaces = ["CLI", "Markdown Docs"]
platforms = ["Windows"]
dependencies = ["report"]
current = "2.0.0-beta.1"
channel = "beta"
released_at = "2026-04-23"
notes = "ARC_V2 开始分层治理任务入口和统计输出。"
architecture_notes = "逐步替换旧批处理拼装方式。"
doc_checklist = { software_copyright = "", patent = "", user_manual = "README.md", design_spec = "", test_report = "" }

[[architectures.history]]
version = "2.0.0-beta.1"
channel = "beta"
released_at = "2026-04-23"
title = "ARC_V2 首个测试版本"
summary = "为后续模块化拆分建立新架构线。"
changes = [
  "建立 ARC_V2 架构线",
  "开始独立记录 ARC_V2 发布日志",
]
breaking_changes = [
  "新旧架构线发布节奏独立维护",
]
```

多架构模式说明：

- `[[architectures]]` 表示同一个工具下的一条架构线
- `doc_checklist` 表示该架构线下的固定文档点检清单
- `[[architectures.history]]` 表示该架构线自己的版本历史
- 生成结果仍然是“一个工具一个发布日志页”，但页内会按 `ARC_V1`、`ARC_V2` 分节展示
- `release-center/index.md` 会汇总所有工具和架构线
- `release-center/history/index.md` 会把所有架构线的历史记录合并成全局时间线
- 同一个 `release.toml` 内，不要混用旧格式 `[version]/[architecture]/[[history]]` 和新格式 `[[architectures]]`

简化后的文档点检约定：

- `doc_checklist` 固定只管理 5 项：`software_copyright`、`patent`、`user_manual`、`design_spec`、`test_report`
- 值直接写 Markdown 路径即可，例如 `user_manual = "README.md"`
- 留空字符串 `""` 表示该项还没补齐
- 如果确实需要更细状态，也可以写成 `user_manual = { path = "README.md", status = "in_progress" }`
- 页面里会统一渲染为：软著、专利、用户手册、设计方案、测试报告
- 每个版本迭代的变更记录，不建议继续塞进 `release.toml`，而是直接写进 `user_manual` 对应的文档中

关于积分管理的建议：

- 不建议继续把积分明细写在 `release.toml` 里
- `release.toml` 更适合做“版本快照 + 文档点检”，不适合做人/分值/审批流管理
- 如果后面一定要做积分，建议单独维护一份“贡献台账”，按人和周期管理，而不是按版本管理
- 推荐位置可以是 `auto_docs/contribution_registry/2026Q2.toml` 这类独立文件，后续再由脚本汇总
- 旧格式 `documents` / `score_items` 仍兼容读取，但不再推荐继续新增

## 你最关心的两个问题

### 1. 是否有现成方案

有，优先推荐 `MkDocs`，而不是自己写 Markdown 渲染器。

### 2. 是否能扫描所有 Markdown

能。当前脚本会递归扫描 `app/` 下所有 `.md`，并按下面的规则生成页面路径：

- `README.md` -> 当前目录首页页面
- 其他 `*.md` -> 当前目录下的独立页面
- 如果目录下没有 `README.md` / `index.md`，系统会自动补一个目录首页
- 例如 `app/tools/README.md` -> `/tools/index.html`
- 例如 `app/tools/install.md` -> `/tools/install.html`
- 例如只有 `app/tools/install.md` 时，仍会自动生成 `/tools/index.html`
- 例如 `app/index.md` -> `/index/index.html`
