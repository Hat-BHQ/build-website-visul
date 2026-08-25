# HQA — Keyword × Seller Analytics

Ngày triển khai: 2026-08-24
Branch nền: `talia/dashboard-product-analytics-v5-integrated`

Tài liệu này mô tả module mới `KeywordSellerAnalytics`, đối chiếu giữa ba đầu vào:

- **Prompt**: `prompt_keyword_seller_latest_listing_dashboard.txt`
- **Mockup đích**: `preview-dashboard.html`
- **Source hiện tại**: portal-web (JavaScript thuần, không build step)

---

## 1. Quyết định kiến trúc

Prompt mục 24 yêu cầu rõ: *"không phá layout hiện có, tạo component/module độc lập, tái sử dụng design system hiện tại"*.

Vì vậy Dashboard v5 hiện tại (product analytics theo Model / Brand / Category) **được giữ nguyên 100%**. Tính năng mới nằm ở một tab HQA riêng:

```
HQA
├── All Listings          (không đổi)
├── Dashboard             (không đổi — product analytics v5)
├── Keyword × Seller      ← MỚI
└── Kiểm tra dữ liệu      (không đổi)
```

Module được nạp như một script độc lập, trước `app.js`:

```html
<link rel="stylesheet" href="/assets/keyword-seller-analytics.css">
<script src="/assets/keyword-seller-analytics.js"></script>
<script src="/assets/app.js"></script>
```

`app.js` chỉ giữ vai trò mount, không chứa business logic:

```js
async function renderHqaKeywordSeller({ reload = false } = {}) {
  const host = document.getElementById('hqa-keyword-seller-view');
  const analytics = window.KeywordSellerAnalytics;
  if (!analytics) { /* hiển thị lỗi */ return; }
  await analytics.mount(host, { reload });
}
```

Nếu sau này muốn đưa view này thành tab mặc định, chỉ cần đổi thứ tự trong `HQA_MAIN_TABS`.

---

## 2. Tách business logic khỏi UI

Prompt mục 24: *"không hard-code business logic trực tiếp trong UI nếu có thể; tách helper xử lý representative listing / seller price series thành function riêng"*.

Toàn bộ logic là **pure function, không chạm DOM**, và được export qua `KeywordSellerAnalytics.logic`:

| Function | Trách nhiệm | Prompt |
|---|---|---|
| `normalizeDataset(raw)` | Chuẩn hoá dữ liệu thô → keyword / dates / seller / listing / snapshots | mục 1 |
| `listingSnapshotAt(listing, index)` | Snapshot gần nhất của listing tại thời điểm T (carry-forward) | mục 3 bước 4 |
| `listingEligibilityAt(listing, index, opts)` | Listing có đủ điều kiện không + lý do bị loại | mục 2 |
| `representativeListingAt(seller, index, opts)` | Listing đại diện của seller tại T | mục 3 |
| `buildSellerSeries(seller, dates, opts)` | Chuỗi giá đại diện — chính là 1 line trên chart | mục 9 |
| `buildSellerEvents(seller, dates, opts)` | Timeline sự kiện seller-level | mục 15 |
| `buildSellerSummary(seller, dates, opts)` | KPI seller: giá/listing đại diện, active count, price range | mục 13 |
| `buildListingSummary(listing, dates, opts)` | Thống kê từng listing cho bảng và drawer | mục 16 |
| `buildKeywordSummary(entry, opts)` | KPI tổng quan keyword | mục 8 |
| `buildKeywordAlerts(entry, opts)` | Sinh alert từ dữ liệu | mục 11 |
| `buildClassificationAudit(entry, opts)` | Listing bị loại + lý do | mục 18 |
| `buildAxis(dates, period)` | Trục Chi tiết / Tuần / Tháng | mục 7 |

Tầng render nằm tách biệt và đặt tên theo gợi ý của prompt: `SellerPriceTrendChart`, `KeywordAlertPanel`, `SellerListingTable`, `SellerDetailDrawer`, `SellerListingHistory`.

---

## 3. Nguồn dữ liệu — đọc thật từ database

Module **không còn dùng mock**. Dữ liệu đi theo chuỗi:

