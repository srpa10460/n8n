// Manual sync (user presses 送信). Idempotent steps: begin -> assets -> commit. Completion is declared only after the
// server's commit reply matches the package hash AND the verified asset count.
import * as db from "./db.js";
import * as bridge from "./bridge.js";

export class SyncError extends Error { constructor(kind, msg, extra) { super(msg); this.kind = kind; this.extra = extra || {}; } }

export async function clientId() {
  let id = await db.read("meta", "client_id");
  if (!id) { id = "C-" + crypto.randomUUID(); await db.writeAll([["meta", "client_id", id]]); }
  return id;
}
export async function ping(ms = 3000) {
  const c = new AbortController(); const t = setTimeout(() => c.abort(), ms);
  try { const r = await fetch("/api/ping", { signal: c.signal, cache: "no-store" }); const j = await r.json(); return { online: true, dev_auth: !!j.dev_auth }; }
  catch (_) { return { online: false, dev_auth: false }; } finally { clearTimeout(t); }
}
export async function devLogin(ttl_s = 3600) {
  const r = await fetch("/api/auth/dev-token", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user: "dev-tester", ttl_s }) });
  const j = await r.json(); if (!r.ok) throw new Error(j.error || "login failed");
  await db.writeAll([["meta", "token", { token: j.token, user: "dev-tester", at: Date.now() }]]); return j;
}
async function authFetch(path, opts = {}, ms = 120000) {
  const t = (await db.read("meta", "token"))?.token;
  const c = new AbortController(); const timer = setTimeout(() => c.abort(), ms);
  let r;
  try { r = await fetch(path, { ...opts, headers: { ...(opts.headers || {}), Authorization: "Bearer " + (t || "") }, signal: c.signal }); }
  catch (e) { throw new SyncError("NETWORK", "通信できない/途中で切断: " + e.message); }
  finally { clearTimeout(timer); }
  const raw = r.headers.get("content-type")?.includes("json") ? await r.json().catch(() => ({})) : null;
  if (r.status === 401) throw new SyncError("AUTH", raw?.error === "token_expired" ? "認証期限切れ: 再ログイン後に再試行してください(未送信データは端末に保持されています)" : "認証エラー: " + (raw?.error || r.status));
  if (r.status === 409 && String(raw?.error).startsWith("conflict")) throw new SyncError("CONFLICT", "サーバー側に別の版があります(競合)", raw);
  if (!r.ok) throw new SyncError("SERVER", raw?.error || "HTTP " + r.status);
  return { r, j: raw };
}
async function setSync(pid, patch) {
  const cur = (await db.read("sync", pid)) || {};
  const nxt = { ...cur, ...patch, project_id: pid };
  await db.writeAll([["sync", pid, nxt]]); return nxt;
}
async function sha256Blob(blob) {
  const h = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function send(pid, onStep = () => {}) {
  const cid = await clientId();
  const catalog = await db.read("catalog", "main") || {};
  const project = await db.read("projects", pid);
  if (!project) throw new Error("案件が端末に無い");
  const pk = (await bridge.call("sync_package", { catalog, project }, {})).result.package;
  const prev = (await db.read("sync", pid)) || {};
  await setSync(pid, { state: "SENDING", sent_version: pk.data_version, sent_hash: pk.content_hash, step: "begin", error: null, error_kind: null, conflict: null, attempts: (prev.attempts || 0) + 1 });
  try {
    onStep("begin");
    const base = prev.base_rev ?? null;
    const b = (await authFetch("/api/sync/begin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_id: cid, project_id: pid, base_rev: base, package: pk }) })).j;
    if (b.already_received) { return await done(pid, pk, b.rev, b.received_hash, pk.assets.length); }
    let i = 0;
    for (const id of b.need_assets) {
      i++; const step = `写真 ${i}/${b.need_assets.length}`; onStep(step); await setSync(pid, { step });
      const rec = await db.read("photos", pid + "/" + id);
      const meta = pk.assets.find(a => a.asset_id === id);
      if (!rec || !rec.blob) throw new SyncError("LOCAL", `端末内に写真 ${id} が見つかりません(送信不可。端末データは削除していません)`);
      if (await sha256Blob(rec.blob) !== meta.sha256) throw new SyncError("LOCAL", `端末内の写真 ${id} が記録したハッシュと一致しません(破損の疑い)`);
      await authFetch(`/api/sync/asset?project=${encodeURIComponent(pid)}&asset=${encodeURIComponent(id)}`, { method: "PUT", headers: { "X-Sha256": meta.sha256, "Content-Type": "application/octet-stream" }, body: rec.blob });
    }
    onStep("commit"); await setSync(pid, { step: "commit" });
    const c = (await authFetch("/api/sync/commit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_id: cid, project_id: pid, data_version: pk.data_version, content_hash: pk.content_hash }) })).j;
    if (c.received_hash !== pk.content_hash || c.assets_verified !== pk.assets.length) throw new SyncError("VERIFY", "サーバー受領の照合に失敗(ハッシュ/添付数が一致しない)。送信完了とは扱いません");
    return await done(pid, pk, c.rev, c.received_hash, c.assets_verified);
  } catch (e) {
    const kind = e instanceof SyncError ? e.kind : "LOCAL";
    await setSync(pid, { state: kind === "CONFLICT" ? "CONFLICT" : "FAILED", error: e.message, error_kind: kind, conflict: kind === "CONFLICT" ? e.extra : null });
    throw e;
  }
}
async function done(pid, pk, rev, hash, n) {
  return setSync(pid, { state: "RECEIVED", step: null, error: null, error_kind: null, conflict: null, base_rev: rev, received_rev: rev, received_hash: hash, received_version: pk.data_version, received_assets: n, received_at: Date.now() });
}

export async function interruptedToFailed() {   // app was killed while SENDING
  const all = await db.all("sync");
  for (const [pid, r] of Object.entries(all)) if (r.state === "SENDING") await setSync(pid, { state: "FAILED", error: "送信が中断されました(アプリ終了または切断)。再試行できます", error_kind: "INTERRUPTED" });
}

// Conflict resolution. Nothing is overwritten silently; local state is always backed up first.
export async function adoptServer(pid) {
  const srv = (await authFetch(`/api/sync/project/${encodeURIComponent(pid)}`)).j;
  const local = await db.read("projects", pid);
  const bk = `conflict-backup/${pid}/${Date.now()}`;
  const writes = [["meta", bk, { project: local, at: Date.now() }], ["projects", pid, srv.package.project]];
  await db.writeAll(writes);                       // backup + adopt in ONE transaction
  for (const a of srv.package.assets) {
    if (await db.read("photos", pid + "/" + a.asset_id)) continue;
    const { r } = await authFetch(`/api/sync/asset?project=${encodeURIComponent(pid)}&asset=${a.asset_id}`);
    await db.writeAll([["photos", pid + "/" + a.asset_id, { blob: await r.blob(), sha256: a.sha256, filename: a.filename, project_id: pid }]]);
  }
  await setSync(pid, { state: "RECEIVED", base_rev: srv.rev, received_rev: srv.rev, received_hash: srv.received_hash, local_hash: srv.received_hash, local_version: srv.package.data_version, conflict: null, error: null, backup_key: bk });
  return bk;
}
export async function rebaseForOverwrite(pid) {   // user saw the diff and chose local; next send uses server's rev as base
  const r = await db.read("sync", pid);
  if (!r?.conflict) throw new Error("競合状態ではありません");
  await setSync(pid, { base_rev: r.conflict.server_rev, state: "FAILED", error: "ローカル版で上書き送信する準備ができました。『送信』を押してください(サーバーの旧版は履歴に保存されます)", error_kind: "REBASED", conflict: null });
}

// Recovery export / import (single JSON file: catalog, projects, sync records, photos with sha256)
export async function exportBackup() {
  const out = { format: "hoa-backup-1", created: new Date().toISOString(), client_id: await clientId(), catalog: await db.read("catalog", "main") || {}, projects: await db.all("projects"), sync: await db.all("sync"), photos: {} };
  for (const [k, v] of Object.entries(await db.all("photos"))) {
    const buf = new Uint8Array(await v.blob.arrayBuffer()); let s = ""; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    out.photos[k] = { sha256: v.sha256, filename: v.filename, project_id: v.project_id, type: v.blob.type, b64: btoa(s) };
  }
  return new Blob([JSON.stringify(out)], { type: "application/json" });
}
export async function importBackup(text) {
  const d = JSON.parse(text); if (d.format !== "hoa-backup-1") throw new Error("未対応のバックアップ形式");
  const report = { imported: [], skipped: [], bad_photos: [] };
  const photoBlobs = {};
  for (const [k, p] of Object.entries(d.photos)) {
    const bin = atob(p.b64); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    const blob = new Blob([u], { type: p.type }); if (await sha256Blob(blob) !== p.sha256) { report.bad_photos.push(k); continue; }
    photoBlobs[k] = { blob, sha256: p.sha256, filename: p.filename, project_id: p.project_id };
  }
  const have = await db.all("projects");
  const writes = [];
  const cur = await db.read("catalog", "main");
  if (!cur || !Object.keys(cur).length) writes.push(["catalog", "main", d.catalog]);
  else { const m = await bridge.call("merge_catalog", { catalog: cur, project: null }, { catalog: d.catalog }); if (m.result._changed.length) writes.push(["catalog", "main", m.state.catalog]); }
  for (const [pid, pj] of Object.entries(d.projects)) {
    if (have[pid]) { report.skipped.push(pid + " (端末に既存。上書きしない)"); continue; }
    writes.push(["projects", pid, pj]); if (d.sync[pid]) writes.push(["sync", pid, d.sync[pid]]); report.imported.push(pid);
    for (const [k, v] of Object.entries(photoBlobs)) if (k.startsWith(pid + "/")) writes.push(["photos", k, v]);
  }
  if (writes.length) await db.writeAll(writes);
  return report;
}
