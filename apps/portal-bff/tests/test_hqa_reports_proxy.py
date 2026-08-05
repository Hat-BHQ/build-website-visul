from fastapi.testclient import TestClient

from app.main import app


def _param_values(call, key: str):
    params = call["params"]
    if isinstance(params, dict):
        value = params.get(key)
        return [] if value is None else [value]
    return [item_value for item_key, item_value in params if item_key == key]


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text_payload: str | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self._text_payload = text_payload
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._payload

    @property
    def text(self):
        if self._text_payload is not None:
            return self._text_payload
        return str(self._payload)


class FakeAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, params=None, json=None):
        headers = headers or {}
        if params is None:
            params_payload = {}
        elif hasattr(params, "multi_items"):
            params_payload = list(params.multi_items())
        else:
            params_payload = dict(params)
        payload = {
            "method": method,
            "url": url,
            "headers": dict(headers),
            "params": params_payload,
            "json": json,
        }
        FakeAsyncClient.calls.append(payload)
        if "export-csv" in url or url.endswith("/export"):
            return FakeResponse(
                200,
                {"ok": True},
                text_payload="col1,col2\n1,2\n",
                headers={
                    "content-type": "text/csv; charset=utf-8",
                    "content-disposition": "attachment; filename=export.csv",
                },
            )
        if "raw-listings" in url and not headers.get("Authorization"):
            return FakeResponse(401, {"detail": "Missing access token"})
        return FakeResponse(200, {"ok": True, "url": url, "params": dict(params or {})})


def test_raw_listings_uses_bff_route_and_forwards_auth(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/hqa/reports/marketplace/raw-listings?page=2&page_size=50&sort=collected_at_desc",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.json()["url"] == "http://hqa-service:8000/internal/v1/reports/marketplace/raw-listings"
    assert FakeAsyncClient.calls[-1]["headers"]["Authorization"] == "Bearer valid-token"
    assert _param_values(FakeAsyncClient.calls[-1], "page") == ["2"]
    assert _param_values(FakeAsyncClient.calls[-1], "page_size") == ["50"]


def test_summary_and_raw_listings_share_auth_pattern(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        summary = client.get(
            "/api/v1/hqa/reports/marketplace/summary?report_date=2026-07-30",
            headers={"Authorization": "Bearer valid-token"},
        )
        raw = client.get(
            "/api/v1/hqa/reports/marketplace/raw-listings?page=1&page_size=50",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert summary.status_code == 200
    assert raw.status_code == 200
    assert FakeAsyncClient.calls[0]["url"] == "http://hqa-service:8000/internal/v1/reports/marketplace/summary"
    assert FakeAsyncClient.calls[1]["url"] == "http://hqa-service:8000/internal/v1/reports/marketplace/raw-listings"
    assert FakeAsyncClient.calls[0]["headers"]["Authorization"] == "Bearer valid-token"
    assert FakeAsyncClient.calls[1]["headers"]["Authorization"] == "Bearer valid-token"


def test_raw_listings_missing_session_returns_upstream_auth_error(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        response = client.get("/api/v1/hqa/reports/marketplace/raw-listings?page=1&page_size=50")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing access token"


def test_csv_export_relay_returns_csv_payload(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/hqa/reports/marketplace/dashboard/export-csv?dataset=summary",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "col1,col2" in response.text


def test_all_listings_new_routes_forward_to_hqa(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        list_response = client.get(
            "/api/v1/hqa/listings?page=1&page_size=20&sort_collected=newest",
            headers={"Authorization": "Bearer valid-token"},
        )
        summary_response = client.get(
            "/api/v1/hqa/listings/summary?brand=jbl",
            headers={"Authorization": "Bearer valid-token"},
        )
        options_response = client.get(
            "/api/v1/hqa/listings/filter-options?brand=jbl&condition=new&condition=used&status=active&status=ended",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert list_response.status_code == 200
    assert summary_response.status_code == 200
    assert options_response.status_code == 200
    urls = [call["url"] for call in FakeAsyncClient.calls]
    assert "http://hqa-service:8000/internal/v1/listings" in urls
    assert "http://hqa-service:8000/internal/v1/hqa/listings/summary" in urls
    assert "http://hqa-service:8000/internal/v1/hqa/listings/filter-options" in urls
    options_call = next(call for call in FakeAsyncClient.calls if call["url"].endswith("/internal/v1/hqa/listings/filter-options"))
    assert ("condition", "new") in options_call["params"]
    assert ("condition", "used") in options_call["params"]
    assert ("status", "active") in options_call["params"]
    assert ("status", "ended") in options_call["params"]


def test_all_listings_filter_options_field_mode_forwards_pagination_query(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/hqa/listings/filter-options?field=model&page=2&page_size=25&search=l100&brand=jbl",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    options_call = next(call for call in FakeAsyncClient.calls if call["url"].endswith("/internal/v1/hqa/listings/filter-options"))
    assert _param_values(options_call, "field") == ["model"]
    assert _param_values(options_call, "page") == ["2"]
    assert _param_values(options_call, "page_size") == ["25"]
    assert _param_values(options_call, "search") == ["l100"]
    assert _param_values(options_call, "brand") == ["jbl"]


def test_all_listings_export_route_relays_csv(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/hqa/listings/export?brand=jbl",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "col1,col2" in response.text


def test_hqa_dashboard_new_routes_forward_to_hqa(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        filter_options = client.get(
            "/api/v1/hqa/dashboard/filter-options?marketplace=ebay&marketplace=reverb&brand=jbl",
            headers={"Authorization": "Bearer valid-token"},
        )
        seller_summary = client.get(
            "/api/v1/hqa/dashboard/sellers/summary?date_from=2026-07-01&date_to=2026-08-31",
            headers={"Authorization": "Bearer valid-token"},
        )
        price_trend = client.get(
            "/api/v1/hqa/dashboard/prices/trend?granularity=week&marketplace=ebay",
            headers={"Authorization": "Bearer valid-token"},
        )
        alerts = client.get(
            "/api/v1/hqa/dashboard/alerts?status=out_of_stock",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert filter_options.status_code == 200
    assert seller_summary.status_code == 200
    assert price_trend.status_code == 200
    assert alerts.status_code == 200

    urls = [call["url"] for call in FakeAsyncClient.calls]
    assert "http://hqa-service:8000/internal/v1/hqa/dashboard/filter-options" in urls
    assert "http://hqa-service:8000/internal/v1/hqa/dashboard/sellers/summary" in urls
    assert "http://hqa-service:8000/internal/v1/hqa/dashboard/prices/trend" in urls
    assert "http://hqa-service:8000/internal/v1/hqa/dashboard/alerts" in urls

    options_call = next(call for call in FakeAsyncClient.calls if call["url"].endswith("/internal/v1/hqa/dashboard/filter-options"))
    assert ("marketplace", "ebay") in options_call["params"]
    assert ("marketplace", "reverb") in options_call["params"]


def test_hqa_dashboard_export_route_relays_csv(monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.calls = []

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/hqa/dashboard/export?dataset=prices_trend&granularity=month",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "col1,col2" in response.text