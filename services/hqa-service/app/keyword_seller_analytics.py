"""Business logic: Keyword -> Seller -> Latest listing -> Price/Status history.

Toan bo ham trong module nay la PURE (khong cham DB, khong cham HTTP) de co the
tai su dung va kiem chung doc lap. Tang I/O nam o ``keyword_seller_source.py``.

Nguyen tac cot loi (prompt muc 3):

    representative_listing(T)
        = listing DU DIEU KIEN co thoi diem xuat hien MOI NHAT <= T
    seller_keyword_price(T)
        = snapshot gia gan nhat cua representative_listing(T)

Dieu kien "du dieu kien" (prompt muc 2):
    - role = whole_product (tu ``listing_classifier``)
    - price > nguong (mac dinh 500 USD)
    - thuoc dung keyword dang chon
    - khong bi exclude_flag

Hai loai bien dong KHONG duoc gop chung thanh "gia tang/giam" (prompt muc 10):
    - PRICE_CHANGED           : cung listing doi gia
    - NEW_LISTING_PRICE_SHIFT : seller doi listing dai dien
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median as _median

from app.listing_classifier import (
    ROLE_WHOLE,
    build_product_context,
    classify_listing_role,
)

EVENT_TRACKING_STARTED = "TRACKING_STARTED"
EVENT_PRICE_CHANGED = "PRICE_CHANGED"
EVENT_NEW_LISTING_PRICE_SHIFT = "NEW_LISTING_PRICE_SHIFT"
EVENT_STATUS_CHANGED = "STATUS_CHANGED"

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

ACTIVE_STATUSES = {"ACTIVE", "NEW_LISTING"}


# ---------------------------------------------------------------------------
# 1. Helper so hoc
# ---------------------------------------------------------------------------


def percent_change(previous, current):
    if previous in (None, 0) or current is None:
        return None
    return (current - previous) / previous * 100.0


def median(values):
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return float(_median(cleaned))


def _round(value, digits: int = 2):
    if value is None:
        return None
    return round(float(value), digits)


# ---------------------------------------------------------------------------
# 2. Gom observation -> listing timeline
# ---------------------------------------------------------------------------


def build_listing_timelines(observations: list[dict]) -> list[dict]:
    """Gom cac dong quan sat thanh timeline theo tung listing.

    Moi listing: ``snapshots`` la dict {date -> {price, status, ...}} da sap xep.
    """
    grouped: dict[tuple[str, str], dict] = {}

    for row in observations:
        listing_id = row.get("listing_id")
        marketplace = row.get("marketplace") or ""
        if not listing_id:
            continue
        key = (marketplace, listing_id)
        observed = row.get("observed_date")
        if observed is None:
            continue

        listing = grouped.get(key)
        if listing is None:
            listing = {
                "key": f"{marketplace}:{listing_id}",
                "marketplace": marketplace,
                "listing_id": listing_id,
                "seller": row.get("seller") or "",
                "title": row.get("listing_title") or "",
                "url": row.get("listing_url") or "",
                "image_url": row.get("image_url") or "",
                "condition": row.get("condition") or "",
                "category_name": row.get("category_name") or "",
                "brand": row.get("brand") or "",
                "model": row.get("model") or "",
                "currency": row.get("currency") or "USD",
                "keyword": row.get("keyword") or "",
                "exclude_flag": bool(row.get("exclude_flag")),
                "published_at": row.get("published_at"),
                "first_seen": row.get("first_seen") or observed,
                "snapshots": {},
            }
            grouped[key] = listing

        # Snapshot moi hon trong cung ngay se ghi de -> giu gia tri cuoi ngay.
        listing["snapshots"][observed] = {
            "date": observed,
            "price": row.get("price"),
            "status": row.get("listing_status") or "UNKNOWN",
            "quantity": row.get("quantity"),
            "listing_views": row.get("listing_views"),
        }

        if row.get("published_at") and not listing.get("published_at"):
            listing["published_at"] = row.get("published_at")
        first_seen = listing.get("first_seen")
        if first_seen is None or observed < first_seen:
            listing["first_seen"] = observed
        if row.get("exclude_flag"):
            listing["exclude_flag"] = True

    listings = []
    for listing in grouped.values():
        ordered_dates = sorted(listing["snapshots"].keys())
        listing["snapshot_dates"] = ordered_dates
        listing["appeared_at"] = listing.get("published_at") or listing.get("first_seen")
        listings.append(listing)

    listings.sort(key=lambda item: (item["seller"].lower(), str(item["appeared_at"]), item["listing_id"]))
    return listings


# ---------------------------------------------------------------------------
# 3. Phan loai role qua listing_classifier
# ---------------------------------------------------------------------------


def classify_listings(listings: list[dict]) -> None:
    """Gan ``role`` / ``role_reasons`` cho tung listing (in-place).

    Dung chung ``build_product_context`` de ca keyword co CUNG mot price band,
    dung nhu cach ``fetch_hqa_dashboard_analysis`` dang lam.
    """
    if not listings:
        return

    classifier_rows = []
    for listing in listings:
        latest_price = None
        for snapshot_date in reversed(listing["snapshot_dates"]):
            price = listing["snapshots"][snapshot_date].get("price")
            if price is not None:
                latest_price = price
                break
        classifier_rows.append(
            {
                "listing_title": listing.get("title"),
                "category_name": listing.get("category_name"),
                "category": listing.get("category_name"),
                "condition": listing.get("condition"),
                "brand": listing.get("brand"),
                "model": listing.get("model"),
                "price": latest_price,
                "exclude_flag": listing.get("exclude_flag"),
            }
        )

    context = build_product_context(classifier_rows)
    for listing, row in zip(listings, classifier_rows):
        classification = classify_listing_role(row, context)
        listing["role"] = classification.get("listing_role")
        listing["role_confidence"] = classification.get("role_confidence")
        listing["role_reasons"] = classification.get("role_reasons") or []
        listing["eligible_role"] = classification.get("eligible_for_market_analytics", False)


# ---------------------------------------------------------------------------
# 4. Snapshot / eligibility / representative listing tai thoi diem T
# ---------------------------------------------------------------------------


def listing_snapshot_at(listing: dict, at: date):
    """Snapshot gan nhat <= ``at``. Giu gia cu neu ngay T khong co snapshot moi."""
    latest = None
    for snapshot_date in listing["snapshot_dates"]:
        if snapshot_date > at:
            break
        latest = listing["snapshots"][snapshot_date]
    return latest


def listing_eligibility_at(listing: dict, at: date, *, min_price: float, eligible_roles: set[str]):
    """Kiem tra listing co du dieu kien lam dai dien tai thoi diem T khong."""
    if listing.get("exclude_flag"):
        return {"eligible": False, "reason": "excluded", "snapshot": None}
    if listing.get("role") not in eligible_roles:
        return {"eligible": False, "reason": "role", "snapshot": None}

    appeared = listing.get("appeared_at")
    if appeared is None or appeared > at:
        return {"eligible": False, "reason": "notYetPublished", "snapshot": None}

    snapshot = listing_snapshot_at(listing, at)
    if snapshot is None:
        return {"eligible": False, "reason": "noSnapshot", "snapshot": None}

    price = snapshot.get("price")
    if price is None or price <= min_price:
        return {"eligible": False, "reason": "price", "snapshot": snapshot}

    return {"eligible": True, "reason": None, "snapshot": snapshot}


def representative_listing_at(listings: list[dict], at: date, *, min_price: float, eligible_roles: set[str]):
    """Listing du dieu kien co thoi diem xuat hien moi nhat <= T.

    Prompt muc 18: listing moi nhung < nguong gia hoac sai role KHONG duoc chon,
    seller van giu gia theo listing cu -> khong tao ra price crash gia.
    """
    best = None
    best_snapshot = None
    for listing in listings:
        verdict = listing_eligibility_at(listing, at, min_price=min_price, eligible_roles=eligible_roles)
        if not verdict["eligible"]:
            continue
        if best is None:
            best, best_snapshot = listing, verdict["snapshot"]
            continue
        current_key = (listing.get("appeared_at"), listing.get("first_seen"), listing.get("listing_id"))
        best_key = (best.get("appeared_at"), best.get("first_seen"), best.get("listing_id"))
        if current_key > best_key:
            best, best_snapshot = listing, verdict["snapshot"]
    if best is None:
        return None
    return {"listing": best, "snapshot": best_snapshot}


# ---------------------------------------------------------------------------
# 5. Truc thoi gian + chuoi gia cua seller
# ---------------------------------------------------------------------------


def build_axis(listings: list[dict]) -> list[date]:
    dates: set[date] = set()
    for listing in listings:
        dates.update(listing["snapshot_dates"])
    return sorted(dates)


def build_seller_series(seller_listings: list[dict], axis: list[date], *, min_price: float, eligible_roles: set[str]):
    """Chuoi gia dai dien cua 1 seller doc theo truc thoi gian."""
    points = []
    for at in axis:
        representative = representative_listing_at(
            seller_listings, at, min_price=min_price, eligible_roles=eligible_roles
        )
        if representative is None:
            points.append({"date": at, "price": None, "listing_id": None, "status": None})
            continue
        listing = representative["listing"]
        snapshot = representative["snapshot"]
        points.append(
            {
                "date": at,
                "price": _round(snapshot.get("price")),
                "listing_id": listing.get("listing_id"),
                "listing_key": listing.get("key"),
                "listing_title": listing.get("title"),
                "listing_url": listing.get("url"),
                "status": snapshot.get("status"),
            }
        )
    return points


def build_seller_events(seller_listings: list[dict], series: list[dict]) -> list[dict]:
    """Timeline su kien seller-level (prompt muc 15)."""
    events: list[dict] = []
    previous = None

    listing_by_id = {listing.get("listing_id"): listing for listing in seller_listings}

    for point in series:
        if point.get("price") is None:
            continue
        if previous is None:
            events.append(
                {
                    "date": point["date"],
                    "type": EVENT_TRACKING_STARTED,
                    "listing_id": point["listing_id"],
                    "price": point["price"],
                    "message": f"Bắt đầu theo dõi {point['listing_id']} @ {point['price']}",
                }
            )
            previous = point
            continue

        same_listing = previous.get("listing_id") == point.get("listing_id")

        if not same_listing:
            events.append(
                {
                    "date": point["date"],
                    "type": EVENT_NEW_LISTING_PRICE_SHIFT,
                    "listing_id": point["listing_id"],
                    "previous_listing_id": previous.get("listing_id"),
                    "price": point["price"],
                    "previous_price": previous.get("price"),
                    "change_pct": _round(percent_change(previous.get("price"), point.get("price"))),
                    "message": (
                        f"Seller đăng listing mới: {previous.get('listing_id')} "
                        f"→ {point.get('listing_id')}"
                    ),
                }
            )
        elif previous.get("price") != point.get("price"):
            events.append(
                {
                    "date": point["date"],
                    "type": EVENT_PRICE_CHANGED,
                    "listing_id": point["listing_id"],
                    "price": point["price"],
                    "previous_price": previous.get("price"),
                    "change_pct": _round(percent_change(previous.get("price"), point.get("price"))),
                    "message": f"{point['listing_id']}: {previous.get('price')} → {point.get('price')}",
                }
            )

        if previous.get("status") != point.get("status") and point.get("status"):
            events.append(
                {
                    "date": point["date"],
                    "type": EVENT_STATUS_CHANGED,
                    "listing_id": point["listing_id"],
                    "status": point.get("status"),
                    "previous_status": previous.get("status"),
                    "message": f"{previous.get('status')} → {point.get('status')}",
                }
            )

        previous = point

    # Status change o cap tung listing (ke ca listing khong phai dai dien).
    for listing in seller_listings:
        previous_status = None
        for snapshot_date in listing["snapshot_dates"]:
            status = listing["snapshots"][snapshot_date].get("status")
            if previous_status is not None and status != previous_status:
                events.append(
                    {
                        "date": snapshot_date,
                        "type": EVENT_STATUS_CHANGED,
                        "listing_id": listing.get("listing_id"),
                        "status": status,
                        "previous_status": previous_status,
                        "message": f"{listing.get('listing_id')}: {previous_status} → {status}",
                    }
                )
            previous_status = status

    unique: dict[tuple, dict] = {}
    for event in events:
        signature = (event["date"], event["type"], event.get("listing_id"), event.get("status"))
        unique.setdefault(signature, event)

    return sorted(unique.values(), key=lambda item: (item["date"], item["type"]))


# ---------------------------------------------------------------------------
# 6. Tong hop seller / listing / keyword
# ---------------------------------------------------------------------------


def build_listing_summary(listing: dict, at: date, *, min_price: float, eligible_roles: set[str]) -> dict:
    snapshot = listing_snapshot_at(listing, at)
    prices = [
        listing["snapshots"][snapshot_date].get("price")
        for snapshot_date in listing["snapshot_dates"]
        if listing["snapshots"][snapshot_date].get("price") is not None
    ]
    first_price = prices[0] if prices else None
    current_price = snapshot.get("price") if snapshot else None
    verdict = listing_eligibility_at(listing, at, min_price=min_price, eligible_roles=eligible_roles)

    return {
        "listing_id": listing.get("listing_id"),
        "marketplace": listing.get("marketplace"),
        "title": listing.get("title"),
        "url": listing.get("url"),
        "image_url": listing.get("image_url"),
        "role": listing.get("role"),
        "role_reasons": listing.get("role_reasons"),
        "condition": listing.get("condition"),
        "category_name": listing.get("category_name"),
        "currency": listing.get("currency"),
        "published_at": listing.get("published_at"),
        "first_seen": listing.get("first_seen"),
        "current_price": _round(current_price),
        "first_price": _round(first_price),
        "min_price": _round(min(prices)) if prices else None,
        "max_price": _round(max(prices)) if prices else None,
        "change_pct": _round(percent_change(first_price, current_price)),
        "status": snapshot.get("status") if snapshot else "UNKNOWN",
        "eligible": verdict["eligible"],
        "ineligible_reason": verdict["reason"],
        "last_updated": listing["snapshot_dates"][-1] if listing["snapshot_dates"] else None,
        "sparkline": [
            {
                "date": snapshot_date,
                "price": _round(listing["snapshots"][snapshot_date].get("price")),
                "status": listing["snapshots"][snapshot_date].get("status"),
            }
            for snapshot_date in listing["snapshot_dates"]
        ],
    }


def build_seller_summary(
    seller: str,
    seller_listings: list[dict],
    series: list[dict],
    at: date,
    *,
    min_price: float,
    eligible_roles: set[str],
) -> dict:
    representative = representative_listing_at(
        seller_listings, at, min_price=min_price, eligible_roles=eligible_roles
    )
    listing_summaries = [
        build_listing_summary(listing, at, min_price=min_price, eligible_roles=eligible_roles)
        for listing in seller_listings
    ]

    active = [item for item in listing_summaries if item["status"] in ACTIVE_STATUSES and item["eligible"]]
    active_prices = [item["current_price"] for item in active if item["current_price"] is not None]

    representative_id = representative["listing"].get("listing_id") if representative else None
    representative_price = representative["snapshot"].get("price") if representative else None

    priced_points = [point for point in series if point.get("price") is not None]
    first_price = priced_points[0]["price"] if priced_points else None

    return {
        "seller": seller,
        "marketplace": seller_listings[0].get("marketplace") if seller_listings else "",
        "representative_listing_id": representative_id,
        "representative_price": _round(representative_price),
        "representative_url": representative["listing"].get("url") if representative else None,
        "active_listing_count": len(active),
        "total_listing_count": len(listing_summaries),
        "active_price_min": _round(min(active_prices)) if active_prices else None,
        "active_price_max": _round(max(active_prices)) if active_prices else None,
        "change_pct": _round(percent_change(first_price, representative_price)),
        "last_updated": max(
            (item["last_updated"] for item in listing_summaries if item["last_updated"]),
            default=None,
        ),
        "listings": listing_summaries,
    }


def build_classification_audit(listings: list[dict], at: date, *, min_price: float, eligible_roles: set[str]):
    """Listing bi loai khoi phan tich chinh va ly do (prompt muc 18)."""
    audit = []
    reason_labels = {
        "role": "Không phải whole_product",
        "price": f"Giá <= ngưỡng {min_price:g}",
        "excluded": "Bị đánh dấu loại trừ",
        "noSnapshot": "Chưa có snapshot giá",
        "notYetPublished": "Chưa xuất hiện tại thời điểm này",
    }
    for listing in listings:
        verdict = listing_eligibility_at(listing, at, min_price=min_price, eligible_roles=eligible_roles)
        if verdict["eligible"]:
            continue
        snapshot = verdict.get("snapshot") or listing_snapshot_at(listing, at)
        audit.append(
            {
                "listing_id": listing.get("listing_id"),
                "seller": listing.get("seller"),
                "title": listing.get("title"),
                "url": listing.get("url"),
                "role": listing.get("role"),
                "role_reasons": listing.get("role_reasons"),
                "price": _round(snapshot.get("price")) if snapshot else None,
                "reason": verdict["reason"],
                "reason_label": reason_labels.get(verdict["reason"], verdict["reason"]),
            }
        )
    return audit


# ---------------------------------------------------------------------------
# 7. Alert panel (prompt muc 11)
# ---------------------------------------------------------------------------


def build_keyword_alerts(
    sellers: list[dict],
    events_by_seller: dict[str, list[dict]],
    *,
    price_drop_warning_pct: float,
    price_drop_critical_pct: float,
    multiple_active_threshold: int,
) -> list[dict]:
    alerts: list[dict] = []

    for summary in sellers:
        seller = summary["seller"]
        events = events_by_seller.get(seller, [])

        # Alert 1 + 2: bien dong gia, tach bach 2 loai su kien.
        for event in reversed(events):
            change = event.get("change_pct")
            if event["type"] == EVENT_PRICE_CHANGED and change is not None and change < 0:
                drop = abs(change)
                if drop >= price_drop_warning_pct:
                    alerts.append(
                        {
                            "type": "PRICE_DROP",
                            "severity": SEVERITY_CRITICAL if drop >= price_drop_critical_pct else SEVERITY_WARNING,
                            "seller": seller,
                            "listing_id": event.get("listing_id"),
                            "title": f"{seller} giảm giá mạnh",
                            "detail": f"{event.get('listing_id')}: {event.get('previous_price')} → {event.get('price')}",
                            "change_pct": change,
                            "date": event["date"],
                        }
                    )
                break
            if event["type"] == EVENT_NEW_LISTING_PRICE_SHIFT:
                alerts.append(
                    {
                        "type": EVENT_NEW_LISTING_PRICE_SHIFT,
                        "severity": SEVERITY_WARNING,
                        "seller": seller,
                        "listing_id": event.get("listing_id"),
                        "title": f"{seller} vừa đăng listing mới",
                        "detail": (
                            f"Listing cũ: {event.get('previous_listing_id')} - {event.get('previous_price')} | "
                            f"Listing mới: {event.get('listing_id')} - {event.get('price')}"
                        ),
                        "change_pct": change,
                        "date": event["date"],
                    }
                )
                break

        # Alert 3: nhieu listing ACTIVE cung luc.
        if summary["active_listing_count"] >= multiple_active_threshold:
            alerts.append(
                {
                    "type": "MULTIPLE_ACTIVE_LISTINGS",
                    "severity": SEVERITY_INFO,
                    "seller": seller,
                    "listing_id": summary.get("representative_listing_id"),
                    "title": f"{seller} đang có {summary['active_listing_count']} listing ACTIVE",
                    "detail": (
                        f"Khoảng giá: {summary.get('active_price_min')} – {summary.get('active_price_max')} | "
                        f"Latest: {summary.get('representative_listing_id')} - {summary.get('representative_price')}"
                    ),
                    "change_pct": None,
                    "date": summary.get("last_updated"),
                }
            )

        # Alert 4: doi trang thai.
        for event in reversed(events):
            if event["type"] != EVENT_STATUS_CHANGED:
                continue
            status = event.get("status")
            if status in ACTIVE_STATUSES:
                break
            alerts.append(
                {
                    "type": "STATUS_CHANGE",
                    "severity": SEVERITY_WARNING if status == "OUT_OF_STOCK" else SEVERITY_INFO,
                    "seller": seller,
                    "listing_id": event.get("listing_id"),
                    "title": f"{seller}: {status}",
                    "detail": f"{event.get('previous_status')} → {status}",
                    "change_pct": None,
                    "date": event["date"],
                }
            )
            break

    severity_rank = {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    alerts.sort(key=lambda item: (severity_rank.get(item["severity"], 3), str(item.get("date") or "")))
    return alerts


# ---------------------------------------------------------------------------
# 8. Payload tong cho dashboard
# ---------------------------------------------------------------------------


def build_keyword_payload(
    observations: list[dict],
    *,
    keyword: str,
    min_price: float = 500.0,
    eligible_roles: set[str] | None = None,
    price_drop_warning_pct: float = 20.0,
    price_drop_critical_pct: float = 30.0,
    multiple_active_threshold: int = 2,
    include_all_roles: bool = False,
) -> dict:
    """Payload day du cho 1 keyword: KPI, chart series, bang, alert, audit."""
    roles = eligible_roles or {ROLE_WHOLE}

    listings = build_listing_timelines(observations)
    classify_listings(listings)

    axis = build_axis(listings)
    if not axis:
        return {
            "keyword": keyword,
            "currency": "USD",
            "axis": [],
            "sellers": [],
            "series": [],
            "alerts": [],
            "audit": [],
            "summary": {
                "seller_count": 0,
                "listing_count": 0,
                "median_price": None,
                "min_price": None,
                "max_price": None,
                "active_listings": 0,
                "out_of_stock": 0,
                "ended": 0,
                "new_listings": 0,
            },
            "empty_reason": "no_listing",
        }

    latest = axis[-1]

    listings_by_seller: dict[str, list[dict]] = defaultdict(list)
    for listing in listings:
        seller = listing.get("seller") or "(không rõ seller)"
        if not include_all_roles and listing.get("role") not in roles:
            # Van giu de audit, nhung khong dua vao chuoi gia.
            listings_by_seller[seller].append(listing)
            continue
        listings_by_seller[seller].append(listing)

    series: list[dict] = []
    seller_summaries: list[dict] = []
    events_by_seller: dict[str, list[dict]] = {}

    for seller, seller_listings in listings_by_seller.items():
        seller_series = build_seller_series(
            seller_listings, axis, min_price=min_price, eligible_roles=roles
        )
        if not any(point.get("price") is not None for point in seller_series):
            continue

        events = build_seller_events(seller_listings, seller_series)
        summary = build_seller_summary(
            seller, seller_listings, seller_series, latest, min_price=min_price, eligible_roles=roles
        )

        events_by_seller[seller] = events
        series.append({"seller": seller, "points": seller_series})
        summary["events"] = events
        seller_summaries.append(summary)

    seller_summaries.sort(key=lambda item: (-(item.get("representative_price") or 0), item["seller"].lower()))

    representative_prices = [
        summary["representative_price"]
        for summary in seller_summaries
        if summary.get("representative_price") is not None
    ]

    eligible_listing_count = sum(
        1
        for listing in listings
        if listing_eligibility_at(listing, latest, min_price=min_price, eligible_roles=roles)["eligible"]
    )

    status_counts = {"ACTIVE": 0, "OUT_OF_STOCK": 0, "ENDED": 0, "NEW_LISTING": 0}
    for listing in listings:
        snapshot = listing_snapshot_at(listing, latest)
        if not snapshot:
            continue
        status = snapshot.get("status")
        if status in status_counts:
            status_counts[status] += 1

    alerts = build_keyword_alerts(
        seller_summaries,
        events_by_seller,
        price_drop_warning_pct=price_drop_warning_pct,
        price_drop_critical_pct=price_drop_critical_pct,
        multiple_active_threshold=multiple_active_threshold,
    )

    audit = build_classification_audit(listings, latest, min_price=min_price, eligible_roles=roles)

    currency = listings[0].get("currency") if listings else "USD"

    return {
        "keyword": keyword,
        "currency": currency or "USD",
        "generated_for": latest,
        "axis": axis,
        "sellers": seller_summaries,
        "series": series,
        "alerts": alerts,
        "audit": audit,
        "summary": {
            "seller_count": len(seller_summaries),
            "listing_count": eligible_listing_count,
            "total_listing_count": len(listings),
            "median_price": _round(median(representative_prices)),
            "min_price": _round(min(representative_prices)) if representative_prices else None,
            "max_price": _round(max(representative_prices)) if representative_prices else None,
            "active_listings": status_counts["ACTIVE"] + status_counts["NEW_LISTING"],
            "out_of_stock": status_counts["OUT_OF_STOCK"],
            "ended": status_counts["ENDED"],
            "new_listings": status_counts["NEW_LISTING"],
            "excluded_listings": len(audit),
        },
        "empty_reason": None if seller_summaries else "no_eligible_seller",
    }


def build_export_rows(payload: dict) -> list[dict]:
    """Phang hoa payload thanh cac dong CSV cho Export."""
    rows = []
    for summary in payload.get("sellers", []):
        for listing in summary.get("listings", []):
            rows.append(
                {
                    "keyword": payload.get("keyword"),
                    "seller": summary.get("seller"),
                    "marketplace": listing.get("marketplace"),
                    "listing_id": listing.get("listing_id"),
                    "listing_title": listing.get("title"),
                    "listing_url": listing.get("url"),
                    "role": listing.get("role"),
                    "is_representative": listing.get("listing_id") == summary.get("representative_listing_id"),
                    "first_seen": listing.get("first_seen"),
                    "published_at": listing.get("published_at"),
                    "current_price": listing.get("current_price"),
                    "min_price": listing.get("min_price"),
                    "max_price": listing.get("max_price"),
                    "change_pct": listing.get("change_pct"),
                    "status": listing.get("status"),
                    "eligible": listing.get("eligible"),
                    "ineligible_reason": listing.get("ineligible_reason"),
                    "last_updated": listing.get("last_updated"),
                    "currency": listing.get("currency"),
                }
            )
    return rows
