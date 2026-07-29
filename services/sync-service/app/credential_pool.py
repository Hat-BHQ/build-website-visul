from datetime import datetime
from sqlalchemy.orm import Session
from app.models import MarketplaceAccount


def select_available_account(db: Session, marketplace: str) -> MarketplaceAccount | None:
    now = datetime.utcnow()
    return (
        db.query(MarketplaceAccount)
        .filter(
            MarketplaceAccount.marketplace == marketplace,
            MarketplaceAccount.status == "active",
            MarketplaceAccount.remaining_quota > 0,
        )
        .filter(
            (MarketplaceAccount.cooldown_until.is_(None))
            | (MarketplaceAccount.cooldown_until <= now)
        )
        .order_by(MarketplaceAccount.remaining_quota.desc(), MarketplaceAccount.last_used_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
