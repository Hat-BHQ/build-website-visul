/*
 * KeywordSellerAnalytics
 * =====================================================================
 * Module doc lap cho HQA Dashboard: Keyword -> Seller -> Listing moi nhat
 * -> Price / Status history.
 *
 * Nguyen tac (theo prompt_keyword_seller_latest_listing_dashboard.txt):
 *   - 1 chart  = 1 keyword
 *   - 1 line   = 1 seller
 *   - Gia dai dien cua seller tai thoi diem T = snapshot gan nhat cua
 *     listing DU DIEU KIEN co thoi diem xuat hien MOI NHAT <= T.
 *   - Listing cu khong bi mat, van giu price/status history rieng.
 *
 * Module nay khong phu thuoc app.js. Toan bo business logic nam trong
 * `KeywordSellerAnalytics.logic` (pure functions, khong cham DOM) de co the
 * unit-test va sau nay tai su dung o backend/BFF.
 *
 * Du lieu lay tu DB qua HQA service:
 *   GET /api/v1/hqa/keyword-seller/keywords
 *   GET /api/v1/hqa/keyword-seller/analytics?keyword=...
 *   GET /api/v1/hqa/keyword-seller/export?keyword=...
 * Backend da phan loai role bang listing_classifier va ap rule gia dai dien;
 * cac ham trong `logic` duoc giu de tinh lai tuc thi khi doi nguong gia/vai tro
 * ma khong phai goi lai API. Co the thay tang du lieu bang setDataSource()
 * hoac chi thay ham goi HTTP bang setApiClient().
 */