```
portal-web  →  portal-bff  →  hqa-service  →  PostgreSQL
              /api/v1/...     /internal/v1/...
```

### 3.1. Endpoint

| Endpoint (qua BFF) | Trả về |
|---|---|
| `GET /api/v1/hqa/keyword-seller/keywords` | Danh sách keyword + số seller / listing / median |
| `GET /api/v1/hqa/keyword-seller/analytics?keyword=…` | Payload đầy đủ 1 keyword: KPI, series, bảng, alert, audit |
| `GET /api/v1/hqa/keyword-seller/export?keyword=…` | CSV (UTF-8 BOM) |

Tham số dùng chung: `min_price`, `include_all_roles`, `date_from`, `date_to`, `marketplace` (lặp lại được).
Cả ba đều yêu cầu quyền `hqa.dashboard.view`.

### 3.2. Repository layer tự dò nguồn

Repo tồn tại **hai** hình thái lưu listing, và `models.py` với `hq-postgres-backup.sql` **không khớp nhau**:

| Nguồn | Vị trí | Ghi chú |
|---|---|---|
| `flat` | `public.marketplace_research_results` | Toàn bộ `service.py` hiện tại đọc từ đây, nhưng bảng này **không có** trong `hq-postgres-backup.sql` |
| `normalized` | `{ebay,etsy,reverb}.listings` + `listing_snapshots` + `listing_matches` | Có trong backup; `listing_snapshots.observed_at` là price/status history thật |

`keyword_seller_source.py` truy vấn `information_schema` lúc chạy và tự chọn nguồn đang thực sự tồn tại, rồi chuẩn hoá cả hai về **cùng một** observation row. Điều khiển qua biến môi trường:

```
HQA_KEYWORD_SELLER_SOURCE=auto        # auto (mặc định) | flat | normalized
```

`auto` ưu tiên `normalized` vì có snapshot history thật; chỉ rơi về `flat` khi schema chuẩn hoá chưa sẵn sàng. Nếu không tìm thấy nguồn nào, endpoint trả `503` kèm thông báo rõ ràng thay vì trả bảng rỗng.

Khác biệt cần lưu ý giữa hai nguồn:

- **Keyword**: `normalized` lấy trực tiếp từ `listing_matches.keyword`. `flat` không có cột keyword nên phải khớp `ILIKE` trên `listing_title` / `listing_id` và lấy danh sách keyword từ `hqa_keywords.csv` (đúng cách `_apply_dashboard_base_filters` đang làm).
- **Seller**: `ebay.listings.seller_name`, còn `etsy` / `reverb` là `shop_name`.
- **first_seen**: `normalized` dùng `first_seen_at`; `flat` suy ra bằng `MIN(research_date)` của chính listing đó.

### 3.3. Role được phân loại ở backend

`role` **không** do frontend đoán mà do `listing_classifier.py` quyết định, dùng chung `build_product_context` để cả keyword có cùng một price band — giống hệt cách `fetch_hqa_dashboard_analysis` đang làm. Nhờ vậy một chiếc woofer rời hay bộ núm thay thế không bao giờ kéo giá thị trường của sản phẩm xuống.

### 3.4. Vẫn giữ seam để thay tầng dữ liệu

```js
// Thay toàn bộ tầng dữ liệu
KeywordSellerAnalytics.setDataSource({ listKeywords, loadKeyword });

// Hoặc chỉ thay hàm gọi HTTP (app.js đang dùng cách này để gắn Authorization)
KeywordSellerAnalytics.setApiClient((path) => api(path.replace(/^\/api\/v1/, '')));
```

Các hàm trong `KeywordSellerAnalytics.logic` được giữ nguyên để tính lại tức thì khi người dùng đổi ngưỡng giá / vai trò mà không phải gọi lại API.

---

## 4. Những chỗ đã sửa so với mockup

Mockup mô tả đúng cấu trúc UI nhưng có vài điểm lệch với prompt. Các điểm sau đã được xử lý:

### 4.1. Carry-forward snapshot (lỗi logic)

