const state = {
  accessToken: null,
  user: null,
  modules: [],
  currentModule: 'HQA',
  hqa: {
    activeReport: 'all_listings',
    page: 1,
    pageSize: 30,
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
    appliedFilters: {
      report_date: getHcmDateString(),
      q: '',
      marketplace: '',
      brand: '',
      model: '',
      category: '',
      listing_location: '',
      category_name: '',
      seller: '',
      condition: '',
      buying_options: '',
      listing_status: '',
      price_min: '',
      price_max: '',
      sort: 'collected_at_desc',
    },
    draftFilters: {
      report_date: getHcmDateString(),
      q: '',
      marketplace: '',
      brand: '',
      model: '',
      category: '',
      listing_location: '',
      category_name: '',
      seller: '',
      condition: '',
      buying_options: '',
      listing_status: '',
      price_min: '',
      price_max: '',
      sort: 'collected_at_desc',
    },
  },
};

const HQA_REPORTS = [
  { key: 'main_repeated', tableNumber: 1, label: 'Main / Repeated' },
  { key: 'amplifier_receiver', tableNumber: 2, label: 'Amplifiers / Receivers' },
  { key: 'speaker_parts', tableNumber: 3, label: 'Speakers / Parts' },
  { key: 'other_home_audio', tableNumber: 4, label: 'Other Home Audio' },
  { key: 'vintage_accessories', tableNumber: 5, label: 'Vintage / Accessories' },
  { key: 'non_audio_irrelevant', tableNumber: 6, label: 'Non Audio / Irrelevant' },
  { key: 'ended', tableNumber: 7, label: 'Ended' },
  { key: 'out_of_stock', tableNumber: 8, label: 'Out of Stock' },
];

const HQA_REPORT_OPTIONS = [
  { key: 'all_listings', label: 'All listings' },
  ...HQA_REPORTS.map((item) => ({
    key: item.key,
    label: item.key === 'ended' || item.key === 'out_of_stock'
      ? `Table ${item.tableNumber} - ${item.label}`
      : `Table ${item.tableNumber}`,
  })),
];

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

function metric(label, value) {
  return `<article class="metric-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function formatPrice(price, currency) {
  if (price == null) return '-';
  return `${Number(price).toLocaleString()} ${escapeHtml(currency || '')}`.trim();
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

function toApiDate(value) {
  return value || getHcmDateString();
}

function buildPagination(totalPages, currentPage) {
  const pages = [];
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);
  for (let number = start; number <= end; number += 1) pages.push(number);
  return pages;
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
  const openAction = item.listing_url
    ? `<a href="${escapeHtml(item.listing_url)}" target="_blank" rel="noopener noreferrer" class="link-action">Open</a>`
    : '<span class="link-action disabled">N/A</span>';

  const categoryCell = mode === 'raw'
    ? `<td>${escapeHtml(item.category || '-')}</td><td>${escapeHtml(item.category_name || '-')}</td>`
    : `<td><div><strong>${escapeHtml(item.category || '-')}</strong><small>${escapeHtml(item.category_name || '-')}</small></div></td>`;

  const quantityCell = mode === 'raw' ? `<td>${escapeHtml(item.quantity ?? '-')}</td>` : '';

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
    ${quantityCell}
    <td><span class="status-pill ${statusClass(normalizedStatus.key)}">${escapeHtml(normalizedStatus.label)}</span></td>
    <td>${escapeHtml(item.research_date || '-')}</td>
    <td>${openAction}</td>
  </tr>`;
}

function listingTable(payload, options = {}) {
  const { mode = 'report', showPagination = true } = options;
  if (!payload) return '<div class="center-inline">Loading report...</div>';
  if (payload.error) {
    return `<div class="error">${escapeHtml(payload.error)} <button id="retry-report" type="button">Retry</button></div>`;
  }
  if (!payload.items.length) {
    return mode === 'raw'
      ? '<div class="empty-state">Không có listing trong ngày được chọn.</div>'
      : '<div class="empty-state">Không có listing phù hợp với điều kiện của báo cáo.</div>';
  }
  const pages = buildPagination(payload.total_pages, payload.page);
  const pagination = showPagination ? `
    <div class="pagination report-pagination">
      <button id="page-prev" ${payload.page <= 1 ? 'disabled' : ''}>Previous</button>
      ${pages.map((page) => `<button class="page-btn ${page === payload.page ? 'active' : ''}" data-page="${page}">${page}</button>`).join('')}
      <button id="page-next" ${payload.page >= payload.total_pages ? 'disabled' : ''}>Next</button>
      <span class="page-meta">${payload.total} records</span>
    </div>` : `<div class="page-meta">${payload.total} records</div>`;
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            ${mode === 'raw'
              ? '<th>Image</th><th>Marketplace</th><th>Listing</th><th>Category</th><th>Category name</th><th>Seller / Shop</th><th>Condition</th><th>Price</th><th>Quantity</th><th>Status</th><th>Research date</th><th>Action</th>'
              : '<th>Image</th><th>Marketplace</th><th>Listing</th><th>Category</th><th>Seller / Shop</th><th>Condition</th><th>Price</th><th>Status</th><th>Research date</th><th>Action</th>'}
          </tr>
        </thead>
        <tbody>${payload.items.map((item) => listingRow(item, mode)).join('')}</tbody>
      </table>
    </div>
    ${pagination}`;
}

function tabsView(summary, activeReport) {
  const groups = summary?.groups || [];
  const groupMap = Object.fromEntries(groups.map((group) => [group.key, group]));
  return `
    <div class="report-tabs">
      <button data-report-tab="all_listings" class="${activeReport === 'all_listings' ? 'active' : ''}">All listings <span>${summary?.total_listings_on_date || 0}</span></button>
      ${HQA_REPORTS.map((item) => {
        const group = groupMap[item.key] || {};
        const badge = group.keyword_filter_enabled
          ? '<small class="keyword-badge enabled" title="Keyword duoc lay tu tab HQa-List keyword trong bo du lieu HQA.">Keyword filter enabled</small>'
          : (item.key === 'non_audio_irrelevant'
            ? '<small class="keyword-badge not-configured" title="Keyword duoc lay tu tab HQa-List keyword trong bo du lieu HQA.">Keyword filter not configured</small>'
            : '<small class="keyword-badge not-required" title="Keyword duoc lay tu tab HQa-List keyword trong bo du lieu HQA.">Keyword not required</small>');
        return `<button data-report-tab="${item.key}" class="${activeReport === item.key ? 'active' : ''}">T${item.tableNumber} ${escapeHtml(item.label)} <span>${group.count || 0}</span>${badge}</button>`;
      }).join('')}
    </div>`;
}

function getHqaFilterScope() {
  if (state.hqa.activeReport === 'all_listings') {
    return { view: 'all_listings', report_key: '' };
  }
  return { view: 'report', report_key: state.hqa.activeReport };
}

function buildFilterOptionSelect(fieldKey, allLabel, responseKey) {
  const selected = state.hqa.draftFilters[fieldKey] || '';
  const disabled = state.hqa.loadingFilterOptions;
  const options = state.hqa.filterOptions[responseKey]?.items || [];
  const available = new Set(options.map((item) => item.value));
  const showFallback = selected && !available.has(selected);
  const loadingOption = disabled ? '<option value="">Loading...</option>' : '';
  const fallbackOption = showFallback ? `<option value="${escapeHtml(selected)}" selected>${escapeHtml(selected)} (unavailable)</option>` : '';

  return `
    <select id="${fieldKey}" aria-label="${allLabel}" ${disabled ? 'disabled' : ''}>
      <option value="" ${selected === '' ? 'selected' : ''}>${escapeHtml(allLabel)}</option>
      ${loadingOption}
      ${fallbackOption}
      ${options.map((item) => `<option value="${escapeHtml(item.value)}" ${item.value === selected ? 'selected' : ''}>${escapeHtml(item.label)} (${item.count})</option>`).join('')}
    </select>`;
}

function buildFilterOptionsParams() {
  const scope = getHqaFilterScope();
  const filters = state.hqa.draftFilters;
  const params = new URLSearchParams({
    report_date: toApiDate(filters.report_date),
    view: scope.view,
  });
  if (scope.report_key) params.set('report_key', scope.report_key);
  [
    'q',
    'marketplace',
    'brand',
    'model',
    'category',
    'listing_location',
    'condition',
    'category_name',
    'buying_options',
    'listing_status',
    'seller',
    'price_min',
    'price_max',
  ].forEach((key) => {
    if (filters[key]) params.set(key, filters[key]);
  });
  return params;
}

function sanitizeDraftFiltersByOptions() {
  const mapping = {
    brand: 'brands',
    model: 'models',
    category: 'categories',
    listing_location: 'listing_locations',
    condition: 'conditions',
    category_name: 'category_names',
    buying_options: 'buying_options',
  };
  Object.entries(mapping).forEach(([filterKey, responseKey]) => {
    const value = state.hqa.draftFilters[filterKey];
    if (!value) return;
    const items = state.hqa.filterOptions[responseKey]?.items || [];
    const hasValue = items.some((item) => item.value === value);
    if (!hasValue) state.hqa.draftFilters[filterKey] = '';
  });
}

async function loadHqaFilterOptions() {
  const requestId = state.hqa.filterOptionsRequestId + 1;
  state.hqa.filterOptionsRequestId = requestId;
  state.hqa.loadingFilterOptions = true;
  state.hqa.filterOptionsError = '';
  const params = buildFilterOptionsParams();
  try {
    const payload = await api(`/hqa/reports/marketplace/filter-options?${params.toString()}`);
    if (requestId !== state.hqa.filterOptionsRequestId) return;
    state.hqa.filterOptions = payload.options || state.hqa.filterOptions;
    sanitizeDraftFiltersByOptions();
  } catch (reason) {
    if (requestId !== state.hqa.filterOptionsRequestId) return;
    state.hqa.filterOptionsError = reason.message;
    state.hqa.filterOptions = {
      brands: { items: [], truncated: false },
      models: { items: [], truncated: false },
      categories: { items: [], truncated: false },
      listing_locations: { items: [], truncated: false },
      conditions: { items: [], truncated: false },
      category_names: { items: [], truncated: false },
      buying_options: { items: [], truncated: false },
    };
  } finally {
    if (requestId === state.hqa.filterOptionsRequestId) {
      state.hqa.loadingFilterOptions = false;
    }
  }
}

async function loadHqaSummary() {
  const reportDate = toApiDate(state.hqa.appliedFilters.report_date);
  const params = new URLSearchParams({ report_date: reportDate });
  [
    'marketplace',
    'q',
    'brand',
    'model',
    'category',
    'listing_location',
    'condition',
    'category_name',
    'buying_options',
    'listing_status',
    'seller',
    'price_min',
    'price_max',
  ].forEach((key) => {
    if (state.hqa.appliedFilters[key]) params.set(key, state.hqa.appliedFilters[key]);
  });
  state.hqa.loadingSummary = true;
  state.hqa.error = '';
  try {
    state.hqa.summary = await api(`/hqa/reports/marketplace/summary?${params.toString()}`);
  } catch (reason) {
    state.hqa.error = reason.message;
  } finally {
    state.hqa.loadingSummary = false;
  }
}

function buildListingParams(reportKey, page = 1) {
  const filters = state.hqa.appliedFilters;
  const params = new URLSearchParams({
    report_key: reportKey,
    page: String(page),
    page_size: String(state.hqa.pageSize),
    sort: 'price_desc',
  });
  if (!['ended', 'out_of_stock'].includes(reportKey)) {
    params.set('report_date', toApiDate(filters.report_date));
  } else {
    if (filters.report_date) {
      params.set('date_from', filters.report_date);
      params.set('date_to', filters.report_date);
    }
  }
  ['q', 'marketplace', 'brand', 'model', 'category', 'listing_location', 'category_name', 'seller', 'condition', 'buying_options', 'listing_status', 'price_min', 'price_max'].forEach((key) => {
    if (filters[key]) params.set(key, filters[key]);
  });
  return params;
}

function buildRawListingParams(page = 1) {
  const filters = state.hqa.appliedFilters;
  const params = new URLSearchParams({
    report_date: toApiDate(filters.report_date),
    page: String(page),
    page_size: String(state.hqa.pageSize),
    sort: filters.sort || 'collected_at_desc',
  });
  ['q', 'marketplace', 'brand', 'model', 'category', 'listing_location', 'category_name', 'seller', 'condition', 'buying_options', 'listing_status', 'price_min', 'price_max'].forEach((key) => {
    if (filters[key]) params.set(key, filters[key]);
  });
  return params;
}

async function loadReportListing(reportKey, page = 1) {
  const params = buildListingParams(reportKey, page);
  state.hqa.loadingListings = true;
  try {
    const payload = await api(`/hqa/reports/marketplace/listings?${params.toString()}`);
    state.hqa.listingsByReport[reportKey] = payload;
    state.hqa.page = payload.page;
  } catch (reason) {
    state.hqa.listingsByReport[reportKey] = { items: [], total: 0, page, page_size: state.hqa.pageSize, total_pages: 0, error: reason.message };
  } finally {
    state.hqa.loadingListings = false;
  }
}

async function loadRawListing(page = 1) {
  const params = buildRawListingParams(page);
  state.hqa.loadingListings = true;
  try {
    const payload = await api(`/hqa/reports/marketplace/raw-listings?${params.toString()}`);
    state.hqa.rawListings = payload;
    state.hqa.page = payload.page;
  } catch (reason) {
    state.hqa.rawListings = { items: [], total: 0, page, page_size: state.hqa.pageSize, total_pages: 0, error: reason.message };
  } finally {
    state.hqa.loadingListings = false;
  }
}

async function loadVisibleHqaListings() {
  if (state.hqa.activeReport === 'all_listings') {
    await loadRawListing(state.hqa.page);
    return;
  }
  await loadReportListing(state.hqa.activeReport, state.hqa.page);
}

async function renderHqa(content, options = {}) {
  const { reloadData = true } = options;
  content.innerHTML = '<div class="center-inline">Loading HQA reports...</div>';
  if (!state.hqa.draftFilters.report_date) {
    state.hqa.draftFilters.report_date = getHcmDateString();
  }
  if (!state.hqa.appliedFilters.report_date) {
    state.hqa.appliedFilters.report_date = state.hqa.draftFilters.report_date;
  }
  await loadHqaFilterOptions();
  if (reloadData) {
    await loadHqaSummary();
    await loadVisibleHqaListings();
  }

  const summary = state.hqa.summary;
  const counts = Object.fromEntries((summary?.groups || []).map((group) => [group.key, group.count]));
  const reportMeta = Object.fromEntries((summary?.groups || []).map((group) => [group.key, group]));
  const currentPayload = state.hqa.activeReport === 'all_listings'
    ? state.hqa.rawListings
    : state.hqa.listingsByReport[state.hqa.activeReport];
  const selectedOption = state.hqa.activeReport;

  content.innerHTML = `
    <section class="hqa-reports-screen">
      <div class="page-heading">
        <div>
          <span class="eyebrow">Module</span>
          <h1>HQA Marketplace Reports</h1>
          <p>Raw listings theo ngay va 8 bang bao cao loc chuyen biet.</p>
        </div>
        <button id="refresh-data" type="button">Refresh data</button>
      </div>
      ${state.hqa.error ? `<div class="error">${escapeHtml(state.hqa.error)}</div>` : ''}
      <div class="metrics">
        ${metric('Total listings on selected date', summary?.total_listings_on_date || 0)}
        ${metric('New listings qualified', summary?.total_new_today || 0)}
        ${metric('Ended listings', summary?.total_ended || 0)}
        ${metric('Out of stock', summary?.total_out_of_stock || 0)}
      </div>
      <div class="panel">
        <form class="filters hqa-filter-grid" id="hqa-filters">
          <input id="report-date" type="date" value="${escapeHtml(state.hqa.draftFilters.report_date)}" aria-label="Report date">
          <select id="report-selector" aria-label="Report selector">
            ${HQA_REPORT_OPTIONS.map((option) => `<option value="${option.key}" ${option.key === selectedOption ? 'selected' : ''}>${escapeHtml(option.label)}</option>`).join('')}
          </select>
          <select id="marketplace" aria-label="Marketplace">
            <option value="">All marketplaces</option>
            <option value="ebay" ${state.hqa.draftFilters.marketplace === 'ebay' ? 'selected' : ''}>eBay</option>
            <option value="reverb" ${state.hqa.draftFilters.marketplace === 'reverb' ? 'selected' : ''}>Reverb</option>
            <option value="etsy" ${state.hqa.draftFilters.marketplace === 'etsy' ? 'selected' : ''}>Etsy</option>
          </select>
          <input id="query" placeholder="Search title, listing ID, seller" value="${escapeHtml(state.hqa.draftFilters.q)}">
          ${buildFilterOptionSelect('brand', 'All brands', 'brands')}
          ${buildFilterOptionSelect('model', 'All models', 'models')}
          ${buildFilterOptionSelect('category', 'All categories', 'categories')}
          ${buildFilterOptionSelect('listing_location', 'All locations', 'listing_locations')}
          ${buildFilterOptionSelect('condition', 'All conditions', 'conditions')}
          ${buildFilterOptionSelect('category_name', 'All category names', 'category_names')}
          ${buildFilterOptionSelect('buying_options', 'All buying options', 'buying_options')}
          <input id="seller" placeholder="Seller / Shop" value="${escapeHtml(state.hqa.draftFilters.seller)}">
          <select id="listing-status" aria-label="Listing status">
            <option value="" ${state.hqa.draftFilters.listing_status === '' ? 'selected' : ''}>All statuses</option>
            <option value="active" ${state.hqa.draftFilters.listing_status === 'active' ? 'selected' : ''}>ACTIVE</option>
            <option value="ended" ${state.hqa.draftFilters.listing_status === 'ended' ? 'selected' : ''}>ENDED</option>
            <option value="new_listing" ${state.hqa.draftFilters.listing_status === 'new_listing' ? 'selected' : ''}>NEW_LISTING</option>
            <option value="out_of_stock" ${state.hqa.draftFilters.listing_status === 'out_of_stock' ? 'selected' : ''}>OUT_OF_STOCK</option>
            <option value="unknown" ${state.hqa.draftFilters.listing_status === 'unknown' ? 'selected' : ''}>UNKNOWN</option>
          </select>
          <select id="sort" aria-label="Sort">
            <option value="collected_at_desc" ${state.hqa.draftFilters.sort === 'collected_at_desc' ? 'selected' : ''}>Newest collected</option>
            <option value="price_desc" ${state.hqa.draftFilters.sort === 'price_desc' ? 'selected' : ''}>Price high to low</option>
            <option value="price_asc" ${state.hqa.draftFilters.sort === 'price_asc' ? 'selected' : ''}>Price low to high</option>
            <option value="title_asc" ${state.hqa.draftFilters.sort === 'title_asc' ? 'selected' : ''}>Listing title A-Z</option>
          </select>
          <input id="price-min" type="number" min="0" step="0.01" placeholder="Minimum price" value="${escapeHtml(state.hqa.draftFilters.price_min)}">
          <input id="price-max" type="number" min="0" step="0.01" placeholder="Maximum price" value="${escapeHtml(state.hqa.draftFilters.price_max)}">
          <div class="filter-actions">
            <button type="submit">Apply filters</button>
            <button id="reset-filters" type="button">Reset filters</button>
            <button id="refresh-inline" type="button">Refresh data</button>
          </div>
        </form>
        ${state.hqa.filterOptionsError ? `<div class="error">Khong the tai danh sach filter options. ${escapeHtml(state.hqa.filterOptionsError)}</div>` : ''}
      </div>
      <div class="panel">
        ${tabsView(summary, state.hqa.activeReport)}
      </div>
      <div class="panel">
        ${state.hqa.loadingListings ? '<div class="center-inline">Loading listings...</div>' : ''}
        ${state.hqa.activeReport === 'all_listings'
          ? `<section class="report-section"><div class="section-header"><h2>All listings</h2><span>${summary?.total_listings_on_date || 0} records</span></div>${listingTable(currentPayload, { mode: 'raw', showPagination: true })}</section>`
          : (() => {
            const activeMeta = reportMeta[state.hqa.activeReport] || {};
            const activeReport = HQA_REPORTS.find((report) => report.key === state.hqa.activeReport);
            const heading = activeReport ? `Table ${activeReport.tableNumber} - ${activeReport.label}` : state.hqa.activeReport;
            const badge = activeMeta.keyword_filter_enabled
              ? '<small class="keyword-badge enabled">Keyword filter enabled</small>'
              : (state.hqa.activeReport === 'non_audio_irrelevant'
                ? '<small class="keyword-badge not-configured">Keyword filter not configured</small>'
                : '<small class="keyword-badge not-required">Keyword not required</small>');
            return `<section class="report-section"><div class="section-header"><h2>${escapeHtml(heading)}</h2><span>${counts[state.hqa.activeReport] || 0} records</span>${badge}</div>${listingTable(currentPayload, { mode: 'report', showPagination: true })}</section>`;
          })()
        }
      </div>
    </section>`;

  document.getElementById('refresh-data').addEventListener('click', async () => {
    state.hqa.draftFilters = { ...state.hqa.appliedFilters };
    await renderHqa(content);
  });
  document.getElementById('refresh-inline').addEventListener('click', async () => {
    state.hqa.draftFilters = { ...state.hqa.appliedFilters };
    await renderHqa(content);
  });
  document.getElementById('report-selector').addEventListener('change', async (event) => {
    state.hqa.activeReport = event.target.value;
    state.hqa.draftFilters.report_date = document.getElementById('report-date').value || state.hqa.draftFilters.report_date;
    state.hqa.page = 1;
    await renderHqa(content);
  });
  document.querySelectorAll('[data-report-tab]').forEach((button) => button.addEventListener('click', async () => {
    state.hqa.activeReport = button.dataset.reportTab;
    state.hqa.draftFilters.report_date = document.getElementById('report-date').value || state.hqa.draftFilters.report_date;
    state.hqa.page = 1;
    await renderHqa(content);
  }));

  const debounceOptionRefresh = (() => {
    let timer = null;
    return () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(async () => {
        state.hqa.draftFilters = {
          ...state.hqa.draftFilters,
          report_date: document.getElementById('report-date').value || getHcmDateString(),
          q: document.getElementById('query').value.trim(),
          marketplace: document.getElementById('marketplace').value,
          brand: document.getElementById('brand').value,
          model: document.getElementById('model').value,
          category: document.getElementById('category').value,
          listing_location: document.getElementById('listing_location').value,
          category_name: document.getElementById('category_name').value,
          seller: document.getElementById('seller').value.trim(),
          condition: document.getElementById('condition').value,
          buying_options: document.getElementById('buying_options').value,
          listing_status: document.getElementById('listing-status').value.trim(),
          price_min: document.getElementById('price-min').value,
          price_max: document.getElementById('price-max').value,
          sort: document.getElementById('sort').value,
        };
        await renderHqa(content, { reloadData: false });
      }, 250);
    };
  })();

  ['report-date', 'marketplace', 'brand', 'model', 'category', 'listing_location', 'category_name', 'condition', 'buying_options', 'listing-status'].forEach((id) => {
    document.getElementById(id)?.addEventListener('change', debounceOptionRefresh);
  });

  document.getElementById('hqa-filters').addEventListener('submit', async (event) => {
    event.preventDefault();
    state.hqa.draftFilters = {
      report_date: document.getElementById('report-date').value || getHcmDateString(),
      q: document.getElementById('query').value.trim(),
      marketplace: document.getElementById('marketplace').value,
      brand: document.getElementById('brand').value,
      model: document.getElementById('model').value,
      category: document.getElementById('category').value,
      listing_location: document.getElementById('listing_location').value,
      category_name: document.getElementById('category_name').value,
      seller: document.getElementById('seller').value.trim(),
      condition: document.getElementById('condition').value,
      buying_options: document.getElementById('buying_options').value,
      listing_status: document.getElementById('listing-status').value.trim(),
      price_min: document.getElementById('price-min').value,
      price_max: document.getElementById('price-max').value,
      sort: document.getElementById('sort').value,
    };
    state.hqa.appliedFilters = { ...state.hqa.draftFilters };
    state.hqa.activeReport = document.getElementById('report-selector').value;
    state.hqa.page = 1;
    await renderHqa(content);
  });

  document.getElementById('reset-filters').addEventListener('click', async () => {
    const resetFilters = {
      report_date: getHcmDateString(),
      q: '',
      marketplace: '',
      brand: '',
      model: '',
      category: '',
      listing_location: '',
      category_name: '',
      seller: '',
      condition: '',
      buying_options: '',
      listing_status: '',
      price_min: '',
      price_max: '',
      sort: 'collected_at_desc',
    };
    state.hqa.draftFilters = { ...resetFilters };
    state.hqa.appliedFilters = { ...resetFilters };
    state.hqa.activeReport = 'all_listings';
    state.hqa.page = 1;
    await renderHqa(content);
  });

  const paginationPayload = state.hqa.activeReport === 'all_listings'
    ? state.hqa.rawListings
    : state.hqa.listingsByReport[state.hqa.activeReport];
  if (paginationPayload) {
    document.getElementById('page-prev')?.addEventListener('click', async () => {
      state.hqa.page = Math.max(1, state.hqa.page - 1);
      await renderHqa(content);
    });
    document.getElementById('page-next')?.addEventListener('click', async () => {
      state.hqa.page = Math.min(paginationPayload.total_pages || 1, state.hqa.page + 1);
      await renderHqa(content);
    });
    document.querySelectorAll('.page-btn').forEach((button) => button.addEventListener('click', async () => {
      const page = Number(button.dataset.page);
      state.hqa.page = page;
      await renderHqa(content);
    }));
  }
  document.getElementById('retry-report')?.addEventListener('click', async () => {
    await renderHqa(content);
  });
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
