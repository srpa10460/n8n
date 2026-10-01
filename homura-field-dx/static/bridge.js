// Runs the shared Python core (hoa_field.engine) in the browser via Pyodide - the SAME code as the server uses.
let py = null, loading = null;
export function ready() { return !!py; }
export function load(setStatus = () => {}) {
  if (py) return Promise.resolve(py);
  if (loading) return loading;
  loading = (async () => {
    setStatus("Python実行環境を読み込み中…");
    await new Promise((res, rej) => { const s = document.createElement("script"); s.src = "/vendor/pyodide/pyodide.js"; s.onload = res; s.onerror = () => rej(new Error("pyodide.js 読み込み失敗 (初回はオンラインで準備が必要)")); document.head.appendChild(s); });
    const p = await loadPyodide({ indexURL: "/vendor/pyodide/" });
    const man = await (await fetch("/py/manifest.json")).json();
    p.FS.mkdirTree("/home/pyodide/hoa_field");
    for (const f of man.files) p.FS.writeFile("/home/pyodide/hoa_field/" + f, await (await fetch("/py/" + f)).text());
    p.runPython("import sys; sys.path.insert(0,'/home/pyodide')\nfrom hoa_field.engine import call_json");
    py = p; setStatus(""); return p;
  })().catch(e => { loading = null; throw e; });
  return loading;
}
export async function call(op, state, payload) {
  const p = await load();
  const fn = p.globals.get("call_json");
  const out = fn(op, JSON.stringify(state), JSON.stringify(payload || {}));
  fn.destroy?.();
  const j = JSON.parse(out);
  if (j.error) throw new Error(j.error);
  return j;
}