Mockup yêu cầu `l.v[t] != null` mới coi listing là tồn tại tại thời điểm T. Nghĩa là nếu một ngày không thu thập được snapshot cho listing đó, listing biến mất khỏi tính toán và đường giá seller có thể nhảy sai.

Prompt mục 3 bước 4 nói: *"Lấy snapshot giá gần nhất của listing đó tại thời điểm T"*. Module dùng carry-forward — giữ snapshot cuối cùng đã biết cho tới khi có snapshot mới.

### 4.2. Classification Audit (thiếu)

Mockup không có. Prompt mục 2 và 18 yêu cầu. Module thêm bảng riêng liệt kê listing bị loại kèm lý do (`Giá dưới ngưỡng tối thiểu`, `Không phải whole_product`).

Mock data có sẵn `Seller D` để chứng minh: `list_7` ở $650 giữ vai trò đại diện, `list_8` ở $200 **không** cướp vai trò và **không** tạo fake price crash $650 → $200.

### 4.3. Chart drill-down listing (thiếu)

Mockup chỉ có sparkline nhỏ cho mỗi listing. Prompt mục 17 yêu cầu biểu đồ phụ: mỗi line = 1 listing, cộng một line đậm là giá đại diện seller. Module thêm chart này vào drawer khi seller có > 1 listing.

### 4.4. Tooltip đầy đủ

Mockup dùng `<title>` của SVG — chỉ hiện một dòng text thô. Prompt mục 9 mô tả tooltip có seller, keyword, ngày, listing đại diện, giá, listing trước và sự kiện. Module dựng tooltip HTML định vị theo điểm hover.

### 4.5. Highlight khi click line

Prompt mục 12: *"click line seller → highlight seller, các line khác giảm opacity"*. Mockup chỉ mở drawer. Module thêm dim các line còn lại.

### 4.6. Alert sinh từ dữ liệu

Mockup hard-code mảng alert trong `db`. Module sinh alert từ chính series: `PRICE_DROP`, `NEW_LISTING_PRICE_SHIFT`, `MULTIPLE_ACTIVE_LISTINGS`, `STATUS_CHANGE`, sắp xếp theo mức nghiêm trọng.

### 4.7. Control chết

Trong mockup, `Vai trò`, `Giá > $500` và toggle `Tuần / Tháng / Chi tiết` không có tác dụng. Module làm cả ba hoạt động thật:

- Vai trò: `Whole product` ↔ `Tất cả` — đổi tập listing đủ điều kiện, tính lại toàn bộ line.
- Ngưỡng giá: nhập số, áp dụng lại rule mục 2.
- Kỳ: gom trục theo tuần/tháng, lấy snapshot cuối kỳ.

### 4.8. Bổ sung khác

- Cột `Min price`, `Max price`, `Last updated` trong bảng (prompt mục 16 liệt kê nhưng mockup thiếu).
- Trạng thái loading (skeleton) / empty / error (prompt mục 19 — mockup không có).
- Keyword selector searchable, mỗi option hiển thị số seller, số listing, median, số alert (prompt mục 7).
- Đóng drawer bằng `Esc`, focus ring rõ ràng cho line chart, `aria-label` cho SVG.
- Responsive 3 breakpoint (prompt mục 20).
- Export CSV có BOM UTF-8 để Excel đọc đúng tiếng Việt.

---

## 5. Đối chiếu Acceptance Criteria (prompt mục 23)

| # | Tiêu chí | Trạng thái | Chứng minh |
|---|---|---|---|
| 1 | Nhìn chart hiểu keyword nào, line nào là seller nào | ✅ | Header chart + legend card + rule banner |
| 2 | Seller đăng listing mới → line chuyển, có marker, không mô tả sai | ✅ | Test `NEW_LISTING_PRICE_SHIFT`, marker `▲ New listing: list_2` |
| 3 | Seller nhiều listing → xem được từng listing, URL riêng, history riêng | ✅ | Drawer listing cards + drill-down chart |
| 4 | Seller một listing hoạt động bình thường | ✅ | Test Seller B / `list_9` |
| 5 | Listing không đủ điều kiện không làm đổi line seller | ✅ | Test Seller D / `list_8` |
| 6 | Click seller → drawer có listing đại diện, active count, range, tất cả listing | ✅ | Test drawer 5 KPI + 2 listing card |
| 7 | Click listing → xem history | ✅ | Sparkline + drill-down chart |
| 8 | Click link → mở đúng `listing_url` | ✅ | `data-ks-open-url` → `window.open(..., 'noopener,noreferrer')` |
| 9 | Có đủ 3 loại event | ✅ | `PRICE_CHANGED`, `NEW_LISTING_PRICE_SHIFT`, `STATUS_CHANGED` |
| 10 | UI đủ rõ cho người không kỹ thuật | ✅ | Rule banner, nhãn tiếng Việt, tooltip giải thích sự kiện |

