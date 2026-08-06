const state = {
  accessToken: null,
  user: null,
  modules: [],
  currentModule: 'HQA',
  hqa: {
    mainTab: 'all_listings',
    activeReport: 'all_listings',
    page: 1,
    pageSize: 50,
    summary: null,
    loadingSummary: false,
    loadingListings: false,
    error: '',
    rawListings: null,
    listingsByReport: {},
    loadingFilterOptions: false,
    filterOptionsError: '',
    filterOptionsRequestId: 0,
    filterOptions: {
      brands: { items: [], truncated: false },
      models: { items: [], truncated: false },
      categories: { items: [], truncated: false },
      listing_locations: { items: [], truncated: false },
      conditions: { items: [], truncated: false },
      category_names: { items: [], truncated: false },
      buying_options: { items: [], truncated: false },
    },
    allListings: {
      loadingOptions: false,
      optionsError: '',
      loadingSummary: false,
      summaryError: '',
      isExporting: false,
      notification: null,
      openLazyField: '',
      lazyOptions: {
        marketplace: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
        brand: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
        model: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
        conditions: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
        statuses: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
        categoryNames: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
        buyingOptions: { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null },
      },
      optionCache: {},
      optionSearchDebounce: {},
      appliedFilters: {
        fromDate: '',
        toDate: '',
        marketplace: '',
        brand: '',
        model: '',
        conditions: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        sortCollected: 'newest',
        minPrice: '',
        maxPrice: '',
        search: '',
      },
      draftFilters: {
        fromDate: '',
        toDate: '',
        marketplace: '',
        brand: '',
        model: '',
        conditions: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        sortCollected: 'newest',
        minPrice: '',
        maxPrice: '',
        search: '',
      },
      summary: null,
    },
    dashboard: {
      loading: false,
      loadingOptions: false,
      isExporting: false,
      error: '',
      optionsError: '',
      sectionErrors: {},
      filterOptions: {
        marketplaces: [],
        brands: [],
        models: [],
        statuses: [],
        category_names: [],
        buying_options: [],
        sellers: [],
        currencies: [],
      },
      appliedSellerFilters: {
        keyword: '',
        marketplaces: [],
        brands: [],
        models: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        sellers: [],
        currency: '',
        dateFrom: '',
        dateTo: '',
      },
      draftSellerFilters: {
        keyword: '',
        marketplaces: [],
        brands: [],
        models: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        sellers: [],
        currency: '',
        dateFrom: '',
        dateTo: '',
      },
      appliedPriceFilters: {
        keyword: '',
        marketplaces: [],
        brands: [],
        models: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        sellers: [],
        currency: '',
        dateFrom: '',
        dateTo: '',
        granularity: 'month',
        minPrice: '',
        maxPrice: '',
      },
      draftPriceFilters: {
        keyword: '',
        marketplaces: [],
        brands: [],
        models: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        sellers: [],
        currency: '',
        dateFrom: '',
        dateTo: '',
        granularity: 'month',
        minPrice: '',
        maxPrice: '',
      },
      sellersSummary: null,
      sellersTrend: { points: [] },
      topSellers: { items: [] },
      pricesSummary: null,
      pricesTrend: { points: [] },
      pricesByKeyword: { items: [] },
      alerts: { alerts: [] },
    },
    dataCheck: {
      hasRun: false,
      loading: false,
      loadingCleanup: false,
      error: '',
      summary: null,
      groups: null,
      page: 1,
      pageSize: 20,
      filters: {
        marketplace: '',
        listingId: '',
        status: '',
      },
      expandedKeys: {},
      showConfirmModal: false,
      confirmationInput: '',
      cleanupResult: null,
    },
  },
};

const REPORT_META = {
  all_listings: {
    shortLabel: 'All listings',
    label: 'All listings – All database listings',
    title: 'All database records',
    color: '#2563EB',
    softColor: '#DBEAFE',
    textColor: '#1E40AF',
  },
  main_repeated: {
    shortLabel: 'T1 Main / Repeated',
    label: 'Table 1 – Main / Repeated Products',
    title: 'Table 1 – Main / Repeated Products',
    color: '#4F46E5',
    softColor: '#E0E7FF',
    textColor: '#3730A3',
  },
  amplifier_receiver: {
    shortLabel: 'T2 Amplifiers / Receivers',
    label: 'Table 2 – Amplifiers / Receivers',
    title: 'Table 2 – Amplifiers / Receivers',
    color: '#7C3AED',
    softColor: '#EDE9FE',
    textColor: '#5B21B6',
  },
  speaker_parts: {
    shortLabel: 'T3 Speakers / Parts',
    label: 'Table 3 – Speakers / Speaker Parts',
    title: 'Table 3 – Speakers / Speaker Parts',
    color: '#0891B2',
    softColor: '#CFFAFE',
    textColor: '#155E75',
  },
  other_home_audio: {
    shortLabel: 'T4 Other Home Audio',
    label: 'Table 4 – Other Home Audio',
    title: 'Table 4 – Other Home Audio',
    color: '#0F766E',
    softColor: '#CCFBF1',
    textColor: '#115E59',
  },
  vintage_accessories: {
    shortLabel: 'T5 Vintage / Accessories',
    label: 'Table 5 – Vintage / Accessories',
    title: 'Table 5 – Vintage / Accessories',
    color: '#D97706',
    softColor: '#FEF3C7',
    textColor: '#92400E',
  },
  non_audio_irrelevant: {
    shortLabel: 'T6 Non-Audio / Irrelevant',
    label: 'Table 6 – Non-Audio / Irrelevant',
    title: 'Table 6 – Non-Audio / Irrelevant',
    color: '#64748B',
    softColor: '#E2E8F0',
    textColor: '#334155',
  },
  ended: {
    shortLabel: 'T7 Ended',
    label: 'Table 7 – Ended Listings',
    title: 'Table 7 – Ended Listings',
    color: '#6B7280',
    softColor: '#E5E7EB',
    textColor: '#374151',
  },
  out_of_stock: {
    shortLabel: 'T8 Out of Stock',
    label: 'Table 8 – Out of Stock Listings',
    title: 'Table 8 – Out of Stock Listings',
    color: '#DC2626',
    softColor: '#FEE2E2',
    textColor: '#991B1B',
  },
};

const HQA_MAIN_TABS = [
  { key: 'all_listings', label: 'All Listings' },
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'data_check', label: 'Kiem tra du lieu' },
];
const PAGE_SIZE_OPTIONS = [30, 50, 100, 200];
const ALL_LISTINGS_BASE_OPTION_FIELDS = {
  marketplace: { apiField: 'marketplace', searchable: false, multi: false },
  brand: { apiField: 'brand', searchable: false, multi: false },
};
const LAZY_FILTER_CONFIG = {
  model: { apiField: 'model', searchable: true, multi: false },
  condition: { stateKey: 'conditions', uiField: 'conditions', apiField: 'condition', searchable: true, multiple: true },
  status: { stateKey: 'statuses', uiField: 'statuses', apiField: 'status', searchable: true, multiple: true },
  category_name: { stateKey: 'categoryNames', uiField: 'categoryNames', apiField: 'category_name', searchable: true, multiple: true },
  buying_option: { stateKey: 'buyingOptions', uiField: 'buyingOptions', apiField: 'buying_option', searchable: true, multiple: true },
};
let listingsAbortController = null;
let listingsRequestSequence = 0;
let allListingsOutsideClickBound = false;
let allListingsFilterEventsBound = false;

function getLazyFilterConfigByApiField(apiField) {
  const normalized = String(apiField || '').trim();
  if (!normalized) return null;
  if (normalized === 'model') {
    return {
      stateKey: 'model',
      uiField: 'model',
      apiField: 'model',
      searchable: true,
      multiple: false,
    };
  }
  return LAZY_FILTER_CONFIG[normalized] || null;
}

function getLazyFilterConfigByUiField(uiField) {
  const normalized = String(uiField || '').trim();
  if (!normalized) return null;
  if (normalized === 'model') return getLazyFilterConfigByApiField('model');
  const values = Object.values(LAZY_FILTER_CONFIG);
  return values.find((item) => item.uiField === normalized) || null;
}

function getOptionFieldConfig(fieldKey) {
  if (ALL_LISTINGS_BASE_OPTION_FIELDS[fieldKey]) return ALL_LISTINGS_BASE_OPTION_FIELDS[fieldKey];
  return getLazyFilterConfigByUiField(fieldKey);
}

function defaultLazyOptionState() {
  return { items: [], page: 0, pageSize: 30, hasMore: true, isLoading: false, isLoaded: false, search: '', error: '', requestId: 0, controller: null };
}

function resetLazyOptionField(fieldKey, { clearCache = false } = {}) {
  state.hqa.allListings.lazyOptions[fieldKey] = {
    ...defaultLazyOptionState(),
    pageSize: state.hqa.allListings.lazyOptions[fieldKey]?.pageSize || 30,
  };
  if (clearCache) {
    Object.keys(state.hqa.allListings.optionCache).forEach((key) => {
      if (key.startsWith(`${fieldKey}|`)) delete state.hqa.allListings.optionCache[key];
    });
  }
}

function clearAllLazyOptionCache() {
  Object.keys(state.hqa.allListings.lazyOptions).forEach((fieldKey) => resetLazyOptionField(fieldKey, { clearCache: true }));
  state.hqa.allListings.optionCache = {};
}

function normalizeOptionValue(value) {
  return String(value || '').trim();
}

function buildLazyOptionCacheKey(fieldKey, searchTerm = '') {
  const normalizedSearch = normalizeOptionValue(searchTerm).toLowerCase();
  const brandValue = fieldKey === 'model' ? normalizeOptionValue(state.hqa.allListings.draftFilters.brand).toLowerCase() : '';
  return `${fieldKey}|brand=${brandValue}|search=${normalizedSearch}`;
}

function mergeOptionItems(existingItems, incomingItems) {
  const merged = [];
  const seen = new Set();
  [...(existingItems || []), ...(incomingItems || [])].forEach((item) => {
    const value = normalizeOptionValue(item?.value || item);
    if (!value) return;
    const key = value.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    merged.push({ value, label: normalizeOptionValue(item?.label || value) || value });
  });
  return merged;
}

async function loadLazyOptionField(fieldKey, { reset = false, useCache = true } = {}) {
  const fieldConfig = getOptionFieldConfig(fieldKey);
  if (!fieldConfig) return;
  const fieldState = state.hqa.allListings.lazyOptions[fieldKey];
  if (!fieldState) return;
  if (fieldState.isLoading) return;

  const cacheKey = buildLazyOptionCacheKey(fieldKey, fieldState.search);
  if (reset && useCache && state.hqa.allListings.optionCache[cacheKey]) {
    const cached = state.hqa.allListings.optionCache[cacheKey];
    state.hqa.allListings.lazyOptions[fieldKey] = {
      ...fieldState,
      items: [...cached.items],
      page: cached.page,
      hasMore: cached.hasMore,
      isLoaded: true,
      isLoading: false,
      error: '',
      controller: null,
    };
    return;
  }

  const targetPage = reset ? 1 : fieldState.page + 1;
  if (!reset && !fieldState.hasMore) return;

  if (reset && fieldState.controller) {
    fieldState.controller.abort();
  }
  const controller = new AbortController();
  const requestId = fieldState.requestId + 1;
  state.hqa.allListings.lazyOptions[fieldKey] = {
    ...fieldState,
    isLoading: true,
    error: '',
    requestId,
    controller,
  };

  const params = new URLSearchParams();
  params.set('field', fieldConfig.apiField);
  params.set('page', String(targetPage));
  params.set('page_size', String(fieldState.pageSize || 30));
  const trimmedSearch = normalizeOptionValue(fieldState.search);
  if (trimmedSearch) params.set('search', trimmedSearch);
  if (fieldKey === 'model') {
    const brandValue = normalizeOptionValue(state.hqa.allListings.draftFilters.brand);
    if (brandValue) params.set('brand', brandValue);
  }

  try {
    const payload = await api(`/hqa/listings/filter-options?${params.toString()}`, { signal: controller.signal });
    const currentState = state.hqa.allListings.lazyOptions[fieldKey];
    if (!currentState || currentState.requestId !== requestId) return;

    const incomingItems = (payload.items || []).map((item) => ({
      value: normalizeOptionValue(item?.value || item),
      label: normalizeOptionValue(item?.label || item?.value || item),
    })).filter((item) => item.value);
    const nextItems = reset ? incomingItems : mergeOptionItems(currentState.items, incomingItems);
    const nextState = {
      ...currentState,
      items: nextItems,
      page: Number(payload.page || targetPage),
      hasMore: Boolean(payload.has_more),
      isLoaded: true,
      isLoading: false,
      error: '',
      controller: null,
    };
    state.hqa.allListings.lazyOptions[fieldKey] = nextState;
    state.hqa.allListings.optionCache[cacheKey] = {
      items: [...nextState.items],
      page: nextState.page,
      hasMore: nextState.hasMore,
    };
  } catch (error) {
    if (error?.name === 'AbortError') return;
    const currentState = state.hqa.allListings.lazyOptions[fieldKey];
    if (!currentState || currentState.requestId !== requestId) return;
    state.hqa.allListings.lazyOptions[fieldKey] = {
      ...currentState,
      isLoading: false,
      error: 'Khong the tai danh sach. Thu lai.',
      controller: null,
    };
  }
}

function debounceLazyOptionSearch(fieldKey, value) {
  const oldTimer = state.hqa.allListings.optionSearchDebounce[fieldKey];
  if (oldTimer) clearTimeout(oldTimer);
  state.hqa.allListings.optionSearchDebounce[fieldKey] = setTimeout(async () => {
    const fieldState = state.hqa.allListings.lazyOptions[fieldKey];
    if (!fieldState) return;
    state.hqa.allListings.lazyOptions[fieldKey] = {
      ...fieldState,
      search: normalizeOptionValue(value),
      items: [],
      page: 0,
      hasMore: true,
      isLoaded: false,
      error: '',
    };
    await loadLazyOptionField(fieldKey, { reset: true, useCache: true });
    renderHqaFilterOptions();
  }, 350);
}

function reportMeta(reportKey) {
  return REPORT_META[reportKey] || REPORT_META.all_listings;
}

