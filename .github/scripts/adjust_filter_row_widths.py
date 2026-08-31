from pathlib import Path

for path in [Path('mobile.html'), Path('app base.html')]:
    t = path.read_text(encoding='utf-8')

    # Give row 1 and row 3 their own sizing rules while leaving row 2 untouched.
    old_html = '''        <div class="rank-filter-grid">\n          <input id="ffaFullSearch" type="search" placeholder="Rechercher nom / prénom...">\n          <input id="ffaFullYear" inputmode="numeric" placeholder="Année naissance">\n        </div>\n        <div class="rank-filter-grid">\n          <select id="ffaFullSex"><option value="">Tous sexes</option><option value="M">Hommes</option><option value="F">Femmes</option></select>\n          <select id="ffaFullCategory"><option value="">Toutes catégories</option><option>CA</option><option>JU</option><option>ES</option><option>SE</option><option>M0</option><option>M1</option><option>M2</option><option>M3</option><option>M4</option><option>M5</option><option>M6</option><option>M7</option><option>M8</option><option>M9</option><option>M10</option></select>\n        </div>\n        <div class="rank-filter-grid">\n          <input id="ffaFullMinPb" inputmode="numeric" placeholder="PB min, ex 30:00">\n          <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00">\n        </div>'''
    new_html = '''        <div class="rank-filter-grid rank-filter-grid-identity">\n          <input id="ffaFullSearch" type="search" placeholder="Rechercher nom / prénom...">\n          <input id="ffaFullYear" inputmode="numeric" placeholder="Année naissance">\n        </div>\n        <div class="rank-filter-grid">\n          <select id="ffaFullSex"><option value="">Tous sexes</option><option value="M">Hommes</option><option value="F">Femmes</option></select>\n          <select id="ffaFullCategory"><option value="">Toutes catégories</option><option>CA</option><option>JU</option><option>ES</option><option>SE</option><option>M0</option><option>M1</option><option>M2</option><option>M3</option><option>M4</option><option>M5</option><option>M6</option><option>M7</option><option>M8</option><option>M9</option><option>M10</option></select>\n        </div>\n        <div class="rank-filter-grid rank-filter-grid-pb">\n          <input id="ffaFullMinPb" inputmode="numeric" placeholder="PB min, ex 30:00">\n          <input id="ffaFullMaxPb" inputmode="numeric" placeholder="PB max, ex 35:00">\n        </div>'''
    if old_html not in t:
        raise SystemExit(f'Filter HTML block not found in {path}')
    t = t.replace(old_html, new_html, 1)

    old_css = '''.rank-filter-grid{display:grid;grid-template-columns:.88fr 1.12fr;gap:8px;margin-bottom:9px}\n.rank-filter-grid select,.rank-filter-grid input{width:100%;min-width:0;padding:11px}\n.rank-filter-grid select{font-size:14px!important;padding:11px 24px 11px 10px}'''
    new_css = '''.rank-filter-grid{display:grid;grid-template-columns:.88fr 1.12fr;gap:8px;margin-bottom:9px}\n.rank-filter-grid-identity{grid-template-columns:1.45fr .75fr}\n.rank-filter-grid-pb{grid-template-columns:1fr 1fr}\n.rank-filter-grid select,.rank-filter-grid input{width:100%;min-width:0;padding:11px}\n.rank-filter-grid-pb input{height:48px;min-height:48px;margin:0}\n.rank-filter-grid select{font-size:14px!important;padding:11px 24px 11px 10px}'''
    if old_css not in t:
        raise SystemExit(f'Filter CSS block not found in {path}')
    t = t.replace(old_css, new_css, 1)

    path.write_text(t, encoding='utf-8')
