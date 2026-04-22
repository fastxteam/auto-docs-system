# Markdown 与 shadcn-lwq 能力示例

这个目录专门演示当前文档站已经接入的 `markdown_extensions` 与 `mkdocs-shadcn-lwq` 插件能力。

## 当前已启用

- `shadcn-lwq/search`
- `shadcn-lwq/autonumber`
- `shadcn-lwq/excalidraw`
- `pymdownx.blocks.details`
- `pymdownx.blocks.caption`
- `pymdownx.blocks.tab`
- `pymdownx.arithmatex`
- `shadcn.extensions.iconify`
- `shadcn.extensions.hover_card`
- `shadcn.extensions.echarts.alpha`
- `shadcn.extensions.codexec`

## Iconify 行内图标

状态图标可以直接内嵌在正文里：

- 扫描目录 +lucide:folder-search;height=1.1em+
- 构建页面 +heroicons:bolt-solid;color=#2563eb;height=1.1em+
- 输出 HTML +lucide:file-code-2;height=1.1em+

## Hover Card 悬浮信息

把鼠标悬停到 [路由规则]^[#route-card]，或者看一个 [行内提示]^[`README.md` 会被当作目录首页，其余 Markdown 则保持普通内容页语义。]。

/// hover-card | route-card
    position: right

`README.md` 会映射到当前目录的 `index.html`，普通 `*.md` 会映射到同目录下的独立页面。

///

## 标签页

/// tab | `uv run scan-docs`

    :::bash
    uv run scan-docs
///

/// tab | `uv run build-docs`

    :::bash
    uv run build-docs
///

/// tab | 路由规则

    :::text
    README.md -> 当前目录 index.html
    其他 *.md -> 当前目录下的独立 html
///

## 公式渲染

脚本页面数量和构建成本可以粗略表示为：

$$
T \approx n_{\text{markdown}} + n_{\text{assets}}
$$

如果每个目录都保留一个 `README.md`，那么导航的层级信息也能稳定保留下来。

## Caption + Autonumber

| 阶段 | 输入 | 输出 |
| :--- | :--- | :--- |
| Scan | `app/**/*.md` | 源 Markdown 清单 |
| Stage | `app/` + 资源文件 | `.doc_build/docs/` |
| Build | MkDocs + Theme | `dist/html/` |

/// table-caption
{#tbl:doc-pipeline} 文档构建流水线的三个阶段。
///

!!! note "{#th:route-rule} 路由分配规则"
    `README.md` 作为目录首页，其他 Markdown 作为普通内容页。

## Excalidraw

下面这张图通过 `shadcn-lwq/excalidraw` 插件在构建时内联 SVG：

~{文档构建流程}(docsite-flow.json)

## 继续查看

- 跨页引用、ECharts 和 Codexec 示例：见 [references.md](references.md)
