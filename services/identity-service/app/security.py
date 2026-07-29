import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session as DbSession
from app.config import settings
from app.models import Membership, Session, User
from app.jwt_utils import decode_jwt, encode_jwt

PASSWORD_ITERATIONS = 310000

ROLE_PERMISSIONS = {
    "HQA": {
        "admin": [
            "hqa.dashboard.view", "hqa.listings.view", "hqa.listings.export",
            "hqa.sync.run", "hqa.sync.view", "hqa.users.view", "hqa.users.manage",
        ],
        "user": ["hqa.dashboard.view", "hqa.listings.view", "hqa.sync.view"],
    },
    "HQS": {
        "admin": [
            "hqs.dashboard.view", "hqs.requests.view", "hqs.requests.create",
            "hqs.requests.update", "hqs.requests.assign", "hqs.requests.close",
            "hqs.users.view", "hqs.users.manage",
        ],
        "user": ["hqs.dashboard.view", "hqs.requests.view", "hqs.requests.create"],
    },
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, salt, expected = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def module_payload(user: User) -> list[dict]:
    if user.system_role == "superadmin":
        return [
            {"code": code, "role": "superadmin", "permissions": ["*"]}
            for code in sorted(ROLE_PERMISSIONS)
        ]
    result = []
    for membership in user.memberships:
        if membership.status != "active":
            continue
        permissions = ROLE_PERMISSIONS.get(membership.module_code, {}).get(membership.role, [])
        result.append({
            "code": membership.module_code,
            "role": membership.role,
            "permissions": permissions,
        })
    return result


def create_access_token(user: User) -> str:
    now = utcnow()
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.full_name,
        "system_role": user.system_role,
        "modules": module_payload(user),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "type": "access",
    }
    return encode_jwt(payload, settings.jwt_secret)


def decode_access_token(token: str) -> dict:
    payload = decode_jwt(token, settings.jwt_secret)
    if payload.get("type") != "access":
        raise ValueError("Invalid token type")
    return payload


def create_refresh_session(db: DbSession, user: User, ip: str | None, user_agent: str | None):
    now = utcnow()
    token = secrets.token_urlsafe(48)
    session = Session(
        user_id=user.id,
        refresh_hash=hash_token(token),
        last_activity_at=now,
        idle_expires_at=now + timedelta(minutes=settings.session_idle_minutes),
        absolute_expires_at=now + timedelta(hours=settings.session_absolute_hours),
        ip_address=ip,
        user_agent=user_agent,
    )
    db.add(session)
    db.commit()
    return token, session


def rotate_refresh_session(db: DbSession, refresh_token: str):
    now = utcnow()
    session = db.query(Session).filter(Session.refresh_hash == hash_token(refresh_token)).first()
    if not session or session.revoked_at is not None:
        raise ValueError("Session not found")
    if now >= session.idle_expires_at or now >= session.absolute_expires_at:
        session.revoked_at = now
        db.commit()
        raise ValueError("Session expired")
    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    if not user:
        raise ValueError("User unavailable")
    new_token = secrets.token_urlsafe(48)
    session.refresh_hash = hash_token(new_token)
    session.last_activity_at = now
    session.idle_expires_at = now + timedelta(minutes=settings.session_idle_minutes)
    db.commit()
    db.refresh(user)
    return new_token, session, user


def revoke_refresh_session(db: DbSession, refresh_token: str) -> None:
    session = db.query(Session).filter(Session.refresh_hash == hash_token(refresh_token)).first()
    if session and session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()
