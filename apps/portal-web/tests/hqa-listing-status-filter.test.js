const fs = require('fs');
const path = require('path');
const assert = require('assert');

const appJsPath = path.join(__dirname, '..', 'assets', 'app.js');
const stylesCssPath = path.join(__dirname, '..', 'assets', 'styles.css');
const source = fs.readFileSync(appJsPath, 'utf8');
const styles = fs.readFileSync(stylesCssPath, 'utf8');

assert(source.includes("const HQA_MAIN_TABS = ["), 'HQA tabs list must exist');
assert(source.includes("{ key: 'all_listings', label: 'All Listings' }"), 'All Listings tab must exist');
assert(source.includes("{ key: 'dashboard', label: 'Dashboard' }"), 'Dashboard tab must exist');
assert(source.includes("{ key: 'data_check', label: 'Kiem tra du lieu' }"), 'Data check tab must exist');
assert(!source.includes("{ key: 'daily_report', label: 'Daily Report' }"), 'Daily Report tab must be removed from main tabs');
assert(!source.includes('/hqa/reports/marketplace/listings?${'), 'All Listings flow must not call Daily Report listings endpoint');
assert(!source.includes('/hqa/reports/marketplace/summary?${'), 'All Listings flow must not call Daily Report summary endpoint');
assert(source.includes('Quan ly, loc va xuat toan bo du lieu marketplace listings.'), 'Subtitle must be updated');

assert(source.includes('appendArrayParams(params, \"condition\", filters.conditions)') || source.includes("appendArrayParams(params, 'condition', filters.conditions)"), 'Conditions must be encoded as repeated query params');
assert(source.includes('appendArrayParams(params, \"status\", filters.statuses)') || source.includes("appendArrayParams(params, 'status', filters.statuses)"), 'Statuses must be encoded as repeated query params');
assert(source.includes('appendArrayParams(params, \"category_name\", filters.categoryNames)') || source.includes("appendArrayParams(params, 'category_name', filters.categoryNames)"), 'Category names must be encoded as repeated query params');
assert(source.includes('appendArrayParams(params, \"buying_option\", filters.buyingOptions)') || source.includes("appendArrayParams(params, 'buying_option', filters.buyingOptions)"), 'Buying options must be encoded as repeated query params');
assert(source.includes("if (filters.minPrice !== '') params.set('min_price', String(filters.minPrice).trim());"), 'min_price must be included in All Listings params');
assert(source.includes("if (filters.maxPrice !== '') params.set('max_price', String(filters.maxPrice).trim());"), 'max_price must be included in All Listings params');
assert(source.includes("params.set('sort_by', 'price');"), 'Price sort must send sort_by=price when selected');
assert(source.includes("params.set('sort_order', 'asc');") || source.includes("params.set('sort_order', 'desc');"), 'Price sort must send sort_order asc/desc when selected');
assert(source.includes("if (filters.marketplace) params.set('marketplace', filters.marketplace);"), 'marketplace must be included in All Listings params');

assert(source.includes('function cloneAllListingsFilters(filters)'), 'All Listings filter cloning helper must exist');
assert(source.includes('conditions: [...(filters.conditions || [])]'), 'Filter cloning must deep-copy conditions');
assert(source.includes('statuses: [...(filters.statuses || [])]'), 'Filter cloning must deep-copy statuses');
assert(source.includes('categoryNames: [...(filters.categoryNames || [])]'), 'Filter cloning must deep-copy category names');
assert(source.includes('buyingOptions: [...(filters.buyingOptions || [])]'), 'Filter cloning must deep-copy buying options');

assert(source.includes('function renderAllListingsLazySelect('), 'Lazy multi-select renderer must exist');
assert(source.includes('data-lazy-filter-trigger="${apiField}"'), 'Lazy filter trigger markup must exist');
assert(source.includes('data-option-field="${apiField}"'), 'Lazy option field markup must exist');
assert(source.includes('data-option-value="${escapeHtml(item.value)}"'), 'Lazy option value markup must exist');
assert(source.includes('data-option-select-all="${apiField}"'), 'Lazy option select-all markup must exist');
assert(source.includes('data-option-clear="${apiField}"'), 'Lazy option clear markup must exist');
assert(source.includes('data-option-search-input="${fieldKey}"'), 'Lazy option search input markup must exist');
assert(source.includes('data-option-load-more="${apiField}"'), 'Lazy option load-more markup must exist');
assert(source.includes('data-option-retry="${apiField}"'), 'Lazy option retry markup must exist');

assert(source.includes('if (nextFilters.fromDate && nextFilters.toDate && nextFilters.fromDate > nextFilters.toDate)'), 'Date range validation must exist');
assert(source.includes('parseNonNegativeNumber(nextFilters.minPrice)'), 'Min price validation must exist');
assert(source.includes('parseNonNegativeNumber(nextFilters.maxPrice)'), 'Max price validation must exist');
assert(source.includes("candidate.replace(/,/g, '')"), 'Price parser must normalize comma thousand separators');
assert(source.includes('Min price must be less than or equal to max price.'), 'Price range validation message must exist');
assert(source.includes('Sort by Price'), 'Price sort dropdown label must exist');
assert(source.includes('id="sort-price"'), 'Price sort dropdown must exist');

