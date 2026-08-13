# HQA Dashboard - kiểm tra đồng nhất prompt / mockup / source

Ngày rà soát: 2026-08-13

## Kết luận trước khi chỉnh sửa

Ba đầu vào chưa đồng nhất hoàn toàn:

- `form.txt` yêu cầu Dashboard dùng đúng tập filter đã áp dụng ở All Listings, không dựng một bộ filter Dashboard riêng.
- `hqa_dashboard_tab_mockup.html` mô tả đúng cấu trúc UI mong muốn (KPI, radar cảnh báo, 2 trend chart, phân tích nhóm+kỳ, dải giá, sparkline, gợi ý giá, Top 10 seller), nhưng dùng dữ liệu mẫu hard-code.
- Source cũ đã có Dashboard nhưng còn dùng filter riêng và nhiều endpoint rời; một số phần drill-down chưa gắn đúng Model + kỳ, chart chưa phải multi-series theo Model và một số số liệu fallback chưa đúng yêu cầu prompt.

## Cách source hiện tại render và tích hợp

- Frontend: JavaScript thuần, template string + `innerHTML`, không framework, không build step.
- Chart.js: đã có CDN `Chart.js 4.4.1` trong `apps/portal-web/index.html`; không thêm framework hay package frontend mới.
- Chuyển tab: `HQA_MAIN_TABS` + `setHqaMainTab()` + `renderHqa()`.
- Dashboard được render tại `#hqa-dashboard-view`.
- Nút `Refresh data` dùng chung shell HQA; khi ở Dashboard sẽ đồng bộ filter All Listings và tải lại analytics.

## Filter được tái sử dụng từ All Listings

Dashboard lấy từ `state.hqa.allListings.appliedFilters`:

- From date / To date
- Marketplace
- Brand
- Model
- Condition (multi)
- Status (multi)
- Category name (multi)
- Buying option (multi)
- Min price / Max price
- Search keyword

Dashboard không còn form filter dữ liệu riêng. Hai control `Nhóm` và `Kỳ` chỉ thay đổi cách tổng hợp/hiển thị analytics:

- Nhóm: Model (mặc định) / Brand / Category
- Kỳ: Tháng (mặc định) / Tuần

## Field mapping chuẩn

Frontend tập trung tên field ở `DASHBOARD_FIELD_MAP`:

- `listing_id`
- `marketplace`
- `brand`
- `model`
- `category_name`
- `condition`
- `listing_status`
- `price`
- `seller_or_shop`
- `listing_title`
- `quantity`
- `collected_at`
- `research_date`
- `listing_published_at`
- `last_status_checked_at`
- `listing_url`
- `currency`

Backend dùng bảng thật `public.marketplace_research_results`, mốc thời gian Dashboard là `research_date`.

## Dashboard sau chỉnh sửa

1. KPI kỳ mới nhất: Listing phân tích + Unique IDs, Số Model, Người bán, Giá trung vị, Hết hàng + %.
2. Cảnh báo theo từng nhóm và kỳ mới nhất so kỳ trước:
   - Giá giảm mạnh >= 20%, >= 30% là critical.
   - Đáy giá mới thấp hơn mọi kỳ trước.
   - Người bán mới chưa từng xuất hiện ở kỳ trước đó.
   - Hết hàng tăng >= 30 điểm %, >= 50 điểm % là critical.
3. Hai Chart.js multi-series theo nhóm: giá trung bình và số người bán theo kỳ.
4. Drill-down theo nhóm + kỳ:
   - seller, min, median, avg, max, % OOS và delta.
   - P25-P75 range SVG.
   - sparkline 6 kỳ.
   - gợi ý giá: min x 0.97 / median / P75 với logic recommendation theo prompt.
   - Top 10 seller, sort listing desc rồi avg price asc, đánh dấu seller rẻ nhất.
5. CSV BOM UTF-8 tại frontend:
   - group x period summary.
   - alerts.
   - Top 10 seller của nhóm + kỳ đang chọn.
6. Responsive, aria-label cho chart/SVG, phần thiếu dữ liệu hiển thị empty state thay vì lỗi.

## Backend/API bổ sung

Endpoint aggregate mới:

- HQA service: `GET /internal/v1/hqa/dashboard/analysis`
- Portal BFF: `GET /api/v1/hqa/dashboard/analysis`

Một request trả về toàn bộ group x period statistics, alerts, latest-period KPI và Top seller. Cách này dùng dữ liệu thật từ PostgreSQL và tránh phải tải toàn bộ các trang listing về browser chỉ để tính analytics.

## File chỉnh sửa

- `apps/portal-web/assets/app.js`
- `apps/portal-web/assets/styles.css`
- `apps/portal-web/index.html`
- `apps/portal-web/package.json`
- `apps/portal-web/tests/hqa-listing-status-filter.test.js`
- `apps/portal-web/tests/hqa-dashboard-render.test.js`
- `apps/portal-web/tests/hqa-data-check-modal-interaction.test.js` (ổn định timing test bất đồng bộ)
- `apps/portal-bff/app/main.py`
- `services/hqa-service/app/main.py`
- `services/hqa-service/app/service.py`
- `services/hqa-service/tests/test_marketplace_reports_api.py`

## Validation đã chạy

- `npm test` tại `apps/portal-web`: pass, gồm static integration checks, pagination, Dashboard render/interactions và Data Check modal.
- `node --check apps/portal-web/assets/app.js`: pass.
- Toàn bộ `apps/portal-bff/tests`: 14 test pass.
- `python -m compileall` cho HQA service + Portal BFF: pass.
- Direct service test với SQLite attached schema `public`: pass cho group-period metrics và đủ 4 loại alert.
- Toàn bộ `services/hqa-service/tests`: 145 test pass khi bootstrap test DB bằng SQLite; chỉ có 2 warning FastAPI `on_event` deprecation đã tồn tại từ trước.
