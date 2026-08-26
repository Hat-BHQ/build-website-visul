/*
 * KeywordSellerAnalytics - dashboard-v2 FIX
 * ================================================================
 * 1 chart = 1 keyword
 * 1 line  = 1 seller
 * Seller representative price = latest snapshot of the newest eligible listing.
 *
 * UI fixes in this version:
 * - searchable single-select keyword picker + clickable keyword cards
 * - keyword cards in one horizontal scrolling row
 * - default period = latest ISO week; latest month; lifecycle
 * - period-aware seller deltas / alerts / overview
 * - alert list vertical scroll aligned with chart height
 * - seller cards one horizontal scrolling row
 * - semantic colors are documented in COLOR_SEMANTICS
 * - pencil loading animation restored
 * - new-listing positive shift is informational, not critical
 * - no fallback-to-first-keyword bug when metadata for another keyword is not loaded
 */
(function (global) {
  'use strict';

  var CONFIG = {
    minPrice: 500,
    currency: 'USD',
    keywordCardLimit: 30,
    maxChartSellers: 12,
    eligibleRoles: ['whole_product'],
    priceDropWarningPct: 20,
    priceDropCriticalPct: 30,
    multipleActiveThreshold: 2,
    periods: [
      { key: 'week', label: 'Tuần gần nhất' },
      { key: 'month', label: 'Tháng gần nhất' },
      { key: 'lifecycle', label: 'Vòng đời listing' },
    ],
    sellerColors: [
      '#f97316', '#2563eb', '#7c3aed', '#0891b2', '#c026d3', '#0f766e',
      '#b45309', '#475569', '#4f46e5', '#0284c7', '#9333ea', '#0d9488',
    ],
  };

  // IMPORTANT FOR DOCUMENTATION:
  // Seller line colors are CATEGORICAL only: they distinguish sellers and do not
  // mean good/bad. Semantic status/change colors are defined below.
  var COLOR_SEMANTICS = {
    sellerLine: 'Màu định danh seller, không mang ý nghĩa tăng/giảm',
    green: 'Giá giảm / ACTIVE / trạng thái tích cực',
    red: 'Giá tăng hoặc cảnh báo nghiêm trọng / OUT_OF_STOCK',
    amber: 'Cảnh báo cần theo dõi',
    blue: 'Thông tin / lịch sử',
    orange: 'Listing đại diện mới / điểm chuyển listing',
    gray: 'Không đổi / trung tính / ENDED',
  };

  var EVENT = {
    TRACKING_STARTED: 'TRACKING_STARTED',
    PRICE_CHANGED: 'PRICE_CHANGED',
    NEW_LISTING_PRICE_SHIFT: 'NEW_LISTING_PRICE_SHIFT',
    STATUS_CHANGED: 'STATUS_CHANGED',
  };

  var API_BASE = '/api/v1/hqa/keyword-seller';

  // =========================================================================
  // FILTER 2 MODE LOAI TRU NHAU
  //   brand_model : Brand + Model  (Keyword bi disable)
  //   keyword     : Keyword        (Brand + Model bi disable)
  // Condition / Min price / Period luon kha dung o ca 2 mode.
  // =========================================================================
  var FILTER_MODE = { BRAND_MODEL: 'brand_model', KEYWORD: 'keyword' };
  var OPTION_PAGE_SIZE = 30;
  var OPTION_SEARCH_DEBOUNCE_MS = 320;

  // apiField = ten field gui len /keyword-seller/filter-options.
  // mode = '' nghia la field khong bi rang buoc boi mode nao.
  var FILTER_FIELDS = {
    brand: { apiField: 'brand', label: 'Brand', placeholder: 'Tất cả brand', mode: FILTER_MODE.BRAND_MODEL },
    model: { apiField: 'model', label: 'Model', placeholder: 'Tất cả model', mode: FILTER_MODE.BRAND_MODEL },
    keyword: { apiField: 'keyword', label: 'Keyword', placeholder: 'Chọn keyword', mode: FILTER_MODE.KEYWORD },
    condition: { apiField: 'condition', label: 'Condition', placeholder: 'Tất cả condition', mode: '' },
  };
  var FILTER_FIELD_ORDER = ['brand', 'model', 'keyword', 'condition'];

  var globalListenersBound = false;

  function defaultLazyOptionState() {
    return {
      items: [], page: 0, pageSize: OPTION_PAGE_SIZE, hasMore: true,
      isLoading: false, isLoaded: false, search: '', error: '',
      requestId: 0, controller: null,
    };
  }

  function defaultOptionStates() {
    var states = {};
    FILTER_FIELD_ORDER.forEach(function (field) { states[field] = defaultLazyOptionState(); });
    return states;
  }

  var view = {
    host: null,
    apiClient: null,

    // --- scope ---
    filterMode: FILTER_MODE.BRAND_MODEL,
    brand: '',
    model: '',
    keyword: '',
    condition: '',
    minPrice: CONFIG.minPrice,
    period: 'week',
    // Backend luon chay role=whole_product (business rule co dinh),
    // nen role khong xuat hien tren toolbar.
    role: 'whole_product',

    // --- dropdown ---
    openFilterField: '',
    optionStates: defaultOptionStates(),
    optionCache: {},
    optionSearchTimers: {},

    // --- du lieu ---
    keywordOptions: [],
    keywordOptionsLoaded: false,
    cache: {},

    loading: false,
    error: '',
    optionsError: '',
    selectedSeller: '',
    expandedSeller: '',
    destroyed: false,
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatCurrency(value, currency) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '—';
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency', currency: currency || CONFIG.currency, maximumFractionDigits: 0,
      }).format(n);
    } catch (_) {
      return '$' + Math.round(n).toLocaleString('en-US');
    }
  }

  function formatPercent(value, digits) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return n.toFixed(digits == null ? 1 : digits) + '%';
  }

  function formatCount(value) {
    return Number(value || 0).toLocaleString('en-US');
  }

  function normalizeDate(value) {
    if (!value) return '';
    return String(value).slice(0, 10);
  }

  function parseDate(value) {
    var iso = normalizeDate(value);
    var date = new Date(iso + 'T00:00:00Z');
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatDayMonth(value) {
    var iso = normalizeDate(value);
    var parts = iso.split('-');
    return parts.length === 3 ? parts[2] + '/' + parts[1] : iso;
  }

  function median(values) {
    var clean = (values || []).map(Number).filter(Number.isFinite).sort(function (a, b) { return a - b; });
    if (!clean.length) return null;
    var m = Math.floor(clean.length / 2);
    return clean.length % 2 ? clean[m] : (clean[m - 1] + clean[m]) / 2;
  }

  function percentChange(current, previous) {
    var c = Number(current); var p = Number(previous);
    if (!Number.isFinite(c) || !Number.isFinite(p) || p === 0) return null;
    return ((c - p) / p) * 100;
  }

  function sameMonth(a, b) {
    return normalizeDate(a).slice(0, 7) === normalizeDate(b).slice(0, 7);
  }

  function isoWeekStart(value) {
    var date = parseDate(value);
    if (!date) return null;
    var day = date.getUTCDay();
    var diff = day === 0 ? -6 : 1 - day;
    var start = new Date(date);
    start.setUTCDate(date.getUTCDate() + diff);
    return start;
  }

  function dateInLatestWeek(value, latest) {
    var date = parseDate(value); var start = isoWeekStart(latest);
    if (!date || !start) return false;
    var end = new Date(start); end.setUTCDate(start.getUTCDate() + 7);
    return date >= start && date < end;
  }

  function uniqueSortedDates(values) {
    var seen = {};
    (values || []).forEach(function (value) {
      var d = normalizeDate(value);
      if (d) seen[d] = true;
    });
    return Object.keys(seen).sort();
  }

  function windowDates(allDates, period) {
    var dates = uniqueSortedDates(allDates);
    if (!dates.length || period === 'lifecycle') return dates;
    var latest = dates[dates.length - 1];
    if (period === 'month') return dates.filter(function (d) { return sameMonth(d, latest); });
    return dates.filter(function (d) { return dateInLatestWeek(d, latest); });
  }

  function periodDescription(allDates, period) {
    var visible = windowDates(allDates, period);
    if (!visible.length) return 'Không có dữ liệu thời gian.';
    if (period === 'lifecycle') return 'Vòng đời listing: ' + visible[0] + ' → ' + visible[visible.length - 1]
      + ' · mốc bắt đầu ưu tiên ngày đăng; giá chỉ hiển thị từ snapshot đầu tiên.';
    if (period === 'month') return 'Tháng gần nhất có dữ liệu: ' + visible[visible.length - 1].slice(0, 7);
    var start = isoWeekStart(visible[visible.length - 1]);
    var end = new Date(start); end.setUTCDate(start.getUTCDate() + 6);
    var fmt = function (d) { return d.toISOString().slice(0, 10); };
    return 'Tuần ISO gần nhất có dữ liệu: ' + fmt(start) + ' → ' + fmt(end);
  }

  function severityRank(value) {
    return value === 'critical' ? 0 : (value === 'warning' ? 1 : 2);
  }

  function semanticChangeClass(change) {
    var n = Number(change);
    if (!Number.isFinite(n) || Math.abs(n) < 0.0001) return 'ks-change--flat';
    return n < 0 ? 'ks-change--down' : 'ks-change--up';
  }

  function semanticChangeMarkup(change) {
    var n = Number(change);
    if (!Number.isFinite(n) || Math.abs(n) < 0.0001) return '<span class="ks-change ks-change--flat">±0%</span>';
    return '<span class="ks-change ' + semanticChangeClass(n) + '">' + (n < 0 ? '▼' : '▲') + ' ' + formatPercent(Math.abs(n)) + '</span>';
  }

  function keywordFromPayload(payload) {
    if (!payload) return null;
    return {
      keyword: payload.keyword || '',
      currency: payload.currency || CONFIG.currency,
      axis: uniqueSortedDates(payload.axis || []),
      lifecycleAxis: uniqueSortedDates(payload.lifecycle_axis || payload.axis || []),
      summary: payload.summary || {},
      sellers: payload.sellers || [],
      series: payload.series || [],
      alerts: payload.alerts || [],
      audit: payload.audit || [],
      source: payload.source || '',
      minPrice: Number(payload.min_price == null ? CONFIG.minPrice : payload.min_price),
    };
  }

  function axisForPeriod(payload, period) {
    if (period === 'lifecycle' && payload && payload.lifecycleAxis && payload.lifecycleAxis.length) {
      return payload.lifecycleAxis;
    }
    return payload && payload.axis ? payload.axis : [];
  }

  // FIX: old code returned keywords[0] when keyword was not found. That made every
  // card display the selected keyword's 172 sellers / 397 listings / 37 alerts.
  function findKeyword(cache, keyword) {
    if (!keyword) return null;
    return cache && Object.prototype.hasOwnProperty.call(cache, keyword) ? cache[keyword] : null;
  }

  function findSeller(payload, sellerName) {
    return (payload && payload.sellers || []).find(function (item) { return item.seller === sellerName; }) || null;
  }

  function seriesForSeller(payload, sellerName) {
    return (payload && payload.series || []).find(function (item) { return item.seller === sellerName; }) || null;
  }

  function visiblePoints(payload, sellerName, period) {
    var allowed = new Set(windowDates(axisForPeriod(payload, period), period));
    var series = seriesForSeller(payload, sellerName);
    return (series && series.points || [])
      .map(function (point) {
        return Object.assign({}, point, { date: normalizeDate(point.date) });
      })
      .filter(function (point) { return point.date && allowed.has(point.date) && Number.isFinite(Number(point.price)); });
  }

  function firstAndLast(points) {
    if (!points || !points.length) return { first: null, last: null };
    return { first: points[0], last: points[points.length - 1] };
  }

  function currentListingStatusCounts(payload) {
    var counts = { active: 0, out: 0, ended: 0 };
    (payload.sellers || []).forEach(function (seller) {
      (seller.listings || []).forEach(function (listing) {
        if (!listing.eligible) return;
        var status = String(listing.status || '').toUpperCase();
        if (status === 'ACTIVE' || status === 'NEW_LISTING') counts.active += 1;
        else if (status === 'OUT_OF_STOCK') counts.out += 1;
        else if (status === 'ENDED') counts.ended += 1;
      });
    });
    return counts;
  }

  function buildSellerRows(payload, period) {
    return (payload.sellers || []).map(function (seller) {
      var points = visiblePoints(payload, seller.seller, period);
      var endpoints = firstAndLast(points);
      var last = endpoints.last;
      var change = endpoints.first && last ? percentChange(last.price, endpoints.first.price) : null;
      return {
        seller: seller.seller,
        points: points,
        changePct: change,
        representativeListingId: last ? last.listing_id : seller.representative_listing_id,
        representativePrice: last ? Number(last.price) : Number(seller.representative_price),
        representativeStatus: last ? last.status : '',
        activeListingCount: Number(seller.active_listing_count || 0),
        totalListingCount: Number(seller.total_listing_count || (seller.listings || []).length || 0),
        activePriceMin: seller.active_price_min,
        activePriceMax: seller.active_price_max,
        listings: seller.listings || [],
        events: seller.events || [],
        raw: seller,
      };
    }).filter(function (row) { return Number.isFinite(row.representativePrice); });
  }

  function eventInsideWindow(event, visibleDates, period) {
    if (!event || !event.date || !visibleDates.length) return false;
    if (period === 'lifecycle') return true;
    var date = normalizeDate(event.date);
    return date >= visibleDates[0] && date <= visibleDates[visibleDates.length - 1];
  }

  function classifyEventAlert(event, sellerName) {
    var type = String(event.type || '').toUpperCase();
    var change = Number(event.change_pct != null ? event.change_pct : event.changePct);
    var oldPrice = event.previous_price != null ? event.previous_price : event.previousPrice;
    var newPrice = event.price;
    var oldListing = event.previous_listing_id != null ? event.previous_listing_id : event.previousListingId;
    var newListing = event.listing_id != null ? event.listing_id : event.listingId;

    if (type === EVENT.PRICE_CHANGED) {
      if (!Number.isFinite(change)) return null;
      if (change < 0 && Math.abs(change) >= CONFIG.priceDropWarningPct) {
        return {
          severity: Math.abs(change) >= CONFIG.priceDropCriticalPct ? 'critical' : 'warning',
          type: type, seller: sellerName, date: normalizeDate(event.date), changePct: change,
          title: sellerName + ' giảm giá listing',
          detail: (newListing || '') + ': ' + formatCurrency(oldPrice) + ' → ' + formatCurrency(newPrice),
        };
      }
      if (change > 0 && change >= CONFIG.priceDropWarningPct) {
        return {
          severity: 'info', type: type, seller: sellerName, date: normalizeDate(event.date), changePct: change,
          title: sellerName + ' tăng giá listing',
          detail: (newListing || '') + ': ' + formatCurrency(oldPrice) + ' → ' + formatCurrency(newPrice),
        };
      }
      return null;
    }

    if (type === EVENT.NEW_LISTING_PRICE_SHIFT) {
      var severity = 'info';
      if (Number.isFinite(change) && change < 0 && Math.abs(change) >= CONFIG.priceDropWarningPct) {
        severity = Math.abs(change) >= CONFIG.priceDropCriticalPct ? 'critical' : 'warning';
      }
      return {
        severity: severity, type: type, seller: sellerName, date: normalizeDate(event.date), changePct: change,
        title: sellerName + ' đăng listing mới',
        detail: 'Listing cũ ' + (oldListing || '—') + ' ' + formatCurrency(oldPrice)
          + ' → listing mới ' + (newListing || '—') + ' ' + formatCurrency(newPrice)
          + '. Đây là đổi listing đại diện, không phải listing cũ tăng/giảm giá.',
      };
    }

    if (type === EVENT.STATUS_CHANGED) {
      var status = String(event.status || '').toUpperCase();
      if (status === 'ACTIVE' || status === 'NEW_LISTING') return null;
      return {
        severity: status === 'OUT_OF_STOCK' ? 'warning' : 'info', type: type, seller: sellerName,
        date: normalizeDate(event.date), changePct: null,
        title: sellerName + ': ' + (status || 'đổi trạng thái'),
        detail: (event.previous_status || event.previousStatus || '—') + ' → ' + (status || '—'),
      };
    }
    return null;
  }

  function buildPeriodAlerts(payload, period) {
    var visible = windowDates(axisForPeriod(payload, period), period);
    var alerts = [];
    (payload.sellers || []).forEach(function (seller) {
      (seller.events || []).forEach(function (event) {
        if (!eventInsideWindow(event, visible, period)) return;
        var alert = classifyEventAlert(event, seller.seller);
        if (alert) alerts.push(alert);
      });
      if (Number(seller.active_listing_count || 0) >= CONFIG.multipleActiveThreshold) {
        alerts.push({
          severity: 'info', type: 'MULTIPLE_ACTIVE_LISTINGS', seller: seller.seller,
          date: visible[visible.length - 1] || '', changePct: null,
          title: seller.seller + ' có nhiều listing ACTIVE',
          detail: formatCount(seller.active_listing_count) + ' listing ACTIVE · khoảng giá '
            + formatCurrency(seller.active_price_min) + ' – ' + formatCurrency(seller.active_price_max),
        });
      }
    });

    // Deduplicate by seller + type + date + detail.
    var seen = {};
    alerts = alerts.filter(function (item) {
      var key = [item.seller, item.type, item.date, item.detail].join('@@');
      if (seen[key]) return false;
      seen[key] = true; return true;
    });
    alerts.sort(function (a, b) {
      var rank = severityRank(a.severity) - severityRank(b.severity);
      if (rank !== 0) return rank;
      return String(b.date || '').localeCompare(String(a.date || ''));
    });
    return alerts;
  }

  function buildOverview(payload, period) {
    var sellers = buildSellerRows(payload, period);
    var prices = sellers.map(function (row) { return row.representativePrice; }).filter(Number.isFinite);
    var eligibleListings = 0;
    var multiListing = 0;
    (payload.sellers || []).forEach(function (seller) {
      var eligible = (seller.listings || []).filter(function (listing) { return !!listing.eligible; });
      eligibleListings += eligible.length;
      if (Number(seller.total_listing_count || (seller.listings || []).length) > 1) multiListing += 1;
    });
    var counts = currentListingStatusCounts(payload);
    var falling = sellers.filter(function (row) { return Number(row.changePct) < -0.0001; }).length;
    var rising = sellers.filter(function (row) { return Number(row.changePct) > 0.0001; }).length;
    var alerts = buildPeriodAlerts(payload, period);

    var firstPrices = sellers.map(function (row) {
      var endpoints = firstAndLast(row.points);
      return endpoints.first ? Number(endpoints.first.price) : null;
    }).filter(Number.isFinite);
    var firstMedian = median(firstPrices);
    var currentMedian = median(prices);
    var medianChange = percentChange(currentMedian, firstMedian);

    var minSeller = sellers.slice().sort(function (a, b) { return a.representativePrice - b.representativePrice; })[0] || null;
    var maxSeller = sellers.slice().sort(function (a, b) { return b.representativePrice - a.representativePrice; })[0] || null;

    return {
      sellers: sellers,
      sellerCount: sellers.length,
      eligibleListingCount: eligibleListings,
      medianPrice: currentMedian,
      minPrice: prices.length ? Math.min.apply(null, prices) : null,
      maxPrice: prices.length ? Math.max.apply(null, prices) : null,
      activeListings: counts.active,
      outOfStock: counts.out,
      ended: counts.ended,
      multiListingSellerCount: multiListing,
      fallingSellerCount: falling,
      risingSellerCount: rising,
      alerts: alerts,
      alertCount: alerts.length,
      firstMedian: firstMedian,
      medianChangePct: medianChange,
      minSeller: minSeller,
      maxSeller: maxSeller,
      visibleDates: windowDates(axisForPeriod(payload, period), period),
    };
  }

  function chooseChartSellers(overview) {
    var rows = overview.sellers.slice();
    rows.sort(function (a, b) {
      return Math.abs(Number(b.changePct || 0)) - Math.abs(Number(a.changePct || 0));
    });
    var selected = rows.slice(0, CONFIG.maxChartSellers);
    function add(row) {
      if (!row || selected.some(function (item) { return item.seller === row.seller; })) return;
      if (selected.length >= CONFIG.maxChartSellers) selected[selected.length - 1] = row;
      else selected.push(row);
    }
    add(overview.minSeller); add(overview.maxSeller);
    return selected;
  }

  function buildInsights(payload, overview) {
    var insights = [];
    if (overview.medianChangePct != null) {
      var direction = Math.abs(overview.medianChangePct) < 0.05 ? 'gần như đi ngang'
        : (overview.medianChangePct < 0 ? 'giảm' : 'tăng');
      insights.push({
        tone: overview.medianChangePct < 0 ? 'good' : (overview.medianChangePct > 0 ? 'bad' : 'neutral'),
        text: 'Median giá đại diện ' + direction + ' ' + formatPercent(Math.abs(overview.medianChangePct)) + ' trong phạm vi đang xem.',
      });
    }
    if (overview.minSeller) insights.push({ tone: 'good', text: overview.minSeller.seller + ' đang có giá đại diện thấp nhất: ' + formatCurrency(overview.minSeller.representativePrice) + '.' });
    if (overview.maxSeller) insights.push({ tone: 'bad', text: overview.maxSeller.seller + ' đang có giá đại diện cao nhất: ' + formatCurrency(overview.maxSeller.representativePrice) + '.' });
    if (overview.multiListingSellerCount) insights.push({ tone: 'info', text: formatCount(overview.multiListingSellerCount) + ' seller có nhiều hơn 1 listing; click seller để đối chiếu các URL/listing song song.' });
    if (overview.fallingSellerCount || overview.risingSellerCount) insights.push({ tone: 'info', text: formatCount(overview.fallingSellerCount) + ' seller giảm giá và ' + formatCount(overview.risingSellerCount) + ' seller tăng giá trong phạm vi đang xem.' });
    if (overview.outOfStock || overview.ended) insights.push({ tone: 'warn', text: formatCount(overview.outOfStock) + ' listing OUT_OF_STOCK và ' + formatCount(overview.ended) + ' listing ENDED ở trạng thái mới nhất.' });
    if (!insights.length) insights.push({ tone: 'neutral', text: 'Chưa đủ dữ liệu biến động để đưa ra nhận định nhanh cho keyword này.' });
    return insights.slice(0, 6);
  }

  function queryString(params) {
    var q = new URLSearchParams();
    Object.keys(params || {}).forEach(function (key) {
      var value = params[key];
      if (value !== '' && value != null) q.set(key, String(value));
    });
    return q.toString();
  }

  async function api(path, options) {
    if (!view.apiClient) throw new Error('KeywordSellerAnalytics chưa nhận apiClient.');
    return view.apiClient(path, options);
  }

  // =========================================================================
  // SCOPE HELPERS
  // =========================================================================

  function isKeywordMode() {
    return view.filterMode === FILTER_MODE.KEYWORD;
  }

  // Condition khong bi disable khi doi mode; Brand/Model va Keyword thi co.
  function isFieldEnabled(field) {
    var config = FILTER_FIELDS[field];
    if (!config) return false;
    if (!config.mode) return true;
    return config.mode === view.filterMode;
  }

  function scopeLabel() {
    if (isKeywordMode()) return view.keyword || '';
    return [view.brand, view.model].filter(Boolean).join(' ');
  }

  function scopeIsComplete() {
    return isKeywordMode() ? !!view.keyword : !!(view.brand || view.model);
  }

  function scopeHint() {
    return isKeywordMode() ? 'Vui lòng chọn Keyword.' : 'Vui lòng chọn Brand hoặc Model.';
  }

  // Cache key phai mang TOAN BO scope, khong duoc cache[keyword] nhu ban cu.
  // Period co chu dich KHONG nam trong key: payload tra ve la lifecycle day du,
  // viec cat theo tuan/thang duoc tinh client-side trong buildOverview(), nen
  // doi period khong lam thay doi du lieu tra ve tu backend.
  function analyticsCacheKey() {
    return [
      view.filterMode,
      view.brand || '',
      view.model || '',
      view.keyword || '',
      view.condition || '',
      view.minPrice,
    ].join('@@');
  }

  function findAnalytics() {
    var key = analyticsCacheKey();
    return Object.prototype.hasOwnProperty.call(view.cache, key) ? view.cache[key] : null;
  }

  function analyticsParams() {
    var params = {
      filter_mode: view.filterMode,
      min_price: view.minPrice,
      include_all_roles: view.role === 'all' ? 'true' : 'false',
    };
    // Khong bao gio gui filter cua mode dang khong active.
    if (isKeywordMode()) {
      params.keyword = view.keyword;
    } else {
      if (view.brand) params.brand = view.brand;
      if (view.model) params.model = view.model;
    }
    if (view.condition) params.condition = view.condition;
    return params;
  }

  function analyticsPath() {
    return API_BASE + '/analytics?' + queryString(analyticsParams());
  }

  function exportPath() {
    return API_BASE + '/export?' + queryString(analyticsParams());
  }

  function keywordCardsPath() {
    return API_BASE + '/keywords?' + queryString({
      min_price: view.minPrice,
      limit: CONFIG.keywordCardLimit,
      condition: view.condition || '',
    });
  }

  function filterOptionsPath(field, page, search) {
    var params = {
      field: FILTER_FIELDS[field].apiField,
      page: page,
      page_size: OPTION_PAGE_SIZE,
    };
    if (search) params.search = search;
    // Model phu thuoc Brand: chi gui brand khi dang lay option cua model.
    if (field === 'model' && view.brand) params.brand = view.brand;
    return API_BASE + '/filter-options?' + queryString(params);
  }

  // =========================================================================
  // LAZY OPTION LOADER (cung pattern voi All Listings trong app.js)
  // =========================================================================

  function normalizeOptionValue(value) {
    return String(value == null ? '' : value).trim();
  }

  function buildLazyOptionCacheKey(field) {
    var fieldState = view.optionStates[field] || defaultLazyOptionState();
    var search = normalizeOptionValue(fieldState.search).toLowerCase();
    // Model phai co brand trong cache key, neu khong se tra option sai scope.
    if (field === 'model') {
      return 'model|brand=' + normalizeOptionValue(view.brand).toLowerCase() + '|search=' + search;
    }
    return field + '|search=' + search;
  }

  function clearLazyOptionCache(field) {
    Object.keys(view.optionCache).forEach(function (key) {
      if (key.indexOf(field + '|') === 0) delete view.optionCache[key];
    });
  }

  function abortOptionRequest(field) {
    var fieldState = view.optionStates[field];
    if (fieldState && fieldState.controller) {
      try { fieldState.controller.abort(); } catch (_) { /* no-op */ }
    }
  }

  function resetLazyOptionField(field, options) {
    var opts = options || {};
    abortOptionRequest(field);
    if (view.optionSearchTimers[field]) {
      clearTimeout(view.optionSearchTimers[field]);
      delete view.optionSearchTimers[field];
    }
    view.optionStates[field] = defaultLazyOptionState();
    if (opts.clearCache) clearLazyOptionCache(field);
  }

  function mergeOptionItems(existingItems, incomingItems) {
    var merged = [];
    var seen = {};
    (existingItems || []).concat(incomingItems || []).forEach(function (item) {
      var value = normalizeOptionValue(item && item.value != null ? item.value : item);
      if (!value) return;
      var key = value.toLowerCase();
      if (seen[key]) return;
      seen[key] = true;
      merged.push({ value: value, label: normalizeOptionValue(item && item.label) || value });
    });
    return merged;
  }

  async function loadLazyOptionField(field, options) {
    var opts = options || {};
    var reset = !!opts.reset;
    var useCache = opts.useCache !== false;

    if (!FILTER_FIELDS[field] || !isFieldEnabled(field)) return;

    var fieldState = view.optionStates[field];
    if (!fieldState || fieldState.isLoading) return;

    var cacheKey = buildLazyOptionCacheKey(field);
    if (reset && useCache && view.optionCache[cacheKey]) {
      var cached = view.optionCache[cacheKey];
      view.optionStates[field] = Object.assign({}, fieldState, {
        items: cached.items.slice(),
        page: cached.page,
        hasMore: cached.hasMore,
        isLoaded: true,
        isLoading: false,
        error: '',
        controller: null,
      });
      return;
    }

    if (!reset && !fieldState.hasMore) return;
    var targetPage = reset ? 1 : fieldState.page + 1;

    // Abort request cu de response cu khong ghi de response moi.
    abortOptionRequest(field);
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var requestId = fieldState.requestId + 1;

    view.optionStates[field] = Object.assign({}, fieldState, {
      isLoading: true, error: '', requestId: requestId, controller: controller,
    });

    var search = normalizeOptionValue(fieldState.search);

    try {
      var payload = await api(
        filterOptionsPath(field, targetPage, search),
        controller ? { signal: controller.signal } : undefined
      );

      var currentState = view.optionStates[field];
      if (!currentState || currentState.requestId !== requestId) return;

      var incoming = ((payload && payload.items) || []).map(function (item) {
        return {
          value: normalizeOptionValue(item && item.value != null ? item.value : item),
          label: normalizeOptionValue((item && (item.label || item.value)) || item),
        };
      }).filter(function (item) { return !!item.value; });

      var nextItems = reset ? incoming : mergeOptionItems(currentState.items, incoming);
      var nextState = Object.assign({}, currentState, {
        items: nextItems,
        page: Number((payload && payload.page) || targetPage),
        hasMore: Boolean(payload && payload.has_more),
        isLoaded: true,
        isLoading: false,
        error: '',
        controller: null,
      });

      view.optionStates[field] = nextState;
      view.optionCache[cacheKey] = {
        items: nextState.items.slice(),
        page: nextState.page,
        hasMore: nextState.hasMore,
      };
    } catch (error) {
      if (error && error.name === 'AbortError') return;
      var failedState = view.optionStates[field];
      if (!failedState || failedState.requestId !== requestId) return;
      view.optionStates[field] = Object.assign({}, failedState, {
        isLoading: false,
        error: 'Không tải được danh sách. Thử lại.',
        controller: null,
      });
    }
  }

  function debounceLazyOptionSearch(field, value) {
    if (view.optionSearchTimers[field]) clearTimeout(view.optionSearchTimers[field]);
    view.optionSearchTimers[field] = setTimeout(async function () {
      var fieldState = view.optionStates[field];
      if (!fieldState) return;
      // Search moi: reset page/items/hasMore truoc khi goi lai.
      view.optionStates[field] = Object.assign({}, fieldState, {
        search: normalizeOptionValue(value),
        items: [], page: 0, hasMore: true, isLoaded: false, error: '',
      });
      await loadLazyOptionField(field, { reset: true, useCache: true });
      updateFilterDropdown(field);
    }, OPTION_SEARCH_DEBOUNCE_MS);
  }

  function renderPencilLoader(title, subtitle) {
    return '<div class="ks-pencil-loading" role="status" aria-live="polite">'
      + '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 200 200" class="pencil" aria-hidden="true">'
      + '<defs><clipPath id="ks-pencil-eraser"><rect height="30" width="30" ry="5" rx="5"></rect></clipPath></defs>'
      + '<circle transform="rotate(-113,100,100)" stroke-linecap="round" stroke-dashoffset="439.82" stroke-dasharray="439.82 439.82" stroke-width="2" stroke="currentColor" fill="none" r="70" class="pencil__stroke"></circle>'
      + '<g transform="translate(100,100)" class="pencil__rotate"><g fill="none">'
      + '<circle transform="rotate(-90)" stroke-dashoffset="402" stroke-dasharray="402.12 402.12" stroke-width="30" stroke="hsl(223,90%,50%)" r="64" class="pencil__body1"></circle>'
      + '<circle transform="rotate(-90)" stroke-dashoffset="465" stroke-dasharray="464.96 464.96" stroke-width="10" stroke="hsl(223,90%,60%)" r="74" class="pencil__body2"></circle>'
      + '<circle transform="rotate(-90)" stroke-dashoffset="339" stroke-dasharray="339.29 339.29" stroke-width="10" stroke="hsl(223,90%,40%)" r="54" class="pencil__body3"></circle></g>'
      + '<g transform="rotate(-90) translate(49,0)" class="pencil__eraser"><g class="pencil__eraser-skew">'
      + '<rect height="30" width="30" ry="5" rx="5" fill="hsl(223,90%,70%)"></rect><rect clip-path="url(#ks-pencil-eraser)" height="30" width="5" fill="hsl(223,90%,60%)"></rect>'
      + '<rect height="20" width="30" fill="hsl(223,10%,90%)"></rect><rect height="20" width="15" fill="hsl(223,10%,70%)"></rect><rect height="20" width="5" fill="hsl(223,10%,80%)"></rect>'
      + '<rect height="2" width="30" y="6" fill="hsla(223,10%,10%,0.2)"></rect><rect height="2" width="30" y="13" fill="hsla(223,10%,10%,0.2)"></rect></g></g>'
      + '<g transform="rotate(-90) translate(49,-30)" class="pencil__point"><polygon points="15 0,30 30,0 30" fill="hsl(33,90%,70%)"></polygon><polygon points="15 0,6 30,0 30" fill="hsl(33,90%,50%)"></polygon><polygon points="15 0,20 10,10 10" fill="hsl(223,10%,10%)"></polygon></g></g></svg>'
      + '<div class="ks-pencil-copy"><strong>' + escapeHtml(title || 'Đang tải Dashboard') + '</strong><span>' + escapeHtml(subtitle || 'Đang phân tích dữ liệu, vui lòng chờ...') + '</span></div></div>';
  }

  // =========================================================================
  // SEARCHABLE SINGLE SELECT (markup dung chung class multi-select-* cua
  // All Listings de UX/CSS giong het trang All Listings)
  // =========================================================================

  function optionRowMarkup(field, item) {
    var selected = String(view[field] || '') === item.value;
    return '<button type="button" class="lazy-option-row ' + (selected ? 'is-selected' : '') + '"'
      + ' data-ks-option-field="' + escapeHtml(field) + '"'
      + ' data-ks-option-value="' + escapeHtml(item.value) + '"'
      + ' role="option" aria-selected="' + (selected ? 'true' : 'false') + '">'
      + escapeHtml(item.label || item.value)
      + '</button>';
  }

  function optionListMarkup(field) {
    var fieldState = view.optionStates[field] || defaultLazyOptionState();
    var items = fieldState.items || [];
    var html = '';

    if (fieldState.isLoading && !items.length) {
      html += '<div class="multi-select-loading">Đang tải dữ liệu...</div>';
    }
    if (fieldState.error) {
      html += '<div class="multi-select-error">' + escapeHtml(fieldState.error)
        + ' <button type="button" data-ks-option-retry="' + escapeHtml(field) + '">Retry</button></div>';
    }
    if (!fieldState.isLoading && !fieldState.error && !items.length) {
      html += '<div class="multi-select-empty">Không tìm thấy dữ liệu phù hợp.</div>';
    }

    html += items.map(function (item) { return optionRowMarkup(field, item); }).join('');
    return html;
  }

  function optionFooterMarkup(field) {
    var fieldState = view.optionStates[field] || defaultLazyOptionState();
    if (fieldState.hasMore) {
      return '<button type="button" class="multi-select-load-more" data-ks-option-load-more="'
        + escapeHtml(field) + '"' + (fieldState.isLoading ? ' disabled' : '') + '>'
        + (fieldState.isLoading && (fieldState.items || []).length ? 'Đang tải...' : 'Load more')
        + '</button>';
    }
    return '<span class="multi-select-complete">Đã tải hết dữ liệu</span>';
  }

  function renderFilterSelect(field) {
    var config = FILTER_FIELDS[field];
    var enabled = isFieldEnabled(field);
    var open = enabled && view.openFilterField === field;
    var fieldState = view.optionStates[field] || defaultLazyOptionState();
    var value = String(view[field] || '');

    var triggerContent = value
      ? '<span class="multi-select-chip">' + escapeHtml(value) + '</span>'
      : '<span class="multi-select-placeholder">' + escapeHtml(config.placeholder) + '</span>';

    return '<div class="ks-field ks-filter-field' + (enabled ? '' : ' is-disabled') + '"'
      + ' data-ks-filter-wrap="' + escapeHtml(field) + '">'
      + '<span>' + escapeHtml(config.label)
      + (enabled ? '' : '<em class="ks-field-lock" title="Bị khoá bởi chế độ lọc đang chọn">khoá</em>')
      + '</span>'
      + '<div class="multi-select" style="position:relative">'
      + '<button type="button" class="multi-select-trigger" id="ks-trigger-' + escapeHtml(field) + '"'
      + ' data-ks-filter-trigger="' + escapeHtml(field) + '"'
      + ' aria-haspopup="listbox" aria-expanded="' + (open ? 'true' : 'false') + '"'
      + ' aria-disabled="' + (enabled ? 'false' : 'true') + '"'
      + (enabled ? '' : ' disabled tabindex="-1"') + '>'
      + '<span class="multi-select-trigger-content" title="' + escapeHtml(value || config.placeholder) + '">'
      + triggerContent + '</span>'
      + '<span class="multi-select-chevron" aria-hidden="true">▾</span>'
      + '</button>'
      + '<div class="multi-select-dropdown" id="ks-dropdown-' + escapeHtml(field) + '"'
      + (open ? '' : ' hidden') + ' style="z-index:10000">'
      + '<div class="multi-select-search"><input type="search" id="ks-search-' + escapeHtml(field) + '"'
      + ' data-ks-option-search="' + escapeHtml(field) + '" placeholder="Search..."'
      + ' aria-label="' + escapeHtml('Tìm ' + config.label) + '" autocomplete="off" spellcheck="false"'
      + ' value="' + escapeHtml(fieldState.search || '') + '"></div>'
      + '<div class="multi-select-actions"><span class="multi-select-actions-hint">Select one value</span>'
      + '<button type="button" data-ks-option-clear="' + escapeHtml(field) + '">Clear</button></div>'
      + '<div class="multi-select-options" id="ks-options-' + escapeHtml(field) + '" role="listbox"'
      + ' aria-label="' + escapeHtml(config.label) + '">' + optionListMarkup(field) + '</div>'
      + '<div class="multi-select-footer" id="ks-footer-' + escapeHtml(field) + '">'
      + optionFooterMarkup(field) + '</div>'
      + '</div></div></div>';
  }

  // Chi ve lai phan body cua dropdown de KHONG lam mat focus cua search input.
  function updateFilterDropdown(field) {
    if (!view.host) return;
    var list = view.host.querySelector('#ks-options-' + field);
    var footer = view.host.querySelector('#ks-footer-' + field);
    if (list) list.innerHTML = optionListMarkup(field);
    if (footer) footer.innerHTML = optionFooterMarkup(field);
  }

  // =========================================================================
  // DROPDOWN OPEN / CLOSE
  // =========================================================================

  function closeAllDropdowns(options) {
    var opts = options || {};
    view.openFilterField = '';
    if (!view.host) return;

    FILTER_FIELD_ORDER.forEach(function (field) {
      var dropdown = view.host.querySelector('#ks-dropdown-' + field);
      var trigger = view.host.querySelector('#ks-trigger-' + field);
      var search = view.host.querySelector('#ks-search-' + field);

      if (dropdown) dropdown.hidden = true;
      if (trigger) trigger.setAttribute('aria-expanded', 'false');

      if (opts.clearSearch) {
        if (search) search.value = '';
        var fieldState = view.optionStates[field];
        if (fieldState && fieldState.search) {
          resetLazyOptionField(field);
        }
      }
    });
  }

  function toggleFilterField(field) {
    // Field bi disable: khong mo dropdown, khong search, khong goi API.
    if (!isFieldEnabled(field)) return;

    var willOpen = view.openFilterField !== field;
    closeAllDropdowns();
    if (!willOpen) return;

    view.openFilterField = field;
    if (!view.host) return;

    var dropdown = view.host.querySelector('#ks-dropdown-' + field);
    var trigger = view.host.querySelector('#ks-trigger-' + field);
    var search = view.host.querySelector('#ks-search-' + field);

    if (dropdown) dropdown.hidden = false;
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    if (search) {
      requestAnimationFrame(function () { search.focus(); search.select(); });
    }

    var fieldState = view.optionStates[field];
    if (fieldState && !fieldState.isLoaded && !fieldState.isLoading) {
      loadLazyOptionField(field, { reset: true, useCache: true }).then(function () {
        if (view.openFilterField === field) updateFilterDropdown(field);
      });
    }
  }

  function ensureGlobalListeners() {
    if (globalListenersBound) return;
    globalListenersBound = true;

    document.addEventListener('click', function (event) {
      if (!view.openFilterField || !view.host || view.destroyed) return;
      var wrapper = view.host.querySelector('[data-ks-filter-wrap="' + view.openFilterField + '"]');
      if (wrapper && wrapper.contains(event.target)) return;
      closeAllDropdowns();
    });

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || !view.openFilterField || view.destroyed) return;
      closeAllDropdowns();
    });
  }

  // =========================================================================
  // SCOPE MUTATIONS
  // =========================================================================

  function setFilterMode(mode) {
    if (mode !== FILTER_MODE.BRAND_MODEL && mode !== FILTER_MODE.KEYWORD) return;
    // Click vao mode dang active thi KHONG tu tat mode.
    if (mode === view.filterMode) return;

    closeAllDropdowns({ clearSearch: true });

    // Xoa sach state cua mode cu de request khong bi nhiem filter an.
    if (mode === FILTER_MODE.KEYWORD) {
      view.brand = '';
      view.model = '';
      resetLazyOptionField('brand', { clearCache: true });
      resetLazyOptionField('model', { clearCache: true });
    } else {
      view.keyword = '';
      resetLazyOptionField('keyword', { clearCache: true });
    }

    // Condition / Min price / Period giu nguyen.
    view.filterMode = mode;
    view.selectedSeller = '';
    view.error = '';
    render();
    refreshData(false);
  }

  function selectOptionValue(field, rawValue) {
    if (!isFieldEnabled(field)) return;
    var value = normalizeOptionValue(rawValue);
    if (!value) return;

    if (field === 'brand') {
      if (view.brand === value) { closeAllDropdowns(); return; }
      view.brand = value;
      // Doi Brand -> Model cu co the khong con dung scope.
      view.model = '';
      resetLazyOptionField('model', { clearCache: true });
    } else if (field === 'model') {
      view.model = value;
    } else if (field === 'keyword') {
      view.keyword = value;
    } else if (field === 'condition') {
      view.condition = value;
      // Card keyword phai tinh lai theo condition moi.
      view.keywordOptionsLoaded = false;
    }

    view.selectedSeller = '';
    view.error = '';
    closeAllDropdowns();
    render();
    refreshData(false);
  }

  function clearFilterField(field) {
    if (!isFieldEnabled(field)) return;

    if (field === 'brand') {
      view.brand = '';
      // Brand bi Clear -> Model cung Clear vi co the khong con dung scope.
      view.model = '';
      resetLazyOptionField('model', { clearCache: true });
    } else if (field === 'model') {
      view.model = '';
    } else if (field === 'keyword') {
      // Mode van la Keyword, khong tu doi mode khi Clear.
      view.keyword = '';
    } else if (field === 'condition') {
      view.condition = '';
      view.keywordOptionsLoaded = false;
    }

    view.selectedSeller = '';
    view.error = '';
    render();
    refreshData(false);
  }

  function setMinPrice(rawValue) {
    var value = Number(rawValue);
    view.minPrice = Number.isFinite(value) && value >= 0 ? value : CONFIG.minPrice;
    view.cache = {};
    view.keywordOptionsLoaded = false;
    render();
    refreshData(true);
  }

  // =========================================================================
  // CARD DUOI TOOLBAR
  // =========================================================================

  function cardStatsMarkup(payload) {
    if (!payload) {
      return '<span>Đang tính số liệu whole-product...</span><em>&nbsp;</em>';
    }
    var overview = buildOverview(payload, view.period);
    return '<span>' + formatCount(overview.sellerCount) + ' sellers · '
      + formatCount(overview.eligibleListingCount) + ' listings đủ điều kiện · median '
      + formatCurrency(overview.medianPrice, payload.currency) + '</span>'
      + '<em>' + formatCount(overview.alertCount) + ' cảnh báo trong kỳ đang xem</em>';
  }

  function keywordCardMarkup(option) {
    var active = option.keyword === view.keyword;
    var cached = active ? findAnalytics() : null;
    var detail = cached
      ? cardStatsMarkup(cached)
      // /keywords la danh sach nhanh theo DB match, chua chay whole-product
      // classifier, nen phai ghi ro nhan "DB match" theo dung yeu cau.
      : '<span>DB match: ' + formatCount(option.seller_count) + ' sellers · '
        + formatCount(option.listing_count) + ' listings</span>'
        + '<em>Chọn để tính số liệu whole-product chính xác</em>';

    return '<button type="button" class="ks-keyword-card ' + (active ? 'is-active' : '') + '"'
      + ' data-ks-keyword-card="' + escapeHtml(option.keyword) + '">'
      + '<b>' + escapeHtml(option.keyword) + '</b>' + detail + '</button>';
  }

  // Mode A KHONG dung keyword card. Card duoc ve theo Brand / Model.
  function brandModelCardMarkup() {
    if (!view.brand && !view.model) return '';
    var payload = findAnalytics();
    var title = '';
    if (view.brand) title += '<b>' + escapeHtml(view.brand) + '</b>';
    if (view.model) title += '<b class="ks-card-model">' + escapeHtml(view.model) + '</b>';
    return '<div class="ks-keyword-card ks-scope-card is-active">' + title + cardStatsMarkup(payload) + '</div>';
  }

  function renderScopeStrip() {
    if (isKeywordMode()) {
      var options = view.keywordOptions.slice(0, CONFIG.keywordCardLimit);
      if (!options.length) return '';
      return '<div class="ks-keyword-strip-wrap"><div class="ks-keyword-strip" role="list">'
        + options.map(keywordCardMarkup).join('') + '</div>'
        + '<div class="ks-strip-note">← Kéo ngang để xem thêm keyword · số liệu whole-product chính xác được tính khi keyword đã tải analytics.</div></div>';
    }

    var card = brandModelCardMarkup();
    if (!card) return '';
    return '<div class="ks-keyword-strip-wrap"><div class="ks-keyword-strip" role="list">' + card + '</div>'
      + '<div class="ks-strip-note">Card theo Brand / Model đang chọn · dùng chung analytics scope với phần chi tiết bên dưới.</div></div>';
  }

  // =========================================================================
  // TOOLBAR
  // =========================================================================

  function renderModeSwitch() {
    var modes = [
      { key: FILTER_MODE.BRAND_MODEL, label: 'Brand + Model' },
      { key: FILTER_MODE.KEYWORD, label: 'Keyword' },
    ];
    return '<div class="ks-field ks-mode-field"><span>Lọc theo</span>'
      + '<div class="ks-segment ks-mode-segment" role="radiogroup" aria-label="Chế độ lọc">'
      + modes.map(function (item) {
        var active = item.key === view.filterMode;
        return '<button type="button" role="radio" aria-checked="' + (active ? 'true' : 'false') + '"'
          + ' class="' + (active ? 'is-active' : '') + '" data-ks-filter-mode="' + item.key + '">'
          + escapeHtml(item.label) + '</button>';
      }).join('')
      + '</div></div>';
  }

  function renderToolbar() {
    return '<div class="ks-toolbar">'
      // ROW 1 theo mockup: MODE | BRAND + MODEL | KEYWORD.
      + '<section class="ks-toolbar-panel ks-toolbar-top" aria-label="Bộ lọc sản phẩm">'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--mode">' + renderModeSwitch() + '</div>'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--brand-model">'
      + '<div class="ks-brand-model-group">'
      + renderFilterSelect('brand') + renderFilterSelect('model')
      + '</div></div>'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--keyword">' + renderFilterSelect('keyword') + '</div>'
      + '</section>'
      // ROW 2 theo mockup: CONDITION | NGUONG GIA | TUAN/THANG/VONG DOI | ACTIONS.
      + '<section class="ks-toolbar-panel ks-toolbar-bottom" aria-label="Bộ lọc điều kiện và thời gian">'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--condition">' + renderFilterSelect('condition') + '</div>'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--price">'
      + '<label class="ks-field ks-price-field"><span>Ngưỡng giá</span><div class="ks-price-row"><b>&gt; $</b>'
      + '<input id="ks-min-price" type="number" min="0" step="1" value="' + escapeHtml(view.minPrice) + '">'
      + '<button type="button" id="ks-min-price-clear" class="ks-mini-clear" title="Về mặc định $' + CONFIG.minPrice + '">Clear</button>'
      + '</div></label></div>'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--period">'
      + '<div class="ks-segment ks-period-segment" aria-label="Khoảng thời gian">'
      + CONFIG.periods.map(function (item) {
        return '<button type="button" data-ks-period="' + item.key + '" class="'
          + (item.key === view.period ? 'is-active' : '') + '">' + escapeHtml(item.label) + '</button>';
      }).join('')
      + '</div></div>'
      + '<div class="ks-toolbar-cell ks-toolbar-cell--actions">'
      + '<div class="ks-toolbar-actions">'
      + '<button type="button" id="ks-refresh" class="ks-icon-button" title="Làm mới">↻</button>'
      + '<button type="button" id="ks-export" class="ks-export-button"' + (scopeIsComplete() ? '' : ' disabled')
      + '>⇩ Xuất CSV</button>'
      + '</div></div>'
      + '</section>'
      + '</div>';
  }

  function renderAlertCard(alert) {
    var sev = alert.severity || 'info';
    var label = sev === 'critical' ? 'NGHIÊM TRỌNG' : (sev === 'warning' ? 'CẦN THEO DÕI' : 'THÔNG TIN');
    var metric = Number.isFinite(Number(alert.changePct)) ? semanticChangeMarkup(alert.changePct) : '';
    return '<article class="ks-alert ks-alert--' + sev + '">'
      + '<div class="ks-alert-severity">● ' + label + '</div>'
      + '<h4>' + escapeHtml(alert.title) + '</h4>'
      + (metric ? '<div class="ks-alert-metric">' + metric + '</div>' : '')
      + '<p>' + escapeHtml(alert.detail) + '</p>'
      + '<small>' + escapeHtml(alert.date || '') + '</small>'
      + '<button type="button" data-ks-open-seller="' + escapeHtml(alert.seller) + '">Xem seller →</button>'
      + '</article>';
  }

  function renderAlerts(overview) {
    return '<aside class="ks-alert-column"><div class="ks-column-title">Cảnh báo (' + formatCount(overview.alertCount) + ')</div>'
      + '<div class="ks-alert-scroll">'
      + (overview.alerts.length ? overview.alerts.map(renderAlertCard).join('') : '<div class="ks-empty-card">Không có cảnh báo đáng chú ý trong phạm vi đang xem.</div>')
      + '</div></aside>';
  }

  function sellerColor(index) { return CONFIG.sellerColors[index % CONFIG.sellerColors.length]; }