function reportStyleVariables(reportKey) {
  const meta = reportMeta(reportKey);
  return `--report-color: ${meta.color}; --report-soft-color: ${meta.softColor}; --report-text-color: ${meta.textColor};`;
}

function formatRecordCount(value) {
  return Number(value || 0).toLocaleString();
}

function buildPageButtons(totalPages, currentPage) {
  if (totalPages <= 1) return [1];
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = [1];
  const start = Math.max(2, currentPage - 2);
  const end = Math.min(totalPages - 1, currentPage + 2);
  if (start > 2) pages.push('...');
  for (let page = start; page <= end; page += 1) pages.push(page);
  if (end < totalPages - 1) pages.push('...');
  pages.push(totalPages);
  return pages;
}

function buildPaginationState(payload) {
  const total = Number(payload?.total || 0);
  const page = Math.max(1, Number(payload?.page || 1));
  const pageSize = Math.max(1, Number(payload?.page_size || state.hqa.pageSize || 50));
  const totalPages = Number(payload?.total_pages || (total ? Math.ceil(total / pageSize) : 0));
  const offset = (page - 1) * pageSize;
  const fromRecord = payload && Object.prototype.hasOwnProperty.call(payload, 'from_record')
    ? Number(payload.from_record || 0)
    : (total && offset < total ? offset + 1 : 0);
  const toRecord = payload && Object.prototype.hasOwnProperty.call(payload, 'to_record')
    ? Number(payload.to_record || 0)
    : (total && offset < total ? Math.min(offset + Number(payload?.items?.length || 0), total) : 0);
  const hasPrevious = payload && Object.prototype.hasOwnProperty.call(payload, 'has_previous')
    ? Boolean(payload.has_previous)
    : page > 1 && totalPages > 0;
  const hasNext = payload && Object.prototype.hasOwnProperty.call(payload, 'has_next')
    ? Boolean(payload.has_next)
    : page < totalPages;
  return { total, page, pageSize, totalPages, fromRecord, toRecord, hasPrevious, hasNext };
}

function buildHqaShellMarkup() {
  return `
    <section class="hqa-reports-screen hqa-module" data-hqa-root>
      <div class="page-heading">
        <div>
          <span class="eyebrow">Module</span>
          <h1>HQA Marketplace Reports</h1>
          <p>Quan ly, loc va xuat toan bo du lieu marketplace listings.</p>
        </div>
        <button id="refresh-data" type="button" data-table-interaction="true">Refresh data</button>
      </div>
      <div class="panel"><div id="hqa-main-tabs"></div></div>
      <div id="hqa-local-error" hidden></div>
      <div id="hqa-toast-host" class="hqa-toast-host" aria-live="polite" aria-atomic="true"></div>
      <section id="hqa-standard-view">
        <div id="hqa-summary" class="metrics"></div>
        <div class="panel hqa-filter-panel"><div id="hqa-filter-options"></div></div>
        <section id="hqa-listings-section" class="report-section" aria-busy="false">
          <div id="hqa-listings-loading" class="section-loading-overlay" hidden>
            <div class="loading-indicator">
              <span class="loading-spinner" aria-hidden="true"></span>
              <div class="loading-copy">
                <strong>Loading data...</strong>
                <small>Please wait while listings are updated.</small>
              </div>
            </div>
          </div>
          <div id="hqa-listings-content"></div>
          <div id="hqa-pagination"></div>
        </section>
      </section>
      <section id="hqa-dashboard-view" class="panel" hidden></section>
      <section id="hqa-data-check-view" class="panel" hidden></section>
    </section>`;
}

function ensureHqaShell(content) {
  if (content.dataset.hqaShellReady === 'true') return;
  content.innerHTML = buildHqaShellMarkup();
  content.dataset.hqaShellReady = 'true';
}

function hqaMainTabsView() {
  return `
    <div class="hqa-main-tabs" role="tablist" aria-label="eBay Marketplace Reports views">
      ${HQA_MAIN_TABS.map((tab) => `<button type="button" class="hqa-main-tab ${state.hqa.mainTab === tab.key ? 'active' : ''}" data-hqa-main-tab="${tab.key}" role="tab" aria-selected="${state.hqa.mainTab === tab.key ? 'true' : 'false'}">${escapeHtml(tab.label)}</button>`).join('')}
    </div>`;
}

function renderHqaMainTabs() {
  const tabs = document.getElementById('hqa-main-tabs');
  if (!tabs) return;
  tabs.innerHTML = hqaMainTabsView();
}

function setHqaMainTab(tabKey) {
  state.hqa.mainTab = tabKey;
  if (tabKey === 'all_listings') {
    state.hqa.activeReport = 'all_listings';
  }
}

function renderHqaMainTabVisibility() {
  const standardView = document.getElementById('hqa-standard-view');
  const dashboardView = document.getElementById('hqa-dashboard-view');
  const dataCheckView = document.getElementById('hqa-data-check-view');
  if (!standardView || !dashboardView || !dataCheckView) return;
  const isDashboard = state.hqa.mainTab === 'dashboard';
  const isDataCheck = state.hqa.mainTab === 'data_check';
  standardView.hidden = isDashboard;
  if (isDataCheck) {
    standardView.hidden = true;
  }
  dashboardView.hidden = !isDashboard;
  dataCheckView.hidden = !isDataCheck;
}

function appendDashboardListParams(params, key, values) {
  (values || []).forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized) return;
    params.append(key, normalized);
  });
}

function buildDashboardCommonParams(filters) {
  const params = new URLSearchParams();
  if (filters.keyword) params.set('keyword', filters.keyword.trim());
  if (filters.currency) params.set('currency', filters.currency.trim());
  if (filters.dateFrom) params.set('date_from', filters.dateFrom);
  if (filters.dateTo) params.set('date_to', filters.dateTo);
  appendDashboardListParams(params, 'marketplace', filters.marketplaces || []);
  appendDashboardListParams(params, 'brand', filters.brands || []);
  appendDashboardListParams(params, 'model', filters.models || []);
  appendDashboardListParams(params, 'status', filters.statuses || []);
  appendDashboardListParams(params, 'category_name', filters.categoryNames || []);
  appendDashboardListParams(params, 'buying_option', filters.buyingOptions || []);
  appendDashboardListParams(params, 'seller', filters.sellers || []);
  return params;
}

function buildDashboardSellerParams() {
  return buildDashboardCommonParams(state.hqa.dashboard.appliedSellerFilters);
}

function buildDashboardPriceParams() {
  const filters = state.hqa.dashboard.appliedPriceFilters;
  const params = buildDashboardCommonParams(filters);
  if (filters.minPrice !== '') params.set('min_price', String(filters.minPrice).trim());
  if (filters.maxPrice !== '') params.set('max_price', String(filters.maxPrice).trim());
  if (filters.granularity) params.set('granularity', filters.granularity);
  return params;
}

async function loadHqaDashboardFilterOptions() {
  state.hqa.dashboard.loadingOptions = true;
  state.hqa.dashboard.optionsError = '';
  try {
    const draft = state.hqa.dashboard.draftSellerFilters;
    const params = buildDashboardCommonParams(draft);
    const payload = await api(`/hqa/dashboard/filter-options?${params.toString()}`);
    state.hqa.dashboard.filterOptions = payload.options || {};
  } catch (error) {
    state.hqa.dashboard.optionsError = error.message || 'Could not load dashboard filter options.';
  } finally {
    state.hqa.dashboard.loadingOptions = false;
  }
}

async function loadHqaDashboardData() {
  state.hqa.dashboard.loading = true;
  state.hqa.dashboard.error = '';

  const sellerParams = buildDashboardSellerParams().toString();
  const sellerSuffix = sellerParams ? `?${sellerParams}` : '';
  const priceParams = buildDashboardPriceParams().toString();
  const priceSuffix = priceParams ? `?${priceParams}` : '';

  const requests = [
    { key: 'sellersSummary', path: `/hqa/dashboard/sellers/summary${sellerSuffix}` },
    { key: 'sellersTrend', path: `/hqa/dashboard/sellers/trend${sellerSuffix}` },
    { key: 'topSellers', path: `/hqa/dashboard/sellers/top${sellerSuffix}` },
    { key: 'pricesSummary', path: `/hqa/dashboard/prices/summary${priceSuffix}` },
    { key: 'pricesTrend', path: `/hqa/dashboard/prices/trend${priceSuffix}` },
    { key: 'pricesByKeyword', path: `/hqa/dashboard/prices/by-keyword${priceSuffix}` },
    { key: 'alerts', path: `/hqa/dashboard/alerts${priceSuffix}` },
  ];

  const results = await Promise.allSettled(requests.map((request) => api(request.path)));
  const sectionErrors = {};
  requests.forEach((request, index) => {
    const result = results[index];
    if (result.status === 'fulfilled') {
      state.hqa.dashboard[request.key] = result.value;
      return;
    }
    sectionErrors[request.key] = result.reason?.message || 'Failed to load section.';
  });

  state.hqa.dashboard.sectionErrors = sectionErrors;
  if (Object.keys(sectionErrors).length === requests.length) {
    state.hqa.dashboard.error = 'Could not load dashboard.';
  }
  state.hqa.dashboard.loading = false;
}

