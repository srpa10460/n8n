"""Builds docs/manual/HOA_Field_DX_Manual.pdf from the REAL UI screenshots in docs/screens (made by tests/e2e_offline.py).
Chromium renders HTML -> PDF with outline (bookmarks) and internal links. Run: <venv>/bin/python scripts/build_manual.py"""
import html, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "manual"
CHROME = os.environ.get("HOA_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
VERSION = "開発版 (CHECKPOINT-002)"

# (id, title, [blocks]) block = ("p", text) | ("ul", [..]) | ("img", file, caption) | ("table", header, rows) | ("note", text) | ("warn", text)
S = []
def sec(i, t, *b): S.append((i, t, list(b)))

sec("about", "1. このマニュアルについて",
 ("p", "本書は HOMURA Interior Field DX の現場アプリ(A)の操作手順です。画面画像は、実際に動作したアプリを自動操作して収録したものです。"),
 ("warn", "画面内の案件・対象物・写真はすべて合成データです(写真は「SYNTHETIC PHOTO PLACEHOLDER」と表示された模擬画像)。承認は開発用の模擬承認で、実案件の承認ではありません。"),
 ("table", ["区分", "内容"], [
   ["実装・検証済み", "案件作成 / 対象物Catalog登録 / 対象物追加・配置 / 寸法入力(mm・cm・m・in・ft) / 写真・注記 / 検証 / 干渉確認 / 作図プレビュー / レビュー・承認 / 出力 / オフライン作業 / 端末保存と再起動後の復元 / 手動送信 / 競合表示 / 復旧用エクスポート"],
   ["未実装", "写真からの自動作図・自動寸法抽出 / 寸法拘束(開口に収まるか等) / 扉・引出の開閉範囲の自動計算 / 分数インチ入力(1/2 等)"],
   ["未検証", "実際の現場端末(機種・OS・ブラウザ未確定)での動作、容量上限、本番サーバー(HTTPS)での運用、実認証"]]),
 ("p", "動作確認の範囲: Linux上のChromium 141(自動テスト)。タブレット等の対象端末での合格は報告していません。"))

sec("prep", "2. 最初の準備(オンラインが必要です)",
 ("p", "現場に出る前に、一度オンラインでアプリを開き、画面左の「0 同期・端末データ」で次を確認します。"),
 ("ul", ["アプリ本体のオフライン保存: 準備済み", "Python実行環境(検証ロジック本体、約14MB): 読込済み", "対象物Catalog(端末保存): 現場で使う定義が登録済み", "永続ストレージ: 「永続保存を要求」を押して許可を得る(端末が拒否する場合があります)"]),
 ("img", "10b_prepare_state_online.png", "図2-1 オフライン準備状態"),
 ("note", "初回の準備にはオンライン接続が必要です。準備前にオフラインで開くとアプリが起動しません。"))

sec("project", "3. 案件を作成する",
 ("p", "1 案件 >> 案件ID・部屋の幅/奥行/高さ・単位を入力 >> 「案件を作成」。案件IDは英数字と _ . - が使えます(最大64文字)。"),
 ("img", "09_project_created.png", "図3-1 案件を作成した直後。ヘッダーに案件ID・データ版・端末保存済みが表示される"))

sec("catalog", "4. 対象物Catalogを登録する",
 ("p", "2 対象物Catalog で、対象物の種類を登録します。寸法項目ごとに、軸(x=幅 / y=奥行 / z=高さ)・必須/任意・測定基準点・測定方法・許容差・有効範囲・出典を指定します。箱形状は幅・奥行・高さの必須項目が各1つ必要です。"),
 ("ul", ["同じIDで登録すると新しい版になります。すでに追加した対象物は登録時の版のままで、意味は変わりません。", "作業・保守・開閉に必要な空間は、奥行(mm)と根拠(必須)を入力した場合だけ登録されます。入力しなければ「未確認」と表示され、補完されません。"]),
 ("img", "10_catalog_prepared_online.png", "図4-1 登録済みCatalog一覧"))

sec("objects", "5. 対象物を追加し配置する",
 ("p", "3 対象物・配置 >> 対象物ID・Catalog定義・表示名 >> 追加。続いて各行で配置(x, y, z と単位、回転)を入力して「配置」。配置は対象物の最小隅(左・手前)の座標で、前面は回転0のとき +y 方向です。"),
 ("img", "11a_offline_objects.png", "図5-1 対象物の追加と配置"))

sec("dims", "6. 寸法を入力する",
 ("p", "4 寸法入力 >> 値・単位・区分(実測/写真推定)・測定者 >> 「入力」。入力した値は内部で mm(0.001mm単位)に換算して保持し、入力した元の文字列も記録します。"),
 ("table", ["表示", "意味", "扱い"], [
   ["実測", "現場で測った値。寸法の正本", "検証・干渉確認・承認の対象"],
   ["写真推定(未確認)", "写真等からの推定値", "承認不可。干渉確認は「未確認」"],
   ["未入力(未確認)", "値がない", "推測で補完しない。承認不可"],
   ["無効", "0以下、または有効範囲外", "エラー。修正が必要"]]),
 ("img", "11_offline_dims.png", "図6-1 寸法入力。30 in を入力すると 762.000 mm と換算される"))

sec("photos", "7. 写真と注記",
 ("p", "5 写真・注記 >> 写真タグを選び、ファイル(png/jpg/webp、8MBまで)を選択 >> 「添付」。必須写真と必須注記が揃うまで、検証でエラーになります。同じ写真ファイルを同じ対象物に重ねて添付することはできません(別のファイルを使ってください)。"),
 ("warn", "写真からの自動作図・自動寸法抽出は未実装です。写真は証跡として添付し、寸法は人が実測値を入力します。"),
 ("img", "12_offline_photos.png", "図7-1 写真の添付と注記"))

sec("check", "8. 検証結果を読む",
 ("p", "6 検証結果 には、入力検証と干渉確認が表示されます。干渉確認は3つに分けて表示します。"),
 ("table", ["区分", "意味", "判定"], [
   ["物体どうしの重なり", "2つの立体が同じ空間を占めていないか。面が接するだけ(0mm)は重なりではない", "PASS / FAIL"],
   ["物体間の距離(参考値)", "立体間の最短距離(各軸の隙間も併記)", "INFO(基準がないため合否なし)"],
   ["作業・保守・開閉に必要な空間", "Catalogに登録した奥行と根拠に基づき、その空間が他の物体や部屋の外に当たらないか", "PASS / FAIL / UNCHECKED"]]),
 ("note", "UNCHECKED(未確認)は合格ではありません。必要空間が未登録、寸法が未確定の物体がある、扉・引出の開閉範囲が未登録、のいずれかを意味します。承認するには理由の記入が必要です。FAILは承認できません。"),
 ("img", "13a_offline_check.png", "図8-1 検証結果"))

sec("preview", "9. 作図プレビュー",
 ("p", "7 作図プレビュー は実測で確定した対象物のみ描画します(写真推定・未入力・未配置は描かれず、凡例に未描画と表示)。点線は床から浮いた対象物です。未承認の版には透かしが入ります。"),
 ("img", "13_offline_preview.png", "図9-1 未承認の版の作図プレビュー(透かし入り)"))

sec("review", "10. レビューと承認",
 ("p", "8 レビュー・承認 >> 「この版をレビューに提出」 >> 確認事項をすべて確認 >> 承認者名と種類を指定 >> 承認。承認は表示中のデータ版とhashにだけ結び付き、承認後に1つでも値を変えると承認は失効します。"),
 ("ul", ["開発模擬承認: テスト用。実案件の承認ではなく、画面・出力に「開発模擬」と表示されます。", "Human最終承認: 実案件で、責任者本人が行う承認です(本書の画像には含まれません)。"]),
 ("img", "14a_review_before_approve.png", "図10-1 承認前の確認事項"),
 ("img", "14_offline_approved.png", "図10-2 承認後(開発模擬)"))

sec("export", "11. 出力",
 ("p", "9 出力 >> 平面図(SVG)・3Dモデル(OBJ)・manifest・snapshot を端末内で生成します(通信不要)。未承認の版には「UNAPPROVED PREVIEW」、開発模擬承認の版には「DEV SIMULATED APPROVAL」が入ります。manifestにはプロジェクトID・対象物ID・写真ID・データ版・内容hash・承認情報が記録されます。"),
 ("img", "14b_offline_export.png", "図11-1 出力"))

sec("offline", "12. オフライン作業と送信",
 ("p", "オフラインでも、案件・Catalog・対象物・採寸・単位・測定基準・写真・注記の入力ができ、端末に保存されます。アプリを終了して開き直しても、案件と写真は復元されます。"),
 ("table", ["表示", "意味"], [
   ["端末保存済み vN", "端末への書き込みが完了した版。書き込みに失敗したときは「保存失敗」と表示され、保存済みとは表示されません"],
   ["未送信", "サーバーに受領されていない版がある"],
   ["送信中 vN", "vN を送信している途中。その間に入力を変えると「新しい未送信版」も表示される"],
   ["サーバー受領済み revN", "サーバーが受領し、ハッシュと添付写真の件数を照合できた"],
   ["送信失敗", "理由を表示。端末内のデータは削除されない。再試行できる"]]),
 ("p", "送信手順(接続後に処理): オンラインに戻る >> 0 同期・端末データ >> 開発用ログイン >> 案件の「送信」。自動送信はしません。"),
 ("img", "15_offline_sync_pending.png", "図12-1 オフラインで作業した後。端末保存済みだが未送信"),
 ("img", "16_restored_after_restart.png", "図12-2 アプリを終了して再起動した後。写真も復元されている"),
 ("img", "17_synced.png", "図12-3 送信後。サーバー受領済み"))

sec("trouble", "13. トラブル対応",
 ("table", ["症状", "原因と対処"], [
   ["オフラインでアプリが開かない", "初回のオンライン準備が済んでいない。オンラインで一度開き、「0 同期・端末データ」の準備状態を確認する"],
   ["「保存失敗」と表示される", "端末の容量不足などで書き込めていません。変更は保存されていません。復旧用ファイルを書き出し、不要なデータを整理して再入力する。未送信データは自動削除されません"],
   ["送信失敗(通信)", "通信が切れた。接続を確認して「再試行」。再送しても重複登録されない"],
   ["送信失敗(認証期限切れ)", "再ログインして「再試行」。未送信データは端末に残っている"],
   ["送信失敗(競合)", "別の端末が先に更新した。「差分を表示」で内容を確認し、サーバー版の採用(この端末の版は端末内に退避)か、この端末の版での上書き(サーバーの旧版は履歴に残る)を選ぶ"],
   ["写真を添付できない", "png/jpg/webp以外、8MB超、または同じ写真が同じ対象物に添付済み"],
   ["承認できない", "入力検証エラー、干渉FAIL、確認事項の未チェック、未確認項目の理由未記入、表示した版が古い、のいずれか"],
   ["端末を交換・初期化する", "「復旧用ファイルを書き出す」で保存し、新しい端末で「読み込む」。既存の案件は上書きされない"]]),
 ("img", "18_send_failed_interrupted.png", "図13-1 送信中に通信が切れた場合"),
 ("img", "20_auth_expired.png", "図13-2 認証期限切れ"),
 ("img", "21_conflict_diff.png", "図13-3 競合と差分表示"),
 ("img", "22_save_failed_quota.png", "図13-4 保存失敗(容量不足を模擬)"),
 ("img", "23_backup_imported.png", "図13-5 復旧用ファイルの読み込み後"))

sec("limits", "14. 既知の制約",
 ("ul", ["動作確認はChromium(Linux)のみ。現場端末での永続保存・容量・再起動後の復元は未検証です。", "認証は開発用の仮方式です。本番運用の認証・HTTPS・サーバーは未整備です。", "干渉確認は軸に平行な箱形状が対象です。それ以外の形状は登録できません。", "容量不足の検証は、書き込み失敗を模擬した試験です(実際に端末を満杯にした試験ではありません)。"]))


def esc(t): return html.escape(t)

def render():
    toc = "".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t, _ in S)
    body = []
    for i, t, blocks in S:
        body.append(f'<section><h1 id="{i}">{esc(t)}</h1>')
        for b in blocks:
            if b[0] == "p": body.append(f"<p>{esc(b[1])}</p>")
            elif b[0] == "note": body.append(f'<p class="note">{esc(b[1])}</p>')
            elif b[0] == "warn": body.append(f'<p class="warn">{esc(b[1])}</p>')
            elif b[0] == "ul": body.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in b[1]) + "</ul>")
            elif b[0] == "table":
                body.append("<table><tr>" + "".join(f"<th>{esc(h)}</th>" for h in b[1]) + "</tr>" +
                            "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in b[2]) + "</table>")
            elif b[0] == "img":
                f = ROOT / "docs" / "screens" / b[1]
                if not f.exists(): sys.exit(f"missing screenshot {f}")
                body.append(f'<figure><img src="../screens/{b[1]}"><figcaption>{esc(b[2])}</figcaption></figure>')
        body.append('<p class="back"><a href="#toc">▲ 目次へ戻る</a></p></section>')
    css = """@page{size:A4;margin:16mm 16mm 18mm 16mm}
    body{font-family:'IPAGothic','IPAPGothic',sans-serif;font-size:10.5pt;line-height:1.6;color:#111}
    h1{font-size:16pt;border-bottom:2px solid #1f5fbf;padding-bottom:3pt;margin:0 0 8pt;page-break-after:avoid}
    section{page-break-before:always}.cover{text-align:center;padding-top:60mm}.cover h1{border:0;font-size:26pt}
    a{color:#1f5fbf;text-decoration:none}table{border-collapse:collapse;width:100%;margin:6pt 0;font-size:9.5pt}
    th,td{border:1px solid #999;padding:3pt 5pt;vertical-align:top;text-align:left}th{background:#e8eef8}
    figure{margin:8pt 0;text-align:center;page-break-inside:avoid}figure img{max-width:100%;max-height:205mm;border:1px solid #bbb}
    figcaption{font-size:9pt;color:#444}.note{background:#eef4ff;border-left:4px solid #1f5fbf;padding:4pt 6pt}
    .warn{background:#fff3d6;border-left:4px solid #b36b00;padding:4pt 6pt}.back{text-align:right;font-size:9pt}
    ul.toc{font-size:12pt;line-height:2;list-style:none;padding-left:0}"""
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>HOMURA Interior Field DX 現場アプリ 操作マニュアル</title><style>{css}</style></head><body>
    <div class="cover"><h1>HOMURA Interior Field DX<br>現場アプリ 操作マニュアル</h1><p>{VERSION}</p>
    <p class="warn" style="display:inline-block;text-align:left">画面・データはすべて合成データ。承認は開発用の模擬承認。<br>対象端末での動作は未検証。</p></div>
    <section id="toc"><h1>目次</h1><ul class="toc">{toc}</ul><p class="note">各項目をクリックすると該当ページへ移動します。PDFのしおり(ブックマーク)からも移動できます。</p></section>
    {''.join(body)}</body></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manual.html").write_text(doc, encoding="utf-8")
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"]); pg = b.new_page()
        pg.goto((OUT / "manual.html").as_uri()); pg.wait_for_load_state("load")
        pg.pdf(path=str(OUT / "HOA_Field_DX_Manual.pdf"), format="A4", print_background=True, outline=True, tagged=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;width:100%;text-align:center;font-family:IPAGothic">HOMURA Interior Field DX 操作マニュアル (開発版) — <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
               margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
        b.close()
    print("wrote", OUT / "HOA_Field_DX_Manual.pdf")

if __name__ == "__main__":
    render()
