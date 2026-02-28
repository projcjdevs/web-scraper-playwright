import asyncio
import time
import logging
from playwright.async_api import async_playwright, Browser, Playwright

logger = logging.getLogger("audit.browser_manager")

class BrowserManager:

    def __init__(
        self, 
        max_concurrent_browsers: int = 1, # one website lead per run para mas efficient, pero pwede rin mag multiple browsers if needed
        max_audits_before_restart: int = 20,
        max_uptime_seconds: int = 1750,
    ):
        self._max_concurrent_browsers = max_concurrent_browsers
        self._max_audits = max_audits_before_restart
        self._max_uptime = max_uptime_seconds

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent_browsers)
        self._audit_count: int = 0
        self._start_time: float = 0.0
        self._active: bool = False
        self._waiting_count: int = 0
        self._restart_lock: asyncio.Lock = asyncio.Lock() 

    async def start(self):
        logger.info("Launching Playwright instance...sana gumana")
        self._playwright = await async_playwright().start()
        await self._launch_browser()
        logger.info("Browser launched successfully.(YAY)")

    async def _launch_browser(self) -> None:
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",   
                "--disable-extensions",
                "--no-sandbox",               
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",  
            ],
        )
        self._audit_count = 0
        self._start_time = time.monotonic()
        logger.info("Browser launched and ready for audits.")

    async def _maybe_restart(self) -> None:
        needs_restart = (
            self._audit_count >= self._max_audits or
            (time.monotonic() - self._start_time) >= self._max_uptime
        )
        if not needs_restart:
            return
        
        async with self._restart_lock:
            still_needs_restart = (
                self._audit_count >= self._max_audits or
                (time.monotonic() - self._start_time) >= self._max_uptime
            )
            if not still_needs_restart:
                return
            
            logger.warning(
                "Restarting browser (audits=%d, uptime=%.0fs).", 
                self._audit_count,
                time.monotonic() - self._start_time,
            )
            try: 
                await self._browser.close()
            except Exception as e:
                logger.error("Error closing browser during restart: %s", e)
            await self._launch_browser()

    async def acquire_context(self):
        if self._active:
            self._waiting_count += 1
            logger.info(
                "Audit queued — waiting for current audit to finish (%d in queue)",
                self._waiting_count,
            )

        await self._semaphore.acquire()

        if self._waiting_count > 0:
            self._waiting_count -= 1

        self._active = True

        try:
            await self._maybe_restart()

            if not self._browser or not self._browser.is_connected():
                logger.warning("Browser found dead on acquire — force relaunching...")
                await self._launch_browser()

            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                java_script_enabled=True,
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            return context

        except Exception:
            self._active = False
            self._semaphore.release()
            raise

    def release_context(self) -> None:
        self._audit_count += 1
        self._active = False
        self._semaphore.release()

    async def stop(self) -> None:
        logger.info("Shutting down browser manager...")
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.error("Error closing browser during shutdown: %s", e)
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser manager shutdown complete.")
        