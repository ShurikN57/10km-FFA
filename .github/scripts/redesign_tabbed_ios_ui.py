from pathlib import Path
import re

FILES=[Path('mobile.html'),Path('app base.html')]

CSS = r'''
/* ===== UI 2026 : navigation mobile par onglets ===== */
:root{
  --bg:#05070b;
  --panel:#11151d;
  --panel2:#1a1f29;
  --text:#f7f8fb;
  --muted:#929baa;
  --line:#2b3340;
  --accent:#4c91ff;
  --accent2:#2768e8;
}
body{
  background:radial-gradient(circle at 50% -12%,#121a27 0,#080b11 28%,#05070b 55%);
  padding-bottom:calc(106px + env(safe-area-inset-bottom));
}
.wrap{
  max-width:640px;
  padding:22px 18px 18px;
  padding-top:calc(22px + env(safe-area-inset-top));
}
.app-hero{padding:12px 3px 22px}
.app-hero h1{font-size:34px;line-height:1.04;letter-spacing:-1.1px;margin:0 0 9px;font-weight:850}
.app-base{font-size:14px;color:var(--muted);font-weight:550}
.tab-panel{display:none;animation:tabFade .18s ease}
.tab-panel.active{display:block}
@keyframes tabFade{from{opacity:.45;transform:translateY(4px)}to{opacity:1;transform:none}}
.card,.premium-card{
  background:linear-gradient(145deg,rgba(24,29,39,.98),rgba(13,17,24,.98));
  border:1px solid #303846;
  border-radius:24px;
  box-shadow:0 18px 45px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.025);
}
.premium-card{padding:20px 18px;margin-bottom:14px}
.section-head{display:flex;gap:13px;align-items:center;margin-bottom:17px}
.section-icon{
  width:52px;height:52px;flex:0 0 52px;border-radius:50%;display:grid;place-items:center;
  border:1px solid #3b4657;background:linear-gradient(145deg,#222a37,#151a23);
  color:var(--accent);box-shadow:inset 0 0 24px rgba(76,145,255,.05)
}
.section-icon svg{width:28px;height:28px;stroke:currentColor}
.section-copy{min-width:0}
.section-copy h2{margin:0 0 4px;font-size:21px;letter-spacing:-.35px}
.section-copy p{margin:0;color:var(--muted);font-size:13px;line-height:1.45}
input[type=search],input:not([type]),select{
  border:1px solid #343d4c!important;background:#1a1f28!important;color:var(--text)!important;
  border-radius:15px!important;min-height:48px;font-size:16px!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.02)
}
input::placeholder{color:#8b93a0;opacity:1}
button{border-radius:14px;border-color:#354050;background:#1b202a}
button.primary{
  background:linear-gradient(180deg,#347cf4,#2766d9)!important;
  border-color:#4a91ff!important;color:white!important;
  box-shadow:0 7px 18px rgba(39,102,217,.22)
}
button.primary:active{background:#2766d9!important}
.ffaRankModeBtn{min-height:46px}
.stats{grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.stat{
  background:linear-gradient(145deg,#1b212b,#141922);border:1px solid #303846;
  border-radius:18px;padding:15px 12px;text-align:left
}
.stat .n{font-size:26px;letter-spacing:-.4px}
.stat .l{font-size:12px;margin-top:3px}
.analysis-tools{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 12px}
.analysis-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:14px}
.tablewrap{border-radius:18px;border-color:#303846;background:#0f131a;overflow:hidden}
th{background:#141922}
#ffaFullResults{border-radius:18px!important;border-color:#303846!important;overflow:hidden}
#ffaAthleteSearchResults{border-radius:18px!important;border-color:#303846!important}
#ffaFullMsg{font-size:11px;color:#7f8997;min-height:0}
#ffaAthleteSearchMsg:empty{display:none}
.app-tabbar-shell{
  position:fixed;left:0;right:0;bottom:0;z-index:1000;
  padding:10px 14px calc(10px + env(safe-area-inset-bottom));
  pointer-events:none
}
.app-tabbar{
  max-width:610px;margin:0 auto;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;
  background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:30px;padding:6px;
  box-shadow:0 14px 40px rgba(0,0,0,.48);backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
  pointer-events:auto
}
.app-tab{
  min-height:62px;border:0;background:transparent;border-radius:24px;padding:8px 5px 7px;
  color:#c8ced8;font-size:11px;font-weight:650;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px
}
.app-tab svg{width:25px;height:25px;stroke:currentColor;fill:none;stroke-width:1.9}
.app-tab.active{background:linear-gradient(145deg,#373e49,#2c323c);color:#5b9dff;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.app-tab span{line-height:1}
.rank-filter-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:9px}
.rank-filter-grid select,.rank-filter-grid input{width:100%;padding:11px}
.rank-pagination{display:flex;gap:8px;margin-top:10px}
.rank-pagination button{flex:1}
#restoreCard{margin-bottom:12px}
@media(max-width:390px){
  .wrap{padding-left:14px;padding-right:14px}
  .app-hero h1{font-size:31px}
  .premium-card{padding:17px 14px}
  .section-head{gap:10px}
  .section-icon{width:46px;height:46px;flex-basis:46px}
}
'''

