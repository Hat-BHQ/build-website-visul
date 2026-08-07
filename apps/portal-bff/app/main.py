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
    content_type = response.headers.get("content-type", "")
    if "text/csv" in content_type:
        headers = {}
        if response.headers.get("content-disposition"):
            headers["Content-Disposition"] = response.headers["content-disposition"]
        return Response(content=response.text, media_type="text/csv", headers=headers)
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
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/listings", request)


@app.get("/api/v1/hqa/listings/summary")
async def hqa_all_listings_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/listings/summary", request)


@app.get("/api/v1/hqa/listings/filter-options")
async def hqa_all_listings_filter_options(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/listings/filter-options", request)


@app.get("/api/v1/hqa/listings/export")
async def hqa_all_listings_export(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/listings/export", request)


@app.get("/api/v1/hqa/data-check/duplicates/summary")
async def hqa_data_check_duplicates_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/data-check/duplicates/summary", request)


@app.get("/api/v1/hqa/data-check/duplicates")
async def hqa_data_check_duplicates(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/data-check/duplicates", request)


@app.post("/api/v1/hqa/data-check/duplicates/cleanup")
async def hqa_data_check_duplicates_cleanup(request: Request):
    return await relay(
        "POST",
        f"{settings.hqa_service_url}/internal/v1/hqa/data-check/duplicates/cleanup",
        request,
        await request.json(),
    )


@app.get("/api/v1/hqa/dashboard/filter-options")
async def hqa_dashboard_filter_options(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/filter-options", request)


@app.get("/api/v1/hqa/dashboard/sellers/total")
async def hqa_dashboard_sellers_total(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/sellers/total", request)


@app.get("/api/v1/hqa/dashboard/summary")
async def hqa_dashboard_summary_v2(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/summary", request)


@app.get("/api/v1/hqa/dashboard/seller-trend")
async def hqa_dashboard_seller_trend_v2(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/seller-trend", request)


@app.get("/api/v1/hqa/dashboard/price-trend")
async def hqa_dashboard_price_trend_v2(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/price-trend", request)


@app.get("/api/v1/hqa/dashboard/price-comparison")
async def hqa_dashboard_price_comparison_v2(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/price-comparison", request)


@app.get("/api/v1/hqa/dashboard/sellers/summary")
async def hqa_dashboard_sellers_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/sellers/summary", request)


@app.get("/api/v1/hqa/dashboard/sellers/trend")
async def hqa_dashboard_sellers_trend(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/sellers/trend", request)


@app.get("/api/v1/hqa/dashboard/sellers/top")
async def hqa_dashboard_sellers_top(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/sellers/top", request)


@app.get("/api/v1/hqa/dashboard/prices/summary")
async def hqa_dashboard_prices_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/prices/summary", request)


@app.get("/api/v1/hqa/dashboard/prices/trend")
async def hqa_dashboard_prices_trend(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/prices/trend", request)


@app.get("/api/v1/hqa/dashboard/prices/by-keyword")
async def hqa_dashboard_prices_by_keyword(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/prices/by-keyword", request)


@app.get("/api/v1/hqa/dashboard/alerts")
async def hqa_dashboard_alerts(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/alerts", request)


@app.get("/api/v1/hqa/dashboard/export")
async def hqa_dashboard_export(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/hqa/dashboard/export", request)


@app.get("/api/v1/hqa/listings/{listing_id}")
async def hqa_listing_detail(listing_id: str, request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/listings/{listing_id}", request)


@app.get("/api/v1/hqa/reports/marketplace/summary")
async def hqa_marketplace_report_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/summary", request)


@app.get("/api/v1/hqa/reports/marketplace/listings")
async def hqa_marketplace_report_listings(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/listings", request)


@app.get("/api/v1/hqa/reports/marketplace/raw-listings")
async def hqa_marketplace_raw_listings(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/raw-listings", request)


@app.get("/api/v1/hqa/reports/marketplace/filter-options")
async def hqa_marketplace_filter_options(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/filter-options", request)


@app.get("/api/v1/hqa/reports/marketplace/raw-listings/export-csv")
async def hqa_marketplace_raw_listings_export_csv(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/raw-listings/export-csv", request)


@app.get("/api/v1/hqa/reports/marketplace/listings/export-csv")
async def hqa_marketplace_report_listings_export_csv(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/listings/export-csv", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/summary")
async def hqa_marketplace_dashboard_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/summary", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/price-trend")
async def hqa_marketplace_dashboard_price_trend(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/price-trend", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/seller-trend")
async def hqa_marketplace_dashboard_seller_trend(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/seller-trend", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/status-trend")
async def hqa_marketplace_dashboard_status_trend(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/status-trend", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/keyword-summary")
async def hqa_marketplace_dashboard_keyword_summary(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/keyword-summary", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/alerts")
async def hqa_marketplace_dashboard_alerts(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/alerts", request)


@app.get("/api/v1/hqa/reports/marketplace/dashboard/export-csv")
async def hqa_marketplace_dashboard_export_csv(request: Request):
    return await relay("GET", f"{settings.hqa_service_url}/internal/v1/reports/marketplace/dashboard/export-csv", request)


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
