import base64
import io
import logging
from PIL import Image
from playwright.async_api import Page

logger = logging.getLogger("audit.screenshotter")

MAX_WIDTH = 1000
JPEG_QUALITY = 65
VIEWPORT_HEIGHT = 900

def _optimize_screenshot(png_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(png_bytes))
        img = img.convert("RGB") 

        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            new_height = int(img.height * ratio)
            img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        jpeg_bytes = buffer.getvalue()

        size_kb = len(jpeg_bytes) / 1024
        logger.debug(
            "Screenshot optimized: %dx%d -> %dx%d, %.1f KB",
            png_bytes and Image.open(io.BytesIO(png_bytes)).width or 0,
            png_bytes and Image.open(io.BytesIO(png_bytes)).height or 0,
            img.width, img.height, size_kb,
        )

        if size_kb > 500:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=45, optimize=True)
            jpeg_bytes = buffer.getvalue()
            logger.debug("Re-compressed to quality 45 to reduce size: %.1f KB", len(jpeg_bytes) / 1024)

        return base64.b64encode(jpeg_bytes).decode("utf-8")
    
    except Exception as e:
        logger.error("ERROR: Screenshot optimization failed: %s", e)
        return ""
    

async def capture_screenshot(page: Page) -> dict[str, str]:

    screenshots = {"hero": "", "mid": "", "footer": ""}

    try:
        hero_bytes = await page.screenshot(type="png")
        screenshots["hero"] = _optimize_screenshot(hero_bytes)

        try:
            await page.evaluate("window.scrollBy(0, 900)")
            await page.wait_for_timeout(600)

            await page.evaluate("document.readyState")  
            mid_bytes = await page.screenshot(type="png")
            screenshots["mid"] = _optimize_screenshot(mid_bytes)

        except Exception as e:
            logger.warning("Mid screenshot failed, skipping: %s", e)

        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(600)

            await page.evaluate("document.readyState") 
            footer_bytes = await page.screenshot(type="png")
            screenshots["footer"] = _optimize_screenshot(footer_bytes)

        except Exception as e:
            logger.warning("Footer screenshot failed, skipping: %s", e)

    except Exception as e:
        logger.error("Screenshot capture failed: %s", e)

    return screenshots 