"""Deterministic, auditable listing-role + product-identity classifier.

Why this module exists
----------------------
The HQA marketplace dashboard must talk in the language of *products* (something a
Marketing person recognises) while the underlying data is a stream of raw
marketplace *listings*. A single product (e.g. "JBL L26 Speaker") shows up as many
listings: the whole product, replacement woofers, foam surrounds, grilles, dealer
brochures, and the occasional mis-matched listing. If we aggregate price/seller
trends over *all* of those listings, a $19 foam-repair kit silently drags the market
price down and produces a fake "price crash" alert.

So every listing is tagged with:
  * a product identity  (product_key / product_label)  -> which product it belongs to
  * a listing role       (whole_product / component_part / accessory / ...) -> what it is
  * eligibility          (only whole_product feeds the main price & seller analytics)

The classifier is intentionally NOT a black box: it is a deterministic multi-signal
scorer that returns the reasons behind every decision, so the result can be audited
in the dashboard's "classification audit" table.

Schema note / deviation from the original spec
-----------------------------------------------
The prompt assumed the source table exposes ``product_id`` and ``keyword`` columns.
The real ``public.marketplace_research_results`` schema has NEITHER. Product identity
therefore falls back to normalized ``brand`` + ``model`` (and, when those are missing,
to a short signature taken from the listing title). All field access goes through
``FIELD_MAP`` so a future schema that *does* carry ``product_id`` needs only a one-line
change here.
"""

from __future__ import annotations

import re
from statistics import median as _median
from typing import Any, Iterable

CLASSIFIER_VERSION = "hqa-role-v2"

# Central field map. Only place that knows the real column names of a listing row.
FIELD_MAP = {
    "listing_id": "listing_id",
    "title": "listing_title",
    "brand": "brand",
    "model": "model",
    "category": "category",
    "category_name": "category_name",
    "condition": "condition",
    "price": "price",
    "seller": "seller_or_shop",
    "status": "listing_status",
    "currency": "currency",
    "url": "listing_url",
    "exclude_flag": "exclude_flag",
    "research_date": "research_date",
    # product_id / keyword deliberately absent -- not in the real schema.
}

# Listing roles ---------------------------------------------------------------
ROLE_WHOLE = "whole_product"
ROLE_COMPONENT = "component_part"
ROLE_ACCESSORY = "accessory"
ROLE_DOC = "documentation_media"
ROLE_IRRELEVANT = "irrelevant"
ROLE_UNCERTAIN = "uncertain"

# --- Signal vocabularies (all matched on the normalized, lower-cased title) ---
# Kept as tuples of *phrases*; multi-word phrases are matched as substrings on the
# normalized title, single words as whole-word tokens.
COMPONENT_TOKENS = (
    "woofer", "tweeter", "midrange", "driver", "drivers", "crossover", "crossovers",
    "terminal", "binding post", "foam", "refoam", "surround", "cone", "diaphragm",
    "voice coil", "recone", "recone kit", "board", "pcb", "module", "amp module",
    "transformer", "knob", "knobs", "switch", "jack", "chassis", "faceplate",
    "capacitor", "cap kit", "rebuild kit", "repair kit", "restoration kit",
    "dust cap", "spider", "gasket", "potentiometer", "cabinet only", "enclosure only",
    "frame only", "parts only", "for parts repair", "fuse", "lamp", "meter",
)
ACCESSORY_TOKENS = (
    "grill", "grille", "grills", "grilles", "cover", "dust cover", "stand", "stands",
    "mount", "wall mount", "case", "carrying case", "bag", "skin", "badge", "logo",
    "emblem", "feet", "remote", "cable", "cord", "adapter", "bracket", "spikes",
)
DOC_TOKENS = (
    "manual", "owners manual", "owner's manual", "service manual", "brochure",
    "catalog", "catalogue", "book", "schematic", "datasheet", "advertisement",
    "flyer", "leaflet", "literature", "magazine", "poster", "print ad",
)
# Whole-product positives are supporting signals only -- never decisive on their own.
WHOLE_POSITIVE_TOKENS = (
    "pair", "speakers pair", "pair speakers", "stereo receiver", "receiver",
    "amplifier", "integrated amplifier", "power amplifier", "preamplifier", "preamp",
    "turntable", "record player", "tape deck", "cassette deck", "cd player",
    "tuner", "guitar", "complete", "restored", "serviced", "refurbished",
    "tested", "tested working", "working", "fully working", "excellent condition",
)

