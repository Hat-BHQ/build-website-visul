from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.config import settings

app = FastAPI(title="Portal BFF", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_token_payload(data: dict) -> dict:
    return {key: value for key, value in data.items() if key != "refresh_token"}


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=24 * 60 * 60,
        path="/api/v1/auth",
    )


async def relay(method: str, url: str, request: Request, json_data=None):
    headers = {}
    if authorization := request.headers.get("authorization"):
        headers["Authorization"] = authorization
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.request(method, url, headers=headers, params=request.query_params, json=json_data)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    if response.status_code == 204:
        return None
    return response.json()


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
async def ready():
    async with httpx.AsyncClient(timeout=5) as client:
        checks = await client.get(f"{settings.identity_service_url}/health/ready")
        checks.raise_for_status()
    return {"status": "ready", "identity": "ok"}


@app.post("/api/v1/auth/login")
async def login(request: Request, response: Response):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=20) as client:
        upstream = await client.post(f"{settings.identity_service_url}/internal/v1/auth/login", json=payload)
    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.json().get("detail", "Login failed"))
    data = upstream.json()
    set_refresh_cookie(response, data["refresh_token"])
    return public_token_payload(data)


@app.post("/api/v1/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh session")
    async with httpx.AsyncClient(timeout=20) as client:
        upstream = await client.post(
            f"{settings.identity_service_url}/internal/v1/auth/refresh",
            json={"refresh_token": token},
        )
    if upstream.status_code >= 400:
        response.delete_cookie(settings.cookie_name, path="/api/v1/auth")
        raise HTTPException(status_code=upstream.status_code, detail=upstream.json().get("detail", "Refresh failed"))
    data = upstream.json()
    set_refresh_cookie(response, data["refresh_token"])
    return public_token_payload(data)


@app.get("/api/v1/auth/session")
async def session(request: Request, response: Response):
    return await refresh(request, response)


@app.post("/api/v1/auth/logout", status_code=204)
async def logout(request: Request, response: Response):
    token = request.cookies.get(settings.cookie_name)
    if token:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(f"{settings.identity_service_url}/internal/v1/auth/logout", json={"refresh_token": token})
    response.delete_cookie(settings.cookie_name, path="/api/v1/auth")


@app.get("/api/v1/hqa/dashboard")
async def hqa_dashboard(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/dashboard", request)


@app.get("/api/v1/hqa/listings")
async def hqa_listings(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/listings", request)


@app.get("/api/v1/hqa/listings/{listing_id}")
async def hqa_listing_detail(listing_id: str, request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/listings/{listing_id}", request)


@app.post("/api/v1/sync/jobs", status_code=202)
async def create_sync_job(request: Request):
    return await relay("POST", f"{settings.sync_service_url}/internal/v1/jobs", request, await request.json())


@app.get("/api/v1/sync/jobs")
async def sync_jobs(request: Request):
    return await relay("GET", f"{settings.sync_service_url}/internal/v1/jobs", request)


@app.get("/api/v1/sync/jobs/{job_id}")
async def sync_job(job_id: str, request: Request):
    return await relay("GET", f"{settings.sync_service_url}/internal/v1/jobs/{job_id}", request)


@app.get("/api/v1/hqs/dashboard")
async def hqs_dashboard(request: Request):
    return await relay("GET", f"{settings.hqs_service_url}/internal/v1/dashboard", request)


@app.get("/api/v1/hqs/requests")
async def hqs_requests(request: Request):
    return await relay("GET", f"{settings.hqs_service_url}/internal/v1/requests", request)


@app.post("/api/v1/hqs/requests", status_code=201)
async def create_hqs_request(request: Request):
    return await relay("POST", f"{settings.hqs_service_url}/internal/v1/requests", request, await request.json())


@app.get("/api/v1/system/users")
async def system_users(request: Request):
    return await relay("GET", f"{settings.identity_service_url}/internal/v1/admin/users", request)


@app.post("/api/v1/system/users", status_code=201)
async def create_system_user(request: Request):
    return await relay("POST", f"{settings.identity_service_url}/internal/v1/admin/users", request, await request.json())


@app.put("/api/v1/system/users/{user_id}/membership")
async def assign_system_membership(user_id: str, request: Request):
    return await relay("PUT", f"{settings.identity_service_url}/internal/v1/admin/users/{user_id}/membership", request, await request.json())


@app.patch("/api/v1/system/users/{user_id}/status")
async def update_system_user_status(user_id: str, request: Request):
    return await relay("PATCH", f"{settings.identity_service_url}/internal/v1/admin/users/{user_id}/status", request, await request.json())