function buildSimpleLineChart({ title, points, lines }) {
  if (!points?.length) {
    return `<article class="dashboard-chart"><header><h3>${escapeHtml(title)}</h3></header><div class="empty-state">No trend data in selected range.</div></article>`;
  }
  const width = 860;
  const height = 260;
  const padLeft = 50;
  const padRight = 18;
  const padTop = 22;
  const padBottom = 48;
  const allValues = [];
  points.forEach((point) => lines.forEach((line) => allValues.push(Number(point[line.key] || 0))));
  const max = Math.max(...allValues, 1);
  const min = Math.min(...allValues, 0);
  const xStep = points.length > 1 ? (width - padLeft - padRight) / (points.length - 1) : 0;
  const yScale = (value) => {
    if (max === min) return (height - padBottom + padTop) / 2;
    return padTop + (max - value) * ((height - padTop - padBottom) / (max - min));
  };

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = min + (max - min) * ratio;
    const y = yScale(value);
    return `<g><line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#E2E8F0" stroke-width="1" /><text x="${padLeft - 8}" y="${y + 4}" text-anchor="end" font-size="11" fill="#64748B">${Math.round(value)}</text></g>`;
  }).join('');

  const monthTicks = points.map((point, index) => {
    const x = padLeft + (xStep * index);
    return `<text x="${x}" y="${height - 20}" text-anchor="middle" font-size="11" fill="#64748B">${escapeHtml(point.month || '-')}</text>`;
  }).join('');

  const lineSvg = lines.map((line) => {
    const path = points.map((point, index) => {
      const x = padLeft + (xStep * index);
      const y = yScale(Number(point[line.key] || 0));
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');
    const circles = points.map((point, index) => {
      const x = padLeft + (xStep * index);
      const value = Number(point[line.key] || 0);
      const y = yScale(value);
      return `<circle cx="${x}" cy="${y}" r="4" fill="${line.color}"><title>${escapeHtml(point.month || '-')} ${line.label}: ${value.toLocaleString()}</title></circle>`;
    }).join('');
    return `<path d="${path}" fill="none" stroke="${line.color}" stroke-width="2.5"/>${circles}`;
  }).join('');

  return `
    <article class="dashboard-chart">
      <header>
        <h3>${escapeHtml(title)}</h3>
        <div class="dashboard-legend">${lines.map((line) => `<span><i style="background:${line.color}"></i>${escapeHtml(line.label)}</span>`).join('')}</div>
      </header>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)} chart">
        ${yTicks}
        ${lineSvg}
        ${monthTicks}
      </svg>
    </article>`;
}

function dashboardStatusTable(points) {
  if (!points?.length) return '<div class="empty-state">No status trend data.</div>';
  return `<div class="table-wrap"><table><thead><tr><th>Month</th><th>Active</th><th>Ended</th><th>Out of stock</th><th>New listing</th><th>Unknown</th></tr></thead><tbody>${points.map((row) => `<tr><td>${escapeHtml(row.month || '-')}</td><td>${formatRecordCount(row.active || 0)}</td><td>${formatRecordCount(row.ended || 0)}</td><td>${formatRecordCount(row.out_of_stock || 0)}</td><td>${formatRecordCount(row.new_listing || 0)}</td><td>${formatRecordCount(row.unknown || 0)}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderHqaDashboard() {
  const dashboardView = document.getElementById('hqa-dashboard-view');
  if (!dashboardView) return;
  const data = state.hqa.dashboard;
  const sellerSummary = data.sellersSummary || {};
  const priceSummary = data.pricesSummary || {};
  const keywordItems = data.pricesByKeyword?.items || [];
  const alertItems = data.alerts?.alerts || [];
  const options = data.filterOptions || {};

  const dashboardSelectOptions = (items, selected = []) => {
    const selectedSet = new Set(selected || []);
    return (items || []).map((item) => `<option value="${escapeHtml(item)}" ${selectedSet.has(item) ? 'selected' : ''}>${escapeHtml(item)}</option>`).join('');
  };

  dashboardView.innerHTML = `
    <div class="dashboard-header-row">
      <h2>Marketplace Dashboard</h2>
      <div class="dashboard-export-actions">
        <button type="button" id="dashboard-drilldown" ${data.loading ? 'disabled' : ''}>Drill-down to Listings</button>
        <select id="dashboard-export-dataset" ${data.loading ? 'disabled' : ''}>
          <option value="sellers_summary">Sellers summary</option>
          <option value="sellers_trend">Sellers trend</option>
          <option value="sellers_top">Top sellers</option>
          <option value="prices_summary">Prices summary</option>
          <option value="prices_trend">Prices trend</option>
          <option value="prices_by_keyword">Prices by keyword</option>
          <option value="alerts">Alerts</option>
        </select>
        <button type="button" id="dashboard-export" ${(data.loading || data.isExporting) ? 'disabled' : ''}>${data.isExporting ? 'Exporting...' : 'Export CSV'}</button>
      </div>
    </div>
    <form id="dashboard-filters" class="hqa-filter-grid dashboard-filter-grid" ${data.loading ? 'data-loading="true"' : ''}>
      <h3 class="dashboard-filter-title">Seller Filters</h3>
      <input id="dashboard-seller-keyword" placeholder="Keyword" value="${escapeHtml(data.draftSellerFilters.keyword)}">
      <input id="dashboard-seller-currency" placeholder="Currency (USD...)" value="${escapeHtml(data.draftSellerFilters.currency)}">
      <label class="form-field"><span>Date from</span><input id="dashboard-seller-date-from" type="date" value="${escapeHtml(data.draftSellerFilters.dateFrom)}"></label>
      <label class="form-field"><span>Date to</span><input id="dashboard-seller-date-to" type="date" value="${escapeHtml(data.draftSellerFilters.dateTo)}"></label>
      <select id="dashboard-seller-marketplace" multiple size="4">${dashboardSelectOptions(options.marketplaces, data.draftSellerFilters.marketplaces)}</select>
      <select id="dashboard-seller-brand" multiple size="4">${dashboardSelectOptions(options.brands, data.draftSellerFilters.brands)}</select>
      <select id="dashboard-seller-model" multiple size="4">${dashboardSelectOptions(options.models, data.draftSellerFilters.models)}</select>
      <select id="dashboard-seller-status" multiple size="4">${dashboardSelectOptions(options.statuses, data.draftSellerFilters.statuses)}</select>
      <select id="dashboard-seller-category" multiple size="4">${dashboardSelectOptions(options.category_names, data.draftSellerFilters.categoryNames)}</select>
      <select id="dashboard-seller-buying" multiple size="4">${dashboardSelectOptions(options.buying_options, data.draftSellerFilters.buyingOptions)}</select>
      <select id="dashboard-seller-seller" multiple size="4">${dashboardSelectOptions(options.sellers, data.draftSellerFilters.sellers)}</select>

      <h3 class="dashboard-filter-title">Price Filters</h3>
      <input id="dashboard-price-keyword" placeholder="Keyword" value="${escapeHtml(data.draftPriceFilters.keyword)}">
      <input id="dashboard-price-currency" placeholder="Currency (USD...)" value="${escapeHtml(data.draftPriceFilters.currency)}">
      <label class="form-field"><span>Date from</span><input id="dashboard-price-date-from" type="date" value="${escapeHtml(data.draftPriceFilters.dateFrom)}"></label>
      <label class="form-field"><span>Date to</span><input id="dashboard-price-date-to" type="date" value="${escapeHtml(data.draftPriceFilters.dateTo)}"></label>
      <label class="form-field"><span>Min price</span><input id="dashboard-price-min" type="text" value="${escapeHtml(data.draftPriceFilters.minPrice)}"></label>
      <label class="form-field"><span>Max price</span><input id="dashboard-price-max" type="text" value="${escapeHtml(data.draftPriceFilters.maxPrice)}"></label>
      <select id="dashboard-price-granularity">
        <option value="day" ${data.draftPriceFilters.granularity === 'day' ? 'selected' : ''}>Day</option>
        <option value="week" ${data.draftPriceFilters.granularity === 'week' ? 'selected' : ''}>Week</option>
        <option value="month" ${data.draftPriceFilters.granularity === 'month' ? 'selected' : ''}>Month</option>
      </select>
      <div class="filter-actions"><button type="submit">Apply dashboard filters</button><button type="button" id="dashboard-reset">Reset</button></div>
      ${data.optionsError ? `<div class="error">${escapeHtml(data.optionsError)}</div>` : ''}
    </form>
    ${data.error ? `<div class="error">${escapeHtml(data.error)}</div>` : ''}
    <div class="metrics dashboard-metrics">
      ${metric('Total listings', sellerSummary.total_listings || 0)}
      ${metric('Total sellers', sellerSummary.total_sellers || 0)}
      ${metric('New sellers', sellerSummary.new_sellers || 0)}
      ${metric('Active listings', sellerSummary.active_listings || 0)}
      ${metric('Price sample', priceSummary.sample_size || 0)}
      ${metric('Avg price', priceSummary.avg_price || 0)}
      ${metric('Median price', priceSummary.median_price || 0)}
      ${metric('Min price', priceSummary.min_price || 0)}
      ${metric('Max price', priceSummary.max_price || 0)}
      ${metric('Currency', priceSummary.currency || 'unknown')}
    </div>
    <div class="dashboard-grid">
      ${buildSimpleLineChart({
        title: 'Price trend',
        points: data.pricesTrend?.points || [],
        lines: [
          { key: 'avg_price', label: 'Avg', color: '#2563EB' },
          { key: 'median_price', label: 'Median', color: '#0F766E' },
          { key: 'max_price', label: 'Max', color: '#D97706' },
        ],
      })}
      ${buildSimpleLineChart({
        title: 'Seller trend',
        points: data.sellersTrend?.points || [],
        lines: [{ key: 'seller_count', label: 'Sellers', color: '#7C3AED' }],
      })}
    </div>
    <div class="panel dashboard-subpanel">
      <h3>Prices by keyword</h3>
      <div class="table-wrap"><table><thead><tr><th>Keyword</th><th>Count</th><th>Share %</th><th>Avg</th><th>Min</th><th>Max</th></tr></thead><tbody>${keywordItems.map((item) => `<tr><td>${escapeHtml(item.keyword)}</td><td>${formatRecordCount(item.count || 0)}</td><td>${Number(item.share_pct || 0).toFixed(2)}%</td><td>${formatRecordCount(item.avg_price || 0)}</td><td>${formatRecordCount(item.min_price || 0)}</td><td>${formatRecordCount(item.max_price || 0)}</td></tr>`).join('')}</tbody></table></div>
    </div>
    <div class="panel dashboard-subpanel">
      <h3>Alerts</h3>
      ${alertItems.length
        ? `<ul class="dashboard-alerts">${alertItems.map((alert) => `<li><strong>${escapeHtml(alert.type)}</strong>: ${escapeHtml(alert.message || '')}</li>`).join('')}</ul>`
        : '<div class="empty-state">No alerts in the selected range.</div>'}
    </div>
    <div class="panel dashboard-subpanel">
      <h3>Top sellers</h3>
      <div class="table-wrap"><table><thead><tr><th>Seller</th><th>Listings</th><th>Unique listings</th><th>Avg price</th><th>Min</th><th>Max</th></tr></thead><tbody>${(data.topSellers?.items || []).map((item) => `<tr><td>${escapeHtml(item.seller || '-')}</td><td>${formatRecordCount(item.listing_count || 0)}</td><td>${formatRecordCount(item.unique_listings || 0)}</td><td>${formatRecordCount(item.avg_price || 0)}</td><td>${formatRecordCount(item.min_price || 0)}</td><td>${formatRecordCount(item.max_price || 0)}</td></tr>`).join('')}</tbody></table></div>
    </div>`;
}

function dataCheckGroupKey(item) {
  const marketplace = String(item?.marketplace || '').trim().toLowerCase();
  const listingId = String(item?.listing_id || '').trim().toLowerCase();
  return `${marketplace}::${listingId}`;
}

function buildDataCheckParams(page = 1) {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', String(state.hqa.dataCheck.pageSize || 20));
  const filters = state.hqa.dataCheck.filters || {};
  if (filters.marketplace) params.set('marketplace', filters.marketplace.trim());
  if (filters.listingId) params.set('listing_id', filters.listingId.trim());
  if (filters.status) params.set('status', filters.status.trim());
  return params;
}

async function loadDataCheckSummaryAndGroups(page = 1) {
  state.hqa.dataCheck.loading = true;
  state.hqa.dataCheck.error = '';
  try {
    const [summary, groups] = await Promise.all([
      api('/hqa/data-check/duplicates/summary'),
      api(`/hqa/data-check/duplicates?${buildDataCheckParams(page).toString()}`),
    ]);
    state.hqa.dataCheck.hasRun = true;
    state.hqa.dataCheck.summary = summary;
    state.hqa.dataCheck.groups = groups;
    state.hqa.dataCheck.page = Number(groups?.page || page);
  } catch (error) {
    state.hqa.dataCheck.error = error.message || 'Khong the kiem tra du lieu.';
  } finally {
    state.hqa.dataCheck.loading = false;
  }
}

function renderDataCheckDetailRows(item) {
  const keepRecord = item.keep_record || {};
  const allRows = [
    { ...keepRecord, keep: true },
    ...((item.delete_records || []).map((row) => ({ ...row, keep: false }))),
  ];
  if (!allRows.length) return '<div class="empty-state">Khong co record chi tiet.</div>';
  return `
    <div class="table-wrap data-check-detail-table-wrap">
      <table class="data-check-detail-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>ID</th>
            <th>Listing title</th>
            <th>Status</th>
            <th>Quantity</th>
            <th>Collected at</th>
            <th>Updated at</th>
            <th>Listing published at</th>
            <th>Last status checked at</th>
          </tr>
        </thead>
        <tbody>
          ${allRows.map((row) => `<tr>
            <td><span class="${row.keep ? 'data-check-keep-pill' : 'data-check-delete-pill'}">${row.keep ? 'Giu lai' : 'Se xoa'}</span></td>
            <td>${escapeHtml(row.id || '-')}</td>
            <td>${escapeHtml(row.listing_title || '-')}</td>
            <td>${escapeHtml(normalizeListingStatus(row.listing_status).label)}</td>
            <td>${escapeHtml(row.quantity ?? '-')}</td>
            <td>${escapeHtml(formatDateTimeHcm(row.collected_at))}</td>
            <td>${escapeHtml(formatDateTimeHcm(row.updated_at))}</td>
            <td>${escapeHtml(formatDateTimeHcm(row.listing_published_at))}</td>
            <td>${escapeHtml(formatDateTimeHcm(row.last_status_checked_at))}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

function renderDataCheckTable() {
  const groups = state.hqa.dataCheck.groups;
  if (!groups || !groups.items?.length) {
    if (!state.hqa.dataCheck.hasRun) {
      return '<div class="empty-state">Nhan "Kiem tra du lieu" de quet bang marketplace_research_results.</div>';
    }
    return '<div class="empty-state">Không phát hiện listing trùng</div>';
  }

  return `
    <div class="table-wrap">
      <table class="data-check-table">
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Listing ID</th>
            <th>So record trung</th>
            <th>Record duoc giu</th>
            <th>Trang thai duoc giu</th>
            <th>Last status checked</th>
            <th>So record se xoa</th>
            <th>Chi tiet</th>
          </tr>
        </thead>
        <tbody>
          ${groups.items.map((item) => {
            const key = dataCheckGroupKey(item);
            const expanded = Boolean(state.hqa.dataCheck.expandedKeys[key]);
            const keep = item.keep_record || {};
            const deleteCount = Number(item.delete_records?.length || 0);
            return `
              <tr>
                <td>${escapeHtml(item.marketplace || '-')}</td>
                <td>${escapeHtml(item.listing_id || '-')}</td>
                <td>${formatRecordCount(item.record_count || 0)}</td>
                <td>${escapeHtml(keep.id || '-')}</td>
                <td><span class="status-pill ${statusClass(keep.listing_status)}">${escapeHtml(normalizeListingStatus(keep.listing_status).label)}</span></td>
                <td>${escapeHtml(formatDateTimeHcm(keep.last_status_checked_at))}</td>
                <td>${formatRecordCount(deleteCount)}</td>
                <td><button type="button" data-data-check-toggle="${escapeHtml(key)}">${expanded ? 'An chi tiet' : 'Xem chi tiet'}</button></td>
              </tr>
              ${expanded ? `<tr><td colspan="8">${renderDataCheckDetailRows(item)}</td></tr>` : ''}
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
    <div class="listing-footer-summary data-check-pager">
      <div class="listing-page-count">Page ${groups.page || 1} / ${Math.max(1, Math.ceil((groups.total_groups || 0) / (groups.page_size || 20)))}</div>
      <div class="inline-actions">
        <button type="button" data-data-check-page="prev" ${(groups.page || 1) <= 1 ? 'disabled' : ''}>Previous</button>
        <button type="button" data-data-check-page="next" ${((groups.page || 1) * (groups.page_size || 20)) >= (groups.total_groups || 0) ? 'disabled' : ''}>Next</button>
      </div>
    </div>`;
}

function renderDataCheckModal() {
  const existing = document.querySelector('.data-check-modal-backdrop');
  if (!state.hqa.dataCheck.showConfirmModal) {
    if (existing) existing.remove();
    if (state.hqa.dataCheck.modalKeydownHandler) {
      document.removeEventListener('keydown', state.hqa.dataCheck.modalKeydownHandler);
      state.hqa.dataCheck.modalKeydownHandler = null;
    }
    return;
  }

  const recordsToDelete = Number(state.hqa.dataCheck.summary?.records_to_delete || 0);
  if (existing) existing.remove();
  if (state.hqa.dataCheck.modalKeydownHandler) {
    document.removeEventListener('keydown', state.hqa.dataCheck.modalKeydownHandler);
    state.hqa.dataCheck.modalKeydownHandler = null;
  }

  const backdrop = document.createElement('div');
  backdrop.className = 'data-check-modal-backdrop';
  backdrop.innerHTML = `
    <div class="data-check-modal" role="dialog" aria-modal="true" aria-label="Xac nhan xoa du lieu trung">
      <h3>Xac nhan xoa du lieu trung</h3>
      <p>Ban sap xoa <strong>${formatRecordCount(recordsToDelete)}</strong> record trung.</p>
      <p>Nhap chinh xac: <strong>DELETE_DUPLICATE_LISTINGS</strong></p>
      <input id="data-check-confirm-input" autocomplete="off" spellcheck="false" placeholder="DELETE_DUPLICATE_LISTINGS" value="${escapeHtml(state.hqa.dataCheck.confirmationInput || '')}">
      <div class="inline-actions data-check-modal-actions">
        <button type="button" id="data-check-cancel-button">Huy</button>
        <button type="button" id="data-check-confirm-button">Xoa du lieu trung</button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  const dialog = backdrop.querySelector('.data-check-modal');
  const input = backdrop.querySelector('#data-check-confirm-input');
  const cancelButton = backdrop.querySelector('#data-check-cancel-button');
  const confirmButton = backdrop.querySelector('#data-check-confirm-button');

  const updateControls = () => {
    const tokenMatched = (state.hqa.dataCheck.confirmationInput || '').trim() === 'DELETE_DUPLICATE_LISTINGS';
    const loading = Boolean(state.hqa.dataCheck.loadingCleanup);
    input.disabled = loading;
    cancelButton.disabled = loading;
    confirmButton.disabled = loading || !tokenMatched;
    confirmButton.textContent = loading ? 'Dang xoa...' : 'Xoa du lieu trung';
  };

  const closeModal = () => {
    if (state.hqa.dataCheck.loadingCleanup) return;
    state.hqa.dataCheck.showConfirmModal = false;
    state.hqa.dataCheck.confirmationInput = '';
    backdrop.remove();
    if (state.hqa.dataCheck.modalKeydownHandler) {
      document.removeEventListener('keydown', state.hqa.dataCheck.modalKeydownHandler);
      state.hqa.dataCheck.modalKeydownHandler = null;
    }
    renderDataCheckView();
  };

  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) {
      closeModal();
    }
  });

  dialog.addEventListener('click', (event) => {
    event.stopPropagation();
  });

  input.addEventListener('input', (event) => {
    state.hqa.dataCheck.confirmationInput = String(event.target.value || '');
    updateControls();
  });

  input.addEventListener('keydown', async (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    if (confirmButton.disabled) return;
    confirmButton.click();
  });

  cancelButton.addEventListener('click', () => {
    closeModal();
  });

  confirmButton.addEventListener('click', async () => {
    if ((state.hqa.dataCheck.confirmationInput || '').trim() !== 'DELETE_DUPLICATE_LISTINGS') {
      updateControls();
      return;
    }
    state.hqa.dataCheck.loadingCleanup = true;
    updateControls();
    await executeDataCheckCleanup();
    if (!state.hqa.dataCheck.showConfirmModal) {
      if (state.hqa.dataCheck.modalKeydownHandler) {
        document.removeEventListener('keydown', state.hqa.dataCheck.modalKeydownHandler);
        state.hqa.dataCheck.modalKeydownHandler = null;
      }
      backdrop.remove();
      return;
    }
    state.hqa.dataCheck.loadingCleanup = false;
    updateControls();
  });

  const keydownHandler = (event) => {
    if (event.key === 'Escape') {
      closeModal();
    }
  };
  state.hqa.dataCheck.modalKeydownHandler = keydownHandler;
  document.addEventListener('keydown', keydownHandler);

  updateControls();
  requestAnimationFrame(() => {
    input.focus();
  });
}

function renderDataCheckView() {
  const view = document.getElementById('hqa-data-check-view');
  if (!view) return;
  const summary = state.hqa.dataCheck.summary || {
    total_records: 0,
    unique_listing_keys: 0,
    duplicate_groups: 0,
    duplicate_records: 0,
    records_to_delete: 0,
    missing_listing_id: 0,
  };
  const canCleanup = state.hqa.dataCheck.hasRun && Number(summary.records_to_delete || 0) > 0;

  view.innerHTML = `
    <div class="dashboard-header-row">
      <h2>Kiem tra du lieu listing trung</h2>
      <div class="inline-actions">
        <button type="button" id="data-check-run" ${state.hqa.dataCheck.loading ? 'disabled' : ''}>${state.hqa.dataCheck.loading ? 'Dang kiem tra...' : 'Kiem tra du lieu'}</button>
        <button type="button" id="data-check-refresh" ${(state.hqa.dataCheck.loading || !state.hqa.dataCheck.hasRun) ? 'disabled' : ''}>Lam moi</button>
        ${canCleanup ? `<button type="button" id="data-check-cleanup" ${state.hqa.dataCheck.loadingCleanup ? 'disabled' : ''}>${state.hqa.dataCheck.loadingCleanup ? 'Dang xu ly...' : 'Xoa du lieu trung'}</button>` : ''}
      </div>
    </div>
    ${state.hqa.dataCheck.error ? `<div class="error">${escapeHtml(state.hqa.dataCheck.error)}</div>` : ''}
    ${state.hqa.dataCheck.cleanupResult ? `<div class="hqa-toast hqa-toast-success"><span>Da xoa ${formatRecordCount(state.hqa.dataCheck.cleanupResult.records_deleted || 0)} record trung.</span></div>` : ''}
    <div class="metrics data-check-metrics">
      ${metric('Tong record', summary.total_records || 0)}
      ${metric('Listing duy nhat', summary.unique_listing_keys || 0)}
      ${metric('Nhom bi trung', summary.duplicate_groups || 0)}
      ${metric('Record bi trung', summary.duplicate_records || 0)}
      ${metric('Record se xoa', summary.records_to_delete || 0)}
      ${metric('Record thieu listing ID', summary.missing_listing_id || 0)}
    </div>
    <form id="data-check-filters" class="filters hqa-filter-grid">
      <label class="filter-field filter-field--product"><span class="filter-field__label">Marketplace</span><input id="data-check-marketplace" value="${escapeHtml(state.hqa.dataCheck.filters.marketplace)}" placeholder="ebay"></label>
      <label class="filter-field filter-field--product"><span class="filter-field__label">Listing ID</span><input id="data-check-listing-id" value="${escapeHtml(state.hqa.dataCheck.filters.listingId)}" placeholder="398210152319"></label>
      <label class="filter-field filter-field--status"><span class="filter-field__label">Status (record giu)</span><input id="data-check-status" value="${escapeHtml(state.hqa.dataCheck.filters.status)}" placeholder="ended"></label>
      <div class="filter-actions"><button type="submit" ${(state.hqa.dataCheck.loading || !state.hqa.dataCheck.hasRun) ? 'disabled' : ''}>Loc ket qua</button></div>
    </form>
    ${state.hqa.dataCheck.hasRun && Number(summary.records_to_delete || 0) <= 0 ? '<div class="empty-state">Không phát hiện listing trùng</div>' : ''}
    ${renderDataCheckTable()}
  `;
  renderDataCheckModal();
}

async function executeDataCheckCleanup() {
  state.hqa.dataCheck.error = '';
  renderDataCheckView();
  try {
    const response = await api('/hqa/data-check/duplicates/cleanup', {
      method: 'POST',
      body: JSON.stringify({ confirmation: 'DELETE_DUPLICATE_LISTINGS' }),
    });
    state.hqa.dataCheck.cleanupResult = response;
    state.hqa.dataCheck.showConfirmModal = false;
    state.hqa.dataCheck.confirmationInput = '';
    await loadDataCheckSummaryAndGroups(1);
    await loadAllListingsSummary();
    renderHqaSummary();
    await loadActiveListings({ scrollToTable: false });
    setAllListingsNotification('success', `Da xoa ${formatRecordCount(response.records_deleted || 0)} record trung.`);
  } catch (error) {
    state.hqa.dataCheck.error = error.message || 'Xoa du lieu trung that bai.';
  } finally {
    state.hqa.dataCheck.loadingCleanup = false;
    renderDataCheckView();
  }
}

async function downloadCsv(path, filename, retry = true) {
  const headers = new Headers();
  if (state.accessToken) headers.set('Authorization', `Bearer ${state.accessToken}`);
  const response = await fetch(`/api/v1${path}`, { method: 'GET', headers, credentials: 'include' });
  if (response.status === 401 && retry) {
    if (await refreshSession()) return downloadCsv(path, filename, false);
  }
  if (!response.ok) {
    let message = `CSV export failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch (_) { /* no-op */ }
    throw new Error(message);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

function setAllListingsNotification(type, message) {
  state.hqa.allListings.notification = { type, message };
  renderAllListingsToast();
}

function clearAllListingsNotification() {
  state.hqa.allListings.notification = null;
  renderAllListingsToast();
}

function renderAllListingsToast() {
  const host = document.getElementById('hqa-toast-host');
  if (!host) return;
  const notice = state.hqa.allListings.notification;
  if (!notice) {
    host.innerHTML = '';
    return;
  }
  host.innerHTML = `
    <div class="hqa-toast hqa-toast-${escapeHtml(notice.type)}" role="status" aria-live="polite">
      <span>${escapeHtml(notice.message)}</span>
      <button type="button" id="hqa-toast-close" aria-label="Close notification">Close</button>
    </div>`;
  const closeButton = document.getElementById('hqa-toast-close');
  if (closeButton && !closeButton.dataset.bound) {
    closeButton.dataset.bound = 'true';
    closeButton.addEventListener('click', clearAllListingsNotification);
  }
}

function appendArrayParams(params, key, values) {
  (values || []).forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized) return;
    params.append(key, normalized);
  });
}

function buildAllListingsParams(page = 1, includePagination = true) {
  const filters = state.hqa.allListings.appliedFilters;
  const params = new URLSearchParams();
  if (includePagination) {
    params.set('page', String(page));
    params.set('page_size', String(state.hqa.pageSize));
  }
  if (filters.fromDate) params.set('from_date', filters.fromDate);
  if (filters.toDate) params.set('to_date', filters.toDate);
  if (filters.marketplace) params.set('marketplace', filters.marketplace);
  if (filters.brand) params.set('brand', filters.brand);
  if (filters.model) params.set('model', filters.model);
  if (filters.sortCollected) params.set('sort_collected', filters.sortCollected);
  if (filters.search) params.set('search', filters.search.trim());
  if (filters.minPrice !== '') params.set('min_price', String(filters.minPrice).trim());
  if (filters.maxPrice !== '') params.set('max_price', String(filters.maxPrice).trim());
  appendArrayParams(params, 'condition', filters.conditions);
  appendArrayParams(params, 'status', filters.statuses);
  appendArrayParams(params, 'category_name', filters.categoryNames);
  appendArrayParams(params, 'buying_option', filters.buyingOptions);
  return params;
}

function buildAllListingsOptionsParams() {
  const filters = state.hqa.allListings.draftFilters;
  const params = new URLSearchParams();
  if (filters.fromDate) params.set('from_date', filters.fromDate);
  if (filters.toDate) params.set('to_date', filters.toDate);
  if (filters.marketplace) params.set('marketplace', filters.marketplace);
  if (filters.brand) params.set('brand', filters.brand);
  if (filters.model) params.set('model', filters.model);
  if (filters.search) params.set('search', filters.search.trim());
  if (filters.minPrice !== '') params.set('min_price', String(filters.minPrice).trim());
  if (filters.maxPrice !== '') params.set('max_price', String(filters.maxPrice).trim());
  appendArrayParams(params, 'condition', filters.conditions);
  appendArrayParams(params, 'status', filters.statuses);
  appendArrayParams(params, 'category_name', filters.categoryNames);
  appendArrayParams(params, 'buying_option', filters.buyingOptions);
  return params;
}

function buildMultiSelectLabel(selectedValues, allLabel) {
  if (!selectedValues?.length) return allLabel;
  if (selectedValues.length === 1) return selectedValues[0];
  if (selectedValues.length === 2) return `${selectedValues[0]}, ${selectedValues[1]}`;
  return `${selectedValues.length} selected`;
}

function getMultiSelectChipClass(fieldKey, value) {
  if (fieldKey !== 'statuses') return 'multi-select-chip';
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'active') return 'multi-select-chip multi-select-chip-status-active';
  if (normalized === 'out_of_stock') return 'multi-select-chip multi-select-chip-status-out';
  if (normalized === 'ended' || normalized === 'end') return 'multi-select-chip multi-select-chip-status-ended';
  return 'multi-select-chip';
}

function buildMultiSelectChipPreview(fieldKey, label, selectedValues = []) {
  const values = (selectedValues || []).map((value) => String(value || '').trim()).filter(Boolean);
  if (!values.length) {
    return `<span class="multi-select-placeholder">${escapeHtml(label)}</span>`;
  }
  const visible = values.slice(0, 2);
  const extra = values.length - visible.length;
  const chips = visible.map((value) => `<span class="${getMultiSelectChipClass(fieldKey, value)}">${escapeHtml(value)}</span>`).join('<span class="multi-select-chip-separator">|</span>');
  if (extra > 0) {
    return `${chips}<span class="multi-select-chip-separator">|</span><span class="multi-select-chip">+${extra}</span>`;
  }
  return chips;
}

function isAllListingsPriceRangeInvalid(filters) {
  if (filters.minPrice === '' || filters.maxPrice === '') return false;
  const minValue = Number(filters.minPrice);
  const maxValue = Number(filters.maxPrice);
  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return false;
  return minValue > maxValue;
}

function parseNonNegativeNumber(rawValue) {
  if (rawValue === '' || rawValue === null || rawValue === undefined) return { ok: true, value: '' };
  const candidate = String(rawValue).trim();
  let normalized = candidate;
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(candidate)) {
    normalized = candidate.replace(/,/g, '');
  }
  if (!/^\d+(\.\d+)?$/.test(normalized)) {
    return { ok: false, message: 'Gia tri gia phai la so hop le.' };
  }
  const numeric = Number(normalized);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return { ok: false, message: 'Gia khong duoc am.' };
  }
  return { ok: true, value: normalized };
}

async function loadAllListingsFilterOptions() {
  state.hqa.allListings.loadingOptions = true;
  state.hqa.allListings.optionsError = '';
  try {
    await Promise.all([
      loadLazyOptionField('marketplace', { reset: true, useCache: true }),
      loadLazyOptionField('brand', { reset: true, useCache: true }),
    ]);
  } catch (error) {
    state.hqa.allListings.optionsError = error.message || 'Could not load All Listings base filter options.';
  } finally {
    state.hqa.allListings.loadingOptions = false;
  }
}

async function loadAllListingsSummary() {
  state.hqa.allListings.loadingSummary = true;
  state.hqa.allListings.summaryError = '';
  try {
    const params = buildAllListingsParams(1, false);
    state.hqa.allListings.summary = await api(`/hqa/listings/summary?${params.toString()}`);
  } catch (error) {
    state.hqa.allListings.summaryError = error.message || 'Could not load All Listings summary.';
  } finally {
    state.hqa.allListings.loadingSummary = false;
  }
}

function renderHqaSummary() {
  const summaryContainer = document.getElementById('hqa-summary');
  if (!summaryContainer) return;
  const allSummary = state.hqa.allListings.summary || {};
  summaryContainer.innerHTML = `
    ${metric('Total records stored', allSummary.total_records_stored || 0, `Unique listing IDs: ${allSummary.unique_listing_ids || 0}`)}
    ${metric('Filtered records', allSummary.filtered_records || 0)}
    ${metric('Active', allSummary.active || 0)}
    ${metric('Ended', allSummary.ended || 0)}
    ${metric('Out of stock', allSummary.out_of_stock || 0)}`;
}

function cloneAllListingsFilters(filters) {
  return {
    ...filters,
    conditions: [...(filters.conditions || [])],
    statuses: [...(filters.statuses || [])],
    categoryNames: [...(filters.categoryNames || [])],
    buyingOptions: [...(filters.buyingOptions || [])],
  };
}

function buildDefaultAllListingsFilters() {
  return {
    fromDate: '',
    toDate: '',
    marketplace: '',
    brand: '',
    model: '',
    conditions: [],
    statuses: [],
    categoryNames: [],
    buyingOptions: [],
    sortCollected: 'newest',
    minPrice: '',
    maxPrice: '',
    search: '',
  };
}

function snapshotAllListingsFiltersFromDom() {
  return {
    fromDate: document.getElementById('from-date')?.value || '',
    toDate: document.getElementById('to-date')?.value || '',
    marketplace: document.getElementById('marketplace')?.value || '',
    brand: document.getElementById('brand')?.value || '',
    model: state.hqa.allListings.draftFilters.model || '',
    conditions: [...(state.hqa.allListings.draftFilters.conditions || [])],
    statuses: [...(state.hqa.allListings.draftFilters.statuses || [])],
    categoryNames: [...(state.hqa.allListings.draftFilters.categoryNames || [])],
    buyingOptions: [...(state.hqa.allListings.draftFilters.buyingOptions || [])],
    sortCollected: document.getElementById('sort-collected')?.value || 'newest',
    minPrice: document.getElementById('min-price')?.value.trim() || '',
    maxPrice: document.getElementById('max-price')?.value.trim() || '',
    search: document.getElementById('search')?.value.trim() || '',
  };
}

function updateAllListingsDraftFilterField(key, value) {
  state.hqa.allListings.draftFilters = {
    ...state.hqa.allListings.draftFilters,
    [key]: value,
  };
}

function updateAllListingsDraftMultiSelect(key, values) {
  state.hqa.allListings.draftFilters = {
    ...state.hqa.allListings.draftFilters,
    [key]: [...new Set((values || []).map((value) => String(value || '').trim()).filter(Boolean))],
  };
}

function getDraftValuesByLazyApiField(apiField) {
  const config = getLazyFilterConfigByApiField(apiField);
  if (!config) return [];
  const current = state.hqa.allListings.draftFilters[config.stateKey];
  if (config.multiple) {
    return [...new Set((current || []).map((value) => String(value || '').trim()).filter(Boolean))];
  }
  return current ? [String(current).trim()] : [];
}

function setDraftValuesByLazyApiField(apiField, values) {
  const config = getLazyFilterConfigByApiField(apiField);
  if (!config) return;
  const normalized = [...new Set((values || []).map((value) => String(value || '').trim()).filter(Boolean))];
  if (config.multiple) {
    updateAllListingsDraftMultiSelect(config.stateKey, normalized);
    return;
  }
  updateAllListingsDraftFilterField(config.stateKey, normalized[0] || '');
}

function toggleLazyOptionValue(apiField, value) {
  const config = getLazyFilterConfigByApiField(apiField);
  const normalizedValue = String(value || '').trim();
  if (!config || !normalizedValue) return;

  if (!config.multiple) {
    setDraftValuesByLazyApiField(apiField, [normalizedValue]);
    state.hqa.allListings.openLazyField = '';
    renderHqaFilterOptions();
    return;
  }

  const currentValues = getDraftValuesByLazyApiField(apiField);
  const set = new Set(currentValues.map((item) => item.toLowerCase()));
  if (set.has(normalizedValue.toLowerCase())) {
    setDraftValuesByLazyApiField(apiField, currentValues.filter((item) => item.toLowerCase() !== normalizedValue.toLowerCase()));
  } else {
    setDraftValuesByLazyApiField(apiField, [...currentValues, normalizedValue]);
  }
  renderHqaFilterOptions();
}

function setAllLoadedLazyOptions(apiField, checked) {
  const config = getLazyFilterConfigByApiField(apiField);
  if (!config || !config.multiple) return;
  const lazyState = state.hqa.allListings.lazyOptions[config.uiField] || defaultLazyOptionState();
  const loadedValues = (lazyState.items || []).map((item) => normalizeOptionValue(item?.value || item)).filter(Boolean);
  const nextValues = checked ? loadedValues : [];
  setDraftValuesByLazyApiField(apiField, nextValues);
  renderHqaFilterOptions();
}

function openAllListingsLazyField(apiField) {
  const config = getLazyFilterConfigByApiField(apiField);
  if (!config) return;
  const isClosing = state.hqa.allListings.openLazyField === apiField;
  state.hqa.allListings.openLazyField = isClosing ? '' : apiField;
  renderHqaFilterOptions();

  if (isClosing) return;
  const fieldState = state.hqa.allListings.lazyOptions[config.uiField];
  if (fieldState && !fieldState.isLoaded && !fieldState.isLoading) {
    loadLazyOptionField(config.uiField, { reset: true, useCache: true }).then(() => {
      if (state.hqa.allListings.openLazyField === apiField) {
        renderHqaFilterOptions();
      }
    });
  }
}

function bindAllListingsFilterEvents() {
  if (allListingsFilterEventsBound) return;
  const filterContainer = document.getElementById('hqa-filter-options');
  if (!filterContainer) return;

  allListingsFilterEventsBound = true;

  filterContainer.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.id !== 'hqa-filters') return;
    event.preventDefault();

    const nextFilters = snapshotAllListingsFiltersFromDom();
    if (nextFilters.fromDate && nextFilters.toDate && nextFilters.fromDate > nextFilters.toDate) {
      setAllListingsNotification('warning', 'From date must be less than or equal to To date.');
      return;
    }
    const parsedMinPrice = parseNonNegativeNumber(nextFilters.minPrice);
    if (!parsedMinPrice.ok) {
      setAllListingsNotification('warning', parsedMinPrice.message);
      return;
    }
    const parsedMaxPrice = parseNonNegativeNumber(nextFilters.maxPrice);
    if (!parsedMaxPrice.ok) {
      setAllListingsNotification('warning', parsedMaxPrice.message);
      return;
    }
    nextFilters.minPrice = parsedMinPrice.value;
    nextFilters.maxPrice = parsedMaxPrice.value;
    if (nextFilters.minPrice !== '' && nextFilters.maxPrice !== '' && Number(nextFilters.minPrice) > Number(nextFilters.maxPrice)) {
      setAllListingsNotification('warning', 'Min price must be less than or equal to max price.');
      return;
    }

    clearAllListingsNotification();
    state.hqa.allListings.openLazyField = '';
    state.hqa.allListings.draftFilters = cloneAllListingsFilters(nextFilters);
    state.hqa.allListings.appliedFilters = cloneAllListingsFilters(nextFilters);
    state.hqa.page = 1;
    await loadAllListingsSummary();
    renderHqaSummary();
    await loadActiveListings();
    renderHqaFilterOptions();
  });

  filterContainer.addEventListener('input', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === 'search') {
      updateAllListingsDraftFilterField('search', target.value.trim());
    }
    if (target.id === 'min-price') {
      updateAllListingsDraftFilterField('minPrice', target.value.trim());
    }
    if (target.id === 'max-price') {
      updateAllListingsDraftFilterField('maxPrice', target.value.trim());
    }
    const searchInput = target.closest('[data-option-search-input]');
    if (searchInput instanceof HTMLInputElement) {
      const uiField = searchInput.getAttribute('data-option-search-input') || '';
      debounceLazyOptionSearch(uiField, searchInput.value);
    }
  });

  filterContainer.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const selectAll = target.closest('[data-option-select-all]');
    if (selectAll && selectAll instanceof HTMLInputElement) {
      const apiField = selectAll.getAttribute('data-option-select-all') || '';
      setAllLoadedLazyOptions(apiField, Boolean(selectAll.checked));
      return;
    }

    if (!['from-date', 'to-date', 'marketplace', 'brand', 'sort-collected'].includes(target.id)) return;

    const before = cloneAllListingsFilters(state.hqa.allListings.draftFilters);
    const next = snapshotAllListingsFiltersFromDom();
    if (target.id === 'brand' && before.brand !== next.brand) {
      next.model = '';
      resetLazyOptionField('model', { clearCache: true });
    }
    state.hqa.allListings.draftFilters = cloneAllListingsFilters(next);
    renderHqaFilterOptions();
  });

  filterContainer.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const trigger = target.closest('[data-lazy-filter-trigger]');
    if (trigger) {
      event.preventDefault();
      event.stopPropagation();
      const apiField = trigger.getAttribute('data-lazy-filter-trigger') || '';
      openAllListingsLazyField(apiField);
      return;
    }

    const option = target.closest('[data-option-value]');
    if (option) {
      event.preventDefault();
      event.stopPropagation();
      const apiField = option.getAttribute('data-option-field') || '';
      const value = option.getAttribute('data-option-value') || '';
      toggleLazyOptionValue(apiField, value);
      return;
    }

    const retryButton = target.closest('[data-option-retry]');
    if (retryButton) {
      event.preventDefault();
      event.stopPropagation();
      const apiField = retryButton.getAttribute('data-option-retry') || '';
      const config = getLazyFilterConfigByApiField(apiField);
      if (!config) return;
      await loadLazyOptionField(config.uiField, { reset: true, useCache: false });
      renderHqaFilterOptions();
      return;
    }

    const loadMoreButton = target.closest('[data-option-load-more]');
    if (loadMoreButton) {
      event.preventDefault();
      event.stopPropagation();
      const apiField = loadMoreButton.getAttribute('data-option-load-more') || '';
      const config = getLazyFilterConfigByApiField(apiField);
      if (!config) return;
      await loadLazyOptionField(config.uiField, { reset: false, useCache: false });
      renderHqaFilterOptions();
      return;
    }

    const clearButton = target.closest('[data-option-clear]');
    if (clearButton) {
      event.preventDefault();
      event.stopPropagation();
      const apiField = clearButton.getAttribute('data-option-clear') || '';
      setDraftValuesByLazyApiField(apiField, []);
      renderHqaFilterOptions();
      return;
    }

    if (target.id === 'reset-filters') {
      event.preventDefault();
      state.hqa.allListings.openLazyField = '';
      const resetAll = buildDefaultAllListingsFilters();
      state.hqa.allListings.draftFilters = cloneAllListingsFilters(resetAll);
      state.hqa.allListings.appliedFilters = cloneAllListingsFilters(resetAll);
      state.hqa.page = 1;
      clearAllListingsNotification();
      resetLazyOptionField('model', { clearCache: true });
      renderHqaFilterOptions();
      await loadAllListingsSummary();
      renderHqaSummary();
      await loadActiveListings();
      return;
    }

    if (target.id === 'refresh-inline') {
      event.preventDefault();
      state.hqa.allListings.openLazyField = '';
      state.hqa.allListings.draftFilters = cloneAllListingsFilters(state.hqa.allListings.appliedFilters);
      clearAllLazyOptionCache();
      await loadAllListingsFilterOptions();
      renderHqaFilterOptions();
      await loadAllListingsSummary();
      renderHqaSummary();
      await loadActiveListings({ scrollToTable: false });
      return;
    }

    if (target.id === 'export-all-listings') {
      event.preventDefault();
      state.hqa.allListings.isExporting = true;
      renderHqaFilterOptions();
      setAllListingsNotification('info', 'Dang xuat CSV...');
      try {
        const params = buildAllListingsParams(1, false);
        await downloadCsv(`/hqa/listings/export?${params.toString()}`, 'hqa_all_listings.csv');
        setAllListingsNotification('success', 'Export CSV thanh cong.');
      } catch (error) {
        const message = (error?.message || '').toLowerCase().includes('no data')
          ? 'Khong co du lieu de xuat.'
          : 'Xuat CSV that bai. Vui long thu lai.';
        setAllListingsNotification((error?.message || '').toLowerCase().includes('no data') ? 'warning' : 'error', message);
      } finally {
        state.hqa.allListings.isExporting = false;
        renderHqaFilterOptions();
      }
    }
  });

  filterContainer.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!state.hqa.allListings.openLazyField) return;
    state.hqa.allListings.openLazyField = '';
    renderHqaFilterOptions();
  });

  if (!allListingsOutsideClickBound) {
    allListingsOutsideClickBound = true;
    document.addEventListener('click', (event) => {
      if (!state.hqa.allListings.openLazyField) return;
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest('#hqa-filters')) return;
      state.hqa.allListings.openLazyField = '';
      renderHqaFilterOptions();
    });
  }
}

function renderLazyOptionSelectedBlock(fieldKey, selectedValues, loadedValuesSet) {
  const config = getLazyFilterConfigByUiField(fieldKey);
  if (!config) return '';
  const missingSelected = (selectedValues || []).filter((value) => !loadedValuesSet.has(value.toLowerCase()));
  if (!missingSelected.length) return '';
  if (!config.multiple) {
    const value = String(missingSelected[0] || '').trim();
    if (!value) return '';
    return `
      <div class="multi-select-selected-block">
        <div class="multi-select-selected-title">Selected</div>
        <button type="button" class="lazy-option-row is-selected" data-option-field="${config.apiField}" data-option-value="${escapeHtml(value)}">${escapeHtml(value)}</button>
      </div>`;
  }
  return `
    <div class="multi-select-selected-block">
      <div class="multi-select-selected-title">Selected</div>
      ${missingSelected.map((item) => `<label class="multi-select-option is-selected" data-option-field="${config.apiField}" data-option-value="${escapeHtml(item)}"><input type="checkbox" value="${escapeHtml(item)}" checked> <span class="multi-select-option__label">${escapeHtml(item)}</span></label>`).join('')}
    </div>`;
}

function renderAllListingsLazySelect(apiField, label, selectedValues = [], fieldClass = '') {
  const fieldConfig = getLazyFilterConfigByApiField(apiField);
  if (!fieldConfig) return '';
  const { uiField } = fieldConfig;
  const fieldKey = uiField;
  const optionState = state.hqa.allListings.lazyOptions[fieldKey] || defaultLazyOptionState();
  const expanded = state.hqa.allListings.openLazyField === apiField;
  const selected = new Set((selectedValues || []).map((value) => String(value || '').trim()).filter(Boolean));
  const selectedArray = [...selected];
  const loadedValuesSet = new Set((optionState.items || []).map((item) => String(item.value || '').trim().toLowerCase()).filter(Boolean));
  const loadedOptions = (optionState.items || []).map((item) => ({
    value: String(item.value || '').trim(),
    label: String(item.label || item.value || '').trim(),
  })).filter((item) => item.value);
  const selectedCount = selectedArray.length;
  const allChecked = loadedOptions.length > 0 && loadedOptions.every((item) => selected.has(item.value));
  const triggerLabel = buildMultiSelectLabel(selectedArray, label);

  return `
    <label class="filter-field ${fieldClass}">
      <span class="filter-field__label">${escapeHtml(label)}</span>
      <div class="multi-select" data-multi-select="${fieldKey}">
        <button type="button" class="multi-select-trigger" data-lazy-filter-trigger="${apiField}" aria-haspopup="listbox" aria-expanded="${expanded ? 'true' : 'false'}">
          <span class="multi-select-trigger-content" title="${escapeHtml(triggerLabel)}">${buildMultiSelectChipPreview(fieldKey, label, selectedArray)}</span>
          <span class="multi-select-chevron" aria-hidden="true">▾</span>
        </button>
        <div class="multi-select-dropdown" ${expanded ? '' : 'hidden'}>
          ${fieldConfig.searchable ? `<div class="multi-select-search"><input type="text" data-option-search-input="${fieldKey}" placeholder="Search..." value="${escapeHtml(optionState.search || '')}"></div>` : ''}
          <div class="multi-select-actions">
            ${fieldConfig.multiple ? `<label><input type="checkbox" data-option-select-all="${apiField}" ${allChecked ? 'checked' : ''}> Select all loaded</label>` : '<span class="multi-select-actions-hint">Select one value</span>'}
            <button type="button" data-option-clear="${apiField}">Clear</button>
          </div>
          <div class="multi-select-options" role="listbox" aria-label="${escapeHtml(label)}">
            ${renderLazyOptionSelectedBlock(fieldKey, selectedArray, loadedValuesSet)}
            ${optionState.isLoading && !loadedOptions.length ? '<div class="multi-select-loading">Dang tai du lieu...</div>' : ''}
            ${optionState.error ? `<div class="multi-select-error">${escapeHtml(optionState.error)} <button type="button" data-option-retry="${apiField}">Retry</button></div>` : ''}
            ${!optionState.isLoading && !optionState.error && !loadedOptions.length ? '<div class="multi-select-empty">Khong tim thay du lieu phu hop.</div>' : ''}
            ${fieldConfig.multiple
              ? loadedOptions.map((item) => `<label class="multi-select-option ${selected.has(item.value) ? 'is-selected' : ''}" data-option-field="${apiField}" data-option-value="${escapeHtml(item.value)}"><input type="checkbox" value="${escapeHtml(item.value)}" ${selected.has(item.value) ? 'checked' : ''}> <span class="multi-select-option__label">${escapeHtml(item.label || item.value)}</span></label>`).join('')
              : loadedOptions.map((item) => `<button type="button" class="lazy-option-row ${selected.has(item.value) ? 'is-selected' : ''}" data-option-field="${apiField}" data-option-value="${escapeHtml(item.value)}">${escapeHtml(item.label || item.value)}</button>`).join('')}
          </div>
          <div class="multi-select-footer">
            ${optionState.hasMore ? `<button type="button" class="multi-select-load-more" data-option-load-more="${apiField}" ${optionState.isLoading ? 'disabled' : ''}>${optionState.isLoading && loadedOptions.length ? 'Dang tai...' : 'Load more'}</button>` : '<span class="multi-select-complete">Da tai het du lieu</span>'}
          </div>
        </div>
      </div>
      ${selectedCount ? `<small class="filter-selected-count">${selectedCount} selected</small>` : ''}
    </label>`;
}

function renderHqaFilterOptions() {
  const container = document.getElementById('hqa-filter-options');
  if (!container) return;
  if (state.hqa.mainTab !== 'all_listings') {
    container.innerHTML = '';
    return;
  }

  const filters = state.hqa.allListings.draftFilters;
  const loadingAttribute = state.hqa.allListings.loadingOptions ? 'data-loading="true"' : '';
  const priceRangeInvalid = isAllListingsPriceRangeInvalid(filters);
  const marketplaceOptions = (state.hqa.allListings.lazyOptions.marketplace?.items || []).map((item) => item.value || item);
  const brandOptions = (state.hqa.allListings.lazyOptions.brand?.items || []).map((item) => item.value || item);
  const optionList = (items, selected) => items.map((item) => `<option value="${escapeHtml(item)}" ${item === selected ? 'selected' : ''}>${escapeHtml(item)}</option>`).join('');

  container.innerHTML = `
    <form class="filters hqa-filter-grid" id="hqa-filters" ${loadingAttribute} autocomplete="off">
      <label class="filter-field filter-field--time"><span class="filter-field__label">From date</span><input id="from-date" type="date" value="${escapeHtml(filters.fromDate)}"></label>
      <label class="filter-field filter-field--time"><span class="filter-field__label">To date</span><input id="to-date" type="date" value="${escapeHtml(filters.toDate)}"></label>
      <label class="filter-field filter-field--product"><span class="filter-field__label">Marketplace</span><select id="marketplace" aria-label="Marketplace"><option value="" ${filters.marketplace === '' ? 'selected' : ''}>All marketplaces</option>${optionList(marketplaceOptions || [], filters.marketplace)}</select></label>
      <label class="filter-field filter-field--product"><span class="filter-field__label">Brand</span><select id="brand" aria-label="Brand"><option value="" ${filters.brand === '' ? 'selected' : ''}>All brands</option>${optionList(brandOptions || [], filters.brand)}</select></label>
      ${renderAllListingsLazySelect('model', 'Model', filters.model ? [filters.model] : [], 'filter-field--product')}
      ${renderAllListingsLazySelect('condition', 'Condition', filters.conditions || [], 'filter-field--status')}
      ${renderAllListingsLazySelect('status', 'Status', filters.statuses || [], 'filter-field--status')}
      ${renderAllListingsLazySelect('category_name', 'Category name', filters.categoryNames || [], 'filter-field--product')}
      ${renderAllListingsLazySelect('buying_option', 'Buying option', filters.buyingOptions || [], 'filter-field--status')}
      <label class="filter-field filter-field--price ${priceRangeInvalid ? 'is-error' : ''}"><span class="filter-field__label">Minimum price</span><input id="min-price" type="number" min="0" step="0.01" placeholder="Minimum price" value="${escapeHtml(filters.minPrice)}"></label>
      <label class="filter-field filter-field--price ${priceRangeInvalid ? 'is-error' : ''}"><span class="filter-field__label">Maximum price</span><input id="max-price" type="number" min="0" step="0.01" placeholder="Maximum price" value="${escapeHtml(filters.maxPrice)}"></label>
      <label class="filter-field filter-field--time"><span class="filter-field__label">Collected time</span><select id="sort-collected" aria-label="Sort collected time"><option value="newest" ${filters.sortCollected === 'newest' ? 'selected' : ''}>Newest first</option><option value="oldest" ${filters.sortCollected === 'oldest' ? 'selected' : ''}>Oldest first</option></select></label>
      <label class="filter-field filter-field--search"><span class="filter-field__label">Search</span><input id="search" placeholder="Search listing title, listing ID, seller" value="${escapeHtml(filters.search)}"></label>
      <div class="filter-actions">
        <button type="submit">Apply filters</button>
        <button id="reset-filters" type="button" data-table-interaction="true">Reset filters</button>
        <button id="refresh-inline" type="button" data-table-interaction="true">Refresh data</button>
        <button id="export-all-listings" type="button" data-table-interaction="true" ${state.hqa.allListings.isExporting ? 'disabled' : ''}>${state.hqa.allListings.isExporting ? 'Dang xuat...' : 'Export CSV'}</button>
      </div>
      ${state.hqa.allListings.optionsError ? `<div class="error">${escapeHtml(state.hqa.allListings.optionsError)}</div>` : ''}
    </form>`;
}

function renderHqaListingsContent(payload) {
  const listingsContent = document.getElementById('hqa-listings-content');
  const listingsSection = document.getElementById('hqa-listings-section');
  if (!listingsContent || !listingsSection) return;
  const rawMeta = reportMeta('all_listings');
  listingsContent.innerHTML = `<div class="report-section-header" style="${reportStyleVariables('all_listings')}"><div><h2 class="report-section-title">${escapeHtml(rawMeta.title)}</h2><p class="report-section-subtitle">All stored marketplace research rows matching current filters.</p></div></div>${listingTable(payload, { mode: 'raw' })}`;

  listingsSection.classList.toggle('is-loading', state.hqa.listingsLoading);
  listingsSection.setAttribute('aria-busy', String(state.hqa.listingsLoading));
}

function renderHqaPagination(payload) {
  const paginationContainer = document.getElementById('hqa-pagination');
  if (!paginationContainer) return;
  paginationContainer.innerHTML = renderPaginationFooter(payload);
}

function renderHqaLocalError(message = '') {
  const errorElement = document.getElementById('hqa-local-error');
  if (!errorElement) return;
  if (!message) {
    errorElement.hidden = true;
    errorElement.innerHTML = '';
    return;
  }
  errorElement.hidden = false;
  errorElement.innerHTML = `<div class="local-error-card"><span>${escapeHtml(message)}</span><button type="button" id="retry-listings" class="secondary-button">Retry</button></div>`;
  document.getElementById('retry-listings')?.addEventListener('click', () => {
    loadActiveListings();
  });
}

function clearListingsLocalError() {
  renderHqaLocalError('');
}

function showListingsLocalError(message) {
  renderHqaLocalError(message);
}

function setListingsLoading(isLoading) {
  state.hqa.listingsLoading = isLoading;
  state.hqa.loadingListings = isLoading;

  const section = document.getElementById('hqa-listings-section');
  const overlay = document.getElementById('hqa-listings-loading');

  if (!section || !overlay) return;

  section.classList.toggle('is-loading', isLoading);
  section.setAttribute('aria-busy', String(isLoading));
  overlay.hidden = !isLoading;

  section.querySelectorAll('button, select, input').forEach((element) => {
    if (element.closest('#hqa-pagination') || element.dataset.tableInteraction === 'true') {
      element.disabled = isLoading;
    }
  });
}

async function loadActiveListings({ resetPage = false, scrollToTable = false } = {}) {
  if (resetPage) {
    state.hqa.page = 1;
  }

  listingsAbortController?.abort();
  listingsAbortController = new AbortController();

  const requestId = ++listingsRequestSequence;

  setListingsLoading(true);
  clearListingsLocalError();

  try {
    const url = buildAllListingsParams(state.hqa.page);
    const path = `/hqa/listings?${url.toString()}`;
    const payload = await api(path, {
      method: 'GET',
      signal: listingsAbortController.signal,
      headers: { Accept: 'application/json' },
    });

    if (requestId !== listingsRequestSequence) return;

    state.hqa.rawListings = {
      ...payload,
      items: payload.items || [],
      to_record: (payload.items || []).length
        ? Number(payload.from_record || ((payload.page - 1) * payload.page_size + 1)) + (payload.items || []).length - 1
        : 0,
    };

    state.hqa.page = payload.page || state.hqa.page;
    state.hqa.pageSize = payload.page_size || state.hqa.pageSize;

    renderHqaListingsContent(payload);
    renderHqaPagination(payload);

    if (scrollToTable) {
      document.getElementById('hqa-listings-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch (error) {
    if (error.name === 'AbortError') return;
    showListingsLocalError(error.message || 'Could not load listings.');
  } finally {
    if (requestId === listingsRequestSequence) {
      setListingsLoading(false);
    }
  }
}

function getHcmDateString() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

const app = document.getElementById('app');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[char]);
}

function hasModule(code) {
  return state.user?.system_role === 'superadmin' || state.modules.some((item) => item.code === code);
}

function can(permission) {
  return state.user?.system_role === 'superadmin' || state.modules.some(
    (item) => item.permissions.includes('*') || item.permissions.includes(permission)
  );
}

async function refreshSession() {
  const response = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' });
  if (!response.ok) return false;
  const payload = await response.json();
  applySession(payload);
  return true;
}

async function api(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  if (state.accessToken) headers.set('Authorization', `Bearer ${state.accessToken}`);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: 'include' });
  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return api(path, options, false);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch (_) { /* no-op */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function applySession(payload) {
  state.accessToken = payload.access_token;
  state.user = payload.user;
  state.modules = payload.modules || [];
}

async function bootstrap() {
  try {
    const response = await fetch('/api/v1/auth/session', { credentials: 'include' });
    if (!response.ok) throw new Error('No session');
    applySession(await response.json());
    renderShell();
  } catch (_) {
    renderLogin();
  }
}

function renderLogin(error = '') {
  app.innerHTML = `
    <main class="login-shell">
      <form class="login-card" id="login-form">
        <div class="brand-mark">HQ</div>
        <h1>HQ Platform</h1>
        <p>Sign in to access assigned modules.</p>
        <label>Email<input id="email" value="" type="email" autocomplete="username" required></label>
        <label>Password<input id="password" value="ChangeMe123!" type="password" required></label>
        ${error ? `<div class="error">${escapeHtml(error)}</div>` : ''}
        <button id="login-button">Sign in</button>
      </form>
    </main>`;
  document.getElementById('login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = document.getElementById('login-button');
    button.disabled = true; button.textContent = 'Signing in...';
    try {
      const payload = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: document.getElementById('email').value,
          password: document.getElementById('password').value,
        }),
      });
      applySession(payload); renderShell();
    } catch (reason) { renderLogin(reason.message); }
  });
}

function sidebarButton(code, label) {
  if (code !== 'SYSTEM' && !hasModule(code)) return '';
  if (code === 'SYSTEM' && state.user.system_role !== 'superadmin') return '';
  return `<button data-module="${code}" class="${state.currentModule === code ? 'active' : ''}">${label}</button>`;
}

function renderShell() {
  if (!hasModule(state.currentModule) && state.currentModule !== 'SYSTEM') {
    state.currentModule = state.modules[0]?.code || (state.user.system_role === 'superadmin' ? 'HQA' : 'NONE');
  }
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="logo">HQ</div>
        <nav>
          ${sidebarButton('HQA', 'HQA')}
          ${sidebarButton('HQS', 'HQS')}
          ${sidebarButton('SYSTEM', 'System')}
        </nav>
        <div class="sidebar-user">
          <strong>${escapeHtml(state.user.full_name)}</strong>
          <span>${escapeHtml(state.user.system_role || state.modules.map((m) => `${m.code}:${m.role}`).join(', '))}</span>
          <button id="logout">Sign out</button>
        </div>
      </aside>
      <main class="content" id="content"></main>
    </div>`;
  document.querySelectorAll('[data-module]').forEach((button) => button.addEventListener('click', () => {
    state.currentModule = button.dataset.module; renderShell();
  }));
  document.getElementById('logout').addEventListener('click', logout);
  renderCurrentModule();
}

async function logout() {
  await api('/auth/logout', { method: 'POST' }).catch(() => null);
  state.accessToken = null; state.user = null; state.modules = [];
  renderLogin();
}

function renderCurrentModule() {
  const content = document.getElementById('content');
  if (state.currentModule === 'HQA') return renderHqa(content);
  if (state.currentModule === 'HQS') return renderHqs(content);
  return renderSystem(content);
}

function formatMetricValue(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toLocaleString();
  }
  return escapeHtml(value);
}

function metric(label, value, detail = '') {
  return `<article class="metric-card"><span>${escapeHtml(label)}</span><strong>${formatMetricValue(value)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ''}</article>`;
}

function formatPrice(price, currency) {
  if (price == null) return '-';
  return `${Number(price).toLocaleString()} ${escapeHtml(currency || '')}`.trim();
}

function formatDateTimeHcm(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const map = Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
  if (!map.day || !map.month || !map.year || !map.hour || !map.minute) return '-';
  return `${map.day}/${map.month}/${map.year} ${map.hour}:${map.minute}`;
}

function statusClass(status) {
  const normalized = normalizeListingStatus(status).key;
  if (normalized === 'active') return 'status-active';
  if (normalized === 'new_listing') return 'status-new';
  if (normalized === 'ended') return 'status-ended';
  if (normalized === 'out_of_stock') return 'status-out';
  return 'status-unknown';
}

function normalizeListingStatus(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'active') return { key: 'active', label: 'ACTIVE' };
  if (normalized === 'ended') return { key: 'ended', label: 'ENDED' };
  if (normalized === 'new_listing') return { key: 'new_listing', label: 'NEW_LISTING' };
  if (normalized === 'out_of_stock') return { key: 'out_of_stock', label: 'OUT_OF_STOCK' };
  return { key: 'unknown', label: 'UNKNOWN' };
}

