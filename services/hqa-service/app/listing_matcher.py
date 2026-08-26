import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


# =========================================================
# 1. ALIAS / CANONICAL WORDS
# =========================================================

TOKEN_ALIASES = {
    # Speaker
    "speaker": "speaker",
    "speakers": "speaker",

    # Receiver
    "receiver": "receiver",
    "receivers": "receiver",

    # Amplifier
    "amplifier": "amplifier",
    "amplifiers": "amplifier",
    "amp": "amplifier",
    "amps": "amplifier",

    # Turntable
    "turntable": "turntable",
    "turntables": "turntable",

    # Tuner
    "tuner": "tuner",
    "tuners": "tuner",

    # Equalizer
    "equalizer": "equalizer",
    "equalizers": "equalizer",
    "equaliser": "equalizer",
    "equalisers": "equalizer",
}


PRODUCT_TERMS = {
    "speaker",
    "receiver",
    "amplifier",
    "turntable",
    "tuner",
    "equalizer",
}


# =========================================================
# 2. NORMALIZE
# =========================================================

def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""

    text = str(value)

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        ch for ch in text
        if not unicodedata.combining(ch)
    )

    text = text.lower()

    text = text.replace("&", " and ")

    # Giữ lại chữ + số
    text = re.sub(r"[^a-z0-9]+", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def canonical_tokens(value: Optional[str]) -> list[str]:
    normalized = normalize_text(value)

    if not normalized:
        return []

    tokens = normalized.split()

    return [
        TOKEN_ALIASES.get(token, token)
        for token in tokens
    ]


# =========================================================
# 3. EXACT BRAND / MODEL MATCH
# =========================================================

def contains_exact_phrase(
    title: Optional[str],
    phrase: Optional[str],
) -> bool:
    if not phrase:
        return True

    normalized_title = normalize_text(title)
    normalized_phrase = normalize_text(phrase)

    if not normalized_title or not normalized_phrase:
        return False

    pattern = (
        rf"(?<![a-z0-9])"
        rf"{re.escape(normalized_phrase)}"
        rf"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            normalized_title,
            flags=re.IGNORECASE,
        )
    )


# =========================================================
# 4. PRODUCT TERM
# =========================================================

def extract_product_terms(keyword: Optional[str]) -> list[str]:
    tokens = canonical_tokens(keyword)

    result = []

    for token in tokens:
        if token in PRODUCT_TERMS and token not in result:
            result.append(token)

    return result


def product_type_matches(
    title: Optional[str],
    keyword: Optional[str],
) -> bool:

    expected_terms = extract_product_terms(keyword)

    # Keyword không có product noun
    # thì không ép check ở đây.
    if not expected_terms:
        return True

    title_tokens = set(canonical_tokens(title))

    return all(
        expected in title_tokens
        for expected in expected_terms
    )


# =========================================================
# 5. PART / ACCESSORY / MANUAL DETECTION
# =========================================================

WHOLE_PRODUCT_REJECT_PATTERNS = [

    # Replacement part
    r"\breplacement\s+(woofer|tweeter|driver|cone|crossover|diaphragm)\b",

    # Part for product
    r"\b(woofer|tweeter|driver|cone|crossover|diaphragm|grille|grill)\s+for\b",

    # Compatible part
    r"\b(woofer|tweeter|driver|cone|crossover|stand|grille|grill)\s+compatible\b",

    r"\bcompatible\s+(woofer|tweeter|driver|stand|grille|grill)\b",

    # Speaker stand
    r"\bspeaker\s+stand\b",

    r"\bstands?\s+for\s+.*speaker\b",

    # Documentation
    r"\bservice\s+manual\b",
    r"\bowner'?s?\s+manual\b",
    r"\buser\s+manual\b",
    r"\brepair\s+manual\b",
    r"\bschematic\b",
    r"\bbrochure\b",

    # Parts only
    r"\bwoofer\s+only\b",
    r"\btweeter\s+only\b",
    r"\bcrossover\s+only\b",
    r"\bdriver\s+only\b",
]


def is_non_whole_product(title: Optional[str]) -> bool:
    normalized = normalize_text(title)

    if not normalized:
        return False

    for pattern in WHOLE_PRODUCT_REJECT_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


# =========================================================
# 6. EXCLUDE KEYWORDS
# =========================================================

def has_excluded_term(
    title: Optional[str],
    exclude_keywords: Optional[str],
) -> bool:

    if not exclude_keywords:
        return False

    normalized_title = normalize_text(title)

    # Có thể đang lưu:
    # manual, woofer, replacement
    # hoặc manual|woofer|replacement

    terms = re.split(
        r"[,|;\n]+",
        str(exclude_keywords),
    )

    for raw_term in terms:
        term = normalize_text(raw_term)

        if not term:
            continue

        pattern = (
            rf"(?<![a-z0-9])"
            rf"{re.escape(term)}"
            rf"(?![a-z0-9])"
        )

        if re.search(pattern, normalized_title):
            return True

    return False


# =========================================================
# 7. RESULT
# =========================================================

@dataclass
class ListingMatchResult:
    matched: bool

    brand_match: bool
    model_match: bool
    product_match: bool

    exclude_match: bool
    whole_product_match: bool

    reason: str


def match_listing(
    *,
    title: str,
    keyword: str,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    role: str = "whole_product",
    exclude_keywords: Optional[str] = None,
) -> ListingMatchResult:

    brand_match = contains_exact_phrase(
        title,
        brand,
    )

    model_match = contains_exact_phrase(
        title,
        model,
    )

    product_match = product_type_matches(
        title,
        keyword,
    )

    exclude_match = has_excluded_term(
        title,
        exclude_keywords,
    )

    if role == "whole_product":
        whole_product_match = not is_non_whole_product(
            title
        )
    else:
        whole_product_match = True

    matched = (
        brand_match
        and model_match
        and product_match
        and not exclude_match
        and whole_product_match
    )

    reasons = []

    if not brand_match:
        reasons.append("brand_mismatch")

    if not model_match:
        reasons.append("model_mismatch")

    if not product_match:
        reasons.append("product_type_mismatch")

    if exclude_match:
        reasons.append("exclude_keyword")

    if not whole_product_match:
        reasons.append("not_whole_product")

    if matched:
        reasons.append("matched")

    return ListingMatchResult(
        matched=matched,
        brand_match=brand_match,
        model_match=model_match,
        product_match=product_match,
        exclude_match=exclude_match,
        whole_product_match=whole_product_match,
        reason=",".join(reasons),
    )