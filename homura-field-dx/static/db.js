// Device persistence (IndexedDB). A write is "saved" ONLY after the transaction's complete event.
// Any failure (quota, blocked, aborted) rejects; callers must not show "saved" in that case.
const DB_NAME = "hoa_field", DB_VER = 1;
let _db = null;
function open() {
  if (_db) return Promise.resolve(_db);
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB_NAME, DB_VER);
    r.onupgradeneeded = () => {   // additive only: never drop stores/data on upgrade
      const d = r.result;
      for (const s of ["meta", "catalog", "projects", "photos", "sync"]) if (!d.objectStoreNames.contains(s)) d.createObjectStore(s);
    };
    r.onsuccess = () => { _db = r.result; _db.onversionchange = () => _db.close(); res(_db); };
    r.onerror = () => rej(r.error || new Error("IndexedDB open failed"));
    r.onblocked = () => rej(new Error("IndexedDB blocked"));
  });
}
// writes: [[store, key, value], ...] executed atomically; resolves only on tx.oncomplete
export async function writeAll(writes) {
  const db = await open();
  return new Promise((res, rej) => {
    let tx;
    try { tx = db.transaction([...new Set(writes.map(w => w[0]))], "readwrite", { durability: "strict" }); }
    catch (e) { return rej(e); }
    tx.oncomplete = () => res(true);
    tx.onerror = () => rej(tx.error || new Error("transaction error"));
    tx.onabort = () => rej(tx.error || new Error("transaction aborted"));
    try { for (const [s, k, v] of writes) tx.objectStore(s).put(v, k); } catch (e) { try { tx.abort(); } catch (_) {} rej(e); }
  });
}
export async function read(store, key) {
  const db = await open();
  return new Promise((res, rej) => { const r = db.transaction(store).objectStore(store).get(key); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
}
export async function all(store) {
  const db = await open();
  return new Promise((res, rej) => {
    const out = {}; const r = db.transaction(store).objectStore(store).openCursor();
    r.onsuccess = () => { const c = r.result; if (c) { out[c.key] = c.value; c.continue(); } else res(out); };
    r.onerror = () => rej(r.error);
  });
}
export async function storageInfo() {
  const o = { persisted: null, usage: null, quota: null };
  try { if (navigator.storage?.persisted) o.persisted = await navigator.storage.persisted(); } catch (_) {}
  try { if (navigator.storage?.estimate) { const e = await navigator.storage.estimate(); o.usage = e.usage; o.quota = e.quota; } } catch (_) {}
  return o;
}
export async function requestPersist() { try { return navigator.storage?.persist ? await navigator.storage.persist() : false; } catch (_) { return false; } }