# Category hints. Weaker than title tokens; a "Vintage Speakers" category is a
# whole-product *hint* but must NOT overrule a woofer/grille token in the title.
COMPONENT_CATEGORY_HINTS = ("part", "component", "driver", "woofer", "crossover", "replacement", "repair")
ACCESSORY_CATEGORY_HINTS = ("accessory", "accessories", "grille", "grill", "cover", "stand", "mount", "bag")
DOC_CATEGORY_HINTS = ("manual", "literature", "book", "magazine", "brochure", "catalog", "media")
WHOLE_CATEGORY_HINTS = ("speaker", "receiver", "amplifier", "turntable", "guitar", "home audio", "stereo", "monitor")

# Product-type inference for a human-readable label.
PRODUCT_TYPE_RULES = (
    ("Acoustic Guitar", ("acoustic guitar", "dreadnought")),
    ("Electric Guitar", ("electric guitar", "stratocaster", "telecaster", "les paul")),
    ("Guitar", ("guitar",)),
    ("Stereo Receiver", ("stereo receiver", "receiver")),
    ("Integrated Amplifier", ("integrated amplifier",)),
    ("Amplifier", ("amplifier", "amp")),
    ("Preamplifier", ("preamplifier", "preamp")),
    ("Turntable", ("turntable", "record player")),
    ("Cassette Deck", ("cassette deck", "tape deck")),
    ("CD Player", ("cd player",)),
    ("Tuner", ("tuner",)),
    ("Studio Monitor", ("studio monitor", "monitor")),
    ("Speaker", ("speaker", "loudspeaker")),
)

# --- Scoring weights ---------------------------------------------------------
# A title token is the strongest signal; category hints and relative price are
# supporting evidence. These weights make a component TOKEN (3.0) outweigh a
# whole-product CATEGORY hint (1.4) -- exactly the JBL "woofer in Vintage Speakers"
# case the spec calls out.
W_TOKEN_STRONG = 3.0
W_CATEGORY_HINT = 1.4
W_PRICE_SIGNAL = 1.0
W_WHOLE_POSITIVE_TOKEN = 1.2
W_WHOLE_CATEGORY = 1.4
W_EXCLUDE_FLAG = 2.2

MIN_EVIDENCE = 1.0          # below this, and with no whole signal -> uncertain
CONFLICT_MARGIN = 0.9       # top two role scores this close -> uncertain (conflict)

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({"the", "and", "for", "with", "vintage", "original", "genuine", "oem", "new", "used", "lot", "of", "a", "an", "pair", "set"})


def _get(row: Any, key: str, default=None):
    """Read a logical field from a dict-like or attribute-like row via FIELD_MAP."""
    column = FIELD_MAP.get(key, key)
    if isinstance(row, dict):
        return row.get(column, default)
    if hasattr(row, "get"):
        try:
            return row.get(column, default)
        except TypeError:
            pass
    return getattr(row, column, default)


