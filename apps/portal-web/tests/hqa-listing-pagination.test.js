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

  const listingRequests = [];
  let pageSequence = 1;

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
        total_records_stored: 89,
        unique_listing_ids: 89,
        filtered_records: 89,
        active: 89,
        ended: 0,
        out_of_stock: 0,
      });
    }

    if (url.includes('/api/v1/hqa/listings?')) {
      const params = new URL(url, 'http://localhost');
      const page = Number(params.searchParams.get('page') || '1');
      const pageSize = Number(params.searchParams.get('page_size') || '50');
      listingRequests.push({ page, pageSize });

      return createJsonResponse({
        items: Array.from({ length: page === 1 ? 50 : 39 }, (_, index) => ({
          id: `${page}-${index + 1}`,
          listing_id: `L-${page}-${index + 1}`,
          listing_title: `Row ${page}-${index + 1}`,
          price: 10 + index,
        })),
        page,
        page_size: pageSize,
        total: 89,
        total_pages: 2,
      });
    }

    if (url.includes('/api/v1/auth/refresh')) {
      return createJsonResponse({}, 401);
    }

    if (url.includes('/api/v1/hqa/listings/export')) {
      return createJsonResponse({});
    }

    return createJsonResponse({});
  };

  global.fetch = window.fetch;

  const appJsPath = path.join(__dirname, '..', 'assets', 'app.js');
  window.eval(fs.readFileSync(appJsPath, 'utf8'));

  await flush(10);

  const state = window.__hqaState;
  assert.strictEqual(state.hqa.page, 1, 'Initial page should be 1');

  const nextButton = document.querySelector('[data-page-action="next"]');
  assert(nextButton, 'Next pagination button should exist');
  nextButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(6);

  assert.strictEqual(state.hqa.page, 2, 'Clicking Next should advance the page state to 2');
  assert.deepStrictEqual(listingRequests.slice(-1), [{ page: 2, pageSize: 50 }], 'Next should issue a request for page 2');

  const prevButton = document.querySelector('[data-page-action="prev"]');
  assert(prevButton, 'Previous pagination button should exist after page change');
  prevButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(6);

  assert.strictEqual(state.hqa.page, 1, 'Clicking Previous should return the page state to 1');
  assert.deepStrictEqual(listingRequests.slice(-1), [{ page: 1, pageSize: 50 }], 'Previous should issue a request for page 1');

  const lastButton = document.querySelector('[data-page-action="last"]');
  assert(lastButton, 'Last pagination button should exist');
  lastButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(6);

  assert.strictEqual(state.hqa.page, 2, 'Clicking Last should jump to the last page');

  const firstButton = document.querySelector('[data-page-action="first"]');
  assert(firstButton, 'First pagination button should exist');
  firstButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(6);

  assert.strictEqual(state.hqa.page, 1, 'Clicking First should return to the first page');

  const pageTwoButton = document.querySelector('[data-page-action="page"][data-page="2"]');
  assert(pageTwoButton, 'Page 2 button should exist');
  pageTwoButton.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await flush(6);

  assert.strictEqual(state.hqa.page, 2, 'Clicking a page-number button should jump to that page');

  console.log('hqa-listing-pagination tests passed');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
