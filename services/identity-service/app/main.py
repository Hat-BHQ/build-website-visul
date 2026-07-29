from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DbSession
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Membership, User
from app.schemas import (AssignMembershipRequest, CreateUserRequest, LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UserStatusRequest)
from app.security import (
    create_access_token, create_refresh_session, decode_access_token, hash_password,
    module_payload, revoke_refresh_session, rotate_refresh_session, verify_password,
)

bearer = HTTPBearer(auto_error=False)



def claims_from_credentials(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def can_manage_module(claims: dict, module_code: str) -> bool:
    if claims.get("system_role") == "superadmin":
        return True
    permission = f"{module_code.lower()}.users.manage"
    return any(item.get("code") == module_code and permission in item.get("permissions", []) for item in claims.get("modules", []))


def serialize_admin_user(user: User) -> dict:
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name,
        "system_role": user.system_role, "is_active": user.is_active,
        "memberships": [
            {"module_code": item.module_code, "role": item.role, "status": item.status}
            for item in user.memberships
        ],
    }

def user_data(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "system_role": user.system_role,
    }


def seed_user(db: DbSession, email: str, password: str, full_name: str, system_role=None, membership=None):
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        user = User(
            email=email.lower(), full_name=full_name,
            password_hash=hash_password(password), system_role=system_role,
        )
        db.add(user)
        db.flush()
    if membership:
        module_code, role = membership
        exists = db.query(Membership).filter(
            Membership.user_id == user.id, Membership.module_code == module_code
        ).first()
        if not exists:
            db.add(Membership(user_id=user.id, module_code=module_code, role=role))
    db.commit()


def bootstrap():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_user(db, settings.bootstrap_superadmin_email, settings.bootstrap_superadmin_password,
                  "System Root", system_role="superadmin")
        seed_user(db, settings.bootstrap_hqa_admin_email, settings.bootstrap_hqa_admin_password,
                  "HQA Administrator", membership=("HQA", "admin"))
        seed_user(db, settings.bootstrap_hqa_user_email, settings.bootstrap_hqa_user_password,
                  "HQA User", membership=("HQA", "user"))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    yield


app = FastAPI(title="Identity Service", version="2.0.0", lifespan=lifespan)


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready(db: DbSession = Depends(get_db)):
    db.query(User).limit(1).all()
    return {"status": "ready", "database": "ok"}


@app.post("/internal/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DbSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    refresh_token, _ = create_refresh_session(
        db, user, request.client.host if request.client else None, request.headers.get("user-agent")
    )
    return {
        "access_token": create_access_token(user),
        "refresh_token": refresh_token,
        "user": user_data(user),
        "modules": module_payload(user),
    }


@app.post("/internal/v1/auth/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: DbSession = Depends(get_db)):
    try:
        refresh_token, _, user = rotate_refresh_session(db, payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return {
        "access_token": create_access_token(user),
        "refresh_token": refresh_token,
        "user": user_data(user),
        "modules": module_payload(user),
    }


@app.post("/internal/v1/auth/logout", status_code=204)
def logout(payload: LogoutRequest, db: DbSession = Depends(get_db)):
    revoke_refresh_session(db, payload.refresh_token)


@app.get("/internal/v1/auth/me")
def me(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return claims


@app.get("/internal/v1/auth/authorize")
def authorize(
    module: str,
    permission: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if claims.get("system_role") == "superadmin":
        return {"allowed": True}
    for item in claims.get("modules", []):
        if item.get("code") == module and permission in item.get("permissions", []):
            return {"allowed": True}
    raise HTTPException(status_code=403, detail="Permission denied")


@app.get("/internal/v1/admin/users")
def list_users(
    module_code: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: DbSession = Depends(get_db),
):
    claims = claims_from_credentials(credentials)
    if claims.get("system_role") != "superadmin" and (not module_code or not can_manage_module(claims, module_code)):
        raise HTTPException(status_code=403, detail="Permission denied")
    query = db.query(User)
    if module_code and claims.get("system_role") != "superadmin":
        query = query.join(Membership).filter(Membership.module_code == module_code)
    return {"items": [serialize_admin_user(user) for user in query.order_by(User.created_at.desc()).all()]}


@app.post("/internal/v1/admin/users", status_code=201)
def create_user(
    payload: CreateUserRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: DbSession = Depends(get_db),
):
    claims = claims_from_credentials(credentials)
    if claims.get("system_role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(email=payload.email.lower(), full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return serialize_admin_user(user)


@app.put("/internal/v1/admin/users/{user_id}/membership")
def assign_membership(
    user_id: str,
    payload: AssignMembershipRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: DbSession = Depends(get_db),
):
    claims = claims_from_credentials(credentials)
    if not can_manage_module(claims, payload.module_code):
        raise HTTPException(status_code=403, detail="Permission denied")
    if claims.get("system_role") != "superadmin" and payload.role == "admin":
        raise HTTPException(status_code=403, detail="Only superadmin can assign admin")
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    membership = db.query(Membership).filter(Membership.user_id == user_id, Membership.module_code == payload.module_code).first()
    if not membership:
        membership = Membership(user_id=user_id, module_code=payload.module_code, role=payload.role)
        db.add(membership)
    else:
        membership.role = payload.role; membership.status = "active"
    db.commit(); db.refresh(user)
    return serialize_admin_user(user)


@app.patch("/internal/v1/admin/users/{user_id}/status")
def update_user_status(
    user_id: str,
    payload: UserStatusRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: DbSession = Depends(get_db),
):
    claims = claims_from_credentials(credentials)
    if claims.get("system_role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.id == claims.get("sub") and not payload.is_active:
        raise HTTPException(status_code=400, detail="Cannot disable current superadmin session")
    user.is_active = payload.is_active; db.commit(); db.refresh(user)
    return serialize_admin_user(user)
