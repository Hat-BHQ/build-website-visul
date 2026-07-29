const state = {
  accessToken: null,
  user: null,
  modules: [],
  currentModule: 'HQA',
  page: 1,
  pages: 1,
  query: '',
  marketplace: '',
};

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
        <label>Email<input id="email" value="root@example.com" type="email" required></label>
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

async function renderHqa(content) {
  content.innerHTML = '<div class="center-inline">Loading HQA data...</div>';
  try {
    const params = new URLSearchParams({ page: state.page, page_size: 20 });
    if (state.query) params.set('q', state.query);
    if (state.marketplace) params.set('marketplace', state.marketplace);
    const [dashboard, listings, jobs] = await Promise.all([
      api('/hqa/dashboard'), api(`/hqa/listings?${params}`), api('/sync/jobs')
    ]);
    state.pages = listings.pages;
    content.innerHTML = `
      <section>
        <div class="page-heading">
          <div><span class="eyebrow">Module</span><h1>HQA Marketplace</h1></div>
          ${can('hqa.sync.run') ? '<button id="run-sync">Run eBay sync</button>' : ''}
        </div>
        <div class="metrics">
          ${metric('Active listings', dashboard.active_listings)}
          ${metric('Inactive listings', dashboard.inactive_listings)}
          ${metric('eBay', dashboard.by_marketplace.ebay || 0)}
          ${metric('Reverb', dashboard.by_marketplace.reverb || 0)}
        </div>
        <div class="panel">
          <form class="filters" id="filters">
            <input id="query" placeholder="Search title or listing ID" value="${escapeHtml(state.query)}">
            <select id="marketplace">
              <option value="">All marketplaces</option>
              <option value="ebay" ${state.marketplace === 'ebay' ? 'selected' : ''}>eBay</option>
              <option value="reverb" ${state.marketplace === 'reverb' ? 'selected' : ''}>Reverb</option>
              <option value="etsy" ${state.marketplace === 'etsy' ? 'selected' : ''}>Etsy</option>
            </select>
            <button>Search</button>
          </form>
          <div class="table-wrap"><table><thead><tr>
            <th>Marketplace</th><th>Listing</th><th>Seller / Shop</th><th>Price</th><th>Qty</th><th>Status</th>
          </tr></thead><tbody>${listings.items.map((item) => `
            <tr>
              <td><span class="chip">${escapeHtml(item.marketplace)}</span></td>
              <td><strong>${escapeHtml(item.listing_title)}</strong><small>${escapeHtml(item.external_listing_id)}</small></td>
              <td>${escapeHtml(item.seller_name || item.shop_name || 'N/A')}</td>
              <td>${item.current_price == null ? '-' : `${Number(item.current_price).toLocaleString()} ${escapeHtml(item.currency || '')}`}</td>
              <td>${escapeHtml(item.quantity ?? '-')}</td><td>${escapeHtml(item.listing_status)}</td>
            </tr>`).join('')}</tbody></table></div>
          <div class="pagination">
            <button id="previous" ${state.page <= 1 ? 'disabled' : ''}>Previous</button>
            <span>Page ${listings.page} / ${listings.pages}</span>
            <button id="next" ${state.page >= listings.pages ? 'disabled' : ''}>Next</button>
          </div>
        </div>
        <div class="panel"><h2>Recent sync jobs</h2>
          ${jobs.items.length === 0 ? '<p>No jobs yet.</p>' : `<div class="job-list">${jobs.items.slice(0, 8).map((job) => `
            <div><strong>${escapeHtml(job.marketplace)}</strong><span>${escapeHtml(job.status)}</span><span>${job.processed_items}/${job.total_items}</span></div>
          `).join('')}</div>`}
        </div>
      </section>`;
    document.getElementById('filters').addEventListener('submit', (event) => {
      event.preventDefault(); state.query = document.getElementById('query').value.trim();
      state.marketplace = document.getElementById('marketplace').value; state.page = 1; renderHqa(content);
    });
    document.getElementById('previous').addEventListener('click', () => { state.page -= 1; renderHqa(content); });
    document.getElementById('next').addEventListener('click', () => { state.page += 1; renderHqa(content); });
    document.getElementById('run-sync')?.addEventListener('click', async () => {
      await api('/sync/jobs', { method: 'POST', body: JSON.stringify({
        marketplace: 'ebay', sync_type: 'status', idempotency_key: `web-${Date.now()}`, item_ids: []
      }) });
      setTimeout(() => renderHqa(content), 800);
    });
  } catch (reason) {
    content.innerHTML = `<div class="error">${escapeHtml(reason.message)}</div>`;
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
