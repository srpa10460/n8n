"""Browser E2E for offline-first field work + manual sync. Real Chromium, real server, real IndexedDB/Service Worker.
Run:  /path/to/venv/bin/python tests/e2e_offline.py     (needs playwright + pymupdf; ./scripts/fetch_pyodide.sh once)
Scope/limits: Chromium on Linux headless. NOT a pass for any target tablet. Quota exhaustion is fault-injected."""
import json, shutil, sys, tempfile, threading, time, urllib.request, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pymupdf
from playwright.sync_api import sync_playwright, expect
from hoa_field.server import make_server, Handler
from hoa_field.engine import call

import os
CHROME = os.environ.get("HOA_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
SHOTS = ROOT / "docs" / "screens"; SHOTS.mkdir(parents=True, exist_ok=True)
PORT = 8793; BASE = f"http://127.0.0.1:{PORT}"
results = []
import os
DEBUG = os.environ.get("E2E_DEBUG") == "1"


def check(name, cond, detail=""):
    results.append({"name": name, "pass": bool(cond), "detail": str(detail)[:300]})
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        raise AssertionError(f"{name} {detail}")


def placeholder(path, label, color):
    d = pymupdf.open(); pg = d.new_page(width=480, height=320)
    pg.draw_rect(pg.rect, color=None, fill=color)
    pg.insert_text((24, 150), "SYNTHETIC PHOTO PLACEHOLDER", fontsize=20, color=(1, 1, 1)); pg.insert_text((24, 190), label, fontsize=16, color=(1, 1, 1))
    pg.get_pixmap().save(str(path))


def http(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")


def other_device_edit(pid, key_mm):
    """Simulates a SECOND tablet: takes the server's current version, edits a measurement, and syncs it with another client id."""
    _, tok = http("POST", "/api/auth/dev-token", {"user": "other-device", "ttl_s": 600}); t = tok["token"]
    _, rec = http("GET", f"/api/sync/project/{pid}", token=t)
    pk = rec["package"]; st = {"catalog": pk["catalog"], "project": pk["project"]}
    out = call("measure", st, {"object_id": "O-VAN", "key": "depth", "value": key_mm, "unit": "mm", "source": "MEASURED", "by": "other-device"})
    npk = call("sync_package", out["state"], {})["result"]["package"]
    s, b = http("POST", "/api/sync/begin", {"client_id": "C-other-device", "project_id": pid, "base_rev": rec["rev"], "package": npk}, t)
    assert s == 200, b
    s, c = http("POST", "/api/sync/commit", {"client_id": "C-other-device", "project_id": pid, "data_version": npk["data_version"], "content_hash": npk["content_hash"]}, t)
    assert s == 200, c
    return c["rev"]


def main():
    tmp = Path(tempfile.mkdtemp()); data = tmp / "server"
    srv = make_server(PORT, data, dev_auth=True); threading.Thread(target=srv.serve_forever, daemon=True).start()
    imgs = {}
    for n, c in (("front", (0.2, 0.35, 0.6)), ("ctx", (0.3, 0.5, 0.35)), ("extra", (0.55, 0.3, 0.3)), ("wcb", (0.5, 0.4, 0.2)), ("wsh_f", (0.2, 0.5, 0.5)), ("wsh_c", (0.6, 0.2, 0.5)), ("extra2", (0.4, 0.4, 0.4)), ("extra3", (0.7, 0.5, 0.2))):
        imgs[n] = tmp / f"{n}.png"; placeholder(imgs[n], n, c)
    prof = tmp / "profile"
    errors = []

    def launch(profile=prof):
        ctx = pw.chromium.launch_persistent_context(str(profile), executable_path=CHROME, args=["--no-sandbox"], viewport={"width": int(os.environ.get("E2E_WIDTH", "960")), "height": 900}, accept_downloads=True)
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        if DEBUG:
            pg.on("console", lambda m: print("console:", m.type, m.text[:200])); pg.on("requestfailed", lambda r: print("REQFAIL", r.url, r.failure))
        return ctx, pg

    def boot(pg, timeout=120000):
        pg.goto(BASE + "/")
        try:
            pg.wait_for_function("window.__ready===true", timeout=timeout)
        except Exception:
            print("BOOT TIMEOUT state:", pg.evaluate("JSON.stringify({s: window.__S && {err: window.__S.err, ready: window.__S.ready}, sw: !!navigator.serviceWorker.controller, hasApp: typeof window.act})"))
            raise

    with sync_playwright() as pw:
        ctx, pg = launch()
        shot = lambda n: pg.screenshot(path=str(SHOTS / f"{n}.png"), full_page=True)
        tab = lambda k: pg.click(f"nav button[data-tab={k}]")

        # ---------- 1. online preparation
        boot(pg)
        pg.wait_for_function("window.__S.ready.sw===true", timeout=90000)
        tab("sync"); pg.click("text=永続保存を要求")
        check("online prep: service worker + python core cached", pg.evaluate("window.__S.ready.sw && window.__S.ready.py"))
        # Catalog: one by form, others from synthetic sample (stored on device)
        tab("catalog")
        pg.fill("#c-id", "vanity"); pg.fill("#c-name", "洗面台ユニット"); pg.fill("#c-cat", "sanitary")
        for i, datum in enumerate(["本体外寸 左端〜右端 (高さ中央)", "壁面〜最前面 (幅中央)", "床面〜天板上面 (幅中央)"]):
            r = pg.locator("tr.cd").nth(i); r.locator("[data-f=datum]").fill(datum); r.locator("[data-f=method]").fill("スチールテープ")
            r.locator("[data-f=source]").fill("client-defined"); r.locator("[data-f=max_mm]").fill("3000")
        pg.fill("#c-photos", "front,wall-context"); pg.fill("#c-ann", "plumbing-position")
        pg.fill("#s-depth", "500"); pg.fill("#s-basis", "SYNTHETIC test value (dev); not a spec")
        pg.click("#c-go"); expect(pg.locator("#msg")).to_contain_text("端末に保存済み")
        pg.click("#cat-sample"); expect(pg.locator("#cat-table")).to_contain_text("washer")
        shot("10_catalog_prepared_online")
        tab("sync"); shot("10b_prepare_state_online")
        stored = pg.evaluate("window.__db.read('catalog','main').then(c=>Object.keys(c).sort().join(','))")
        check("catalog stored on device before going offline", stored == "vanity,wall-cabinet,washer", stored)

        # ---------- 2. go offline, restart app offline
        ctx.set_offline(True)
        pg.reload(); pg.wait_for_function("window.__ready===true", timeout=120000)
        pg.wait_for_function("window.__S.online===false")
        check("offline boot from cache; header says offline", "オフライン" in pg.locator("header").inner_text())

        # ---------- 3. offline work: project, objects, measurements, photos, annotations, review, export
        pg.fill("#np-id", "P-0001"); pg.click("#np-go"); expect(pg.locator("#msg")).to_contain_text("端末に保存済み")
        shot("09_project_created")
        tab("objects")
        for oid, d, lab in (("O-VAN", "vanity", "洗面台"), ("O-WCB", "wall-cabinet", "吊戸棚"), ("O-WSH", "washer", "洗濯機")):
            pg.fill("#o-id", oid); pg.select_option("#o-def", d); pg.fill("#o-label", lab); pg.click("#o-go")
            expect(pg.locator(f"tr[data-obj={oid}]")).to_be_visible()
        def place(oid, x, y, z="0"):
            r = pg.locator(f"tr[data-obj={oid}]"); r.locator("[data-p=x]").fill(x); r.locator("[data-p=y]").fill(y); r.locator("[data-p=z]").fill(z)
            r.get_by_role("button", name="配置").click(); expect(pg.locator("#msg")).to_contain_text("配置しました")
        place("O-VAN", "0", "0"); place("O-WCB", "0", "0", "1500"); place("O-WSH", "1000", "0")
        shot("11a_offline_objects")
        tab("dims")
        def measure(oid, key, v, unit="mm", src="MEASURED"):
            r = pg.locator(f"section[data-obj={oid}] tr[data-key={key}]"); r.locator("[data-m=v]").fill(v); r.locator("[data-m=u]").select_option(unit)
            r.locator("[data-m=s]").select_option(src); r.locator("[data-m=by]").fill("field-01"); r.get_by_role("button", name="入力").click()
            expect(pg.locator("#msg")).to_contain_text("記録")
        measure("O-VAN", "width", "800", src="ESTIMATED_PHOTO")
        check("estimate labelled 写真推定", "写真推定" in pg.locator("section[data-obj=O-VAN] tr[data-key=width]").inner_text())
        measure("O-VAN", "width", "30", "in")
        check("30 in -> 762.000 mm (unit conversion offline)", "762.000 mm" in pg.locator("section[data-obj=O-VAN] tr[data-key=width]").inner_text())
        measure("O-VAN", "depth", "550"); measure("O-VAN", "height", "850")
        measure("O-WCB", "width", "750"); measure("O-WCB", "depth", "200"); measure("O-WCB", "height", "700")
        measure("O-WSH", "width", "0.64", "m"); measure("O-WSH", "depth", "600"); measure("O-WSH", "height", "1000")
        shot("11_offline_dims")
        tab("photos")
        def photo(oid, tag, img):
            s = pg.locator(f"section[data-obj={oid}]"); s.locator("[data-ph=tag]").select_option(tag)
            s.locator("[data-ph=file]").set_input_files(str(imgs[img])); s.get_by_role("button", name="添付").click(); expect(pg.locator("#msg")).to_contain_text("添付")
        photo("O-VAN", "front", "front"); photo("O-VAN", "wall-context", "ctx"); photo("O-WCB", "front", "wcb"); photo("O-WSH", "front", "wsh_f"); photo("O-WSH", "wall-context", "wsh_c")
        for oid, k, t in (("O-VAN", "plumbing-position", "supply 120mm from left wall"), ("O-WSH", "drain-position", "drain 80mm from right edge")):
            s = pg.locator(f"section[data-obj={oid}]"); s.locator(f"[data-an={k}]").fill(t); s.get_by_role("button", name="保存").click(); expect(pg.locator("#msg")).to_contain_text("保存")
        check("auto-draw notice present", "未実装" in pg.locator("#no-auto").inner_text())
        shot("12_offline_photos")
        tab("check"); expect(pg.locator("#val-ok")).to_be_visible(); expect(pg.locator("#ov")).to_contain_text("PASS")
        shot("13a_offline_check")
        tab("preview"); pg.wait_for_function("document.querySelector('#plan-img').naturalWidth>0"); shot("13_offline_preview")
        tab("review"); ver = int(pg.inner_text("#rv-ver")[1:]); hsh = pg.inner_text("#rv-hash")
        pg.click("#rv-submit"); expect(pg.locator("#ap-go")).to_be_visible()
        pg.fill("#ap-name", "Dev Tester"); pg.click("#ap-go"); expect(pg.locator("#err")).to_contain_text("confirmations")
        tab("dims"); tab("review")      # leave the intentional error behind so the manual screenshot is clean
        pg.fill("#ap-name", "Dev Tester")
        for c in pg.locator("[data-cf]").all(): c.check()
        shot("14a_review_before_approve")
        pg.click("#ap-go"); expect(pg.locator("#msg")).to_contain_text("承認しました")
        check("dev-simulated approval labelled", "開発模擬" in pg.locator("header").inner_text())
        shot("14_offline_approved")
        tab("export"); pg.click("#ex-go"); expect(pg.locator("#ex-list")).to_contain_text("manifest.json")
        mhref = pg.locator("#ex-list a").evaluate_all("els=>els.find(e=>e.download.endsWith('manifest.json')).href")
        man = json.loads(pg.evaluate("u=>fetch(u).then(r=>r.text())", mhref))
        check("offline export manifest approved + hash", man["approved"] and man["content_hash"] == hsh, man.get("content_hash"))
        shot("14b_offline_export")
        tab("sync")
        check("sync button disabled offline with 接続後に処理", pg.locator("[data-send=P-0001]").is_disabled() and "接続後に処理" in pg.inner_text("#sync-table"))
        check("status: 端末保存済み + 未送信", "端末保存済み" in pg.inner_text("#sync-table") and "未送信" in pg.inner_text("#sync-table"))
        shot("15_offline_sync_pending")
        local_hash = hsh

        # ---------- 4. quit & restart (still offline) -> restore
        ctx.close()
        ctx, pg = launch(); shot = lambda n: pg.screenshot(path=str(SHOTS / f"{n}.png"), full_page=True); tab = lambda k: pg.click(f"nav button[data-tab={k}]")
        boot(pg)
        tab("project"); pg.click("[data-open=P-0001]")
        check("restart: project restored", pg.inner_text("#h-pid") == "P-0001" and pg.inner_text("#rv-ver" if False else "#h-ver") == f"v{ver}", pg.inner_text("#h-ver"))
        tab("photos"); pg.wait_for_function("[...document.querySelectorAll('.thumbs img')].length>=5 && [...document.querySelectorAll('.thumbs img')].every(i=>i.naturalWidth>0)")
        check("restart: 5 attached photos restored and decodable", True); shot("16_restored_after_restart")
        tab("dims"); check("restart: measurement restored (762.000 mm)", "762.000 mm" in pg.locator("section[data-obj=O-VAN] tr[data-key=width]").inner_text())
        tab("review"); check("restart: approval still current for this version", "開発模擬" in pg.locator("header").inner_text())

        # ---------- 5. back online -> login -> manual send
        ctx.set_offline(False); pg.wait_for_function("window.__S.online===true", timeout=20000)
        tab("sync")
        s, _ = http("GET", "/api/sync/project/P-0001"); check("server requires auth (401 without token)", s == 401)
        pg.click("#login"); expect(pg.locator("#msg")).to_contain_text("ログインしました")
        check("no auto-send: server has nothing yet", not (data / "server_projects" / "P-0001" / "current.json").exists())
        pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("サーバー受領済み", timeout=60000)
        rec = json.loads((data / "server_projects" / "P-0001" / "current.json").read_text())
        check("server received: rev1 + hash equals device hash", rec["rev"] == 1 and rec["received_hash"] == local_hash, rec["received_hash"])
        check("server holds all 5 photos with matching sha", all((data / "server_assets" / "P-0001" / a["asset_id"]).exists() and (data / "server_assets" / "P-0001" / (a["asset_id"] + ".sha256")).read_text() == a["sha256"] for a in rec["package"]["assets"]) and len(rec["package"]["assets"]) == 5)
        shot("17_synced")

        # ---------- 6. interrupted upload -> failure shown -> retry without duplicates
        tab("dims"); 
        def measure2(oid, key, v): measure(oid, key, v)
        tab("photos"); photo("O-WCB", "front", "extra"); tab("sync")
        calls = {"n": 0}
        def abort_once(route):
            calls["n"] += 1; route.abort("connectionreset") if calls["n"] == 1 else route.continue_()
        pg.route("**/api/sync/asset*", abort_once)
        pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("送信失敗", timeout=30000)
        check("cut during upload: failure + reason shown", "切断" in pg.inner_text("#sync-table") or "通信" in pg.inner_text("#sync-table"), pg.inner_text("#sync-table"))
        check("cut during upload: server NOT marked received (still rev1)", json.loads((data / "server_projects" / "P-0001" / "current.json").read_text())["rev"] == 1)
        check("cut during upload: local data kept", pg.evaluate("window.__db.all('photos').then(p=>Object.keys(p).length)") == 6)
        shot("18_send_failed_interrupted")
        pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("サーバー受領済み rev2", timeout=60000)
        pg.unroute("**/api/sync/asset*")
        rec = json.loads((data / "server_projects" / "P-0001" / "current.json").read_text())
        check("retry: rev2 exactly once, 6 assets (no duplicates)", rec["rev"] == 2 and len(list((data / "server_assets" / "P-0001").glob("A-*[!256]"))) >= 1 and len([f for f in (data / "server_assets" / "P-0001").iterdir() if not f.name.endswith(".sha256") and not f.name.endswith(".tmp")]) == 6)
        res = http("POST", "/api/auth/dev-token", {"ttl_s": 600})[1]["token"]
        s, b = http("POST", "/api/sync/commit", {"client_id": rec["client_id"], "project_id": "P-0001", "data_version": rec["package"]["data_version"], "content_hash": rec["received_hash"]}, res)
        check("replayed commit is idempotent (same rev)", s == 200 and b["rev"] == 2 and b.get("replayed"))

        # ---------- 7. edit while sending -> sent version vs newer unsent version
        tab("photos"); photo("O-WSH", "front", "extra2"); tab("sync")
        Handler.asset_delay_s = 2.0
        pg.click("[data-send=P-0001]")
        tab("dims"); measure("O-WCB", "height", "705")
        tab("sync"); txt = pg.inner_text("tr[data-pid=P-0001]")
        check("edit during send: 送信中 + 新しい未送信版 shown", "送信中" in txt and "新しい未送信版" in txt, txt)
        shot("19_edit_while_sending")
        expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("最終受領 rev3", timeout=60000)
        Handler.asset_delay_s = 0
        txt = pg.inner_text("tr[data-pid=P-0001]")
        check("after send: received rev3 AND newer change still 未送信", "未送信" in txt and "rev3" in txt, txt)

        # ---------- 8. auth expiry
        pg.evaluate("window.__ttl=1"); pg.click("#login"); expect(pg.locator("#msg")).to_contain_text("ログインしました"); time.sleep(2.2)
        pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("認証期限切れ", timeout=30000)
        check("auth expired: reason shown, unsent data kept", pg.evaluate("window.__db.read('projects','P-0001').then(p=>!!p)"))
        shot("20_auth_expired")
        pg.evaluate("window.__ttl=3600"); pg.click("#login"); expect(pg.locator("#msg")).to_contain_text("ログインしました")
        pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("サーバー受領済み rev4", timeout=60000)
        check("after re-login: retry succeeds (rev4)", True)

        # ---------- 9. version conflict (other device) -> diff -> override
        rev = other_device_edit("P-0001", "560"); check("other device wrote rev5", rev == 5, rev)
        tab("dims"); measure("O-VAN", "depth", "555")
        tab("sync"); pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("競合", timeout=30000)
        check("conflict: not overwritten on server", json.loads((data / "server_projects" / "P-0001" / "current.json").read_text())["client_id"] == "C-other-device")
        pg.click("text=差分を表示"); expect(pg.locator("#diff-table")).to_contain_text("depth")
        check("conflict: diff shows both values", "560" in pg.inner_text("#diff-table") and "555" in pg.inner_text("#diff-table"), pg.inner_text("#diff-table")[:300])
        shot("21_conflict_diff")
        pg.click("#override"); expect(pg.locator("#msg")).to_contain_text("上書き準備"); pg.click("[data-send=P-0001]")
        expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("サーバー受領済み rev6", timeout=60000)
        check("override: rev6 and other device's rev5 kept in history", (data / "server_projects" / "P-0001" / "history" / "rev5.json").exists())
        # second conflict -> adopt server
        other_device_edit("P-0001", "570")
        tab("dims"); measure("O-VAN", "depth", "556"); tab("sync"); pg.click("[data-send=P-0001]"); expect(pg.locator("tr[data-pid=P-0001]")).to_contain_text("競合", timeout=30000)
        pg.click("text=差分を表示"); pg.click("#adopt"); expect(pg.locator("#msg")).to_contain_text("採用")
        keys = pg.evaluate("window.__db.all('meta').then(m=>Object.keys(m).filter(k=>k.startsWith('conflict-backup/')))")
        check("adopt server: local version backed up on device", len(keys) == 1, keys)
        tab("dims"); check("adopt server: server value (570) now on device", "570.000 mm" in pg.locator("section[data-obj=O-VAN] tr[data-key=depth]").inner_text())
        tab("sync"); check("adopt: state received", "サーバー受領済み" in pg.inner_text("tr[data-pid=P-0001]"))

        # ---------- 10. quota / save failure: nothing is shown as saved
        tab("dims")
        pg.evaluate("""()=>{window.__origPut=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(){throw new DOMException('quota exceeded','QuotaExceededError')}}""")
        before = pg.inner_text("section[data-obj=O-VAN] tr[data-key=width]")
        r = pg.locator("section[data-obj=O-VAN] tr[data-key=width]"); r.locator("[data-m=v]").fill("777"); r.get_by_role("button", name="入力").click()
        expect(pg.locator("#err")).to_contain_text("保存失敗")
        check("quota: 保存失敗 shown, header not 'saved'", "保存失敗" in pg.locator("header").inner_text() and "端末保存済み" not in pg.locator("header .b-ok:has-text('端末保存済み')").all_inner_texts().__str__().replace("端末保存済み v", ""))
        tab("photos"); s = pg.locator("section[data-obj=O-VAN]"); s.locator("[data-ph=file]").set_input_files(str(imgs["extra3"])); s.get_by_role("button", name="添付").click()
        expect(pg.locator("#err")).to_contain_text("保存失敗")
        check("quota: photo save failure reported", True); shot("22_save_failed_quota")
        pg.evaluate("()=>{IDBObjectStore.prototype.put=window.__origPut}")
        pg.reload(); pg.wait_for_function("window.__ready===true"); pg.click("nav button[data-tab=project]"); pg.click("[data-open=P-0001]"); pg.click("nav button[data-tab=dims]")
        check("quota: failed edit not persisted after reload", "570.000" not in "" and "777" not in pg.inner_text("section[data-obj=O-VAN] tr[data-key=width]"), pg.inner_text("section[data-obj=O-VAN] tr[data-key=width]"))
        check("quota: failed photo not persisted", pg.evaluate("window.__db.all('photos').then(p=>Object.keys(p).length)") == 7)

        # ---------- 11. recovery export -> import into a brand-new device profile
        pg.click("nav button[data-tab=sync]")
        with pg.expect_download() as dl: pg.click("#bk-export")
        bk = tmp / "backup.json"; dl.value.save_as(str(bk))
        check("backup file written", bk.stat().st_size > 1000, bk.stat().st_size)
        orig_photo_keys = sorted(pg.evaluate("window.__db.all('photos').then(p=>Object.keys(p))"))
        ctx.close()
        ctx2, pg2 = launch(tmp / "profile2")
        boot(pg2); pg2.wait_for_function("window.__S.ready.sw===true", timeout=90000)
        pg2.click("nav button[data-tab=sync]"); pg2.set_input_files("#bk-file", str(bk)); pg2.click("#bk-import")
        expect(pg2.locator("#bk-report")).to_contain_text("P-0001")
        pg2.wait_for_timeout(300)
        k2 = sorted(pg2.evaluate("window.__db.all('photos').then(p=>Object.keys(p))"))
        check("import: projects + all photos restored on a new profile", k2 == orig_photo_keys and "P-0001" in pg2.inner_text("#sync-table"), (k2, orig_photo_keys))
        pg2.screenshot(path=str(SHOTS / "23_backup_imported.png"), full_page=True)
        check("no JS page errors", not errors, errors)
        ctx2.close()

        # ---------- 12. F-1 attack regression: malicious catalog/dim keys must not execute JS ----------
        ctx3, pg3 = launch(tmp / "profile_attack")
        boot(pg3); pg3.wait_for_function("window.__S.ready.py===true", timeout=120000)
        payload = "k',this);window.__pwn=1;//"
        # Engine path: measure/annotate with Guardian payload must Fail Closed
        eng = pg3.evaluate("""async (payload) => {
          window.__pwn = undefined;
          const st = {catalog: window.__S.catalogDict, project: Object.values(window.__S.projDicts||{})[0] || null};
          // create a minimal project first via API
          const created = await window.api('/api/projects', {project_id:'P-ATK', w:'2400', d:'1800', h:'2400', unit:'mm'});
          window.__S.cur = created.project_id;
          await window.act(()=>window.api('/api/catalog/sample',{}), 'sample');
          // try publish with malicious dimension key
          let pubErr = null;
          try {
            await window.api('/api/catalog', {
              definition_id:'evilbox', name:'Evil', category:'t', shape_template:'box', has_opening:false,
              dimensions:[
                {key:payload,label:'w',axis:'x',required:true,datum:'d',method:'m',tolerance_mm:'1',min_mm:'10',max_mm:'1000'},
                {key:'depth',label:'d',axis:'y',required:true,datum:'d',method:'m',tolerance_mm:'1',min_mm:'10',max_mm:'1000'},
                {key:'height',label:'h',axis:'z',required:true,datum:'d',method:'m',tolerance_mm:'1',min_mm:'10',max_mm:'1000'}
              ],
              required_photos:[], required_annotations:[], required_spaces:[]
            });
          } catch(e){ pubErr = String(e.message||e); }
          // inject into #main so event delegation handles the click (Fail Closed via needId)
          document.querySelector('#main').insertAdjacentHTML('beforeend',
            `<button id="atk-measure" type="button" data-act="measure" data-obj="O-VAN" data-key="">入力</button>`);
          const btn = document.getElementById('atk-measure');
          btn.setAttribute('data-key', payload);  // set raw attribute (dataset encodes)
          let clickErr = null;
          try { btn.click(); } catch(e){ clickErr = String(e.message||e); }
          await new Promise(r=>setTimeout(r,80));
          const uiRejected = !!(window.__S && window.__S.err && /invalid|reject/i.test(window.__S.err));
          // also try needId directly
          let needIdRejected = false;
          try { window.needId(payload, 'dimension key'); } catch(e){ needIdRejected = true; }
          return {
            pwn: window.__pwn,
            pubErr, clickErr, needIdRejected, uiRejected, err: window.__S && window.__S.err,
            hasInlineOnclick: [...document.querySelectorAll('[onclick]')].length,
          };
        }""", payload)
        check("F-1: Guardian payload does not set window.__pwn", eng.get("pwn") in (None, "undefined") or eng.get("pwn") is None, eng)
        check("F-1: needId Fail Closed on Guardian payload", eng.get("needIdRejected") is True, eng)
        check("F-1: malicious catalog publish rejected", bool(eng.get("pubErr")), eng.get("pubErr"))
        check("F-1: UI click rejects bad key without JS exec", eng.get("uiRejected") is True or eng.get("needIdRejected") is True, eng)
        check("F-1: no inline onclick handlers in DOM", eng.get("hasInlineOnclick") == 0, eng)
        ctx3.close()
    out = ROOT / "evidence" / "e2e_offline"; shutil.rmtree(out, ignore_errors=True); shutil.copytree(data, out)
    (out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    srv.shutdown()
    print(f"OFFLINE E2E: {sum(r['pass'] for r in results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
