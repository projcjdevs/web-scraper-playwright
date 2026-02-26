import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI 
from fastapi.responses import JSONResponse

from app.config import (
    MAX_CONCURRENT_BROWSERS,
    MAX_AUDITS_BEFORE_RESTART,
    MAX_UPTIME_SECONDS,
)

from app.models import AuditRequest, AuditErrorResponse
from app.core.browser_manager import BrowserManager
from app.core.analyzer import run_audit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("audit.main")

browser_manager = BrowserManager(
    max_concurrent_browsers=MAX_CONCURRENT_BROWSERS,
    max_audits_before_restart=MAX_AUDITS_BEFORE_RESTART,
    max_uptime_seconds=MAX_UPTIME_SECONDS,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await browser_manager.start()
    logger.info("Website Audit Analyzer is ready on port 8000")
    yield
    await browser_manager.stop()
    logger.info("Website Audit Analyzer has been shut down")

app = FastAPI(
    title="Website Audit Analyzer",
    description="Production data-acquisition microservice for AI-powered lead generation pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "website-audit-analyzer"}

@app.post("/analyze")
async def analyze_website(request: AuditRequest):
    context = None
    try:
        context = await browser_manager.acquire_context()
        result = await run_audit(context, request.url)
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.exception("Unhandled error during audit for %s: %s", request.url, e)
        error_response = AuditErrorResponse(
            status="navigation_error",
            resolved_url=request.url,
            error_reason=f"Internal service error: {str(e)}",
        )
        return JSONResponse(content=error_response.model_dump())
    
    finally:
        if context:
            try:
                await context.close()
            except Exception as e:
                logger.warning("Error closing browser context: %s", e)
            browser_manager.release_context()