(function (global) {
  'use strict';

  // ==================================================================
  // 1. CONFIG
  // ==================================================================

  var CONFIG = {
    // Rule loc du lieu - prompt muc 2.
    minPrice: 500,
    eligibleRoles: ['whole_product'],

    // So keyword hien thi tren thanh nav nhanh (DB co the co rat nhieu keyword).
    keywordNavLimit: 8,

    // Nguong canh bao - dong bo voi DASHBOARD_CONFIG cua dashboard hien tai.
    priceDropWarningPct: 20,
    priceDropCriticalPct: 30,
    priceShiftWarningPct: 5,
    multipleActiveThreshold: 2,

    // Mau line chart - prompt muc 21 (accent cam, khong dung qua nhieu mau).
    colors: [
      '#f97316', '#2563eb', '#16a34a', '#7c3aed',
      '#0891b2', '#ef4444', '#c026d3', '#0f766e',
      '#b45309', '#475569',
    ],

    periods: [
      { key: 'detail', label: 'Chi tiết' },
      { key: 'week', label: 'Tuần' },
      { key: 'month', label: 'Tháng' },
    ],

    roles: [
      { key: 'whole_product', label: 'Whole product' },
      { key: 'all', label: 'Tất cả' },
    ],

    currency: 'USD',
  };

  var EVENT_TYPES = {
    TRACKING_STARTED: 'TRACKING_STARTED',
    PRICE_CHANGED: 'PRICE_CHANGED',
    NEW_LISTING_PRICE_SHIFT: 'NEW_LISTING_PRICE_SHIFT',
    STATUS_CHANGED: 'STATUS_CHANGED',
  };

  var EVENT_LABELS = {
    TRACKING_STARTED: 'Bắt đầu theo dõi',
    PRICE_CHANGED: 'Price Changed',
    NEW_LISTING_PRICE_SHIFT: 'New Listing Price Shift',
    STATUS_CHANGED: 'Status Changed',
  };

  var EXCLUSION_REASONS = {
    role: 'Không phải whole_product',
    price: 'Giá dưới ngưỡng tối thiểu',
    noSnapshot: 'Chưa có snapshot giá',
  };

  // ==================================================================
  // 2. UTILITIES (format / escape / math)
  // ==================================================================

  function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatCurrency(value, currency) {
    var numeric = Number(value);
    if (!isFinite(numeric)) return '—';
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency || CONFIG.currency,
        maximumFractionDigits: 0,
      }).format(numeric);
    } catch (error) {
      return '$' + Math.round(numeric).toLocaleString('en-US');
    }
  }

  function formatPercent(value, digits) {
    var numeric = Number(value);
    if (!isFinite(numeric)) return '—';
    return numeric.toFixed(digits === undefined ? 1 : digits) + '%';
  }

  function formatDayMonth(isoDate) {
    var parts = String(isoDate || '').split('-');
    if (parts.length < 3) return String(isoDate || '');
    return parts[2] + '/' + parts[1];
  }

  function median(values) {
    var sorted = values.filter(function (value) { return isFinite(value); }).slice().sort(function (a, b) { return a - b; });
    if (!sorted.length) return null;
    var middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function percentChange(current, previous) {
    var currentValue = Number(current);
    var previousValue = Number(previous);
    if (!isFinite(currentValue) || !isFinite(previousValue) || previousValue === 0) return null;
    return ((currentValue - previousValue) / previousValue) * 100;
  }

  function isoWeekKey(isoDate) {
    var date = new Date(isoDate + 'T00:00:00Z');
    if (isNaN(date.getTime())) return String(isoDate);
    var target = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
    var dayNumber = (target.getUTCDay() + 6) % 7;
    target.setUTCDate(target.getUTCDate() - dayNumber + 3);
    var firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
    var firstDayNumber = (firstThursday.getUTCDay() + 6) % 7;
    firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNumber + 3);
    var week = 1 + Math.round((target - firstThursday) / (7 * 24 * 3600 * 1000));
    return target.getUTCFullYear() + '-W' + String(week).padStart(2, '0');
  }

  function monthKey(isoDate) {
    return String(isoDate || '').slice(0, 7);
  }

  // ==================================================================
  // 3. PURE BUSINESS LOGIC
  // ==================================================================

  /**
   * Chuyen dataset tho thanh cau truc chuan hoa:
   *   keyword -> dates[] -> seller -> listing -> snapshots (index-based)
   * Chap nhan 2 dang snapshot dau vao:
   *   { '2026-08-11': 600 }                        // gia thuan
   *   { '2026-08-11': { price: 600, status: '..' } }
   */
  function normalizeDataset(raw) {
    var keywords = (raw && raw.keywords ? raw.keywords : []).map(function (entry) {
      var dateSet = {};
      (entry.sellers || []).forEach(function (seller) {
        (seller.listings || []).forEach(function (listing) {
          Object.keys(listing.snapshots || {}).forEach(function (date) { dateSet[date] = true; });
          if (listing.publishedAt) dateSet[listing.publishedAt] = true;
        });
      });
      var dates = Object.keys(dateSet).sort();
      var dateIndex = {};
      dates.forEach(function (date, index) { dateIndex[date] = index; });

      var sellers = (entry.sellers || []).map(function (seller) {
        var listings = (seller.listings || []).map(function (listing) {
          var snapshots = Object.keys(listing.snapshots || {}).sort().map(function (date) {
            var value = listing.snapshots[date];
            var isObject = value && typeof value === 'object';
            return {
              date: date,
              index: dateIndex[date],
              price: Number(isObject ? value.price : value),
              status: String((isObject && value.status) || listing.status || 'ACTIVE').toUpperCase(),
            };
          });
          var publishedAt = listing.publishedAt || (snapshots.length ? snapshots[0].date : null);
          return {
            listingId: listing.listingId,
            title: listing.title || listing.listingId,
            url: listing.url || '',
            role: listing.role || 'whole_product',
            condition: listing.condition || '',
            categoryName: listing.categoryName || '',
            quantity: listing.quantity === undefined ? null : listing.quantity,
            views: listing.views === undefined ? null : listing.views,
            status: String(listing.status || 'ACTIVE').toUpperCase(),
            publishedAt: publishedAt,
            firstSeenIndex: publishedAt && dateIndex[publishedAt] !== undefined
              ? dateIndex[publishedAt]
              : (snapshots.length ? snapshots[0].index : Number.MAX_SAFE_INTEGER),
            snapshots: snapshots,
          };
        });
        return { seller: seller.seller, listings: listings };
      });

      return {
        keyword: entry.keyword,
        label: entry.label || entry.keyword,
        marketplace: entry.marketplace || 'ebay',
        dates: dates,
        sellers: sellers,
      };
    });

    return {
      generatedAt: (raw && raw.generatedAt) || null,
      currency: (raw && raw.currency) || CONFIG.currency,
      keywords: keywords,
    };
  }

  function resolveOptions(options) {
    var resolved = options || {};
    return {
      minPrice: resolved.minPrice === undefined ? CONFIG.minPrice : Number(resolved.minPrice),
      roleFilter: resolved.roleFilter || 'whole_product',
    };
  }

  /**
   * Snapshot gan nhat cua listing tai thoi diem index (carry-forward).
   * Khac voi mockup goc: neu ngay T khong co snapshot moi, ta van giu gia
   * cuoi cung da biet thay vi coi listing la "khong ton tai".
   */
  function listingSnapshotAt(listing, index) {
    var found = null;
    var snapshots = listing.snapshots || [];
    for (var i = 0; i < snapshots.length; i += 1) {
      if (snapshots[i].index > index) break;
      found = snapshots[i];
    }
    return found;
  }

  /** Kiem tra listing co du dieu kien tham gia phan tich chinh khong (prompt muc 2). */
  function listingEligibilityAt(listing, index, options) {
    var settings = resolveOptions(options);
    if (settings.roleFilter !== 'all' && CONFIG.eligibleRoles.indexOf(listing.role) === -1) {
      return { eligible: false, reason: 'role', snapshot: listingSnapshotAt(listing, index) };
    }
    if (listing.firstSeenIndex > index) {
      return { eligible: false, reason: 'notYetPublished', snapshot: null };
    }
    var snapshot = listingSnapshotAt(listing, index);
    if (!snapshot) return { eligible: false, reason: 'noSnapshot', snapshot: null };
    if (!(snapshot.price > settings.minPrice)) {
      return { eligible: false, reason: 'price', snapshot: snapshot };
    }
    return { eligible: true, reason: null, snapshot: snapshot };
  }

  /**
   * Listing dai dien cua seller tai thoi diem index:
   * listing du dieu kien co firstSeenIndex lon nhat <= index.
   * Tie-break: publishedAt moi hon, roi den listingId de ket qua on dinh.
   */
  function representativeListingAt(seller, index, options) {
    var eligible = [];
    (seller.listings || []).forEach(function (listing) {
      var check = listingEligibilityAt(listing, index, options);
      if (check.eligible) eligible.push({ listing: listing, snapshot: check.snapshot });
    });
    if (!eligible.length) return null;
    eligible.sort(function (a, b) {
      if (b.listing.firstSeenIndex !== a.listing.firstSeenIndex) {
        return b.listing.firstSeenIndex - a.listing.firstSeenIndex;
      }
      return String(b.listing.listingId).localeCompare(String(a.listing.listingId));
    });
    return eligible[0];
  }

  /** Chuoi gia dai dien cua seller tren toan bo truc ngay. */
  function buildSellerSeries(seller, dates, options) {
    return dates.map(function (date, index) {
      var representative = representativeListingAt(seller, index, options);
      if (!representative) return null;
      return {
        index: index,
        date: date,
        price: representative.snapshot.price,
        status: representative.snapshot.status,
        listingId: representative.listing.listingId,
        listingUrl: representative.listing.url,
        activeListingCount: countActiveListingsAt(seller, index),
      };
    });
  }

  function countActiveListingsAt(seller, index) {
    var count = 0;
    (seller.listings || []).forEach(function (listing) {
      if (listing.firstSeenIndex > index) return;
      var snapshot = listingSnapshotAt(listing, index);
      if (snapshot && snapshot.status === 'ACTIVE') count += 1;
    });
    return count;
  }

  function lastPoint(series) {
    for (var i = series.length - 1; i >= 0; i -= 1) {
      if (series[i]) return series[i];
    }
    return null;
  }

  function firstPoint(series) {
    for (var i = 0; i < series.length; i += 1) {
      if (series[i]) return series[i];
    }
    return null;
  }

  /** Timeline su kien seller-level (prompt muc 15). */
  function buildSellerEvents(seller, dates, options) {
    var series = buildSellerSeries(seller, dates, options);
    var events = [];
    var previous = null;

    series.forEach(function (point) {
      if (!point) return;
      if (!previous) {
        events.push({
          type: EVENT_TYPES.TRACKING_STARTED,
          date: point.date,
          listingId: point.listingId,
          price: point.price,
          detail: point.listingId + ' @ ' + formatCurrency(point.price),
        });
      } else if (previous.listingId !== point.listingId) {
        events.push({
          type: EVENT_TYPES.NEW_LISTING_PRICE_SHIFT,
          date: point.date,
          listingId: point.listingId,
          previousListingId: previous.listingId,
          price: point.price,
          previousPrice: previous.price,
          changePct: percentChange(point.price, previous.price),
          detail: previous.listingId + ' ' + formatCurrency(previous.price)
            + ' → ' + point.listingId + ' ' + formatCurrency(point.price),
        });
      } else if (previous.price !== point.price) {
        events.push({
          type: EVENT_TYPES.PRICE_CHANGED,
          date: point.date,
          listingId: point.listingId,
          price: point.price,
          previousPrice: previous.price,
          changePct: percentChange(point.price, previous.price),
          detail: point.listingId + ': ' + formatCurrency(previous.price) + ' → ' + formatCurrency(point.price),
        });
      }
      previous = point;
    });

    // Status change duoc tinh o cap listing de khong bo sot listing lich su.
    (seller.listings || []).forEach(function (listing) {
      var previousStatus = null;
      (listing.snapshots || []).forEach(function (snapshot) {
        if (previousStatus && previousStatus !== snapshot.status) {
          events.push({
            type: EVENT_TYPES.STATUS_CHANGED,
            date: snapshot.date,
            listingId: listing.listingId,
            fromStatus: previousStatus,
            toStatus: snapshot.status,
            detail: listing.listingId + ': ' + previousStatus + ' → ' + snapshot.status,
          });
        }
        previousStatus = snapshot.status;
      });
    });

    events.sort(function (a, b) { return String(a.date).localeCompare(String(b.date)); });
    return events;
  }

  /** KPI cua 1 seller trong 1 keyword (prompt muc 13). */
  function buildSellerSummary(seller, dates, options) {
    var series = buildSellerSeries(seller, dates, options);
    var current = lastPoint(series);
    var first = firstPoint(series);
    var lastIndex = dates.length - 1;

    var activeListings = (seller.listings || []).filter(function (listing) {
      var snapshot = listingSnapshotAt(listing, lastIndex);
      return snapshot && snapshot.status === 'ACTIVE';
    });
    var activePrices = activeListings.map(function (listing) {
      var snapshot = listingSnapshotAt(listing, lastIndex);
      return snapshot ? snapshot.price : null;
    }).filter(function (price) { return isFinite(price); });

    var lastUpdated = '';
    (seller.listings || []).forEach(function (listing) {
      (listing.snapshots || []).forEach(function (snapshot) {
        if (snapshot.date > lastUpdated) lastUpdated = snapshot.date;
      });
    });

    return {
      seller: seller.seller,
      series: series,
      current: current,
      representativeListingId: current ? current.listingId : null,
      representativePrice: current ? current.price : null,
      changePct: current && first ? percentChange(current.price, first.price) : null,
      activeListingCount: activeListings.length,
      totalListingCount: (seller.listings || []).length,
      activePriceMin: activePrices.length ? Math.min.apply(null, activePrices) : null,
      activePriceMax: activePrices.length ? Math.max.apply(null, activePrices) : null,
      lastUpdated: lastUpdated,
      events: buildSellerEvents(seller, dates, options),
    };
  }

  /** Thong ke cap listing dung cho bang va drawer (prompt muc 16). */
  function buildListingSummary(listing, dates, options) {
    var settings = resolveOptions(options);
    var snapshots = listing.snapshots || [];
    var prices = snapshots.map(function (snapshot) { return snapshot.price; });
    var current = snapshots.length ? snapshots[snapshots.length - 1] : null;
    var firstSnapshot = snapshots.length ? snapshots[0] : null;
    var eligible = settings.roleFilter === 'all'
      ? true
      : (CONFIG.eligibleRoles.indexOf(listing.role) !== -1 && !!current && current.price > settings.minPrice);
    var exclusionReason = null;
    if (!eligible) {
      if (CONFIG.eligibleRoles.indexOf(listing.role) === -1) exclusionReason = 'role';
      else if (!current) exclusionReason = 'noSnapshot';
      else exclusionReason = 'price';
    }

    return {
      listingId: listing.listingId,
      title: listing.title,
      url: listing.url,
      role: listing.role,
      status: current ? current.status : listing.status,
      condition: listing.condition,
      categoryName: listing.categoryName,
      firstSeen: listing.publishedAt,
      currentPrice: current ? current.price : null,
      firstPrice: firstSnapshot ? firstSnapshot.price : null,
      changePct: current && firstSnapshot ? percentChange(current.price, firstSnapshot.price) : null,
      minPrice: prices.length ? Math.min.apply(null, prices) : null,
      maxPrice: prices.length ? Math.max.apply(null, prices) : null,
      lastUpdated: current ? current.date : null,
      eligible: eligible,
      exclusionReason: exclusionReason,
      exclusionLabel: exclusionReason ? EXCLUSION_REASONS[exclusionReason] : '',
      priceSeries: dates.map(function (date, index) {
        var snapshot = listingSnapshotAt(listing, index);
        return snapshot && listing.firstSeenIndex <= index ? snapshot.price : null;
      }),
    };
  }

  /** KPI tong quan keyword (prompt muc 8). */
  function buildKeywordSummary(entry, options) {
    var dates = entry.dates || [];
    var summaries = (entry.sellers || []).map(function (seller) {
      return buildSellerSummary(seller, dates, options);
    });
    var representativePrices = summaries
      .map(function (summary) { return summary.representativePrice; })
      .filter(function (price) { return isFinite(price); });

    var listingCount = 0;
    var eligibleListingCount = 0;
    var outOfStock = 0;
    var ended = 0;
    var lastIndex = dates.length - 1;
    (entry.sellers || []).forEach(function (seller) {
      (seller.listings || []).forEach(function (listing) {
        listingCount += 1;
        var summary = buildListingSummary(listing, dates, options);
        if (summary.eligible) eligibleListingCount += 1;
        var snapshot = listingSnapshotAt(listing, lastIndex);
        if (snapshot && snapshot.status === 'OUT_OF_STOCK') outOfStock += 1;
        if (snapshot && snapshot.status === 'ENDED') ended += 1;
      });
    });

    var risingSellers = summaries.filter(function (summary) { return summary.changePct > 0.5; }).length;
    var fallingSellers = summaries.filter(function (summary) { return summary.changePct < -0.5; }).length;

    return {
      keyword: entry.keyword,
      label: entry.label,
      marketplace: entry.marketplace,
      dates: dates,
      sellerSummaries: summaries,
      sellerCount: summaries.length,
      listingCount: listingCount,
      eligibleListingCount: eligibleListingCount,
      medianPrice: median(representativePrices),
      minPrice: representativePrices.length ? Math.min.apply(null, representativePrices) : null,
      maxPrice: representativePrices.length ? Math.max.apply(null, representativePrices) : null,
      outOfStockCount: outOfStock,
      endedCount: ended,
      multiListingSellerCount: summaries.filter(function (summary) { return summary.totalListingCount > 1; }).length,
      risingSellerCount: risingSellers,
      fallingSellerCount: fallingSellers,
    };
  }

  /** Alert panel (prompt muc 11). Sinh tu du lieu, khong hard-code. */
  function buildKeywordAlerts(entry, options) {
    var dates = entry.dates || [];
    var alerts = [];

    (entry.sellers || []).forEach(function (seller) {
      var summary = buildSellerSummary(seller, dates, options);
      var events = summary.events;

      events.forEach(function (event) {
        if (event.type === EVENT_TYPES.PRICE_CHANGED && event.changePct !== null && event.changePct <= -CONFIG.priceDropWarningPct) {
          alerts.push({
            id: 'drop::' + seller.seller + '::' + event.date,
            type: 'PRICE_DROP',
            severity: event.changePct <= -CONFIG.priceDropCriticalPct ? 'critical' : 'warning',
            seller: seller.seller,
            date: event.date,
            title: seller.seller + ' giảm giá mạnh',
            headline: formatPercent(Math.abs(event.changePct)),
            body: event.listingId + ': ' + formatCurrency(event.previousPrice) + ' → ' + formatCurrency(event.price)
              + ' ngày ' + formatDayMonth(event.date) + '.',
          });
        }
        if (event.type === EVENT_TYPES.NEW_LISTING_PRICE_SHIFT) {
          var shift = event.changePct === null ? 0 : event.changePct;
          alerts.push({
            id: 'shift::' + seller.seller + '::' + event.date,
            type: 'NEW_LISTING_PRICE_SHIFT',
            severity: Math.abs(shift) >= CONFIG.priceShiftWarningPct ? 'critical' : 'warning',
            seller: seller.seller,
            date: event.date,
            title: seller.seller + ' đăng listing mới',
            headline: (shift >= 0 ? '▲' : '▼') + ' ' + formatPercent(Math.abs(shift)),
            body: 'Listing cũ ' + event.previousListingId + ' ' + formatCurrency(event.previousPrice)
              + ' → listing mới ' + event.listingId + ' ' + formatCurrency(event.price)
              + '. Đây là đổi listing đại diện, không phải listing cũ tăng giá.',
          });
        }
        if (event.type === EVENT_TYPES.STATUS_CHANGED) {
          alerts.push({
            id: 'status::' + seller.seller + '::' + event.listingId + '::' + event.date,
            type: 'STATUS_CHANGE',
            severity: event.toStatus === 'ENDED' ? 'warning' : 'info',
            seller: seller.seller,
            date: event.date,
            title: seller.seller + ' đổi trạng thái listing',
            headline: event.toStatus,
            body: event.listingId + ': ' + event.fromStatus + ' → ' + event.toStatus
              + ' ngày ' + formatDayMonth(event.date) + '.',
          });
        }
      });

      if (summary.activeListingCount >= CONFIG.multipleActiveThreshold + 1) {
        alerts.push({
          id: 'multi::' + seller.seller,
          type: 'MULTIPLE_ACTIVE_LISTINGS',
          severity: 'info',
          seller: seller.seller,
          date: summary.lastUpdated,
          title: seller.seller + ' đang có ' + summary.activeListingCount + ' listing ACTIVE',
          headline: formatCurrency(summary.activePriceMin) + ' – ' + formatCurrency(summary.activePriceMax),
          body: 'Latest listing: ' + summary.representativeListingId + ' ' + formatCurrency(summary.representativePrice)
            + '. Giá đại diện không phải giá duy nhất seller đang bán.',
        });
      }
    });

    var severityRank = { critical: 0, warning: 1, info: 2 };
    alerts.sort(function (a, b) {
      if (severityRank[a.severity] !== severityRank[b.severity]) return severityRank[a.severity] - severityRank[b.severity];
      return String(b.date).localeCompare(String(a.date));
    });
    return alerts;
  }

  /** Classification audit - listing bi loai va ly do (prompt muc 18). */
  function buildClassificationAudit(entry, options) {
    var dates = entry.dates || [];
    var rows = [];
    (entry.sellers || []).forEach(function (seller) {
      (seller.listings || []).forEach(function (listing) {
        var summary = buildListingSummary(listing, dates, options);
        if (summary.eligible) return;
        rows.push({
          seller: seller.seller,
          listingId: summary.listingId,
          role: summary.role,
          currentPrice: summary.currentPrice,
          status: summary.status,
          url: summary.url,
          reason: summary.exclusionReason,
          reasonLabel: summary.exclusionLabel,
        });
      });
    });
    return rows;
  }

  /** Truc hien thi theo ky: chi tiet / tuan / thang (prompt muc 7). */
  function buildAxis(dates, period) {
    if (!dates || !dates.length) return [];
    if (period === 'week' || period === 'month') {
      var buckets = [];
      var seen = {};
      dates.forEach(function (date, index) {
        var key = period === 'week' ? isoWeekKey(date) : monthKey(date);
        if (seen[key] === undefined) {
          seen[key] = buckets.length;
          buckets.push({ key: key, index: index, date: date });
        } else {
          buckets[seen[key]].index = index;
          buckets[seen[key]].date = date;
        }
      });
      return buckets.map(function (bucket) {
        return {
          index: bucket.index,
          date: bucket.date,
          label: period === 'week' ? 'T' + bucket.key.split('-W')[1] : bucket.key.slice(5) + '/' + bucket.key.slice(0, 4),
        };
      });
    }
    return dates.map(function (date, index) {
      return { index: index, date: date, label: formatDayMonth(date) };
    });
  }

  function findKeyword(dataset, keyword) {
    var keywords = (dataset && dataset.keywords) || [];
    for (var i = 0; i < keywords.length; i += 1) {
      if (keywords[i].keyword === keyword) return keywords[i];
    }
    return keywords[0] || null;
  }

  function findSeller(entry, sellerName) {
    var sellers = (entry && entry.sellers) || [];
    for (var i = 0; i < sellers.length; i += 1) {
      if (sellers[i].seller === sellerName) return sellers[i];
    }
    return null;
  }

  // ==================================================================
  // 4. DATA SOURCE - du lieu that tu HQA service qua portal-bff
  // ==================================================================
  //
  //   GET /api/v1/hqa/keyword-seller/keywords   -> danh sach keyword + counter
  //   GET /api/v1/hqa/keyword-seller/analytics  -> payload day du cua 1 keyword
  //   GET /api/v1/hqa/keyword-seller/export     -> CSV
  //
  // Backend da tinh san role (whole_product) bang listing_classifier va da ap
  // rule "gia dai dien", nen phia UI chi con viec ve. Cac ham trong
  // `KeywordSellerAnalytics.logic` van duoc giu de render lai tuc thi khi doi
  // nguong gia / vai tro ma khong phai goi lai API.

  var API_BASE = '/api/v1/hqa/keyword-seller';

  /**
   * Host app (app.js) co the bom ham goi API rieng de dinh kem Authorization
   * header va tu dong refresh token.
   */
  var apiClient = function defaultApiClient(path) {
    return fetch(path, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    }).then(function (response) {
      if (!response.ok) {
        var error = new Error('HTTP ' + response.status);
        error.status = response.status;
        throw error;
      }
      return response.json();
    });
  };

  function setApiClient(client) {
    if (typeof client !== 'function') throw new TypeError('setApiClient expects a function');
    apiClient = client;
  }

  function buildQuery(params) {
    var parts = [];
    Object.keys(params || {}).forEach(function (key) {
      var value = params[key];
      if (value === undefined || value === null || value === '') return;
      parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value));
    });
    return parts.length ? ('?' + parts.join('&')) : '';
  }

  function analyticsQuery(keyword) {
    return {
      keyword: keyword,
      min_price: view.minPrice,
      include_all_roles: view.roleFilter === 'all' ? 'true' : 'false',
    };
  }

  function exportUrl(keyword) {
    return API_BASE + '/export' + buildQuery(analyticsQuery(keyword));
  }

  /** Doi payload backend ve dung shape ma `normalizeDataset` mong doi. */
  function adaptKeywordPayload(payload) {
    var sellers = ((payload && payload.sellers) || []).map(function (seller) {
      var listings = (seller.listings || []).map(function (listing) {
        var snapshots = {};
        (listing.sparkline || []).forEach(function (point) {
          if (!point || !point.date) return;
          snapshots[point.date] = { price: point.price, status: point.status || 'ACTIVE' };
        });
        return {
          listingId: listing.listing_id,
          title: listing.title || listing.listing_id,
          url: listing.url || '',
          role: listing.role || 'whole_product',
          condition: listing.condition || '',
          categoryName: listing.category_name || '',
          status: listing.status || 'ACTIVE',
          publishedAt: listing.published_at || listing.first_seen || null,
          snapshots: snapshots,
        };
      });
      return { seller: seller.seller, listings: listings };
    });

    return {
      keyword: (payload && payload.keyword) || '',
      label: (payload && payload.keyword) || '',
      marketplace: 'ebay',
      sellers: sellers,
    };
  }

  function fetchKeywordOptions() {
    return apiClient(API_BASE + '/keywords' + buildQuery({ min_price: view.minPrice }))
      .then(function (payload) {
        return ((payload && payload.items) || []).map(function (item) {
          return {
            keyword: item.keyword,
            sellerCount: item.seller_count || 0,
            listingCount: item.listing_count || 0,
            medianPrice: (item.median_price === null || item.median_price === undefined)
              ? null : Number(item.median_price),
          };
        });
      });
  }

  function fetchKeywordAnalytics(keyword) {
    return apiClient(API_BASE + '/analytics' + buildQuery(analyticsQuery(keyword)))
      .then(function (payload) {
        return { raw: payload, entry: adaptKeywordPayload(payload) };
      });
  }

  var dataSource = {
    listKeywords: fetchKeywordOptions,
    loadKeyword: fetchKeywordAnalytics,
  };

  /**
   * Thay toan bo tang du lieu. Nhan { listKeywords, loadKeyword }.
   * Van chap nhan mot ham duy nhat (dang cu) de tuong thich nguoc.
   */
  function setDataSource(loader) {
    if (typeof loader === 'function') {
      dataSource = {
        listKeywords: function () {
          return Promise.resolve(loader({})).then(function (raw) {
            return ((raw && raw.keywords) || []).map(function (entry) {
              return { keyword: entry.keyword, sellerCount: 0, listingCount: 0, medianPrice: null };
            });
          });
        },
        loadKeyword: function (keyword) {
          return Promise.resolve(loader({ keyword: keyword })).then(function (raw) {
            var match = ((raw && raw.keywords) || []).filter(function (entry) {
              return entry.keyword === keyword;
            })[0];
            return { raw: null, entry: match || null };
          });
        },
      };
      return;
    }
    if (!loader || typeof loader.loadKeyword !== 'function') {
      throw new TypeError('setDataSource expects { listKeywords, loadKeyword }');
    }
    dataSource = loader;
  }

  // ==================================================================
  // 5. VIEW STATE
  // ==================================================================

  var view = {
    root: null,
    dataset: null,
    // Danh sach keyword lay tu DB (dung cho selector, ke ca keyword chua tai).
    keywordOptions: [],
    // Cache theo keyword de doi qua lai khong goi lai API.
    rawKeywords: [],
    loadedKeywords: {},
    serverPayloads: {},
    loading: false,
    error: '',
    keyword: '',
    period: 'detail',
    roleFilter: 'whole_product',
    minPrice: CONFIG.minPrice,
    expandAll: true,
    // sellerName -> bool. Khong co key => dung mac dinh cua expandAll.
    expandedSellers: {},
    highlightSeller: '',
    drawerSeller: '',
    keywordSearch: '',
    keywordPickerOpen: false,
    keyboardBound: false,
  };

  /**
   * Thong so hien thi cua 1 keyword tren selector.
   * Keyword da tai -> tinh lai tai cho theo nguong gia dang chon (chinh xac).
   * Keyword chua tai -> dung counter tu DB.
   */
  function keywordMeta(keywordValue) {
    var entry = findKeyword(view.dataset, keywordValue);
    if (entry) {
      var summary = buildKeywordSummary(entry, currentOptions());
      return {
        sellerCount: summary.sellerCount,
        listingCount: summary.listingCount,
        medianPrice: summary.medianPrice,
        alertCount: buildKeywordAlerts(entry, currentOptions()).length,
        loaded: true,
      };
    }
    var option = view.keywordOptions.filter(function (item) {
      return item.keyword === keywordValue;
    })[0] || {};
    return {
      sellerCount: option.sellerCount || 0,
      listingCount: option.listingCount || 0,
      medianPrice: option.medianPrice === undefined ? null : option.medianPrice,
      alertCount: null,
      loaded: false,
    };
  }

  function currentOptions() {
    return { minPrice: view.minPrice, roleFilter: view.roleFilter };
  }

  function currentKeywordEntry() {
    return findKeyword(view.dataset, view.keyword);
  }

  function sellerColor(entry, sellerName) {
    var index = (entry.sellers || []).findIndex(function (seller) { return seller.seller === sellerName; });
    return CONFIG.colors[(index < 0 ? 0 : index) % CONFIG.colors.length];
  }

  // ==================================================================
  // 6. RENDER - SVG CHARTS
  // ==================================================================

  function buildChartGeometry(axis, seriesList) {
    var width = 960;
    var height = 340;
    var padding = { left: 76, right: 26, top: 26, bottom: 46 };
    var values = [];
    seriesList.forEach(function (item) {
      item.points.forEach(function (point) { if (point) values.push(point.price); });
    });
    if (!values.length) values = [0, 1];
    var rawMin = Math.min.apply(null, values);
    var rawMax = Math.max.apply(null, values);
    var pad = Math.max((rawMax - rawMin) * 0.12, 25);
    var yMin = Math.max(0, Math.floor((rawMin - pad) / 50) * 50);
    var yMax = Math.ceil((rawMax + pad) / 50) * 50;
    if (yMax === yMin) yMax = yMin + 50;
    var plotWidth = width - padding.left - padding.right;
    var plotHeight = height - padding.top - padding.bottom;
    var divisor = Math.max(1, axis.length - 1);

    return {
      width: width,
      height: height,
      padding: padding,
      yMin: yMin,
      yMax: yMax,
      x: function (position) {
        return axis.length === 1
          ? padding.left + plotWidth / 2
          : padding.left + position * (plotWidth / divisor);
      },
      y: function (value) {
        return padding.top + ((yMax - value) / (yMax - yMin)) * plotHeight;
      },
    };
  }

  function renderTrendChart(entry, axis, summaries) {
    var seriesList = summaries.map(function (summary) {
      return {
        seller: summary.seller,
        color: sellerColor(entry, summary.seller),
        points: axis.map(function (tick) { return summary.series[tick.index] || null; }),
      };
    });

    var geometry = buildChartGeometry(axis, seriesList);
    var markup = '';

    for (var i = 0; i <= 4; i += 1) {
      var value = geometry.yMin + ((geometry.yMax - geometry.yMin) * i) / 4;
      var lineY = geometry.y(value);
      markup += '<line x1="' + geometry.padding.left + '" y1="' + lineY + '" x2="' + (geometry.width - geometry.padding.right)
        + '" y2="' + lineY + '" class="ks-grid-line" />';
      markup += '<text x="' + (geometry.padding.left - 10) + '" y="' + (lineY + 4) + '" text-anchor="end" class="ks-axis-text">'
        + escapeHtml(formatCurrency(Math.round(value))) + '</text>';
    }

    var labelStep = Math.ceil(axis.length / 12);
    axis.forEach(function (tick, position) {
      if (position % labelStep !== 0 && position !== axis.length - 1) return;
      markup += '<text x="' + geometry.x(position) + '" y="' + (geometry.height - 16) + '" text-anchor="middle" class="ks-axis-text">'
        + escapeHtml(tick.label) + '</text>';
    });

    seriesList.forEach(function (series, seriesIndex) {
      var dimmed = view.highlightSeller && view.highlightSeller !== series.seller;
      var segments = [];
      var previousListingId = null;

      series.points.forEach(function (point, position) {
        if (!point) return;
        segments.push({ x: geometry.x(position), y: geometry.y(point.price), point: point, position: position });
        if (previousListingId && previousListingId !== point.listingId && !dimmed) {
          markup += '<line x1="' + geometry.x(position) + '" y1="' + geometry.padding.top
            + '" x2="' + geometry.x(position) + '" y2="' + (geometry.height - geometry.padding.bottom)
            + '" stroke="' + series.color + '" stroke-dasharray="4 4" opacity="0.5" />';
          markup += '<text x="' + (geometry.x(position) + 5) + '" y="' + (geometry.padding.top + 12 + seriesIndex * 13)
            + '" class="ks-marker-text" fill="' + series.color + '">▲ New listing: ' + escapeHtml(point.listingId) + '</text>';
        }
        previousListingId = point.listingId;
      });

      if (!segments.length) return;
      markup += '<polyline points="' + segments.map(function (segment) { return segment.x + ',' + segment.y; }).join(' ')
        + '" fill="none" stroke="' + series.color + '" stroke-width="' + (view.highlightSeller === series.seller ? 4 : 2.75)
        + '" stroke-linecap="round" stroke-linejoin="round" class="ks-line' + (dimmed ? ' is-dimmed' : '')
        + '" data-ks-seller="' + escapeHtml(series.seller) + '" tabindex="0" role="button"'
        + ' aria-label="Đường giá của ' + escapeHtml(series.seller) + '" />';

      segments.forEach(function (segment) {
        markup += '<circle cx="' + segment.x + '" cy="' + segment.y + '" r="' + (view.highlightSeller === series.seller ? 5.5 : 4.25)
          + '" fill="' + series.color + '" stroke="#ffffff" stroke-width="2" class="ks-point' + (dimmed ? ' is-dimmed' : '')
          + '" data-ks-seller="' + escapeHtml(series.seller) + '"'
          + ' data-ks-listing="' + escapeHtml(segment.point.listingId) + '"'
          + ' data-ks-date="' + escapeHtml(segment.point.date) + '"'
          + ' data-ks-price="' + escapeHtml(String(segment.point.price)) + '"'
          + ' data-ks-status="' + escapeHtml(segment.point.status) + '" />';
      });
    });

    return '<svg viewBox="0 0 ' + geometry.width + ' ' + geometry.height + '" class="ks-chart-svg" role="img"'
      + ' aria-label="Xu hướng giá đại diện theo seller cho keyword ' + escapeHtml(entry.keyword) + '">'
      + markup + '</svg>';
  }

  function renderSparkline(values, color) {
    var valid = values.filter(function (value) { return isFinite(value) && value !== null; });
    if (valid.length < 2) return '<div class="ks-spark-empty">Chưa đủ dữ liệu</div>';
    var min = Math.min.apply(null, valid);
    var max = Math.max.apply(null, valid);
    var width = 280;
    var height = 52;
    var divisor = Math.max(1, values.length - 1);
    var points = [];
    values.forEach(function (value, index) {
      if (value === null || !isFinite(value)) return;
      var x = index * (width / divisor);
      var y = height - 6 - ((value - min) / (max - min || 1)) * (height - 12);
      points.push(x + ',' + y);
    });
    return '<svg viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none" class="ks-spark-svg" aria-hidden="true">'
      + '<polyline points="' + points.join(' ') + '" fill="none" stroke="' + color
      + '" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" /></svg>';
  }

  /** Prompt muc 17: bieu do drill-down - moi line 1 listing + line dam = gia dai dien. */
  function renderListingDrillChart(entry, seller, summary) {
    var dates = entry.dates || [];
    var axis = dates.map(function (date, index) { return { index: index, date: date, label: formatDayMonth(date) }; });
    var listingSeries = (seller.listings || []).map(function (listing, index) {
      var listingSummary = buildListingSummary(listing, dates, currentOptions());
      return {
        seller: listing.listingId,
        color: CONFIG.colors[(index + 3) % CONFIG.colors.length],
        points: listingSummary.priceSeries.map(function (price, position) {
          return price === null ? null : { price: price, listingId: listing.listingId, date: dates[position] };
        }),
      };
    });
    var representativeSeries = {
      seller: '__representative__',
      color: '#182230',
      points: summary.series,
    };
    var all = listingSeries.concat([representativeSeries]);
    var geometry = buildChartGeometry(axis, all);
    var markup = '';

    for (var i = 0; i <= 3; i += 1) {
      var value = geometry.yMin + ((geometry.yMax - geometry.yMin) * i) / 3;
      var lineY = geometry.y(value);
      markup += '<line x1="' + geometry.padding.left + '" y1="' + lineY + '" x2="' + (geometry.width - geometry.padding.right)
        + '" y2="' + lineY + '" class="ks-grid-line" />';
      markup += '<text x="' + (geometry.padding.left - 10) + '" y="' + (lineY + 4) + '" text-anchor="end" class="ks-axis-text">'
        + escapeHtml(formatCurrency(Math.round(value))) + '</text>';
    }
    var labelStep = Math.ceil(axis.length / 8);
    axis.forEach(function (tick, position) {
      if (position % labelStep !== 0 && position !== axis.length - 1) return;
      markup += '<text x="' + geometry.x(position) + '" y="' + (geometry.height - 16) + '" text-anchor="middle" class="ks-axis-text">'
        + escapeHtml(tick.label) + '</text>';
    });

    all.forEach(function (series) {
      var isRepresentative = series.seller === '__representative__';
      var coordinates = [];
      series.points.forEach(function (point, position) {
        if (!point) return;
        coordinates.push(geometry.x(position) + ',' + geometry.y(point.price));
      });
      if (coordinates.length < 1) return;
      markup += '<polyline points="' + coordinates.join(' ') + '" fill="none" stroke="' + series.color
        + '" stroke-width="' + (isRepresentative ? 3.5 : 1.75) + '"'
        + (isRepresentative ? '' : ' stroke-dasharray="5 4"')
        + ' stroke-linecap="round" stroke-linejoin="round" opacity="' + (isRepresentative ? 1 : 0.85) + '" />';
    });

    var legend = listingSeries.map(function (series) {
      return '<span class="ks-drill-legend-item"><i style="background:' + series.color + '"></i>'
        + escapeHtml(series.seller) + '</span>';
    }).join('');

    return '<svg viewBox="0 0 ' + geometry.width + ' ' + geometry.height + '" class="ks-chart-svg" role="img"'
      + ' aria-label="Lịch sử giá từng listing của ' + escapeHtml(seller.seller) + '">' + markup + '</svg>'
      + '<div class="ks-drill-legend"><span class="ks-drill-legend-item"><i style="background:#182230"></i>'
      + 'Giá đại diện seller</span>' + legend + '</div>';
  }

  // ==================================================================
  // 7. RENDER - PANELS
  // ==================================================================

  function statusPill(status) {
    var normalized = String(status || '').toUpperCase();
    var modifier = 'ks-pill--active';
    if (normalized === 'OUT_OF_STOCK') modifier = 'ks-pill--out';
    else if (normalized === 'ENDED') modifier = 'ks-pill--ended';
    else if (normalized === 'NEW_LISTING') modifier = 'ks-pill--new';
    return '<span class="ks-pill ' + modifier + '">' + escapeHtml(normalized || '—') + '</span>';
  }

  function changeCell(changePct) {
    if (changePct === null || changePct === undefined || !isFinite(changePct)) {
      return '<span class="ks-change ks-change--flat">—</span>';
    }
    if (Math.abs(changePct) < 0.05) return '<span class="ks-change ks-change--flat">±0%</span>';
    var down = changePct < 0;
    return '<span class="ks-change ' + (down ? 'ks-change--down' : 'ks-change--up') + '">'
      + (down ? '▼' : '▲') + ' ' + formatPercent(Math.abs(changePct)) + '</span>';
  }

  function renderToolbar() {
    var search = view.keywordSearch.trim().toLowerCase();
    var filtered = view.keywordOptions.filter(function (item) {
      return !search || item.keyword.toLowerCase().indexOf(search) !== -1;
    });

    var options = filtered.map(function (item) {
      var meta = keywordMeta(item.keyword);
      var alertLabel = meta.alertCount === null ? '' : (' · ' + meta.alertCount + ' alert');
      return '<button type="button" class="ks-combo-option' + (item.keyword === view.keyword ? ' is-active' : '')
        + '" data-ks-keyword="' + escapeHtml(item.keyword) + '" role="option"'
        + ' aria-selected="' + (item.keyword === view.keyword ? 'true' : 'false') + '">'
        + '<b>' + escapeHtml(item.keyword) + '</b>'
        + '<small>' + meta.sellerCount + ' seller · ' + meta.listingCount + ' listing · median '
        + escapeHtml(formatCurrency(meta.medianPrice)) + alertLabel + '</small></button>';
    }).join('');

    return ''
      + '<div class="ks-toolbar">'
      + '  <div class="ks-field ks-field--combo">'
      + '    <label id="ks-keyword-label">Keyword</label>'
      + '    <button type="button" class="ks-combo-trigger" id="ks-keyword-trigger" aria-haspopup="listbox"'
      + '      aria-expanded="' + (view.keywordPickerOpen ? 'true' : 'false') + '" aria-labelledby="ks-keyword-label">'
      + '      <span>' + escapeHtml(view.keyword || 'Chọn keyword') + '</span><i aria-hidden="true">▾</i></button>'
      + '    <div class="ks-combo-pop" id="ks-keyword-pop"' + (view.keywordPickerOpen ? '' : ' hidden') + ' role="listbox">'
      + '      <input type="search" id="ks-keyword-search" class="ks-combo-search" placeholder="Tìm keyword..."'
      + '        value="' + escapeHtml(view.keywordSearch) + '" aria-label="Tìm keyword" />'
      + '      <div class="ks-combo-list">' + (options || '<div class="ks-combo-empty">Không tìm thấy keyword.</div>') + '</div>'
      + '    </div>'
      + '  </div>'
      + '  <div class="ks-field">'
      + '    <label for="ks-role">Vai trò</label>'
      + '    <select id="ks-role">' + CONFIG.roles.map(function (role) {
        return '<option value="' + role.key + '"' + (view.roleFilter === role.key ? ' selected' : '') + '>'
          + escapeHtml(role.label) + '</option>';
      }).join('') + '</select>'
      + '  </div>'
      + '  <div class="ks-field">'
      + '    <label for="ks-min-price">Ngưỡng giá</label>'
      + '    <div class="ks-price-input"><span>&gt; $</span>'
      + '      <input type="number" id="ks-min-price" min="0" step="50" value="' + escapeHtml(String(view.minPrice)) + '" />'
      + '    </div>'
      + '  </div>'
      + '  <div class="ks-segment" role="group" aria-label="Kỳ hiển thị">' + CONFIG.periods.map(function (period) {
        return '<button type="button" data-ks-period="' + period.key + '"'
          + ' class="' + (view.period === period.key ? 'is-active' : '') + '"'
          + ' aria-pressed="' + (view.period === period.key ? 'true' : 'false') + '">'
          + escapeHtml(period.label) + '</button>';
      }).join('') + '</div>'
      + '  <div class="ks-toolbar-actions">'
      + '    <button type="button" class="ks-icon-button" id="ks-refresh" title="Tải lại dữ liệu" aria-label="Tải lại dữ liệu">↻</button>'
      + '    <button type="button" class="ks-export-button" id="ks-export">⇩ Xuất CSV</button>'
      + '  </div>'
      + '</div>';
  }

  function renderKeywordNav() {
    // Chi hien thi mot so keyword dau de thanh nav khong bi tran khi DB co nhieu keyword.
    var visible = view.keywordOptions.slice(0, CONFIG.keywordNavLimit);
    if (!visible.length) return '';
    return '<div class="ks-keyword-nav">' + visible.map(function (item) {
      var meta = keywordMeta(item.keyword);
      var alertLabel = meta.alertCount === null ? 'Chưa tải' : (meta.alertCount + ' cảnh báo');
      return '<button type="button" class="ks-keyword-card' + (item.keyword === view.keyword ? ' is-active' : '')
        + '" data-ks-keyword="' + escapeHtml(item.keyword) + '">'
        + '<b>' + escapeHtml(item.keyword) + '</b>'
        + '<span>' + meta.sellerCount + ' sellers · ' + meta.listingCount + ' listings · median '
        + escapeHtml(formatCurrency(meta.medianPrice)) + '</span>'
        + '<span class="ks-keyword-card-alerts">' + escapeHtml(alertLabel) + '</span></button>';
    }).join('') + '</div>';
  }

  function renderAlertPanel(alerts) {
    if (!alerts.length) {
      return '<div class="ks-alerts"><div class="ks-alert-empty">Không có cảnh báo nào trong kỳ hiện tại.</div></div>';
    }
    var severityLabel = { critical: '● NGHIÊM TRỌNG', warning: '● CẢNH BÁO', info: '● THÔNG TIN' };
    return '<div class="ks-alerts">' + alerts.slice(0, 8).map(function (alert) {
      return '<article class="ks-alert ks-alert--' + alert.severity + '" data-ks-alert-seller="' + escapeHtml(alert.seller) + '">'
        + '<div class="ks-alert-severity">' + severityLabel[alert.severity] + '</div>'
        + '<h4>' + escapeHtml(alert.title) + '</h4>'
        + '<strong>' + escapeHtml(alert.headline) + '</strong>'
        + '<p>' + escapeHtml(alert.body) + '</p>'
        + '<button type="button" class="ks-alert-action" data-ks-open-seller="' + escapeHtml(alert.seller) + '">Xem seller →</button>'
        + '</article>';
    }).join('') + '</div>';
  }

  function renderKeywordSummaryPanel(summary) {
    return ''
      + '<aside class="ks-summary">'
      + '  <h3>Tổng quan keyword</h3>'
      + '  <div class="ks-summary-keyword">' + escapeHtml(summary.keyword) + '</div>'
      + '  <div class="ks-summary-label">' + escapeHtml(summary.label) + '</div>'
      + '  <div class="ks-summary-median">' + escapeHtml(formatCurrency(summary.medianPrice)) + '</div>'
      + '  <div class="ks-summary-caption">Median giá đại diện hiện tại của các seller</div>'
      + '  <div class="ks-summary-grid">'
      + '    <div class="ks-stat"><span>Sellers</span><b>' + summary.sellerCount + '</b></div>'
      + '    <div class="ks-stat"><span>Listings đủ điều kiện</span><b>' + summary.eligibleListingCount + '</b></div>'
      + '    <div class="ks-stat"><span>Min seller</span><b>' + escapeHtml(formatCurrency(summary.minPrice)) + '</b></div>'
      + '    <div class="ks-stat"><span>Max seller</span><b>' + escapeHtml(formatCurrency(summary.maxPrice)) + '</b></div>'
      + '    <div class="ks-stat"><span>Seller nhiều listing</span><b>' + summary.multiListingSellerCount + '</b></div>'
      + '    <div class="ks-stat"><span>Hết hàng / Ended</span><b>' + summary.outOfStockCount + ' / ' + summary.endedCount + '</b></div>'
      + '    <div class="ks-stat"><span>Seller giảm giá</span><b class="ks-text-down">' + summary.fallingSellerCount + '</b></div>'
      + '    <div class="ks-stat"><span>Seller tăng giá</span><b class="ks-text-up">' + summary.risingSellerCount + '</b></div>'
      + '  </div>'
      + '  <div class="ks-rule-box">'
      + '    <h4>Quy tắc đang áp dụng</h4>'
      + '    <ul>'
      + '      <li>Keyword là phạm vi thống kê.</li>'
      + '      <li>Mỗi line là một seller.</li>'
      + '      <li>Listing đăng mới nhất quyết định giá đại diện.</li>'
      + '      <li>Listing cũ vẫn giữ nguyên history.</li>'
      + '      <li>' + escapeHtml(view.roleFilter === 'all' ? 'Tất cả vai trò' : 'Chỉ whole product')
      + ' · giá &gt; ' + escapeHtml(formatCurrency(view.minPrice)) + '.</li>'
      + '    </ul>'
      + '  </div>'
      + '</aside>';
  }

  function renderLegend(entry, summaries) {
    return '<div class="ks-legend">' + summaries.map(function (summary) {
      var color = sellerColor(entry, summary.seller);
      var dimmed = view.highlightSeller && view.highlightSeller !== summary.seller;
      return '<button type="button" class="ks-legend-card' + (dimmed ? ' is-dimmed' : '')
        + (view.highlightSeller === summary.seller ? ' is-active' : '') + '"'
        + ' data-ks-open-seller="' + escapeHtml(summary.seller) + '">'
        + '<b><i class="ks-dot" style="background:' + color + '"></i>' + escapeHtml(summary.seller) + '</b>'
        + '<small>' + summary.totalListingCount + ' listing · ' + summary.activeListingCount + ' active</small>'
        + '<span class="ks-legend-meta">Đại diện: ' + escapeHtml(summary.representativeListingId || '—')
        + '<br/>Giá hiện tại: ' + escapeHtml(formatCurrency(summary.representativePrice))
        + ' · ' + changeCell(summary.changePct) + '</span></button>';
    }).join('') + '</div>';
  }

  function renderSellerTable(entry, summaries) {
    var dates = entry.dates || [];
    var rows = summaries.map(function (summary) {
      var seller = findSeller(entry, summary.seller);
      var expanded = view.expandedSellers[summary.seller] === undefined
        ? view.expandAll
        : view.expandedSellers[summary.seller];
      var color = sellerColor(entry, summary.seller);

      var sellerRow = '<tr class="ks-row-seller' + (view.highlightSeller === summary.seller ? ' is-active' : '')
        + '" data-ks-toggle-seller="' + escapeHtml(summary.seller) + '">'
        + '<td><span class="ks-caret">' + (expanded ? '▾' : '▸') + '</span>'
        + '<i class="ks-dot" style="background:' + color + '"></i>' + escapeHtml(summary.seller) + '</td>'
        + '<td>' + escapeHtml(summary.representativeListingId || '—') + '</td>'
        + '<td>—</td>'
        + '<td><b>' + escapeHtml(formatCurrency(summary.representativePrice)) + '</b></td>'
        + '<td>' + changeCell(summary.changePct) + '</td>'
        + '<td>' + escapeHtml(formatCurrency(summary.activePriceMin)) + '</td>'
        + '<td>' + escapeHtml(formatCurrency(summary.activePriceMax)) + '</td>'
        + '<td>seller</td>'
        + '<td>' + summary.activeListingCount + ' active</td>'
        + '<td><span class="ks-badge ks-badge--rep">Latest listing</span></td>'
        + '<td>' + escapeHtml(summary.lastUpdated || '—') + '</td>'
        + '<td><button type="button" class="ks-link-button" data-ks-open-seller="' + escapeHtml(summary.seller)
        + '">Drill-down</button></td></tr>';

      if (!expanded) return sellerRow;

      var listingRows = (seller.listings || []).map(function (listing) {
        var listingSummary = buildListingSummary(listing, dates, currentOptions());
        var isRepresentative = summary.representativeListingId === listingSummary.listingId;
        return '<tr class="ks-row-listing' + (listingSummary.eligible ? '' : ' is-excluded')
          + '" data-ks-open-seller="' + escapeHtml(summary.seller) + '">'
          + '<td class="ks-indent">' + escapeHtml(listingSummary.title) + '</td>'
          + '<td>' + escapeHtml(listingSummary.listingId) + '</td>'
          + '<td>' + escapeHtml(listingSummary.firstSeen || '—') + '</td>'
          + '<td>' + escapeHtml(formatCurrency(listingSummary.currentPrice)) + '</td>'
          + '<td>' + changeCell(listingSummary.changePct) + '</td>'
          + '<td>' + escapeHtml(formatCurrency(listingSummary.minPrice)) + '</td>'
          + '<td>' + escapeHtml(formatCurrency(listingSummary.maxPrice)) + '</td>'
          + '<td>' + escapeHtml(listingSummary.role) + '</td>'
          + '<td>' + statusPill(listingSummary.status) + '</td>'
          + '<td>' + (isRepresentative
            ? '<span class="ks-badge ks-badge--rep">Đại diện</span>'
            : (listingSummary.eligible
              ? '<span class="ks-badge ks-badge--history">History</span>'
              : '<span class="ks-badge ks-badge--excluded" title="' + escapeHtml(listingSummary.exclusionLabel) + '">Bị loại</span>'))
          + '</td>'
          + '<td>' + escapeHtml(listingSummary.lastUpdated || '—') + '</td>'
          + '<td><button type="button" class="ks-link-button" data-ks-open-url="' + escapeHtml(listingSummary.url)
          + '">Mở link ↗</button></td></tr>';
      }).join('');

      return sellerRow + listingRows;
    }).join('');

    return ''
      + '<section class="dashboard-panel ks-table-panel">'
      + '  <div class="dashboard-panel-heading">'
      + '    <div class="dashboard-panel-title-wrap"><span class="dashboard-panel-title">Seller → Listing đại diện → Listing lịch sử</span></div>'
      + '    <button type="button" class="ks-ghost-button" id="ks-toggle-rows">'
      + (view.expandAll ? 'Thu gọn tất cả' : 'Mở rộng tất cả') + '</button>'
      + '  </div>'
      + '  <div class="dashboard-panel-subtext">Click vào seller để mở drill-down; click "Mở link" để sang đúng listing trên marketplace.</div>'
      + '  <div class="ks-table-wrap"><table class="ks-table"><thead><tr>'
      + '<th>Seller / Listing</th><th>Listing ID</th><th>First seen</th><th>Giá hiện tại</th><th>% thay đổi</th>'
      + '<th>Min</th><th>Max</th><th>Vai trò</th><th>Status</th><th>Đại diện?</th><th>Cập nhật</th><th>Link</th>'
      + '</tr></thead><tbody>' + rows + '</tbody></table></div>'
      + '</section>';
  }

  function renderAuditPanel(auditRows) {
    if (!auditRows.length) return '';
    return ''
      + '<section class="dashboard-panel ks-audit-panel">'
      + '  <div class="dashboard-panel-heading"><div class="dashboard-panel-title-wrap">'
      + '<span class="dashboard-panel-title">Classification audit — listing bị loại khỏi phân tích</span></div>'
      + '<span class="dashboard-panel-meta">' + auditRows.length + ' listing</span></div>'
      + '  <div class="dashboard-panel-subtext">Các listing này không được chọn làm listing đại diện và không làm thay đổi đường giá seller.</div>'
      + '  <div class="ks-table-wrap"><table class="ks-table"><thead><tr>'
      + '<th>Seller</th><th>Listing ID</th><th>Vai trò</th><th>Giá</th><th>Status</th><th>Lý do loại</th><th>Link</th>'
      + '</tr></thead><tbody>' + auditRows.map(function (row) {
        return '<tr><td>' + escapeHtml(row.seller) + '</td><td>' + escapeHtml(row.listingId) + '</td>'
          + '<td>' + escapeHtml(row.role) + '</td><td>' + escapeHtml(formatCurrency(row.currentPrice)) + '</td>'
          + '<td>' + statusPill(row.status) + '</td>'
          + '<td><span class="ks-badge ks-badge--excluded">' + escapeHtml(row.reasonLabel) + '</span></td>'
          + '<td><button type="button" class="ks-link-button" data-ks-open-url="' + escapeHtml(row.url) + '">Mở link ↗</button></td></tr>';
      }).join('') + '</tbody></table></div>'
      + '</section>';
  }

  // ==================================================================
  // 8. RENDER - SELLER DETAIL DRAWER
  // ==================================================================

  function renderDrawer(entry, summaries) {
    var open = Boolean(view.drawerSeller);
    var seller = open ? findSeller(entry, view.drawerSeller) : null;
    if (!seller) {
      return '<div class="ks-overlay" id="ks-overlay" hidden></div>'
        + '<aside class="ks-drawer" id="ks-drawer" role="dialog" aria-modal="true" aria-label="Chi tiết seller" hidden></aside>';
    }

    var summary = summaries.filter(function (item) { return item.seller === seller.seller; })[0]
      || buildSellerSummary(seller, entry.dates, currentOptions());
    var dates = entry.dates || [];

    var listingCards = (seller.listings || []).map(function (listing, index) {
      var listingSummary = buildListingSummary(listing, dates, currentOptions());
      var isRepresentative = summary.representativeListingId === listingSummary.listingId;
      var color = CONFIG.colors[(index + 3) % CONFIG.colors.length];
      var badge = isRepresentative
        ? '<span class="ks-badge ks-badge--rep">Đại diện</span>'
        : (listingSummary.eligible
          ? '<span class="ks-badge ks-badge--history">History</span>'
          : '<span class="ks-badge ks-badge--excluded">Bị loại: ' + escapeHtml(listingSummary.exclusionLabel) + '</span>');

      return '<article class="ks-listing-card' + (isRepresentative ? ' is-representative' : '') + '">'
        + '<div class="ks-listing-card-head"><div><b>' + escapeHtml(listingSummary.listingId) + '</b>'
        + '<small>First seen ' + escapeHtml(listingSummary.firstSeen || '—') + ' · ' + escapeHtml(listingSummary.role) + '</small></div>'
        + badge + '</div>'
        + '<div class="ks-listing-card-title">' + escapeHtml(listingSummary.title) + '</div>'
        + '<div class="ks-spark">' + renderSparkline(listingSummary.priceSeries, color) + '</div>'
        + '<div class="ks-listing-card-meta">Hiện tại <b>' + escapeHtml(formatCurrency(listingSummary.currentPrice))
        + '</b> · ' + statusPill(listingSummary.status) + ' · ' + changeCell(listingSummary.changePct) + '</div>'
        + '<div class="ks-listing-card-meta ks-muted">Min ' + escapeHtml(formatCurrency(listingSummary.minPrice))
        + ' · Max ' + escapeHtml(formatCurrency(listingSummary.maxPrice))
        + ' · Cập nhật ' + escapeHtml(listingSummary.lastUpdated || '—') + '</div>'
        + '<div class="ks-listing-url">' + escapeHtml(listingSummary.url) + '</div>'
        + '<button type="button" class="ks-link-button" data-ks-open-url="' + escapeHtml(listingSummary.url)
        + '">Mở listing ↗</button>'
        + '</article>';
    }).join('');

    var events = summary.events.slice().reverse().map(function (event) {
      return '<div class="ks-event ks-event--' + escapeHtml(event.type.toLowerCase()) + '">'
        + '<i aria-hidden="true"></i>'
        + '<div><b>' + escapeHtml(EVENT_LABELS[event.type] || event.type) + '</b>'
        + '<p>' + escapeHtml(event.detail) + '</p></div>'
        + '<time>' + escapeHtml(formatDayMonth(event.date)) + '</time></div>';
    }).join('');

    return ''
      + '<div class="ks-overlay is-open" id="ks-overlay"></div>'
      + '<aside class="ks-drawer is-open" id="ks-drawer" role="dialog" aria-modal="true"'
      + ' aria-label="Chi tiết seller ' + escapeHtml(seller.seller) + '">'
      + '  <header class="ks-drawer-head">'
      + '    <div><h2>' + escapeHtml(seller.seller) + '</h2>'
      + '      <div class="ks-drawer-meta">Keyword: ' + escapeHtml(entry.keyword) + ' · '
      + escapeHtml(entry.marketplace) + ' · ' + summary.totalListingCount + ' listing</div></div>'
      + '    <button type="button" class="ks-drawer-close" id="ks-drawer-close" aria-label="Đóng">✕</button>'
      + '  </header>'
      + '  <div class="ks-drawer-kpis">'
      + '    <div class="ks-dk"><span>Giá đại diện</span><b>' + escapeHtml(formatCurrency(summary.representativePrice)) + '</b></div>'
      + '    <div class="ks-dk"><span>Listing đại diện</span><b>' + escapeHtml(summary.representativeListingId || '—') + '</b></div>'
      + '    <div class="ks-dk"><span>Active listings</span><b>' + summary.activeListingCount + '</b></div>'
      + '    <div class="ks-dk"><span>Khoảng giá active</span><b>'
      + escapeHtml(formatCurrency(summary.activePriceMin)) + ' – ' + escapeHtml(formatCurrency(summary.activePriceMax))
      + '</b></div>'
      + '    <div class="ks-dk ks-dk--wide"><span>Cập nhật gần nhất</span><b>' + escapeHtml(summary.lastUpdated || '—') + '</b></div>'
      + '  </div>'
      + (summary.totalListingCount > 1
        ? '<section class="ks-drawer-section"><h3>Listing history — ' + escapeHtml(seller.seller) + '</h3>'
          + '<p class="ks-muted">Line đậm là giá đại diện của seller; line đứt là từng listing riêng.</p>'
          + '<div class="ks-drill-chart">' + renderListingDrillChart(entry, seller, summary) + '</div></section>'
        : '')
      + '  <section class="ks-drawer-section"><h3>Listing đang được theo dõi</h3>' + listingCards + '</section>'
      + '  <section class="ks-drawer-section"><h3>Seller event timeline</h3>'
      + (events || '<div class="empty-state">Chưa ghi nhận sự kiện nào.</div>') + '</section>'
      + '</aside>';
  }

  // ==================================================================
  // 9. CSV EXPORT
  // ==================================================================

  function csvCell(value) {
    var text = value === null || value === undefined ? '' : String(value);
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function exportCsv(entry, summaries) {
    var dates = entry.dates || [];
    var header = ['keyword', 'seller', 'listing_id', 'listing_title', 'role', 'first_seen', 'current_price',
      'change_pct', 'min_price', 'max_price', 'listing_status', 'is_representative', 'is_eligible',
      'exclusion_reason', 'last_updated', 'listing_url'];
    var lines = [header.map(csvCell).join(',')];

    summaries.forEach(function (summary) {
      var seller = findSeller(entry, summary.seller);
      (seller.listings || []).forEach(function (listing) {
        var listingSummary = buildListingSummary(listing, dates, currentOptions());
        lines.push([
          entry.keyword,
          summary.seller,
          listingSummary.listingId,
          listingSummary.title,
          listingSummary.role,
          listingSummary.firstSeen,
          listingSummary.currentPrice,
          listingSummary.changePct === null ? '' : listingSummary.changePct.toFixed(2),
          listingSummary.minPrice,
          listingSummary.maxPrice,
          listingSummary.status,
          summary.representativeListingId === listingSummary.listingId ? 'yes' : 'no',
          listingSummary.eligible ? 'yes' : 'no',
          listingSummary.exclusionLabel,
          listingSummary.lastUpdated,
          listingSummary.url,
        ].map(csvCell).join(','));
      });
    });

    var blob = new global.Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    var url = global.URL.createObjectURL(blob);
    var anchor = global.document.createElement('a');
    anchor.href = url;
    anchor.download = 'keyword-seller-' + String(entry.keyword).replace(/[^a-z0-9]+/gi, '-').toLowerCase() + '.csv';
    global.document.body.appendChild(anchor);
    anchor.click();
    global.document.body.removeChild(anchor);
    global.URL.revokeObjectURL(url);
  }

  // ==================================================================
  // 10. RENDER - ROOT + STATES (prompt muc 19)
  // ==================================================================

  function renderLoadingState() {
    return ''
      + '<div class="ks-state" role="status" aria-live="polite">'
      + '  <div class="ks-skeleton ks-skeleton--toolbar"></div>'
      + '  <div class="ks-skeleton ks-skeleton--chart"></div>'
      + '  <div class="ks-skeleton ks-skeleton--table"></div>'
      + '  <p class="ks-state-text">Đang tải dữ liệu keyword...</p>'
      + '</div>';
  }

  function renderErrorState(message) {
    return '<div class="ks-state ks-state--error" role="alert">'
      + '<p class="ks-state-title">Không thể tải dữ liệu.</p>'
      + '<p class="ks-state-text">' + escapeHtml(message || 'Vui lòng thử lại.') + '</p>'
      + '<button type="button" class="ks-export-button" id="ks-retry">Thử lại</button></div>';
  }

  function render() {
    if (!view.root) return;

    if (view.loading && !view.dataset) {
      view.root.innerHTML = renderLoadingState();
      return;
    }
    if (view.error && !view.dataset) {
      view.root.innerHTML = renderErrorState(view.error);
      bindEvents();
      return;
    }

    var dataset = view.dataset || { keywords: [] };
    if (!view.keywordOptions.length) {
      view.root.innerHTML = '<div class="ks-state"><p class="ks-state-title">Chưa có keyword nào được theo dõi.</p>'
        + '<p class="ks-state-text">Không tìm thấy listing whole-product trên ngưỡng giá hiện tại. '
        + 'Hãy hạ ngưỡng giá hoặc kiểm tra tiến trình thu thập dữ liệu.</p></div>';
      return;
    }
    // Keyword duoc chon nhung chua tai xong -> hien loading thay vi bang rong.
    if (!findKeyword(dataset, view.keyword)) {
      view.root.innerHTML = renderLoadingState();
      return;
    }

    var entry = currentKeywordEntry();
    view.keyword = entry.keyword;

    var options = currentOptions();
    var summaries = (entry.sellers || [])
      .map(function (seller) { return buildSellerSummary(seller, entry.dates, options); })
      .filter(function (summary) { return summary.current !== null; });
    var keywordSummary = buildKeywordSummary(entry, options);
    var alerts = buildKeywordAlerts(entry, options);
    var auditRows = buildClassificationAudit(entry, options);
    var axis = buildAxis(entry.dates, view.period);

    var chartBody = summaries.length
      ? '<div class="ks-chart-wrap" id="ks-chart-wrap">' + renderTrendChart(entry, axis, summaries)
        + '<div class="ks-tooltip" id="ks-tooltip" hidden></div></div>' + renderLegend(entry, summaries)
      : '<div class="empty-state">Không tìm thấy seller đủ điều kiện với bộ lọc hiện tại.</div>';

    var mainBody = keywordSummary.eligibleListingCount === 0
      ? '<div class="empty-state">Không có listing whole-product &gt; '
        + escapeHtml(formatCurrency(view.minPrice)) + ' phù hợp với keyword này.</div>'
      : ''
        + '<div class="ks-grid">'
        + '  <section class="ks-alert-column" aria-label="Cảnh báo">'
        + '    <div class="ks-column-title">Cảnh báo (' + alerts.length + ')</div>'
        + renderAlertPanel(alerts)
        + '  </section>'
        + '  <section class="dashboard-panel ks-chart-panel">'
        + '    <div class="ks-chart-head"><div><h2>Xu hướng giá theo seller</h2>'
        + '<p>Mỗi line = 1 seller · giá đại diện = snapshot gần nhất của listing đủ điều kiện được đăng mới nhất</p></div>'
        + '<div class="ks-chart-kpi"><small>Median seller hiện tại</small><strong>'
        + escapeHtml(formatCurrency(keywordSummary.medianPrice)) + '</strong></div></div>'
        + chartBody
        + '  </section>'
        + renderKeywordSummaryPanel(keywordSummary)
        + '</div>'
        + renderSellerTable(entry, summaries)
        + renderAuditPanel(auditRows);

    view.root.innerHTML = ''
      + '<div class="ks-module">'
      + '  <div class="ks-breadcrumb">Keyword → Seller → Listing mới nhất → Price / Status history</div>'
      + '  <div class="ks-rule-banner"><b>Cách đọc biểu đồ:</b> mỗi biểu đồ đại diện cho <b>1 keyword</b>, mỗi đường'
      + ' đại diện cho <b>1 seller</b>. Khi seller đăng listing mới đủ điều kiện, đường seller chuyển sang listing đó và'
      + ' hệ thống ghi nhận sự kiện <b>New Listing Price Shift</b> — đây không phải là listing cũ tăng hay giảm giá.</div>'
      + renderToolbar()
      + renderKeywordNav()
      + (view.error ? '<div class="error">' + escapeHtml(view.error) + '</div>' : '')
      + mainBody
      + renderDrawer(entry, summaries)
      + '</div>';

    bindEvents();
  }

  // ==================================================================
  // 11. EVENTS
  // ==================================================================

  function openSellerDrawer(sellerName) {
    view.drawerSeller = sellerName;
    view.highlightSeller = sellerName;
    render();
    var drawer = view.root.querySelector('#ks-drawer');
    if (drawer && drawer.focus) {
      try { drawer.focus({ preventScroll: true }); } catch (error) { drawer.focus(); }
    }
  }

  function closeSellerDrawer() {
    view.drawerSeller = '';
    render();
  }

  function openExternal(url) {
    if (!url) return;
    global.open(url, '_blank', 'noopener,noreferrer');
  }

  function bindEvents() {
    var root = view.root;
    if (!root) return;

    var retry = root.querySelector('#ks-retry');
    if (retry) retry.addEventListener('click', function () { load(true); });

    var trigger = root.querySelector('#ks-keyword-trigger');
    if (trigger) {
      trigger.addEventListener('click', function () {
        view.keywordPickerOpen = !view.keywordPickerOpen;
        render();
        var search = view.root.querySelector('#ks-keyword-search');
        if (search && view.keywordPickerOpen) search.focus();
      });
    }

    var search = root.querySelector('#ks-keyword-search');
    if (search) {
      search.addEventListener('input', function (event) {
        view.keywordSearch = event.target.value;
        render();
        var next = view.root.querySelector('#ks-keyword-search');
        if (next) {
          next.focus();
          next.setSelectionRange(next.value.length, next.value.length);
        }
      });
    }

    root.querySelectorAll('[data-ks-keyword]').forEach(function (element) {
      element.addEventListener('click', function () {
        view.keyword = element.getAttribute('data-ks-keyword');
        view.keywordPickerOpen = false;
        view.keywordSearch = '';
        view.highlightSeller = '';
        view.drawerSeller = '';
        view.expandedSellers = {};
        // Keyword chua co trong cache -> goi API cho rieng keyword do.
        if (!view.loadedKeywords[view.keyword]) {
          load(false);
          return;
        }
        render();
      });
    });

    var role = root.querySelector('#ks-role');
    if (role) {
      role.addEventListener('change', function (event) {
        view.roleFilter = event.target.value;
        render();
      });
    }

    var minPrice = root.querySelector('#ks-min-price');
    if (minPrice) {
      minPrice.addEventListener('change', function (event) {
        var parsed = Number(event.target.value);
        view.minPrice = isFinite(parsed) && parsed >= 0 ? parsed : CONFIG.minPrice;
        render();
      });
    }

    root.querySelectorAll('[data-ks-period]').forEach(function (button) {
      button.addEventListener('click', function () {
        view.period = button.getAttribute('data-ks-period');
        render();
      });
    });

    var refresh = root.querySelector('#ks-refresh');
    if (refresh) refresh.addEventListener('click', function () { load(true); });

    var exportButton = root.querySelector('#ks-export');
    if (exportButton) {
      exportButton.addEventListener('click', function () {
        var entry = currentKeywordEntry();
        if (!entry) return;
        // Uu tien export tu server de CSV khop chinh xac voi du lieu DB.
        if (view.serverPayloads[view.keyword]) {
          window.open(exportUrl(view.keyword), '_blank', 'noopener');
          return;
        }
        var summaries = (entry.sellers || []).map(function (seller) {
          return buildSellerSummary(seller, entry.dates, currentOptions());
        });
        exportCsv(entry, summaries);
      });
    }

    var toggleRows = root.querySelector('#ks-toggle-rows');
    if (toggleRows) {
      toggleRows.addEventListener('click', function () {
        view.expandAll = !view.expandAll;
        view.expandedSellers = {};
        render();
      });
    }

    root.querySelectorAll('[data-ks-toggle-seller]').forEach(function (row) {
      row.addEventListener('click', function (event) {
        if (event.target.closest('[data-ks-open-seller],[data-ks-open-url]')) return;
        var name = row.getAttribute('data-ks-toggle-seller');
        var currentlyExpanded = view.expandedSellers[name] === undefined ? view.expandAll : view.expandedSellers[name];
        view.expandedSellers[name] = !currentlyExpanded;
        render();
      });
    });

    root.querySelectorAll('[data-ks-open-seller]').forEach(function (element) {
      element.addEventListener('click', function (event) {
        event.stopPropagation();
        openSellerDrawer(element.getAttribute('data-ks-open-seller'));
      });
    });

    root.querySelectorAll('[data-ks-open-url]').forEach(function (element) {
      element.addEventListener('click', function (event) {
        event.stopPropagation();
        openExternal(element.getAttribute('data-ks-open-url'));
      });
    });

    root.querySelectorAll('.ks-line[data-ks-seller]').forEach(function (element) {
      var activate = function () { openSellerDrawer(element.getAttribute('data-ks-seller')); };
      element.addEventListener('click', activate);
      element.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          activate();
        }
      });
    });

    bindChartTooltip(root);

    var overlay = root.querySelector('#ks-overlay');
    if (overlay) overlay.addEventListener('click', closeSellerDrawer);
    var drawerClose = root.querySelector('#ks-drawer-close');
    if (drawerClose) drawerClose.addEventListener('click', closeSellerDrawer);

    if (!view.keyboardBound && global.document) {
      view.keyboardBound = true;
      global.document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        if (view.drawerSeller) closeSellerDrawer();
        else if (view.keywordPickerOpen) { view.keywordPickerOpen = false; render(); }
      });
    }
  }

  /** Tooltip prompt muc 9: seller, keyword, ngay, listing dai dien, gia, listing truoc, su kien. */
  function bindChartTooltip(root) {
    var wrap = root.querySelector('#ks-chart-wrap');
    var tooltip = root.querySelector('#ks-tooltip');
    if (!wrap || !tooltip) return;
    var entry = currentKeywordEntry();

    wrap.querySelectorAll('.ks-point').forEach(function (point) {
      point.addEventListener('mouseenter', function () {
        var sellerName = point.getAttribute('data-ks-seller');
        var seller = findSeller(entry, sellerName);
        var date = point.getAttribute('data-ks-date');
        var listingId = point.getAttribute('data-ks-listing');
        var events = seller ? buildSellerEvents(seller, entry.dates, currentOptions()) : [];
        var todaysEvent = events.filter(function (item) { return item.date === date; })[0];
        var series = seller ? buildSellerSeries(seller, entry.dates, currentOptions()) : [];
        var index = (entry.dates || []).indexOf(date);
        var previous = null;
        for (var i = index - 1; i >= 0; i -= 1) {
          if (series[i]) { previous = series[i]; break; }
        }

        tooltip.innerHTML = '<b>' + escapeHtml(sellerName) + '</b>'
          + '<div class="ks-tooltip-row">Keyword: ' + escapeHtml(entry.keyword) + '</div>'
          + '<div class="ks-tooltip-row">Ngày: ' + escapeHtml(date) + '</div>'
          + '<div class="ks-tooltip-row">Listing đại diện: <b>' + escapeHtml(listingId) + '</b></div>'
          + '<div class="ks-tooltip-price">' + escapeHtml(formatCurrency(point.getAttribute('data-ks-price'))) + '</div>'
          + '<div class="ks-tooltip-row">Status: ' + escapeHtml(point.getAttribute('data-ks-status')) + '</div>'
          + (previous && previous.listingId !== listingId
            ? '<div class="ks-tooltip-row">Listing trước: ' + escapeHtml(previous.listingId) + '</div>' : '')
          + (todaysEvent
            ? '<div class="ks-tooltip-event">Sự kiện: ' + escapeHtml(EVENT_LABELS[todaysEvent.type] || todaysEvent.type) + '</div>'
            : '');
        tooltip.hidden = false;

        var wrapBox = wrap.getBoundingClientRect();
        var pointBox = point.getBoundingClientRect();
        var left = pointBox.left - wrapBox.left + pointBox.width / 2;
        tooltip.style.left = Math.max(8, Math.min(left, wrapBox.width - 220)) + 'px';
        tooltip.style.top = Math.max(8, pointBox.top - wrapBox.top - 12) + 'px';
      });
      point.addEventListener('mouseleave', function () { tooltip.hidden = true; });
    });
  }

  // ==================================================================
  // 12. PUBLIC API
  // ==================================================================

  /**
   * Tai du lieu theo tung keyword.
   *
   * Lan dau: lay danh sach keyword tu DB (de do selector), roi tai keyword dau
   * tien. Doi keyword: chi goi API cho keyword do va cache lai, nen bam qua lai
   * giua cac keyword da xem khong tao them request.
   */
  function load(force) {
    var needKeywordList = force || !view.keywordOptions.length;

    view.loading = true;
    view.error = '';
    render();

    return Promise.resolve()
      .then(function () {
        if (!needKeywordList) return view.keywordOptions;
        return dataSource.listKeywords().then(function (options) {
          view.keywordOptions = options || [];
          return view.keywordOptions;
        });
      })
      .then(function (options) {
        if (!options.length) {
          view.dataset = normalizeDataset({ keywords: [] });
          view.keyword = '';
          return view.dataset;
        }

        var exists = options.some(function (item) { return item.keyword === view.keyword; });
        if (!view.keyword || !exists) view.keyword = options[0].keyword;

        if (!force && view.loadedKeywords[view.keyword]) {
          return view.dataset;
        }

        return dataSource.loadKeyword(view.keyword).then(function (result) {
          var entry = result && result.entry;
          if (!entry) throw new Error('Không có dữ liệu cho keyword này.');

          view.serverPayloads[view.keyword] = result.raw || null;
          view.loadedKeywords[view.keyword] = true;

          // Gop keyword vua tai vao dataset dang co (cache nhieu keyword).
          var merged = (view.rawKeywords || []).filter(function (item) {
            return item.keyword !== entry.keyword;
          });
          merged.push(entry);
          view.rawKeywords = merged;
          view.dataset = normalizeDataset({ keywords: merged });
          return view.dataset;
        });
      })
      .catch(function (error) {
        if (error && error.status === 503) {
          view.error = 'Chưa kết nối được nguồn dữ liệu listing. Vui lòng kiểm tra cấu hình database.';
        } else {
          view.error = (error && error.message) || 'Không thể tải dữ liệu. Vui lòng thử lại.';
        }
      })
      .then(function () {
        view.loading = false;
        render();
        return view.dataset;
      });
  }

  function mount(root, options) {
    view.root = root;
    var settings = options || {};
    if (settings.keyword) view.keyword = settings.keyword;
    if (settings.minPrice !== undefined) view.minPrice = Number(settings.minPrice);
    if (settings.roleFilter) view.roleFilter = settings.roleFilter;
    if (typeof settings.apiClient === 'function') setApiClient(settings.apiClient);

    // Da co du lieu roi thi ve lai ngay, khong goi API lai khi chuyen tab.
    var force = Boolean(settings.reload);
    if (!force && view.keywordOptions.length && view.dataset) {
      render();
      return Promise.resolve(view.dataset);
    }
    return load(force);
  }

  function destroy() {
    if (view.root) view.root.innerHTML = '';
    view.root = null;
    view.drawerSeller = '';
    view.highlightSeller = '';
  }

  global.KeywordSellerAnalytics = {
    config: CONFIG,
    eventTypes: EVENT_TYPES,
    mount: mount,
    refresh: function () { return load(true); },
    destroy: destroy,
    setDataSource: setDataSource,
    setApiClient: setApiClient,
    // Pure helpers - dung cho unit test va tai su dung o noi khac.
    logic: {
      normalizeDataset: normalizeDataset,
      listingSnapshotAt: listingSnapshotAt,
      listingEligibilityAt: listingEligibilityAt,
      representativeListingAt: representativeListingAt,
      buildSellerSeries: buildSellerSeries,
      buildSellerEvents: buildSellerEvents,
      buildSellerSummary: buildSellerSummary,
      buildListingSummary: buildListingSummary,
      buildKeywordSummary: buildKeywordSummary,
      buildKeywordAlerts: buildKeywordAlerts,
      buildClassificationAudit: buildClassificationAudit,
      buildAxis: buildAxis,
      percentChange: percentChange,
      median: median,
    },
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = global.KeywordSellerAnalytics;
  }
}(typeof window !== 'undefined' ? window : globalThis));
