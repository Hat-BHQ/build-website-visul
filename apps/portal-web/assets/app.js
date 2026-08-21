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
        priceSort: 'default',
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
        priceSort: 'default',
        minPrice: '',
        maxPrice: '',
        search: '',
      },
      summary: null,
    },
    dashboard: {
      loading: false,
      isExporting: false,
      error: '',
      appliedFilters: {
        keyword: '',
        marketplaces: [],
        brands: [],
        models: [],
        conditions: [],
        statuses: [],
        categoryNames: [],
        buyingOptions: [],
        dateFrom: '',
        dateTo: '',
        minPrice: '',
        maxPrice: '',
        currency: '',
      },
      analysis: null,
      granularity: 'month',
      selectedProduct: '',
      selectedPeriod: '',
      roleFilter: 'all',
      // Searchable multi-select product picker that drives BOTH comparison charts.
      chartProducts: [],
      chartProductSearch: '',
      chartProductVisible: 30,
      chartProductSelectorOpen: false,
      chartWarn: '',
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
  { key: 'data_check', label: 'Kiểm tra dữ liệu' },
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
let dashboardGlobalListenersBound = false;

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
        <button class="hvr-float-shadow" id="refresh-data" type="button" data-table-interaction="true">Refresh data</button>
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
    <div class="hqa-main-tabs cl-effect-5 " role="tablist" aria-label="eBay Marketplace Reports views">
      ${HQA_MAIN_TABS.map((tab) => `<button type="button" class="hqa-main-tab ${state.hqa.mainTab === tab.key ? 'active' : ''}" data-hqa-main-tab="${tab.key}" role="tab" aria-selected="${state.hqa.mainTab === tab.key ? 'true' : 'false'}"><span data-hover="${escapeHtml(tab.label)}">${escapeHtml(tab.label)}</span></button>`).join('')}
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

function appendDashboardArrayParams(params, key, values) {
  const normalizedValues = Array.isArray(values) ? values : (values ? [values] : []);
  normalizedValues.forEach((value) => {
    const normalized = String(value || '').trim();
    if (normalized) params.append(key, normalized);
  });
}

function syncDashboardFiltersFromAllListings() {
  const source = state.hqa.allListings.appliedFilters || {};
  state.hqa.dashboard.appliedFilters = {
    keyword: source.search || '',
    marketplaces: source.marketplace ? [source.marketplace] : [],
    brands: source.brand ? [source.brand] : [],
    models: source.model ? [source.model] : [],
    conditions: Array.isArray(source.conditions) ? [...source.conditions] : [],
    statuses: Array.isArray(source.statuses) ? [...source.statuses] : [],
    categoryNames: Array.isArray(source.categoryNames) ? [...source.categoryNames] : [],
    buyingOptions: Array.isArray(source.buyingOptions) ? [...source.buyingOptions] : [],
    dateFrom: source.fromDate || '',
    dateTo: source.toDate || '',
    minPrice: source.minPrice ?? '',
    maxPrice: source.maxPrice ?? '',
    currency: '',
  };
}

function buildDashboardCommonParams(filters = state.hqa.dashboard.appliedFilters) {
  const params = new URLSearchParams();
  if (filters.keyword) params.set('keyword', String(filters.keyword).trim());
  appendDashboardArrayParams(params, 'marketplace', filters.marketplaces);
  appendDashboardArrayParams(params, 'brand', filters.brands);
  appendDashboardArrayParams(params, 'model', filters.models);
  appendDashboardArrayParams(params, 'condition', filters.conditions);
  appendDashboardArrayParams(params, 'status', filters.statuses);
  appendDashboardArrayParams(params, 'category_name', filters.categoryNames);
  appendDashboardArrayParams(params, 'buying_option', filters.buyingOptions);
  if (filters.currency) params.set('currency', String(filters.currency).trim());
  if (filters.dateFrom) params.set('date_from', filters.dateFrom);
  if (filters.dateTo) params.set('date_to', filters.dateTo);
  if (filters.minPrice !== '' && filters.minPrice !== null && filters.minPrice !== undefined) params.set('min_price', String(filters.minPrice).trim());
  if (filters.maxPrice !== '' && filters.maxPrice !== null && filters.maxPrice !== undefined) params.set('max_price', String(filters.maxPrice).trim());
  return params;
}

const DASHBOARD_FIELD_MAP = {
  recordId: 'id',
  listingId: 'listing_id',
  marketplace: 'marketplace',
  brand: 'brand',
  model: 'model',
  category: 'category_name',
  condition: 'condition',
  status: 'listing_status',
  price: 'price',
  seller: 'seller_or_shop',
  title: 'listing_title',
  quantity: 'quantity',
  collectedAt: 'collected_at',
  researchDate: 'research_date',
  publishedAt: 'listing_published_at',
  lastCheckedAt: 'last_status_checked_at',
  url: 'listing_url',
  currency: 'currency',
};

const DASHBOARD_CONFIG = {
  groupBy: 'model',
  granularity: 'month',
  defaultCurrency: 'USD',
  supportedCurrencies: ['USD', 'VND'],
  priceDropWarningPct: 20,
  priceDropCriticalPct: 30,
  outOfStockWarningPoints: 30,
  outOfStockCriticalPoints: 50,
  productSeriesMax: 10,
  productPageSize: 30,
  productSeriesDefault: 4,
   colors: ['#2fa2e4', '#7C5CFC', '#16A34A', '#f5be0b', '#475569', '#ef6644', '#0891B2', '#C026D3', '#0F766E', '#c20c0c'],
   dashPatterns: [[], [7, 4], [2, 3], [9, 3, 2, 3], [12, 4], [4, 3], [10, 2], [2, 2, 8, 2], [6, 2, 2, 2], [14, 4]],
  pointStyles: ['circle', 'rect', 'triangle', 'rectRot', 'star', 'crossRot', 'cross', 'rectRounded', 'dash', 'line'],
};

let hqaDashboardCharts = [];

async function loadHqaDashboardData() {
  state.hqa.dashboard.loading = true;
  state.hqa.dashboard.error = '';
  try {
    const params = buildDashboardCommonParams();
    params.set('granularity', state.hqa.dashboard.granularity || DASHBOARD_CONFIG.granularity);
    params.set('price_drop_warning_pct', String(DASHBOARD_CONFIG.priceDropWarningPct));
    params.set('price_drop_critical_pct', String(DASHBOARD_CONFIG.priceDropCriticalPct));
    params.set('out_of_stock_warning_points', String(DASHBOARD_CONFIG.outOfStockWarningPoints));
    params.set('out_of_stock_critical_points', String(DASHBOARD_CONFIG.outOfStockCriticalPoints));
    const payload = await api(`/hqa/dashboard/analysis?${params.toString()}`);
    state.hqa.dashboard.analysis = payload;
    reconcileDashboardSelection(payload);
  } catch (error) {
    state.hqa.dashboard.error = error.message || 'Could not load dashboard analytics.';
    state.hqa.dashboard.analysis = null;
  } finally {
    state.hqa.dashboard.loading = false;
  }
}

// Keep the drill-down + chart selection valid across (re)loads. Drops products that no
// longer exist and falls back to the top-N whole-product products when empty.
function reconcileDashboardSelection(payload) {
  const dashboard = state.hqa.dashboard;
  const products = payload?.groups || [];
  const periods = payload?.periods || [];
  const productSet = new Set(products);

  if (!productSet.has(dashboard.selectedProduct)) {
    dashboard.selectedProduct = products[0] || '';
  }
  if (!periods.includes(dashboard.selectedPeriod)) {
    dashboard.selectedPeriod = payload?.latest_period?.period || periods[periods.length - 1] || '';
  }

  dashboard.chartProducts = (dashboard.chartProducts || []).filter((key) => productSet.has(key));
  if (!dashboard.chartProducts.length) {
    dashboard.chartProducts = products.slice(0, DASHBOARD_CONFIG.productSeriesDefault);
  }
  dashboard.chartProducts = dashboard.chartProducts.slice(0, DASHBOARD_CONFIG.productSeriesMax);
}

function formatDashboardCurrency(value, currency = DASHBOARD_CONFIG.defaultCurrency) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return '—';
  const cleanedCurrency = String(currency || 'USD').trim().toUpperCase();
  if (cleanedCurrency === 'MIXED' || cleanedCurrency === 'UNKNOWN') {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(numericValue);
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: cleanedCurrency === 'VND' ? 'VND' : 'USD',
      maximumFractionDigits: cleanedCurrency === 'VND' ? 0 : 2,
    }).format(numericValue);
  } catch (error) {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(numericValue);
  }
}

function formatDashboardNumber(value, fractionDigits = 0) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return '—';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(numericValue);
}

function dashboardPercentChange(currentValue, previousValue) {
  const current = Number(currentValue);
  const previous = Number(previousValue);
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

function dashboardSeriesStyle(index) {
  return {
    color: DASHBOARD_CONFIG.colors[index % DASHBOARD_CONFIG.colors.length],
    dash: DASHBOARD_CONFIG.dashPatterns[index % DASHBOARD_CONFIG.dashPatterns.length],
    pointStyle: DASHBOARD_CONFIG.pointStyles[index % DASHBOARD_CONFIG.pointStyles.length],
  };
}

// Stable style keyed by product_key (NOT array index) so a product keeps the same
// colour / dash / point across both charts and after deselect + reselect.
function dashboardSeriesStyleForProduct(productKey) {
  const key = String(productKey || '');
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) % 100000;
  }
  return dashboardSeriesStyle(Math.abs(hash));
}

// Collision-free colour assignment for the CURRENT chart selection. Each selected
// product is given the lowest free palette slot and keeps it across re-renders;
// deselecting a product releases its slot for reuse. Because the picker caps the
// selection at DASHBOARD_CONFIG.productSeriesMax (10) and the palette has 10 colours,
// no two selected products ever share a colour. Returns Map(product_key -> style).
function dashboardChartStyleMap() {
  const dashboard = state.hqa.dashboard;
  const selected = dashboard.chartProducts || [];
  const palette = DASHBOARD_CONFIG.colors;
  const assign = dashboard.chartColorAssign || (dashboard.chartColorAssign = {});

  const selectedSet = new Set(selected);
  Object.keys(assign).forEach((key) => { if (!selectedSet.has(key)) delete assign[key]; });

  const used = new Set(Object.values(assign));
  selected.forEach((key) => {
    if (assign[key] === undefined) {
      let idx = 0;
      while (used.has(idx) && idx < palette.length) idx += 1;
      assign[key] = idx % palette.length;
      used.add(assign[key]);
    }
  });

  const map = new Map();
  selected.forEach((key) => { map.set(key, dashboardSeriesStyle(assign[key])); });
  return map;
}

