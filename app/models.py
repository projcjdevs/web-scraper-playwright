from pydantic import BaseModel, field_validator
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

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
        TRACKING_PARAMS = {
            "gclid", "gbraid", "wbraid", "gad_source", "gad_campaignid",
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "msclkid", "mc_eid", "ref", "_ga",
        }

        existing_params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned_params = {
            k: v for k, v in existing_params.items()
            if k not in TRACKING_PARAMS
        }

        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(cleaned_params, doseq=True),
            "",
        ))

        return clean_url
    
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