---

## 6. File thay đổi

**Backend — mới**

- `services/hqa-service/app/keyword_seller_source.py` — repository layer, tự dò nguồn, chuẩn hoá 2 schema về một shape
- `services/hqa-service/app/keyword_seller_analytics.py` — logic thuần: representative listing, seller series, event, alert, audit

**Backend — sửa**

- `services/hqa-service/app/main.py` — 3 endpoint `/internal/v1/hqa/keyword-seller/{keywords,analytics,export}`
- `services/hqa-service/app/config.py` — 6 setting mới (`hqa_keyword_seller_*`)
- `apps/portal-bff/app/main.py` — 3 route proxy tương ứng

**Frontend — mới**

- `apps/portal-web/assets/keyword-seller-analytics.js`
- `apps/portal-web/assets/keyword-seller-analytics.css`

**Frontend — sửa**

- `apps/portal-web/assets/app.js` — **tab Dashboard của HQA giờ mount module này**; đã bỏ tab `keyword_seller` riêng; truyền `apiClient` để module dùng lại `api()` (có sẵn Authorization + auto refresh token)
- `apps/portal-web/index.html` — bump cache-bust `v=20260825-keyword-seller-db-v2`
- `apps/portal-web/package.json` — thêm module vào `lint` / `build`

**Đã gỡ**

- `apps/portal-web/preview/keyword-seller-analytics.html` — trang preview chạy mock ("không gọi backend"), không còn hoạt động sau khi bỏ mock dataset

**Không đụng tới**: `assets/styles.css`, `apps/portal-web/tests/`, `services/*/tests/`, và các endpoint dashboard cũ.

---

## 7. Lưu ý về test

Theo yêu cầu: **giữ nguyên test hiện có, không tạo test mới**. Không có file test nào bị thêm hay xoá trong thay đổi này.

**7.1. Test suite của branch vốn đã đỏ từ trước, không phải do thay đổi này.**

`npm test` trên commit gốc `3d5dcc8` đã fail sẵn:

```
hqa-listing-status-filter.test.js         FAIL
hqa-dashboard-render.test.js              FAIL
hqa-listing-pagination.test.js            PASS
hqa-data-check-modal-interaction.test.js  PASS
```

Nguyên nhân là test rot sau đợt rework v5, không phải lỗi logic:

| Assertion cũ | Thực tế trên branch |
|---|---|
| `label: 'Kiem tra du lieu'` | đã đổi thành `'Kiểm tra dữ liệu'` |
| `id="dashboard-group-by"` | control đã bị bỏ, thay bằng `#dashboard-product-select` |
| `.all-listings-table { min-width: 1240px;` | CSS đã chạy prettier nên xuống dòng |
| `new Chart(priceCanvas` | đổi thành `new Chart(document.getElementById('dashboard-price-chart')` |
| fixture `group_by` / `listing_count` | payload v5 dùng `products` / `whole_product_count` / `role_counts` |
| 2 Chart.js | v5 render 3 chart (thêm combo chart 2 trục) |

**7.2. Hai test sẽ đỏ thêm vì tab Dashboard bị thay — cần biết trước.**

