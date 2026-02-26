import asyncio
import logging
from playwright.async_api import BrowserContext, TimeoutError as PlaywrightTimeout

from app.config import NAVIGATION_TIMEOUT_MS, MAX_RETRIES
from app.core.dom_extractor import extract_all_signals
from app.core.screenshotter import capture_screenshot

logger = logging.getLogger("audit.analyzer")


async def run_audit(context: BrowserContext, url: str) -> dict:

    resolved_url = url
    last_error = None
    page = None 

    try:
        for attempt in range(MAX_RETRIES + 1):

            if page:
                try:
                    await page.close()
                except Exception:
                    pass  

            page = await context.new_page()

            await page.route(
                "**/*.{mp4,webm,ogg,mp3,wav,flac,aac,woff2,woff,ttf,otf}",
                lambda route: route.abort(),
            )

            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )
                resolved_url = page.url

                if response and response.status in (401, 403, 407):
                    return {
                        "status": "auth_blocked",
                        "resolved_url": resolved_url,
                        "error_reason": f"HTTP {response.status}: Access denied/authentication required",
                    }

                if response and response.status >= 500:
                    if attempt < MAX_RETRIES:
                        logger.warning(
                            "Server error %d on attempt %d for %s, retrying...",
                            response.status, attempt + 1, url,
                        )
                        await asyncio.sleep(1)
                        continue
                    return {
                        "status": "navigation_error",
                        "resolved_url": resolved_url,
                        "error_reason": f"HTTP {response.status}: Server error after {MAX_RETRIES + 1} attempts",
                    }

                last_error = None
                break

            except PlaywrightTimeout as e:

                last_error = "timeout"
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "Timeout on attempt %d for %s, retrying with fresh page...",
                        attempt + 1, url,
                    )
                    await asyncio.sleep(0.5)
                    continue

                return {
                    "status": "timeout",
                    "resolved_url": resolved_url,
                    "error_reason": f"Page load exceeded {NAVIGATION_TIMEOUT_MS}ms after {MAX_RETRIES + 1} attempts",
                }

            except Exception as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "Navigation error on attempt %d for %s: %s",
                        attempt + 1, url, e,
                    )
                    await asyncio.sleep(0.5)
                    continue

                error_str = str(e).lower()
                if "err_name_not_resolved" in error_str:
                    status = "navigation_error"
                    reason = "DNS resolution failed - domain does not exist"
                elif "err_connection_refused" in error_str:
                    status = "navigation_error"
                    reason = "Connection refused - server is down or port blocked"
                elif "ssl" in error_str:
                    status = "navigation_error"
                    reason = f"SSL/TLS error: {e}"
                else:
                    status = "navigation_error"
                    reason = f"Navigation failed: {e}"

                return {
                    "status": status,
                    "resolved_url": resolved_url,
                    "error_reason": reason,
                }

        if last_error:
            return {
                "status": "timeout" if last_error == "timeout" else "navigation_error",
                "resolved_url": resolved_url,
                "error_reason": f"Failed after {MAX_RETRIES + 1} attempts: {last_error}",
            }

        try:
            dom_signals, screenshots = await asyncio.gather(
                extract_all_signals(page),
                capture_screenshot(page),
            )
        except Exception as e:
            logger.error("Extraction/screenshot error for %s: %s", url, e)
            try:
                dom_signals = await extract_all_signals(page)
            except Exception:
                dom_signals = {}
            try:
                screenshots = await capture_screenshot(page)
            except Exception:
                screenshots = {"hero": "", "mid": "", "footer": ""}

        page_load_time_ms = dom_signals.pop("page_load_time_ms", 0)

        return {
            "status": "success",
            "resolved_url": resolved_url,
            "technical": dom_signals,
            "screenshots": screenshots,
            "performance": {"page_load_time_ms": page_load_time_ms},
        }

    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass  