from pathlib import Path
p=Path('mobile.html')
s=p.read_text(encoding='utf-8')

# 1) Distance selector: four equal segments on one line.
s=s.replace('.distance-switch{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:0 0 14px;padding:5px;background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:18px}\n.distance-btn{min-height:44px;border:0!important;background:transparent!important;color:#c8ced8!important;border-radius:13px!important;font-size:14px!important;font-weight:800!important;padding:8px!important}\n.distance-btn.active{background:linear-gradient(180deg,#4c91ff,#3178e8)!important;color:#fff!important;box-shadow:0 5px 14px rgba(76,145,255,.20)}',
'''.distance-switch{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:2px;margin:0 0 14px;padding:4px;background:rgba(25,30,39,.88);border:1px solid #3a4350;border-radius:18px;overflow:hidden}\n.distance-btn{min-width:0;min-height:44px;border:0!important;background:transparent!important;color:#c8ced8!important;border-radius:13px!important;font-size:13px!important;font-weight:800!important;padding:8px 4px!important;white-space:nowrap}\n.distance-btn.active{background:linear-gradient(180deg,#4c91ff,#3178e8)!important;color:#fff!important;box-shadow:0 5px 14px rgba(76,145,255,.20)}''',1)

# 2) Search icons in ranking and athlete search fields.
needle='.ffa-search-wrap{position:relative}\n.ffa-search-wrap #ffaAthleteSearch{padding-right:42px!important}'
repl='''.ffa-search-wrap{position:relative}\n.ffa-search-wrap #ffaAthleteSearch{padding-left:46px!important;padding-right:42px!important}\n.ranking-search-wrap #ffaFullSearch{padding-left:42px!important}\n.search-field-icon{position:absolute;left:14px;top:50%;transform:translateY(-50%);width:22px;height:22px;pointer-events:none;color:#4c91ff;z-index:2}\n.search-field-icon svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}'''
if needle not in s: raise SystemExit('search CSS anchor not found')
s=s.replace(needle,repl,1)

# 3) Rank mode segmented control like reference capture.
insert='''\n.ffa-rank-mode-switch{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin-top:10px;padding:3px;border:1px solid #3a4350;border-radius:15px;background:#1a1f28;overflow:hidden}\n.ffa-rank-mode-switch .ffaRankModeBtn{min-width:0;min-height:44px!important;padding:8px 4px!important;border:0!important;border-radius:12px!important;background:transparent!important;color:#eef2f7!important;font-size:12px!important;font-weight:800!important;box-shadow:none!important}\n.ffa-rank-mode-switch .ffaRankModeBtn[data-mode].active,.ffa-rank-mode-switch .ffaRankModeBtn[style*="background"]{background:#3b82f6!important;color:#fff!important}\n'''
s=s.replace('.ffaRankModeBtn{min-height:46px}', '.ffaRankModeBtn{min-height:46px}'+insert,1)

# Ranking search icon markup.
old='''          <div class="ranking-search-wrap">\n            <input id="ffaFullSearch" type="search" placeholder="Nom, prénom..." autocomplete="off">'''
new='''          <div class="ranking-search-wrap">\n            <span class="search-field-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4 4"/></svg></span>\n            <input id="ffaFullSearch" type="search" placeholder="Nom, prénom..." autocomplete="off">'''
if old not in s: raise SystemExit('ranking search markup anchor not found')
s=s.replace(old,new,1)

# Athlete search icon + segmented control wrapper.
old='''        <div class="ffa-search-wrap">\n          <input id="ffaAthleteSearch" type="search" placeholder="Nom et prénom..." autocomplete="off" style="width:100%;margin:0">\n          <button type="button" id="ffaAthleteSearchClear" class="ffa-search-clear" aria-label="Effacer la recherche">×</button>\n        </div>\n        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px">'''
new='''        <div class="ffa-search-wrap">\n          <span class="search-field-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4 4"/></svg></span>\n          <input id="ffaAthleteSearch" type="search" placeholder="Nom et prénom..." autocomplete="off" style="width:100%;margin:0">\n          <button type="button" id="ffaAthleteSearchClear" class="ffa-search-clear" aria-label="Effacer la recherche">×</button>\n        </div>\n        <div class="ffa-rank-mode-switch">'''
if old not in s: raise SystemExit('athlete search markup anchor not found')
s=s.replace(old,new,1)

# Ensure current H/F button gets a class matching CSS rather than relying only on inline background.
# Keep existing JS behavior untouched; CSS also catches its inline background.

p.write_text(s,encoding='utf-8')
print('patched mobile.html')
