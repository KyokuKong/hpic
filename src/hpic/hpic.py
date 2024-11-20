import os.path
from lib2to3.fixes.fix_input import context
from pathlib import Path

import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .playwright_manager import BrowserPool
from urllib import parse


class Hpic:
    manager: BrowserPool  # 浏览器进程池
    
    def __init__(self, process_limit=3, jinja_env="./"):
        """基于Playwright的Html图像渲染，支持多进程和自动资源管理 \n
        可选参数：\n
        - process_limit: 最大浏览器进程数 \n
        - jinja_env: Jinja2模板引擎环境 \n
        """
        
        m = BrowserPool()
        m.max_processes = process_limit
        m.env = Environment(loader=FileSystemLoader(jinja_env))
        self.manager = m
    
    async def render(self, template: any,
                     data: dict[str, any] = None,
                     width: int = 450,
                     height: int = 800,
                     output: str = "output.png",
                     is_full_page: bool = False,
                     skip_template: bool = False):
        """对浏览器进程池发起渲染请求，在浏览器渲染完成后截图返回渲染结果 \n
        在进程池设置偏小的场景下，这个函数可能会导致一定时间内的阻塞，如果你需要在主线程中使用hpic，那么使用异步版本是一个更好的选择 \n
        render()可以接受以下参数作为template，包括网页URL，本地URL，HTML字符串，Jinja2模板，jinja2模板名称等 \n
        当传入了字典作为data时，render()会将模板作为jinja2模板进行渲染，并将data替换进模板中的占位符 \n
        注意：直接传入jinja2模板文件名时"""
        u = "" # 如果是网站url则存入这个变量
        t: jinja2.Template = jinja2.Template("")  # 初始化一个空模板
        # 封装判定传入的模板是否为url的函数
        def is_url(content: str) -> bool:
            """检查字符串是否是URL"""
            # 使用urlparse检查是否是有效的URL
            parsed = parse.urlparse(content)
            return bool(parsed.scheme) or content.startswith(("./", "../"))  # 支持相对路径URL
        # 如果传入的模板是URL则直接通过goto方法访问url，否则将其作为html字符串传入
        # 这里判断传入的template是文件名时，是否在 当前根目录中存在该文件
        if isinstance(template, str) and not is_url(template):
            if template.endswith(".jinja2") or template.endswith(".html") or template.endswith(".htm"):
                # 在当前根目录中查找对应文件，查找到则说明此url为本地文件
                if os.path.exists(template):
                    # 查找到文件则将url改写成./开头的相对路径
                    template = f"./{template}"
                # 不存在则尝试用jinja的模板引擎加载（尝试让jinja在其模板目录中查找并加载）
                try:
                    template = self.manager.env.get_template(template)
                    t = template
                except TemplateNotFound as e:
                    raise e
            else:
                # 作为html内容传入jinja
                t = jinja2.Template(template)
        # 这里判断传入的url是否是网站，不是则将其传入jinja
        elif isinstance(template, str) and is_url(template):
            if template.startswith("http://") or template.startswith("https://"):
                # 作为网页URL传入
                u = template
            else:
                # 作为本地URL传入
                if skip_template:
                    # 跳过模板加载
                    html_path = Path(template).resolve()
                    u = f"file://{html_path}"
                else:
                    with open(template, "r", encoding="utf-8") as f:
                        t = jinja2.Template(f.read())
        
        # 如果t为空则说明传入的是网页url，直接通过goto访问，否则渲染模板
        html_content = t.render(data) if t else ""
        
        # 从池中获取浏览器实例
        async with await self.manager.get_driver() as browser:
            try:
                page = await browser.new_page()
                
                # 设置页面内容
                if html_content:
                    await page.set_content(html_content)
                else:
                    await page.goto(u)
                
                # 等待页面加载完成
                await page.wait_for_load_state('networkidle')
                # 获取页面内容高度
                content_height = await page.evaluate('''() => {
                                return Math.max(
                                    document.body.scrollHeight,
                                    document.body.offsetHeight,
                                    document.documentElement.clientHeight,
                                    document.documentElement.scrollHeight,
                                    document.documentElement.offsetHeight
                                );
                            }''')
                
                # 设置视口大小（可根据内容调整）
                await page.set_viewport_size({"width": width, "height": content_height if not height else height})
                
                # 截图并保存到指定路径
                await page.screenshot(path=output, full_page=is_full_page)
                
            finally:
                # 关闭页面
                await page.close()

        
        
        
            