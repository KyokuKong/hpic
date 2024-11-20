# Hpic

对Playwright进行封装，利用无头Chrome/Firefox进行网页截图实现图片渲染。

内置了Chrome线程池管理和Jinja2模板渲染支持，原生异步渲染。

## 安装

```shell
pip install hpic
```

## 使用

```python
import asyncio
from hpic import Hpic

h = Hpic()
asyncio.run(h.render("https://www.github.com", data={}, output="github.png"))

```