// Single-product colour: its assigned chart colour if it is in the current chart
// selection, otherwise a stable per-key colour (used by the drill-down accent).
function dashboardProductColor(productKey) {
  const style = dashboardChartStyleMap().get(productKey);
  return (style || dashboardSeriesStyleForProduct(productKey)).color;
}

function dashboardProductMap(analysis) {
  const map = new Map();
  (analysis?.products || []).forEach((product) => map.set(product.product_key, product));
  return map;
}

function getDashboardProduct(analysis, productKey) {
  return dashboardProductMap(analysis).get(productKey) || null;
}

function dashboardGroupPeriodMap(analysis) {
  const map = new Map();
  (analysis?.group_periods || []).forEach((item) => {
    map.set(`${item.group}@@${item.period}`, item);
  });
  return map;
}

function getDashboardGroupPeriod(analysis, group, period) {
  if (!analysis || !group || !period) return null;
  return dashboardGroupPeriodMap(analysis).get(`${group}@@${period}`) || null;
}

function getDashboardPreviousPeriod(analysis, period) {
  const periods = analysis?.periods || [];
  const index = periods.indexOf(period);
  return index > 0 ? periods[index - 1] : '';
}

function renderDashboardDelta(currentValue, previousValue, type, currency = 'USD', inverse = false) {
  const current = Number(currentValue);
  const previous = Number(previousValue);
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return '<span class="dashboard-delta dashboard-delta--muted">—</span>';
  const delta = current - previous;
  if (Math.abs(delta) < 0.0001) return '<span class="dashboard-delta dashboard-delta--muted">±0</span>';
  const up = delta > 0;
  const positive = inverse ? !up : up;
  let value = '';
  if (type === 'currency') value = formatDashboardCurrency(Math.abs(delta), currency);
  else if (type === 'points') value = `${Math.abs(delta).toFixed(0)}đ%`;
  else value = formatDashboardNumber(Math.abs(delta), 0);
  return `<span class="dashboard-delta ${positive ? 'dashboard-delta--good' : 'dashboard-delta--bad'}">${up ? '▲' : '▼'} ${escapeHtml(value)}</span>`;
}

function renderDashboardRangeSvg(stats, color, currency) {
  if (!stats || !Number.isFinite(Number(stats.min_price)) || !Number.isFinite(Number(stats.max_price))) {
    return '<div class="empty-state">Không có đủ dữ liệu giá cho kỳ đã chọn.</div>';
  }
  const min = Number(stats.min_price);
  const max = Number(stats.max_price);
  const p25 = Number.isFinite(Number(stats.p25)) ? Number(stats.p25) : min;
  const p75 = Number.isFinite(Number(stats.p75)) ? Number(stats.p75) : max;
  const median = Number.isFinite(Number(stats.median_price)) ? Number(stats.median_price) : min;
  const avg = Number.isFinite(Number(stats.avg_price)) ? Number(stats.avg_price) : median;
  const width = 720;
  const height = 96;
  const left = 28;
  const right = 28;
  const y = 50;
  const span = Math.max(max - min, 1);
  const x = (value) => left + ((value - min) / span) * (width - left - right);
  const tick = (value, label, below = false, strong = false) => {
    const px = x(value);
    return `<line x1="${px}" y1="${y - 7}" x2="${px}" y2="${y + 7}" stroke="${strong ? color : '#94A3B8'}" stroke-width="${strong ? 2 : 1}"/><text x="${px}" y="${below ? y + 24 : y - 15}" text-anchor="middle" fill="#64748B" font-size="10.5">${escapeHtml(label)}</text>`;
  };
  return `<svg viewBox="0 0 ${width} ${height}" width="100%" role="img" aria-label="Dải giá thị trường từ ${escapeHtml(formatDashboardCurrency(min, currency))} đến ${escapeHtml(formatDashboardCurrency(max, currency))}" class="dashboard-range-svg"><rect x="${x(p25)}" y="${y - 10}" width="${Math.max(x(p75) - x(p25), 5)}" height="20" rx="4" fill="${color}" opacity="0.16"/><line x1="${x(min)}" y1="${y}" x2="${x(max)}" y2="${y}" stroke="#CBD5E1" stroke-width="2" stroke-linecap="round"/>${tick(min, formatDashboardCurrency(min, currency), true)}${tick(max, formatDashboardCurrency(max, currency), true)}${tick(median, `Trung vị ${formatDashboardCurrency(median, currency)}`, false, true)}<circle cx="${x(avg)}" cy="${y}" r="4.5" fill="${color}"/><text x="${x(avg)}" y="${y + 39}" text-anchor="middle" fill="${color}" font-size="10.5">TB ${escapeHtml(formatDashboardCurrency(avg, currency))}</text></svg>`;
}

function renderDashboardSparkline(statsRows, selectedPeriod, color) {
  const usable = (statsRows || []).filter((row) => Number.isFinite(Number(row.avg_price)));
  if (!usable.length) return '<div class="empty-state">Không có dữ liệu xu hướng giá.</div>';
  const selectedIndex = Math.max(0, usable.findIndex((row) => row.period === selectedPeriod));
  const endIndex = selectedIndex >= 0 ? selectedIndex : usable.length - 1;
  const startIndex = Math.max(0, endIndex - 5);
  const rows = usable.slice(startIndex, endIndex + 1);
  const width = 320;
  const height = 68;
  const padding = 10;
  const values = rows.map((row) => Number(row.avg_price));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const x = (index) => padding + (rows.length <= 1 ? 0 : (index / (rows.length - 1)) * (width - padding * 2));
  const y = (value) => height - padding - ((value - min) / span) * (height - padding * 2);
  const path = values.map((value, index) => `${index ? 'L' : 'M'} ${x(index).toFixed(1)} ${y(value).toFixed(1)}`).join(' ');
  const circles = values.map((value, index) => {
    const isSelected = rows[index]?.period === selectedPeriod;
    return `<circle cx="${x(index)}" cy="${y(value)}" r="${isSelected ? 4.5 : 2.6}" fill="${isSelected ? color : '#94A3B8'}"><title>${escapeHtml(rows[index]?.period || '')}: ${escapeHtml(formatDashboardCurrency(value, rows[index]?.currency || 'USD'))}</title></circle>`;
  }).join('');
  return `<svg viewBox="0 0 ${width} ${height}" width="100%" role="img" aria-label="Xu hướng giá trung bình 6 kỳ" class="dashboard-sparkline"><path d="${path}" fill="none" stroke="${color}" stroke-width="2.3" stroke-linejoin="round" stroke-linecap="round"/>${circles}</svg>`;
}

function buildDashboardRecommendation(current, previous) {
  if (!current || !Number.isFinite(Number(current.min_price)) || !Number.isFinite(Number(current.median_price)) || !Number.isFinite(Number(current.p75))) return null;
  const fast = Number(current.min_price) * 0.97;
  const balanced = Number(current.median_price);
  const premium = Number(current.p75);
  const priceChange = previous ? dashboardPercentChange(current.avg_price, previous.avg_price) : null;
  let recommended = 'Cân bằng';
  let reason = `Thị trường tương đối ổn định. Niêm yết quanh trung vị ${formatDashboardCurrency(balanced, current.currency)} để cân bằng tốc độ bán và lợi nhuận.`;

  if (Number(current.out_of_stock_pct || 0) >= 40 || Number(current.seller_count || 0) <= 3) {
    recommended = 'Lợi nhuận cao';
    reason = `Nguồn cung đang hạn chế: hết hàng ${Number(current.out_of_stock_pct || 0).toFixed(0)}% và có ${formatDashboardNumber(current.seller_count || 0)} người bán. Có thể thử vùng P75 ${formatDashboardCurrency(premium, current.currency)}.`;
  } else if (Number(current.new_seller_count || 0) >= 3 || (priceChange !== null && priceChange <= -15)) {
    recommended = 'Bán nhanh';
    const signals = [];
    if (Number(current.new_seller_count || 0) >= 3) signals.push(`${current.new_seller_count} người bán mới`);
    if (priceChange !== null && priceChange <= -15) signals.push(`giá TB giảm ${Math.abs(priceChange).toFixed(0)}%`);
    reason = `Cạnh tranh đang nóng lên (${signals.join(', ')}). Mức ${formatDashboardCurrency(fast, current.currency)} giúp nổi bật hơn giá thấp nhất hiện tại.`;
  }

  return {
    recommended,
    reason,
    items: [
      { label: 'Bán nhanh', note: 'thấp hơn giá rẻ nhất ~3%', value: fast, color: '#16A34A' },
      { label: 'Cân bằng', note: 'ngang trung vị thị trường', value: balanced, color: '#2F6BE4' },
      { label: 'Lợi nhuận cao', note: 'nhóm giá cao P75', value: premium, color: '#F59E0B' },
    ],
  };
}