def normalize_text(value: Any) -> str:
    """Lower-case, collapse whitespace, pad with spaces so ' ad ' style phrases match."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} " if text else ""


def _phrase_hit(norm_title: str, phrase: str) -> bool:
    phrase = phrase.strip().lower()
    if not phrase:
        return False
    if " " in phrase:
        return f" {phrase} " in norm_title
    # single word -> whole-word match with an optional trailing plural 's'
    # (so "woofer" also matches "woofers", "grille" matches "grilles", etc.)
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}s?(?![a-z0-9])", norm_title) is not None


def _any_hit(norm_title: str, phrases: Iterable[str]) -> list[str]:
    return [p.strip() for p in phrases if _phrase_hit(norm_title, p)]


def _to_float(value: Any):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


# ---------------------------------------------------------------------------
# Product identity
# ---------------------------------------------------------------------------
def _clean_display(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _type_hit(haystack: str, phrase: str) -> bool:
    """Type-label matcher -- looser than role matching, allows a trailing plural 's'."""
    phrase = phrase.strip().lower()
    if not phrase:
        return False
    if " " in phrase:
        return phrase in haystack
    return re.search(rf"\b{re.escape(phrase)}s?\b", haystack) is not None


def infer_product_type(norm_title: str, norm_category: str) -> str:
    haystack = f"{norm_title} {norm_category}"
    for type_label, phrases in PRODUCT_TYPE_RULES:
        if any(_type_hit(haystack, p) for p in phrases):
            return type_label
    return ""


def derive_product_identity(row: Any) -> dict:
    """Return product identity for a listing row.

    product_key rules (adapted to the real schema which lacks product_id/keyword):
      1. product_id  -> not available in this schema.
      2. brand + model (normalized)      -> "brand::<brand>|model::<model>"
      3. model only                      -> "model::<model>"
      4. brand only                      -> "brand::<brand>"
      5. neither                         -> short signature from the title tokens.
    """
    brand_raw = _clean_display(_get(row, "brand"))
    model_raw = _clean_display(_get(row, "model"))
    title_raw = _clean_display(_get(row, "title"))
    norm_title = normalize_text(title_raw)
    norm_category = normalize_text(_get(row, "category_name") or _get(row, "category"))
    product_type = infer_product_type(norm_title, norm_category)

    nb = normalize_text(brand_raw).strip()
    nm = normalize_text(model_raw).strip()

    if nb and nm:
        product_key = f"brand::{nb}|model::{nm}"
    elif nm:
        product_key = f"model::{nm}"
    elif nb:
        product_key = f"brand::{nb}"
    else:
        tokens = [t for t in _WORD_RE.findall(norm_title) if t not in _STOPWORDS]
        signature = " ".join(tokens[:4]) or "unknown"
        product_key = f"title::{signature}"

    # Human-readable label for Marketing.
    if brand_raw and model_raw:
        label = f"{brand_raw} {model_raw}"
    elif model_raw:
        label = model_raw
    elif brand_raw:
        label = brand_raw
    else:
        label = title_raw[:48] or "Unknown product"
    if product_type and product_type.lower() not in label.lower():
        label = f"{label} {product_type}".strip()

    return {
        "product_key": product_key,
        "product_label": _clean_display(label),
        "brand": brand_raw,
        "model": model_raw,
        "product_type": product_type,
    }


# ---------------------------------------------------------------------------
# Product reference band (built once per product, used for the relative-price signal)
# ---------------------------------------------------------------------------
def _token_only_role(norm_title: str, norm_category: str, exclude_flag: bool) -> str:
    """Cheap first-pass role using tokens/category only (no price).

    Used to pick the *candidate* whole-product listings whose prices define the
    product's reference band. Never surfaced to the user.
    """
    if exclude_flag:
        return ROLE_IRRELEVANT
    if _any_hit(norm_title, DOC_TOKENS) or _any_hit(norm_category, DOC_CATEGORY_HINTS):
        return ROLE_DOC
    if _any_hit(norm_title, COMPONENT_TOKENS):
        return ROLE_COMPONENT
    if _any_hit(norm_title, ACCESSORY_TOKENS):
        return ROLE_ACCESSORY
    return ROLE_WHOLE


def build_product_context(product_rows: list[Any]) -> dict:
    """Compute a robust reference price band from likely whole-product listings.

    reference_median = median of prices of first-pass whole-product candidates.
    Falls back to all priced listings if there are too few candidates.
    """
    candidate_prices: list[float] = []
    all_prices: list[float] = []
    for row in product_rows:
        price = _to_float(_get(row, "price"))
        if price is None or price <= 0:
            continue
        all_prices.append(price)
        norm_title = normalize_text(_get(row, "title"))
        norm_category = normalize_text(_get(row, "category_name") or _get(row, "category"))
        role = _token_only_role(norm_title, norm_category, _is_truthy_flag(_get(row, "exclude_flag")))
        if role == ROLE_WHOLE:
            candidate_prices.append(price)

    band_source = candidate_prices if len(candidate_prices) >= 3 else all_prices
    if not band_source:
        return {"reference_median": None, "reference_p25": None, "reference_p75": None, "sample": 0}
    band_source = sorted(band_source)
    return {
        "reference_median": float(_median(band_source)),
        "reference_p25": _percentile(band_source, 0.25),
        "reference_p75": _percentile(band_source, 0.75),
        "sample": len(band_source),
    }


def _percentile(sorted_values: list[float], q: float):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * frac


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------
def _confidence_from(top: float, second: float) -> int:
    """Map (winning score, runner-up score) to a 0-100 confidence."""
    if top <= 0:
        return 0
    margin = top - second
    raw = 55 + top * 9 + margin * 12
    return int(max(30, min(99, round(raw))))


def classify_listing_role(row: Any, product_context: dict | None = None) -> dict:
    """Classify one listing into a role with confidence + reasons + eligibility.

    Multi-signal, deterministic. No single field decides the outcome:
      * title tokens          (strongest)
      * category hints        (supporting)
      * relative price        (supporting; only vs the product's own band)
      * exclude_flag          (supporting; irrelevant-leaning)
    condition ("For parts or not working") and listing_status are recorded but do
    NOT change the role -- a broken whole unit is still a whole product.
    Strong conflicting evidence -> uncertain (we never guess to inflate coverage).
    """
    product_context = product_context or {}
    norm_title = normalize_text(_get(row, "title"))
    norm_category = normalize_text(_get(row, "category_name") or _get(row, "category"))
    exclude_flag = _is_truthy_flag(_get(row, "exclude_flag"))
    price = _to_float(_get(row, "price"))

    scores = {ROLE_WHOLE: 0.0, ROLE_COMPONENT: 0.0, ROLE_ACCESSORY: 0.0, ROLE_DOC: 0.0, ROLE_IRRELEVANT: 0.0}
    reasons: list[str] = []

    # --- documentation ---
    doc_hits = _any_hit(norm_title, DOC_TOKENS)
    if doc_hits:
        scores[ROLE_DOC] += W_TOKEN_STRONG
        reasons.append(f"title mentions {doc_hits[0].strip()}")
    if _any_hit(norm_category, DOC_CATEGORY_HINTS):
        scores[ROLE_DOC] += W_CATEGORY_HINT
        reasons.append("category suggests documentation/media")

    # --- component ---
    comp_hits = _any_hit(norm_title, COMPONENT_TOKENS)
    if comp_hits:
        scores[ROLE_COMPONENT] += W_TOKEN_STRONG
        reasons.append(f"title token '{comp_hits[0].strip()}' indicates a part")
    if _any_hit(norm_category, COMPONENT_CATEGORY_HINTS):
        scores[ROLE_COMPONENT] += W_CATEGORY_HINT
        reasons.append("category suggests a speaker/electronic component")

    # --- accessory ---
    acc_hits = _any_hit(norm_title, ACCESSORY_TOKENS)
    if acc_hits:
        scores[ROLE_ACCESSORY] += W_TOKEN_STRONG
        reasons.append(f"title token '{acc_hits[0].strip()}' indicates an accessory")
    if _any_hit(norm_category, ACCESSORY_CATEGORY_HINTS):
        scores[ROLE_ACCESSORY] += W_CATEGORY_HINT
        reasons.append("category suggests an accessory")

    # A strong part/accessory/doc *title token* is a hard negative for whole_product:
    # "pair of woofers" and "grille pair" contain whole-ish words but are clearly not
    # the whole product, so whole-product supporting cues (positive tokens, category,
    # in-band price) are suppressed when such a token is present. This is what makes a
    # woofer stay a component even when its category is "Vintage Speakers".
    has_hard_part_token = bool(comp_hits or acc_hits or doc_hits)

    # --- whole-product supporting signals (suppressed by a hard part token) ---
    if not has_hard_part_token:
        whole_hits = _any_hit(norm_title, WHOLE_POSITIVE_TOKENS)
        if whole_hits:
            scores[ROLE_WHOLE] += W_WHOLE_POSITIVE_TOKEN
            reasons.append(f"whole-item cue '{whole_hits[0].strip()}'")
        if _any_hit(norm_category, WHOLE_CATEGORY_HINTS):
            scores[ROLE_WHOLE] += W_WHOLE_CATEGORY
            reasons.append("category is a whole-product category")

    # --- exclude flag (irrelevant-leaning, supporting only) ---
    if exclude_flag:
        scores[ROLE_IRRELEVANT] += W_EXCLUDE_FLAG
        reasons.append("exclude_flag is set")

    # --- relative price signal (only vs this product's own band) ---
    ref_median = product_context.get("reference_median")
    if price is not None and price > 0 and ref_median:
        ratio = price / ref_median
        if ratio < 0.35:
            scores[ROLE_COMPONENT] += W_PRICE_SIGNAL
            reasons.append("price far below the product's whole-item band")
        elif 0.6 <= ratio <= 2.5 and not has_hard_part_token:
            scores[ROLE_WHOLE] += W_PRICE_SIGNAL * 0.6
            reasons.append("price sits within the product's whole-item band")

    # --- decision ---
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (top_role, top_score), (second_role, second_score) = ranked[0], ranked[1]

    role: str
    if top_score < MIN_EVIDENCE:
        # No decisive negative signal. Treat as whole product only if it has a real
        # positive cue; otherwise we genuinely don't know.
        if scores[ROLE_WHOLE] > 0:
            role = ROLE_WHOLE
        else:
            role = ROLE_UNCERTAIN
            reasons.append("insufficient signal to classify")
    elif (top_score - second_score) < CONFLICT_MARGIN and second_score >= MIN_EVIDENCE and top_role != second_role:
        role = ROLE_UNCERTAIN
        reasons.append(f"conflicting signals ({top_role} vs {second_role})")
    else:
        role = top_role

    confidence = _confidence_from(top_score, second_score) if role != ROLE_UNCERTAIN else min(
        60, _confidence_from(top_score, second_score)
    )
    if role == ROLE_UNCERTAIN and top_score < MIN_EVIDENCE:
        confidence = 40

    # De-duplicate reasons, keep order, cap length.
    seen: set[str] = set()
    deduped = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            deduped.append(reason)

    return {
        "listing_role": role,
        "role_confidence": confidence,
        "role_reasons": deduped[:4],
        "eligible_for_market_analytics": role == ROLE_WHOLE,
        "classifier_version": CLASSIFIER_VERSION,
    }


def classify_product_rows(product_rows: list[Any]) -> list[dict]:
    """Classify every listing of a single product using a shared reference band.

    Returns a list of dicts: {row, identity, classification} in the input order.
    """
    context = build_product_context(product_rows)
    identity = derive_product_identity(product_rows[0]) if product_rows else {}
    results = []
    for row in product_rows:
        results.append(
            {
                "row": row,
                "identity": identity,
                "context": context,
                "classification": classify_listing_role(row, context),
            }
        )
    return results
