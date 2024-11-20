import asyncio

from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright


class BrowserProcess:
    def __init__(self, browser):
        self.browser = browser
        self.lock = asyncio.Lock()
    
    async def close(self):
        await self.browser.close()


class DriverContextManager:
    def __init__(self, proc, pool):
        self.proc = proc
        self.browser = proc.browser
        self.pool = pool
    
    async def __aenter__(self):
        return self.browser
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.proc.lock.release()
        # 通知等待的协程有进程可用
        async with self.pool.condition:
            self.pool.condition.notify()


class BrowserPool:
    env: Environment
    
    def __init__(self):
        self.max_processes = 0
        self.processes = []
        self.playwright = None
        self.process_lock = asyncio.Lock()
        self.condition = asyncio.Condition()
        self.initialized = False
    
    async def init(self, env: Environment = Environment(loader=FileSystemLoader('./template'))):
        self.playwright = await async_playwright().start()
        self.initialized = True
        # 初始化Jinja2模板引擎
        self.env = env
    
    async def get_driver(self) -> DriverContextManager:
        if not self.initialized:
            await self.init()
        
        async with self.condition:
            while True:
                # 尝试获取空闲的浏览器进程
                for proc in self.processes:
                    if not proc.lock.locked():
                        await proc.lock.acquire()
                        return DriverContextManager(proc, self)
                
                # 如果没有空闲的进程，且未达到最大进程数，则创建新进程
                if len(self.processes) < self.max_processes:
                    browser = await self.playwright.chromium.launch()
                    proc = BrowserProcess(browser)
                    await proc.lock.acquire()
                    self.processes.append(proc)
                    return DriverContextManager(proc, self)
                else:
                    # 达到最大进程数，等待进程释放
                    await self.condition.wait()
    
    async def close(self):
        async with self.process_lock:
            for proc in self.processes:
                await proc.close()
            self.processes = []
        if self.playwright:
            await self.playwright.stop()
            self.initialized = False