function renderDashboardTopSellers(items, color, currency, totalSellers) {
  if (!items?.length) return '<div class="empty-state">Không có dữ liệu người bán cho Model + kỳ đã chọn.</div>';
  const top = items.slice(0, 10);
  const maxListings = Math.max(...top.map((item) => Number(item.listing_count || 0)), 1);
  const priced = top.filter((item) => Number.isFinite(Number(item.min_price)));
  const cheapest = priced.length ? Math.min(...priced.map((item) => Number(item.min_price))) : null;
  return `
    <div class="dashboard-top-sellers-heading"><span>Xếp theo số listing · thanh nền = mức áp đảo · <b class="dashboard-cheapest-mark">▼</b> = rẻ nhất</span><span>Tổng ${formatRecordCount(totalSellers || items.length)} người bán${Number(totalSellers || items.length) > 10 ? ' · hiện 10' : ''}</span></div>
    <div class="dashboard-top-seller-grid dashboard-top-seller-grid--header"><span>#</span><span>Người bán</span><span>Listing</span><span>Giá TB</span><span>Rẻ nhất</span></div>
    <div class="dashboard-top-seller-list">${top.map((item, index) => {
      const minPrice = Number(item.min_price);
      const isCheapest = cheapest !== null && Number.isFinite(minPrice) && minPrice <= cheapest + 0.001;
      const width = Math.max(6, Math.round((Number(item.listing_count || 0) / maxListings) * 100));
      return `<div class="dashboard-top-seller-row"><span class="dashboard-top-seller-fill" style="width:${width}%;background:${color};"></span><span class="dashboard-rank">${index + 1}</span><span class="dashboard-seller-name">${escapeHtml(item.seller || 'Unknown seller')}</span><span class="dashboard-seller-count">${formatRecordCount(item.listing_count || 0)}</span><span class="dashboard-seller-value">${formatDashboardCurrency(item.avg_price, currency)}</span><span class="dashboard-seller-min ${isCheapest ? 'dashboard-seller-min--lead' : ''}">${isCheapest ? '▼ rẻ nhất ' : ''}${formatDashboardCurrency(item.min_price, currency)}</span></div>`;
    }).join('')}</div>`;
}

function renderDashboardAlerts(alerts) {
  if (!alerts?.length) return '<div class="empty-state">Không phát hiện bất thường whole-product ở kỳ mới nhất.</div>';
  const meta = {
    critical: { label: 'NGHIÊM TRỌNG', color: '#DC2626' },
    warning: { label: 'CẦN THEO DÕI', color: '#D97706' },
    info: { label: 'GHI NHẬN', color: '#2563EB' },
  };

  return `<div class="dashboard-alert-list dashboard-scroll">${alerts.map((alert) => {
    const severity = meta[String(alert.severity || 'info').toLowerCase()] || meta.info;
    const severityKey = String(
  alert.severity || 'info'
).toLowerCase();

    const currency = alert.currency || 'USD';
    let metric = escapeHtml(alert.title || 'Cảnh báo');
    let detail = alert.message || '';
    if (alert.type === 'price_drop') {
      metric = `Giá TB ▼ ${Math.abs(Number(alert.change_percent || 0)).toFixed(1)}%`;
      detail = `${formatDashboardCurrency(alert.previous_avg_price, currency)} → ${formatDashboardCurrency(alert.current_avg_price, currency)} · ${formatRecordCount(alert.whole_product_count || 0)} whole-product listing`;
    } else if (alert.type === 'new_low') {
      metric = `Đáy giá mới ${formatDashboardCurrency(alert.current_min_price, currency)}`;
      detail = `Dưới đáy cũ ${formatDashboardCurrency(alert.previous_floor_price, currency)} · không tính parts`;
    } else if (alert.type === 'new_seller') {
      metric = `Seller ↑ ${formatRecordCount(alert.new_seller_count || 0)}`;
      detail = `${(alert.new_sellers || []).slice(0, 3).map(escapeHtml).join(', ')}${Number(alert.new_seller_count || 0) > 3 ? '…' : ''} · whole-product sellers`;
    } else if (alert.type === 'out_of_stock_spike') {
      metric = `Hết hàng ▲ ${Number(alert.change_points || 0).toFixed(0)}đ%`;
      detail = `${Number(alert.previous_out_of_stock_pct || 0).toFixed(0)}% → ${Number(alert.current_out_of_stock_pct || 0).toFixed(0)}% whole-product listing`;
    }
    return `<button type="button" class="dashboard-alert-card dashboard-alert-card--${severityKey}" data-dashboard-alert-product="${escapeHtml(alert.product_key || alert.group || '')}" data-dashboard-alert-period="${escapeHtml(alert.period || '')}">
      <span class="dashboard-alert-sev" style="color:${severity.color}">● ${severity.label}</span>
      <span class="dashboard-alert-title">${escapeHtml(alert.product_label || alert.group || 'Sản phẩm')}</span>
      <span class="dashboard-alert-metric" style="color:${severity.color}">${escapeHtml(metric)}</span>
      <span class="dashboard-alert-detail">${escapeHtml(detail)}</span>
      <span class="dashboard-alert-cta">Xem phân tích →</span>
    </button>`;
  }).join('')}</div>`;
}

// Role-breakdown chips + audit table for the drill-down section.
const DASHBOARD_ROLE_LABELS = {
  whole_product: 'Sản phẩm hoàn chỉnh',
  component: 'Linh kiện',
  accessory: 'Phụ kiện',
  documentation: 'Tài liệu',
  irrelevant: 'Không liên quan',
  uncertain: 'Chưa chắc chắn',
};
const DASHBOARD_ROLE_BADGE = {
  whole_product: 'dashboard-role-badge--whole',
  component_part: 'dashboard-role-badge--part',
  accessory: 'dashboard-role-badge--accessory',
  documentation_media: 'dashboard-role-badge--doc',
  irrelevant: 'dashboard-role-badge--irrelevant',
  uncertain: 'dashboard-role-badge--uncertain',
};
// Map audit-table role filter -> which listing_role values it matches.
const DASHBOARD_ROLE_FILTERS = {
  all: null,
  whole_product: ['whole_product'],
  component: ['component_part'],
  accessory: ['accessory'],
  other: ['documentation_media', 'irrelevant'],
  uncertain: ['uncertain'],
};

function renderDashboardRoleBreakdown(roleCounts, activeFilter) {
  const counts = roleCounts || {};
  // key -> which role-filter it activates when clicked
  const cards = [
    { key: 'whole_product', filter: 'whole_product' },
    { key: 'component', filter: 'component' },
    { key: 'accessory', filter: 'accessory' },
    { key: 'documentation', filter: 'other' },
    { key: 'irrelevant', filter: 'other' },
    { key: 'uncertain', filter: 'uncertain' },
  ];
  return `<div class="dashboard-role-grid">${cards.map((card) => {
    const active = activeFilter === card.filter && activeFilter !== 'all';
    return `<button type="button" class="dashboard-role-card ${active ? 'dashboard-role-card--active' : ''}" data-dashboard-role-filter="${card.filter}"><small>${escapeHtml(DASHBOARD_ROLE_LABELS[card.key])}</small><strong>${formatRecordCount(counts[card.key] || 0)}</strong></button>`;
  }).join('')}</div>`;
}

