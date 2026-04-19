# Python 脚本中心

这个站点会自动扫描 `app/` 下的 Markdown，并按照目录结构生成静态页面路由。

## 约定

- Python 脚本放在 `app/`
- 说明文档和脚本放在一起维护
- `index.md` 作为目录首页
- `README.md` 也会在构建时自动转成目录首页

## 下一步

1. 在 `app/` 下按业务拆目录
2. 每个目录补一个 `index.md` 或 `README.md`
3. 执行 `uv run build-docs`

