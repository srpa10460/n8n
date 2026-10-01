import * as db from "/db.js";
import * as bridge from "/bridge.js";
import * as sync from "/sync.js";

const SECTIONS=[["sync","0 同期・端末データ"],["project","1 案件"],["catalog","2 対象物Catalog"],["objects","3 対象物・配置"],["dims","4 寸法入力"],["photos","5 写真・注記"],["check","6 検証結果"],["preview","7 作図プレビュー"],["review","8 レビュー・承認"],["export","9 出力"]];
let S={units:["mm","cm","m","in","ft"],projects:[],catalog:{},catalogDict:{},projDicts:{},syncRecs:{},cur:null,detail:null,tab:"project",msg:null,err:null,exported:null,online:false,devAuth:false,saveInfo:null,photoURLs:{},ready:{sw:false,py:false,persist:null,usage:null,quota:null},busy:{},clientId:""};
const $=s=>document.querySelector(s);
const esc=t=>String(t??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
// F-1: allowlist IDs. HTML escape is NOT a JS security boundary. Never concat untrusted keys into code.
const ID_RE=/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
function needId(v,what="id"){if(typeof v!=="string"||!ID_RE.test(v))throw new Error("invalid "+what+": rejected (Fail Closed)");return v}
function isSafeId(v){return typeof v==="string"&&ID_RE.test(v)}
function attrId(v,what="id"){return isSafeId(v)?esc(v):""}
const badge=(t,cls)=>`<span class="badge b-${cls}">${esc(t)}</span>`;
const dimBadge=s=>({MEASURED:badge("実測","ok"),ESTIMATED:badge("写真推定(未確認)","warn"),MISSING:badge("未入力(未確認)","gray"),INVALID:badge("無効","ng")}[s]);
const stBadge=s=>({PASS:badge("PASS","ok"),FAIL:badge("FAIL","ng"),UNCHECKED:badge("UNCHECKED 未確認","warn"),INFO:badge("INFO 参考値","gray")}[s]||esc(s));
const unitOpts=sel=>S.units.map(u=>`<option ${u===(sel||"mm")?"selected":""}>${u}</option>`).join("");

async function act(fn,okmsg){
  document.querySelectorAll("#msg,#err").forEach(e=>e.remove());   // a stale message must never look like the result of this action
  S.msg=null;S.err=null;
  try{S.err=null;const j=await fn();await refresh(false);if(j&&j.project_id)S.detail=j;if(j&&j.exported)S.exported=j.exported;S.msg=okmsg?okmsg+"(端末に保存済み)":null;S.saveInfo={ok:true,at:new Date().toLocaleTimeString()}}
  catch(e){S.err=e.message;S.msg=null;if(e.saveFail)S.saveInfo={ok:false,at:new Date().toLocaleTimeString(),err:e.message}}
  render();ensurePhotoURLs();
}
async function refresh(rend=true){
  S.catalogDict=(await db.read("catalog","main"))||{};S.projDicts=await db.all("projects");S.syncRecs=await db.all("sync");
  S.projects=Object.values(S.projDicts).map(p=>({project_id:p.project_id,status:p.status,data_version:p.data_version,objects:Object.keys(p.instances).length}));
  try{if(bridge.ready()){const o=await bridge.call("detail",{catalog:S.catalogDict,project:S.cur?S.projDicts[S.cur]:null},{});S.catalog=o.result.catalog_view;if(S.cur)S.detail=o.result.detail}}catch(e){S.err=e.message}
  if(rend)render();
}
function go(t){S.tab=t;S.msg=S.err=null;render()}
function selectProject(id){S.cur=id;S.exported=null;refresh().then(()=>{go("objects");ensurePhotoURLs()})}

function header(){
  const netb=netBadge();
  const d=S.detail;
  if(!d){return '<span class="sub">案件未選択</span> '+netBadge()}
  const a=d.approval_current;
  const ap=a?badge(a.kind==="DEV_SIMULATED"?"承認済(開発模擬・実案件承認ではない)":"承認済(Human最終)",a.kind==="DEV_SIMULATED"?"warn":"ok"):badge("未承認","gray");
  return netb+` 案件 <b id="h-pid">${esc(d.project_id)}</b> ${badge(d.status,"gray")} データ版 <b id="h-ver">v${d.data_version}</b> <span class="mono" title="${esc(d.content_hash)}">hash ${esc(d.content_hash.slice(0,12))}</span> ${ap} ${badge("写真→自動作図: 未実装","warn")} ${saveBadge()} ${syncBadges(d.project_id)}`;
}
function renderNav(){$("#nav").innerHTML=SECTIONS.map(([k,l])=>`<button type="button" data-act="tab" data-tab="${k}" class="${S.tab===k?"on":""}">${l}</button>`).join("")}

function msgs(){return (S.msg?`<div class="notice" style="border-color:var(--ok);background:var(--okbg);color:var(--ok)" id="msg">${esc(S.msg)}</div>`:"")+(S.err?`<div class="err" id="err">${esc(S.err)}</div>`:"")}
function needProject(){return S.detail?"":'<div class="notice">先に「1 案件」で案件を作成/選択してください。</div>'}

const V={};
V.project=()=>`
<section class="card"><h2>案件の作成</h2>
 <div class="row">
 <label>案件ID<input id="np-id" placeholder="P-0001"></label>
 <label>幅<input id="np-w" size="6" value="2400"></label><label>奥行<input id="np-d" size="6" value="1800"></label><label>高さ<input id="np-h" size="6" value="2400"></label>
 <label>単位<select id="np-u">${unitOpts("mm")}</select></label>
 <button class="btn" id="np-go" type="button" data-act="create-project">案件を作成</button></div>
 <div class="sub">部屋の内寸(壁面間・床〜天井)。内部は mm (0.001mm単位)で保持します。</div></section>
<section class="card"><h2>案件一覧</h2>
 <table><tr><th>案件ID</th><th>状態</th><th>データ版</th><th>対象物数</th><th></th></tr>
 ${S.projects.map(p=>`<tr><td>${esc(p.project_id)}</td><td>${esc(p.status)}</td><td>v${p.data_version}</td><td>${p.objects}</td><td>${isSafeId(p.project_id)?`<button class="btn sec" type="button" data-act="open-project" data-open="${attrId(p.project_id)}">開く</button>`:badge("不正ID拒否","ng")}</td></tr>`).join("")||'<tr><td colspan="5" class="sub">案件なし</td></tr>'}</table></section>`;
function createProject(){try{needId($("#np-id").value.trim(),"project_id")}catch(e){S.err=e.message;S.msg=null;return render()}act(async()=>{const j=await api("/api/projects",{project_id:$("#np-id").value.trim(),w:$("#np-w").value,d:$("#np-d").value,h:$("#np-h").value,unit:$("#np-u").value});S.cur=j.project_id;return j},"案件を作成しました")}

V.catalog=()=>{
 const rows=Object.entries(S.catalog).map(([id,vs])=>{const l=vs[vs.length-1];return `<tr><td>${esc(id)}</td><td>${esc(l.name)}</td><td>${esc(l.category)}</td><td>v${l.version}${vs.length>1?` <span class="sub">(全${vs.length}版)</span>`:""}</td>
  <td>${l.dimensions.map(d=>esc(d.key)+(d.required?"*":"")+"("+esc(d.axis)+")").join(", ")}</td>
  <td class="sub">${l.required_spaces.map(s=>esc(s.kind)+":"+esc(s.side)+" "+esc(s.depth_mm)+"mm").join("; ")||"未定義"}${l.has_opening?" / 開閉あり":""}</td></tr>`}).join("");
 return `<section class="card"><h2>登録済みCatalog</h2>
 <table id="cat-table"><tr><th>ID</th><th>名称</th><th>カテゴリ</th><th>最新版</th><th>寸法項目 (*必須 / 軸)</th><th>必要な作業・保守空間</th></tr>${rows||'<tr><td colspan="6" class="sub">未登録</td></tr>'}</table>
 <p><button class="btn sec" id="cat-sample" type="button" data-act="catalog-sample">合成サンプルCatalogを読み込む (開発用・実仕様ではない)</button></p></section>
<section class="card"><h2>対象物の追加 / 新しい版の登録</h2>
 <div class="notice">同じIDで登録すると新しい版になります。既存の対象物は登録時の版に固定され、意味は変わりません。</div>
 <div class="row"><label>ID<input id="c-id" placeholder="vanity"></label><label>名称<input id="c-name"></label><label>カテゴリ<input id="c-cat"></label>
 <label>形状テンプレート<select id="c-shape"><option>box</option></select></label>
 <label>開閉(扉・引出)あり<select id="c-open"><option value="0">なし</option><option value="1">あり</option></select></label></div>
 <h3>寸法項目 (箱形状は 幅x・奥行y・高さz の必須項目が各1つ必要)</h3>
 <table id="c-dims"><tr><th>キー</th><th>名称</th><th>軸</th><th>必須</th><th>測定基準点</th><th>測定方法</th><th>許容差mm</th><th>最小mm</th><th>最大mm</th><th>出典</th></tr>
 ${[["width","幅","x"],["depth","奥行","y"],["height","高さ","z"]].map(([k,l,a],i)=>`<tr class="cd">
  <td><input data-f="key" size="8" value="${k}"></td><td><input data-f="label" size="6" value="${l}"></td>
  <td><select data-f="axis"><option ${a==="x"?"selected":""}>x</option><option ${a==="y"?"selected":""}>y</option><option ${a==="z"?"selected":""}>z</option></select></td>
  <td><select data-f="required"><option value="1">必須</option><option value="0">任意</option></select></td>
  <td><input data-f="datum" size="22" placeholder="例: 左外端〜右外端"></td><td><input data-f="method" size="10" placeholder="例: スチールテープ"></td>
  <td><input data-f="tolerance_mm" size="4" value="2"></td><td><input data-f="min_mm" size="5" value="10"></td><td><input data-f="max_mm" size="5" value="5000"></td><td><input data-f="source" size="10" placeholder="出典"></td></tr>`).join("")}</table>
 <div class="row" style="margin-top:8px"><label>必須写真タグ (カンマ区切り)<input id="c-photos" placeholder="front,wall-context" size="26"></label>
 <label>必須注記キー (カンマ区切り)<input id="c-ann" placeholder="plumbing-position" size="26"></label></div>
 <h3>必要な作業・保守・開閉空間 (入力値と根拠が必要。未入力なら「未確認」と表示されます)</h3>
 <div class="row"><label>種別<select id="s-kind"><option value="service">作業・保守</option><option value="opening">開閉範囲</option></select></label>
 <label>面<select id="s-side"><option value="front">前面</option><option value="back">背面</option><option value="left">左</option><option value="right">右</option><option value="top">上</option></select></label>
 <label>奥行(mm)<input id="s-depth" size="6"></label><label>根拠(必須)<input id="s-basis" size="34" placeholder="例: 機器メーカー仕様書 p.12"></label></div>
 <button class="btn" id="c-go" type="button" data-act="add-catalog">Catalogに登録</button></section>`}
function addCatalog(){
 const dims=[...document.querySelectorAll("tr.cd")].map(tr=>{const o={};tr.querySelectorAll("[data-f]").forEach(e=>o[e.dataset.f]=e.value);o.required=o.required==="1";return o});
 const csv=v=>v.split(",").map(x=>x.trim()).filter(Boolean);
 try{needId($("#c-id").value.trim(),"definition_id");dims.forEach(d=>needId(d.key,"dimension key"));csv($("#c-photos").value).forEach(t=>needId(t,"photo tag"));csv($("#c-ann").value).forEach(a=>needId(a,"annotation key"))}catch(e){S.err=e.message;S.msg=null;return render()}
 const spaces=$("#s-depth").value.trim()?[{kind:$("#s-kind").value,side:$("#s-side").value,depth_mm:$("#s-depth").value,basis:$("#s-basis").value}]:[];
 act(()=>api("/api/catalog",{definition_id:$("#c-id").value.trim(),name:$("#c-name").value.trim(),category:$("#c-cat").value.trim(),shape_template:$("#c-shape").value,has_opening:$("#c-open").value==="1",dimensions:dims,required_photos:csv($("#c-photos").value),required_annotations:csv($("#c-ann").value),required_spaces:spaces}),"Catalogに登録しました");
}

V.objects=()=>{
 if(!S.detail)return needProject();const d=S.detail;const defs=Object.keys(S.catalog);
 return `<section class="card"><h2>対象物を追加</h2>
 <div class="row"><label>対象物ID<input id="o-id" placeholder="O-VAN"></label><label>Catalog定義<select id="o-def">${defs.map(x=>`<option>${esc(x)}</option>`).join("")}</select></label><label>表示名<input id="o-label"></label>
 <button class="btn" id="o-go" type="button" data-act="add-object">追加 (最新版に固定)</button></div></section>
 <section class="card"><h2>配置</h2>
 <div class="sub">配置は対象物の最小隅(左・手前)の座標。前面は、回転0で +y 方向を向きます。回転は平面で反時計回り。部屋の内寸 ${esc(d.room.w)} x ${esc(d.room.d)} x ${esc(d.room.h)} mm。</div>
 <table><tr><th>ID</th><th>名称/定義版</th><th>配置 x,y,z (mm)</th><th>回転</th><th>配置入力</th></tr>
 ${d.instances.map(i=>`<tr data-obj="${esc(i.object_id)}"><td>${esc(i.object_id)}</td><td>${esc(i.label)}<div class="sub">${esc(i.definition.id)}@v${i.definition.version}${i.definition.latest_version>i.definition.version?` ${badge("新版v"+i.definition.latest_version+"あり(この対象物はv"+i.definition.version+"のまま)","warn")}`:""}</div></td>
 <td>${i.placement?`${esc(i.placement.x)}, ${esc(i.placement.y)}, ${esc(i.placement.z)}`:badge("未配置","gray")}</td><td>${i.placement?i.placement.rot+"°":""}</td>
 <td><input size="5" data-p="x" placeholder="x"> <input size="5" data-p="y" placeholder="y"> <input size="5" data-p="z" placeholder="z" value="0"> <select data-p="unit">${unitOpts("mm")}</select> <select data-p="rot"><option>0</option><option>90</option><option>180</option><option>270</option></select> ${isSafeId(i.object_id)?`<button class="btn sec" type="button" data-act="place" data-obj="${attrId(i.object_id)}">配置</button>`:badge("不正ID拒否","ng")}</td></tr>`).join("")||'<tr><td colspan="5" class="sub">対象物なし</td></tr>'}</table></section>`};
function addObject(){try{needId($("#o-id").value.trim(),"object_id");needId($("#o-def").value,"definition_id")}catch(e){S.err=e.message;S.msg=null;return render()}act(()=>api(`/api/projects/${S.cur}/instance`,{object_id:$("#o-id").value.trim(),definition_id:$("#o-def").value,label:$("#o-label").value.trim()}),"対象物を追加しました")}
function place(id,btn){id=needId(id,"object_id");const tr=btn.closest("tr");const g=k=>tr.querySelector(`[data-p=${k}]`).value;act(()=>api(`/api/projects/${S.cur}/place`,{object_id:id,x:g("x"),y:g("y"),z:g("z"),unit:g("unit"),rotation:g("rot")}),"配置しました")}

V.dims=()=>{
 if(!S.detail)return needProject();
 return `<div class="notice">凡例: ${dimBadge("MEASURED")} 現場で測った値(寸法の正本) / ${dimBadge("ESTIMATED")} 写真等からの推定(承認不可・干渉確認の対象外) / ${dimBadge("MISSING")} 入力なし。未入力の寸法は推測で補完しません。</div>`+
 S.detail.instances.map(i=>`<section class="card" data-obj="${esc(i.object_id)}"><h2>${esc(i.object_id)} ${esc(i.label)} <span class="sub">${esc(i.definition.id)}@v${i.definition.version}</span> ${i.confirmed?badge("寸法確定","ok"):badge("寸法未確定","warn")}</h2>
 <table><tr><th>項目</th><th>軸</th><th>測定基準点 / 方法 / 許容差 / 有効範囲</th><th>現在値</th><th>状態</th><th>入力</th></tr>
 ${i.dims.map(x=>`<tr data-key="${esc(x.key)}"><td>${esc(x.label)}${x.required?" *":""}<div class="sub">${esc(x.key)}</div></td><td>${esc(x.axis)}</td>
 <td class="sub">${esc(x.datum)} / ${esc(x.method)} / ±${esc(x.tolerance_mm)}mm / ${esc(x.min_mm)}〜${esc(x.max_mm)}mm<br>出典: ${esc(x.source)}</td>
 <td>${x.mm?`${esc(x.mm)} mm<div class="sub">入力: ${esc(x.input)}</div>`:"—"}${x.why?`<div class="sub">${esc(x.why)}</div>`:""}</td><td>${dimBadge(x.state)}</td>
 <td><input size="7" data-m="v" placeholder="値"> <select data-m="u">${unitOpts("mm")}</select> <select data-m="s"><option value="MEASURED">実測</option><option value="ESTIMATED_PHOTO">写真推定</option></select> <input size="8" data-m="by" placeholder="測定者"> ${(isSafeId(i.object_id)&&isSafeId(x.key))?`<button class="btn sec" type="button" data-act="measure" data-obj="${attrId(i.object_id)}" data-key="${attrId(x.key)}">入力</button>`:badge("不正キー拒否","ng")}</td></tr>`).join("")}</table></section>`).join("")||'<div class="sub">対象物なし</div>'};
function measure(o,k,btn){o=needId(o,"object_id");k=needId(k,"dimension key");const tr=btn.closest("tr");const g=c=>tr.querySelector(`[data-m=${c}]`).value;act(()=>api(`/api/projects/${S.cur}/measure`,{object_id:o,key:k,value:g("v"),unit:g("u"),source:g("s"),by:g("by")}),"寸法を記録しました")}

V.photos=()=>{
 if(!S.detail)return needProject();
 return `<div class="notice" id="no-auto">写真からの自動作図・自動寸法抽出は未実装です。写真は証跡として添付し、寸法は人が実測値を入力します。</div>`+
 S.detail.instances.map(i=>{const have=new Set(i.photos.map(p=>p.tag));const tags=[...new Set([...i.definition.required_photos,...i.photos.map(p=>p.tag)])];
 return `<section class="card" data-obj="${esc(i.object_id)}"><h2>${esc(i.object_id)} ${esc(i.label)}</h2>
 <div>必須写真: ${i.definition.required_photos.map(t=>have.has(t)?badge(t+" 済","ok"):badge(t+" 未","ng")).join(" ")||'<span class="sub">なし</span>'}</div>
 <div class="thumbs">${i.photos.map(p=>`<span><img src="${esc(S.photoURLs[S.cur+"/"+p.asset_id]||"")}" alt="${esc(p.tag)}" title="${esc(p.filename)} sha256:${esc((p.sha256||"").slice(0,12))}"></span>`).join("")}</div>
 <div class="row" style="margin-top:8px"><label>写真タグ<select data-ph="tag">${tags.map(t=>`<option>${esc(t)}</option>`).join("")}</select></label><label>ファイル(png/jpg/webp, 8MBまで)<input type="file" data-ph="file" accept="image/png,image/jpeg,image/webp"></label>
 ${isSafeId(i.object_id)?`<button class="btn sec" type="button" data-act="upload" data-obj="${attrId(i.object_id)}">添付</button>`:badge("不正ID拒否","ng")}</div>
 <h3>注記</h3>
 ${i.definition.required_annotations.map(k=>{const ok=isSafeId(i.object_id)&&isSafeId(k);return `<div class="row"><label style="min-width:160px">${esc(k)} (必須) ${i.annotations[k]?badge("入力済","ok"):badge("未入力","ng")}<input size="46" data-an="${ok?attrId(k):""}" value="${esc(i.annotations[k]||"")}" ${ok?"":"disabled"}></label>${ok?`<button class="btn sec" type="button" data-act="annot" data-obj="${attrId(i.object_id)}" data-key="${attrId(k)}">保存</button>`:badge("不正キー拒否","ng")}</div>`}).join("")||'<div class="sub">必須注記なし</div>'}
 </section>`}).join("")};
function upload(o,btn){o=needId(o,"object_id");const c=btn.closest("section");const f=c.querySelector("[data-ph=file]").files[0];const tag=c.querySelector("[data-ph=tag]").value;
 if(!f){S.err="ファイルを選択してください";return render()}
 needId(tag,"photo tag");
 S.msg=S.err=null;document.querySelectorAll("#msg,#err").forEach(e=>e.remove());   // file reading is async: clear the old result first
 const fr=new FileReader();fr.onload=()=>act(()=>api(`/api/projects/${S.cur}/photo`,{object_id:o,tag,filename:f.name,data_base64:fr.result.split(",")[1],_blob:f}),"写真を添付しました");fr.readAsDataURL(f)}
function annot(o,k,btn){o=needId(o,"object_id");k=needId(k,"annotation key");const v=btn.closest(".row").querySelector("input").value;act(()=>api(`/api/projects/${S.cur}/annotate`,{object_id:o,key:k,text:v}),"注記を保存しました")}

function checkTable(rs){return `<table><tr><th>対象</th><th>種別</th><th>判定</th><th>内容</th></tr>${rs.map(r=>`<tr><td class="mono">${esc(r.id)}</td><td>${esc(r.kind)}</td><td>${stBadge(r.status)}</td><td>${esc(r.reason)}</td></tr>`).join("")}</table>`}
V.check=()=>{
 if(!S.detail)return needProject();const d=S.detail;const iv=d.interference;
 const kinds={OVERLAP:"物体どうしの重なり",DISTANCE:"物体間の距離(参考値)",SERVICE:"作業・保守に必要な空間",OPENING:"開閉範囲",ROOM:"部屋の範囲内か"};
 return `<section class="card"><h2>入力検証</h2>${d.validation.length?`<table id="val-table"><tr><th>重大度</th><th>コード</th><th>対象</th><th>内容</th></tr>${d.validation.map(v=>`<tr><td>${v.severity==="ERROR"?badge("ERROR","ng"):badge("WARN","warn")}</td><td>${esc(v.code)}</td><td>${esc(v.object_id)}</td><td>${esc(v.detail)}</td></tr>`).join("")}</table>`:`<div id="val-ok">${badge("エラーなし","ok")}</div>`}</section>
 <section class="card"><h2>干渉確認 総合: <span id="ov">${iv.overall==="PASS"?badge("PASS","ok"):iv.overall==="FAIL"?badge("FAIL","ng"):badge("INCOMPLETE 未確認あり","warn")}</span></h2>
 <div class="sub">適用範囲: ${iv.scope.map(esc).join(" / ")}。未確認は合格として扱いません。</div>
 ${Object.entries(kinds).map(([k,l])=>{const rs=iv.results.filter(r=>r.kind===k);return rs.length?`<h3>${l}</h3>${checkTable(rs)}`:""}).join("")}</section>`};
V.preview=()=>{
 if(!S.detail)return needProject();
 return `<section class="card"><h2>作図プレビュー (平面・実測値のみで描画)</h2>
 <div class="sub">実測で確定した対象物のみ描かれます。写真推定・未入力・未配置の対象物は図に出ず、凡例に未描画と表示されます。点線は床から浮いた対象物(吊戸棚等)。未承認の図には透かしが入ります。</div>
 <img class="plan" id="plan-img" alt="plan" src="data:image/svg+xml;charset=utf-8,${encodeURIComponent(S.detail.plan_svg)}"></section>`};

V.review=()=>{
 if(!S.detail)return needProject();const d=S.detail,r=d.review;const a=d.approval_current;
 const blocked=r.validation_errors>0||r.fail.length>0;
 const labels={version_hash_seen:`承認対象は データ版 v${d.data_version} / hash ${d.content_hash.slice(0,12)} であることを確認した`,plan_seen:"「7 作図プレビュー」を確認した",dims_measured:"すべての必須寸法が実測値であることを確認した (写真推定の値はない)",interference_seen:"「6 検証結果」の干渉確認(FAIL=0)を確認した",no_estimates:"未確認として表示された項目の扱いを理解している",waivers_reasoned:"未確認(UNCHECKED)項目を承認する場合、理由を記入した"};
 return `<section class="card"><h2>レビュー対象版</h2>
 <table><tr><th>案件</th><td>${esc(d.project_id)}</td></tr><tr><th>状態</th><td>${esc(d.status)}</td></tr><tr><th>データ版</th><td id="rv-ver">v${d.data_version}</td></tr><tr><th>内容hash</th><td class="mono" id="rv-hash">${esc(d.content_hash)}</td></tr>
 <tr><th>入力検証エラー</th><td>${r.validation_errors}</td></tr><tr><th>干渉 FAIL</th><td>${r.fail.length?esc(r.fail.join(", ")):"なし"}</td></tr><tr><th>未確認(UNCHECKED)</th><td>${r.unchecked.length}件</td></tr><tr><th>写真推定の値</th><td>${r.estimated.length?esc(r.estimated.map(e=>e.join(".")).join(", ")):"なし"}</td></tr></table>
 ${a?`<div class="notice" style="border-color:var(--ok)">現在の版に有効な承認があります: ${a.kind==="DEV_SIMULATED"?"<b>開発模擬承認 (実案件の承認ではありません)</b>":"Human最終承認"} / ${esc(a.approver)} / v${a.version}</div>`:""}
 ${d.status==="DRAFT"?`<button class="btn" id="rv-submit" type="button" data-act="submit-review">この版をレビューに提出</button> <span class="sub">入力検証エラーがあると提出できません。</span>`:""}</section>
 ${d.status==="IN_REVIEW"?`<section class="card"><h2>承認 (この版のみ)</h2>
 ${blocked?`<div class="err">入力検証エラーまたは干渉FAILがあるため承認できません (免除不可)。</div>`:""}
 ${r.unchecked.length?`<h3>未確認項目 (承認するには各項目に理由が必要)</h3>${r.unchecked.map(u=>`<div class="row"><label style="min-width:280px"><span class="mono">${esc(u)}</span><input size="46" data-wv="${esc(u)}" placeholder="例: 現場で目視確認した 等"></label></div>`).join("")}`:""}
 <h3>確認事項</h3>${r.required_confirmations.map(c=>`<div><label style="flex-direction:row;align-items:center;gap:6px;color:var(--text);font-size:14px"><input type="checkbox" data-cf="${c}"> ${esc(labels[c])}</label></div>`).join("")}
 <div class="row" style="margin-top:8px"><label>承認者名<input id="ap-name" size="22"></label>
 <label>承認の種類<select id="ap-kind"><option value="DEV_SIMULATED">開発模擬承認 (テスト用・実案件の承認ではない)</option><option value="HUMAN_FINAL">Human最終承認 (実案件。責任者本人のみ)</option></select></label>
 <button class="btn" id="ap-go" type="button" data-act="approve" ${blocked?"disabled":""}>v${d.data_version} を承認</button></div>
 <div class="sub">承認は表示中のデータ版・hashに必須紐づけ(省略不可)。承認後にデータを変更すると承認は失効します。HUMAN_FINALは現段階では認証済み本人性を保証しません(F-4 OPEN / Production Gate)。</div></section>`:""}
 <section class="card"><h2>承認履歴</h2><table><tr><th>版</th><th>種類</th><th>承認者</th><th>日時</th><th>有効</th></tr>${d.approvals.map(x=>`<tr><td>v${x.approved_version}</td><td>${x.kind==="DEV_SIMULATED"?badge("開発模擬","warn"):badge("Human最終","ok")}</td><td>${esc(x.approver)}</td><td class="mono">${esc(x.at)}</td><td>${x.valid?badge("有効","ok"):badge("失効","ng")} <span class="sub">${esc(x.invalidated_reason)}</span></td></tr>`).join("")||'<tr><td colspan="5" class="sub">なし</td></tr>'}</table></section>
 <section class="card"><h2>変更履歴 (直近)</h2><div class="mono">${d.history.map(esc).join("<br>")}</div></section>`};
function approve(){
 const d=S.detail;const conf=[...document.querySelectorAll("[data-cf]")].filter(c=>c.checked).map(c=>c.dataset.cf);
 const wv={};document.querySelectorAll("[data-wv]").forEach(i=>{if(i.value.trim())wv[i.dataset.wv]=i.value.trim()});
 const nm=$("#ap-name").value,kd=$("#ap-kind").value;
 act(()=>api(`/api/projects/${S.cur}/approve`,{approver:nm,kind:kd,expect_version:d.data_version,expect_hash:d.content_hash,confirmations:conf,waivers:wv}),"承認しました").then(()=>{const a=$("#ap-name");if(a){a.value=nm;$("#ap-kind").value=kd;conf.forEach(c=>{const e=document.querySelector(`[data-cf=${c}]`);if(e)e.checked=true});Object.entries(wv).forEach(([k,v])=>{const e=document.querySelector(`[data-wv="${k}"]`);if(e)e.value=v})}});
}
V.export=()=>{
 if(!S.detail)return needProject();const d=S.detail;
 return `<section class="card"><h2>出力 (v${d.data_version})</h2>
 ${d.approval_current?`<div class="sub">この版は承認済みです${d.approval_current.kind==="DEV_SIMULATED"?" (開発模擬承認)":""}。</div>`:`<div class="notice">この版は未承認です。出力には「UNAPPROVED PREVIEW」が入ります。</div>`}
 <button class="btn" id="ex-go" type="button" data-act="export">平面図 SVG / 3D OBJ / manifest / snapshot を出力</button>
 ${S.exported?`<h3>生成物</h3><ul id="ex-list">${S.exported.map(f=>`<li><a href="${esc(f.url)}" download="${esc(f.name)}">${esc(f.name)}</a> <span class="sub">${f.bytes} bytes</span></li>`).join("")}</ul>`:""}
 <div class="sub">生成は端末内で完了します(通信不要)。再実行しても同じ内容になります。</div></section>`};

function render(){
 $("#hdr").innerHTML=header();renderNav();
 $("#main").innerHTML=msgs()+(V[S.tab]?V[S.tab]():"");
}


// ============ local API router: maps UI actions to engine ops, then persists to the device ============
class SaveError extends Error { constructor(m){super(m);this.saveFail=true} }
async function persist(writes){
  try{await db.writeAll(writes)}
  catch(e){throw new SaveError("保存失敗: 端末に保存されていません("+(e.name==="QuotaExceededError"?"端末の容量不足 — 不要な端末内データの整理やバックアップ後に再試行。未送信データは削除していません":e.message)+")")}
}
async function op(name,payload,{photo}={}){
  const state={catalog:S.catalogDict,project:S.cur?S.projDicts[S.cur]:null};
  const out=await bridge.call(name,state,payload);
  const ch=out.result._changed||[];
  const writes=[];
  const pid=out.state.project?.project_id;
  if(ch.includes("catalog"))writes.push(["catalog","main",out.state.catalog]);
  if(ch.includes("project")){
    writes.push(["projects",pid,out.state.project]);
    if(photo)writes.push(["photos",pid+"/"+out.result.asset_id,{blob:photo,sha256:out.result.meta.sha256,filename:out.result.meta.filename,project_id:pid}]);
    const old=S.syncRecs[pid]||{};
    writes.push(["sync",pid,{...old,project_id:pid,local_version:out.result.detail.data_version,local_hash:out.result.detail.content_hash,saved_at:Date.now()}]);
  }
  if(writes.length)await persist(writes);       // memory is updated only after the device confirmed the write
  if(ch.includes("project"))S.cur=pid;
  await refresh(false);
  return out.result;
}
async function api(path,b){
  if(path==="/api/catalog/sample")return op("load_sample_catalog",{});
  if(path==="/api/catalog")return op("publish_definition",b);
  if(path==="/api/projects")return (await op("create_project",b)).detail;
  const m=path.match(/^\/api\/projects\/[^/]+\/([a-z_]+)$/);if(!m)throw new Error("unknown action "+path);
  const a=m[1];
  if(a==="instance")return (await op("add_instance",b)).detail;
  if(a==="measure")return (await op("measure",b)).detail;
  if(a==="place")return (await op("place",b)).detail;
  if(a==="annotate")return (await op("annotate",b)).detail;
  if(a==="submit_review")return (await op("submit_review",{})).detail;
  if(a==="approve")return (await op("approve",b)).detail;
  if(a==="photo"){const {_blob,...rest}=b;return (await op("add_photo",rest,{photo:_blob})).detail}
  if(a==="export"){const r=await op("export",{});const t={"plan.svg":"image/svg+xml","model.obj":"text/plain","snapshot.json":"application/json","manifest.json":"application/json"};
    const d=r.detail;d.exported=Object.entries(r.files).map(([n,txt])=>({name:`${S.cur}_v${d.data_version}_${n}`,url:URL.createObjectURL(new Blob([txt],{type:t[n]||"text/plain"})),bytes:txt.length}));return d}
  throw new Error("unknown action "+a);
}
async function ensurePhotoURLs(){
  if(!S.detail)return;let ch=false;
  for(const i of S.detail.instances)for(const p of i.photos){const k=S.cur+"/"+p.asset_id;if(S.photoURLs[k])continue;
    const r=await db.read("photos",k);if(r?.blob){S.photoURLs[k]=URL.createObjectURL(r.blob);ch=true}}
  if(ch)render();
}

// ============ badges ============
function netBadge(){return (S.online?badge("オンライン","ok"):badge("オフライン — 端末内で作業中","warn"))+" "+(S.ready.py?badge("オフライン準備OK","ok"):badge("Python実行環境 未読込","warn"))}
function saveBadge(){const s=S.saveInfo;if(!s)return"";return s.ok?badge("端末保存済み "+s.at,"ok"):badge("保存失敗 — 端末に保存されていません","ng")}
function syncState(pid){
  const r=S.syncRecs[pid]||{};const pending=r.local_hash&&r.local_hash!==r.received_hash;
  if(r.state==="SENDING")return {tx:"SENDING",newer:r.sent_hash&&r.local_hash!==r.sent_hash};
  if(r.state==="CONFLICT")return {tx:"CONFLICT"};
  if(r.state==="FAILED")return {tx:"FAILED"};
  if(pending)return {tx:"UNSENT"};
  return {tx:r.received_hash?"RECEIVED":"UNSENT"};
}
function syncBadges(pid){
  const r=S.syncRecs[pid]||{};const s=syncState(pid);let h="";
  if(r.local_hash)h+=badge("端末保存済み v"+r.local_version,"ok")+" ";
  h+={SENDING:badge("送信中 v"+r.sent_version+(r.step?" ("+r.step+")":""),"warn")+(s.newer?" "+badge("新しい未送信版 v"+r.local_version,"gray"):""),
      CONFLICT:badge("送信失敗: 競合","ng"),FAILED:badge("送信失敗","ng"),UNSENT:badge("未送信"+(r.received_rev?" (最終受領 rev"+r.received_rev+"/v"+r.received_version+")":""),"warn"),
      RECEIVED:badge("サーバー受領済み rev"+r.received_rev+" v"+r.received_version,"ok")}[s.tx];
  return h;
}

// ============ 0: sync / device data ============
const fmtMB=b=>b==null?"?":(b/1048576).toFixed(1)+" MB";
V.sync=()=>{
 const e=S.ready;
 return `<section class="card"><h2>オフライン準備状態</h2>
 <table id="prep-table"><tr><th>アプリ本体のオフライン保存 (Service Worker)</th><td>${e.sw?badge("準備済み","ok"):badge("未準備 — 初回はオンラインで一度開く必要があります","warn")}</td></tr>
 <tr><th>Python実行環境 (検証ロジック本体)</th><td>${e.py?badge("読込済み","ok"):badge("未読込","warn")}</td></tr>
 <tr><th>対象物Catalog (端末保存)</th><td>${Object.keys(S.catalogDict).length}定義 ${Object.keys(S.catalogDict).length?badge("端末に保存済み","ok"):badge("未保存 — 現場へ出る前にCatalogを登録/取得してください","warn")}</td></tr>
 <tr><th>永続ストレージ</th><td>${e.persist===true?badge("許可済み","ok"):e.persist===false?badge("未許可(端末が自動削除する可能性あり)","warn"):"不明"} <button class="btn sec" type="button" data-act="request-persist">永続保存を要求</button></td></tr>
 <tr><th>端末の使用量 / 上限(見積)</th><td id="usage">${fmtMB(e.usage)} / ${fmtMB(e.quota)}</td></tr>
 <tr><th>サーバー接続</th><td>${S.online?badge("接続可","ok"):badge("接続不可 — 送信・Catalog取得は「接続後に処理」","warn")} ${S.devAuth?"":'<span class="sub">(サーバー認証未設定)</span>'}</td></tr></table>
 <div class="notice">前提条件: 初回の準備(アプリ本体・Python実行環境 約14MB・Catalogの保存)にはオンライン接続が必要です。以後はオフラインで 案件/Catalog/対象物/採寸/単位/測定基準/写真/注記 を扱えます。写真は端末(IndexedDB)に保存され、アプリ終了・再起動後も復元されます。端末内の未送信データは自動削除しません。対象端末(機種/OS/ブラウザ)は未確定のため、端末での永続保存・容量はまだ検証していません。</div>
 <div class="row"><button class="btn sec" id="login" type="button" data-act="dev-login" ${S.online&&S.devAuth?"":"disabled"}>開発用ログイン (接続後に処理)</button>
 <button class="btn sec" id="fetch-cat" type="button" data-act="fetch-catalog" ${S.online?"":"disabled"}>サーバーからCatalog取得 (接続後に処理)</button></div></section>
 <section class="card"><h2>案件の送信状況</h2><table id="sync-table"><tr><th>案件</th><th>状態</th><th>詳細 / 失敗理由</th><th>操作</th></tr>
 ${Object.keys(S.projDicts).map(pid=>{const r=S.syncRecs[pid]||{};const s=syncState(pid);const busy=!!S.busy[pid];
  return `<tr data-pid="${esc(pid)}"><td>${esc(pid)}</td><td>${syncBadges(pid)}</td>
  <td class="sub">${r.error?`<span style="color:var(--ng)">${esc(r.error)}</span><br>`:""}${r.attempts?"試行 "+r.attempts+"回":""}${s.tx==="RECEIVED"?` / 添付 ${r.received_assets}件をサーバーで照合済み`:""}
  ${r.conflict?`<br>競合: サーバー rev${esc(r.conflict.server_rev)} (別端末 ${esc(r.conflict.server_client_id)} v${esc(r.conflict.server_data_version)}) との差分 ${r.conflict.diff.length}件`:""}</td>
  <td>${isSafeId(pid)?`<button class="btn" type="button" data-act="send" data-send="${attrId(pid)}" ${(!S.online||busy||s.tx==="RECEIVED"||s.tx==="CONFLICT")?"disabled":""}>${s.tx==="FAILED"?"再試行":"送信"}</button>`:badge("不正ID拒否","ng")}${!S.online?' <span class="sub">接続後に処理</span>':""}
  ${s.tx==="CONFLICT"&&isSafeId(pid)?`<button class="btn sec" type="button" data-act="show-diff" data-pid="${attrId(pid)}">差分を表示</button>`:""}</td></tr>`}).join("")||'<tr><td colspan="4" class="sub">案件なし</td></tr>'}</table>
 <div id="diff-area"></div>
 <div class="sub">送信は手動です。送信中に入力を変更しても、送信対象の版(v)と新しい未送信版を区別して表示します。サーバーが受領した内容(ハッシュ・添付数)を照合できるまで「サーバー受領済み」にはなりません。</div></section>
 <section class="card"><h2>復旧用エクスポート / インポート</h2>
 <div class="sub">端末内の全案件・写真・Catalog・送信状況を1ファイルに書き出します(写真のSHA-256付き)。端末故障や容量不足に備え、定期的に保存してください。インポートは既存の案件を上書きしません。</div>
 <div class="row" style="margin-top:8px"><button class="btn" id="bk-export" type="button" data-act="backup-export">復旧用ファイルを書き出す</button>
 <label>復旧用ファイルを読み込む<input type="file" id="bk-file" accept="application/json"></label><button class="btn sec" id="bk-import" type="button" data-act="backup-import">読み込む</button></div>
 <div id="bk-report" class="sub"></div></section>`};
async function doSend(pid){
  S.busy[pid]=true;S.err=S.msg=null;render();
  try{await sync.send(pid,()=>{refresh(false).then(()=>{$("#hdr").innerHTML=header();if(S.tab==="sync")render()})});S.msg="サーバー受領済みを確認しました: "+pid}
  catch(e){S.err="送信失敗("+(e.kind||"?")+"): "+e.message}
  S.busy[pid]=false;await refresh(false);render();
}
function showDiff(pid){
  const r=S.syncRecs[pid];const c=r.conflict;if(!c)return;
  $("#diff-area").innerHTML=`<h3>競合の差分 (ローカル ↔ サーバー rev${esc(c.server_rev)})</h3>
  <table id="diff-table"><tr><th>項目</th><th>この端末</th><th>サーバー</th></tr>${c.diff.map(d=>`<tr><td class="mono">${esc(d.path)}</td><td>${esc(JSON.stringify(d.local))}</td><td>${esc(JSON.stringify(d.server))}</td></tr>`).join("")||'<tr><td colspan="3" class="sub">差分なし(版情報のみ相違)</td></tr>'}</table>
  <div class="notice">自動で上書きしません。どちらかを選んでください。<br>・サーバー版を採用: この端末の版は復旧用に端末内へ退避してから置き換えます。<br>・この端末の版で上書き: サーバーの旧版は履歴として残り、新しい版として送信されます。</div>
  <button class="btn sec" id="adopt" type="button" data-act="adopt" data-pid="${attrId(pid)}">サーバー版を採用 (この端末の版は退避)</button>
  <button class="btn" id="override" type="button" data-act="override" data-pid="${attrId(pid)}">この端末の版で上書き送信の準備</button>`;
}
async function adopt(pid){await act(async()=>{await sync.adoptServer(pid);S.projDicts=await db.all("projects");return null},"サーバー版を採用しました(この端末の旧版は退避済み)")}
async function overrideSrv(pid){await act(async()=>{await sync.rebaseForOverwrite(pid);return null},"上書き準備ができました")}
async function devLogin(){await act(async()=>{await sync.devLogin(Number(window.__ttl||3600));return null},"ログインしました (開発用トークン)")}
async function fetchCatalog(){await act(async()=>{const t=(await db.read("meta","token"))?.token;const r=await fetch("/api/sync/catalog",{headers:{Authorization:"Bearer "+(t||"")}});const j=await r.json();if(!r.ok)throw new Error(j.error||"HTTP "+r.status);
  const o=await bridge.call("merge_catalog",{catalog:S.catalogDict,project:null},{catalog:j.catalog});if(o.result._changed.length)await persist([["catalog","main",o.state.catalog]]);return null},"Catalogを取得し端末に保存しました")}
async function requestPersist(){S.ready.persist=await db.requestPersist();await refreshStorage();render()}
async function exportBackup(){await act(async()=>{const b=await sync.exportBackup();const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="hoa-backup-"+new Date().toISOString().replace(/[:.]/g,"-")+".json";a.click();$("#bk-report").textContent="書き出しました: "+a.download+" ("+b.size+" bytes)";return null},"復旧用ファイルを書き出しました")}
async function importBackup(){const f=$("#bk-file").files[0];if(!f){S.err="ファイルを選択してください";return render()}
  await act(async()=>{const rep=await sync.importBackup(await f.text());S.pendingReport=rep;return null},"読み込みました");
  if(S.pendingReport){const r=S.pendingReport;$("#bk-report").textContent=`取り込み: ${r.imported.join(",")||"なし"} / スキップ: ${r.skipped.join(",")||"なし"} / 破損写真: ${r.bad_photos.join(",")||"なし"}`}}
async function refreshStorage(){const i=await db.storageInfo();S.ready.persist=i.persisted;S.ready.usage=i.usage;S.ready.quota=i.quota}

// ============ init ============
async function checkSW(){
  try{const reg=await navigator.serviceWorker.getRegistration();const c=await caches.open("hoa-field-shell-v1");
    S.ready.sw=!!(reg&&reg.active)&&!!(await c.match("/vendor/pyodide/pyodide.asm.wasm"))}catch(_){S.ready.sw=false}
}
async function pollNet(){
  const before=JSON.stringify([S.online,S.devAuth,S.ready.sw,S.ready.py,S.ready.persist]);
  const p=await sync.ping();S.online=p.online;S.devAuth=p.dev_auth;await refreshStorage();await checkSW();
  $("#hdr").innerHTML=header();   // header only: never wipe a form the user is typing in
  if(before!==JSON.stringify([S.online,S.devAuth,S.ready.sw,S.ready.py,S.ready.persist])&&S.tab==="sync")render();
}
function onUIClick(ev){
  const btn=ev.target.closest("[data-act]");
  if(!btn||btn.disabled)return;
  const name=btn.dataset.act;
  try{
    if(name==="tab")return go(needId(btn.dataset.tab,"tab"));
    if(name==="create-project")return createProject();
    if(name==="open-project")return selectProject(needId(btn.dataset.open,"project_id"));
    if(name==="catalog-sample")return act(()=>api("/api/catalog/sample",{}),"合成サンプルを読み込みました");
    if(name==="add-catalog")return addCatalog();
    if(name==="add-object")return addObject();
    if(name==="place")return place(btn.dataset.obj,btn);
    if(name==="measure")return measure(btn.dataset.obj,btn.dataset.key,btn);
    if(name==="upload")return upload(btn.dataset.obj,btn);
    if(name==="annot")return annot(btn.dataset.obj,btn.dataset.key,btn);
    if(name==="submit-review")return act(()=>api(`/api/projects/${S.cur}/submit_review`,{}),"レビューに提出しました");
    if(name==="approve")return approve();
    if(name==="export")return act(()=>api(`/api/projects/${S.cur}/export`,{}),"出力しました");
    if(name==="request-persist")return requestPersist();
    if(name==="dev-login")return devLogin();
    if(name==="fetch-catalog")return fetchCatalog();
    if(name==="send")return doSend(needId(btn.dataset.send,"project_id"));
    if(name==="show-diff")return showDiff(needId(btn.dataset.pid,"project_id"));
    if(name==="adopt")return adopt(needId(btn.dataset.pid,"project_id"));
    if(name==="override")return overrideSrv(needId(btn.dataset.pid,"project_id"));
    if(name==="backup-export")return exportBackup();
    if(name==="backup-import")return importBackup();
  }catch(e){S.err=e.message;S.msg=null;render()}
}
async function init(){
  // Test hooks only. No inline onclick; UI uses data-* + event delegation (F-1).
  Object.assign(window,{act,api,go,selectProject,createProject,addCatalog,addObject,place,measure,upload,annot,approve,doSend,showDiff,adopt,overrideSrv,devLogin,fetchCatalog,requestPersist,exportBackup,importBackup,needId,ID_RE,__S:S,__db:db});
  document.addEventListener("click",onUIClick);
  render();
  if("serviceWorker" in navigator){try{await navigator.serviceWorker.register("/sw.js")}catch(e){S.err="Service Worker登録失敗: "+e.message}}
  try{await bridge.load();S.ready.py=true}catch(e){S.err=e.message}
  try{S.clientId=await sync.clientId();await sync.interruptedToFailed()}catch(e){S.err="端末ストレージを開けません: "+e.message}
  await refresh(false);
  window.addEventListener("online",pollNet);window.addEventListener("offline",pollNet);
  await pollNet();setInterval(pollNet,5000);
  window.__ready=true;
}
init();
