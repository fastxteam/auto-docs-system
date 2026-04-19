# cleanup

这是普通内容页示例，不是目录首页。

## 路由

这个文件会被映射到：

```text
/scripts/cleanup.html
```

## 适合放什么

- 单个脚本说明
- 参数解释
- 使用示例
- 常见问题

## 示例代码

```python
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    print(f"working in {root}")


if __name__ == "__main__":
    main()
```
