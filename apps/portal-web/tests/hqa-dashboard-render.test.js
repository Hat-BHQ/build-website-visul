const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { JSDOM } = require('jsdom');

function wait(ms = 0) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function flush(times = 4) {
  for (let i = 0; i < times; i += 1) await wait(0);
}

function createJsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return payload; },
    async text() { return JSON.stringify(payload); },
    headers: { get() { return 'application/json'; } },
  };
}

function dashboardPayload(groupBy = 'model', granularity = 'month') {
  const groupA = groupBy === 'brand' ? 'Brand A' : (groupBy === 'category' ? 'Category A' : 'Model A');
  const groupB = groupBy === 'brand' ? 'Brand B' : (groupBy === 'category' ? 'Category B' : 'Model B');
  const p1 = granularity === 'week' ? '2026-W30' : '2026-07';
  const p2 = granularity === 'week' ? '2026-W31' : '2026-08';
  return {
    group_by: groupBy,
    granularity,
    periods: [p1, p2],
    groups: [groupA, groupB],
    previous_period: p1,
    latest_period: {
      period: p2,
      listing_count: 25,
      unique_ids: 23,
      seller_count: 8,
      model_count: 2,
      median_price: 430,
      out_of_stock_count: 5,
      out_of_stock_pct: 20,
      currency: 'USD',
    },
    group_periods: [
      {
        group: groupA, period: p1, listing_count: 10, unique_ids: 10, seller_count: 3, price_sample: 10,
        min_price: 400, p25: 430, median_price: 450, avg_price: 455, p75: 480, max_price: 520,
        std: 35, cv: 7.69, out_of_stock_count: 0, out_of_stock_pct: 0, new_seller_count: 3,
        new_sellers: ['seller-a', 'seller-b', 'seller-c'], currency: 'USD',
        top_sellers: [
          { seller: 'seller-a', listing_count: 5, avg_price: 445, min_price: 400 },
          { seller: 'seller-b', listing_count: 3, avg_price: 460, min_price: 430 },
        ],
      },
      {
        group: groupA, period: p2, listing_count: 14, unique_ids: 13, seller_count: 5, price_sample: 14,
        min_price: 290, p25: 320, median_price: 340, avg_price: 335, p75: 360, max_price: 410,
        std: 32, cv: 9.55, out_of_stock_count: 7, out_of_stock_pct: 50, new_seller_count: 3,
        new_sellers: ['seller-d', 'seller-e', 'seller-f'], currency: 'USD',
        top_sellers: [
          { seller: 'seller-a', listing_count: 6, avg_price: 330, min_price: 290 },
          { seller: 'seller-d', listing_count: 4, avg_price: 350, min_price: 310 },
        ],
      },
      {
        group: groupB, period: p1, listing_count: 7, unique_ids: 7, seller_count: 2, price_sample: 7,
        min_price: 150, p25: 170, median_price: 180, avg_price: 182, p75: 195, max_price: 215,
        std: 20, cv: 10.99, out_of_stock_count: 0, out_of_stock_pct: 0, new_seller_count: 2,
        new_sellers: ['seller-g', 'seller-h'], currency: 'USD', top_sellers: [],
      },
      {
        group: groupB, period: p2, listing_count: 11, unique_ids: 10, seller_count: 3, price_sample: 11,
        min_price: 148, p25: 168, median_price: 181, avg_price: 183, p75: 198, max_price: 220,
        std: 21, cv: 11.48, out_of_stock_count: 1, out_of_stock_pct: 9.1, new_seller_count: 1,
        new_sellers: ['seller-i'], currency: 'USD', top_sellers: [],
      },
    ],
    alerts: [
      {
        type: 'price_drop', severity: 'warning', group: groupA, period: p2, currency: 'USD', title: 'Giá giảm mạnh',
        previous_avg_price: 455, current_avg_price: 335, change_percent: -26.37,
      },
      {
        type: 'new_seller', severity: 'info', group: groupA, period: p2, currency: 'USD', title: 'Người bán mới',
        new_seller_count: 3, new_sellers: ['seller-d', 'seller-e', 'seller-f'],
      },
    ],
    meta: { source_table: 'public.marketplace_research_results', time_field: 'research_date' },
  };
}