function renderDashboardAuditTable(relatedListings, selectedPeriod, roleFilter) {
  const rolesWanted = DASHBOARD_ROLE_FILTERS[roleFilter] || null;
  const rows = (relatedListings || [])
    .filter((item) => item.period === selectedPeriod)
    .filter((item) => !rolesWanted || rolesWanted.includes(item.role));
  if (!rows.length) {
    return '<div class="empty-state">Không có listing liên quan cho bộ lọc/kỳ đã chọn.</div>';
  }
  const body = rows.map((item) => {
    const badgeClass = DASHBOARD_ROLE_BADGE[item.role] || 'dashboard-role-badge--uncertain';
    const eligible = item.eligible ? '✓' : (item.role === 'uncertain' ? '✕ review' : '✕');
    const titleCell = item.url
      ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || '-')}</a>`
      : escapeHtml(item.title || '-');
    return `<tr>
      <td class="dashboard-audit-title">${titleCell}</td>
      <td><span class="dashboard-role-badge ${badgeClass}">${escapeHtml(item.role)}</span></td>
      <td>${Number.isFinite(Number(item.role_confidence)) ? `${Math.round(Number(item.role_confidence))}%` : '—'}</td>
      <td class="dashboard-audit-reason">${escapeHtml(item.reason || '')}</td>
      <td class="dashboard-num">${item.price === null || item.price === undefined ? '—' : formatDashboardCurrency(item.price, item.currency || 'USD')}</td>
      <td>${escapeHtml(item.condition || '—')}</td>
      <td>${escapeHtml(item.category || '—')}</td>
      <td>${eligible}</td>
    </tr>`;
  }).join('');
  return `<div class="dashboard-audit-wrap"><table class="dashboard-audit-table">
    <thead><tr><th>Listing title</th><th>Role</th><th>Confidence</th><th>Reason</th><th>Giá</th><th>Condition</th><th>Category</th><th>Eligible</th></tr></thead>
    <tbody>${body}</tbody>
  </table></div>`;
}

function buildDashboardLegendMarkup(productKeys, productMap, styleMap) {
  return (productKeys || []).map((key) => {
    const style = (styleMap && styleMap.get(key)) || dashboardSeriesStyleForProduct(key);
    const product = productMap.get(key);
    const label = product ? product.product_label : key;
    const dashed = style.dash && style.dash.length ? 'dashboard-legend-item--dashed' : '';
    return `<span class="dashboard-legend-item ${dashed}"><i style="background:${style.color}"></i>${escapeHtml(label)}</span>`;
  }).join('');
}

function destroyHqaDashboardCharts() {
  hqaDashboardCharts.forEach((chart) => {
    try { chart.destroy(); } catch (error) { /* no-op */ }
  });
  hqaDashboardCharts = [];
}

// Render the two comparison charts from the CURRENT chart-product selection only.
// Missing product/period cells stay null (never coerced to 0). Called on its own when
// the selection changes so KPIs/alerts/drill-down are not re-fetched or re-rendered.
// Convert a #RRGGBB hex to an rgba() string (used for the translucent seller bars
// in the dual-axis combo chart so a product's two bars share one hue).
function dashboardRgba(hex, alpha) {
  const clean = String(hex || '').replace('#', '');
  if (clean.length !== 6) return `rgba(100, 116, 139, ${alpha})`;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function renderDashboardComparisonCharts() {
  destroyHqaDashboardCharts();
  const analysis = state.hqa.dashboard.analysis;
  const priceWrap = document.getElementById('dashboard-price-chart-wrap');
  const sellerWrap = document.getElementById('dashboard-seller-chart-wrap');
  const comboWrap = document.getElementById('dashboard-combo-chart-wrap');
  if (!analysis || !priceWrap || !sellerWrap) return;

  const selected = state.hqa.dashboard.chartProducts || [];
  const styleMap = dashboardChartStyleMap();
  const emptyMarkup = '<div class="dashboard-empty-chart">Chọn ít nhất 1 sản phẩm để hiển thị biểu đồ.</div>';
  const legendHost = document.getElementById('dashboard-chart-legend-host');
  if (legendHost) legendHost.innerHTML = buildDashboardLegendMarkup(selected, dashboardProductMap(analysis), styleMap);
  if (!selected.length) {
    priceWrap.innerHTML = emptyMarkup;
    sellerWrap.innerHTML = emptyMarkup;
    if (comboWrap) comboWrap.innerHTML = emptyMarkup;
    return;
  }
  priceWrap.innerHTML = '<canvas id="dashboard-price-chart" role="img" aria-label="Biểu đồ giá trung bình theo kỳ cho các sản phẩm đã chọn"></canvas>';
  sellerWrap.innerHTML = '<canvas id="dashboard-seller-chart" role="img" aria-label="Biểu đồ số người bán theo kỳ cho các sản phẩm đã chọn"></canvas>';

  if (typeof Chart === 'undefined' || !analysis.periods?.length) return;
  const labels = analysis.periods;
  const map = dashboardGroupPeriodMap(analysis);
  const productMap = dashboardProductMap(analysis);

  const buildDatasets = (field) => selected.map((key) => {
    const style = styleMap.get(key) || dashboardSeriesStyleForProduct(key);
    const product = productMap.get(key);
    return {
      label: product ? product.product_label : key,
      data: labels.map((period) => {
        const row = map.get(`${key}@@${period}`);
        const value = row ? Number(row[field]) : NaN;
        return Number.isFinite(value) ? value : null;
      }),
      borderColor: style.color,
      backgroundColor: style.color,
      borderWidth: 2,
      borderDash: style.dash,
      pointStyle: style.pointStyle,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.28,
      spanGaps: true,
    };
  });

  const baseOptions = (formatter) => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatter(context.parsed.y)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#64748B', autoSkip: labels.length > 8, maxTicksLimit: 8 } },
      y: { grid: { color: '#EDF1F7' }, border: { display: false }, ticks: { color: '#64748B', callback: formatter } },
    },
  });

  const currency = analysis.latest_period?.currency || 'USD';
  hqaDashboardCharts.push(new Chart(document.getElementById('dashboard-price-chart'), {
    type: 'line',
    data: { labels, datasets: buildDatasets('avg_price') },
    options: baseOptions((value) => formatDashboardCurrency(value, currency)),
  }));
  hqaDashboardCharts.push(new Chart(document.getElementById('dashboard-seller-chart'), {
    type: 'line',
    data: { labels, datasets: buildDatasets('seller_count') },
    options: baseOptions((value) => formatDashboardNumber(value, 0)),
  }));

  // Full-width dual-axis combo (grouped bar): each selected product shows a solid
  // price bar (left axis) + a translucent seller bar (right axis), same hue per product.
  if (comboWrap) {
    comboWrap.innerHTML = '<canvas id="dashboard-combo-chart" role="img" aria-label="Biểu đồ cột đôi giá trung bình và số người bán theo kỳ cho các sản phẩm đã chọn"></canvas>';
    const comboDatasets = [];
    selected.forEach((key) => {
      const style = styleMap.get(key) || dashboardSeriesStyleForProduct(key);
      const product = productMap.get(key);
      const label = product ? product.product_label : key;
      const seriesFor = (field) => labels.map((period) => {
        const row = map.get(`${key}@@${period}`);
        const value = row ? Number(row[field]) : NaN;
        return Number.isFinite(value) ? value : null;
      });
      comboDatasets.push({
        label: `${label} · Giá TB`, metric: 'price', productLabel: label,
        data: seriesFor('avg_price'), yAxisID: 'yPrice',
        backgroundColor: style.color, borderColor: style.color, borderWidth: 1,
        borderRadius: 3, categoryPercentage: 0.86, barPercentage: 0.92,
      });
      comboDatasets.push({
        label: `${label} · Người bán`, metric: 'sellers', productLabel: label,
        data: seriesFor('seller_count'), yAxisID: 'ySeller',
        backgroundColor: dashboardRgba(style.color, 0.38), borderColor: dashboardRgba(style.color, 0.75), borderWidth: 1,
        borderRadius: 3, categoryPercentage: 0.86, barPercentage: 0.92,
      });
    });
    hqaDashboardCharts.push(new Chart(document.getElementById('dashboard-combo-chart'), {
      type: 'bar',
      data: { labels, datasets: comboDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => {
                const isPrice = context.dataset.metric === 'price';
                const value = isPrice
                  ? formatDashboardCurrency(context.parsed.y, currency)
                  : `${formatDashboardNumber(context.parsed.y, 0)} người bán`;
                return `${context.dataset.productLabel} · ${isPrice ? 'Giá TB' : 'Người bán'}: ${value}`;
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#64748B', autoSkip: labels.length > 8, maxTicksLimit: 8 } },
          yPrice: {
            type: 'linear', position: 'left', beginAtZero: true,
            title: { display: true, text: 'Giá TB (USD)', color: '#475569', font: { weight: '700' } },
            grid: { color: '#EDF1F7' }, border: { display: false },
            ticks: { color: '#64748B', callback: (value) => formatDashboardCurrency(value, currency) },
          },
          ySeller: {
            type: 'linear', position: 'right', beginAtZero: true,
            title: { display: true, text: 'Số người bán', color: '#475569', font: { weight: '700' } },
            grid: { drawOnChartArea: false }, border: { display: false },
            ticks: { color: '#64748B', precision: 0, stepSize: 1 },
          },
        },
      },
    }));
  }
}

// --- Searchable multi-select product picker -------------------------------------
function dashboardFilteredProducts() {
  const analysis = state.hqa.dashboard.analysis;
  const query = String(state.hqa.dashboard.chartProductSearch || '').trim().toLowerCase();
  const products = analysis?.products || [];
  if (!query) return products;
  return products.filter((product) => {
    const haystack = `${product.product_label} ${product.brand} ${product.model} ${product.product_type} ${product.product_key}`.toLowerCase();
    return haystack.includes(query);
  });
}

function buildDashboardProductSelectorMarkup(analysis) {
  return `
    <div class="dashboard-ps" id="dashboard-ps">
      <span class="dashboard-ps-label">Sản phẩm hiển thị trên 2 biểu đồ</span>
      <button type="button" class="dashboard-ps-trigger" id="dashboard-ps-trigger" aria-expanded="false" aria-haspopup="listbox">
        <span class="dashboard-ps-chips" id="dashboard-ps-chips"></span>
        <span class="dashboard-ps-count" id="dashboard-ps-count"></span>
      </button>
      <div class="dashboard-ps-pop" id="dashboard-ps-pop" hidden>
        <div class="dashboard-ps-search"><input type="search" id="dashboard-ps-search" placeholder="Tìm theo tên sản phẩm, brand, model..." aria-label="Tìm sản phẩm" value="${escapeHtml(state.hqa.dashboard.chartProductSearch || '')}"></div>
        <div class="dashboard-ps-actions"><label><input type="checkbox" id="dashboard-ps-select-loaded"> Chọn tất cả đã tải</label><button type="button" id="dashboard-ps-clear">Clear</button></div>
        <div class="dashboard-ps-list" id="dashboard-ps-list" role="listbox" aria-multiselectable="true"></div>
        <div class="dashboard-ps-footer"><button type="button" id="dashboard-ps-load-more">Load more</button></div>
      </div>
      <div class="dashboard-ps-warn" id="dashboard-ps-warn"></div>
    </div>`;
}

// Update chips / count / list / warn without rebuilding the popup (keeps it open + focused).
function refreshDashboardSelectorUI() {
  const analysis = state.hqa.dashboard.analysis;
  if (!analysis) return;
  const dashboard = state.hqa.dashboard;
  const productMap = dashboardProductMap(analysis);
  const selected = dashboard.chartProducts || [];
  const max = DASHBOARD_CONFIG.productSeriesMax;

  const chips = document.getElementById('dashboard-ps-chips');
  if (chips) {
    const selectedProducts = selected.map((key) => productMap.get(key)).filter(Boolean);
    const shown = selectedProducts.slice(0, 3);
    chips.innerHTML = shown.map((product) => `<span class="dashboard-ps-chip"><span>${escapeHtml(product.product_label)}</span></span>`).join('')
      + (selectedProducts.length > 3 ? `<span class="dashboard-ps-chip dashboard-ps-chip--more">+${selectedProducts.length - 3}</span>` : '')
      + (selectedProducts.length ? '' : '<span class="dashboard-ps-placeholder">Chọn sản phẩm để so sánh…</span>');
  }
  const count = document.getElementById('dashboard-ps-count');
  if (count) count.textContent = `${selected.length}/${max}`;
  const compareMeta = document.getElementById('dashboard-compare-meta');
  if (compareMeta) compareMeta.textContent = `Đang so sánh ${selected.length} sản phẩm`;

  const list = document.getElementById('dashboard-ps-list');
  const filtered = dashboardFilteredProducts();
  const visibleRows = filtered.slice(0, dashboard.chartProductVisible);
  if (list) {
    list.innerHTML = visibleRows.length
      ? visibleRows.map((product) => {
        const checked = selected.includes(product.product_key) ? 'checked' : '';
        const excluded = product.excluded_count ? ` · ${formatRecordCount(product.excluded_count)} excluded` : '';
        return `<label class="dashboard-ps-row"><input type="checkbox" data-dashboard-ps-id="${escapeHtml(product.product_key)}" ${checked}><span class="dashboard-ps-main"><strong>${escapeHtml(product.product_label)}</strong><small>${escapeHtml([product.brand, product.model, product.product_type].filter(Boolean).join(' · ') || '—')}</small></span><span class="dashboard-ps-meta">${formatRecordCount(product.whole_product_listings)} listing · ${formatRecordCount(product.seller_count)} seller${excluded}</span></label>`;
      }).join('')
      : '<div class="dashboard-ps-empty">Không tìm thấy sản phẩm phù hợp.</div>';
  }
  const loadMore = document.getElementById('dashboard-ps-load-more');
  if (loadMore) loadMore.hidden = visibleRows.length >= filtered.length;
  const selectLoaded = document.getElementById('dashboard-ps-select-loaded');
  if (selectLoaded) selectLoaded.checked = visibleRows.length > 0 && visibleRows.every((product) => selected.includes(product.product_key));
  const warn = document.getElementById('dashboard-ps-warn');
  if (warn) warn.textContent = dashboard.chartWarn || '';
}

function toggleDashboardProduct(productKey, checkbox) {
  const dashboard = state.hqa.dashboard;
  const max = DASHBOARD_CONFIG.productSeriesMax;
  const selected = dashboard.chartProducts || [];
  if (selected.includes(productKey)) {
    dashboard.chartProducts = selected.filter((key) => key !== productKey);
    dashboard.chartWarn = '';
  } else {
    if (selected.length >= max) {
      if (checkbox) checkbox.checked = false;
      dashboard.chartWarn = `Chỉ có thể hiển thị tối đa ${max} sản phẩm cùng lúc để biểu đồ dễ đọc.`;
      refreshDashboardSelectorUI();
      return;
    }
    dashboard.chartProducts = [...selected, productKey];
    dashboard.chartWarn = '';
  }
  refreshDashboardSelectorUI();
  renderDashboardComparisonCharts();
}

function dashboardScopeSummary(filters) {
  const parts = [];
  if (filters.dateFrom || filters.dateTo) parts.push(`${filters.dateFrom || '...'} → ${filters.dateTo || '...'}`);
  if (filters.marketplaces?.length) parts.push(`Marketplace: ${filters.marketplaces.join(', ')}`);
  if (filters.brands?.length) parts.push(`Brand: ${filters.brands.join(', ')}`);
  if (filters.models?.length) parts.push(`Model: ${filters.models.join(', ')}`);
  if (filters.conditions?.length) parts.push(`Condition: ${filters.conditions.join(', ')}`);
  if (filters.statuses?.length) parts.push(`Status: ${filters.statuses.join(', ')}`);
  if (filters.categoryNames?.length) parts.push(`Category: ${filters.categoryNames.join(', ')}`);
  if (filters.keyword) parts.push(`Search: ${filters.keyword}`);
  return parts.length ? parts.join(' · ') : 'Toàn bộ dữ liệu đang có';
}

function dashboardCsvCell(value) {
  if (value === null || value === undefined) return '';
  const text = Array.isArray(value) ? value.join(' | ') : String(value);
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function downloadDashboardCsv(dataset) {
  const analysis = state.hqa.dashboard.analysis;
  if (!analysis) return;
  let rows = [];
  let filename = `hqa_dashboard_${dataset}.csv`;
  if (dataset === 'group_period') {
    rows = (analysis.group_periods || []).map((item) => ({
      group: item.group,
      period: item.period,
      listing_count: item.listing_count,
      unique_ids: item.unique_ids,
      seller_count: item.seller_count,
      price_sample: item.price_sample,
      min_price: item.min_price,
      p25: item.p25,
      median_price: item.median_price,
      avg_price: item.avg_price,
      p75: item.p75,
      max_price: item.max_price,
      std: item.std,
      cv: item.cv,
      out_of_stock_count: item.out_of_stock_count,
      out_of_stock_pct: item.out_of_stock_pct,
      new_seller_count: item.new_seller_count,
      currency: item.currency,
    }));
  } else if (dataset === 'alerts') {
    rows = (analysis.alerts || []).map((item) => ({
      severity: item.severity,
      type: item.type,
      group: item.group,
      period: item.period,
      currency: item.currency,
      title: item.title,
      message: item.message,
      previous_avg_price: item.previous_avg_price,
      current_avg_price: item.current_avg_price,
      change_percent: item.change_percent,
      current_min_price: item.current_min_price,
      previous_floor_price: item.previous_floor_price,
      new_seller_count: item.new_seller_count,
      new_sellers: item.new_sellers || [],
      previous_out_of_stock_pct: item.previous_out_of_stock_pct,
      current_out_of_stock_pct: item.current_out_of_stock_pct,
      change_points: item.change_points,
    }));
  } else if (dataset === 'top_sellers') {
    const current = getDashboardGroupPeriod(analysis, state.hqa.dashboard.selectedProduct, state.hqa.dashboard.selectedPeriod);
    rows = (current?.top_sellers || []).slice(0, 10).map((item, index) => ({
      rank: index + 1,
      product_key: state.hqa.dashboard.selectedProduct,
      product_label: current?.product_label || '',
      period: state.hqa.dashboard.selectedPeriod,
      seller: item.seller,
      listing_count: item.listing_count,
      avg_price: item.avg_price,
      min_price: item.min_price,
      currency: current?.currency || '',
    }));
    filename = `hqa_dashboard_top10_${state.hqa.dashboard.selectedProduct || 'product'}_${state.hqa.dashboard.selectedPeriod || 'period'}.csv`;
  } else if (dataset === 'audit') {
    const productKey = state.hqa.dashboard.selectedProduct;
    const related = (analysis.related_listings || {})[productKey] || [];
    rows = related.map((item) => ({
      product_key: productKey,
      period: item.period,
      listing_id: item.listing_id,
      listing_title: item.title,
      listing_role: item.role,
      role_confidence: item.role_confidence,
      role_reasons: item.reason,
      eligible_for_market_analytics: item.eligible,
      price: item.price,
      currency: item.currency,
      condition: item.condition,
      category: item.category,
      seller: item.seller,
      status: item.status,
      url: item.url,
    }));
    filename = `hqa_dashboard_role_audit_${productKey || 'product'}.csv`;
  }
  if (!rows.length) {
    state.hqa.dashboard.error = 'Không có dữ liệu để xuất CSV.';
    renderHqaDashboard();
    return;
  }
  const headers = Array.from(rows.reduce((set, row) => {
    Object.keys(row).forEach((key) => set.add(key));
    return set;
  }, new Set()));
  const csv = `\ufeff${headers.map(dashboardCsvCell).join(',')}\r\n${rows.map((row) => headers.map((header) => dashboardCsvCell(row[header])).join(',')).join('\r\n')}`;
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.replace(/[^a-zA-Z0-9._-]+/g, '_');
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function closeDashboardProductSelector() {
  state.hqa.dashboard.chartProductSelectorOpen = false;
  const pop = document.getElementById('dashboard-ps-pop');
  const trigger = document.getElementById('dashboard-ps-trigger');
  if (pop) pop.hidden = true;
  if (trigger) trigger.setAttribute('aria-expanded', 'false');
}

// Global (document-level) listeners for the product picker. Bound exactly once so
// repeated dashboard re-renders never stack duplicate handlers.
function ensureDashboardGlobalListeners() {
  if (dashboardGlobalListenersBound) return;
  dashboardGlobalListenersBound = true;
  document.addEventListener('click', (event) => {
    if (!state.hqa.dashboard.chartProductSelectorOpen) return;
    const selector = document.getElementById('dashboard-ps');
    if (selector && !selector.contains(event.target)) closeDashboardProductSelector();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.hqa.dashboard.chartProductSelectorOpen) closeDashboardProductSelector();
  });
}

// Re-render only the drill-down role chips + audit table (used when a role filter is
// clicked) so the comparison charts and product selection are left untouched.
function refreshDashboardDrillAudit() {
  const data = state.hqa.dashboard;
  const analysis = data.analysis;
  if (!analysis) return;
  const current = getDashboardGroupPeriod(analysis, data.selectedProduct, data.selectedPeriod);
  const roleGrid = document.getElementById('dashboard-role-grid-host');
  if (roleGrid) roleGrid.innerHTML = renderDashboardRoleBreakdown(current?.role_counts, data.roleFilter);
  const auditHost = document.getElementById('dashboard-audit-host');
  if (auditHost) {
    const related = (analysis.related_listings || {})[data.selectedProduct] || [];
    auditHost.innerHTML = renderDashboardAuditTable(related, data.selectedPeriod, data.roleFilter);
  }
  bindDashboardRoleCards();
}

function bindDashboardRoleCards() {
  document.querySelectorAll('[data-dashboard-role-filter]').forEach((card) => {
    card.addEventListener('click', () => {
      const value = card.getAttribute('data-dashboard-role-filter') || 'all';
      state.hqa.dashboard.roleFilter = (state.hqa.dashboard.roleFilter === value) ? 'all' : value;
      refreshDashboardDrillAudit();
    });
  });
}

function renderHqaDashboard() {
  const dashboardView = document.getElementById('hqa-dashboard-view');
  if (!dashboardView) return;
  destroyHqaDashboardCharts();

  const data = state.hqa.dashboard;
  const analysis = data.analysis;
  if (data.loading && !analysis) {
    dashboardView.innerHTML = '<div class="dashboard-loading"><span class="loading-spinner" aria-hidden="true"></span><span>Đang phân tích dữ liệu Dashboard...</span></div>';
    return;
  }
  if (!analysis) {
    dashboardView.innerHTML = `${data.error ? `<div class="error">${escapeHtml(data.error)}</div>` : ''}<div class="empty-state">Chưa có dữ liệu Dashboard.</div>`;
    return;
  }

  const latest = analysis.latest_period || {};
  const products = analysis.groups || [];
  const periods = analysis.periods || [];
  const granularity = analysis.granularity || data.granularity || 'month';
  const periodLabel = granularity === 'week' ? 'tuần' : 'tháng';

  const selectedProduct = products.includes(data.selectedProduct) ? data.selectedProduct : (products[0] || '');
  const selectedPeriod = periods.includes(data.selectedPeriod) ? data.selectedPeriod : (latest.period || periods[periods.length - 1] || '');
  data.selectedProduct = selectedProduct;
  data.selectedPeriod = selectedPeriod;
  if (!DASHBOARD_ROLE_FILTERS[data.roleFilter]) data.roleFilter = 'all';

  const productInfo = getDashboardProduct(analysis, selectedProduct);
  const current = getDashboardGroupPeriod(analysis, selectedProduct, selectedPeriod);
  const previousPeriod = getDashboardPreviousPeriod(analysis, selectedPeriod);
  const previous = previousPeriod ? getDashboardGroupPeriod(analysis, selectedProduct, previousPeriod) : null;
  const selectedProductRows = (analysis.group_periods || []).filter((item) => item.group === selectedProduct);
  const selectedColor = dashboardProductColor(selectedProduct);
  const currency = current?.currency || latest.currency || 'USD';
  const recommendation = buildDashboardRecommendation(current, previous);
  const priceChange = previous ? dashboardPercentChange(current?.avg_price, previous?.avg_price) : null;

  const wholeCount = Number(latest.whole_product_count ?? latest.listing_count ?? 0);
  const relatedCount = Number(latest.related_listing_count ?? 0);
  const kpis = [
    { label: 'Listing phân tích', value: formatRecordCount(wholeCount), detail: `${formatRecordCount(wholeCount)} whole-product / ${formatRecordCount(relatedCount)} liên quan`, accent: '#2F6BE4',tooltip:
      'Listing đủ điều kiện: Chỉ các listing được phân loại là sản phẩm hoàn chỉnh (whole_product) và được sử dụng để tính giá, số người bán, cảnh báo và gợi ý niêm yết. Linh kiện, phụ kiện, tài liệu, listing không liên quan và chưa chắc chắn không được tính.' },
    { label: 'Sản phẩm', value: formatRecordCount(latest.product_count || 0), detail: 'sản phẩm có dữ liệu hợp lệ', accent: '#7C5CFC' },
    { label: 'Người bán', value: formatRecordCount(latest.seller_count || 0), detail: 'whole-product sellers', accent: '#16A34A' },
    { label: 'Giá trung vị', value: formatDashboardCurrency(latest.median_price, latest.currency || 'USD'), detail: 'không tính parts/accessories', accent: '#475569' },
    { label: 'Hết hàng', value: formatRecordCount(latest.out_of_stock_count || 0), detail: `${Number(latest.out_of_stock_pct || 0).toFixed(1)}% whole-product listing`, accent: '#EF4444', valueColor: '#EF4444' },
  ];

  const productLabel = productInfo?.product_label || selectedProduct || 'Sản phẩm';
  const identityBits = productInfo ? [productInfo.brand && `brand ${productInfo.brand}`, productInfo.model && `model ${productInfo.model}`, productInfo.product_type].filter(Boolean) : [];

  // Drill-down body depends on how much whole-product data the period has (spec §25).
  let drillBody = '';
  if (!current || Number(current.related_listing_count || 0) === 0) {
    drillBody = '<div class="empty-state">Sản phẩm không có listing liên quan trong kỳ đã chọn.</div>';
  } else {
    const excluded = Number(current.excluded_from_market_analytics_count || 0);
    const uncertainCount = Number(current.role_counts?.uncertain || 0);
    const relatedForPeriod = Number(current.related_listing_count || 0);
    const uncertainWarn = relatedForPeriod > 0 && (uncertainCount / relatedForPeriod) >= 0.2
      ? `<div class="dashboard-summary-note dashboard-summary-note--warn">${((uncertainCount / relatedForPeriod) * 100).toFixed(0)}% listing chưa phân loại chắc chắn; market analytics đang loại các listing này.</div>`
      : '';
    const hasWhole = Number(current.whole_product_count || 0) > 0;
    const analyticsBody = hasWhole ? `
        <div class="dashboard-stats-grid">
          <div class="dashboard-stat"><small>Listing hợp lệ</small><strong>${formatRecordCount(current.whole_product_count || 0)}</strong></div>
          <div class="dashboard-stat"><small>Listing liên quan</small><strong>${formatRecordCount(current.related_listing_count || 0)}</strong></div>
          <div class="dashboard-stat"><small>Người bán</small><strong>${formatRecordCount(current.seller_count || 0)}</strong><em>${renderDashboardDelta(current.seller_count, previous?.seller_count, 'number')}</em></div>
          <div class="dashboard-stat"><small>Thấp nhất</small><strong>${formatDashboardCurrency(current.min_price, currency)}</strong><em>${renderDashboardDelta(current.min_price, previous?.min_price, 'currency', currency)}</em></div>
          <div class="dashboard-stat"><small>Trung vị</small><strong>${formatDashboardCurrency(current.median_price, currency)}</strong><em>${renderDashboardDelta(current.median_price, previous?.median_price, 'currency', currency)}</em></div>
          <div class="dashboard-stat"><small>Giá TB</small><strong>${formatDashboardCurrency(current.avg_price, currency)}</strong><em>${renderDashboardDelta(current.avg_price, previous?.avg_price, 'currency', currency)}</em></div>
          <div class="dashboard-stat"><small>% hết hàng</small><strong>${Number(current.out_of_stock_pct || 0).toFixed(0)}%</strong><em>${renderDashboardDelta(current.out_of_stock_pct, previous?.out_of_stock_pct, 'points', currency, true)}</em></div>
        </div>
        <div class="dashboard-range-panel"><div class="dashboard-section-label">Dải giá thị trường — chỉ whole product</div><div class="dashboard-range-caption">Vùng tô đậm = 50% listing ở giữa (P25–P75); vạch = trung vị; chấm = giá TB.</div>${renderDashboardRangeSvg(current, selectedColor, currency)}</div>
        <div class="dashboard-spark-grid">
          <div class="dashboard-spark-panel"><div class="dashboard-section-label">Xu hướng giá TB 6 kỳ</div><div class="dashboard-trend-caption">Chỉ whole-product eligible listings · kỳ đang chọn được highlight.</div>${renderDashboardSparkline(selectedProductRows, selectedPeriod, selectedColor)}<div class="dashboard-trend-text">${priceChange === null ? 'Chưa có kỳ trước để so sánh.' : `So kỳ trước: giá TB ${priceChange > 1 ? 'tăng' : (priceChange < -1 ? 'giảm' : 'đi ngang')} ${Math.abs(priceChange).toFixed(1)}%; người bán ${previous ? `${Number(current.seller_count || 0) - Number(previous.seller_count || 0) >= 0 ? '+' : ''}${Number(current.seller_count || 0) - Number(previous.seller_count || 0)}` : '—'}; CV ${Number(current.cv || 0).toFixed(0)}%.`}</div></div>
          <div class="dashboard-spark-panel"><div class="dashboard-section-label">Gợi ý giá niêm yết</div>${recommendation ? `<div class="dashboard-suggestion-list">${recommendation.items.map((item) => `<div class="dashboard-suggestion ${item.label === recommendation.recommended ? 'dashboard-suggestion--active' : ''}"><span class="dashboard-suggestion-dot" style="background:${item.color}"></span><span class="dashboard-suggestion-copy"><b>${escapeHtml(item.label)}</b><small>${escapeHtml(item.note)}</small></span><strong>${formatDashboardCurrency(item.value, currency)}</strong></div>`).join('')}</div>` : '<div class="empty-state">Không đủ dữ liệu giá để tạo gợi ý.</div>'}</div>
        </div>
        ${recommendation ? `<div class="dashboard-note">${escapeHtml(recommendation.reason)}</div>` : ''}
        <div class="dashboard-top-sellers-panel"><div class="dashboard-section-label">Top 10 người bán — chỉ whole product</div>${renderDashboardTopSellers(current.top_sellers || [], selectedColor, currency, current.seller_count)}</div>
      ` : `<div class="dashboard-summary-note dashboard-summary-note--warn">Có ${formatRecordCount(current.related_listing_count || 0)} listing liên quan nhưng chưa có listing sản phẩm hoàn chỉnh đủ điều kiện phân tích giá trong kỳ này.</div>`;

    drillBody = `
      <div class="dashboard-product-line"><b style="color:${selectedColor}">${escapeHtml(productLabel)}</b>${identityBits.length ? ` · ${escapeHtml(identityBits.join(' · '))}` : ''} · CV ${Number(current.cv || 0).toFixed(0)}%</div>
      <div class="dashboard-summary-note">${formatRecordCount(current.related_listing_count || 0)} listing liên quan · <b>${formatRecordCount(current.whole_product_count || 0)} listing sản phẩm hoàn chỉnh dùng cho market analytics</b> · ${formatRecordCount(excluded)} listing parts/accessories/docs/uncertain đã loại khỏi giá và seller trend.</div>
      ${uncertainWarn}
      <div class="dashboard-section-label">Phân loại listing liên quan</div>
      <div id="dashboard-role-grid-host">${renderDashboardRoleBreakdown(current.role_counts, data.roleFilter)}</div>
      ${analyticsBody}
      <div class="dashboard-audit-panel"><div class="dashboard-section-label-row"><span class="dashboard-section-label">Listings liên quan — classification audit</span><button type="button" class="dashboard-audit-export hvr-float-shadow" data-dashboard-export="audit">Xuất role audit CSV</button></div><div class="dashboard-audit-sub">Bảng giúp Marketing thấy vì sao listing được tính hoặc bị loại.</div><div id="dashboard-audit-host">${renderDashboardAuditTable((analysis.related_listings || {})[selectedProduct] || [], selectedPeriod, data.roleFilter)}</div></div>
    `;
  }

  dashboardView.innerHTML = `
    <div class="dashboard-action-row">
      <div class="dashboard-scope-copy"><strong>Marketing Dashboard</strong><span>main analytics chỉ dùng whole-product listings · ${escapeHtml(dashboardScopeSummary(data.appliedFilters))}</span></div>
      <div class="dashboard-view-controls" aria-label="Tùy chọn phân tích Dashboard">
        <label><span>Kỳ</span><select id="dashboard-granularity"><option value="month" ${granularity === 'month' ? 'selected' : ''}>Tháng</option><option value="week" ${granularity === 'week' ? 'selected' : ''}>Tuần</option></select></label>
      </div>
      <div class="dashboard-export-actions" aria-label="Xuất dữ liệu Dashboard">
        <button class="hvr-float-shadow" type="button" data-dashboard-export="group_period">Tổng hợp CSV</button>
        <button class="hvr-float-shadow" type="button" data-dashboard-export="alerts">Cảnh báo CSV</button>
        <button class="hvr-float-shadow" type="button" data-dashboard-export="top_sellers" ${current?.top_sellers?.length ? '' : 'disabled'}>Top 10 CSV</button>
      </div>
    </div>
    ${data.error ? `<div class="error">${escapeHtml(data.error)}</div>` : ''}
    <div class="dashboard-kpi-grid">
  ${kpis.map((item, index) => {
    const hasTooltip = Boolean(item.tooltip);
    const tooltipId = `dashboard-kpi-tooltip-${index}`;

    return `
      <article
        class="dashboard-kpi-card ${hasTooltip ? 'dashboard-kpi-card--has-tooltip' : ''}"
        style="border-top-color:${item.accent}"
        ${hasTooltip ? `tabindex="0" aria-describedby="${tooltipId}"` : ''}
      >
        <div class="dashboard-kpi-label">
          ${escapeHtml(item.label)}

          ${hasTooltip ? `
            <span
              class="dashboard-kpi-info-icon"
              aria-hidden="true"
            >i</span>
          ` : ''}
        </div>

        <div
          class="dashboard-kpi-value"
          style="color:${item.valueColor || item.accent}"
        >
          ${escapeHtml(item.value)}
        </div>

        <div class="dashboard-kpi-detail">
          ${escapeHtml(item.detail)}
        </div>

        ${hasTooltip ? `
          <div
            id="${tooltipId}"
            class="dashboard-kpi-tooltip"
            role="tooltip"
          >
            ${escapeHtml(item.tooltip)}
          </div>
        ` : ''}
      </article>
    `;
  }).join('')}
</div>

    <section class="dashboard-panel dashboard-panel--alert">
      <div class="dashboard-panel-heading"><div class="dashboard-panel-title-wrap"><span class="dashboard-alert-dot" aria-hidden="true"></span><span class="dashboard-panel-title">Cảnh báo bất thường</span></div><span class="dashboard-panel-meta">${formatRecordCount((analysis.alerts || []).length)} cảnh báo</span></div>
      <div class="dashboard-panel-subtext">Cảnh báo theo Sản phẩm × kỳ · chạy trên whole-product analytics · click card để xem drill-down.</div>
      ${renderDashboardAlerts(analysis.alerts || [])}
    </section>

    <section class="dashboard-panel">
      <div class="dashboard-panel-heading"><div class="dashboard-panel-title-wrap"><span class="dashboard-panel-title">Xu hướng thị trường theo sản phẩm</span></div><span class="dashboard-panel-meta" id="dashboard-compare-meta"></span></div>
      <div class="dashboard-panel-subtext">Nguồn là listing thật; chart chỉ hiển thị Sản phẩm đã chọn để tránh rối khi dữ liệu lớn.</div>
      <div class="dashboard-chart-head-row">${buildDashboardProductSelectorMarkup(analysis)}</div>
      <div class="dashboard-chart-legend" id="dashboard-chart-legend-host" aria-hidden="true"></div>
      <div class="dashboard-chart-grid">
        <article class="dashboard-chart-panel"><div class="dashboard-chart-heading">Giá trung bình theo ${escapeHtml(periodLabel)}</div><div class="dashboard-chart-caption">AVG(price) · chỉ whole_product eligible</div><div class="dashboard-chart-wrap" id="dashboard-price-chart-wrap"><canvas id="dashboard-price-chart"></canvas></div></article>
        <article class="dashboard-chart-panel"><div class="dashboard-chart-heading">Số người bán theo ${escapeHtml(periodLabel)}</div><div class="dashboard-chart-caption">COUNT DISTINCT seller · chỉ whole_product eligible</div><div class="dashboard-chart-wrap" id="dashboard-seller-chart-wrap"><canvas id="dashboard-seller-chart"></canvas></div></article>
      </div>
      <article class="dashboard-chart-panel dashboard-chart-panel--full">
        <div class="dashboard-chart-heading">Giá TB &amp; Số người bán theo ${escapeHtml(periodLabel)} — cột đôi (2 trục)</div>
        <div class="dashboard-chart-caption">Cột đậm = Giá TB (trục trái, USD) · cột nhạt = Số người bán (trục phải). Mỗi sản phẩm 1 cặp cột theo màu.</div>
        <div class="dashboard-chart-wrap dashboard-chart-wrap--full" id="dashboard-combo-chart-wrap"><canvas id="dashboard-combo-chart"></canvas></div>
      </article>
    </section>
    <section class="dashboard-panel dashboard-panel--analysis" id="dashboard-analysis-section" tabindex="-1">
      <div class="dashboard-panel-title">Phân tích theo Sản phẩm &amp; thời điểm</div>
      <div class="dashboard-panel-subtext">Drill-down từ market analytics xuống listing thật và classification reason.</div>
      <div class="dashboard-analysis-controls">
        <label class="dashboard-form-field dashboard-form-field--grow"><span>Sản phẩm</span><select id="dashboard-product-select">${products.map((key) => { const info = getDashboardProduct(analysis, key); return `<option value="${escapeHtml(key)}" ${key === selectedProduct ? 'selected' : ''}>${escapeHtml(info?.product_label || key)}</option>`; }).join('')}</select></label>
        <label class="dashboard-form-field dashboard-form-field--period"><span>Kỳ (${escapeHtml(periodLabel)})</span><select id="dashboard-period-select">${periods.map((period) => `<option value="${escapeHtml(period)}" ${period === selectedPeriod ? 'selected' : ''}>${escapeHtml(period)}</option>`).join('')}</select></label>
      </div>
      ${drillBody}
    </section>
  `;

  // ---- events ----
  const granularitySelect = document.getElementById('dashboard-granularity');
  if (granularitySelect) {
    granularitySelect.addEventListener('change', async () => {
      state.hqa.dashboard.granularity = granularitySelect.value || 'month';
      state.hqa.dashboard.selectedPeriod = '';
      await loadHqaDashboardData();
      renderHqaDashboard();
    });
  }

  dashboardView.querySelectorAll('[data-dashboard-export]').forEach((button) => {
    button.addEventListener('click', () => downloadDashboardCsv(button.dataset.dashboardExport || 'group_period'));
  });

  // Product picker (searchable multi-select driving BOTH charts)
  const psTrigger = document.getElementById('dashboard-ps-trigger');
  const psPop = document.getElementById('dashboard-ps-pop');
  if (psTrigger && psPop) {
    psPop.hidden = !state.hqa.dashboard.chartProductSelectorOpen;
    psTrigger.setAttribute('aria-expanded', String(!!state.hqa.dashboard.chartProductSelectorOpen));
    psTrigger.addEventListener('click', () => {
      state.hqa.dashboard.chartProductSelectorOpen = !state.hqa.dashboard.chartProductSelectorOpen;
      psPop.hidden = !state.hqa.dashboard.chartProductSelectorOpen;
      psTrigger.setAttribute('aria-expanded', String(state.hqa.dashboard.chartProductSelectorOpen));
    });
  }
  const psSearch = document.getElementById('dashboard-ps-search');
  if (psSearch) {
    psSearch.addEventListener('input', (event) => {
      state.hqa.dashboard.chartProductSearch = event.target.value;
      state.hqa.dashboard.chartProductVisible = DASHBOARD_CONFIG.productPageSize;
      refreshDashboardSelectorUI();
    });
  }
  const psLoadMore = document.getElementById('dashboard-ps-load-more');
  if (psLoadMore) {
    psLoadMore.addEventListener('click', () => {
      state.hqa.dashboard.chartProductVisible += DASHBOARD_CONFIG.productPageSize;
      refreshDashboardSelectorUI();
    });
  }
  const psClear = document.getElementById('dashboard-ps-clear');
  if (psClear) {
    psClear.addEventListener('click', () => {
      state.hqa.dashboard.chartProducts = [];
      state.hqa.dashboard.chartWarn = '';
      refreshDashboardSelectorUI();
      renderDashboardComparisonCharts();
    });
  }
  const psSelectLoaded = document.getElementById('dashboard-ps-select-loaded');
  if (psSelectLoaded) {
    psSelectLoaded.addEventListener('change', (event) => {
      const dashboard = state.hqa.dashboard;
      const max = DASHBOARD_CONFIG.productSeriesMax;
      const loaded = dashboardFilteredProducts().slice(0, dashboard.chartProductVisible);
      if (event.target.checked) {
        let hitLimit = false;
        for (const product of loaded) {
          if (dashboard.chartProducts.includes(product.product_key)) continue;
          if (dashboard.chartProducts.length >= max) { hitLimit = true; break; }
          dashboard.chartProducts = [...dashboard.chartProducts, product.product_key];
        }
        dashboard.chartWarn = hitLimit ? `Chỉ có thể hiển thị tối đa ${max} sản phẩm cùng lúc để biểu đồ dễ đọc.` : '';
      } else {
        const remove = new Set(loaded.map((product) => product.product_key));
        dashboard.chartProducts = dashboard.chartProducts.filter((key) => !remove.has(key));
        dashboard.chartWarn = '';
      }
      refreshDashboardSelectorUI();
      renderDashboardComparisonCharts();
    });
  }
  const psList = document.getElementById('dashboard-ps-list');
  if (psList) {
    psList.addEventListener('change', (event) => {
      const checkbox = event.target.closest('input[data-dashboard-ps-id]');
      if (!checkbox) return;
      toggleDashboardProduct(checkbox.getAttribute('data-dashboard-ps-id'), checkbox);
    });
  }

  // Drill-down selectors
  const productSelect = document.getElementById('dashboard-product-select');
  if (productSelect) {
    productSelect.addEventListener('change', () => {
      state.hqa.dashboard.selectedProduct = productSelect.value;
      state.hqa.dashboard.roleFilter = 'all';
      const availablePeriods = (analysis.group_periods || []).filter((item) => item.group === productSelect.value).map((item) => item.period);
      if (!availablePeriods.includes(state.hqa.dashboard.selectedPeriod)) {
        state.hqa.dashboard.selectedPeriod = availablePeriods[availablePeriods.length - 1] || analysis.latest_period?.period || '';
      }
      renderHqaDashboard();
    });
  }
  const periodSelect = document.getElementById('dashboard-period-select');
  if (periodSelect) {
    periodSelect.addEventListener('change', () => {
      state.hqa.dashboard.selectedPeriod = periodSelect.value;
      renderHqaDashboard();
    });
  }

  // Alert cards -> select product + period, re-render, scroll + flash + focus
  dashboardView.querySelectorAll('[data-dashboard-alert-product]').forEach((card) => {
    card.addEventListener('click', () => {
      const productKey = card.getAttribute('data-dashboard-alert-product');
      const period = card.getAttribute('data-dashboard-alert-period');
      if (productKey) state.hqa.dashboard.selectedProduct = productKey;
      if (period) state.hqa.dashboard.selectedPeriod = period;
      state.hqa.dashboard.roleFilter = 'all';
      renderHqaDashboard();
      requestAnimationFrame(() => {
        const section = document.getElementById('dashboard-analysis-section');
        if (!section) return;
        section.classList.remove('dashboard-analysis-flash');
        void section.offsetWidth;
        section.classList.add('dashboard-analysis-flash');
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        try { section.focus({ preventScroll: true }); } catch (error) { section.focus(); }
      });
    });
  });

  bindDashboardRoleCards();
  ensureDashboardGlobalListeners();
  refreshDashboardSelectorUI();
  renderDashboardComparisonCharts();
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
  input.focus();
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
    renderDataCheckModal();
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
  if (filters.priceSort === 'price_asc') {
    params.set('sort_by', 'price');
    params.set('sort_order', 'asc');
  } else if (filters.priceSort === 'price_desc') {
    params.set('sort_by', 'price');
    params.set('sort_order', 'desc');
  }
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
    ${metric('Total records stored', allSummary.total_records_stored || 0, `Unique listing IDs: ${allSummary.unique_listing_ids || 0}`, 'metric-card--summary metric-card--total', true)}
    ${metric('Filtered records', allSummary.filtered_records || 0, '', 'metric-card--summary metric-card--filtered', true)}
    ${metric('Active', allSummary.active || 0, '', 'metric-card--summary metric-card--active', true)}
    ${renderEndedOutOfStockSummaryCard(allSummary.ended || 0, allSummary.out_of_stock || 0)}
    ${metric('Accessories', allSummary.accessories || 0, '', 'metric-card--summary metric-card--accessories', true)}`;
}

