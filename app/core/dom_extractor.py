import re
import logging
from playwright.async_api import Page

logger = logging.getLogger("audit.dom_extractor")

PHONE_REGEX_JS = r"""/(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}/"""
EMAIL_REGEX_JS = r"""/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/"""


async def extract_all_signals(page: Page) -> dict:
# Bundled everything into one JS function to minimize round-trips (Para di masyadong maraming calls that slows down the process :>)
    signals = await page.evaluate("""
    () => {
        // Helper: get all visible text content once
        const bodyText = document.body ? document.body.innerText || '' : '';
        
        // 1. SSL check — based on the actual resolved URL in the browser
        const has_ssl = location.protocol === 'https:';
        
        // 2. Title length
        const title_length = (document.title || '').length;
        
        // 3. Meta description presence
        const metaDesc = document.querySelector('meta[name="description"]');
        const has_meta_description = metaDesc !== null && (metaDesc.getAttribute('content') || '').trim().length > 0;
        
        // 4. Viewport meta
        const has_viewport_meta = document.querySelector('meta[name="viewport"]') !== null;
        
        // 5. CTA count — buttons/links with action keywords
        const ctaKeywords = ['book', 'order', 'contact', 'reserve', 'schedule', 'get started', 'sign up', 'call now'];
        let cta_count = 0;
        const clickables = document.querySelectorAll('button, a[role="button"], input[type="submit"], a.btn, a.button, [class*="btn"], [class*="cta"]');
        clickables.forEach(el => {
            const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase().trim();
            if (ctaKeywords.some(kw => text.includes(kw))) {
                cta_count++;
            }
        });
        
        // 6. Contact form detection — look for <form> elements containing input fields
        let has_contact_form = false;
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], textarea');
            if (inputs.length >= 2) {
                has_contact_form = true;
            }
        });
        
        // 7. Phone number detection via regex on visible text
        const phoneRegex = /(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}/;
        // Also check href="tel:" links
        const hasTelLink = document.querySelector('a[href^="tel:"]') !== null;
        const has_phone_number = phoneRegex.test(bodyText) || hasTelLink;
        
        // 8. Email detection
        const emailRegex = /[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}/;
        const hasMailtoLink = document.querySelector('a[href^="mailto:"]') !== null;
        const has_email = emailRegex.test(bodyText) || hasMailtoLink;
        
        // 9. Navigation item count — links inside <nav> elements
        let nav_item_count = 0;
        const navs = document.querySelectorAll('nav');
        navs.forEach(nav => {
            nav_item_count += nav.querySelectorAll('a').length;
        });
        
        // 10. Structured data (schema.org)
        const schemaScripts = document.querySelectorAll('script[type="application/ld+json"]');
        let has_structured_data = schemaScripts.length > 0;
        // Also check for microdata or RDFa
        if (!has_structured_data) {
            has_structured_data = document.querySelector('[itemscope]') !== null 
                || document.querySelector('[vocab*="schema.org"]') !== null;
        }
        
        // 11. Page load time from Navigation Timing API
        let page_load_time_ms = 0;
        try {
            const perf = performance.timing;
            // loadEventEnd might be 0 if called before load completes.
            // Fall back to domContentLoadedEventEnd which aligns with our wait_until strategy.
            const end = perf.loadEventEnd > 0 ? perf.loadEventEnd : perf.domContentLoadedEventEnd;
            page_load_time_ms = Math.max(0, end - perf.navigationStart);
        } catch(e) {
            page_load_time_ms = 0;
        }
        
        return {
            has_ssl,
            title_length,
            has_meta_description,
            has_viewport_meta,
            cta_count,
            has_contact_form,
            has_phone_number,
            has_email,
            nav_item_count,
            has_structured_data,
            page_load_time_ms
        };
    }
    """)

    logger.debug("DOM signals extracted: %s", signals)
    return signals