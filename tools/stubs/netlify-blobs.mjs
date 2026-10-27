// An in-memory stand-in for @netlify/blobs, so the Netlify Functions run locally without Netlify:
// tools/test_api.mjs and tools/dev_serve.mjs map the package here (tools/stubs/hooks.mjs). Only what the
// functions use: get, getWithMetadata, set, setJSON (onlyIfNew, onlyIfMatch), delete and list.
const STORES = (globalThis.__BLOBS__ = globalThis.__BLOBS__ || new Map());
let ETAG = 0;

class Store {
  constructor() { this.m = new Map(); }
  _val(r, o) { return o && o.type === "json" ? JSON.parse(r.v) : r.v; }
  async get(k, o) { const r = this.m.get(k); return r ? this._val(r, o) : null; }
  async getWithMetadata(k, o) { const r = this.m.get(k); return r ? { data: this._val(r, o), etag: r.etag, metadata: {} } : null; }
  async set(k, v, o = {}) { return this._put(k, String(v), o); }
  async setJSON(k, v, o = {}) { return this._put(k, JSON.stringify(v), o); }
  _put(k, v, o) {
    if (o.onlyIfNew && this.m.has(k)) return { modified: false };
    if (o.onlyIfMatch && (!this.m.has(k) || this.m.get(k).etag !== o.onlyIfMatch)) return { modified: false };
    const etag = "e" + ++ETAG;
    this.m.set(k, { v, etag });
    return { modified: true, etag };
  }
  async delete(k) { this.m.delete(k); }
  list(o = {}) {
    const blobs = [...this.m.entries()].filter(([k]) => !o.prefix || k.startsWith(o.prefix)).map(([key, r]) => ({ key, etag: r.etag }));
    if (o.paginate) return (async function* () { yield { blobs, directories: [] }; })();
    return Promise.resolve({ blobs, directories: [] });
  }
  clear() { this.m.clear(); }
}

export function getStore(opts) {
  const name = typeof opts === "string" ? opts : opts && opts.name;
  if (!STORES.has(name)) STORES.set(name, new Store());
  return STORES.get(name);
}
export const getDeployStore = getStore;
