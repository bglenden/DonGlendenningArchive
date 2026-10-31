// Title-aware adapter for the pinned Pagefind engine. Document content is unchanged.
import * as fullText from '../pagefind/pagefind.js';

let cataloguePromise;
let searchSequence = 0;
const rootURL = new URL('../', import.meta.url);
const commonWords = new Set(['a', 'an', 'the', 'and', 'of', 'in', 'on', 'to', 'for', 'with', 'by', 'at']);

export function normalizeTitle(value) {
    return String(value).normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
        .replace(/\bneighborhood(s?)\b/g, 'neighbourhood$1')
        .replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
}

export function titleTier(title, query) {
    const t = normalizeTitle(title), q = normalizeTitle(query);
    if (!q) return 0;
    if (t === q) return 4;
    const withoutArticle = value => value.replace(/^(the|an|a) /, '');
    if (withoutArticle(t) === withoutArticle(q)) return 3;
    const words = q.split(' ').filter(word => !commonWords.has(word));
    if (!words.length || words.some(word => word.length < 3)) return 0;
    if (/^\s*["“].*["”]\s*$/.test(query)) return (` ${t} `).includes(` ${q} `) ? 2 : 0;
    const titleWords = t.split(' ');
    return words.every(word => titleWords.some(candidate => candidate === word || candidate.startsWith(word))) ? 2 : 0;
}

async function catalogue() {
    if (!cataloguePromise) cataloguePromise = fetch(new URL('titles.json', import.meta.url))
        .then(response => { if (!response.ok) throw new Error('Title index unavailable'); return response.json(); })
        .then(data => data.entries)
        .catch(error => { console.warn('Using full-text search without title prioritization.', error); return []; });
    return cataloguePromise;
}

export async function options(settings = {}) {
    return fullText.options({basePath: new URL('../pagefind/', import.meta.url).href,
        baseUrl: rootURL.pathname, ...settings});
}
export const init = () => fullText.init();
export const filters = () => fullText.filters();
export const mergeIndex = (...args) => fullText.mergeIndex(...args);
export const preload = (...args) => fullText.preload(...args);
export function destroy() { searchSequence++; cataloguePromise = undefined; return fullText.destroy(); }

function matchesFilters(entry, selected) {
    return Object.entries(selected || {}).every(([key, values]) => {
        const choices = Array.isArray(values) ? values : [values];
        return !choices.length || choices.some(value => (entry.filters[key] || []).includes(value));
    });
}

function titleResult(entry) {
    const url = new URL(entry.url.replace(/^\//, ''), rootURL).pathname;
    return {id: entry.id, score: 0, words: [], data: async () => ({
        url, content: '', excerpt: entry.downloadOnly ? 'Original document available to download.' : 'Matched document title.',
        word_count: 0, locations: [], weighted_locations: [], sub_results: [],
        filters: entry.filters, meta: {title: entry.title, theme: (entry.filters.theme || []).join(', ')}
    })};
}

export async function search(query, settings = {}) {
    const entries = await catalogue();
    if (!entries.length || query === null) return fullText.search(query, settings);
    const byID = new Map(entries.map(entry => [entry.id, entry]));
    const nativeSettings = {...settings, filters: {}};
    const result = await fullText.search(query, nativeSettings);
    const merged = new Map(result.results.map(item => [item.id, item]));
    const alternate = String(query).replace(/\bneighbou?rhood(s?)\b/gi, word =>
        /neighbour/i.test(word) ? word.replace(/neighbour/i, 'neighbor') : word.replace(/neighbor/i, 'neighbour'));
    if (alternate !== query) {
        const more = await fullText.search(alternate, nativeSettings);
        for (const item of more.results) if (!merged.has(item.id) || merged.get(item.id).score < item.score) merged.set(item.id, item);
    }
    for (const entry of entries) if (titleTier(entry.title, query) && !merged.has(entry.id)) merged.set(entry.id, titleResult(entry));
    const counts = {};
    for (const id of merged.keys()) for (const [key, values] of Object.entries(byID.get(id)?.filters || {})) {
        counts[key] ||= {};
        for (const value of values) counts[key][value] = (counts[key][value] || 0) + 1;
    }
    const ranked = [...merged.values()].filter(item => matchesFilters(byID.get(item.id) || {filters:{}}, settings.filters));
    ranked.sort((a, b) => {
        const left = byID.get(a.id), right = byID.get(b.id);
        const titleDifference = titleTier(right?.title || '', query) - titleTier(left?.title || '', query);
        return titleDifference || b.score - a.score;
    });
    return {...result, results: ranked, unfilteredResultCount: merged.size, filters: counts, totalFilters: counts};
}

export async function debouncedSearch(query, settings = {}, delay = 300) {
    const sequence = ++searchSequence;
    await new Promise(resolve => setTimeout(resolve, delay));
    if (sequence !== searchSequence) return null;
    const result = await search(query, settings);
    return sequence === searchSequence ? result : null;
}
