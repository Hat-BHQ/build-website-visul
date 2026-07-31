const fs = require('fs');
const path = require('path');
const assert = require('assert');

const appJsPath = path.join(__dirname, '..', 'assets', 'app.js');
const source = fs.readFileSync(appJsPath, 'utf8');

const expectedOptions = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'ACTIVE' },
  { value: 'ended', label: 'ENDED' },
  { value: 'new_listing', label: 'NEW_LISTING' },
  { value: 'out_of_stock', label: 'OUT_OF_STOCK' },
  { value: 'unknown', label: 'UNKNOWN' },
];

for (const option of expectedOptions) {
  assert(
    source.includes(`<option value="${option.value}"`) && source.includes(`>${option.label}</option>`),
    `Missing listing_status option ${option.label}`,
  );
}

assert(!source.includes('OUT_OG_STOCK'), 'Invalid status OUT_OG_STOCK must not exist');

assert(
  source.includes("listing_status: document.getElementById('listing-status').value.trim()"),
  'Apply filters must persist selected listing_status',
);

assert(
  source.includes("listing_status: ''"),
  'Reset filters must clear listing_status back to All statuses',
);

assert(
  source.includes("if (filters[key]) params.set(key, filters[key]);"),
  'Query builder must skip empty listing_status when All statuses is selected',
);

console.log('hqa-listing-status-filter tests passed');