function sellerColorByName(payload, sellerName) {
  var sellers = (payload && payload.sellers || [])
    .map(function (item) {
      return String(item.seller || '').trim();
    })
    .filter(Boolean)
    .sort(function (a, b) {
      return a.localeCompare(b);
    });

  var index = sellers.indexOf(
    String(sellerName || '').trim()
  );

  if (index < 0) {
    index = 0;
  }

  return sellerColor(index);
}
  function renderChart(payload, overview) {
    var chartSellers = chooseChartSellers(overview);
    var dates = overview.visibleDates;
    var width = 920; var height = 390; var left = 72; var right = 24; var top = 24; var bottom = 48;
    var allValues = chartSellers.flatMap(function (row) { return row.points.map(function (p) { return Number(p.price); }); }).filter(Number.isFinite);
    if (!dates.length || !allValues.length) {
      return '<section class="ks-chart-panel ks-card"><div class="ks-chart-head"><div><h2>Xu hướng giá theo seller</h2><p>' + escapeHtml(periodDescription(axisForPeriod(payload, view.period), view.period)) + '</p></div></div><div class="ks-chart-empty">Không có dữ liệu giá trong phạm vi thời gian này.</div></section>';
    }
    var min = Math.min.apply(null, allValues); var max = Math.max.apply(null, allValues);
    var pad = Math.max((max - min) * 0.08, 50); min = Math.max(0, min - pad); max += pad;
    var plotW = width - left - right; var plotH = height - top - bottom;
    var xIndex = {}; dates.forEach(function (d, i) { xIndex[d] = i; });
    var x = function (date) { var i = xIndex[date] || 0; return left + (dates.length <= 1 ? plotW / 2 : (i / (dates.length - 1)) * plotW); };
    var y = function (value) { return top + ((max - Number(value)) / Math.max(max - min, 1)) * plotH; };

    var svg = '';
    for (var t = 0; t <= 5; t += 1) {
      var value = min + ((max - min) * t / 5); var yy = y(value);
      svg += '<line class="ks-grid-line" x1="' + left + '" y1="' + yy + '" x2="' + (width - right) + '" y2="' + yy + '"></line>';
      svg += '<text class="ks-axis-text" x="4" y="' + (yy + 4) + '">' + escapeHtml(formatCurrency(value, payload.currency)) + '</text>';
    }
    dates.forEach(function (date, i) {
      var shouldShow = dates.length <= 9 || i === 0 || i === dates.length - 1 || i % Math.ceil(dates.length / 7) === 0;
      if (shouldShow) svg += '<text class="ks-axis-text" x="' + x(date) + '" y="' + (height - 13) + '" text-anchor="middle">' + escapeHtml(formatDayMonth(date)) + '</text>';
    });

    chartSellers.forEach(function (row) {
  var color = sellerColorByName(
    payload,
    row.seller
  );
   var points = row.points.filter(function (p) {
    return dates.indexOf(
      normalizeDate(p.date)
    ) !== -1;
  });
      if (!points.length) return;
      var poly = points.map(function (p) { return x(normalizeDate(p.date)).toFixed(1) + ',' + y(p.price).toFixed(1); }).join(' ');
      svg += '<polyline class="ks-line" data-ks-open-seller="' + escapeHtml(row.seller) + '" points="' + poly + '" fill="none" stroke="' + color + '" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></polyline>';
      var previousListing = null;
      points.forEach(function (point) {
        var changedListing = previousListing && previousListing !== point.listing_id;
        var cx = x(normalizeDate(point.date)); var cy = y(point.price);
        var title = row.seller + ' | ' + normalizeDate(point.date) + ' | ' + (point.listing_id || '—') + ' | ' + formatCurrency(point.price, payload.currency) + ' | ' + (point.status || '—');
        if (changedListing) {
          svg += '<line x1="' + cx + '" y1="' + top + '" x2="' + cx + '" y2="' + (height - bottom) + '" stroke="#f97316" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"></line>';
          svg += '<rect class="ks-point ks-transition-point" data-ks-open-seller="' + escapeHtml(row.seller) + '" x="' + (cx - 5) + '" y="' + (cy - 5) + '" width="10" height="10" transform="rotate(45 ' + cx + ' ' + cy + ')" fill="#f97316" stroke="#fff" stroke-width="2"><title>' + escapeHtml('Listing đại diện mới · ' + title) + '</title></rect>';
        } else {
          svg += '<circle class="ks-point" data-ks-open-seller="' + escapeHtml(row.seller) + '" cx="' + cx + '" cy="' + cy + '" r="3.7" fill="' + color + '" stroke="#fff" stroke-width="1.5"><title>' + escapeHtml(title) + '</title></circle>';
        }
        previousListing = point.listing_id;
      });
    });

    return '<section class="ks-chart-panel ks-card">'
      + '<div class="ks-chart-head"><div><h2>Xu hướng giá theo seller</h2><p>Mỗi line = 1 seller · giá đại diện = snapshot gần nhất của listing đủ điều kiện được đăng mới nhất.</p><small>' + escapeHtml(periodDescription(axisForPeriod(payload, view.period), view.period)) + '</small></div>'
      + '<div class="ks-chart-kpi"><small>Median seller hiện tại</small><strong>' + formatCurrency(overview.medianPrice, payload.currency) + '</strong></div></div>'
      + '<div class="ks-chart-wrap"><svg class="ks-chart-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Xu hướng giá theo seller">' + svg + '</svg></div>'
      + '<div class="ks-chart-note">Biểu đồ hiển thị tối đa ' + CONFIG.maxChartSellers + ' seller ưu tiên theo mức biến động, đồng thời giữ seller min/max để tránh quá rối. Ở Vòng đời listing, trục thời gian bắt đầu từ ngày publish nhưng đường giá chỉ bắt đầu khi hệ thống có snapshot thật; không backfill giá về ngày đăng. Hình thoi cam = thời điểm đổi listing đại diện; rê chuột vào điểm để xem Listing ID.</div>'
      + '</section>';
  }

  function renderSellerStrip(overview, payload) {
    var rows = overview.sellers.slice().sort(function (a, b) {
      return Number(b.representativePrice || 0) - Number(a.representativePrice || 0);
    });
    return '<section class="ks-seller-section ks-card"><div class="ks-section-head"><div><h3>Seller trong keyword</h3><p>Cuộn ngang để xem thêm · click seller để mở các listing/URL song song.</p></div><span>' + formatCount(rows.length) + ' seller</span></div>'
      + '<div class="ks-seller-strip">'
      + rows.map(function (row) {
       var status = String(
        row.representativeStatus || ''
      ).toUpperCase();

      var color = sellerColorByName(
        payload,
        row.seller
      );
        return '<button type="button" class="ks-seller-card" data-ks-open-seller="' + escapeHtml(row.seller) + '">'
          + '<div class="ks-seller-card-title">'
          + '<i style="background:'
        + color
        + '"></i>'
        +'<b>' 
        + escapeHtml(row.seller) 
        + '</b></div>'
          + '<small>' + formatCount(row.totalListingCount) + ' listing · ' + formatCount(row.activeListingCount) + ' active</small>'
          + '<span title="Listing đại diện hiện tại">Đại diện: ' + escapeHtml(row.representativeListingId || '—') + '</span>'
          + '<div class="ks-seller-price">' + formatCurrency(row.representativePrice, payload.currency) + ' ' + semanticChangeMarkup(row.changePct) + '</div>'
          + '<em class="ks-status ks-status--' + (status === 'ACTIVE' || status === 'NEW_LISTING' ? 'active' : (status === 'OUT_OF_STOCK' ? 'out' : 'ended')) + '">' + escapeHtml(status || 'UNKNOWN') + '</em>'
          + '</button>';
      }).join('')
      + '</div>'
      + '<div class="ks-color-note"><b>Chú thích màu:</b> <span class="good">▼ xanh = giá giảm / ACTIVE</span> · <span class="bad">▲ đỏ = giá tăng / nghiêm trọng</span> · <span class="warn">vàng = cần theo dõi</span> · <span class="info">xanh dương = thông tin</span> · <span class="transition">cam = listing đại diện mới</span> · màu line chỉ để phân biệt seller.</div>'
      + '</section>';
  }

  function renderSummary(payload, overview) {
    var insights = buildInsights(payload, overview);
    return '<aside class="ks-summary ks-card"><h3>Tổng quan keyword</h3>'
      + '<div class="ks-summary-keyword">' + escapeHtml(payload.keyword) + '</div>'
      + '<div class="ks-summary-source">Nguồn: ' + escapeHtml(payload.source || 'DB') + ' · whole product · giá &gt; $' + escapeHtml(payload.minPrice) + '</div>'
      + '<div class="ks-summary-median">' + formatCurrency(overview.medianPrice, payload.currency) + '</div><div class="ks-summary-caption">Median giá đại diện hiện tại của seller</div>'
      + '<div class="ks-summary-grid">'
      + stat('Seller', overview.sellerCount) + stat('Listings đủ điều kiện', overview.eligibleListingCount)
      + stat('Min seller', formatCurrency(overview.minPrice, payload.currency)) + stat('Max seller', formatCurrency(overview.maxPrice, payload.currency))
      + stat('Seller nhiều listing', overview.multiListingSellerCount) + stat('Hết hàng / Ended', overview.outOfStock + ' / ' + overview.ended)
      + stat('Seller giảm giá', '<span class="ks-text-good">' + overview.fallingSellerCount + '</span>', true)
      + stat('Seller tăng giá', '<span class="ks-text-bad">' + overview.risingSellerCount + '</span>', true)
      + '</div>'
      + '<div class="ks-insights"><h4>Đánh giá tổng quan</h4>'
      + insights.map(function (item) { return '<div class="ks-insight ks-insight--' + item.tone + '"><i>✓</i><span>' + escapeHtml(item.text) + '</span></div>'; }).join('')
      + '</div></aside>';
  }

  function stat(label, value, raw) {
    return '<div class="ks-stat"><span>' + escapeHtml(label) + '</span><b>' + (raw ? value : escapeHtml(value)) + '</b></div>';
  }

  function renderMain(payload) {
    var overview = buildOverview(payload, view.period);
    return '<div class="ks-grid">' + renderAlerts(overview) + renderChart(payload, overview) + renderSummary(payload, overview) + '</div>'
      + renderSellerStrip(overview, payload);
  }

  function sparklineSvg(listing, payload) {
    var visible = windowDates(payload.axis, 'lifecycle');
    var points = (listing.sparkline || []).filter(function (p) { return p && Number.isFinite(Number(p.price)); });
    if (points.length < 2) return '<div class="ks-spark-empty">Chưa đủ snapshot để vẽ biến động.</div>';
    var w = 340; var h = 64; var pad = 7;
    var values = points.map(function (p) { return Number(p.price); });
    var min = Math.min.apply(null, values); var max = Math.max.apply(null, values); var span = Math.max(max - min, 1);
    var coords = points.map(function (p, i) {
      var x = pad + (i / Math.max(points.length - 1, 1)) * (w - pad * 2);
      var y = h - pad - ((Number(p.price) - min) / span) * (h - pad * 2);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<svg class="ks-spark-svg" viewBox="0 0 ' + w + ' ' + h + '"><polyline points="' + coords + '" fill="none" stroke="#f97316" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></polyline></svg>';
  }

  function renderDrawer(payload, sellerName) {
    var seller = findSeller(payload, sellerName);
    if (!seller) return '';
    var row = buildSellerRows(payload, view.period).find(function (item) { return item.seller === sellerName; });
    var repId = row ? row.representativeListingId : seller.representative_listing_id;
    var events = (seller.events || []).slice().sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });
    return '<div class="ks-overlay" data-ks-close-drawer></div><aside class="ks-drawer" role="dialog" aria-modal="true">'
      + '<div class="ks-drawer-head"><div><h2>' + escapeHtml(sellerName) + '</h2><p>Keyword: ' + escapeHtml(payload.keyword) + '</p></div><button type="button" data-ks-close-drawer>✕</button></div>'
      + '<div class="ks-drawer-kpis">' + drawerKpi('Giá đại diện', formatCurrency(row && row.representativePrice, payload.currency))
      + drawerKpi('Listing đại diện', repId || '—') + drawerKpi('Active listings', seller.active_listing_count || 0)
      + drawerKpi('Khoảng giá active', formatCurrency(seller.active_price_min, payload.currency) + ' – ' + formatCurrency(seller.active_price_max, payload.currency)) + '</div>'
      + '<section class="ks-drawer-section"><h3>Listing đang theo dõi</h3>'
      + (seller.listings || []).map(function (listing) {
        var representative = listing.listing_id === repId;
        var publishedAt = normalizeDate(listing.published_at);
        var firstSeen = normalizeDate(listing.first_seen);
        return '<article class="ks-listing-card ' + (representative ? 'is-representative' : '') + '"><div class="ks-listing-card-head"><div><b>' + escapeHtml(listing.listing_id) + '</b><small>' + escapeHtml(listing.title || '') + '</small></div><span class="ks-badge ' + (representative ? 'ks-badge--rep' : 'ks-badge--history') + '">' + (representative ? 'Đại diện' : 'History') + '</span></div>'
          + '<div class="ks-spark">' + sparklineSvg(listing, payload) + '</div>'
          + '<div class="ks-listing-meta">Ngày đăng: ' + escapeHtml(publishedAt || '—')
          + ' · Theo dõi từ: ' + escapeHtml(firstSeen || '—')
          + ' · Current/last: ' + formatCurrency(listing.current_price, payload.currency) + ' · ' + escapeHtml(listing.status || 'UNKNOWN') + '</div>'
          + (listing.url ? '<a class="ks-open-link" href="' + escapeHtml(listing.url) + '" target="_blank" rel="noopener noreferrer">Mở listing ↗</a>' : '')
          + '</article>';
      }).join('') + '</section>'
      + '<section class="ks-drawer-section"><h3>Sự kiện seller-level</h3>'
      + (events.length ? events.map(function (event) {
        return '<div class="ks-event ks-event--' + escapeHtml(String(event.type || '').toLowerCase()) + '"><i></i><div><b>' + escapeHtml(event.type || '') + '</b><p>' + escapeHtml(event.message || event.detail || '') + '</p></div><time>' + escapeHtml(normalizeDate(event.date)) + '</time></div>';
      }).join('') : '<div class="ks-empty-card">Chưa có event.</div>') + '</section></aside>';
  }

  function drawerKpi(label, value) {
    return '<div class="ks-dk"><span>' + escapeHtml(label) + '</span><b>' + escapeHtml(value) + '</b></div>';
  }

  function render() {
    if (!view.host || view.destroyed) return;

    var payload = findAnalytics();
    var body;

    if (!scopeIsComplete()) {
      body = '<div class="ks-empty-card ks-scope-hint">' + escapeHtml(scopeHint()) + '</div>';
    } else if (payload) {
      body = renderMain(payload);
    } else if (view.loading) {
      body = renderPencilLoader(
        'Đang tải ' + (scopeLabel() || 'dữ liệu'),
        'Đang phân tích seller và listing từ database...'
      );
    } else if (view.error) {
      body = '<div class="ks-state ks-state--error"><b>Không tải được dữ liệu</b><span>'
        + escapeHtml(view.error) + '</span><button type="button" id="ks-retry">Thử lại</button></div>';
    } else {
      body = '<div class="ks-empty-card">Không có dữ liệu phù hợp với bộ lọc đang chọn.</div>';
    }

    view.host.innerHTML = '<div class="ks-module">'
      + renderToolbar()
      + renderScopeStrip()
      + (view.optionsError ? '<div class="ks-inline-error">' + escapeHtml(view.optionsError) + '</div>' : '')
      + (view.error && payload ? '<div class="ks-inline-error">' + escapeHtml(view.error) + '</div>' : '')
      + body
      + (payload && view.selectedSeller ? renderDrawer(payload, view.selectedSeller) : '')
      + '</div>';

    bindEvents();
  }

  // =========================================================================
  // EVENT DELEGATION
  // =========================================================================

  function onHostClick(event) {
    if (view.destroyed || !view.host) return;
    var target = event.target;
    if (!target || !target.closest) return;

    var modeButton = target.closest('[data-ks-filter-mode]');
    if (modeButton) {
      event.preventDefault();
      setFilterMode(modeButton.getAttribute('data-ks-filter-mode') || '');
      return;
    }

    var trigger = target.closest('[data-ks-filter-trigger]');
    if (trigger) {
      event.preventDefault();
      event.stopPropagation();
      toggleFilterField(trigger.getAttribute('data-ks-filter-trigger') || '');
      return;
    }

    var option = target.closest('[data-ks-option-value]');
    if (option) {
      event.preventDefault();
      event.stopPropagation();
      selectOptionValue(
        option.getAttribute('data-ks-option-field') || '',
        option.getAttribute('data-ks-option-value') || ''
      );
      return;
    }

    var clearButton = target.closest('[data-ks-option-clear]');
    if (clearButton) {
      event.preventDefault();
      event.stopPropagation();
      clearFilterField(clearButton.getAttribute('data-ks-option-clear') || '');
      return;
    }

    var loadMore = target.closest('[data-ks-option-load-more]');
    if (loadMore) {
      event.preventDefault();
      event.stopPropagation();
      var loadMoreField = loadMore.getAttribute('data-ks-option-load-more') || '';
      loadLazyOptionField(loadMoreField, { reset: false, useCache: false })
        .then(function () { updateFilterDropdown(loadMoreField); });
      return;
    }

    var retryOption = target.closest('[data-ks-option-retry]');
    if (retryOption) {
      event.preventDefault();
      event.stopPropagation();
      var retryField = retryOption.getAttribute('data-ks-option-retry') || '';
      loadLazyOptionField(retryField, { reset: true, useCache: false })
        .then(function () { updateFilterDropdown(retryField); });
      return;
    }

    // Click ben trong dropdown nhung khong trung control nao: giu dropdown mo.
    if (target.closest('.multi-select-dropdown')) {
      event.stopPropagation();
      return;
    }

    var keywordCard = target.closest('[data-ks-keyword-card]');
    if (keywordCard) {
      event.preventDefault();
      selectOptionValue('keyword', keywordCard.getAttribute('data-ks-keyword-card') || '');
      return;
    }

    var periodButton = target.closest('[data-ks-period]');
    if (periodButton) {
      event.preventDefault();
      view.period = periodButton.getAttribute('data-ks-period') || 'week';
      view.selectedSeller = '';
      render();
      return;
    }

    var openSeller = target.closest('[data-ks-open-seller]');
    if (openSeller) {
      event.preventDefault();
      view.selectedSeller = openSeller.getAttribute('data-ks-open-seller') || '';
      render();
      return;
    }

    if (target.closest('[data-ks-close-drawer]')) {
      event.preventDefault();
      view.selectedSeller = '';
      render();
      return;
    }

    if (target.closest('#ks-min-price-clear')) {
      event.preventDefault();
      // Clear ngưỡng giá = quay ve mac dinh business rule, khong bo filter.
      setMinPrice(CONFIG.minPrice);
      return;
    }

    if (target.closest('#ks-refresh') || target.closest('#ks-retry')) {
      event.preventDefault();
      view.cache = {};
      view.optionCache = {};
      view.keywordOptionsLoaded = false;
      FILTER_FIELD_ORDER.forEach(function (field) { resetLazyOptionField(field); });
      refreshData(true);
      return;
    }

    if (target.closest('#ks-export')) {
      event.preventDefault();
      var payload = findAnalytics();
      if (payload) exportCurrentCsv(payload);
    }
  }

  function onHostInput(event) {
    if (view.destroyed) return;
    var target = event.target;
    if (!target || !target.getAttribute) return;

    var searchField = target.getAttribute('data-ks-option-search');
    if (searchField) {
      event.stopPropagation();
      debounceLazyOptionSearch(searchField, target.value || '');
    }
  }

  function onHostChange(event) {
    if (view.destroyed) return;
    var target = event.target;
    if (target && target.id === 'ks-min-price') setMinPrice(target.value);
  }

  function bindEvents() {
    if (!view.host) return;
    ensureGlobalListeners();
    // Delegation gan MOT lan tren host, khong bi nhan doi sau moi lan render.
    if (view.host.__ksDelegationBound) return;
    view.host.__ksDelegationBound = true;
    view.host.addEventListener('click', onHostClick);
    view.host.addEventListener('input', onHostInput);
    view.host.addEventListener('change', onHostChange);
  }

  // =========================================================================
  // DATA LOADING
  // =========================================================================

  function payloadFromApi(raw) {
    var payload = keywordFromPayload(raw);
    if (payload) payload.scope = (raw && raw.scope) || null;
    return payload;
  }

  async function loadKeywordCards(force) {
    // Card keyword chi ton tai o Mode B.
    if (!isKeywordMode()) return;
    if (!force && view.keywordOptionsLoaded) return;
    try {
      var payload = await api(keywordCardsPath());
      view.keywordOptions = (((payload && payload.items) || [])).map(function (item) {
        return {
          keyword: String(item.keyword || '').trim(),
          seller_count: Number(item.seller_count || 0),
          listing_count: Number(item.listing_count || 0),
          median_price: item.median_price,
        };
      }).filter(function (item) { return !!item.keyword; });
      view.keywordOptionsLoaded = true;
      view.optionsError = '';
    } catch (error) {
      // Card strip chi la phu tro; khong duoc chan analytics chinh.
      view.optionsError = error && error.message ? error.message : 'Không tải được danh sách keyword.';
    }
  }

  async function loadAnalytics(force) {
    if (!scopeIsComplete()) {
      view.loading = false;
      view.error = '';
      render();
      return;
    }

    var key = analyticsCacheKey();
    if (!force && Object.prototype.hasOwnProperty.call(view.cache, key)) {
      render();
      return;
    }

    view.loading = true;
    view.error = '';
    render();

    try {
      var raw = await api(analyticsPath());
      view.cache[key] = payloadFromApi(raw);
    } catch (error) {
      view.error = error && error.message ? error.message : 'Không tải được analytics.';
    } finally {
      view.loading = false;
      render();
    }
  }

  async function refreshData(force) {
    await loadKeywordCards(Boolean(force));
    await loadAnalytics(Boolean(force));
  }

  function csvCell(value) {
    var text = value == null ? '' : String(value);
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function exportCurrentCsv(payload) {
    var overview = buildOverview(payload, view.period);
    var header = [
      'filter_mode', 'scope', 'brand_filter', 'model_filter', 'keyword_filter', 'condition_filter',
      'seller', 'listing_id', 'listing_title', 'published_at', 'first_seen', 'current_price', 'status',
      'eligible', 'representative', 'change_pct', 'listing_url',
    ];
    var rows = [header];
    (payload.sellers || []).forEach(function (seller) {
      var sellerRow = overview.sellers.find(function (item) { return item.seller === seller.seller; });
      (seller.listings || []).forEach(function (listing) {
        rows.push([
          view.filterMode,
          payload.keyword || scopeLabel(),
          view.brand || '',
          view.model || '',
          view.keyword || '',
          view.condition || '',
          seller.seller, listing.listing_id, listing.title || '',
          listing.published_at || '', listing.first_seen || '',
          listing.current_price,
          listing.status || '', listing.eligible ? 'yes' : 'no',
          sellerRow && sellerRow.representativeListingId === listing.listing_id ? 'yes' : 'no',
          sellerRow ? sellerRow.changePct : '', listing.url || '',
        ]);
      });
    });
    var csv = '\ufeff' + rows.map(function (row) { return row.map(csvCell).join(','); }).join('\r\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = ('keyword_seller_' + (scopeLabel() || 'export') + '.csv').replace(/[^a-zA-Z0-9._-]+/g, '_');
    document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
  }

  async function mount(host, options) {
    view.host = host;
    view.apiClient = options && options.apiClient ? options.apiClient : null;
    view.destroyed = false;
    view.openFilterField = '';
    view.selectedSeller = '';
    view.error = '';
    view.optionsError = '';

    var reload = Boolean(options && options.reload);
    if (reload) {
      view.cache = {};
      view.optionCache = {};
      view.optionStates = defaultOptionStates();
      view.keywordOptions = [];
      view.keywordOptionsLoaded = false;
    }

    render();
    await refreshData(reload);
  }

  function destroy() {
    view.destroyed = true;
    view.openFilterField = '';
    FILTER_FIELD_ORDER.forEach(function (field) { abortOptionRequest(field); });
    Object.keys(view.optionSearchTimers).forEach(function (field) {
      clearTimeout(view.optionSearchTimers[field]);
    });
    view.optionSearchTimers = {};
    view.host = null;
    view.selectedSeller = '';
  }

  global.KeywordSellerAnalytics = {
    mount: mount,
    destroy: destroy,
    config: CONFIG,
    colorSemantics: COLOR_SEMANTICS,
    filterModes: FILTER_MODE,
    filterFields: FILTER_FIELDS,
    logic: {
      findKeyword: findKeyword,
      windowDates: windowDates,
      buildOverview: buildOverview,
      buildPeriodAlerts: buildPeriodAlerts,
      classifyEventAlert: classifyEventAlert,
      chooseChartSellers: chooseChartSellers,
      percentChange: percentChange,
      isFieldEnabled: isFieldEnabled,
      scopeIsComplete: scopeIsComplete,
      scopeLabel: scopeLabel,
      analyticsParams: analyticsParams,
      analyticsCacheKey: analyticsCacheKey,
      buildLazyOptionCacheKey: buildLazyOptionCacheKey,
      setFilterMode: setFilterMode,
      selectOptionValue: selectOptionValue,
      clearFilterField: clearFilterField,
      defaultLazyOptionState: defaultLazyOptionState,
      state: view,
    },
  };
})(typeof window !== 'undefined' ? window : globalThis);
