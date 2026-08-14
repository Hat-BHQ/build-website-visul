const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { JSDOM } = require('jsdom');

const wait = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
async function flush(times = 5) { for (let i = 0; i < times; i += 1) await wait(0); }
function json(payload, status = 200) { return { ok: status >= 200 && status < 300, status, async json(){ return payload; }, async text(){ return JSON.stringify(payload); }, headers:{ get(){ return 'application/json'; } } }; }

function productPayload(withDetail = false) {
  const product = { product_key:'P045', product_id:'P045', product_label:'JBL L26 speaker', keyword:'JBL L26 speaker', brand:'JBL', model:'L26', product_type:'speakers', listing_count:6, seller_count:3, related_listing_count:9, excluded_count:3 };
  const base = {
    version:'v5-product-analytics', group_by:'product', granularity:'month', periods:['2026-07','2026-08'], groups:['P045'], products:[product], previous_period:'2026-07',
    latest_period:{ period:'2026-08', listing_count:6, whole_product_count:6, related_listing_count:9, product_count:1, seller_count:3, median_price:500, avg_price:510, out_of_stock_count:1, out_of_stock_pct:16.7, uncertain_count:1, uncertain_pct:11.1, currency:'USD' },
    group_periods:[
      { ...product, group:'P045', period:'2026-07', listing_count:5, seller_count:2, min_price:430, p25:450, median_price:480, avg_price:485, p75:520, max_price:560, cv:9, out_of_stock_count:0, out_of_stock_pct:0, new_seller_count:2, top_sellers:[{seller:'seller-a',listing_count:3,avg_price:475,min_price:430}], currency:'USD' },
      { ...product, group:'P045', period:'2026-08', listing_count:6, seller_count:3, min_price:420, p25:465, median_price:500, avg_price:510, p75:545, max_price:590, cv:10, out_of_stock_count:1, out_of_stock_pct:16.7, new_seller_count:1, top_sellers:[{seller:'seller-a',listing_count:3,avg_price:500,min_price:420},{seller:'seller-b',listing_count:2,avg_price:530,min_price:510}], currency:'USD' }
    ],
    alerts:[{ type:'new_seller', severity:'info', group:'P045', product_key:'P045', product_label:'JBL L26 speaker', period:'2026-08', currency:'USD', title:'Người bán mới', new_seller_count:1, new_sellers:['seller-b'], message:'Có 1 người bán mới.' }],
    meta:{ source_table:'public.marketplace_research_results', market_analytics_scope:'whole_product eligible only' }
  };
  if (withDetail) base.drilldown = { product, period:'2026-08', current:{ ...base.group_periods[1], whole_product_count:6, component_count:1, accessory_count:1, documentation_count:0, irrelevant_count:0, uncertain_count:1, excluded_from_market_analytics_count:3 }, previous:base.group_periods[0], role_breakdown:{whole_product:6,component_part:1,accessory:1,documentation_media:0,irrelevant:0,uncertain:1}, related_listings_total:2, related_listings:[{listing_id:'1',listing_title:'JBL L26 Speakers Pair',listing_url:'https://example.com/1',marketplace:'ebay',seller:'seller-a',price:500,currency:'USD',condition:'Used',category:'Vintage Speakers',status:'active',listing_role:'whole_product',role_confidence:92,role_reasons:['category supports whole product'],eligible_for_market_analytics:true},{listing_id:'2',listing_title:'JBL L26 Woofer',listing_url:'https://example.com/2',marketplace:'ebay',seller:'seller-b',price:80,currency:'USD',condition:'Used',category:'Speaker Parts',status:'active',listing_role:'component_part',role_confidence:95,role_reasons:['title: woofer'],eligible_for_market_analytics:false}] };
  return base;
}

(async () => {
  const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', { url:'http://localhost/', pretendToBeVisual:true, runScripts:'outside-only' });
  const { window } = dom;
  Object.assign(global, { window, document:window.document, navigator:window.navigator, Headers:window.Headers, HTMLElement:window.HTMLElement, Element:window.Element, Node:window.Node });
  global.requestAnimationFrame = (callback) => setTimeout(callback, 0);
  window.HTMLElement.prototype.scrollIntoView = function(){};
  const chartCalls = [];
  window.Chart = class ChartMock { constructor(canvas, config){ chartCalls.push({canvas,config}); } destroy(){} };
  const dashboardUrls = [];
  window.fetch = async (input) => {
    const url = String(input || '');
    if (url.endsWith('/api/v1/auth/session')) return json({ access_token:'token', user:{full_name:'Tester',system_role:'superadmin'}, modules:[{code:'HQA',permissions:['*']}] });
    if (url.includes('/api/v1/hqa/listings/filter-options')) return json(url.includes('field=') ? {items:[],page:1,page_size:30,has_more:false} : {marketplaces:[],brands:[],models:[],conditions:[],statuses:[],category_names:[],buying_options:[]});
    if (url.includes('/api/v1/hqa/listings/summary')) return json({total_records_stored:9,unique_listing_ids:9,filtered_records:9,active:8,ended:0,out_of_stock:1,accessories:1});
    if (url.includes('/api/v1/hqa/listings?')) return json({items:[],page:1,page_size:50,total:0,total_pages:0});
    if (url.includes('/api/v1/hqa/dashboard/analysis')) { dashboardUrls.push(url); return json(productPayload(url.includes('keyword=P045'))); }
    if (url.includes('/api/v1/auth/refresh')) return json({}, 401);
    return json({});
  };
  global.fetch = window.fetch;

  window.eval(fs.readFileSync(path.join(__dirname, '..', 'assets', 'app.js'), 'utf8'));
  await flush(8);
  assert(!document.querySelector('[data-hqa-main-tab="data_check"]'), 'Data Check tab must not render');
  const tab = document.querySelector('[data-hqa-main-tab="dashboard"]');
  assert(tab, 'Dashboard tab must render');
  tab.dispatchEvent(new window.MouseEvent('click', {bubbles:true}));
  await flush(12);
  assert(dashboardUrls.some((url) => url.includes('group_by=product')), 'Dashboard must request product analytics');
  assert.equal(document.querySelectorAll('.pd-kpis article').length, 5, 'Five product KPI cards must render');
  assert.equal(document.querySelectorAll('.pd-alert').length, 1, 'Alert card must render');
  assert(document.getElementById('pd-series-trigger'), 'Shared product selector must render');
  assert.equal(chartCalls.length >= 2, true, 'Two product charts must render');
  await flush(12);
  assert(document.querySelector('#pd-analysis'), 'Product x period drilldown must render');
  assert(document.querySelectorAll('.pd-role').length >= 6, 'Role breakdown must render');
  assert(document.querySelector('.pd-listings table'), 'Role audit table must render');
  console.log('hqa-dashboard-render tests passed');
})().catch((error) => { console.error(error); process.exit(1); });
