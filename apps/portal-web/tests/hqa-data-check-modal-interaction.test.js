const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { JSDOM } = require('jsdom');

function wait(ms = 0) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function flush(times = 3) {
  for (let i = 0; i < times; i += 1) {
    await wait(0);
  }
}

function createJsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return payload;
    },
    async text() {
      return JSON.stringify(payload);
    },
    headers: {
      get() {
        return 'application/json';
      },
    },
  };
}

(async () => {
  const html = '<!doctype html><html><body><div id="app"></div></body></html>';
  const dom = new JSDOM(html, {
    url: 'http://localhost/',
    pretendToBeVisual: true,
    runScripts: 'outside-only',
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

  let cleanupCallCount = 0;

  window.fetch = async (input, options = {}) => {
    const url = String(input || '');
    const method = String(options.method || 'GET').toUpperCase();

    if (url.endsWith('/api/v1/auth/session')) {
      return createJsonResponse({
        access_token: 'access-token',
        user: { full_name: 'Test User', system_role: 'superadmin' },
        modules: [{ code: 'HQA', permissions: ['*'] }],
      });
    }

    if (url.includes('/api/v1/hqa/listings/filter-options')) {
      if (url.includes('field=')) {
        return createJsonResponse({ items: [], page: 1, page_size: 30, has_more: false });
      }
      return createJsonResponse({
        marketplaces: ['ebay'],
        brands: ['Pioneer'],
        models: ['SX1080'],
        conditions: ['used'],
        statuses: ['active'],
        category_names: ['Vintage Speakers'],
        buying_options: ['FIXED_PRICE'],
      });
    }

    if (url.includes('/api/v1/hqa/listings/summary')) {
      return createJsonResponse({
        total_records_stored: 100,
        unique_listing_ids: 80,
        filtered_records: 20,
        active: 10,
        ended: 5,
        out_of_stock: 5,
      });
    }

    if (url.includes('/api/v1/hqa/listings?')) {
      return createJsonResponse({
        items: [],
        page: 1,
        page_size: 50,
        total: 0,
        total_pages: 0,
      });
    }

    if (url.includes('/api/v1/hqa/data-check/duplicates/summary')) {
      return createJsonResponse({
        total_records: 60616,
        unique_listing_keys: 10797,
        duplicate_groups: 1,
        duplicate_records: 3,
        records_to_delete: 2,
        missing_listing_id: 10,
      });
    }

    if (url.includes('/api/v1/hqa/data-check/duplicates?')) {
      return createJsonResponse({
        items: [
          {
            marketplace: 'ebay',
            listing_id: '398210152319',
            record_count: 3,
            keep_record: {
              id: 'KEEP-1',
              listing_title: 'Keep listing',
              listing_status: 'ended',
              quantity: 1,
              collected_at: '2026-08-06T10:00:00Z',
              updated_at: '2026-08-06T10:00:00Z',
              listing_published_at: '2026-08-05T10:00:00Z',
              last_status_checked_at: '2026-08-06T10:00:00Z',
            },
            delete_records: [
              { id: 'DEL-1', listing_title: 'Del 1', listing_status: 'active' },
              { id: 'DEL-2', listing_title: 'Del 2', listing_status: 'active' },
            ],
          },
        ],
        page: 1,
        page_size: 20,
        total_groups: 1,
      });
    }

    if (url.includes('/api/v1/hqa/data-check/duplicates/cleanup') && method === 'POST') {
      cleanupCallCount += 1;
      await wait(25);
      return createJsonResponse({
        duplicate_groups_processed: 1,
        records_deleted: 2,
        records_remaining: 60614,
      });
    }

    if (url.includes('/api/v1/auth/refresh')) {
      return createJsonResponse({}, 401);
    }

    return createJsonResponse({});
  };

  global.fetch = window.fetch;

  const appJsPath = path.join(__dirname, '..', 'assets', 'app.js');
  const source = fs.readFileSync(appJsPath, 'utf8');
  window.eval(source);

  await flush(8);

  const dataCheckTab = document.querySelector('[data-hqa-main-tab="data_check"]');
  assert(dataCheckTab, 'Data check tab must render');
  dataCheckTab.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(5);

  const runButton = document.getElementById('data-check-run');
  assert(runButton, 'Data check run button must exist');
  runButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(8);

  const cleanupButton = document.getElementById('data-check-cleanup');
  assert(cleanupButton, 'Cleanup button must exist after running data check');

  cleanupButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(3);

  let overlay = document.querySelector('.data-check-modal-backdrop');
  assert(overlay, 'Cleanup modal overlay must exist');
  let dialog = overlay.querySelector('.data-check-modal');
  let input = overlay.querySelector('#data-check-confirm-input');
  let cancelButton = overlay.querySelector('#data-check-cancel-button');
  let confirmButton = overlay.querySelector('#data-check-confirm-button');
  assert(input, 'Confirmation input must exist');

  await flush(2);
  assert(document.activeElement === input, 'Confirmation input should auto-focus when modal opens');

  input.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  assert(document.querySelector('.data-check-modal-backdrop') === overlay, 'Clicking input must not close modal');

  const typed = 'DELETE_DUP';
  for (const char of typed) {
    input.value += char;
    input.dispatchEvent(new window.Event('input', { bubbles: true }));
    assert(document.querySelector('.data-check-modal-backdrop') === overlay, 'Modal must not be recreated while typing');
    assert(input.value === typed.slice(0, input.value.length), 'Input value must not be reset while typing');
  }

  assert(confirmButton.disabled === true, 'Confirm button must stay disabled for invalid token');

  input.value = 'DELETE_DUPLICATE_LISTINGS';
  input.dispatchEvent(new window.Event('input', { bubbles: true }));
  assert(confirmButton.disabled === false, 'Confirm button must be enabled for valid token');

  dialog.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  assert(document.querySelector('.data-check-modal-backdrop') === overlay, 'Clicking dialog must not close modal');

  overlay.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(2);
  assert(!document.querySelector('.data-check-modal-backdrop'), 'Clicking overlay background must close modal');

  cleanupButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(2);
  overlay = document.querySelector('.data-check-modal-backdrop');
  cancelButton = overlay.querySelector('#data-check-cancel-button');
  cancelButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(2);
  assert(!document.querySelector('.data-check-modal-backdrop'), 'Cancel button must close modal');

  cleanupButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(2);
  overlay = document.querySelector('.data-check-modal-backdrop');
  document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await flush(2);
  assert(!document.querySelector('.data-check-modal-backdrop'), 'Escape must close modal');

  cleanupButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(2);
  overlay = document.querySelector('.data-check-modal-backdrop');
  input = overlay.querySelector('#data-check-confirm-input');
  confirmButton = overlay.querySelector('#data-check-confirm-button');
  cancelButton = overlay.querySelector('#data-check-cancel-button');

  input.value = 'WRONG_TOKEN';
  input.dispatchEvent(new window.Event('input', { bubbles: true }));
  assert(confirmButton.disabled, 'Confirm button must remain disabled when token is wrong');

  input.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  await flush(2);
  assert(cleanupCallCount === 0, 'Cleanup API must not be called on Enter when token is invalid');

  input.value = 'DELETE_DUPLICATE_LISTINGS';
  input.dispatchEvent(new window.Event('input', { bubbles: true }));
  assert(confirmButton.disabled === false, 'Confirm button must enable when token is valid');

  confirmButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  assert(input.disabled === true, 'Input must be disabled while cleanup request is running');
  assert(cancelButton.disabled === true, 'Cancel button must be disabled while cleanup request is running');
  assert(confirmButton.disabled === true, 'Confirm button must be disabled while cleanup request is running');

  await flush(15);
  assert(cleanupCallCount === 1, 'Cleanup API must be called exactly once after valid confirmation');
  assert(!document.querySelector('.data-check-modal-backdrop'), 'Modal must close after successful cleanup');

  console.log('hqa-data-check-modal-interaction tests passed');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
