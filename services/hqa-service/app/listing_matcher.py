import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
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
# 1b. TWO-MODE FILTER (prompt Keyword/Seller Analytics)
# =========================================================
#
# Dashboard chi co dung 2 mode loai tru nhau:
#
#   FILTER_MODE_BRAND_MODEL : Brand + Model (boundary phrase tren title)
#   FILTER_MODE_KEYWORD     : Keyword STRICT (title == keyword, + plural)
#
# Hai mode KHONG duoc fallback cho nhau.

FILTER_MODE_BRAND_MODEL = "brand_model"
FILTER_MODE_KEYWORD = "keyword"

FILTER_MODES = (
    FILTER_MODE_BRAND_MODEL,
    FILTER_MODE_KEYWORD,
)

# Chi duoc phep plural hoa final noun nam trong danh sach nay.
# KHONG stemming generic, KHONG alias (amp != amplifier, loudspeaker != speaker).
PLURALIZABLE_PRODUCT_TERMS = {
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

# Mot "run" la mot cum toan chu HOAC toan so.
# "gx4000d" -> ["gx", "4000", "d"]   |   "4311b" -> ["4311", "b"]
_ALNUM_RUN_RE = re.compile(r"[a-z]+|[0-9]+")

# Giua hai run, dau ngan cach la TUY CHON.
# Nho vay "GX-4000D" / "GX 4000D" / "GX4000D" duoc coi la MOT model,
# nhung KHONG lam mat bien token o hai dau cum.
_OPTIONAL_SEPARATOR = r"[^a-z0-9]*"


def alnum_runs(value: Optional[str]) -> list[str]:
    """Tach text thanh cac cum toan chu / toan so, bo qua moi dau ngan cach.

        "gx4000d"   -> ["gx", "4000", "d"]
        "gx 4000d"  -> ["gx", "4000", "d"]
        "GX-4000D"  -> ["gx", "4000", "d"]

    Dung chung cho matcher VA cho SQL prefilter, de hai tang khong bao gio
    bat dong quan diem ve mot listing.
    """
    return _ALNUM_RUN_RE.findall(normalize_text(value))


@lru_cache(maxsize=4096)
def _boundary_pattern(normalized_phrase: str):
    runs = _ALNUM_RUN_RE.findall(normalized_phrase)

    if not runs:
        return None

    body = _OPTIONAL_SEPARATOR.join(re.escape(run) for run in runs)

    return re.compile(
        rf"(?<![a-z0-9]){body}(?![a-z0-9])"
    )


def exact_boundary_phrase(
    title: Optional[str],
    phrase: Optional[str],
) -> bool:
    """``phrase`` xuat hien trong ``title`` voi bien token ro rang.

    Khac ``contains_exact_phrase``: phrase rong => False (khong coi la "bo qua").

    Dau ngan cach GIUA cac cum chu/so la tuy chon, nen cac cach viet khac nhau
    cua CUNG mot model duoc gom lam mot:

        GX-4000D  ==  GX 4000D  ==  GX4000D
        AU-777    ==  AU 777    ==  AU777
        SL-1200MK2 == SL 1200 MK2

    Nhung bien o HAI DAU van chat, nen khong he noi long viec phan biet model:

        exact_boundary_phrase("Vintage JBL 4311B speakers", "jbl 4311b") -> True
        exact_boundary_phrase("JBL 4311BA speakers",        "jbl 4311b") -> False
        exact_boundary_phrase("JBL 14311B speakers",        "jbl 4311b") -> False
        exact_boundary_phrase("JBL 4311 speakers",          "jbl 4311b") -> False
        exact_boundary_phrase("JBL model 4311B",            "jbl 4311b") -> False
    """
    normalized_title = normalize_text(title)
    normalized_phrase = normalize_text(phrase)

    if not normalized_title or not normalized_phrase:
        return False

    pattern = _boundary_pattern(normalized_phrase)

    if pattern is None:
        return False

    return bool(pattern.search(normalized_title))


def contains_exact_phrase(
    title: Optional[str],
    phrase: Optional[str],
) -> bool:
    """Ban "lenient": phrase rong nghia la khong rang buoc -> True.

    Giu nguyen semantics cu vi ``match_listing`` dang dua vao no.
    """
    if not phrase:
        return True

    return exact_boundary_phrase(title, phrase)


# =========================================================
# 3b. MODE A — BRAND + MODEL
# =========================================================

def match_brand_model_title(
    title: Optional[str],
    *,
    brand: Optional[str] = None,
    model: Optional[str] = None,
) -> bool:
    """Mode A: validate title theo Brand / Model.

    A1. Brand + Model : title phai chua cum ``brand + " " + model`` LIEN NHAU.
    A2. Brand only    : title phai chua brand voi bien token exact.
    A3. Model only    : title phai chua model voi bien token exact.
    A4. Khong co ca hai -> False (khong duoc fallback ve "match tat ca").
    """
    normalized_brand = normalize_text(brand)
    normalized_model = normalize_text(model)

    if not normalized_brand and not normalized_model:
        return False

    if normalized_brand and normalized_model:
        # Khong cho token nam giua Brand va Model.
        return exact_boundary_phrase(
            title,
            f"{normalized_brand} {normalized_model}",
        )

    if normalized_brand:
        return exact_boundary_phrase(title, normalized_brand)

    return exact_boundary_phrase(title, normalized_model)


# =========================================================
# 3c. MODE B — KEYWORD STRICT
# =========================================================

def keyword_phrase_variants(keyword: Optional[str]) -> list[str]:
    """Cac dang cum tu duoc chap nhan cua keyword.

    Chi bien the DUY NHAT duoc phep: final noun co "s" hoac khong co "s",
    va chi khi final noun nam trong ``PLURALIZABLE_PRODUCT_TERMS``.

        "JBL 4311B speaker"  -> ["jbl 4311b speaker", "jbl 4311b speakers"]
        "JBL 4311B speakers" -> ["jbl 4311b speakers", "jbl 4311b speaker"]
        "JBL 4311B"          -> ["jbl 4311b"]

    KHONG stemming generic. KHONG alias (amp != amplifier,
    loudspeaker != speaker, stereo receiver != receiver).
    """
    normalized = normalize_text(keyword)

    if not normalized:
        return []

    tokens = normalized.split()

    if not tokens:
        return []

    last = tokens[-1]
    head = tokens[:-1]

    singular = last[:-1] if last.endswith("s") else last

    if singular not in PLURALIZABLE_PRODUCT_TERMS:
        return [normalized]

    variants = [
        " ".join(head + [singular]),
        " ".join(head + [singular + "s"]),
    ]

    # Giu dang goc dung dau danh sach de match nhanh truong hop pho bien nhat.
    ordered = [normalized] + [
        variant for variant in variants if variant != normalized
    ]

    return ordered


def match_keyword_strict(
    title: Optional[str],
    keyword: Optional[str],
) -> bool:
    """Mode B: title phai chua NGUYEN CUM keyword, lien mach, dung bien token.

    "Strict" o day nghia la:
    - Cac token cua keyword phai DINH LIEN NHAU, khong duoc chen them token
      nao vao GIUA cum.
    - Final noun duoc phep co "s" hoac khong co "s" (chi voi product term).
    - Khong fuzzy, khong Levenshtein, khong alias, khong semantic.

    Text dung TRUOC hoac SAU cum keyword thi duoc phep.

        match_keyword_strict("JBL 4311B speaker",          "JBL 4311B speaker") -> True
        match_keyword_strict("JBL 4311B speakers",         "JBL 4311B speaker") -> True
        match_keyword_strict("Vintage JBL 4311B speaker",  "JBL 4311B speaker") -> True
        match_keyword_strict("Vintage JBL 4311B speakers", "JBL 4311B speaker") -> True
        match_keyword_strict("JBL 4311B speaker pair",     "JBL 4311B speaker") -> True

        match_keyword_strict("JBL 4311B studio speaker",   "JBL 4311B speaker") -> False
        match_keyword_strict("JBL 4311B loudspeaker",      "JBL 4311B speaker") -> False
        match_keyword_strict("JBL model 4311B speaker",    "JBL 4311B speaker") -> False
        match_keyword_strict("Sansui AU-777 amp",   "Sansui AU-777 amplifier") -> False
    """
    normalized_title = normalize_text(title)

    if not normalized_title:
        return False

    for variant in keyword_phrase_variants(keyword):
        if exact_boundary_phrase(normalized_title, variant):
            return True

    return False


# =========================================================
# 3d. DISPATCH THEO MODE
# =========================================================

def match_listing_by_mode(
    *,
    title: Optional[str],
    filter_mode: Optional[str],
    brand: Optional[str] = None,
    model: Optional[str] = None,
    keyword: Optional[str] = None,
) -> bool:
    """Entry point duy nhat cho matcher 2 mode.

    Khong co fallback giua 2 mode; mode khong hop le -> False.
    """
    mode = (filter_mode or "").strip().lower()

    if mode == FILTER_MODE_BRAND_MODEL:
        return match_brand_model_title(
            title,
            brand=brand,
            model=model,
        )

    if mode == FILTER_MODE_KEYWORD:
        return match_keyword_strict(
            title,
            keyword,
        )

    return False


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