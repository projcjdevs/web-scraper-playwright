from pydantic import BaseModel, field_validator
from typing import Optional
from urllib.parse import urlparse

class AuditRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod

    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            v = "http://" + v
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"invalid URL scheme: {parsed.scheme}")
        if not parsed.netloc:
            raise ValueError("URL must have a valid domain")
        return v
    
class TechnicalSignals(BaseModel):
    has_ssl: bool = False
    title_length: int = 0
    has_meta_description: bool = False
    has_viewport_meta: bool = False
    cta_count: int = 0
    has_contact_form: bool = False
    has_phone_number: bool = False
    has_email: bool = False
    nav_item_count: int = 0
    has_structured_data: bool = False


class PerformanceData(BaseModel):
    page_load_time_ms: int = 0


class Screenshots(BaseModel):
    hero: str = ""
    mid: str = ""
    footer: str = ""


class AuditSuccessResponse(BaseModel):
    status: str = "success"
    resolved_url: str
    technical: TechnicalSignals
    performance: PerformanceData
    screenshots: Screenshots


class AuditErrorResponse(BaseModel):
    status: str
    resolved_url: str = ""
    error_reason: str