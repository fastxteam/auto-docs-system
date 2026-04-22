# 交叉引用与动态图表示例

这个页面专门验证 `autonumber` 的跨页引用，以及 `echarts` / `codexec` 在当前站点中的工作方式。

## 跨页引用

首页示例页中的 @Tbl:doc-pipeline 描述了构建阶段，@Th:route-rule 约束了 `README.md` 与普通 Markdown 的路由分配。

如果这里的链接仍然是可点击的相对路径，说明本地静态 HTML 场景下的交叉引用已经兼容好了。

## ECharts

/// echarts
    renderer: "canvas"
    attrs:
        style: "width:100%;height:360px;"

{
  tooltip: {
    trigger: 'axis'
  },
  xAxis: {
    type: 'category',
    data: ['scan', 'stage', 'build', 'link', 'emit']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      type: 'bar',
      data: [4, 3, 3, 2, 1],
      barWidth: '46%',
      itemStyle: {
        color: '#2563eb'
      }
    }
  ]
}
///

## Codexec

!!! info "说明"
    `codexec` 会在浏览器里调用在线 REPL 服务执行代码，因此静态站点可以构建成功，但运行按钮需要联网。

/// codexec

    :::python
    routes = [
        ("app/README.md", "/index.html"),
        ("app/showcase/README.md", "/showcase/index.html"),
        ("app/showcase/references.md", "/showcase/references.html"),
    ]

    for source, target in routes:
        print(f"{source} -> {target}")

///

## 相关配置片段

/// tab | Plugins

    :::yaml
    plugins:
      - shadcn-lwq/search
      - shadcn-lwq/autonumber
      - shadcn-lwq/excalidraw
///

/// tab | Markdown Extensions

    :::yaml
    markdown_extensions:
      - pymdownx.blocks.caption
      - pymdownx.blocks.tab
      - pymdownx.arithmatex
      - shadcn.extensions.iconify
      - shadcn.extensions.hover_card
      - shadcn.extensions.echarts.alpha
      - shadcn.extensions.codexec
///
