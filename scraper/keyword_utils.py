"""Shared keyword matching and search slug helpers."""
import re

STRONG_TERMS = {
    "qa", "sdet", "test", "testing", "automation", "selenium",
    "quality", "manual",
}

INSTAHYRE_SLUGS = {
    "qa automation engineer": ["sdet", "quality-assurance"],
    "sdet": ["sdet"],
    "senior test engineer": ["sdet", "quality-assurance"],
    "manual testing engineer": ["quality-assurance", "sdet"],
    "manual qa engineer": ["quality-assurance", "sdet"],
    "manual test engineer": ["quality-assurance", "sdet"],
    "software test engineer": ["sdet", "quality-assurance"],
    "qa engineer": ["sdet", "quality-assurance"],
    "selenium java test engineer": ["sdet", "quality-assurance"],
    "qa engineer selenium": ["sdet", "quality-assurance"],
}


def keyword_tokens(keywords: list) -> set:
    tokens = set()
    for kw in keywords:
        tokens.update(re.findall(r"[a-z]{2,}", kw.lower()))
    return tokens


def matches_job_text(text: str, keywords: list) -> bool:
    """Return True if job text matches any configured keyword."""
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    tokens = keyword_tokens(keywords)
    strong = tokens & STRONG_TERMS
    return any(term in text_lower for term in strong)


def search_terms(keywords: list) -> list:
    """Short search terms for sites that fail on long phrases (e.g. WWR)."""
    terms = set()
    for kw in keywords:
        kw_lower = kw.lower()
        if len(kw_lower) <= 20:
            terms.add(kw_lower)
        for token in keyword_tokens([kw]):
            if token in STRONG_TERMS:
                terms.add(token)
    return list(terms) or [keywords[0].lower()] if keywords else ["qa"]


def instahyre_slug_variants(keyword: str) -> list:
    key = keyword.lower().strip()
    if key in INSTAHYRE_SLUGS:
        return INSTAHYRE_SLUGS[key]
    slug = re.sub(r"[^a-z0-9\s-]", "", key)
    slug = re.sub(r"\s+", "-", slug)
    variants = [slug]
    if "sdet" not in variants:
        variants.append("sdet")
    if "quality-assurance" not in variants:
        variants.append("quality-assurance")
    return variants