assert(source.includes('await loadAllListingsFilterOptions();'), 'All Listings filter options loader must be used');
assert(source.includes('await loadAllListingsSummary();'), 'All Listings summary loader must be used');
assert(source.includes('await loadActiveListings();'), 'All Listings loader must be used');
assert(!source.includes('await loadHqaFilterOptions();'), 'Legacy daily-report filter loader must not be used');
assert(!source.includes('await loadHqaSummary();'), 'Legacy daily-report summary loader must not be used');
assert(!source.includes('export-daily-report'), 'Daily report export action must be removed');

assert(source.includes('<th>Listing published at</th><th>Last status checked at</th>'), 'All Listings table must include two datetime headers after status');
assert(source.includes('formatDateTimeHcm(item.listing_published_at)'), 'All Listings rows must render listing_published_at');
assert(source.includes('formatDateTimeHcm(item.last_status_checked_at)'), 'All Listings rows must render last_status_checked_at');
assert(source.includes("timeZone: 'Asia/Ho_Chi_Minh'"), 'Datetime formatter must use Asia/Ho_Chi_Minh timezone');
assert(source.includes("if (!value) return '-';"), 'Datetime formatter must return - for null/undefined values');
assert(source.includes("if (Number.isNaN(date.getTime())) return '-';"), 'Datetime formatter must return - for invalid values');
assert(source.includes('return `${map.day}/${map.month}/${map.year} ${map.hour}:${map.minute}`;'), 'Datetime formatter must output DD/MM/YYYY HH:mm format');

assert(styles.includes('.multi-select {'), 'Multi-select container styles must exist');
assert(styles.includes('.multi-select-trigger {'), 'Multi-select trigger styles must exist');
assert(styles.includes('.multi-select-dropdown {'), 'Multi-select menu styles must exist');
assert(styles.includes('.multi-select-actions {'), 'Multi-select actions styles must exist');
assert(styles.includes('.multi-select-options {'), 'Multi-select option list styles must exist');
assert(styles.includes('.multi-select-search {'), 'Lazy option search styles must exist');
assert(styles.includes('.multi-select-footer {'), 'Lazy option footer styles must exist');
assert(styles.includes('.multi-select-option input[type="checkbox"]'), 'Checkbox size override for lazy options must exist');
assert(styles.includes('.all-listings-table { min-width: 1240px;'), 'All Listings table width must be increased for new datetime columns');
assert(styles.includes('.all-listings-datetime {'), 'Datetime cell class must exist');
assert(styles.includes('white-space: nowrap;'), 'Datetime columns must keep single-line values');

assert(source.includes('/hqa/dashboard/filter-options?${'), 'Dashboard must load filter options from new API');
assert(source.includes('/hqa/dashboard/sellers/total'), 'Dashboard must load total sellers KPI from dedicated API');
assert(source.includes('/hqa/dashboard/summary'), 'Dashboard must use summary API');
assert(source.includes('/hqa/dashboard/seller-trend'), 'Dashboard must use seller trend API');
assert(source.includes('/hqa/dashboard/price-trend'), 'Dashboard must use price trend API');
assert(source.includes('/hqa/dashboard/price-comparison'), 'Dashboard must use price comparison API');
assert(source.includes('/hqa/dashboard/alerts'), 'Dashboard must use alerts API');
assert(source.includes('/hqa/dashboard/export?${'), 'Dashboard export must use new API');
assert(source.includes('appliedFilters'), 'Dashboard state must use shared applied filters');
assert(source.includes('draftFilters'), 'Dashboard state must use shared draft filters');
assert(source.includes('id="dashboard-seller-stats-filters"'), 'Dashboard must render seller stats date filter form');
assert(source.includes('Total Sellers'), 'Dashboard must render Total Sellers KPI card');
assert(source.includes("renderEndedOutOfStockSummaryCard"), 'All Listings summary must render combined ended/out-of-stock card helper');
assert(source.includes("Ended / Out of stock"), 'All Listings summary must show combined ended/out-of-stock label');
assert(source.includes("metric('Accessories', allSummary.accessories || 0"), 'All Listings summary must render accessories KPI');
assert(styles.includes('.metric-card--status-combined'), 'Combined summary card styles must exist');
assert(styles.includes('.metric-card__split'), 'Combined summary card split layout styles must exist');
assert(styles.includes('.metric-card--accessories'), 'Accessories summary card styles must exist');

assert(source.includes('/hqa/data-check/duplicates/summary'), 'Data check summary API must be used');
assert(source.includes('/hqa/data-check/duplicates?${buildDataCheckParams(page).toString()}'), 'Data check duplicate groups API must be used');
assert(source.includes('/hqa/data-check/duplicates/cleanup'), 'Data check cleanup API must be used');
assert(source.includes('DELETE_DUPLICATE_LISTINGS'), 'Cleanup confirmation token must be enforced in frontend flow');
assert(source.includes('Không phát hiện listing trùng') || source.includes('Khong phat hien listing trung'), 'No-duplicates empty state must be shown');
assert(!source.includes('function dedupeAllListingsItems('), 'Frontend must not deduplicate listings in JavaScript');

console.log('hqa-listing-status-filter tests passed');