function listingRow(item, mode = 'report') {
  const normalizedStatus = normalizeListingStatus(item.listing_status);
  const image = item.image_url
    ? `<img src="${escapeHtml(item.image_url)}" alt="listing thumbnail" class="thumb" onerror="this.style.display='none'; this.nextElementSibling.style.display='grid';">`
    : '';
  const placeholderVisible = item.image_url ? 'style="display:none"' : '';
  const listingLink = item.listing_url
    ? `<a href="${escapeHtml(item.listing_url)}" target="_blank" rel="noopener noreferrer" class="listing-link">${escapeHtml(item.listing_title)}</a>`
    : `<span class="listing-link">${escapeHtml(item.listing_title)}</span>`;
  const categoryCell = mode === 'raw'
    ? `<td>${escapeHtml(item.category_name || '-')}</td>`
    : `<td><div><strong>${escapeHtml(item.category || '-')}</strong><small>${escapeHtml(item.category_name || '-')}</small></div></td>`;

  if (mode === 'raw') {
    return `<tr>
      <td>
        <div class="thumb-wrap">
          ${image}
          <div class="thumb placeholder" ${placeholderVisible}>No image</div>
        </div>
      </td>
      <td><span class="chip">${escapeHtml(item.marketplace || '-')}</span></td>
      <td><div class="listing-cell">${listingLink}<small>${escapeHtml(item.listing_id || '-')}</small></div></td>
      ${categoryCell}
      <td>${escapeHtml(item.seller_or_shop || '-')}</td>
      <td>${formatPrice(item.price, item.currency)}</td>
      <td>${escapeHtml(item.quantity ?? '-')}</td>
      <td><span class="status-pill ${statusClass(normalizedStatus.key)}">${escapeHtml(normalizedStatus.label)}</span></td>
      <td class="all-listings-datetime">${escapeHtml(formatDateTimeHcm(item.listing_published_at))}</td>
      <td class="all-listings-datetime">${escapeHtml(formatDateTimeHcm(item.last_status_checked_at))}</td>
    </tr>`;
  }

  const actionCell = item.listing_url
    ? `<td><a href="${escapeHtml(item.listing_url)}" target="_blank" rel="noopener noreferrer" class="link-action">Open</a></td>`
    : '<td><span class="link-action disabled">N/A</span></td>';

  return `<tr>
    <td>
      <div class="thumb-wrap">
        ${image}
        <div class="thumb placeholder" ${placeholderVisible}>No image</div>
      </div>
    </td>
    <td><span class="chip">${escapeHtml(item.marketplace || '-')}</span></td>
    <td><div class="listing-cell">${listingLink}<small>${escapeHtml(item.listing_id || '-')}</small></div></td>
    ${categoryCell}
    <td>${escapeHtml(item.seller_or_shop || '-')}</td>
    <td>${escapeHtml(item.condition || '-')}</td>
    <td>${formatPrice(item.price, item.currency)}</td>
    <td><span class="status-pill ${statusClass(normalizedStatus.key)}">${escapeHtml(normalizedStatus.label)}</span></td>
    <td>${escapeHtml(item.research_date || '-')}</td>
    ${actionCell}
  </tr>`;
}

function renderPaginationFooter(payload) {
  const pagination = buildPaginationState(payload);
  const pageItems = buildPageButtons(pagination.totalPages, pagination.page);
  const hasPagination = pagination.totalPages > 1;
  const pageSizeOptions = PAGE_SIZE_OPTIONS.map((size) => `<option value="${size}" ${pagination.pageSize === size ? 'selected' : ''}>${size}</option>`).join('');
  return `
    <div class="listing-footer">
      <div class="listing-footer-summary">
        <div class="listing-range">Showing ${pagination.fromRecord ? formatRecordCount(pagination.fromRecord) : 0}–${formatRecordCount(pagination.toRecord)} of ${formatRecordCount(pagination.total)} records</div>
        <div class="listing-page-count">Page ${pagination.page} of ${pagination.totalPages || 1}</div>
      </div>
      <div class="listing-footer-controls">
        <label class="page-size-control" for="page-size">
          <span>Rows per page</span>
          <select id="page-size" aria-label="Rows per page">${pageSizeOptions}</select>
        </label>
        <nav class="pagination report-pagination" aria-label="Pagination">
          <button type="button" id="page-first" aria-label="First page" ${pagination.hasPrevious ? '' : 'disabled'}>First</button>
          <button type="button" id="page-prev" aria-label="Previous page" ${pagination.hasPrevious ? '' : 'disabled'}>Previous</button>
          ${pageItems.map((item) => item === '...'
            ? '<span class="page-ellipsis" aria-hidden="true">...</span>'
            : `<button type="button" class="page-btn ${item === pagination.page ? 'active' : ''}" aria-label="Page ${item}" aria-current="${item === pagination.page ? 'page' : 'false'}" data-page="${item}">${item}</button>`).join('')}
          <button type="button" id="page-next" aria-label="Next page" ${pagination.hasNext ? '' : 'disabled'}>Next</button>
          <button type="button" id="page-last" aria-label="Last page" ${pagination.hasNext ? '' : 'disabled'}>Last</button>
        </nav>
      </div>
    </div>`;
}

function listingTable(payload, options = {}) {
  const { mode = 'report' } = options;
  const tableClass = mode === 'raw' ? 'all-listings-table' : 'report-listings-table';
  const includeFooter = mode !== 'raw';
  if (!payload) return '<div class="center-inline">Loading report...</div>';
  if (payload.error) {
    return `<div class="error">${escapeHtml(payload.error)} <button id="retry-report" type="button">Retry</button></div>`;
  }
  if (!payload.items.length) {
    return mode === 'raw'
      ? '<div class="empty-state">No stored marketplace research rows match the current criteria.</div>'
      : '<div class="empty-state">Không có listing phù hợp với điều kiện của báo cáo.</div>';
  }
  return `
    <div class="table-wrap">
      <table class="${tableClass}">
        <thead>
          <tr>
            ${mode === 'raw'
              ? '<th>Image</th><th>Marketplace</th><th>Listing</th><th>Category name</th><th>Seller / Shop</th><th>Price</th><th>Quantity</th><th>Status</th><th>Listing published at</th><th>Last status checked at</th>'
              : '<th>Image</th><th>Marketplace</th><th>Listing</th><th>Category</th><th>Seller / Shop</th><th>Price</th><th>Status</th><th>Research date</th><th>Action</th>'}
          </tr>
        </thead>
        <tbody>${payload.items.map((item) => listingRow(item, mode)).join('')}</tbody>
      </table>
    </div>
    ${includeFooter ? renderPaginationFooter(payload) : ''}`;
}