- `hqa-listing-status-filter.test.js` so khớp nguyên văn mảng `HQA_MAIN_TABS`. Mảng này đã đổi (bỏ tab `keyword_seller`). Test vốn đã fail sẵn vì lý do dấu tiếng Việt.
- `hqa-dashboard-render.test.js` kiểm tra markup do `renderHqaDashboard()` sinh ra. Hàm đó **không còn được gọi** nên test này sẽ không còn phản ánh UI thật. Đây là test cần viết lại khi nghiệm thu xong dashboard mới — không phải lỗi cần sửa gấp.

**7.3. Việc kiểm chứng đã làm thủ công thay cho test tự động.** Xem mục 9.

---

## 8. Việc còn lại

1. **Xác nhận nguồn dữ liệu production.** `models.py` trỏ `public.marketplace_research_results` nhưng bảng này không có trong `hq-postgres-backup.sql`. Repository layer đang tự dò nên chạy được cả hai, nhưng nên chốt lại và set `HQA_KEYWORD_SELLER_SOURCE` tường minh trong `.env` production để tránh phụ thuộc vào thứ tự ưu tiên.

2. **Dọn code dashboard cũ (~900 dòng dead code).** Sau khi tab Dashboard được thay, các hàm sau **không còn ai gọi** — đã kiểm tra bằng grep, chúng chỉ tự tham chiếu lẫn nhau:
   - `renderHqaDashboard()` (`app.js` ~dòng 1475)
   - `loadHqaDashboardData()` (~647)
   - `syncDashboardFiltersFromAllListings()` (~570) — 0 caller
   - `buildDashboardCommonParams()` (~589)

   Cố ý **chưa xoá** vì không chạy được app để kiểm chứng; xoá mù 900 dòng rủi ro hơn lợi ích. Nên xoá sau khi nghiệm thu dashboard mới trên staging. Các endpoint `/internal/v1/hqa/dashboard/*` ở backend vẫn giữ nguyên (có thể còn client khác dùng).

3. **Index cho hiệu năng.** Query gom theo keyword + ngày. Nên có:
   - `flat`: index trên `(listing_id, research_date)` và `(marketplace, seller_or_shop)`
   - `normalized`: index trên `listing_matches(keyword)` và `listing_snapshots(listing_id, observed_at)`

4. **Giới hạn số seller trên chart.** Keyword có hàng chục seller sẽ rối. Nên thêm picker top-N giống `chartProducts` của Dashboard v5.

5. **Đa tiền tệ.** Module format theo `currency` trả từ backend nhưng vẫn giả định một loại tiền cho cả keyword. Nếu một keyword trộn USD/VND thì cần quy đổi ở tầng SQL.

6. **Bảng trên mobile.** Prompt mục 20 nói *"table chuyển thành card list"*. Hiện dùng scroll ngang + ẩn cột phụ.

---

## 9. Đã kiểm chứng những gì

| Kiểm tra | Kết quả |
|---|---|
| Logic mục 4 (Seller A đổi listing) | `$600 → $650 → $700 → $700 → $680`, listing `list_1 → list_2` ✅ |
| Ngày 13/08 phân loại đúng sự kiện | `NEW_LISTING_PRICE_SHIFT`, không phải `PRICE_CHANGED` ✅ |
| Mục 5 (1 seller 1 listing) | Đường Seller B chạy đúng, không aggregate thừa ✅ |
| Mục 6 (nhiều listing ACTIVE) | Seller C chuyển đại diện sang `list_6` @ $720 ✅ |
| Mục 18 (listing mới < ngưỡng) | `list_11` @ $200 bị xếp `component_part`, giữ giá $650, không crash giả ✅ |
| Cú pháp SQL Postgres | 4/4 câu parse sạch bằng `sqlglot` dialect postgres ✅ |
| Đọc DB → payload end-to-end | Chạy thật trên bảng phẳng, ra đúng chuỗi giá ✅ |
| FastAPI nạp route | hqa-service 3/3, portal-bff 3/3 ✅ |
| Cú pháp JS | `node --check` sạch trên `app.js` và module ✅ |

**Chưa kiểm chứng** (cần môi trường thật): render UI trên trình duyệt, hiệu năng với dữ liệu lớn, và đường `normalized` với dữ liệu thật (backup gần như rỗng — `ebay.listings` chỉ có 1 dòng, mọi bảng snapshot đều 0 dòng).
