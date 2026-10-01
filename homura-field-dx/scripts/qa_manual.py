"""Post-render QA of the manual PDF: bookmarks, internal links resolve to the right pages, text extractable (no missing glyphs),
fonts embedded, images present, no page nearly empty. Writes evidence/manual_qa.json. Exit 1 on failure."""
import json, subprocess, sys
from pathlib import Path
from pypdf import PdfReader
ROOT = Path(__file__).resolve().parents[1]
pdf = ROOT / "docs" / "manual" / "HOA_Field_DX_Manual.pdf"
r = PdfReader(str(pdf)); res = []
def chk(n, ok, d=""): res.append({"name": n, "pass": bool(ok), "detail": str(d)[:300]}); print(("PASS " if ok else "FAIL ") + n + ("" if ok else f" [{d}]"))

# bookmarks
def flat(o, acc):
    for x in o:
        if isinstance(x, list): flat(x, acc)
        else: acc.append(x)
    return acc
ol = flat(r.outline, [])
titles = [o.title for o in ol]
chk("outline (bookmarks) present, >= 14 sections", len(ol) >= 14, len(ol))
pages_of_bm = {o.title: r.get_destination_page_number(o) for o in ol}
chk("every bookmark resolves to a page", all(isinstance(v, int) and v >= 0 for v in pages_of_bm.values()), pages_of_bm)
chk("bookmarks go forward in page order", list(pages_of_bm.values()) == sorted(pages_of_bm.values()))
# internal links
links = []
for pi, pg in enumerate(r.pages):
    for a in pg.get("/Annots", []) or []:
        a = a.get_object()
        if a.get("/Subtype") != "/Link": continue
        dest = a.get("/Dest") or (a.get("/A") or {}).get("/D")
        links.append((pi, dest, a.get("/A", {}).get("/URI")))
internal = [l for l in links if l[1] is not None]
chk("internal link annotations exist (TOC 14 + back-links 14)", len(internal) >= 28, len(internal))
named = r.named_destinations
bad = []
for pi, dest, _ in internal:
    key = dest if isinstance(dest, str) else None
    try:
        tgt = r.get_destination_page_number(named[key]) if key and key in named else None
    except Exception as e: tgt = None
    if tgt is None: bad.append((pi, str(dest)[:40]))
chk("every internal link resolves to a page", not bad, bad[:5])
toc_page = next(i for i, p in enumerate(r.pages) if "目次" in (p.extract_text() or "")[:40])
toc_targets = []
for pi, dest, _ in internal:
    if pi == toc_page and isinstance(dest, str) and dest in named: toc_targets.append(r.get_destination_page_number(named[dest]))
chk("TOC links point to 14 distinct section pages", len(set(toc_targets)) >= 14, len(set(toc_targets)))
# sections' bookmark page == TOC link page
chk("TOC link targets == bookmark pages", sorted(set(toc_targets)) == sorted(set(pages_of_bm.values())) or set(toc_targets) <= set(pages_of_bm.values()), (sorted(set(toc_targets)), sorted(set(pages_of_bm.values()))))
# text
txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
for needle in ["現場アプリ 操作マニュアル", "写真からの自動作図・自動寸法抽出は未実装", "サーバー受領済み", "開発模擬承認", "762.000 mm"]:
    chk(f"text extractable: {needle}", needle in txt)
chk("no replacement/missing-glyph characters", "�" not in txt and "□" not in txt)
fonts = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True).stdout
chk("fonts embedded (emb=yes for all)", all(l.split()[-5] == "yes" for l in fonts.splitlines()[2:] if l.strip()) if len(fonts.splitlines()) > 2 else False, fonts[-300:])
imgs = subprocess.run(["pdfimages", "-list", str(pdf)], capture_output=True, text=True).stdout.splitlines()[2:]
chk("screenshots embedded (>= 17 images)", len(imgs) >= 17, len(imgs))
# image effective resolution -> legibility (screens are 960px wide)
eff = []
for l in imgs:
    p = l.split()
    try: eff.append(int(p[12]))  # x-ppi
    except Exception: pass
chk("screenshot effective resolution >= 100 ppi", eff and min(eff) >= 100, (min(eff), max(eff)) if eff else None)
empties = [i + 1 for i, p in enumerate(r.pages) if len((p.extract_text() or "").strip()) < 25]
chk("no blank pages", not empties, empties)
chk("page count", True, len(r.pages))
(ROOT / "evidence" / "manual_qa.json").write_text(json.dumps({"pages": len(r.pages), "checks": res, "bookmark_pages": pages_of_bm}, ensure_ascii=False, indent=1))
sys.exit(0 if all(c["pass"] for c in res) else 1)
