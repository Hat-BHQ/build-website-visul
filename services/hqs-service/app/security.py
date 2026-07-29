from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.jwt_utils import decode_jwt
from app.config import settings
bearer = HTTPBearer(auto_error=False)

def require_permission(permission: str):
    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials: raise HTTPException(status_code=401, detail="Missing access token")
        try: claims = decode_jwt(credentials.credentials, settings.jwt_secret)
        except ValueError as exc: raise HTTPException(status_code=401, detail="Invalid access token") from exc
        if claims.get("system_role") == "superadmin": return claims
        for module in claims.get("modules", []):
            if module.get("code") == "HQS" and permission in module.get("permissions", []): return claims
        raise HTTPException(status_code=403, detail="Permission denied")
    return dependency