async function renderHqa(content, options = {}) {
  const { reloadData = true } = options;
  ensureHqaShell(content);

  if (!HQA_MAIN_TABS.some((tab) => tab.key === state.hqa.mainTab)) {
    state.hqa.mainTab = 'all_listings';
  }
  if (state.hqa.mainTab === 'all_listings') {
    state.hqa.activeReport = 'all_listings';
  }

  renderHqaMainTabs();
  renderHqaMainTabVisibility();
  renderHqaLocalError('');
  renderAllListingsToast();

  if (state.hqa.mainTab === 'dashboard') {
    if (reloadData || !state.hqa.dashboard.sellersSummary) {
      await loadHqaDashboardFilterOptions();
      await loadHqaDashboardData();
    }
    renderHqaDashboard();
  } else if (state.hqa.mainTab === 'data_check') {
    renderDataCheckView();
  } else {
    renderHqaFilterOptions();
    renderHqaSummary();

    const existingPayload = state.hqa.rawListings;

    if (reloadData) {
      await loadAllListingsFilterOptions();
      renderHqaFilterOptions();
      await loadAllListingsSummary();
      renderHqaSummary();
      await loadActiveListings();
    } else if (existingPayload) {
      renderHqaListingsContent(existingPayload);
      renderHqaPagination(existingPayload);
    }
  }

  document.querySelectorAll('[data-hqa-main-tab]').forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = 'true';
    button.addEventListener('click', async () => {
      setHqaMainTab(button.dataset.hqaMainTab);
      await renderHqa(content, { reloadData: true });
    });
  });

  const refreshDataButton = document.getElementById('refresh-data');
  if (refreshDataButton && !refreshDataButton.dataset.bound) {
    refreshDataButton.dataset.bound = 'true';
    refreshDataButton.addEventListener('click', async () => {
      if (state.hqa.mainTab === 'dashboard') {
        await loadHqaDashboardData();
        renderHqaDashboard();
        return;
      }

      if (state.hqa.mainTab === 'data_check') {
        if (!state.hqa.dataCheck.hasRun) {
          renderDataCheckView();
          return;
        }
        await loadDataCheckSummaryAndGroups(state.hqa.dataCheck.page || 1);
        renderDataCheckView();
        return;
      }

      state.hqa.allListings.draftFilters = cloneAllListingsFilters(state.hqa.allListings.appliedFilters);
      clearAllLazyOptionCache();
      await loadAllListingsFilterOptions();
      renderHqaFilterOptions();
      await loadAllListingsSummary();
      renderHqaSummary();
      await loadActiveListings({ scrollToTable: false });
    });
  }

  bindAllListingsFilterEvents();

  const paginationPayload = state.hqa.rawListings;
  if (paginationPayload) {
    const first = document.getElementById('page-first');
    if (first && !first.dataset.bound) {
      first.dataset.bound = 'true';
      first.addEventListener('click', async () => {
        state.hqa.page = 1;
        await loadActiveListings({ scrollToTable: true });
      });
    }
    const prev = document.getElementById('page-prev');
    if (prev && !prev.dataset.bound) {
      prev.dataset.bound = 'true';
      prev.addEventListener('click', async () => {
        state.hqa.page = Math.max(1, state.hqa.page - 1);
        await loadActiveListings({ scrollToTable: true });
      });
    }
    const next = document.getElementById('page-next');
    if (next && !next.dataset.bound) {
      next.dataset.bound = 'true';
      next.addEventListener('click', async () => {
        state.hqa.page = Math.min(paginationPayload.total_pages || 1, state.hqa.page + 1);
        await loadActiveListings({ scrollToTable: true });
      });
    }
    const last = document.getElementById('page-last');
    if (last && !last.dataset.bound) {
      last.dataset.bound = 'true';
      last.addEventListener('click', async () => {
        state.hqa.page = paginationPayload.total_pages || 1;
        await loadActiveListings({ scrollToTable: true });
      });
    }
    document.querySelectorAll('.page-btn').forEach((button) => {
      if (button.dataset.bound) return;
      button.dataset.bound = 'true';
      button.addEventListener('click', async () => {
        state.hqa.page = Number(button.dataset.page);
        await loadActiveListings({ scrollToTable: true });
      });
    });
    const pageSize = document.getElementById('page-size');
    if (pageSize && !pageSize.dataset.bound) {
      pageSize.dataset.bound = 'true';
      pageSize.addEventListener('change', async (event) => {
        state.hqa.pageSize = Number(event.target.value || 50);
        state.hqa.page = 1;
        await loadActiveListings();
      });
    }
  }

  const retryReport = document.getElementById('retry-report');
  if (retryReport && !retryReport.dataset.bound) {
    retryReport.dataset.bound = 'true';
    retryReport.addEventListener('click', async () => {
      await loadActiveListings();
    });
  }

  const dashboardForm = document.getElementById('dashboard-filters');
  if (dashboardForm && !dashboardForm.dataset.bound) {
    dashboardForm.dataset.bound = 'true';

    const selectedValues = (id) => Array.from(document.getElementById(id)?.selectedOptions || []).map((option) => option.value);

    const snapshotDashboardSellerFilters = () => ({
      keyword: document.getElementById('dashboard-seller-keyword')?.value.trim() || '',
      currency: document.getElementById('dashboard-seller-currency')?.value.trim() || '',
      dateFrom: document.getElementById('dashboard-seller-date-from')?.value || '',
      dateTo: document.getElementById('dashboard-seller-date-to')?.value || '',
      marketplaces: selectedValues('dashboard-seller-marketplace'),
      brands: selectedValues('dashboard-seller-brand'),
      models: selectedValues('dashboard-seller-model'),
      statuses: selectedValues('dashboard-seller-status'),
      categoryNames: selectedValues('dashboard-seller-category'),
      buyingOptions: selectedValues('dashboard-seller-buying'),
      sellers: selectedValues('dashboard-seller-seller'),
    });

    const snapshotDashboardPriceFilters = () => ({
      ...snapshotDashboardSellerFilters(),
      keyword: document.getElementById('dashboard-price-keyword')?.value.trim() || '',
      currency: document.getElementById('dashboard-price-currency')?.value.trim() || '',
      dateFrom: document.getElementById('dashboard-price-date-from')?.value || '',
      dateTo: document.getElementById('dashboard-price-date-to')?.value || '',
      granularity: document.getElementById('dashboard-price-granularity')?.value || 'month',
      minPrice: document.getElementById('dashboard-price-min')?.value.trim() || '',
      maxPrice: document.getElementById('dashboard-price-max')?.value.trim() || '',
    });

    dashboardForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const sellerFilters = snapshotDashboardSellerFilters();
      const priceFilters = snapshotDashboardPriceFilters();
      if (sellerFilters.dateFrom && sellerFilters.dateTo && sellerFilters.dateFrom > sellerFilters.dateTo) {
        state.hqa.dashboard.error = 'Seller filter date range is invalid.';
        renderHqaDashboard();
        return;
      }
      if (priceFilters.dateFrom && priceFilters.dateTo && priceFilters.dateFrom > priceFilters.dateTo) {
        state.hqa.dashboard.error = 'Price filter date range is invalid.';
        renderHqaDashboard();
        return;
      }
      const parsedMinPrice = parseNonNegativeNumber(priceFilters.minPrice);
      if (!parsedMinPrice.ok) {
        state.hqa.dashboard.error = parsedMinPrice.message;
        renderHqaDashboard();
        return;
      }
      const parsedMaxPrice = parseNonNegativeNumber(priceFilters.maxPrice);
      if (!parsedMaxPrice.ok) {
        state.hqa.dashboard.error = parsedMaxPrice.message;
        renderHqaDashboard();
        return;
      }
      priceFilters.minPrice = parsedMinPrice.value;
      priceFilters.maxPrice = parsedMaxPrice.value;
      if (priceFilters.minPrice !== '' && priceFilters.maxPrice !== '' && Number(priceFilters.minPrice) > Number(priceFilters.maxPrice)) {
        state.hqa.dashboard.error = 'Min price must be less than or equal to max price.';
        renderHqaDashboard();
        return;
      }

      state.hqa.dashboard.error = '';
      state.hqa.dashboard.draftSellerFilters = sellerFilters;
      state.hqa.dashboard.appliedSellerFilters = sellerFilters;
      state.hqa.dashboard.draftPriceFilters = priceFilters;
      state.hqa.dashboard.appliedPriceFilters = priceFilters;
      await loadHqaDashboardFilterOptions();
      await loadHqaDashboardData();
      renderHqaDashboard();
      await renderHqa(content, { reloadData: false });
    });

    dashboardForm.addEventListener('click', async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.id !== 'dashboard-reset') return;
      const emptySeller = {
        keyword: '', marketplaces: [], brands: [], models: [], statuses: [], categoryNames: [], buyingOptions: [], sellers: [], currency: '', dateFrom: '', dateTo: '',
      };
      const emptyPrice = {
        ...emptySeller,
        granularity: 'month',
        minPrice: '',
        maxPrice: '',
      };
      state.hqa.dashboard.error = '';
      state.hqa.dashboard.draftSellerFilters = emptySeller;
      state.hqa.dashboard.appliedSellerFilters = emptySeller;
      state.hqa.dashboard.draftPriceFilters = emptyPrice;
      state.hqa.dashboard.appliedPriceFilters = emptyPrice;
      await loadHqaDashboardFilterOptions();
      await loadHqaDashboardData();
      renderHqaDashboard();
      await renderHqa(content, { reloadData: false });
    });
  }

  const dashboardExportButton = document.getElementById('dashboard-export');
  if (dashboardExportButton && !dashboardExportButton.dataset.bound) {
    dashboardExportButton.dataset.bound = 'true';
    dashboardExportButton.addEventListener('click', async () => {
      state.hqa.dashboard.isExporting = true;
      renderHqaDashboard();
      try {
        const dataset = document.getElementById('dashboard-export-dataset')?.value || 'sellers_summary';
        const params = dataset.startsWith('prices') || dataset === 'alerts'
          ? buildDashboardPriceParams()
          : buildDashboardSellerParams();
        params.set('dataset', dataset);
        if (state.hqa.dashboard.appliedPriceFilters.granularity) {
          params.set('granularity', state.hqa.dashboard.appliedPriceFilters.granularity);
        }
        await downloadCsv(`/hqa/dashboard/export?${params.toString()}`, `hqa_dashboard_${dataset}.csv`);
      } catch (error) {
        state.hqa.dashboard.error = error.message || 'Dashboard export failed.';
      } finally {
        state.hqa.dashboard.isExporting = false;
        renderHqaDashboard();
      }
    });
  }

  const dashboardDrilldownButton = document.getElementById('dashboard-drilldown');
  if (dashboardDrilldownButton && !dashboardDrilldownButton.dataset.bound) {
    dashboardDrilldownButton.dataset.bound = 'true';
    dashboardDrilldownButton.addEventListener('click', async () => {
      const filters = state.hqa.dashboard.appliedPriceFilters;
      const mapped = {
        fromDate: filters.dateFrom || '',
        toDate: filters.dateTo || '',
        marketplace: filters.marketplaces?.[0] || '',
        brand: filters.brands?.[0] || '',
        model: filters.models?.[0] || '',
        conditions: [],
        statuses: filters.statuses || [],
        categoryNames: filters.categoryNames || [],
        buyingOptions: filters.buyingOptions || [],
        sortCollected: 'newest',
        minPrice: filters.minPrice || '',
        maxPrice: filters.maxPrice || '',
        search: filters.keyword || '',
      };
      state.hqa.allListings.openLazyField = '';
      state.hqa.allListings.draftFilters = cloneAllListingsFilters(mapped);
      state.hqa.allListings.appliedFilters = cloneAllListingsFilters(mapped);
      setHqaMainTab('all_listings');
      state.hqa.page = 1;
      await renderHqa(content, { reloadData: true });
    });
  }

  const dataCheckFilters = document.getElementById('data-check-filters');
  if (dataCheckFilters && !dataCheckFilters.dataset.bound) {
    dataCheckFilters.dataset.bound = 'true';
    dataCheckFilters.addEventListener('submit', async (event) => {
      event.preventDefault();
      state.hqa.dataCheck.filters = {
        marketplace: document.getElementById('data-check-marketplace')?.value.trim() || '',
        listingId: document.getElementById('data-check-listing-id')?.value.trim() || '',
        status: document.getElementById('data-check-status')?.value.trim() || '',
      };
      state.hqa.dataCheck.page = 1;
      await loadDataCheckSummaryAndGroups(1);
      renderDataCheckView();
      await renderHqa(content, { reloadData: false });
    });
  }

  const dataCheckRunButton = document.getElementById('data-check-run');
  if (dataCheckRunButton && !dataCheckRunButton.dataset.bound) {
    dataCheckRunButton.dataset.bound = 'true';
    dataCheckRunButton.addEventListener('click', async () => {
      state.hqa.dataCheck.cleanupResult = null;
      state.hqa.dataCheck.expandedKeys = {};
      state.hqa.dataCheck.page = 1;
      await loadDataCheckSummaryAndGroups(1);
      renderDataCheckView();
      await renderHqa(content, { reloadData: false });
    });
  }

  const dataCheckRefreshButton = document.getElementById('data-check-refresh');
  if (dataCheckRefreshButton && !dataCheckRefreshButton.dataset.bound) {
    dataCheckRefreshButton.dataset.bound = 'true';
    dataCheckRefreshButton.addEventListener('click', async () => {
      if (!state.hqa.dataCheck.hasRun) return;
      await loadDataCheckSummaryAndGroups(state.hqa.dataCheck.page || 1);
      renderDataCheckView();
      await renderHqa(content, { reloadData: false });
    });
  }

  const dataCheckCleanupButton = document.getElementById('data-check-cleanup');
  if (dataCheckCleanupButton && !dataCheckCleanupButton.dataset.bound) {
    dataCheckCleanupButton.dataset.bound = 'true';
    dataCheckCleanupButton.addEventListener('click', () => {
      state.hqa.dataCheck.showConfirmModal = true;
      state.hqa.dataCheck.confirmationInput = '';
      renderDataCheckView();
    });
  }

  const dataCheckContainer = document.getElementById('hqa-data-check-view');
  if (dataCheckContainer && !dataCheckContainer.dataset.bound) {
    dataCheckContainer.dataset.bound = 'true';
    dataCheckContainer.addEventListener('click', async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      const toggleButton = target.closest('[data-data-check-toggle]');
      if (toggleButton) {
        const key = toggleButton.getAttribute('data-data-check-toggle') || '';
        if (!key) return;
        state.hqa.dataCheck.expandedKeys = {
          ...state.hqa.dataCheck.expandedKeys,
          [key]: !state.hqa.dataCheck.expandedKeys[key],
        };
        renderDataCheckView();
        await renderHqa(content, { reloadData: false });
        return;
      }

      const pageButton = target.closest('[data-data-check-page]');
      if (pageButton) {
        const action = pageButton.getAttribute('data-data-check-page') || '';
        const currentPage = Number(state.hqa.dataCheck.groups?.page || state.hqa.dataCheck.page || 1);
        const nextPage = action === 'prev' ? Math.max(1, currentPage - 1) : currentPage + 1;
        await loadDataCheckSummaryAndGroups(nextPage);
        renderDataCheckView();
        await renderHqa(content, { reloadData: false });
        return;
      }
    });
  }
}


async function renderHqs(content) {
  content.innerHTML = '<div class="center-inline">Loading HQS data...</div>';
  try {
    const [dashboard, requests] = await Promise.all([api('/hqs/dashboard'), api('/hqs/requests')]);
    content.innerHTML = `
      <section>
        <div class="page-heading"><div><span class="eyebrow">Module</span><h1>HQS Requests</h1></div></div>
        <div class="metrics">
          ${metric('Open', dashboard.open)}
          ${metric('In progress', dashboard.in_progress)}
          ${metric('Closed', dashboard.closed)}
        </div>
        <div class="panel">
          ${can('hqs.requests.create') ? `
            <form class="filters" id="hqs-form">
              <input id="hqs-title" placeholder="Request title" required>
              <select id="hqs-priority"><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select>
              <button>Create request</button>
            </form>` : ''}
          <div class="table-wrap"><table><thead><tr><th>Title</th><th>Priority</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>${requests.items.map((item) => `<tr><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.priority)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.created_at)}</td></tr>`).join('')}</tbody></table></div>
        </div>
      </section>`;
    document.getElementById('hqs-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      await api('/hqs/requests', { method: 'POST', body: JSON.stringify({
        title: document.getElementById('hqs-title').value,
        priority: document.getElementById('hqs-priority').value,
      }) });
      renderHqs(content);
    });
  } catch (reason) {
    content.innerHTML = `<div class="error">${escapeHtml(reason.message)}</div>`;
  }
}


async function renderSystem(content) {
  content.innerHTML = '<div class="center-inline">Loading users...</div>';
  try {
    const result = await api('/system/users');
    content.innerHTML = `
      <section>
        <div class="page-heading"><div><span class="eyebrow">Superadmin</span><h1>User and module access</h1></div></div>
        <div class="panel">
          <form class="filters" id="user-form">
            <input id="new-user-name" placeholder="Full name" required>
            <input id="new-user-email" type="email" placeholder="Email" required>
            <input id="new-user-password" type="password" placeholder="Temporary password" minlength="8" required>
            <button>Create user</button>
          </form>
          <div class="table-wrap"><table><thead><tr><th>User</th><th>System role</th><th>Memberships</th><th>Status</th><th>Assign</th></tr></thead>
          <tbody>${result.items.map((user) => `<tr>
            <td><strong>${escapeHtml(user.full_name)}</strong><small>${escapeHtml(user.email)}</small></td>
            <td>${escapeHtml(user.system_role || '-')}</td>
            <td>${escapeHtml(user.memberships.map((m) => `${m.module_code}:${m.role}`).join(', ') || '-')}</td>
            <td>${user.is_active ? 'Active' : 'Disabled'}</td>
            <td>${user.system_role === 'superadmin' ? '-' : `
              <div class="inline-actions">
                <select data-module-for="${user.id}"><option value="HQA">HQA</option><option value="HQS">HQS</option></select>
                <select data-role-for="${user.id}"><option value="user">User</option><option value="admin">Admin</option></select>
                <button data-assign-user="${user.id}">Assign</button>
              </div>`}</td>
          </tr>`).join('')}</tbody></table></div>
        </div>
      </section>`;
    document.getElementById('user-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      await api('/system/users', { method: 'POST', body: JSON.stringify({
        full_name: document.getElementById('new-user-name').value,
        email: document.getElementById('new-user-email').value,
        password: document.getElementById('new-user-password').value,
      }) });
      renderSystem(content);
    });
    document.querySelectorAll('[data-assign-user]').forEach((button) => button.addEventListener('click', async () => {
      const userId = button.dataset.assignUser;
      await api(`/system/users/${userId}/membership`, { method: 'PUT', body: JSON.stringify({
        module_code: document.querySelector(`[data-module-for="${userId}"]`).value,
        role: document.querySelector(`[data-role-for="${userId}"]`).value,
      }) });
      renderSystem(content);
    }));
  } catch (reason) {
    content.innerHTML = `<div class="error">${escapeHtml(reason.message)}</div>`;
  }
}

bootstrap();