BODY = r'''<div class="wrap">
  <header class="app-hero">
    <h1>Comparateur 10 km</h1>
    <div id="baseStatus" class="app-base">Chargement de la base FFA…</div>
  </header>

  <main>
    <section class="tab-panel" data-app-panel="classement">
      <div class="premium-card" id="ffaRankingCard">
        <div class="section-head">
          <div class="section-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24"><path d="M8 4h8v4a4 4 0 0 1-8 0V4Z"/><path d="M8 6H5v1a4 4 0 0 0 4 4M16 6h3v1a4 4 0 0 1-4 4M12 12v5M9 20h6M10 17h4"/></svg>
          </div>
          <div class="section-copy">
            <h2>Classement FFA</h2>
            <p>Consultez et filtrez le classement complet des 10 km.</p>
          </div>
        </div>
        <input id="ffaFullSearch" type="search" placeholder="Rechercher nom / prénom..." style="width:100%;margin-bottom:9px">
        <div class="rank-filter-grid">
          <select id="ffaFullSex"><option value="">Tous sexes</option><option value="M">Hommes</option><option value="F">Femmes</option></select>
          <select id="ffaFullCategory"><option value="">Toutes catégories</option><option>CA</option><option>JU</option><option>ES</option><option>SE</option><option>M0</option><option>M1</option><option>M2</option><option>M3</option><option>M4</option><option>M5</option><option>M6</option><option>M7</option><option>M8</option><option>M9</option><option>M10</option></select>
          <input id="ffaFullYear" inputmode="numeric" placeholder="Année naissance">
          <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00">
        </div>
        <button type="button" id="ffaFullReset" style="width:100%;margin-bottom:8px">Réinitialiser les filtres</button>
        <div id="ffaFullMsg" class="msg" style="margin:2px 0 9px"></div>
        <div id="ffaFullResults" style="border:1px solid var(--line)"></div>
        <div class="rank-pagination">
          <button type="button" id="ffaFullPrev">Précédent</button>
          <button type="button" id="ffaFullNext">Suivant</button>
        </div>
      </div>
    </section>

    <section class="tab-panel active" data-app-panel="recherche">
      <div class="premium-card" id="ffaSearchCard">
        <div class="section-head">
          <div class="section-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24"><path d="M5 15h8M3 18h9M9 13l3-7 4 2 3 5-3 3-4-1-3-2Z"/><path d="M14 8l-1 3 3 2 3-1"/></svg>
          </div>
          <div class="section-copy">
            <h2>Rechercher un athlète FFA</h2>
            <p>Trouvez un athlète dans la base FFA et consultez son niveau.</p>
          </div>
        </div>
        <input id="ffaAthleteSearch" type="search" placeholder="Nom et prénom..." autocomplete="off" style="width:100%;margin:0">
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px">
          <button type="button" class="ffaRankModeBtn" data-mode="general" style="padding:9px 5px;font-size:12px">Général</button>
          <button type="button" class="ffaRankModeBtn" data-mode="sex" style="padding:9px 5px;font-size:12px">H/F</button>
          <button type="button" class="ffaRankModeBtn" data-mode="category" style="padding:9px 5px;font-size:12px">Catégorie</button>
        </div>
        <div id="ffaAthleteSearchMsg" class="msg" style="margin-top:8px"></div>
        <div id="ffaAthleteSearchResults" style="display:none;margin-top:8px;border:1px solid var(--line);overflow:hidden"></div>
      </div>
    </section>

    <section class="tab-panel" data-app-panel="analyse">
      <div class="premium-card">
        <div class="section-head">
          <div class="section-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24"><path d="M4 19V9h4v10M10 19V5h4v14M16 19v-7h4v7M3 21h18"/></svg>
          </div>
          <div class="section-copy">
            <h2>Analyse & comparaison</h2>
            <p>Analysez les participants importés depuis GoTiming ou UTMB.</p>
          </div>
        </div>

        <div class="card" id="restoreCard" style="display:none;padding:12px 14px">
          <div class="msg" style="margin-top:0">Un classement précédent est disponible.</div>
          <div class="toolbar" style="margin-top:8px"><button id="restoreBtn">Restaurer</button><button id="dismissRestoreBtn">Ignorer</button></div>
        </div>

        <textarea id="paste" aria-hidden="true" tabindex="-1" style="display:none"></textarea>
        <div id="raceMsg" class="msg" style="margin:0 0 9px;min-height:0"></div>

        <div class="stats">
          <div class="stat"><div class="n" id="sTotal">0</div><div class="l">Participants</div></div>
          <div class="stat"><div class="n" id="sExact">0</div><div class="l">Matchs exacts</div></div>
          <div class="stat"><div class="n" id="sAmb">0</div><div class="l">Ambigus</div></div>
          <div class="stat"><div class="n" id="sNone">0</div><div class="l">Non trouvés</div></div>
        </div>

        <input id="search" type="search" placeholder="Rechercher un coureur..." style="width:100%;margin-bottom:10px">
        <div class="analysis-tools"><button id="onlyFound">Trouvés</button><button id="onlyNo">Non trouvés</button></div>
        <div class="analysis-actions"><button id="export" class="primary">Export CSV</button><button id="clearRace">Effacer</button></div>

        <div class="tablewrap"><table><thead><tr><th data-key="pos" style="cursor:pointer">Pl. <span class="arrow"></span></th><th data-key="nom" style="cursor:pointer">Coureur <span class="arrow"></span></th><th>Temps</th><th data-key="pb" style="cursor:pointer">PB <span class="arrow"></span></th></tr></thead><tbody id="tbody"></tbody></table></div>
      </div>
    </section>
  </main>
</div>

<nav class="app-tabbar-shell" aria-label="Navigation principale">
  <div class="app-tabbar">
    <button type="button" class="app-tab" data-app-tab="classement" aria-label="Classement">
      <svg viewBox="0 0 24 24"><path d="M8 4h8v4a4 4 0 0 1-8 0V4Z"/><path d="M8 6H5v1a4 4 0 0 0 4 4M16 6h3v1a4 4 0 0 1-4 4M12 12v5M9 20h6"/></svg><span>Classement</span>
    </button>
    <button type="button" class="app-tab active" data-app-tab="recherche" aria-label="Recherche">
      <svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg><span>Recherche</span>
    </button>
    <button type="button" class="app-tab" data-app-tab="analyse" aria-label="Analyse">
      <svg viewBox="0 0 24 24"><path d="M12 3v9h9"/><path d="M19.8 15A9 9 0 1 1 9 4.2"/></svg><span>Analyse</span>
    </button>
  </div>
</nav>
'''