(async () => {
  const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', {
    url: 'http://localhost/', pretendToBeVisual: true, runScripts: 'outside-only',
  });
  const { window } = dom;
  global.window = window;
  global.document = window.document;
  global.navigator = window.navigator;
  global.Headers = window.Headers;
  global.HTMLElement = window.HTMLElement;
  global.Element = window.Element;
  global.Node = window.Node;
  global.requestAnimationFrame = (callback) => setTimeout(callback, 0);

  const chartCalls = [];
  window.Chart = class ChartMock {
    constructor(canvas, config) {
      chartCalls.push({ canvas, config });
    }
    destroy() {}
  };

  const dashboardUrls = [];
  window.fetch = async (input) => {
    const url = String(input || '');
    if (url.endsWith('/api/v1/auth/session')) {
      return createJsonResponse({
        access_token: 'access-token', user: { full_name: 'Dashboard Tester', system_role: 'superadmin' },
        modules: [{ code: 'HQA', permissions: ['*'] }],
      });
    }
    if (url.includes('/api/v1/hqa/listings/filter-options')) {
      if (url.includes('field=')) return createJsonResponse({ items: [], page: 1, page_size: 30, has_more: false });
      return createJsonResponse({ marketplaces: ['ebay'], brands: [], models: [], conditions: [], statuses: [], category_names: [], buying_options: [] });
    }
    if (url.includes('/api/v1/hqa/listings/summary')) {
      return createJsonResponse({ total_records_stored: 25, unique_listing_ids: 23, filtered_records: 25, active: 20, ended: 0, out_of_stock: 5, accessories: 0 });
    }
    if (url.includes('/api/v1/hqa/listings?')) {
      return createJsonResponse({ items: [], page: 1, page_size: 50, total: 0, total_pages: 0 });
    }
    if (url.includes('/api/v1/hqa/dashboard/analysis')) {
      dashboardUrls.push(url);
      const parsed = new URL(url, 'http://localhost');
      return createJsonResponse(dashboardPayload(parsed.searchParams.get('group_by') || 'model', parsed.searchParams.get('granularity') || 'month'));
    }
    if (url.includes('/api/v1/auth/refresh')) return createJsonResponse({}, 401);
    return createJsonResponse({});
  };
  global.fetch = window.fetch;

  const source = fs.readFileSync(path.join(__dirname, '..', 'assets', 'app.js'), 'utf8');
  window.eval(source);
  await flush(8);

  const dashboardTab = document.querySelector('[data-hqa-main-tab="dashboard"]');
  assert(dashboardTab, 'Dashboard tab must render');
  dashboardTab.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(10);

  const dashboardView = document.getElementById('hqa-dashboard-view');
  assert(dashboardView && !dashboardView.hidden, 'Dashboard view must be visible');
  assert(dashboardUrls.length >= 1, 'Dashboard analysis endpoint must be requested');
  assert(dashboardUrls[0].includes('group_by=model'), 'Dashboard must start grouped by Model');
  assert(dashboardUrls[0].includes('granularity=month'), 'Dashboard must start grouped by month');
  assert(document.querySelectorAll('.dashboard-kpi-card').length === 5, 'Dashboard must render five KPI cards');
  assert(document.querySelectorAll('.dashboard-alert-item').length === 2, 'Dashboard must render alert radar items');
  assert(document.querySelector('#dashboard-model-select'), 'Dashboard drill-down selector must render');
  assert(document.querySelector('.dashboard-range-svg'), 'Dashboard price range SVG must render');
  assert(document.querySelector('.dashboard-sparkline'), 'Dashboard six-period sparkline must render');
  assert(document.querySelectorAll('.dashboard-suggestion').length === 3, 'Dashboard must render three pricing suggestions');
  assert(document.querySelectorAll('.dashboard-top-seller-row').length === 2, 'Dashboard must render selected group seller rows');
  assert(document.querySelectorAll('[data-dashboard-export]').length === 3, 'Dashboard must render three CSV export actions');
  assert(chartCalls.length === 2, 'Dashboard must render two Chart.js charts');

  const groupBy = document.getElementById('dashboard-group-by');
  groupBy.value = 'brand';
  groupBy.dispatchEvent(new window.Event('change', { bubbles: true }));
  await flush(8);
  assert(dashboardUrls.some((url) => url.includes('group_by=brand')), 'Changing grouping must reload dashboard by Brand');

  const granularity = document.getElementById('dashboard-granularity');
  granularity.value = 'week';
  granularity.dispatchEvent(new window.Event('change', { bubbles: true }));
  await flush(8);
  assert(dashboardUrls.some((url) => url.includes('granularity=week')), 'Changing period must reload dashboard by week');

  console.log('hqa-dashboard-render tests passed');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
