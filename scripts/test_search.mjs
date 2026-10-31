#!/usr/bin/env node
// Run the real browser search engine against local files without a browser/server.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root = new URL('../', import.meta.url);
globalThis.fetch = async input => {
    const url = new URL(String(input), root);
    assert.equal(url.protocol, 'file:');
    assert.ok(fileURLToPath(url).startsWith(fileURLToPath(root)));
    return new Response(await readFile(fileURLToPath(url)), {status:200});
};
const search = await import('../search/pagefind.js');
const native = await import('../pagefind/pagefind.js');
await search.options({language:'en'});
const book = '/03-family-genealogy/read/the-neighbourhood.html';
assert.equal(search.titleTier('Cartography', '"art"'), 0);
assert.equal(search.titleTier('The art of education', '"art"'), 2);
let tests = 2;
for (const query of ['the neighbourhood','neighbourhood','The Neighbourhood','THE NEIGHBOURHOOD',
    '"the neighbourhood"','neighborhood','the neighborhood','"the neighborhood"','neighbourh']) {
    const result = await search.search(query);
    assert.ok((await result.results[0].data()).url.endsWith(book), query);
    assert.equal(new Set(result.results.map(r=>r.id)).size, result.results.length, 'Duplicate results');
    tests++;
}
for (const query of ['the neighbourhood','neighborhood']) {
    const result = await search.search(query,{filters:{theme:['Family History & Genealogy']}});
    assert.ok((await result.results[0].data()).url.endsWith(book));
    for (const item of result.results) assert.ok((await item.data()).filters.theme.includes('Family History & Genealogy'));
    const excluded = await search.search(query,{filters:{theme:['Education Philosophy & Reform']}});
    assert.ok(!(await Promise.all(excluded.results.map(r=>r.data()))).some(d=>d.url.endsWith(book)));
    tests+=2;
}
const multi = await search.search('neighbourhood',{filters:{theme:['Family History & Genealogy','Education Philosophy & Reform']}});
const multiData = await Promise.all(multi.results.map(r=>r.data()));
assert.ok(multiData.some(d=>d.filters.theme.includes('Family History & Genealogy')));
assert.ok(multiData.some(d=>d.filters.theme.includes('Education Philosophy & Reform')));
assert.ok(multiData.every(d=>d.filters.theme.some(t=>['Family History & Genealogy','Education Philosophy & Reform'].includes(t))));
assert.equal(multi.results.length,multi.filters.theme['Family History & Genealogy']+multi.filters.theme['Education Philosophy & Reform']);tests++;
const american = await native.search('neighborhood');
const combined = await search.search('neighborhood');
assert.ok(american.results.every(r=>combined.results.some(x=>x.id===r.id)), 'American-spelling body matches lost'); tests++;
for (const query of ['Elmer Watling','Donald Glendenning','DACUM','mathematics','Black River Bridge','winter storms']) {
    const original = await native.search(query);
    const improved = await search.search(query);
    assert.ok(original.results.every(r=>improved.results.some(x=>x.id===r.id)),query+' lost body matches');
    const titles = new Map(await Promise.all(improved.results.map(async r=>[r.id,(await r.data()).meta.title])));
    const plain = improved.results.filter(r=>!search.titleTier(titles.get(r.id),query)).map(r=>r.id);
    const expected = original.results.filter(r=>!search.titleTier(titles.get(r.id),query)).map(r=>r.id);
    assert.deepEqual(plain,expected,query+' changed non-title ranking'); tests++;
}
const catalogue=JSON.parse(await readFile(new URL('../search/titles.json',import.meta.url)));
assert.equal(catalogue.downloadOnlyCount,catalogue.entries.filter(e=>e.downloadOnly).length);
for (const entry of catalogue.entries.filter(e=>e.downloadOnly)) {
    const found=await search.search(entry.title);
    assert.ok(found.results.some(r=>r.id===entry.id), 'Missing download-only title: '+entry.title);
    tests++;
}
assert.equal((await search.search('')).results.length,0);tests++;
const slow=search.debouncedSearch('neighbourhood',{},40);
const latest=search.debouncedSearch('DACUM',{},0);
assert.equal(await slow,null);assert.ok((await latest).results.length);tests++;
console.log(`${tests} search checks passed: title variants, filters, spelling, all download-only titles, topic/person regressions, and stale-query cancellation.`);