function renderEndedOutOfStockSummaryCard(ended, outOfStock) {
  return `<article class="metric-card metric-card--summary metric-card--status-combined" aria-label="Ended and out-of-stock summary">
    <span class="metric-card__label">Ended / Out of stock</span>
    <div class="metric-card__split" role="group" aria-label="Ended and out-of-stock counts">
      <div class="metric-card__split-item metric-card__split-item--ended">
        <strong class="metric-card__value">${formatMetricValue(ended)}</strong>
        <small class="metric-card__detail">Ended</small>
      </div>
      <div class="metric-card__split-item metric-card__split-item--out">
        <strong class="metric-card__value">${formatMetricValue(outOfStock)}</strong>
        <small class="metric-card__detail">Out of stock</small>
      </div>
    </div>
  </article>`;
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
    priceSort: 'default',
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
    priceSort: document.getElementById('sort-price')?.value || 'default',
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

  filterContainer.addEventListener('change', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const selectAll = target.closest('[data-option-select-all]');
    if (selectAll && selectAll instanceof HTMLInputElement) {
      const apiField = selectAll.getAttribute('data-option-select-all') || '';
      setAllLoadedLazyOptions(apiField, Boolean(selectAll.checked));
      return;
    }

    if (!['from-date', 'to-date', 'marketplace', 'brand', 'sort-collected', 'sort-price'].includes(target.id)) return;

    const before = cloneAllListingsFilters(state.hqa.allListings.draftFilters);
    const next = snapshotAllListingsFiltersFromDom();
    if (target.id === 'brand' && before.brand !== next.brand) {
      next.model = '';
      resetLazyOptionField('model', { clearCache: true });
    }
    state.hqa.allListings.draftFilters = cloneAllListingsFilters(next);

    if (target.id === 'sort-price') {
      state.hqa.allListings.appliedFilters = cloneAllListingsFilters(next);
      state.hqa.page = 1;
      clearAllListingsNotification();
      await loadAllListingsSummary();
      renderHqaSummary();
      await loadActiveListings();
      renderHqaFilterOptions();
      return;
    }

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
      <label class="filter-field filter-field--price"><span class="filter-field__label">Sort by Price</span><select id="sort-price" aria-label="Sort by price"><option value="default" ${filters.priceSort === 'default' ? 'selected' : ''}>Default</option><option value="price_asc" ${filters.priceSort === 'price_asc' ? 'selected' : ''}>Price: Low to High</option><option value="price_desc" ${filters.priceSort === 'price_desc' ? 'selected' : ''}>Price: High to Low</option></select></label>
      <label class="filter-field filter-field--search"><span class="filter-field__label">Search</span><input id="search" placeholder="Search listing title, listing ID, seller" value="${escapeHtml(filters.search)}"></label>
      <div class="filter-actions">
        <button class="hvr-float-shadow" type="submit">Apply filters</button>
        <button class="hvr-float-shadow" id="reset-filters" type="button" data-table-interaction="true">Reset filters</button>
        <button class="hvr-float-shadow" id="refresh-inline" type="button" data-table-interaction="true">Refresh data</button>
        <button class="hvr-float-shadow" id="export-all-listings" type="button" data-table-interaction="true" ${state.hqa.allListings.isExporting ? 'disabled' : ''}>${state.hqa.allListings.isExporting ? 'Dang xuat...' : 'Export CSV'}</button>
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
        <div class="brand-mark"> <img src="/assets/login-logo.svg" alt="TOM Login" class="login-logo-image"></div>
        <h1>Hệ thống</h1>
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
  return `<button data-module="${code}" class="${state.currentModule === code ? 'active' : ''}"><span>${label}</span></button>`;
}

function renderShell() {
  if (!hasModule(state.currentModule) && state.currentModule !== 'SYSTEM') {
    state.currentModule = state.modules[0]?.code || (state.user.system_role === 'superadmin' ? 'HQA' : 'NONE');
  }
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="logo">
        <img src="/assets/logo.svg" alt="TOM Logo" class="logo-image">
        </div>
        <nav>
          ${sidebarButton('HQA', 'HQA')}
          ${sidebarButton('HQS', 'HQS')}
          ${sidebarButton('SYSTEM', 'System')}
        </nav>
        <div class="sidebar-user">
          <strong>${escapeHtml(state.user.full_name)}</strong>
          <span>${escapeHtml(state.user.system_role || state.modules.map((m) => `${m.code}:${m.role}`).join(', '))}</span>
          <button id="logout"><span>Sign out </span></button>
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

function metric(label, value, detail = '', className = '', reserveDetailSpace = false) {
  const normalizedClassName = String(className || '').trim();
  const classes = ['metric-card'];
  if (normalizedClassName) classes.push(normalizedClassName);
  const detailMarkup = detail
    ? `<small class="metric-card__detail">${escapeHtml(detail)}</small>`
    : (reserveDetailSpace ? '<small class="metric-card__detail metric-card__detail--empty" aria-hidden="true">&nbsp;</small>' : '');
  return `<article class="${classes.join(' ')}"><span class="metric-card__label">${escapeHtml(label)}</span><strong class="metric-card__value">${formatMetricValue(value)}</strong>${detailMarkup}</article>`;
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
          <button type="button" data-page-action="first" ${pagination.hasPrevious ? '' : 'disabled'}>First</button>
          <button type="button" data-page-action="prev" ${pagination.hasPrevious ? '' : 'disabled'}>Previous</button>
          ${pageItems.map((item) => item === '...'
            ? '<span class="page-ellipsis" aria-hidden="true">...</span>'
            : `<button type="button" class="page-btn ${item === pagination.page ? 'active' : ''}" data-page-action="page" data-page="${item}" aria-label="Page ${item}" aria-current="${item === pagination.page ? 'page' : 'false'}">${item}</button>`).join('')}
          <button type="button" data-page-action="next" ${pagination.hasNext ? '' : 'disabled'}>Next</button>
          <button type="button" data-page-action="last" ${pagination.hasNext ? '' : 'disabled'}>Last</button>
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
    syncDashboardFiltersFromAllListings();
    if (reloadData || !state.hqa.dashboard.analysis) {
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
        syncDashboardFiltersFromAllListings();
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

  const paginationContainer = document.getElementById('hqa-pagination');
  if (paginationContainer && !paginationContainer.dataset.paginationBound) {
    paginationContainer.dataset.paginationBound = 'true';
    paginationContainer.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-page-action]');
      if (!button || button.disabled) return;

      const action = button.dataset.pageAction;
      const paginationPayload = state.hqa.rawListings;
      const totalPages = Math.max(1, Math.ceil((Number(paginationPayload?.total || state.hqa.total || 0)) / Math.max(1, Number(state.hqa.pageSize || 50))));

      if (action === 'first') {
        if (state.hqa.page !== 1) {
          state.hqa.page = 1;
          await loadActiveListings({ scrollToTable: true });
        }
        return;
      }

      if (action === 'prev') {
        if (state.hqa.page > 1) {
          state.hqa.page -= 1;
          await loadActiveListings({ scrollToTable: true });
        }
        return;
      }

      if (action === 'next') {
        if (state.hqa.page < totalPages) {
          state.hqa.page += 1;
          await loadActiveListings({ scrollToTable: true });
        }
        return;
      }

      if (action === 'last') {
        if (state.hqa.page !== totalPages) {
          state.hqa.page = totalPages;
          await loadActiveListings({ scrollToTable: true });
        }
        return;
      }

      if (action === 'page') {
        const nextPage = Number(button.dataset.page);
        if (Number.isFinite(nextPage) && nextPage >= 1 && nextPage !== state.hqa.page) {
          state.hqa.page = nextPage;
          await loadActiveListings({ scrollToTable: true });
        }
      }
    });
  }

  const pageSize = document.getElementById('page-size');
  if (pageSize && !pageSize.dataset.bound) {
    pageSize.dataset.bound = 'true';
    pageSize.addEventListener('change', async (event) => {
      state.hqa.pageSize = Number(event.target.value || 50);
      state.hqa.page = 1;
      await loadActiveListings();
    });
  }

  const retryReport = document.getElementById('retry-report');
  if (retryReport && !retryReport.dataset.bound) {
    retryReport.dataset.bound = 'true';
    retryReport.addEventListener('click', async () => {
      await loadActiveListings();
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

if (typeof window !== 'undefined') {
  window.__hqaState = state;
}

bootstrap();