TAB_JS = r'''
let activeAppTab="recherche";
function switchAppTab(tab){
  if(!["classement","recherche","analyse"].includes(tab)) return;
  activeAppTab=tab;
  document.querySelectorAll("[data-app-panel]").forEach(p=>p.classList.toggle("active",p.getAttribute("data-app-panel")===tab));
  document.querySelectorAll("[data-app-tab]").forEach(b=>b.classList.toggle("active",b.getAttribute("data-app-tab")===tab));
  if(tab==="classement" && ffaReady && typeof renderFullFfaRanking==="function") renderFullFfaRanking(false);
  if(tab==="recherche" && ffaReady && typeof renderFfaAthleteSearch==="function") renderFfaAthleteSearch();
  window.scrollTo({top:0,behavior:"smooth"});
}
document.querySelectorAll("[data-app-tab]").forEach(btn=>btn.addEventListener("click",()=>switchAppTab(btn.getAttribute("data-app-tab"))));
'''

for path in FILES:
    if not path.exists():
        continue
    text=path.read_text(encoding='utf-8')

    if '/* ===== UI 2026 : navigation mobile par onglets ===== */' not in text:
        text=text.replace('</style>', CSS+'\n</style>', 1)

    # Replace the complete visual body while preserving the JavaScript engine.
    pattern=r'<div class="wrap">[\s\S]*?</div>\s*\n\s*<script>'
    new_text,count=re.subn(pattern, BODY+'\n\n<script>', text, count=1)
    if count!=1:
        raise SystemExit(f'{path}: main body block not found')
    text=new_text

    marker='const $ = id => document.getElementById(id);'
    if TAB_JS.strip() not in text:
        if marker not in text:
            raise SystemExit(f'{path}: JS marker not found')
        text=text.replace(marker, marker+'\n'+TAB_JS,1)

    # The ranking is now a dedicated tab: old open/close buttons no longer exist.
    text=re.sub(r'const _openFfaRanking=\$\("openFfaRanking"\);[\s\S]*?const _closeFfaRanking=\$\("closeFfaRanking"\);\nif\(_closeFfaRanking\)[^\n]*\n', '', text, count=1)

    # Switch automatically to Analyse after an imported race is parsed.
    old='''  compute();\n}'''
    new='''  compute();\n  if(parsed.length) switchAppTab("analyse");\n}'''
    if old in text and 'if(parsed.length) switchAppTab("analyse");' not in text:
        text=text.replace(old,new,1)

    # Base status becomes a clean subtitle rather than a badge.
    text=text.replace('''  $("baseStatus").textContent=ffa.length.toLocaleString("fr-FR")+" profils";''',
                      '''  $("baseStatus").textContent="Base FFA · "+ffa.length.toLocaleString("fr-FR")+" profils";''',1)

    path.write_text(text,encoding='utf-8')
